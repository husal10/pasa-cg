"""
pasa_itsc.sensors.obs_filters
=============================
Input cleaners for corrupted detector readings at one signalised junction,
behind one interface. Intended for the inputs of a learning controller (RL)
as well as for analysis; independent of SUMO.

Every filter is stateful per junction and per episode:

    f = make_filter("pasa_cg_flags", lanes_per_arm=3)
    f.reset()                                   # at episode start
    y = f(readings, phase, w)                   # once per decision step

    readings : (4L,) lane queues (veh), canonical order [N0..,S..,E..,W..]
    phase    : current green, 0 = N+S, 1 = E+W
    w        : (4,) planning per-lane v/c per arm (N,S,E,W); needed by the
               v/c and PASA-CG filters, ignored by the others
    y        : (f.out_dim,) cleaned values in veh; filters with flags append
               0/1 flag indicators (f.n_flags of them) after the queues

Call a stateful filter exactly once per decision step; calling it twice
advances its state twice.

Filters
-------
  raw                 capacity clip only                         out 4L
  l1                  L1 plausibility filter per lane            out 4L
  pasa_mean           opposing-lane mean (phase pairs)           out 2L
  pasa_max            opposing-lane max                          out 2L
  pasa_mean_l1        L1 + mean                                  out 2L
  pasa_max_l1         L1 + max                                   out 2L
  pasa_mean_vc        mean of v/c-normalised lanes, rescaled     out 2L
  pasa_max_vc         max  of v/c-normalised lanes, rescaled     out 2L
  pasa_plus           L1 + max + phase-conditional EWMA (PASA+)  out 2L
  pasa_cg             consistency-gated replacement (PASA-CG)    out 4L
  pasa_cg_<ablation>  PASA-CG with one test or rule switched off out 4L
                      (nolo, nohi, nofrozen, nohyst, nopartner)
  any PASA-CG name + "_flags"  appends the 4L lane flags         out 8L

Notes for RL inputs
-------------------
* Linear aggregation (pasa_mean, pasa_mean_vc) is a fixed linear map of the
  readings: a network can represent it in its first layer, and it discards
  information, so it cannot add robustness by itself.
* pasa_cg is the identity on readings it does not flag, so a policy trained
  on healthy detectors sees the same input distribution through it.
* PASA-CG's discharge tests need greens of at least two decisions (>= 20 s at
  10 s steps); a policy that switches every decision disables them.
"""
from __future__ import annotations

import numpy as np

from pasa_itsc.sensors.pasa import PASAPreprocessor
from pasa_itsc.sensors.pasa_plus import PASAPlusPreprocessor
from pasa_itsc.sensors.pasa_cg import ConsistencyGatedPASA, CG_VARIANTS

Q_MAX = 20.0


def vc_aggregate(q: np.ndarray, w: np.ndarray, how: str, lanes_per_arm: int = 3,
                 q_max: float = Q_MAX) -> np.ndarray:
    """Phase-pair aggregation of v/c-normalised lane queues, rescaled by the
    pair's mean v/c:  a_i = agg(q_a1,i / w_a1, q_a2,i / w_a2) * (w_a1 + w_a2) / 2.
    Same as the env's pasa_*_vc_mp controllers."""
    L = lanes_per_arm
    q = np.clip(np.asarray(q, dtype=float), 0.0, q_max)
    w = np.maximum(np.asarray(w, dtype=float), 1e-3) if w is not None else np.ones(4)
    r = [q[k * L:(k + 1) * L] / w[k] for k in range(4)]
    out = []
    for k1, k2 in ((0, 1), (2, 3)):
        pair = np.vstack([r[k1], r[k2]])
        agg = pair.mean(axis=0) if how == "mean" else pair.max(axis=0)
        out.append(agg * (w[k1] + w[k2]) / 2.0)
    return np.concatenate(out)


class ObsFilter:
    """Base class. Subclasses set out_dim / n_flags and implement _apply."""
    name = "base"

    def __init__(self, lanes_per_arm: int = 3, q_max: float = Q_MAX):
        self.lpa, self.q_max = lanes_per_arm, q_max
        self.n_lanes = 4 * lanes_per_arm
        self.n_flags = 0
        self.out_dim = self.n_lanes

    def reset(self) -> None:
        pass

    def _apply(self, readings, phase, w):
        raise NotImplementedError

    def __call__(self, readings, phase: int, w=None) -> np.ndarray:
        y = np.asarray(self._apply(np.asarray(readings, dtype=float), int(phase), w), dtype=float)
        assert y.shape == (self.out_dim,), (self.name, y.shape, self.out_dim)
        return y

    @property
    def flags(self):
        """Current lane flags (bool, 4L) for filters that detect faults, else None."""
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, out_dim={self.out_dim})"


class RawFilter(ObsFilter):
    name = "raw"

    def _apply(self, r, phase, w):
        return np.clip(r, 0.0, self.q_max)


class L1Filter(ObsFilter):
    name = "l1"

    def __init__(self, lanes_per_arm=3, q_max=Q_MAX):
        super().__init__(lanes_per_arm, q_max)
        self._pp = PASAPreprocessor(lanes_per_arm=lanes_per_arm, q_max=q_max,
                                    aggregation="mean", use_l1=True)

    def reset(self):
        self._pp.reset()

    def _apply(self, r, phase, w):
        return self._pp.filter_lanes(r, phase)


class PASAAggFilter(ObsFilter):
    """Phase-pair aggregation: mean or max, optional L1 first, optional v/c scaling."""

    def __init__(self, how="mean", use_l1=False, vc=False, lanes_per_arm=3, q_max=Q_MAX):
        super().__init__(lanes_per_arm, q_max)
        if vc and use_l1:
            raise ValueError("v/c aggregation with L1 is not defined")
        self.how, self.use_l1, self.vc = how, use_l1, vc
        self.name = f"pasa_{how}" + ("_l1" if use_l1 else "") + ("_vc" if vc else "")
        self.out_dim = 2 * lanes_per_arm
        self._pp = PASAPreprocessor(lanes_per_arm=lanes_per_arm, q_max=q_max,
                                    aggregation=how, use_l1=use_l1)

    def reset(self):
        self._pp.reset()

    def _apply(self, r, phase, w):
        if self.vc:
            return vc_aggregate(r, w, self.how, self.lpa, self.q_max)
        if self.use_l1:
            return self._pp.process(r, phase=phase)
        return self._pp.aggregate(r)


class PASAPlusFilter(ObsFilter):
    name = "pasa_plus"

    def __init__(self, lanes_per_arm=3, q_max=Q_MAX):
        super().__init__(lanes_per_arm, q_max)
        self.out_dim = 2 * lanes_per_arm
        self._pp = PASAPlusPreprocessor(lanes_per_arm=lanes_per_arm)

    def reset(self):
        self._pp.reset()

    def _apply(self, r, phase, w):
        return self._pp.process(r, phase=phase)


class PASACGFilter(ObsFilter):
    """PASA-CG lane replacement; optionally appends the lane flags."""

    def __init__(self, variant="pasa_cg", append_flags=False, lanes_per_arm=3,
                 q_max=Q_MAX, dt=10.0, max_red=90.0, **cg_kwargs):
        super().__init__(lanes_per_arm, q_max)
        if variant not in CG_VARIANTS:
            raise ValueError(f"unknown PASA-CG variant {variant!r}; choose from {list(CG_VARIANTS)}")
        self.variant, self.append_flags = variant, append_flags
        self.name = variant + ("_flags" if append_flags else "")
        self.n_flags = self.n_lanes if append_flags else 0
        self.out_dim = self.n_lanes + self.n_flags
        kw = dict(CG_VARIANTS[variant]); kw.update(cg_kwargs)
        self._cg = ConsistencyGatedPASA(lanes_per_arm=lanes_per_arm, q_max=q_max,
                                        dt=dt, max_red=max_red, **kw)

    def reset(self):
        self._cg.reset()

    @property
    def flags(self):
        return self._cg.flag.copy()

    def _apply(self, r, phase, w):
        if w is None:
            raise ValueError("PASA-CG needs the planning v/c weights w (4,)")
        y = self._cg.process(r, phase, w)
        return np.concatenate([y, self._cg.flag.astype(float)]) if self.append_flags else y


def available_filters() -> list[str]:
    names = ["raw", "l1", "pasa_mean", "pasa_max", "pasa_mean_l1", "pasa_max_l1",
             "pasa_mean_vc", "pasa_max_vc", "pasa_plus"]
    for v in CG_VARIANTS:
        names += [v, v + "_flags"]
    return names


def make_filter(name: str, lanes_per_arm: int = 3, q_max: float = Q_MAX, **kw) -> ObsFilter:
    """Build a filter by name (see module docstring and available_filters())."""
    if name == "raw":
        return RawFilter(lanes_per_arm, q_max)
    if name == "l1":
        return L1Filter(lanes_per_arm, q_max)
    if name == "pasa_plus":
        return PASAPlusFilter(lanes_per_arm, q_max)
    agg = {"pasa_mean": ("mean", False, False), "pasa_max": ("max", False, False),
           "pasa_mean_l1": ("mean", True, False), "pasa_max_l1": ("max", True, False),
           "pasa_mean_vc": ("mean", False, True), "pasa_max_vc": ("max", False, True)}
    if name in agg:
        how, l1, vc = agg[name]
        return PASAAggFilter(how, l1, vc, lanes_per_arm, q_max)
    flags = name.endswith("_flags")
    base = name[:-len("_flags")] if flags else name
    if base in CG_VARIANTS:
        return PASACGFilter(base, append_flags=flags, lanes_per_arm=lanes_per_arm, q_max=q_max, **kw)
    raise ValueError(f"unknown filter {name!r}; choose from {available_filters()}")


# self-test (no SUMO): python -m pasa_itsc.sensors.obs_filters
def _self_test(n_steps: int = 600, seed: int = 0) -> bool:
    rng = np.random.default_rng(seed)
    L, w = 3, np.array([0.30, 0.42, 0.30, 0.42])
    # synthetic two-phase queues: red arms grow, green arms discharge
    seq, phases, q = [], [], np.zeros(4 * L)
    for t in range(n_steps):
        ph = (t // 3) % 2
        for k in range(4):
            sl = slice(k * L, (k + 1) * L)
            if (k < 2) == (ph == 0):
                q[sl] = np.maximum(0, q[sl] - 5 + rng.poisson(1.0, L))
            else:
                q[sl] = q[sl] + rng.poisson(w[k] * 5.0, L)
        q = np.minimum(q, 20)
        seq.append(q.copy()); phases.append(ph)
    dead = [s.copy() for s in seq]
    for s in dead[100:]:
        s[0:L] = 0.0                                  # N arm dead from step 100
    ok, msg = True, []

    def check(cond, text):
        nonlocal ok
        ok &= bool(cond); msg.append(("PASS " if cond else "FAIL ") + text)

    for name in available_filters():                  # every filter runs, right shape
        f = make_filter(name, L); f.reset()
        ys = [f(r, p, w) for r, p in zip(dead, phases)]
        check(all(y.shape == (f.out_dim,) and np.all(np.isfinite(y)) for y in ys),
              f"{name:24s} out_dim {f.out_dim}")
    f = make_filter("pasa_cg", L); f.reset()          # filter == ConsistencyGatedPASA
    ref = ConsistencyGatedPASA(lanes_per_arm=L); ref.reset()
    check(all(np.allclose(f(r, p, w), ref.process(r, p, w)) for r, p in zip(dead, phases)),
          "pasa_cg filter identical to ConsistencyGatedPASA")
    f = PASACGFilter("pasa_cg", use_lo=False, use_hi=False, use_frozen=False); f.reset()
    check(all(np.allclose(f(r, p, w), np.clip(r, 0, Q_MAX)) for r, p in zip(dead, phases)),
          "PASA-CG with all tests off == raw (queue-only MP input)")
    f = make_filter("pasa_cg", L); f.reset()
    healthy_same = np.mean([np.allclose(f(r, p, w), r) for r, p in zip(seq, phases)])
    check(healthy_same > 0.85, f"pasa_cg leaves healthy readings unchanged at {healthy_same:.0%} of steps")
    f = make_filter("pasa_cg_flags", L); f.reset()
    for r, p in zip(dead, phases):
        y = f(r, p, w)
    check(y[4 * L:4 * L + L].all(), "dead N arm flagged by end of run (flags appended)")
    eq = np.ones(4)
    check(all(np.allclose(vc_aggregate(r, eq, "mean", L), make_filter("pasa_mean", L)(r, 0))
              for r in seq[:50]), "pasa_mean_vc with equal v/c == pasa_mean")
    print("\n".join(msg))
    print("[obs_filters] self-test", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
