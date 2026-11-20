"""
pasa_itsc.sensors.pasa
======================
Opposing-arm aggregation of lane readings (N with S, E with W, lane by lane).

    mean : a_i = (q_N,i + q_S,i) / 2
    max  : a_i = max(q_N,i, q_S,i)

use_l1=True adds an earlier per-lane plausibility filter before aggregation
(capacity clip, stuck-high rejection, phase monotonicity); it is not used in the papers.

Lane order: [N0..N(L-1), S.., E.., W..].

    pasa = PASAPreprocessor(lanes_per_arm=3, aggregation="max", use_l1=False)
    agg  = pasa.aggregate(readings)          # shape (2 * lanes_per_arm,)
"""

from __future__ import annotations

import math
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARM_ORDER    = ["N", "S", "E", "W"]
PHASE_PAIRS  = [("N", "S"), ("E", "W")]   # NS = phase 0; EW = phase 1

Q_MAX             = 20.0    # max plausible queue (veh)
LAMBDA_DECAY      = 0.10    # L1 stuck-high decay rate  (e^{-lambda*dt})
DT_STEP           = 10.0    # decision step (s) -- must match env.DECISION_STEP
STUCK_THRESH_FRAC = 0.90    # fraction of Q_max that triggers stuck-high check


# ---------------------------------------------------------------------------
# PASAPreprocessor
# ---------------------------------------------------------------------------

class PASAPreprocessor:
    """Unified Phase-Aware Structural Aggregation preprocessor.

    Parameters
    ----------
    lanes_per_arm : int
        Number of lanes per approach arm (default 3 for grid2x2).
    q_max : float
        Saturation capacity (veh) -- used for clip and stuck-high test.
    aggregation : {"mean", "max"}
        L2 aggregation rule over opposing arm pairs.
        "mean" : average of opposing pair  -- fault attenuation 50%
        "max"  : element-wise max          -- G1 (HZ recovery), G2 (noise ~36%)
    use_l1 : bool
        Apply L1 plausibility filter.
        False : stateless -- capacity clip only.
        True  : stateful -- clip + stuck-high rejection + phase-monotonicity.
    lambda_decay : float
        L1 stuck-high exponential decay coefficient (used when use_l1=True).
    dt : float
        Decision step duration in seconds (used when use_l1=True).
    """

    def __init__(
        self,
        lanes_per_arm:    int   = 3,
        q_max:            float = Q_MAX,
        aggregation:      str   = "mean",
        use_l1:           bool  = False,
        lambda_decay:     float = LAMBDA_DECAY,
        dt:               float = DT_STEP,
    ):
        if aggregation not in ("mean", "max"):
            raise ValueError(
                f"aggregation must be 'mean' or 'max', got {aggregation!r}"
            )

        self.lanes_per_arm = lanes_per_arm
        self.q_max         = q_max
        self.aggregation   = aggregation
        self.use_l1        = use_l1
        self.lambda_decay  = lambda_decay
        self.dt            = dt

        self.n_lanes      = lanes_per_arm * 4
        self.n_aggregates = lanes_per_arm * 2   # NS-pair * lpa + EW-pair * lpa

        # Arm index slices into the (n_lanes,) reading vector
        self._arm_slices: dict[str, slice] = {
            arm: slice(i * lanes_per_arm, (i + 1) * lanes_per_arm)
            for i, arm in enumerate(ARM_ORDER)
        }

        # L1 state (populated by reset(); only used when use_l1=True)
        self._red_max:  np.ndarray  # per-lane max seen during red
        self._in_green: np.ndarray  # bool per lane -- currently in green?

        self.reset()

    # -- public API -----------------------------------------------------------

    def reset(self) -> None:
        """Reset stateful L1 layer (call at episode start).

        _red_max is seeded to q_max so the phase-monotonicity check does not
        clamp lanes to zero on the very first green transition (cold-start
        artefact).  When use_l1=False this is a no-op but kept for API
        consistency with PASAPlusPreprocessor.
        """
        self._red_max  = np.full(self.n_lanes, self.q_max)
        self._in_green = np.zeros(self.n_lanes, dtype=bool)

    def aggregate(self, readings: np.ndarray) -> np.ndarray:
        """Stateless path: capacity clip + L2 aggregation (no L1 filter).

        Appropriate for use_l1=False variants (pasa_mean_mp, pasa_max_mp).
        May also be called on use_l1=True instances; L1 state is NOT updated.

        Parameters
        ----------
        readings : np.ndarray, shape (n_lanes,)
            Raw or fault-injected lane queue counts.

        Returns
        -------
        np.ndarray, shape (n_aggregates,)
            Phase-pair aggregates (NS first, then EW).
        """
        q_hat = np.clip(np.asarray(readings, dtype=float), 0.0, self.q_max)
        return self._aggregate(q_hat)

    def process(
        self,
        readings: np.ndarray,
        phase:    int,
        step:     int = 0,
    ) -> np.ndarray:
        """Full pipeline: L1 filter (if enabled) + L2 aggregation.

        Stateful when use_l1=True -- updates _red_max and _in_green.
        When use_l1=False, identical to aggregate() (stateless path).

        Parameters
        ----------
        readings : np.ndarray, shape (n_lanes,)
            Raw or fault-injected lane queue counts.
        phase : int
            Current signal phase (0 = NS green, 1 = EW green).
            Required for the L1 plausibility filter; ignored when use_l1=False.
        step : int
            Simulation step counter (kept for API parity with
            PASAPlusPreprocessor).

        Returns
        -------
        np.ndarray, shape (n_aggregates,)
            Phase-pair aggregates after L1 (if enabled) and L2.
        """
        readings = np.asarray(readings, dtype=float)

        if self.use_l1:
            is_green = self._phase_to_green_mask(phase)
            q_hat    = self._layer1(readings, is_green)
        else:
            q_hat = np.clip(readings, 0.0, self.q_max)

        return self._aggregate(q_hat)

    def filter_lanes(self, readings: np.ndarray, phase: int) -> np.ndarray:
        """L1 only, no L2: per-lane plausibility-filtered readings (stateful when
        use_l1=True). Used by the l1_mp control to separate L1 from L2."""
        readings = np.asarray(readings, dtype=float)
        if self.use_l1:
            return self._layer1(readings, self._phase_to_green_mask(phase))
        return np.clip(readings, 0.0, self.q_max)

    def arm_readings(self, readings: np.ndarray) -> dict[str, np.ndarray]:
        """Return dict {arm: readings_array} for debugging / plotting."""
        readings = np.clip(np.asarray(readings, dtype=float), 0.0, self.q_max)
        return {arm: readings[sl] for arm, sl in self._arm_slices.items()}

    # -- L1 plausibility filter -----------------------------------------------

    def _layer1(self, readings: np.ndarray, is_green: np.ndarray) -> np.ndarray:
        """L1 plausibility filter.

        (1) Capacity clip       : q_hat = clip(q, 0, Q_max)
        (2) Stuck-high rejection: during green, if q_hat >= 0.9*Q_max ->
                                  exponential decay q_hat *= e^{-lambda*dt}
        (3) Phase-monotonicity  : on green onset, cap at max seen during red
        """
        q_hat = readings.copy()

        # (1) Capacity clip
        q_hat = np.clip(q_hat, 0.0, self.q_max)

        # (2) Stuck-high rejection during green
        stuck_mask = is_green & (q_hat >= self.q_max * STUCK_THRESH_FRAC)
        if np.any(stuck_mask):
            decay = math.exp(-self.lambda_decay * self.dt)
            q_hat[stuck_mask] *= decay

        # (3) Phase-monotonicity: cap newly-green lanes at their red-phase max
        newly_green = is_green & ~self._in_green
        for idx in np.where(newly_green)[0]:
            q_hat[idx] = min(q_hat[idx], self._red_max[idx])

        # Update red-phase maximum tracking
        red_mask = ~is_green
        self._red_max[red_mask] = np.maximum(
            self._red_max[red_mask], q_hat[red_mask]
        )
        self._in_green = is_green.copy()

        return q_hat

    # -- L2 aggregation -------------------------------------------------------

    def _aggregate(self, q_hat: np.ndarray) -> np.ndarray:
        """L2: aggregate over opposing arm pairs -> shape (n_aggregates,)."""
        aggs = []
        for a1, a2 in PHASE_PAIRS:
            q1 = q_hat[self._arm_slices[a1]]
            q2 = q_hat[self._arm_slices[a2]]
            if self.aggregation == "mean":
                aggs.append((q1 + q2) / 2.0)
            else:  # "max"
                aggs.append(np.maximum(q1, q2))
        return np.concatenate(aggs)

    # -- helpers --------------------------------------------------------------

    def _phase_to_green_mask(self, phase: int) -> np.ndarray:
        """Boolean mask -- True for lanes in the active (green) phase.

        phase 0 -> NS green  (arm indices 0,1 -> lanes 0 .. 2*lpa-1)
        phase 1 -> EW green  (arm indices 2,3 -> lanes 2*lpa .. 4*lpa-1)
        """
        mask = np.zeros(self.n_lanes, dtype=bool)
        lpa  = self.lanes_per_arm
        if phase == 0:
            mask[0 : 2 * lpa] = True   # N + S
        else:
            mask[2 * lpa :]   = True   # E + W
        return mask

    def __repr__(self) -> str:
        return (
            f"PASAPreprocessor("
            f"lanes_per_arm={self.lanes_per_arm}, "
            f"aggregation={self.aggregation!r}, "
            f"use_l1={self.use_l1}, "
            f"q_max={self.q_max})"
        )
