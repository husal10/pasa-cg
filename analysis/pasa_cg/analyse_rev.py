"""Analysis of the additional sweeps (results_rev) together with the main sweep. Writes CSVs into out/."""
import sys, numpy as np, pandas as pd
from scipy import stats
from pathlib import Path
OUT = Path("out"); OUT.mkdir(exist_ok=True)
r = pd.read_csv("rev_episodes.csv"); m = pd.read_csv("episodes_main.csv")
KEY = ["profile", "demand", "pattern", "fault_mode"]

def holm(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); a = np.empty(n); run = 0
    for k, i in enumerate(o):
        run = max(run, (n - k) * p[i]); a[i] = min(run, 1)
    return a

def paired(g, a, b, met="total_delay_vh"):
    A = g[g.controller == a].set_index("seed")[met]; B = g[g.controller == b].set_index("seed")[met]
    s = A.index.intersection(B.index)
    if len(s) < 2: return None
    d = (A[s] - B[s]).to_numpy(float)
    p = stats.ttest_rel(A[s], B[s]).pvalue if d.std() > 0 else (1.0 if abs(d.mean()) < 1e-12 else 0.0)
    return dict(n=len(s), diff=d.mean(), rel_pct=100 * d.mean() / B[s].mean(), p=p)

def family(D, pairs, keys, met="total_delay_vh"):
    rows = []
    for key, g in D.groupby(keys):
        fam = []
        for a, b in pairs:
            res = paired(g, a, b, met)
            if res: fam.append(dict(zip(keys, key if isinstance(key, tuple) else (key,)), comparison=f"{a} vs {b}", **res))
        for x, pa in zip(fam, holm([x["p"] for x in fam]) if fam else []):
            x["p_holm"] = pa; x["sig"] = pa < 0.05
        rows += fam
    return pd.DataFrame(rows)

def tally(T, label):
    out = []
    for c, g in T.groupby("comparison"):
        out.append(dict(set=label, comparison=c, scenarios=len(g), better=int((g.sig & (g["diff"] < 0)).sum()),
                        worse=int((g.sig & (g["diff"] > 0)).sum()), ns=int((~g.sig).sum())))
    return pd.DataFrame(out)

# R1: field baselines (main guards)
r1 = r[r.set == "R1_field"]
cols = KEY + ["controller", "seed", "time_loss", "total_delay_vh", "n_trips", "co2_g"]
G = pd.concat([m[[c for c in cols if c in m]], r1[[c for c in cols if c in r1]]])
G = G[G.fault_mode != "NONE"]
P1 = [("pasa_cg_mp", "std_mp_maxrecall"), ("pasa_cg_mp", "webster_fallback_mp"), ("pasa_cg_mp", "oracle_cg_mp"),
      ("pasa_cg_mp", "std_mp_q"), ("pasa_cg_mp", "std_mp_recall"), ("pasa_cg_mp", "fixed_time")]
T1 = family(G[G.pattern.notna()], P1, KEY)
T1 = T1[T1.groupby(KEY).comparison.transform("count") >= 4]          # scenarios that have the new baselines
T1["pg"] = holm(T1.p)                                               # Holm over all R1 tests
T1.to_csv(OUT / "R1_tests.csv", index=False)
tl = tally(T1, "R1 main guards"); print(tl.to_string(index=False))
means = G.groupby(KEY + ["controller"]).time_loss.mean().unstack("controller").round(2)
means.to_csv(OUT / "R1_means.csv")

# R2: min green 20 s
r2 = r[r.set == "R2_mingreen20"]
r2.groupby(KEY + ["controller"]).time_loss.mean().unstack("controller").round(2).to_csv(OUT / "R2_means.csv")
P2 = P1 + [("pasa_cg_mp", "pasa_max_mp"), ("pasa_cg_mp", "std_mp")]
T2 = family(r2[r2.fault_mode != "NONE"], P2, KEY); T2.to_csv(OUT / "R2_tests.csv", index=False)
print(tally(T2, "R2 min green 20").to_string(index=False))
# healthy cost under min green
h2 = family(r2[r2.fault_mode == "NONE"], [("pasa_cg_mp", "std_mp_q")], KEY); h2.to_csv(OUT / "R2_healthy.csv", index=False)

# R3: max-red
r3 = r[r.set.str.startswith("R3")]
r3.groupby(["set", "demand", "fault_mode", "controller"]).time_loss.mean().unstack("controller").round(2).to_csv(OUT / "R3_means.csv")

# R4: planning error, R5: thresholds (PASA-CG only; compared with the default settings)
base = m[(m.profile == "symmetric") & (m.controller == "pasa_cg_mp")][KEY + ["seed", "time_loss", "total_delay_vh", "cg_tpr", "cg_fpr"]].assign(set="default")
mpq = m[(m.profile == "symmetric") & (m.controller == "std_mp_q")][KEY + ["seed", "total_delay_vh"]].rename(columns={"total_delay_vh": "td_mpq"})
for tag in ("R4", "R5"):
    x = r[r.set.str.startswith(tag)][["set"] + KEY + ["seed", "time_loss", "total_delay_vh", "cg_tpr", "cg_fpr", "cg_ttd_s", "cg_detected_frac"]]
    x = pd.concat([x, base[base.pattern.isin(x.pattern.unique()) & base.demand.isin(x.demand.unique()) & base.fault_mode.isin(x.fault_mode.unique())]])
    x = x.merge(mpq, on=KEY + ["seed"], how="left")
    x["vs_mpq_pct"] = 100 * (x.total_delay_vh - x.td_mpq) / x.td_mpq
    s = x.groupby(["set"] + KEY).agg(time_loss=("time_loss", "mean"), vs_mpq_pct=("vs_mpq_pct", "mean"),
                                       tpr=("cg_tpr", "mean"), fpr=("cg_fpr", "mean"), ttd=("cg_ttd_s", "mean")).round(3)
    s.to_csv(OUT / f"{tag}_summary.csv")
    # paired vs default
    rows = []
    for key, g in x.groupby(KEY):
        d0 = g[g.set == "default"].set_index("seed").total_delay_vh
        for st, gs in g[g.set != "default"].groupby("set"):
            a = gs.set_index("seed").total_delay_vh; ss = a.index.intersection(d0.index)
            dd = a[ss] - d0[ss]
            p = stats.ttest_rel(a[ss], d0[ss]).pvalue if dd.std() > 0 else 1.0
            rows.append(dict(zip(KEY, key), set=st, rel_vs_default=100 * dd.mean() / d0[ss].mean(), p=p))
    pd.DataFrame(rows).to_csv(OUT / f"{tag}_vs_default.csv", index=False)

# R6
for st in ("R6_newfaults", "R6_window"):
    x = r[r.set == st]
    x.groupby(KEY + ["controller"]).time_loss.mean().unstack("controller").round(2).to_csv(OUT / f"{st}_means.csv")
    P6 = [("pasa_cg_mp", c) for c in ["std_mp", "std_mp_q", "std_mp_recall", "std_mp_maxrecall", "webster_fallback_mp", "pasa_max_mp"]]
    T6 = family(x, P6, KEY); T6.to_csv(OUT / f"{st}_tests.csv", index=False)
    print(tally(T6, st).to_string(index=False))
    if "cg_ttd_s" in x:
        x[x.controller == "pasa_cg_mp"].groupby(KEY)[["cg_ttd_s", "cg_detected_frac", "cg_tpr"]].mean().round(2).to_csv(OUT / f"{st}_detect.csv")

# R7 clip exemption vs default PASA-CG (main sweep, high demand)
r7 = r[r.set == "R7_clip"][KEY + ["seed", "total_delay_vh", "time_loss", "cg_fpr", "cg_tpr"]]
b7 = m[(m.demand == "high") & (m.controller == "pasa_cg_mp")][KEY + ["seed", "total_delay_vh", "time_loss", "cg_fpr", "cg_tpr"]]
j = r7.merge(b7, on=KEY + ["seed"], suffixes=("_clip", "_def"))
rows = []
for key, g in j.groupby(KEY):
    dd = g.total_delay_vh_clip - g.total_delay_vh_def
    p = stats.ttest_rel(g.total_delay_vh_clip, g.total_delay_vh_def).pvalue if dd.std() > 0 else 1.0
    rows.append(dict(zip(KEY, key), rel=100 * dd.mean() / g.total_delay_vh_def.mean(), p=p,
                     fpr_clip=g.cg_fpr_clip.mean(), fpr_def=g.cg_fpr_def.mean(), tpr_clip=g.cg_tpr_clip.mean(), tpr_def=g.cg_tpr_def.mean()))
R7 = pd.DataFrame(rows); R7["p_holm"] = holm(R7.p); R7.to_csv(OUT / "R7_clip.csv", index=False)
print("R7 sig:", int((R7.p_holm < .05).sum()), "of", len(R7), "| rel range", R7.rel.min().round(2), R7.rel.max().round(2))

# R8: Cologne1 field baselines and min green
c1 = pd.read_csv("c1_episodes.csv").rename(columns={"fault": "fault_mode"})
c1["total_delay_vh"] = c1.time_loss * c1.n_trips / 3600
CK = ["pattern", "fault_mode"]
x8 = pd.concat([c1[CK + ["controller", "seed", "time_loss", "total_delay_vh", "co2_g"]],
                r[r.set == "R8_c1_field"][CK + ["controller", "seed", "time_loss", "total_delay_vh", "co2_g"]]])
x8.groupby(CK + ["controller"]).time_loss.mean().unstack().round(2).to_csv(OUT / "R8_c1_means.csv")
P8 = [("pasa_cg_mp", c) for c in ["std_mp_q", "std_mp_recall", "std_mp_maxrecall", "webster_fallback_mp", "oracle_cg_mp", "fixed_time"]]
T8 = family(x8[x8.fault_mode != "NONE"], P8, CK); T8.to_csv(OUT / "R8_c1_tests.csv", index=False)
print(tally(T8, "R8 Cologne1").to_string(index=False))
m8 = r[r.set == "R8_c1_mingreen20"]
m8.groupby(CK + ["controller"]).time_loss.mean().unstack().round(2).to_csv(OUT / "R8_c1_mingreen_means.csv")
T8m = family(m8[m8.fault_mode != "NONE"], P2, CK); T8m.to_csv(OUT / "R8_c1_mingreen_tests.csv", index=False)
print(tally(T8m, "R8 Cologne1 min green 20").to_string(index=False))

# R9: diagnosis delay
G9 = r[r.set.str.startswith("R9_diagdelay")].copy(); G9["delay_s"] = G9.set.str.extract(r"(\d+)$").astype(int)
z = r1[(r1.profile == "symmetric") & r1.demand.isin(["medium", "high"]) & r1.pattern.isin(["phase_symmetric", "single_approach"])
       & r1.controller.isin(["std_mp_maxrecall", "webster_fallback_mp"]) & r1.fault_mode.isin(["HZ"])].assign(delay_s=0)
sh = r[(r.set == "R6_newfaults") & r.controller.isin(["std_mp_maxrecall", "webster_fallback_mp"]) & (r.fault_mode == "SH")].assign(delay_s=0)
pc = pd.concat([m[(m.profile == "symmetric") & (m.controller == "pasa_cg_mp") & (m.fault_mode == "HZ")],
                r[(r.set == "R6_newfaults") & (r.controller == "pasa_cg_mp") & (r.fault_mode == "SH")]])
pc = pc[pc.demand.isin(["medium", "high"]) & pc.pattern.isin(["phase_symmetric", "single_approach"])]
A9 = pd.concat([G9, z, sh])
tab = A9.groupby(["demand", "pattern", "fault_mode", "controller", "delay_s"]).time_loss.mean().unstack("delay_s").round(2)
pcm = pc.groupby(["demand", "pattern", "fault_mode"]).time_loss.mean().round(2)
tab.to_csv(OUT / "R9_grid.csv"); pcm.to_csv(OUT / "R9_grid_pasacg.csv")
rows = []
for (dem, pat, f, ctl, dl), g in A9.groupby(["demand", "pattern", "fault_mode", "controller", "delay_s"]):
    b = pc[(pc.demand == dem) & (pc.pattern == pat) & (pc.fault_mode == f)].set_index("seed").total_delay_vh
    a = g.set_index("seed").total_delay_vh; s = a.index.intersection(b.index)
    rows.append(dict(demand=dem, pattern=pat, fault_mode=f, controller=ctl, delay_s=dl,
                     pasa_rel=100 * (b[s] - a[s]).mean() / a[s].mean(), p=stats.ttest_rel(b[s], a[s]).pvalue))
T9 = pd.DataFrame(rows); T9["p_holm"] = holm(T9.p); T9.to_csv(OUT / "R9_grid_tests.csv", index=False)
C9 = r[r.set.str.startswith("R9_c1")].copy(); C9["delay_s"] = C9.set.str.extract(r"(\d+)$").astype(int)
z8 = x8[(x8.pattern == "phase_symmetric") & x8.controller.isin(["std_mp_maxrecall", "webster_fallback_mp"]) & (x8.fault_mode == "HZ")].assign(delay_s=0)
pd.concat([C9, z8]).groupby(["fault_mode", "controller", "delay_s"]).time_loss.mean().unstack("delay_s").round(2).to_csv(OUT / "R9_c1.csv")
