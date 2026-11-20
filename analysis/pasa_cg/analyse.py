"""
Statistical analysis of the PASA-CG sweeps (main + ablation).

Primary outcome: network total delay (veh-h) = mean time loss x trips / 3600,
per episode. Comparisons are paired by seed (same demand realisation and fault
orientation for every controller). For each scenario (profile x demand x
pattern x fault) the confirmatory comparisons form one family: paired t-test,
95% CI of the mean difference, Holm correction within the family.

Usage: python analyse.py <results_root> <out_dir>
  results_root contains results_v2/<profile>/<demand>/<pattern>/all_results.json
  and results_ablation/symmetric/<demand>/<pattern>/all_results.json
"""
import json, sys, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

CONFIRMATORY = [
    ("pasa_cg_mp", "std_mp_q"), ("pasa_cg_mp", "std_mp"), ("pasa_cg_mp", "std_mp_recall"),
    ("pasa_cg_mp", "pasa_max_mp"), ("pasa_max_mp", "std_mp_q"),
    ("pasa_mean_vc_mp", "std_mp_q"), ("pasa_max_vc_mp", "std_mp_q"),   # asymmetric only
]
ABLATIONS = ["pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp",
             "pasa_cg_nohyst_mp", "pasa_cg_nopartner_mp"]


def load(kind):
    rows = []
    base = ROOT / ("results_v2" if kind == "main" else "results_ablation")
    for f in sorted(base.glob("*/*/*/all_results.json")):
        profile, demand, pattern = f.parts[-4], f.parts[-3], f.parts[-2]
        d = json.loads(f.read_text())
        for e in d["episodes"]:
            r = {k: v for k, v in e.items() if not isinstance(v, (dict, list))}
            for s, v in (e.get("delay_by_side") or {}).items():
                r[f"delay_{s}"] = v
            r.update(profile=profile, demand=demand, pattern=pattern, sweep=kind,
                     flow_prob=d.get("flow_prob"), code=d["provenance"]["code_sha256"][:8])
            rows.append(r)
    df = pd.DataFrame(rows)
    df["total_delay_vh"] = df["time_loss"] * df["n_trips"] / 3600.0
    # sensitivity: include the wait before entering the network
    df["total_delay_incl_depart_vh"] = (df["time_loss"] + df["depart_delay"]) * df["n_trips"] / 3600.0
    return df


def holm(p):
    p = np.asarray(p, float); n = len(p); order = np.argsort(p)
    adj = np.empty(n); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (n - rank) * p[i]); adj[i] = min(run, 1.0)
    return adj


def paired(df, a, b, metric):
    A = df[df.controller == a].set_index("seed")[metric]
    B = df[df.controller == b].set_index("seed")[metric]
    s = A.index.intersection(B.index)
    if len(s) < 2:
        return None
    d = (A[s] - B[s]).to_numpy(float)
    m, sd, n = d.mean(), d.std(ddof=1), len(d)
    if sd == 0:
        lo = hi = m; p = 1.0 if m == 0 else 0.0
    else:
        se = sd / math.sqrt(n); t = stats.t.ppf(0.975, n - 1)
        lo, hi = m - t * se, m + t * se
        p = stats.ttest_rel(A[s], B[s]).pvalue
    return dict(n=n, mean_a=A[s].mean(), mean_b=B[s].mean(), diff=m, ci_lo=lo, ci_hi=hi,
                rel_pct=100 * m / B[s].mean() if B[s].mean() else np.nan, p=p)


def compare(df, pairs, metric, family_label):
    out = []
    for key, g in df.groupby(["profile", "demand", "pattern", "fault_mode"]):
        fam = []
        for a, b in pairs:
            if a in set(g.controller) and b in set(g.controller):
                r = paired(g, a, b, metric)
                if r:
                    fam.append(dict(zip(["profile", "demand", "pattern", "fault"], key),
                                    comparison=f"{a} vs {b}", **r))
        if fam:
            adj = holm([r["p"] for r in fam])
            for r, pa in zip(fam, adj):
                r["p_holm"] = pa; r["significant"] = pa < 0.05; r["family"] = family_label
            out += fam
    return pd.DataFrame(out)


def cell_summary(df, metrics):
    agg = []
    for key, g in df.groupby(["profile", "demand", "pattern", "fault_mode", "controller"]):
        r = dict(zip(["profile", "demand", "pattern", "fault", "controller"], key), n=len(g))
        for mtr in metrics:
            v = g[mtr].dropna().to_numpy(float)
            if len(v):
                r[mtr] = v.mean()
                r[mtr + "_ci"] = (stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else np.nan
        agg.append(r)
    return pd.DataFrame(agg)


main, abl = load("main"), load("ablation")
main.to_csv(OUT / "episodes_main.csv", index=False)
abl.to_csv(OUT / "episodes_ablation.csv", index=False)

M = ["total_delay_vh", "total_delay_incl_depart_vh", "time_loss", "travel_time", "waiting_time",
     "waiting_p95", "depart_delay", "j0_queue", "j0_s_queue", "mean_queue", "throughput",
     "delay_jain", "j0_approach_jain", "insertion_backlog", "cg_tpr", "cg_fpr", "forced_frac",
     "delay_N", "delay_S", "delay_E", "delay_W"]
cell_summary(main, [m for m in M if m in main]).to_csv(OUT / "summary_main.csv", index=False)
cell_summary(abl, [m for m in M if m in abl]).to_csv(OUT / "summary_ablation.csv", index=False)

conf = compare(main, CONFIRMATORY, "total_delay_vh", "confirmatory")
conf.to_csv(OUT / "confirmatory_total_delay.csv", index=False)
sens = compare(main, CONFIRMATORY, "total_delay_incl_depart_vh", "sensitivity: incl. entry wait")
sens.to_csv(OUT / "sensitivity_total_delay_incl_depart.csv", index=False)
ab = compare(abl, [(v, "pasa_cg_mp") for v in ABLATIONS], "total_delay_vh", "ablation (exploratory)")
ab.to_csv(OUT / "ablation_total_delay.csv", index=False)

# console digest
print("episodes main", len(main), "ablation", len(abl),
      "| code versions", sorted(set(main.code) | set(abl.code)),
      "| flow_prob", sorted(set(main.flow_prob.dropna())))
for name, t in (("CONFIRMATORY", conf), ("ABLATION", ab)):
    print(f"\n{name}: {len(t)} tests, {int(t.significant.sum())} significant after Holm")
    for comp, g in t.groupby("comparison"):
        better = int(((g["diff"] < 0) & g.significant).sum()); worse = int(((g["diff"] > 0) & g.significant).sum())
        print(f"  {comp:40s} scenarios {len(g):3d}  significantly lower delay {better:3d}  higher {worse:3d}  ns {len(g)-better-worse:3d}")
