"""
Statistics for the detector-fault study (max-pressure under detector faults, no PASA-CG).

  F1 fault map    MP-Q (and Std-MP) with a fault vs the same controller with healthy detectors,
                  paired by seed, every scenario; Holm over all fault-map tests of a controller
  F2 aggregation  Std-MP, PASA-max, PASA-mean (v/c), PASA-max (v/c) vs MP-Q, Holm within scenario
                  over these comparisons only, plus BH over all of them
  F3 guards       MP-Q / Std-MP / PASA-max under minimum green and max-red settings
  F4 Cologne1     the same two analyses on Cologne1

Inputs: episodes_main.csv, rev_episodes.csv, c1_episodes.csv   Output: out_fault_study/*.csv
"""
import numpy as np, pandas as pd
from scipy import stats
from pathlib import Path

OUT = Path("out_fault_study"); OUT.mkdir(parents=True, exist_ok=True)
m = pd.read_csv("episodes_main.csv")
r = pd.read_csv("rev_episodes.csv")
c1 = pd.read_csv("c1_episodes.csv").rename(columns={"fault": "fault_mode"})
c1["total_delay_vh"] = c1.time_loss * c1.n_trips / 3600
c1["profile"], c1["demand"] = "c1", "c1"
r6 = r[r.set == "R6_newfaults"]
G = pd.concat([m, r6[[c for c in m.columns if c in r6.columns]]], ignore_index=True)
KEY = ["profile", "demand", "pattern", "fault_mode"]


def holm(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); a = np.empty(n); run = 0
    for k, i in enumerate(o):
        run = max(run, (n - k) * p[i]); a[i] = min(run, 1)
    return a


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)[::-1]; a = np.empty(n); run = 1
    for k, i in enumerate(o):
        run = min(run, p[i] * n / (n - k)); a[i] = run
    return a


def ptest(a, b):
    s = a.index.intersection(b.index); d = (a[s] - b[s]).to_numpy(float)
    p = stats.ttest_rel(a[s], b[s]).pvalue if d.std() > 0 else (1.0 if abs(d.mean()) < 1e-12 else 0.0)
    return len(s), d.mean(), 100 * d.mean() / b[s].mean(), p


def fault_map(D, ctrl, tag):
    rows = []
    h = D[(D.controller == ctrl) & (D.fault_mode == "NONE")].drop_duplicates(["profile", "demand", "seed"])
    for key, g in D[(D.controller == ctrl) & (D.fault_mode != "NONE")].groupby(KEY):
        hb = h[(h.profile == key[0]) & (h.demand == key[1])].set_index("seed")
        n, d, rel, p = ptest(g.set_index("seed").total_delay_vh, hb.total_delay_vh)
        rows.append(dict(zip(KEY, key), controller=ctrl, n=n, healthy_tl=hb.time_loss.mean(),
                         fault_tl=g.time_loss.mean(), d_tl=g.time_loss.mean() - hb.time_loss.mean(),
                         rel_pct=rel, p=p, backlog_max=g.insertion_backlog.max() if "insertion_backlog" in g else np.nan))
    T = pd.DataFrame(rows); T["p_holm"] = holm(T.p); T["sig"] = T.p_holm < 0.05
    T.to_csv(OUT / f"F1_faultmap_{tag}_{ctrl}.csv", index=False)
    return T


def aggregation(D, tag):
    comps = ["std_mp", "pasa_max_mp", "pasa_mean_vc_mp", "pasa_max_vc_mp"]
    rows = []
    for key, g in D.groupby(KEY):
        b = g[g.controller == "std_mp_q"].set_index("seed").total_delay_vh
        if b.empty: continue
        fam = []
        for c in comps:
            a = g[g.controller == c].set_index("seed").total_delay_vh
            if a.empty: continue
            n, d, rel, p = ptest(a, b)
            fam.append(dict(zip(KEY, key), comparison=f"{c} vs std_mp_q", n=n, diff=d, rel_pct=rel, p=p))
        for x, ph in zip(fam, holm([x["p"] for x in fam])):
            x["p_holm"] = ph
        rows += fam
    T = pd.DataFrame(rows)
    # healthy scenarios are identical across patterns on the grid: keep one copy
    T = T[~((T.fault_mode == "NONE") & T.duplicated(["profile", "demand", "fault_mode", "comparison"]))]
    T["sig"] = T.p_holm < 0.05; T["p_bh_all"] = bh(T.p)
    T.to_csv(OUT / f"F2_aggregation_{tag}.csv", index=False)
    tal = T.groupby("comparison").apply(lambda x: pd.Series(dict(
        scenarios=len(x), better=int((x.sig & (x["diff"] < 0)).sum()), worse=int((x.sig & (x["diff"] > 0)).sum()),
        better_bh=int(((x.p_bh_all < .05) & (x["diff"] < 0)).sum()), worse_bh=int(((x.p_bh_all < .05) & (x["diff"] > 0)).sum()))))
    tal.to_csv(OUT / f"F2_tally_{tag}.csv")
    return T, tal


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    grid = G[G.pattern.notna()]
    fm = fault_map(grid, "std_mp_q", "grid"); fs = fault_map(grid, "std_mp", "grid")
    for T in (fm, fs):
        print(T.controller.iloc[0], "fault scenarios", len(T), "worse", int((T.sig & (T.rel_pct > 0)).sum()),
              "better", int((T.sig & (T.rel_pct < 0)).sum()))
    print(fm.pivot_table(index=["profile", "demand", "pattern"], columns="fault_mode", values="d_tl").round(1))
    T, tal = aggregation(m[m.pattern.notna()], "grid"); print(tal)
    # Cologne1
    fc = fault_map(c1, "std_mp_q", "c1"); print(fc[["pattern", "fault_mode", "healthy_tl", "fault_tl", "rel_pct", "p_holm"]].round(3))
    Tc, talc = aggregation(c1, "c1"); print(talc)
    # guards
    K = ["demand", "pattern", "fault_mode", "controller", "seed", "time_loss", "total_delay_vh"]
    gs = [pd.concat([m[m.profile == "symmetric"][K]]).assign(guard="none/90"),
          r[r.set == "R2_mingreen20"][K].assign(guard="20/90"),
          r[r.set == "R3_maxred60"][K].assign(guard="20/60"), r[r.set == "R3_maxred120"][K].assign(guard="20/120")]
    A = pd.concat(gs)
    g = A[A.controller.isin(["std_mp_q", "std_mp", "pasa_max_mp", "fixed_time"])]
    tab = g.groupby(["guard", "demand", "pattern", "fault_mode", "controller"]).time_loss.mean().unstack("controller").round(2)
    tab.to_csv(OUT / "F3_guards.csv"); print(tab.loc[(slice(None), ["medium", "high"], "phase_symmetric", ["NONE", "HZ"]), :])
    c8 = r[r.set == "R8_c1_mingreen20"]
    c8.groupby(["pattern", "fault_mode", "controller"]).time_loss.mean().unstack().round(2).to_csv(OUT / "F3_guards_c1.csv")
