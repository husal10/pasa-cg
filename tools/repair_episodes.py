"""
Audit and repair episodes whose trip statistics came from another run.

Audit: an episode is suspect when its live arrival count (throughput) and its
trip-file arrivals (n_trips - n_unfinished) disagree far beyond the normal gap
(median + 8 MAD over all episodes). Repair: rerun the episode with the folder's
recorded settings (needs patch14, which checks every new episode) and replace it
in the cell file and all_results.json. Fixed-time episodes are replaced in every
fault cell of the folder (they are reused across faults).

Run from pasa_itsc_code:
    python repair_episodes.py audit                       # list suspects only
    python repair_episodes.py repair --net-dir data/net_repair
"""
import sys, json, glob, statistics as st, shutil, argparse
from pathlib import Path
from dataclasses import asdict

ROOTS = ["results_v2", "results_ablation", "results_emis", "results_c1", "results_rev"]


def load_all():
    rows = []
    for root in ROOTS:
        for f in glob.glob(f"{root}/**/grid2x2__*.json", recursive=True) + glob.glob(f"{root}/**/cologne1__*.json", recursive=True):
            for e in json.loads(Path(f).read_text())["episodes"]:
                if e.get("n_trips") is None or e.get("throughput") is None:
                    continue
                gap = e["throughput"] - (e["n_trips"] - (e.get("n_unfinished") or 0))
                rows.append(dict(file=f, folder=str(Path(f).parent), ctrl=e["controller"], fault=e["fault_mode"],
                                 seed=e["seed"], gap=gap, ep=e))
    return rows


def suspects(rows):
    g = [r["gap"] for r in rows]; med = st.median(g); mad = st.median([abs(x - med) for x in g]) or 1
    out = {}
    for r in rows:
        if abs(r["gap"] - med) > 8 * mad:
            key = (r["folder"], r["ctrl"], "NONE" if r["ctrl"] == "fixed_time" else r["fault"], r["seed"])
            out[key] = r
    return out, med, mad


def rerun(folder, ctrl, fault, seed, approach, net_dir):
    meta = json.loads((Path(folder) / "all_results.json").read_text())
    from pasa_itsc.env.sumo_env import SumoTrafficEnv
    from pasa_itsc.evaluation.experiment import _run_episode, _ensure_network
    net = meta.get("network", "grid2x2")
    if meta.get("demand_level") not in ("low", "medium", "high"):   # cologne1: route-file demand
        meta["demand_level"] = "medium"
    _ensure_network(net, net_dir, None, None, demand_level=meta["demand_level"], flow_prob=meta.get("flow_prob"))
    site, ctl = meta.get("fault_site", {}), meta.get("control", {})
    env = SumoTrafficEnv(network=net, use_gui=False, fault_mode=fault, fault_fraction=0.25, controller=ctrl,
                         seed=seed, net_dir=net_dir, demand_level=meta["demand_level"],
                         fault_intersection=site.get("junction", "I_SE"), fault_approach=approach,
                         max_red=ctl.get("max_red_s", 90.0), recall_interval=ctl.get("recall_interval_s", 60.0),
                         demand_profile=meta.get("demand_profile", "symmetric"), warmup=meta.get("warmup_s", 900.0),
                         fault_severity=meta.get("fault_severity", "high"), fault_n_lanes=site.get("n_lanes", 0),
                         fault_pattern=meta.get("fault_pattern", "single_approach"), emissions=bool(meta.get("emissions", False)),
                         min_green=ctl.get("min_green_s", 0.0), max_green=ctl.get("max_green_s", 40.0),
                         fault_start=(meta.get("fault_window_s") or [0.0, None])[0],
                         fault_end=(meta.get("fault_window_s") or [0.0, None])[1],
                         plan_scale=(meta.get("planning_error") or {}).get("scale", 1.0),
                         plan_noise=(meta.get("planning_error") or {}).get("arm_lognormal_sd", 0.0),
                         cg_params=meta.get("cg_params") or None, diag_delay=meta.get("diag_delay_s", 0.0))
    for attempt in range(3):
        try:
            ep = _run_episode(env, ctrl, fault, seed)
        finally:
            env.close()
        if not getattr(env, "trip_check_failed", False):
            break
    else:
        raise RuntimeError("trip check failed 3 times")
    for k, v in (env.last_trip_stats or {}).items():
        setattr(ep, k, v)
    ep.fault_approach = approach
    return asdict(ep)


def replace(folder, ctrl, seed, new_ep, faults):
    for f in [Path(folder) / "all_results.json"] + [p for p in Path(folder).glob(f"*__{ctrl}__*.json")]:
        d = json.loads(f.read_text()); n = 0
        for i, e in enumerate(d["episodes"]):
            if e["controller"] == ctrl and e["seed"] == seed and e["fault_mode"] in faults:
                d["episodes"][i] = dict(new_ep, fault_mode=e["fault_mode"]); n += 1
        if n:
            bak = f.with_suffix(".json.bak_repair")
            if not bak.exists():
                shutil.copy2(f, bak)
            d.setdefault("repairs", []).append({"controller": ctrl, "seed": seed, "faults": sorted(faults)})
            f.write_text(json.dumps(d, indent=1))
            print(f"   replaced {n} episode(s) in {f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["audit", "repair"])
    ap.add_argument("--net-dir", default="data/net_repair")
    a = ap.parse_args()
    rows = load_all(); sus, med, mad = suspects(rows)
    print(f"episodes {len(rows)}, normal gap {med:.0f} +/- {mad:.0f} (MAD); suspect episodes: {len(sus)}")
    for (folder, ctrl, fault, seed), r in sorted(sus.items()):
        e = r["ep"]
        print(f"  {folder} {ctrl} {fault} seed {seed}: gap {r['gap']:.0f}, time loss {e['time_loss']:.1f} s, trips {e['n_trips']}")
    if a.mode == "repair":
        Path(a.net_dir).mkdir(parents=True, exist_ok=True)
        for (folder, ctrl, fault, seed), r in sorted(sus.items()):
            print(f"rerunning {folder} {ctrl} {fault} seed {seed} ...")
            new = rerun(folder, ctrl, fault, seed, r["ep"].get("fault_approach") or ("N" if seed % 2 == 0 else "W"), a.net_dir)
            faults = {"NONE", "HZ", "SL", "GN", "ID", "DR"} if ctrl == "fixed_time" else {fault}
            print(f"   new: time loss {new['time_loss']:.2f} s, trips {new['n_trips']}, throughput {new['throughput']:.0f}")
            replace(folder, ctrl, seed, new, faults)
        print("done; rerun `audit` to confirm no suspects remain")
