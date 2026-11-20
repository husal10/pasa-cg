"""
Figures for the ITSC companion paper (same look as the T-ITS figures).

  fig_conf_faultmap     change in network total delay of MP-Q with a fault vs MP-Q with healthy detectors
  fig_conf_aggregation  change in network total delay of PASA-max vs MP-Q
  fig_conf_guards       MP-Q delay per trip under four guard settings, healthy vs both N-S detectors dead

Inputs: conf/out/*.csv from conf_stats.py, episodes_main.csv, rev_episodes.csv
Usage: python conf_figures.py <fig_dir>
"""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from scipy import stats

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
S = Path("conf/out")
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
CMAP = LinearSegmentedColormap.from_list("bwr_soft", ["#2166AC", "#F7F7F7", "#B2182B"])
PAT = [("single_approach", "A: one approach"), ("cross_phase", "C: cross-phase"),
       ("phase_symmetric", "B: both N-S"), ("distributed", "D: distributed")]
FAULTS = ["HZ", "SL", "GN", "ID", "DR"]
FAULT_NAME = {"HZ": "dead", "SL": "stuck", "GN": "noise", "ID": "dropout", "DR": "drift"}
ROWS = [("symmetric", "low", "Sym., low"), ("symmetric", "medium", "Sym., medium"), ("symmetric", "high", "Sym., high"),
        ("asymmetric", "low", "Asym., low"), ("asymmetric", "medium", "Asym., medium"),
        ("asymmetric", "high", "Asym., high"), ("c1", "c1", "Cologne1")]


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf"); fig.savefig(OUT / f"{name}.png", dpi=600); plt.close(fig)
    print("saved", name)


def heat(T, name, cblabel, lim=30):
    cols = [(p, f) for p, _ in PAT for f in FAULTS]
    M = np.full((len(ROWS), len(cols)), np.nan); Sg = np.zeros_like(M, bool)
    for i, (pr, dm, _) in enumerate(ROWS):
        for j, (p, f) in enumerate(cols):
            r = T[(T.profile == pr) & (T.demand == dm) & (T.pattern == p) & (T.fault_mode == f)]
            if len(r):
                M[i, j] = r.rel_pct.iloc[0]; Sg[i, j] = bool(r.sig.iloc[0])
    fig = plt.figure(figsize=(COL2, 2.25))
    gs = fig.add_gridspec(1, 2, width_ratios=[60, 1], wspace=0.02)
    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(np.clip(M, -lim, lim), cmap=CMAP, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v):
                continue
            txt = f"{v:+.0f}" if abs(v) >= 0.5 else "0"
            ax.text(j, i, txt, ha="center", va="center", fontsize=5.6,
                    color=("white" if abs(v) > 0.65 * lim else "black") if Sg[i, j] else "#8a8a8a",
                    fontweight="bold" if Sg[i, j] else "normal")
    ax.set_yticks(range(len(ROWS))); ax.set_yticklabels([lab for _, _, lab in ROWS])
    ax.set_xticks(range(len(cols))); ax.set_xticklabels([FAULT_NAME[f] for _, f in cols], rotation=90)
    for k in range(1, len(PAT)):
        ax.axvline(k * len(FAULTS) - 0.5, color="black", lw=0.8)
    ax.axhline(5.5, color="black", lw=0.8)
    for k, (_, pn) in enumerate(PAT):
        ax.text(k * len(FAULTS) + (len(FAULTS) - 1) / 2, -0.65, pn, ha="center", va="bottom", fontsize=6.5)
    ax.tick_params(length=0); [s_.set_visible(False) for s_ in ax.spines.values()]
    cax = fig.add_subplot(gs[0, 1])
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=TwoSlopeNorm(0, -lim, lim))
    cb = fig.colorbar(sm, cax=cax); cb.set_label(cblabel, fontsize=7)
    cb.set_ticks([-lim, -lim / 2, 0, lim / 2, lim])
    cb.set_ticklabels([f"≤{-lim}", f"{-lim // 2}", "0", f"+{lim // 2}", f"≥+{lim}"]); cb.ax.tick_params(labelsize=6)
    save(fig, name)


fm = pd.concat([pd.read_csv(S / "F1_faultmap_grid_std_mp_q.csv"), pd.read_csv(S / "F1_faultmap_c1_std_mp_q.csv")])
heat(fm, "fig_conf_faultmap", "Change in network total delay\nvs healthy detectors (%)")
ag = pd.concat([pd.read_csv(S / "F2_aggregation_grid.csv"), pd.read_csv(S / "F2_aggregation_c1.csv")])
heat(ag[ag.comparison == "pasa_max_mp vs std_mp_q"], "fig_conf_aggregation", "Change in network total delay\nvs MP-Q (%)")

# guards
m = pd.read_csv("episodes_main.csv"); r = pd.read_csv("rev_episodes.csv")
K = ["demand", "pattern", "fault_mode", "controller", "seed", "time_loss"]
G = [("A", m[m.profile == "symmetric"][K]), ("B", r[r.set == "R2_mingreen20"][K]),
     ("C", r[r.set == "R3_maxred60"][K]), ("D", r[r.set == "R3_maxred120"][K])]
LAB = {"A": "A\nnone/90", "B": "B\n20/90", "C": "C\n20/60", "D": "D\n20/120"}


def mci(v):
    v = np.asarray(v, float); n = len(v)
    return v.mean(), stats.t.ppf(.975, n - 1) * v.std(ddof=1) / math.sqrt(n)


fig, axes = plt.subplots(1, 2, figsize=(COL1, 1.9), sharey=True)
for ax, dem in zip(axes, ["medium", "high"]):
    x = np.arange(4)
    for fmode, col, mk, lab in [("HZ", "#B2182B", "o", "Both N-S dead"), ("NONE", "#2166AC", "s", "Healthy")]:
        mu = [mci(d[(d.demand == dem) & (d.pattern == "phase_symmetric") & (d.fault_mode == fmode) & (d.controller == "std_mp_q")].time_loss) for _, d in G]
        ax.errorbar(x, [a for a, _ in mu], yerr=[b for _, b in mu], color=col, marker=mk, ms=3.2, lw=0.9, capsize=1.6, elinewidth=0.6, label=lab)
    ft = m[(m.profile == "symmetric") & (m.demand == dem) & (m.controller == "fixed_time") & (m.fault_mode == "NONE")].time_loss.mean()
    ax.axhline(ft, color="#888888", ls="--", lw=0.8); ax.text(3.3, ft + 2, "Fixed time", fontsize=6, ha="right", color="#666666")
    ax.set_xticks(x); ax.set_xticklabels([LAB[g] for g, _ in G], fontsize=6)
    ax.set_title(f"{dem.capitalize()} demand", pad=2); ax.set_ylim(0, 135); ax.set_xlim(-0.3, 3.3)
axes[0].set_ylabel("Delay per trip (s)")
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.55, 1.08))
fig.tight_layout(w_pad=0.6)
fig.text(0.55, -0.01, "Minimum green / max-red (s)", ha="center", fontsize=7)
save(fig, "fig_conf_guards")
