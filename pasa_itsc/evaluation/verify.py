"""
pasa_itsc.evaluation.verify
===========================
End-to-end methodology checks in SUMO, run before a sweep:

    python -m pasa_itsc.main verify --net-dir data/net

Each check runs short headless episodes (warm-up + a few minutes) and asserts a
property the method or the experiment relies on. Prints PASS/FAIL per check
and exits non-zero if any check fails.
"""
from __future__ import annotations

import math
import traceback

import numpy as np

from pasa_itsc.env.sumo_env import SumoTrafficEnv, DECISION_STEP

APPROACH = {"N": [0, 1, 2], "S": [3, 4, 5], "E": [6, 7, 8], "W": [9, 10, 11]}
HEADING = {"N": "south", "S": "north", "E": "west", "W": "east"}


class Ctx:
    def __init__(self, net_dir: str, warmup: float, n_post: int):
        self.net_dir, self.warmup, self.n_post = net_dir, warmup, n_post

    def env(self, **kw) -> SumoTrafficEnv:
        cfg = dict(use_gui=False, net_dir=self.net_dir, demand_level="medium",
                   fault_intersection="I_SE", fault_approach="N", fault_n_lanes=0,
                   fault_pattern="single_approach", fault_mode="NONE",
                   controller="std_mp", seed=0, warmup=self.warmup)
        cfg.update(kw)
        return SumoTrafficEnv(**cfg)

    def run(self, env: SumoTrafficEnv, record=None) -> None:
        """Warm-up + n_post decisions; record(env, action, info, k) after each step."""
        obs, _ = env.reset(seed=env.seed)
        n_total = int(env.warmup // DECISION_STEP) + self.n_post
        try:
            for k in range(n_total):
                a = env.get_controller_action(obs)
                obs, _, term, trunc, info = env.step(a)
                if record is not None:
                    record(env, np.array(a).copy(), info, k)
                if term or trunc:
                    break
        finally:
            env.close()


def _applied_ok(env) -> bool:
    """Every junction shows a green (even) SUMO phase equal to the applied phase."""
    tc = env._traci
    for i, tl in enumerate(env._tl_ids):
        raw = tc.trafficlight.getPhase(tl)
        if raw % 2 != 0 or raw // 2 != env._prev_phases[i]:
            return False
    return True


def _max_red(phases: list[int], phase: int) -> float:
    """Longest run (s) during which `phase` was not served."""
    run = best = 0
    for p in phases:
        run = 0 if p == phase else run + 1
        best = max(best, run)
    return best * DECISION_STEP


# checks

def check_lane_geometry(c: Ctx):
    e = c.env(); e.reset(seed=0)
    try:
        tc, bad = e._traci, []
        for tl in e._tl_ids:
            lanes = e._approach_lanes(tl)
            for arm, ix in APPROACH.items():
                for j in ix:
                    h = e._lane_heading(tc.lane.getShape(lanes[j]))
                    if h != HEADING[arm]:
                        bad.append(f"{tl}:{arm}{j}={h}")
    finally:
        e.close()
    return not bad, "all 48 lanes in N,S,E,W order" if not bad else f"mismatch {bad[:4]}"


def check_prop1_equivalence(c: Ctx):
    seqs = {}
    for ctrl in ("std_mp_q", "pasa_mean_mp"):
        s = []
        c.run(c.env(controller=ctrl), lambda env, a, info, k: s.append(a))
        seqs[ctrl] = np.array(s)
    a, b = seqs["std_mp_q"], seqs["pasa_mean_mp"]
    same = a.shape == b.shape and bool((a == b).all())
    n = 0 if a.shape != b.shape else int((a != b).any(axis=1).sum())
    return same, f"{a.shape[0]} decisions x {a.shape[1]} junctions identical" if same else f"{n} steps differ"


def check_applied_phase(c: Ctx):
    bad = []
    def rec(env, a, info, k):
        if not _applied_ok(env):
            bad.append(k)
    c.run(c.env(controller="std_mp_q"), rec)
    return not bad, "applied SUMO phase == controller phase every step" if not bad else f"{len(bad)} steps off, first at {bad[:3]}"


def check_fixed_time_invariance(c: Ctx):
    q = {}
    for f in ("NONE", "HZ"):
        s = []
        c.run(c.env(controller="fixed_time", fault_mode=f), lambda env, a, info, k: s.append(info["mean_queue"]))
        q[f] = np.array(s)
    ok = q["NONE"].shape == q["HZ"].shape and np.allclose(q["NONE"], q["HZ"])
    return ok, "identical queue trajectories under NONE and HZ" if ok else "fixed-time differs under faults"


def check_fault_masking(c: Ctx):
    msgs, ok = [], True
    for seed, arm in ((0, "N"), (1, "W")):
        st = {"pre_clean": True, "post_zero": True, "others": True, "busy": 0.0}
        def rec(env, a, info, k):
            fi = env.fault_intersection
            raw = env._get_raw_readings(fi)
            flt = env._apply_injection(fi, raw)
            tgt = env._fault_target_lanes[fi] or []
            if env._step * DECISION_STEP < env.warmup:
                st["pre_clean"] &= bool(np.allclose(flt, raw))
            else:
                st["post_zero"] &= bool(np.allclose(flt[tgt], 0.0))
                oth = [j for j in range(len(raw)) if j not in tgt]
                st["others"] &= bool(np.allclose(flt[oth], raw[oth]))
                st["busy"] += float(raw[tgt].sum())
            st["tgt"] = list(tgt)
        # orientation balancing lives in the sweep loop (odd seeds -> W); here the
        # env is given that approach directly, as the sweep would.
        c.run(c.env(fault_mode="HZ", seed=seed, fault_approach=arm), rec)
        good = (st["pre_clean"] and st["post_zero"] and st["others"] and st["busy"] > 0
                and st["tgt"] == APPROACH[arm])
        ok &= good
        msgs.append(f"seed {seed}: targets {st['tgt']} (expect {arm}) clean-warmup={st['pre_clean']} "
                    f"zeroed={st['post_zero']} others-untouched={st['others']} true-queue-on-targets={st['busy']:.0f}")
    return ok, " | ".join(msgs)


def check_pattern_targets(c: Ctx):
    expect = {"single_approach": APPROACH["N"], "cross_phase": APPROACH["N"] + APPROACH["W"],
              "phase_symmetric": APPROACH["N"] + APPROACH["S"], "distributed": [0, 4, 6, 10]}
    got = {}
    for pat in expect:
        e = c.env(fault_mode="HZ", fault_pattern=pat); e.reset(seed=0)
        try:
            got[pat] = list(e._fault_target_lanes[e.fault_intersection] or [])
        finally:
            e.close()
    ok = all(sorted(got[p]) == sorted(v) for p, v in expect.items())
    return ok, ", ".join(f"{p}={got[p]}" for p in expect)


def check_single_injection(c: Ctx):
    calls: dict[int, int] = {}
    e = c.env(fault_mode="GN")
    orig = e._apply_injection_uncached
    def counting(i, raw):
        calls[e._step] = calls.get(e._step, 0) + 1
        return orig(i, raw)
    e._apply_injection_uncached = counting
    c.run(e)
    worst = max(calls.values()) if calls else 0
    return 0 < worst <= 4, f"max injector calls per step = {worst} (limit 4 junctions)"


def check_max_red(c: Ctx):
    phases, forced = [], [0]
    def rec(env, a, info, k):
        if env._step * DECISION_STEP > env.warmup:
            phases.append(env._prev_phases[env.fault_intersection]); forced[0] += info.get("forced", 0)
    c.run(c.env(controller="std_mp", fault_mode="HZ", fault_pattern="phase_symmetric", max_red=90.0), rec)
    red = _max_red(phases, 0)
    ok = red <= 90.0 and forced[0] > 0
    return ok, f"N-S faulted to zero: longest N-S red {red:.0f}s (limit 90), forced decisions {forced[0]}"


def check_recall(c: Ctx):
    phases = []
    def rec(env, a, info, k):
        if env._step * DECISION_STEP > env.warmup:
            phases.append(env._prev_phases[env.fault_intersection])
    c.run(c.env(controller="std_mp_recall", fault_mode="HZ", fault_pattern="phase_symmetric",
                recall_interval=60.0), rec)
    red = _max_red(phases, 0)
    return red <= 60.0, f"recall: longest N-S red at fault junction {red:.0f}s (limit 60)"


def check_trip_metrics(c: Ctx):
    e = c.env(controller="pasa_mean_mp")
    c.run(e)
    t = e.last_trip_stats or {}
    need = ("travel_time", "time_loss", "depart_delay", "delay_jain", "waiting_p95", "n_trips")
    ok = all(k in t and isinstance(t[k], (int, float)) and math.isfinite(t[k]) for k in need) \
        and set(t.get("delay_by_side", {})) == {"N", "S", "E", "W"} and t.get("n_trips", 0) > 0
    return ok, (f"trips {t.get('n_trips')} (unfinished {t.get('n_unfinished')}), time loss {t.get('time_loss', float('nan')):.1f}s, "
                f"backlog {t.get('insertion_backlog')}, sides {sorted(t.get('delay_by_side', {}))}")


def check_vc_weights(c: Ctx):
    out = {}
    for prof in ("symmetric", "asymmetric"):
        e = c.env(controller="pasa_mean_vc_mp", demand_profile=prof); e.reset(seed=0)
        try:
            w = e._vc_w[e.fault_intersection]
        finally:
            e.close()
        out[prof] = np.round(w, 3)
    sym, asym = out["symmetric"], out["asymmetric"]
    ok = asym[1] > asym[0] and asym[3] > asym[2] and abs(sym[1] - sym[0]) / max(sym) < 0.2
    return ok, f"v/c at I_SE (N,S,E,W): symmetric {sym.tolist()} | asymmetric {asym.tolist()}"


def check_pasa_cg(c: Ctx):
    res = {}
    for f, pat in (("NONE", "single_approach"), ("HZ", "phase_symmetric")):
        tot = [0, 0, 0, 0]
        def rec(env, a, info, k):
            if info.get("cg") is not None and not info.get("warmup", False):
                tot[:] = [x + y for x, y in zip(tot, info["cg"])]
        c.run(c.env(controller="pasa_cg_mp", fault_mode=f, fault_pattern=pat), rec)
        res[f] = tot
    fpr = res["NONE"][2] / max(res["NONE"][2] + res["NONE"][3], 1)
    tp, fn = res["HZ"][0], res["HZ"][1]
    tpr = tp / max(tp + fn, 1)
    ok = fpr < 0.05 and tpr > 0.3
    return ok, f"healthy false-alarm rate {fpr:.3f} (limit 0.05) | N+S dead: detected {tpr:.2f} of faulted lane-decisions"


def check_cg_ablations(c: Ctx):
    off = {"pasa_cg_nolo_mp": "c_lo", "pasa_cg_nohi_mp": "c_hi", "pasa_cg_nofrozen_mp": "frozen"}
    msgs, ok = [], True
    for ctrl in ("pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp",
                 "pasa_cg_nohyst_mp", "pasa_cg_nopartner_mp"):
        st = {"max_off": 0.0, "flags": 0}
        def rec(env, a, info, k):
            cg = env._cg[env.fault_intersection]
            if ctrl in off:
                st["max_off"] = max(st["max_off"], float(np.max(getattr(cg, off[ctrl]))))
            st["flags"] += int(cg.flag.sum())
        c.run(c.env(controller=ctrl, fault_mode="HZ", fault_pattern="phase_symmetric"), rec)
        good = st["max_off"] == 0.0
        ok &= good
        msgs.append(f"{ctrl[8:-3]}: off-stat max {st['max_off']:.0f}, lane-flags {st['flags']}")
    return ok, " | ".join(msgs)


def check_obs_filter(c: Ctx):
    e = c.env(controller="std_mp_q", fault_mode="HZ", obs_filter="pasa_cg_flags")
    seen = {"shape": None, "same": True}
    def rec(env, a, info, k):
        o1 = env._get_obs(); st = env._obs_filters[0]._cg.c_lo.copy()
        o2 = env._get_obs()
        seen["same"] &= bool(np.allclose(o1, o2) and np.allclose(st, env._obs_filters[0]._cg.c_lo))
        seen["shape"] = o1.shape
    c.run(e, rec)
    d = c.env(controller="std_mp_q")
    ok = seen["same"] and seen["shape"] == (4 * 25,) and d.observation_space.shape == (28,)
    return ok, (f"pasa_cg_flags obs {seen['shape']} (expect (100,)), repeated calls reuse state={seen['same']}, "
                f"default obs {d.observation_space.shape} (expect (28,))")


CHECKS = [
    ("Lane order matches geometry",           check_lane_geometry),
    ("queue-only MP == PASA-mean",   check_prop1_equivalence),
    ("Applied phase == controller phase",     check_applied_phase),
    ("Fixed-time unaffected by faults",       check_fixed_time_invariance),
    ("Fault masking, warm-up, orientation",   check_fault_masking),
    ("Pattern A/C/B/D target lanes",          check_pattern_targets),
    ("One fault injection per step",          check_single_injection),
    ("Max-red guard prevents starvation",     check_max_red),
    ("Recall serves failed phase",            check_recall),
    ("Trip and fairness metrics recorded",    check_trip_metrics),
    ("Planning v/c weights",                  check_vc_weights),
    ("PASA-CG false alarms and detection",    check_pasa_cg),
    ("PASA-CG ablation switches",             check_cg_ablations),
    ("Observation filter hook (RL input)",    check_obs_filter),
]


def run_all(net_dir: str = "data/net", warmup: float = 300.0, n_post: int = 60) -> bool:
    c = Ctx(net_dir, warmup, n_post)
    results = []
    for name, fn in CHECKS:
        print(f"[verify] {name} ...", flush=True)
        try:
            ok, msg = fn(c)
        except Exception as ex:  # a crash is a failure, with the reason shown
            ok, msg = False, f"error: {type(ex).__name__}: {ex}"
            traceback.print_exc()
        results.append((name, ok, msg))
        print(f"         {'PASS' if ok else 'FAIL'}  {msg}", flush=True)
    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n[verify] summary")
    for name, ok, msg in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"[verify] {len(results) - n_fail}/{len(results)} checks passed")
    return n_fail == 0
