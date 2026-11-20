"""
Further analyses of the existing sweeps (no new runs).

  tally_dedup.csv            healthy cells counted once per profile x demand (126 distinct scenarios);
                             counts under Holm within scenario, Holm over all PASA-CG tests, Holm over
                             all confirmatory tests, and Benjamini-Hochberg over all confirmatory tests
  orientation_split.csv      pattern-B delay by fault orientation (even seeds N+S faulted, odd seeds E+W)
  table_ci.csv               mean delay per trip with 95% CI for the paper's main tables
  c1_confirmatory.csv        Cologne1 tests with the grid's confirmatory family (Holm within scenario)
  healthy_identity.csv       share of healthy PASA-CG episodes identical to MP-Q, flag counts

Usage: python analysis_revision.py <stats_dir> <c1_dir> <out_dir>
  stats_dir holds episodes_main.csv and confirmatory_total_delay.csv (from analyse.py);
  c1_dir holds the Cologne1 per-episode file c1_episodes.csv (from analysis/extract_c1_episodes.py).
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ST, C1, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
m = pd.read_csv(ST / "episodes_main.csv")
c = pd.read_csv(ST / "confirmatory_total_delay.csv")


def holm(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); a = np.empty(n); r = 0
    for k, i in enumerate(o):
        r = max(r, (n - k) * p[i]); a[i] = min(r, 1)
    return a


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); a = np.empty(n); r = 1.0
    for k in range(n - 1, -1, -1):
        i = o[k]; r = min(r, p[i] * n / (k + 1)); a[i] = r
    return a


# Tallies with each healthy condition counted once
d = c.copy()
healthy = d.fault == "NONE"
keep = ~healthy | (d.pattern == "phase_symmetric")          # one copy of each healthy condition
d = d[keep].copy()
d["p_holm_global_cg"] = np.nan
cg = d.comparison.str.startswith("pasa_cg_mp")
d.loc[cg, "p_holm_global_cg"] = holm(d.loc[cg, "p"])
d["p_holm_global_all"] = holm(d.p)
d["p_bh_global_all"] = bh(d.p)
rows = []
for comp, g in d.groupby("comparison"):
    r = {"comparison": comp, "scenarios": len(g)}
    for col, name in (("p_holm", "holm_within_scenario"), ("p_holm_global_cg", "holm_all_pasa_cg"),
                      ("p_holm_global_all", "holm_all_confirmatory"), ("p_bh_global_all", "bh_all_confirmatory")):
        if g[col].isna().all():
            continue
        s = g[col] < 0.05
        r[f"{name}_better"] = int((s & (g["diff"] < 0)).sum())
        r[f"{name}_worse"] = int((s & (g["diff"] > 0)).sum())
    rows.append(r)
tally = pd.DataFrame(rows)
tally.to_csv(OUT / "tally_dedup.csv", index=False)
d.to_csv(OUT / "confirmatory_dedup_with_global.csv", index=False)
print(tally.to_string(index=False))

# Pattern B by fault orientation
b = m[(m.pattern == "phase_symmetric") & (m.fault_mode != "NONE")].copy()
b["orientation"] = np.where(b.seed % 2 == 0, "N+S faulted (phase 0)", "E+W faulted (phase 1)")
orient = (b.groupby(["profile", "demand", "fault_mode", "orientation", "controller"])["time_loss"]
          .mean().unstack("controller").round(2).reset_index())
orient.to_csv(OUT / "orientation_split.csv", index=False)
# paired PASA-CG vs MP-Q within orientation (n = 5 per orientation)
orows = []
for key, g in b.groupby(["profile", "demand", "fault_mode", "orientation"]):
    A = g[g.controller == "pasa_cg_mp"].set_index("seed").total_delay_vh
    B = g[g.controller == "std_mp_q"].set_index("seed").total_delay_vh
    s = A.index.intersection(B.index); dd = A[s] - B[s]
    p = stats.ttest_rel(A[s], B[s]).pvalue if dd.std() > 0 else np.nan
    orows.append(dict(zip(["profile", "demand", "fault", "orientation"], key), n=len(s),
                      rel_pct=100 * dd.mean() / B[s].mean(), p=p, all_seeds_better=bool((dd < 0).all())))
pd.DataFrame(orows).to_csv(OUT / "orientation_tests.csv", index=False)

# Mean delay per trip with 95% CI
def ci(v):
    v = np.asarray(v, float); n = len(v)
    h = stats.t.ppf(0.975, n - 1) * v.std(ddof=1) / np.sqrt(n) if n > 1 else 0.0
    return v.mean(), h


trows = []
for (prof, dem, pat, f, ctrl), g in m.groupby(["profile", "demand", "pattern", "fault_mode", "controller"]):
    if f == "NONE" and pat != "phase_symmetric":
        continue
    if not (f == "NONE" or (pat == "phase_symmetric" and f == "HZ")):
        continue
    mu, h = ci(g.time_loss)
    trows.append(dict(table="healthy" if f == "NONE" else "both_NS_dead", profile=prof, demand=dem,
                      controller=ctrl, mean_s=round(mu, 2), ci95_s=round(h, 2), n=len(g)))
pd.DataFrame(trows).to_csv(OUT / "table_ci.csv", index=False)

# Cologne1 tests with the grid's confirmatory family
c1 = pd.read_csv(C1 / "c1_episodes.csv")
c1["total_delay_vh"] = c1.time_loss * c1.n_trips / 3600
CONF = [("pasa_cg_mp", "std_mp_q"), ("pasa_cg_mp", "std_mp"), ("pasa_cg_mp", "std_mp_recall"),
        ("pasa_cg_mp", "pasa_max_mp"), ("pasa_max_mp", "std_mp_q"),
        ("pasa_mean_vc_mp", "std_mp_q"), ("pasa_max_vc_mp", "std_mp_q")]
crow = []
for (pat, f), g in c1.groupby(["pattern", "fault"]):
    fam = []
    for a_, b_ in CONF:
        A = g[g.controller == a_].set_index("seed").total_delay_vh
        B = g[g.controller == b_].set_index("seed").total_delay_vh
        s = A.index.intersection(B.index)
        if len(s) < 2:
            continue
        dd = (A[s] - B[s]).to_numpy()
        p = stats.ttest_rel(A[s], B[s]).pvalue if dd.std() > 0 else (1.0 if dd.mean() == 0 else 0.0)
        fam.append(dict(pattern=pat, fault=f, comparison=f"{a_} vs {b_}", diff=dd.mean(),
                        rel_pct=100 * dd.mean() / B[s].mean(), p=p))
    for r, pa in zip(fam, holm([r["p"] for r in fam])):
        r["p_holm"] = pa; r["significant"] = pa < 0.05
    crow += fam
c1c = pd.DataFrame(crow)
c1c.to_csv(OUT / "c1_confirmatory.csv", index=False)
dd_ = c1c[(c1c.fault != "NONE") | (c1c.pattern == "phase_symmetric")]
print("\nCologne1, grid family (Holm within scenario):")
for comp, g in dd_.groupby("comparison"):
    print(f"  {comp:30s} better {int((g.significant & (g['diff'] < 0)).sum()):2d} "
          f"worse {int((g.significant & (g['diff'] > 0)).sum()):2d} of {len(g)}")

# Healthy detectors: PASA-CG against MP-Q
h = m[m.fault_mode == "NONE"]
A = h[h.controller == "pasa_cg_mp"].set_index(["profile", "demand", "pattern", "seed"])
B = h[h.controller == "std_mp_q"].set_index(["profile", "demand", "pattern", "seed"])
s = A.index.intersection(B.index)
same = (np.abs(A.loc[s, "time_loss"] - B.loc[s, "time_loss"]) < 1e-9)
ident = same.groupby(level=[0, 1]).mean().rename("share_identical").reset_index()
ident["fpr"] = A.loc[s, "cg_fpr"].groupby(level=[0, 1]).mean().values
ident.to_csv(OUT / "healthy_identity.csv", index=False)
print("\nHealthy episodes identical to MP-Q:", round(float(same.mean()), 3))
print(ident.round(3).to_string(index=False))
