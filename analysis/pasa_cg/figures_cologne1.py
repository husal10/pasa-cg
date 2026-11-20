"""
Cologne1 real-junction case study figures (IEEE two-column style, same look as figures_v2.py).
Input: results_c1/<pattern>/all_results.json (07:00-08:00 route-file demand, emissions on).

  fig_c1_heatmap       % change in network total delay vs queue-only MP, paired by seed, Holm within scenario
  fig_c1_headline      delay per trip: healthy detectors vs both N-S detectors dead
  c1_tests.csv         PASA-CG vs every baseline (total delay and CO2 per trip), Holm within scenario
  c1_summary.csv       mean +/- 95% CI per controller x pattern x fault

Usage: python figures_cologne1.py <dir containing results_c1> <fig_dir> [<stats_dir>]
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
SOUT = Path(sys.argv[3]) if len(sys.argv) > 3 else OUT; SOUT.mkdir(parents=True, exist_ok=True)
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
CTRLS = ["fixed_time", "std_mp", "std_mp_q", "std_mp_recall", "pasa_cg_mp"]  # aggregation variants: see analysis/fault_study
PAT = [("single_approach", "A: one approach"), ("cross_phase", "C: cross-phase"),
       ("phase_symmetric", "B: both N-S"), ("distributed", "D: distributed")]
FAULTS = ["HZ", "SL", "GN", "ID", "DR"]
FAULT_NAME = {"HZ": "dead", "SL": "stuck", "GN": "noise", "ID": "dropout", "DR": "drift"}
CMAP = LinearSegmentedColormap.from_list("bw", ["#2166AC", "#92C5DE", "#F7F7F7", "#F4A582", "#B2182B"])

rows = []
for f in sorted((ROOT / "results_c1").glob("*/all_results.json")):
    for e in json.loads(f.read_text())["episodes"]:
        rows.append(dict(pattern=f.parts[-2], controller=e["controller"], fault=e["fault_mode"], seed=e["seed"],
                         time_loss=e["time_loss"], n_trips=e["n_trips"], co2_g=e.get("co2_g"),
                         stops_per_trip=e.get("stops_per_trip"), cg_tpr=e.get("cg_tpr"), cg_fpr=e.get("cg_fpr")))
D = pd.DataFrame(rows); D["total_delay_vh"] = D.time_loss * D.n_trips / 3600
print(f"{len(D)} Cologne1 episodes")


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


def paired(g, a, b, m):
    A = g[g.controller == a].set_index("seed")[m]; B = g[g.controller == b].set_index("seed")[m]
    s = A.index.intersection(B.index); d = (A[s] - B[s]).to_numpy(float)
    p = stats.ttest_rel(A[s], B[s]).pvalue if d.std() > 0 else (1.0 if d.mean() == 0 else 0.0)
    return 100 * d.mean() / B[s].mean(), p


# summary + PASA-CG tests
summ = []
for key, g in D.groupby(["pattern", "fault", "controller"]):
    r = dict(zip(["pattern", "fault", "controller"], key), n=len(g))
    for m in ["time_loss", "total_delay_vh", "co2_g", "stops_per_trip", "cg_tpr", "cg_fpr"]:
        r[m], r[m + "_ci95"] = mean_ci(g[m])
    summ.append(r)
pd.DataFrame(summ).to_csv(SOUT / "c1_summary.csv", index=False)
tests = []
for (pat, f), g in D.groupby(["pattern", "fault"]):
    for m in ["total_delay_vh", "co2_g"]:
        fam = [dict(pattern=pat, fault=f, metric=m, baseline=b, **dict(zip(["rel", "p"], paired(g, "pasa_cg_mp", b, m))))
               for b in CTRLS if b != "pasa_cg_mp"]
        for r, pa in zip(fam, holm([r["p"] for r in fam])):
            r["p_holm"] = pa; r["sig"] = pa < 0.05
        tests += fam
pd.DataFrame(tests).to_csv(SOUT / "c1_tests.csv", index=False)


# Fig C1: heatmap vs queue-only MP
def fig_heatmap(lim=30, ref="std_mp_q"):
    ctrls = [c for c in CTRLS if c != ref]; cols = [(p, f) for p, _ in PAT for f in FAULTS]
    M = np.full((len(ctrls), len(cols)), np.nan); S = np.zeros_like(M, bool)
    for j, (p, f) in enumerate(cols):
        g = D[(D.pattern == p) & (D.fault == f)]
        res = [paired(g, c, ref, "total_delay_vh") for c in ctrls]
        for i, ((rel, _), pa) in enumerate(zip(res, holm([r[1] for r in res]))):
            M[i, j] = rel; S[i, j] = pa < 0.05
    fig, (ax, cax) = plt.subplots(1, 2, figsize=(COL2, 0.16 * len(ctrls) + 0.95),
                                  gridspec_kw=dict(width_ratios=[60, 1], wspace=0.02))
    ax.imshow(np.clip(M, -lim, lim), cmap=CMAP, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]; txt = f"{v:+.0f}" if abs(v) >= 0.5 else "0"
            ax.text(j, i, txt, ha="center", va="center", fontsize=5.6,
                    color=("white" if abs(v) > 0.65 * lim else "black") if S[i, j] else "#8a8a8a",
                    fontweight="bold" if S[i, j] else "normal")
    ax.set_yticks(range(len(ctrls))); ax.set_yticklabels([LABEL[c] for c in ctrls])
    ax.set_xticks(range(len(cols))); ax.set_xticklabels([FAULT_NAME[f] for _, f in cols], rotation=90)
    for k in range(1, len(PAT)):
        ax.axvline(k * len(FAULTS) - 0.5, color="black", lw=0.8)
    for k, (_, pn) in enumerate(PAT):
        ax.text(k * len(FAULTS) + (len(FAULTS) - 1) / 2, -0.62, pn, ha="center", va="bottom", fontsize=6.5)
    ax.tick_params(length=0); [s_.set_visible(False) for s_ in ax.spines.values()]
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=TwoSlopeNorm(0, -lim, lim)); cb = fig.colorbar(sm, cax=cax)
    cb.set_label(f"Change in network total delay\nvs {LABEL[ref]} (%)", fontsize=7)
    cb.set_ticks([-lim, -lim / 2, 0, lim / 2, lim])
    cb.set_ticklabels([f"≤{-lim}", f"{-lim // 2}", "0", f"+{lim // 2}", f"≥+{lim}"]); cb.ax.tick_params(labelsize=6)
    save(fig, "fig_c1_heatmap")


# Fig C2: delay per trip, healthy vs both N-S dead
def fig_headline():
    cases = [("NONE", "phase_symmetric", "Healthy detectors"), ("HZ", "phase_symmetric", "Both N-S detectors dead")]
    fig, ax = plt.subplots(figsize=(COL1, 2.2)); w = 0.84 / len(CTRLS)
    for j, (f, p, _) in enumerate(cases):
        for k, c in enumerate(CTRLS):
            m, ci = mean_ci(D[(D.pattern == p) & (D.fault == f) & (D.controller == c)]["time_loss"])
            ax.bar(j + (k - (len(CTRLS) - 1) / 2) * w, m, w * 0.92, yerr=ci, color=COLOR[c], hatch=HATCH[c],
                   edgecolor="black", linewidth=0.4, error_kw=dict(lw=0.6, capsize=1.2),
                   label=LABEL[c] if j == 0 else None, zorder=2)
    ax.set_xticks(range(len(cases))); ax.set_xticklabels([n for *_, n in cases])
    ax.set_ylabel("Delay per trip (s)")
    ax.yaxis.grid(True, lw=0.3, color="#DDDDDD", zorder=0); ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=4, fontsize=6, loc="lower center", bbox_to_anchor=(0.5, 1.0), handlelength=1.5, columnspacing=0.8)
    save(fig, "fig_c1_headline")


fig_heatmap(); fig_headline()
T = pd.DataFrame(tests); T = T[T.metric == "total_delay_vh"]
for b, g in T.groupby("baseline"):
    print(f"PASA-CG vs {LABEL[b]:16s} better {int((g.sig & (g.rel < 0)).sum()):2d}  worse {int((g.sig & (g.rel > 0)).sum()):2d}  n.s. {int((~g.sig).sum()):2d}")
