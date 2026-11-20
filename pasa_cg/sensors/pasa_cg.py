"""
pasa_cg.sensors.pasa_cg
=========================
Consistency-gated phase-aware structural aggregation (PASA-CG).

A two-phase signal gives every detector a predictable rhythm. While its phase
is red a real queue can only grow (vehicles arrive, none leave); while its
phase is green it discharges at saturation flow, within one or two decisions
at the demands studied. Opposing arms share green and red, so the opposite lane
is a natural reference. PASA-CG tests each lane against that rhythm, flags
lanes that persistently violate it, and replaces only the flagged readings.
Unflagged lanes pass through unchanged: with no flags the output equals the
clipped readings, so the controller is exactly queue-only max-pressure.

Evidence (lane l of arm a, partner lane p on the opposite arm, planning per-lane
v/c w):

  under-reporting  during consecutive red decisions, observed growth falls short
                   of the planning arrivals lambda_a * dt (lambda_a = w_a s / 3600):
                     C_lo <- max(0, C_lo + (1 - k_lo) lambda_a dt - dq_l)
                   Catches dead, stuck-low and dropping detectors, also when
                   both arms of a phase fail (no partner needed).
  over-reporting   from the 2nd green decision, evidence e_l = 1 when the trusted
                   partner lane reads empty while lane l still reads q_l >= 1 and
                   its reading has stopped falling (q_l >= q_l^prev):
                     C_hi <- max(0, C_hi + e_l q_l - k_hi)
                   Catches drift, stuck-high and positive bias.
  frozen           a non-zero reading unchanged over frozen_steps green decisions.

Flag when C_lo >= max(h_lo lambda_a dt, h_lo_min), C_hi >= h_hi, or frozen;
keep a flag while any statistic stays above release x its threshold (hysteresis).

Replacement of a flagged lane: partner lane scaled by v/c (q_p w_a / w_p) if the
partner is trusted; otherwise, while red, planning arrivals over the red time
(capped at max_red); while green, the previous estimate x green_decay.

Ablation switches (all True / "partner" = full method):
  use_lo       under-reporting test
  use_hi       over-reporting test
  use_frozen   frozen test
  hysteresis   keep flags until the statistics fall below release x threshold
               (False: a flag lasts only while a statistic is above threshold)
  use_partner  replace from the partner lane when it is trusted (False: always
               use the planning-arrival / decay estimate)

Known blind spot: over-reporting on both arms of one phase at once (no clean
reference during green).
Lane order (canonical): [N0..N(L-1), S.., E.., W..]; phase 0 = N+S, phase 1 = E+W.
"""
from __future__ import annotations

import numpy as np

ARMS = ("N", "S", "E", "W")
PARTNER = {"N": "S", "S": "N", "E": "W", "W": "E"}
ARM_PHASE = {"N": 0, "S": 0, "E": 1, "W": 1}

# Ablation variants: controller / filter name -> constructor switches
CG_VARIANTS: dict[str, dict] = {
    "pasa_cg":            {},
    "pasa_cg_nolo":       {"use_lo": False},
    "pasa_cg_nohi":       {"use_hi": False},
    "pasa_cg_nofrozen":   {"use_frozen": False},
    "pasa_cg_nohyst":     {"hysteresis": False},
    "pasa_cg_nopartner":  {"use_partner": False},
    "pasa_cg_clip":       {"clip_exempt": True},   # no under-reporting evidence from full lanes
}


class ConsistencyGatedPASA:
    def __init__(
        self,
        lanes_per_arm: int   = 3,
        dt:            float = 10.0,   # s between decisions
        q_max:         float = 20.0,   # veh, capacity clip
        sat_flow:      float = 1800.0, # veh/h/lane
        k_lo:          float = 0.5,    # allowance, fraction of expected arrivals per red decision
        h_lo:          float = 4.0,    # flag level, in units of expected arrivals per decision
        h_lo_min:      float = 3.0,    # veh, absolute floor of the under-reporting flag level
        k_hi:          float = 0.5,    # veh, allowance per green decision
        h_hi:          float = 3.0,    # veh, flag level
        release:       float = 0.25,   # flag released below release * threshold
        frozen_steps:  int   = 3,      # unchanged non-zero green decisions
        max_red:       float = 90.0,   # s, caps the arrival-based estimate
        green_decay:   float = 0.3,    # estimate multiplier per green decision
        use_lo:        bool  = True,
        use_hi:        bool  = True,
        use_frozen:    bool  = True,
        hysteresis:    bool  = True,
        use_partner:   bool  = True,
        clip_exempt:   bool  = False,  # a lane reading q_max (full) gives no under-reporting evidence
    ):
        self.lpa, self.dt, self.q_max, self.sat = lanes_per_arm, dt, q_max, sat_flow
        self.k_lo, self.h_lo, self.k_hi, self.h_hi = k_lo, h_lo, k_hi, h_hi
        self.h_lo_min = h_lo_min
        self.release, self.frozen_steps = release, frozen_steps
        self.max_red, self.green_decay = max_red, green_decay
        self.use_lo, self.use_hi, self.use_frozen = use_lo, use_hi, use_frozen
        self.hysteresis, self.use_partner = hysteresis, use_partner
        self.clip_exempt = clip_exempt
        self.n = 4 * lanes_per_arm
        self.reset()

    def reset(self) -> None:
        n = self.n
        self.c_lo = np.zeros(n)
        self.c_hi = np.zeros(n)
        self.flag = np.zeros(n, dtype=bool)
        self.prev = np.full(n, np.nan)
        self.frozen = np.zeros(n, dtype=int)
        self.est = np.zeros(n)
        self.red = np.zeros(4)          # s since the arm's phase was last green
        self.green_steps = np.zeros(4, dtype=int)

    def _sl(self, k: int) -> slice:
        return slice(k * self.lpa, (k + 1) * self.lpa)

    def process(self, readings: np.ndarray, phase: int, w: np.ndarray,
                oracle_flags: np.ndarray | None = None) -> np.ndarray:
        """Gated lane readings. readings (4L,), phase = current green (0/1),
        w = planning per-lane v/c per arm in ARMS order (4,).
        oracle_flags (4L,) bool: skip the three tests and use these flags
        (oracle-diagnosis baseline: same replacement, perfect detection)."""
        q = np.clip(np.asarray(readings, dtype=float), 0.0, self.q_max)
        w = np.maximum(np.asarray(w, dtype=float), 1e-3)
        was_red = self.red > 0
        for k, a in enumerate(ARMS):
            green = ARM_PHASE[a] == phase
            self.red[k] = 0.0 if green else self.red[k] + self.dt
            self.green_steps[k] = self.green_steps[k] + 1 if green else 0
        lam_dt = w * self.sat / 3600.0 * self.dt          # expected arrivals per lane per decision
        trusted = ~self.flag
        have_prev = ~np.isnan(self.prev)

        for k, a in enumerate(ARMS if oracle_flags is None else ()):
            kp = ARMS.index(PARTNER[a])
            sl, slp = self._sl(k), self._sl(kp)
            qa = q[sl]
            if self.use_lo and self.red[k] > 0 and was_red[k]:   # consecutive red: growth test
                dq = np.where(have_prev[sl], qa - self.prev[sl], lam_dt[k])
                if self.clip_exempt:     # a full lane cannot show growth: no evidence
                    dq = np.where(qa >= self.q_max - 1e-9, lam_dt[k], dq)
                self.c_lo[sl] = np.maximum(0.0, self.c_lo[sl] + lam_dt[k] - dq - self.k_lo * lam_dt[k])
            if self.green_steps[k] >= 2:                         # discharge tests
                if self.use_hi:
                    # evidence only when the trusted partner lane has emptied while
                    # this lane still reads a queue that has stopped falling
                    cleared = trusted[slp] & (q[slp] <= 0)
                    not_falling = have_prev[sl] & (qa >= self.prev[sl])
                    ev = cleared & not_falling & (qa >= 1)
                    self.c_hi[sl] = np.where(ev, np.maximum(0.0, self.c_hi[sl] + qa - self.k_hi),
                                             np.maximum(0.0, self.c_hi[sl] - self.k_hi))
                if self.use_frozen:
                    same = (qa == self.prev[sl]) & (qa >= 1)
                    self.frozen[sl] = np.where(same, self.frozen[sl] + 1, 0)
            elif self.red[k] > 0:
                self.frozen[sl] = 0

        th_lo = np.repeat(np.maximum(self.h_lo * lam_dt, self.h_lo_min), self.lpa)
        on = (self.c_lo >= th_lo) | (self.c_hi >= self.h_hi) | (self.frozen >= self.frozen_steps)
        if oracle_flags is not None:
            self.flag = np.asarray(oracle_flags, dtype=bool).copy()
        elif self.hysteresis:
            hold = self.flag & ((self.c_lo >= self.release * th_lo)
                                | (self.c_hi >= self.release * self.h_hi) | (self.frozen > 0))
            self.flag = on | hold
        else:
            self.flag = on

        out = q.copy()
        for k, a in enumerate(ARMS):
            kp = ARMS.index(PARTNER[a])
            sl, slp = self._sl(k), self._sl(kp)
            if self.red[k] > 0:
                fallback = np.full(self.lpa, min(lam_dt[k] / self.dt * min(self.red[k], self.max_red), self.q_max))
            else:
                fallback = self.est[sl] * self.green_decay
            if self.use_partner:
                e = q[slp] * w[k] / w[kp]
                est = np.where(~self.flag[slp], e, fallback)
            else:
                est = fallback
            out[sl] = np.where(self.flag[sl], est, q[sl])
            self.est[sl] = out[sl]
        self.prev = q.copy()
        return out
