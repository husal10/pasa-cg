"""
pasa_cg.sensors.pasa_plus
===========================
Earlier three-stage preprocessor (per-lane plausibility filter, opposing-arm
maximum, phase-conditional exponential smoothing). Kept so that older result
files can be reproduced; not used in the papers.

    pp = PASAPlusPreprocessor(lanes_per_arm=3)
    pp.reset()                               # once per episode
    agg = pp.process(readings, phase=0, step=t)
"""

from __future__ import annotations

import math
import numpy as np


# Constants

ARM_ORDER   = ["N", "S", "E", "W"]
PHASE_PAIRS = [("N", "S"), ("E", "W")]   # NS = phase 0; EW = phase 1

Q_MAX       = 20.0    # max plausible queue (veh)
LAMBDA_DECAY= 0.10    # L1 stuck-high decay rate  (e^{-lambda*delta t})
DT_STEP     = 10.0    # decision step (s) - must match env.DECISION_STEP

ALPHA_FAST  = 0.70    # L3 EWMA - discharge / fast mode
ALPHA_BASE  = 0.25    # L3 EWMA - default
BOOST_MAX   = 0.15    # L3 cross-direction consistency boost (absolute)

STUCK_THRESH_FRAC = 0.90  # fraction of Q_max that triggers stuck-high check


# PASAPlusPreprocessor

class PASAPlusPreprocessor:
    """Full PASA+ pipeline (L1 -> L2 -> L3).

    Parameters
    ----------
    lanes_per_arm : int   Number of lanes per approach arm (default 4).
    q_max         : float Saturation capacity (veh).
    lambda_decay  : float L1 stuck-high decay coefficient.
    alpha_fast    : float L3 EWMA fast (discharge) weight.
    alpha_base    : float L3 EWMA base weight.
    boost_max     : float Maximum cross-direction alpha boost.
    dt            : float Decision step size (s).
    """

    def __init__(
        self,
        lanes_per_arm: int   = 4,
        q_max:         float = Q_MAX,
        lambda_decay:  float = LAMBDA_DECAY,
        alpha_fast:    float = ALPHA_FAST,
        alpha_base:    float = ALPHA_BASE,
        boost_max:     float = BOOST_MAX,
        dt:            float = DT_STEP,
    ):
        self.lanes_per_arm = lanes_per_arm
        self.q_max         = q_max
        self.lambda_decay  = lambda_decay
        self.alpha_fast    = alpha_fast
        self.alpha_base    = alpha_base
        self.boost_max     = boost_max
        self.dt            = dt

        self.n_lanes      = lanes_per_arm * 4
        self.n_aggregates = lanes_per_arm * 2   # NS + EW pairs

        # Arm slices into the (n_lanes,) reading vector
        self._arm_slices: dict[str, slice] = {
            arm: slice(i * lanes_per_arm, (i + 1) * lanes_per_arm)
            for i, arm in enumerate(ARM_ORDER)
        }

        # L1 state
        self._red_max: np.ndarray   # per-lane max seen during red phase
        self._in_green: np.ndarray  # bool per lane - currently green phase?

        # L3 state
        self._ewma: np.ndarray      # shape (n_aggregates,)
        self._prev_phase: int

        self.reset()

    # public API

    def reset(self) -> None:
        """Reset all layer states (call at episode start).

        _red_max is seeded to q_max so the phase-monotonicity check does not
        zero out lanes on the very first green transition (cold-start artefact).
        """
        self._red_max   = np.full(self.n_lanes, self.q_max)
        self._in_green  = np.zeros(self.n_lanes, dtype=bool)
        self._ewma      = np.zeros(self.n_aggregates)
        self._prev_phase = -1

    def process(
        self,
        readings:  np.ndarray,
        phase:     int,
        step:      int = 0,
        is_green:  np.ndarray | None = None,
    ) -> np.ndarray:
        """Run full PASA+ pipeline on *readings*.

        Parameters
        ----------
        readings : np.ndarray, shape (n_lanes,)
            Raw queue counts.
        phase : int
            Current signal phase (0 = NS green, 1 = EW green).
        step : int
            Simulation step counter (unused here, kept for API consistency).
        is_green : np.ndarray | None, shape (n_lanes,)
            Boolean mask - True if that lane's approach is currently in green.
            Derived from *phase* when not provided.

        Returns
        -------
        np.ndarray, shape (n_aggregates,)
            PASA+ smoothed aggregates.
        """
        readings = np.asarray(readings, dtype=float)

        if is_green is None:
            is_green = self._phase_to_green_mask(phase)

        # L1: plausibility filter
        q_hat = self._layer1(readings, is_green)

        # L2: phase-pair max
        agg = self._layer2(q_hat)

        # L3: phase-conditional EWMA
        smoothed = self._layer3(agg, phase)

        return smoothed

    # L1

    def _layer1(self, readings: np.ndarray, is_green: np.ndarray) -> np.ndarray:
        q_hat = readings.copy()

        # (1) Capacity clip
        q_hat = np.clip(q_hat, 0.0, self.q_max)

        # (2) Stuck-high rejection: during green, high reading -> decay
        stuck_mask = is_green & (q_hat >= self.q_max * STUCK_THRESH_FRAC)
        q_hat[stuck_mask] = q_hat[stuck_mask] * math.exp(-self.lambda_decay * self.dt)

        # (3) Phase-monotonicity: cap at max seen during red for newly-green lanes
        newly_green = is_green & ~self._in_green
        for i in np.where(newly_green)[0]:
            q_hat[i] = min(q_hat[i], self._red_max[i])

        # Track red-phase maximums
        red_mask = ~is_green
        self._red_max[red_mask] = np.maximum(
            self._red_max[red_mask], q_hat[red_mask]
        )
        self._in_green = is_green.copy()

        return q_hat

    # L2

    def _layer2(self, q_hat: np.ndarray) -> np.ndarray:
        """Max aggregation over opposing arm pairs -> shape (n_aggregates,)."""
        aggs = []
        for a1, a2 in PHASE_PAIRS:
            q1 = q_hat[self._arm_slices[a1]]
            q2 = q_hat[self._arm_slices[a2]]
            aggs.append(np.maximum(q1, q2))
        return np.concatenate(aggs)

    # L3

    def _layer3(self, agg: np.ndarray, phase: int) -> np.ndarray:
        """Phase-conditional EWMA with adaptive alpha and cross-direction boost."""
        phase_changed = (phase != self._prev_phase)
        self._prev_phase = phase

        if phase_changed:
            # Hard reset on phase transition
            self._ewma = agg.copy()
            return self._ewma.copy()

        # Split aggregates into NS and EW halves
        half = self.n_aggregates // 2
        ns_agg = agg[:half]
        ew_agg = agg[half:]
        ns_ewma = self._ewma[:half]
        ew_ewma = self._ewma[half:]

        # Adaptive alpha
        # Discharge: phase 0 (NS green) -> NS discharges -> use alpha_fast for NS
        ns_alpha = self._compute_alpha(ns_agg, ns_ewma, active=(phase == 0))
        ew_alpha = self._compute_alpha(ew_agg, ew_ewma, active=(phase == 1))

        # Cross-direction consistency boost
        ns_alpha = self._cross_boost(ns_alpha, ew_agg, ew_ewma)
        ew_alpha = self._cross_boost(ew_alpha, ns_agg, ns_ewma)

        # EWMA update
        self._ewma[:half] = ns_alpha * ns_agg + (1 - ns_alpha) * ns_ewma
        self._ewma[half:] = ew_alpha * ew_agg + (1 - ew_alpha) * ew_ewma

        return self._ewma.copy()

    def _compute_alpha(
        self,
        agg:    np.ndarray,
        ewma:   np.ndarray,
        active: bool,
    ) -> float:
        """Choose alpha: fast when discharging (phase is green for this pair)."""
        if active:
            # Discharge check: current aggregate < previous smoothed value
            if np.mean(agg) < np.mean(ewma):
                return self.alpha_fast
        return self.alpha_base

    def _cross_boost(
        self,
        alpha:       float,
        cross_agg:   np.ndarray,
        cross_ewma:  np.ndarray,
    ) -> float:
        """Boost alpha when opposing direction shows consistent trend (reduces lag)."""
        consistency = 1.0 - np.mean(np.abs(cross_agg - cross_ewma)) / (self.q_max + 1e-9)
        boost = self.boost_max * max(0.0, consistency)
        return min(1.0, alpha + boost)

    # helpers

    def _phase_to_green_mask(self, phase: int) -> np.ndarray:
        """Boolean mask - True for lanes in the active (green) phase.

        phase 0 -> NS green (arm indices 0,1 -> lanes 0..2*lpa-1)
        phase 1 -> EW green (arm indices 2,3 -> lanes 2*lpa..4*lpa-1)
        """
        mask = np.zeros(self.n_lanes, dtype=bool)
        lpa = self.lanes_per_arm
        if phase == 0:
            mask[0:2*lpa] = True   # N + S
        else:
            mask[2*lpa:]  = True   # E + W
        return mask

    def __repr__(self) -> str:
        return (
            f"PASAPlusPreprocessor("
            f"lanes_per_arm={self.lanes_per_arm}, "
            f"q_max={self.q_max}, "
            f"alpha_base={self.alpha_base}, alpha_fast={self.alpha_fast})"
        )
