"""
pasa_cg.sensors.fault_modes
=============================
Detector faults applied per lane to the queue readings (veh).

HZ  dead          reads 0
SL  stuck         frozen at the last non-zero reading
GN  noise         additive Gaussian noise
ID  dropout       reads 0 with a fixed probability per decision
DR  drift         positive offset that grows over the run
SH  stuck at max  reads q_max
ND  negative drift under-count that grows over the run
GA  gain          reads gain x true queue
MX  mixed         each faulty lane draws one of HZ/SL/GN/ID/DR (not used in the papers)

The magnitudes used in the papers are set by FAULT_SEVERITY in env/sumo_env.py
(severity "high").

    fi = FaultInjector(n_lanes=12, fault_mode="HZ", fault_fraction=1.0, seed=0)
    faulted = fi.inject(readings, step=t)
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Literal


# Constants / type alias

FaultMode = Literal["HZ", "SL", "GN", "ID", "DR", "SH", "ND", "GA", "MX", "NONE"]
# Additional fault types: SH stuck at maximum (reads q_max), ND negative drift
# (under-count growing to drift_total), GA gain fault (reads gain x true queue).

Q_MAX_DEFAULT = 20.0      # vehicles (capacity per lane approach)
NOISE_SIGMA   = Q_MAX_DEFAULT / 4.0   # GN standard deviation
DROPOUT_RATE  = 0.3       # ID: P(drop at any step)
DRIFT_RATE    = 0.05      # DR: veh/step drift increment (expected)


# FaultInjector

@dataclass
class FaultInjector:
    """Injects sensor faults into a vector of raw queue readings.

    Parameters
    ----------
    n_lanes : int
        Total number of sensor lanes per intersection.
    fault_mode : FaultMode
        Which fault to apply.  "NONE" returns readings unchanged.
    fault_fraction : float
        Fraction of lanes that are faulty  (0 -> 1).
    q_max : float
        Saturation capacity (clips all readings if they exceed this).
    seed : int | None
        RNG seed for reproducibility.
    """
    n_lanes:        int       = 16
    fault_mode:     FaultMode = "NONE"
    fault_fraction: float     = 0.25   # 25 % of sensors faulty
    q_max:          float     = Q_MAX_DEFAULT
    seed:           int | None = 42
    # Optional lane groups that share ONE physical sensor (e.g. a camera/radar
    # covering a whole approach). Lanes in a group share the MX sub-mode and
    # the ID dropout events. None -> every lane is an independent sensor (loops).
    groups:         list | None = None
    # Fault magnitudes (defaults = legacy constants; the env passes the
    # severity-scaled values, see FAULT_SEVERITY in sumo_env.py).
    noise_sigma:    float = NOISE_SIGMA     # GN: std of additive noise (veh)
    drift_rate:     float = DRIFT_RATE      # DR: mean drift per injection call (veh)
    dropout_rate:   float = DROPOUT_RATE    # ID: P(reading dropped) per call
    # MX: None -> random sub-mode per sensor (legacy); int -> balanced rotation,
    # so across mx_index = 0..4 every sensor takes every sub-mode exactly once.
    mx_index:       int | None = None
    gain:           float = 0.5           # GA: reading = gain x true queue

    # internal state (post-init)
    _rng:       np.random.Generator          = field(init=False, repr=False)
    _faulty:    np.ndarray                   = field(init=False, repr=False)
    _stuck_val: np.ndarray                   = field(init=False, repr=False)
    _drift_acc: np.ndarray                   = field(init=False, repr=False)
    _lane_modes: list[str]                   = field(init=False, repr=False)

    def __post_init__(self):
        self._rng = np.random.default_rng(self.seed)
        n_faulty  = max(0, int(round(self.n_lanes * self.fault_fraction)))
        indices   = self._rng.choice(self.n_lanes, size=n_faulty, replace=False)
        self._faulty = np.zeros(self.n_lanes, dtype=bool)
        self._faulty[indices] = True

        self._stuck_val = np.zeros(self.n_lanes)
        self._drift_acc = np.zeros(self.n_lanes)

        # For MX mode, assign a sub-mode to each faulty lane
        submodes = ["HZ", "SL", "GN", "ID", "DR"]
        self._lane_group = {l: g for g, lanes in enumerate(self.groups or []) for l in lanes}
        group_mode: dict[int, str] = {}
        self._lane_modes = []
        for i in range(self.n_lanes):
            if not self._faulty[i] or self.fault_mode == "NONE":
                self._lane_modes.append("NONE")
            elif self.fault_mode == "MX":
                g = self._lane_group.get(i)
                if self.mx_index is not None:
                    k = (self.mx_index + 2 * (g if g is not None else i)) % len(submodes)
                    self._lane_modes.append(submodes[k])
                elif g is None:
                    self._lane_modes.append(str(self._rng.choice(submodes)))
                else:   # one sensor -> one failure type for all its lanes
                    if g not in group_mode:
                        group_mode[g] = str(self._rng.choice(submodes))
                    self._lane_modes.append(group_mode[g])
            else:
                self._lane_modes.append(self.fault_mode)
        self._group_drop: dict[int, bool] = {}

    # public API

    def inject(self, readings: np.ndarray, step: int = 0) -> np.ndarray:
        """Apply faults to *readings* and return corrupted array.

        Parameters
        ----------
        readings : np.ndarray, shape (n_lanes,)
            Raw queue counts (vehicles).
        step : int
            Current simulation step (used for DR mode drift accumulation).

        Returns
        -------
        np.ndarray, shape (n_lanes,)
            Readings with faults applied. Healthy lanes are unchanged.
        """
        out = readings.astype(float).copy()
        # ID on a shared sensor: one dropout draw per sensor per step
        if self._lane_group and "ID" in self._lane_modes:
            self._group_drop = {g: bool(self._rng.random() < self.dropout_rate)
                                for g in sorted(set(self._lane_group.values()))}
        for i, mode in enumerate(self._lane_modes):
            if mode == "NONE":
                continue
            out[i] = self._apply_mode(mode, out[i], i, step)
        return out

    def reset(self):
        """Reset per-lane state (stuck value, drift accumulator)."""
        self._stuck_val[:] = 0.0
        self._drift_acc[:] = 0.0

    @property
    def faulty_indices(self) -> np.ndarray:
        """Boolean mask - True where a lane is faulty."""
        return self._faulty.copy()

    # per-mode logic

    def _apply_mode(self, mode: str, val: float, idx: int, step: int) -> float:
        if mode == "HZ":
            return 0.0

        elif mode == "SL":
            if val > 0:
                self._stuck_val[idx] = val
            return float(self._stuck_val[idx])

        elif mode == "GN":
            noisy = val + self._rng.normal(0.0, self.noise_sigma)
            return float(np.clip(noisy, 0.0, self.q_max))

        elif mode == "ID":
            g = self._lane_group.get(idx)
            if g is not None and g in self._group_drop:
                return 0.0 if self._group_drop[g] else float(val)
            if self._rng.random() < self.dropout_rate:
                return 0.0
            return float(val)

        elif mode == "DR":
            # Drift grows each step with small Gaussian increment
            self._drift_acc[idx] += self._rng.normal(self.drift_rate, self.drift_rate * 0.5)
            drifted = val + self._drift_acc[idx]
            return float(np.clip(drifted, 0.0, self.q_max))

        elif mode == "SH":
            return float(self.q_max)

        elif mode == "ND":
            self._drift_acc[idx] += self._rng.normal(self.drift_rate, self.drift_rate * 0.5)
            return float(np.clip(val - self._drift_acc[idx], 0.0, self.q_max))

        elif mode == "GA":
            return float(np.clip(self.gain * val, 0.0, self.q_max))

        return float(val)


# Convenience factory

def make_injector(
    mode: FaultMode,
    n_lanes: int = 16,
    fault_fraction: float = 0.25,
    seed: int = 42,
    q_max: float = Q_MAX_DEFAULT,
) -> FaultInjector:
    """Shorthand for constructing a FaultInjector."""
    return FaultInjector(
        n_lanes=n_lanes,
        fault_mode=mode,
        fault_fraction=fault_fraction,
        q_max=q_max,
        seed=seed,
    )


ALL_FAULT_MODES: list[FaultMode] = ["NONE", "HZ", "SL", "GN", "ID", "DR"]   # MX kept in code, not studied
EXTRA_FAULT_MODES: list[FaultMode] = ["SH", "ND", "GA"]                       # additional fault types
