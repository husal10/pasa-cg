"""
pasa_itsc.controllers.max_pressure
==================================
Max-pressure phase selection for a two-phase junction (Varaiya 2013).

    W_l   = x_l - x_out,l              lane weight (x_out = 0 when no downstream input)
    P_S   = sum over lanes l of phase S of c_l * max(0, W_l)
    S*    = argmax_S P_S               ties keep the current phase

select_phase(upstream, downstream=None) chooses the mode from the input length:
    n_arms x lanes_per_arm inputs   per-lane mode (std_mp, std_mp_q, pasa_cg_mp, ...)
    n_phases x lanes_per_arm inputs aggregated mode (pasa_mean_mp, pasa_max_mp, ...)

With downstream=None the pressure of a phase is the sum of its lane queues
(queue-only max-pressure). Averaging the two opposing readings scales both
phase pressures by the same factor and therefore never changes the decision;
verify.py checks this in SUMO.

Reference
---------
Varaiya, P. (2013). The max-pressure controller for arbitrary networks of
signalized intersections. Transportation Research Part C, 36, 177-195.
"""

from __future__ import annotations

import numpy as np
from typing import Sequence


class MaxPressureController:
    """Exact Varaiya (2013) Max-Pressure controller.

    Parameters
    ----------
    lanes_per_arm : int
        Lanes per approach arm.  Also the number of aggregate slots per phase
        in PASA/PASA+ aggregated mode (default 4).
    n_phases : int
        Number of signal phases.  For a 4-arm 2-phase intersection: 2.
    n_arms : int
        Total approach arms (default 4).  Stored for documentation; the
        controller auto-detects mode from len(upstream_queues) at call time.
    sat_flow_weights : Sequence[float] | None
        Saturation-flow weights, one per lane within a phase (length =
        lanes_per_arm).  None -> uniform weights of 1.0.

    Note
    ----
    No min-green or max-green constraints are applied.  The phase is
    re-evaluated every decision step (10 s) and switches immediately when
    a different phase has higher pressure.

    The pressure formula and inputs differ by variant:

      std_mp (Varaiya 2013, full):
          P_S = sum _{l in S} c_l * max(0, x_in_l - x_out_l)
          upstream  = raw/faulted per-lane queue counts (12 lanes)
          downstream = TraCI outgoing-lane halting counts
          -> Spillback-aware; downstream queues penalise oversaturated exits.

      pasa_mp / pasa_plus_mp (aggregate argmax):
          P_NS = sum  PASA_agg_NS,   P_EW = sum  PASA_agg_EW
          upstream  = PASA or PASA+ phase-pair aggregates (6 values)
          downstream = None -> x_out zeroed; no spillback term
          -> Argmax selects the phase whose fault-processed aggregate sum
            is larger; not equivalent to full Varaiya under faulty sensors.

    Yellow-phase insertion (3 s) is handled externally by the environment
    whenever the selected phase differs from the previous one.
    """

    def __init__(
        self,
        lanes_per_arm:    int                    = 4,
        n_phases:         int                    = 2,
        n_arms:           int                    = 4,
        sat_flow_weights: Sequence[float] | None = None,
    ):
        self.lanes_per_arm = lanes_per_arm
        self.n_phases      = n_phases
        self.n_arms        = n_arms

        # backward-compat: aggregated-mode input length
        self.n_aggregates  = lanes_per_arm * n_phases

        self._weights: np.ndarray = (
            np.ones(lanes_per_arm)
            if sat_flow_weights is None
            else np.asarray(sat_flow_weights, dtype=float)
        )

        self._current_phase: int = 0

    def select_phase(
        self,
        upstream_queues:   np.ndarray,
        downstream_queues: np.ndarray | None = None,
    ) -> int:
        """Select phase with maximum Varaiya (2013) pressure.

        Parameters
        ----------
        upstream_queues : ndarray, shape (n_inputs,)
            Queue counts on approach lanes (or PASA/PASA+ aggregates).

            Full mode (Std-MP):
                n_inputs = n_arms x lanes_per_arm = 12 for the 2x2 grid.
                Lanes must be ordered so that the first n_inputs // n_phases
                entries correspond to phase-0 arms (N+S) and the remaining
                entries to phase-1 arms (E+W).  This is consistent with the
                deduplication order returned by SUMO's getControlledLanes()
                after _unique_lanes() filtering.

            Aggregated mode (PASA-MP / PASA+-MP):
                n_inputs = n_phases x lanes_per_arm = 6.
                downstream_queues should be None.

        downstream_queues : ndarray or None, shape (n_inputs,)
            Downstream outgoing-lane queue counts (x_out term).
            None  -> x_out = 0 for all inputs (no spillback prevention;
                    standard for aggregated mode).
            array -> full Varaiya (2013): W_i = max(0, x_in_i - x_out_i);
                    standard for Std-MP full mode.

        Returns
        -------
        int
            Selected phase index.
        """
        upstream  = np.asarray(upstream_queues, dtype=float)
        n_inputs  = len(upstream)
        # Mode dispatch:
        #   std_mp  (downstream_queues provided):
        #       W_l = max(0, x_in_l - x_out_l)  - Varaiya (2013) Eq. 3
        #   pasa_mp / pasa_plus_mp (downstream_queues=None):
        #       P_phase = sum of PASA/PASA+ aggregates for that phase
        #       No max(0,...) clamp - aggregates are compared directly;
        #       the phase with the higher aggregate sum wins.
        if downstream_queues is None:
            # PASA / PASA+ mode: use aggregates directly (no x_out, no clamp)
            W = np.asarray(upstream_queues, dtype=float)
        else:
            # Std-MP full mode: Varaiya (2013) movement weights
            x_out = np.asarray(downstream_queues, dtype=float)
            W = np.maximum(0.0, upstream - x_out)

        # Auto-detect inputs-per-phase from vector length
        inputs_per_phase = n_inputs // self.n_phases

        # Broadcast sat-flow weights: extend or trim to inputs_per_phase.
        c = np.ones(inputs_per_phase)
        n_w = min(len(self._weights), inputs_per_phase)
        c[:n_w] = self._weights[:n_w]

        # Phase pressure: P_S = sum_{i in S} c_i * W_i   (Varaiya 2013, Sec. III)
        # Active phase S covers exactly one contiguous block of inputs.
        pressures = np.array([
            np.dot(W[p * inputs_per_phase : (p + 1) * inputs_per_phase], c)
            for p in range(self.n_phases)
        ])

        # Argmax over phase pressures - re-evaluated every decision step (10 s).
        # No min-green / max-green constraints.
        #
        # std_mp    : pressures computed as sum  max(0, x_in - x_out)  (Varaiya 2013)
        # pasa_* : pressures are sum  PASA/PASA+ aggregates; x_out zeroed (no downstream term)
        #
        # Yellow insertion handled externally by the environment when phase changes.
        # Ties keep the current phase (no needless switch). np.argmax alone
        # would always resolve ties to phase 0 (NS), biasing results towards
        # whichever phase happens to be indexed first.
        best = np.flatnonzero(np.isclose(pressures, pressures.max()))
        cur = getattr(self, "_current_phase", None)
        self._current_phase = int(cur) if cur is not None and cur in best else int(best[0])
        return self._current_phase

    def compute_pressures(
        self,
        upstream_queues:   np.ndarray,
        downstream_queues: np.ndarray | None = None,
    ) -> np.ndarray:
        """Return Varaiya (2013) pressure per phase without changing state.

        Returns
        -------
        np.ndarray, shape (n_phases,)
            Pressure value for each phase.
        """
        upstream = np.asarray(upstream_queues, dtype=float)
        n_inputs = len(upstream)
        if downstream_queues is None:
            W = np.asarray(upstream_queues, dtype=float)
        else:
            x_out = np.asarray(downstream_queues, dtype=float)
            W     = np.maximum(0.0, upstream - x_out)
        inputs_per_phase = n_inputs // self.n_phases
        c = np.ones(inputs_per_phase)
        n_w = min(len(self._weights), inputs_per_phase)
        c[:n_w] = self._weights[:n_w]
        return np.array([
            np.dot(W[p * inputs_per_phase : (p + 1) * inputs_per_phase], c)
            for p in range(self.n_phases)
        ])

    def reset(self) -> None:
        """Reset internal phase state (call at the start of each episode)."""
        self._current_phase = 0

    @property
    def current_phase(self) -> int:
        """Currently active phase index."""
        return self._current_phase

    def __repr__(self) -> str:
        return (
            f"MaxPressureController("
            f"lanes_per_arm={self.lanes_per_arm}, "
            f"n_phases={self.n_phases}, "
            f"n_arms={self.n_arms})"
        )
