"""
Sustainability figures for PASA-CG (IEEE T-ITS style, same look as figures_v2.py).
Input: results_emis/<profile>/<demand>/<pattern>/all_results.json (SUMO emissions
device on; key cells: medium/high demand, patterns A and B, both profiles).

  fig_sus_headline_both_NS_dead   CO2 per trip and stops per trip, both N-S detectors dead
  fig_sus_heatmap_co2             % change in CO2 per trip vs queue-only MP (paired by seed, Holm)
  sustainability_summary.csv      mean +/- 95% CI per controller x scenario (CO2, fuel, NOx, PMx, stops)
  sustainability_rel_co2.csv      data behind the heatmap

Usage: python figures_sustainability.py <dir containing results_emis> <fig_dir>
"""
import sys, math, json
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from scipy import stats

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
COL1, COL2 = 3.5, 7.16
LABEL = {"fixed_time": "Fixed time", "std_mp": "Std-MP", "std_mp_q": "MP-Q",
         "std_mp_recall": "Short recall*", "pasa_max_mp": "PASA-max",
         "pasa_mean_vc_mp": "PASA-mean (v/c)", "pasa_max_vc_mp": "PASA-max (v/c)", "pasa_cg_mp": "PASA-CG"}
COLOR = {"fixed_time": "#BBBBBB", "std_mp": "#4477AA", "std_mp_q": "#66CCEE", "std_mp_recall": "#228833",
         "pasa_max_mp": "#CCBB44", "pasa_mean_vc_mp": "#AA3377", "pasa_max_vc_mp": "#EE99AA", "pasa_cg_mp": "#CC3311"}
HATCH = {"fixed_time": "", "std_mp": "", "std_mp_q": "////", "std_mp_recall": "xxx", "pasa_max_mp": "...",
         "pasa_mean_vc_mp": "\\\\\\\\", "pasa_max_vc_mp": "--", "pasa_cg_mp": ""}
DEM = [("medium", "Medium"), ("high", "High")]
PAT = [("single_approach", "A: one approach"), ("phase_symmetric", "B: both N-S")]
FAULTS = ["HZ", "SL", "GN", "ID", "DR"]
FAULT_NAME = {"HZ": "dead", "SL": "stuck", "GN": "noise", "ID": "dropout", "DR": "drift"}
# aggregation variants are reported in the companion ITSC paper
CTRLS = {"symmetric": ["fixed_time", "std_mp", "std_mp_q", "std_mp_recall", "pasa_cg_mp"],
         "asymmetric": ["fixed_time", "std_mp", "std_mp_q", "std_mp_recall", "pasa_cg_mp"]}
CMAP = LinearSegmentedColormap.from_list("bw", ["#2166AC", "#92C5DE", "#F7F7F7", "#F4A582", "#B2182B"])

rows = []
for f in sorted((ROOT / "results_emis").glob("*/*/*/all_results.json")):
    prof, dem, pat = f.parts[-4], f.parts[-3], f.parts[-2]
    for e in json.loads(f.read_text())["episodes"]:
        rows.append(dict(profile=prof, demand=dem, pattern=pat, controller=e["controller"],
                         fault_mode=e["fault_mode"], seed=e["seed"], co2_g=e.get("co2_g"), fuel_g=e.get("fuel_g"),
                         nox_g=e.get("nox_g"), pmx_mg=e.get("pmx_mg"), stops_per_trip=e.get("stops_per_trip"),
                         co2_total_kg=e.get("co2_total_kg"), time_loss=e.get("time_loss")))
D = pd.DataFrame(rows)
print(f"{len(D)} episodes from results_emis")


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf"); fig.savefig(OUT / f"{name}.png", dpi=600); plt.close(fig)
    print("saved", name)


def mean_ci(v):
    v = np.asarray(pd.Series(v).dropna(), float); n = len(v)
    return (v.mean() if n else np.nan), (stats.t.ppf(0.975, n - 1) * v.std(ddof=1) / math.sqrt(n) if n > 1 else 0.0)


def holm(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); adj = np.empty(n); run = 0
    for r, i in enumerate(o):
        run = max(run, (n - r) * p[i]); adj[i] = min(run, 1)
    return adj


# summary table
summ = []
for key, g in D.groupby(["profile", "demand", "pattern", "fault_mode", "controller"]):
    r = dict(zip(["profile", "demand", "pattern", "fault", "controller"], key), n=len(g))
    for m in ["co2_g", "fuel_g", "nox_g", "pmx_mg", "stops_per_trip", "time_loss"]:
        r[m], r[m + "_ci95"] = mean_ci(g[m])
    summ.append(r)
pd.DataFrame(summ).to_csv(OUT / "sustainability_summary.csv", index=False)


# Fig S1: headline, both N-S detectors dead
def fig_headline():
    metrics = [("co2_g", "CO$_2$ per trip (g)"), ("stops_per_trip", "Stops per trip")]
    fig, axes = plt.subplots(2, 2, figsize=(COL2, 4.1), sharex="col")
    for r_i, (met, ylab) in enumerate(metrics):
        for c_i, prof in enumerate(["symmetric", "asymmetric"]):
            ax = axes[r_i, c_i]; ctrls = CTRLS[prof]; w = 0.84 / len(ctrls)
            for k, c in enumerate(ctrls):
                for j, (dm, _) in enumerate(DEM):
                    g = D[(D.profile == prof) & (D.demand == dm) & (D.pattern == "phase_symmetric")
                          & (D.fault_mode == "HZ") & (D.controller == c)]
                    m, ci = mean_ci(g[met]); x = j + (k - (len(ctrls) - 1) / 2) * w
                    ax.bar(x, m, w * 0.92, yerr=ci, color=COLOR[c], hatch=HATCH[c], edgecolor="black", linewidth=0.4,
                           error_kw=dict(lw=0.6, capsize=1.2), label=LABEL[c] if j == 0 else None, zorder=2)
                    if k == 0:
                        h = D[(D.profile == prof) & (D.demand == dm) & (D.pattern == "phase_symmetric")
                              & (D.fault_mode == "NONE") & (D.controller == "std_mp_q")]
                        hm, _ = mean_ci(h[met])
                        ax.plot([j - 0.44, j + 0.44], [hm, hm], color="black", lw=0.7, ls=":", zorder=3,
                                label="MP-Q, healthy detectors" if j == 0 else None)
            ax.set_xticks(range(len(DEM))); ax.set_xticklabels([f"{n} demand" for _, n in DEM])
            if r_i == 0:
                ax.set_title(f"{prof.capitalize()} demand", pad=3)
            if c_i == 0:
                ax.set_ylabel(ylab)
            ax.yaxis.grid(True, lw=0.3, color="#DDDDDD", zorder=0); ax.set_axisbelow(True)
    h, l = axes[0, 1].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.025), handlelength=1.6)
    fig.subplots_adjust(hspace=0.18, wspace=0.18)
    save(fig, "fig_sus_headline_both_NS_dead")


# Fig S2: % change in CO2 per trip vs queue-only MP
def rel_vs(ref, metric):
    out = []
    for key, g in D.groupby(["profile", "demand", "pattern", "fault_mode"]):
        B = g[g.controller == ref].set_index("seed")[metric]; fam = []
        for c in CTRLS[key[0]]:
            if c == ref:
                continue
            A = g[g.controller == c].set_index("seed")[metric]; s = A.index.intersection(B.index)
            if len(s) < 2:
                continue
            d = (A[s] - B[s]).to_numpy(float)
            p = stats.ttest_rel(A[s], B[s]).pvalue if d.std() > 0 else (1.0 if d.mean() == 0 else 0.0)
            fam.append(dict(profile=key[0], demand=key[1], pattern=key[2], fault=key[3], controller=c,
                            rel=100 * d.mean() / B[s].mean(), p=p))
        for r, pa in zip(fam, holm([r["p"] for r in fam]) if fam else []):
            r["p_holm"] = pa; r["sig"] = pa < 0.05
        out += fam
    return pd.DataFrame(out)


def fig_heatmap(lim=30):
    ref = "std_mp_q"; R = rel_vs(ref, "co2_g"); R.to_csv(OUT / "sustainability_rel_co2.csv", index=False)
    panels = [(p, d) for p in ["symmetric", "asymmetric"] for d in DEM]
    cols = [(p, f) for p, _ in PAT for f in FAULTS]
    heights = [0.16 * (len(CTRLS[p]) - 1) + 0.42 for p, _ in panels]
    fig = plt.figure(figsize=(COL2 * 0.62, sum(heights) + 0.55))
    gs = fig.add_gridspec(len(panels), 2, width_ratios=[40, 1], height_ratios=heights, hspace=0.42, wspace=0.03)
    for r_i, (prof, (dm, dname)) in enumerate(panels):
        ctrls = [c for c in CTRLS[prof] if c != ref]; ax = fig.add_subplot(gs[r_i, 0])
        M = np.full((len(ctrls), len(cols)), np.nan); S = np.zeros_like(M, bool)
        for i, c in enumerate(ctrls):
            for j, (p, f) in enumerate(cols):
                r = R[(R.profile == prof) & (R.demand == dm) & (R.pattern == p) & (R.fault == f) & (R.controller == c)]
                if len(r):
                    M[i, j] = r.rel.iloc[0]; S[i, j] = bool(r.sig.iloc[0])
        ax.imshow(np.clip(M, -lim, lim), cmap=CMAP, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                if np.isnan(M[i, j]):
                    continue
                v = M[i, j]; txt = f"{v:+.0f}" if abs(v) >= 0.5 else "0"
                ax.text(j, i, txt, ha="center", va="center", fontsize=5.6,
                        color=("white" if abs(v) > 0.65 * lim else "black") if S[i, j] else "#8a8a8a",
                        fontweight="bold" if S[i, j] else "normal")
        ax.set_yticks(range(len(ctrls))); ax.set_yticklabels([LABEL[c] for c in ctrls])
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels([FAULT_NAME[f] for _, f in cols] if r_i == len(panels) - 1 else [], rotation=90)
        ax.axvline(len(FAULTS) - 0.5, color="black", lw=0.8)
        for k, (_, pn) in enumerate(PAT):
            ax.text(k * len(FAULTS) + (len(FAULTS) - 1) / 2, -0.62, pn, ha="center", va="bottom", fontsize=6.5)
        ax.text(-0.01, 1.0, f"{prof.capitalize()}, {dname.lower()} demand", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=7.5, fontweight="bold")
        ax.tick_params(length=0); [s_.set_visible(False) for s_ in ax.spines.values()]
    cax = fig.add_subplot(gs[:, 1])
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=TwoSlopeNorm(0, -lim, lim))
    cb = fig.colorbar(sm, cax=cax)
    cb.set_label(f"Change in CO$_2$ per trip vs {LABEL[ref]} (%)", fontsize=7)
    cb.set_ticks([-lim, -lim / 2, 0, lim / 2, lim])
    cb.set_ticklabels([f"≤{-lim}", f"{-lim // 2}", "0", f"+{lim // 2}", f"≥+{lim}"]); cb.ax.tick_params(labelsize=6)
    save(fig, "fig_sus_heatmap_co2")
    return R


fig_headline()
R = fig_heatmap()
cg = R[R.controller == "pasa_cg_mp"]
print(f"PASA-CG vs queue-only MP, CO2/trip: {int((cg.sig & (cg.rel < 0)).sum())} lower, "
      f"{int((cg.sig & (cg.rel > 0)).sum())} higher, {int((~cg.sig).sum())} n.s. of {len(cg)} scenarios")
