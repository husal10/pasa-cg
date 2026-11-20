"""
Figures for the guard and diagnosis-delay sweeps (IEEE two-column style, same look as figures_v2.py / figures_cologne1.py).

  fig_rev_guards     both N-S detectors dead (pattern B, HZ), symmetric grid: delay per trip under four
                     guard settings (min green / max red), with MP-Q healthy for reference
  fig_rev_diagdelay  both N-S detectors dead: oracle field fallbacks when the diagnosis arrives late,
                     against PASA-CG (which needs no diagnosis); grid medium, grid high, Cologne1

Inputs (episode tables written by the analysis scripts):
  episodes_main.csv   main grid sweep        rev_episodes.csv   revision sweeps (results_rev)
  c1_episodes.csv     Cologne1 main sweep

Usage: python figures_revision.py <dir with the three csv files> <fig_dir>
"""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
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
LABEL = {"std_mp_q": "MP-Q", "std_mp_recall": "Short recall*", "std_mp_maxrecall": "Maximum recall*",
         "webster_fallback_mp": "Fixed-time fallback*", "pasa_cg_mp": "PASA-CG", "fixed_time": "Fixed time"}
COLOR = {"std_mp_q": "#66CCEE", "std_mp_recall": "#228833", "std_mp_maxrecall": "#4477AA",
         "webster_fallback_mp": "#777777", "pasa_cg_mp": "#CC3311", "fixed_time": "#BBBBBB"}
MARK = {"std_mp_q": "s", "std_mp_recall": "^", "std_mp_maxrecall": "D", "webster_fallback_mp": "v", "pasa_cg_mp": "o"}

m = pd.read_csv(SRC / "episodes_main.csv")
r = pd.read_csv(SRC / "rev_episodes.csv")
c1 = pd.read_csv(SRC / "c1_episodes.csv").rename(columns={"fault": "fault_mode"})


def mean_ci(v):
    v = np.asarray(pd.Series(v).dropna(), float); n = len(v)
    return v.mean(), (stats.t.ppf(0.975, n - 1) * v.std(ddof=1) / math.sqrt(n) if n > 1 else 0.0)


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf"); fig.savefig(OUT / f"{name}.png", dpi=600); plt.close(fig)
    print("saved", name)


# Guards
K = ["demand", "pattern", "fault_mode", "controller", "seed", "time_loss"]
GUARDS = [("A", "none / 90 s"), ("B", "20 s / 90 s"), ("C", "20 s / 60 s"), ("D", "20 s / 120 s")]
parts = [pd.concat([m[m.profile == "symmetric"][K], r[(r.set == "R1_field") & (r.profile == "symmetric")][K]]).assign(g="A"),
         r[r.set == "R2_mingreen20"][K].assign(g="B"), r[r.set == "R3_maxred60"][K].assign(g="C"),
         r[r.set == "R3_maxred120"][K].assign(g="D")]
A = pd.concat(parts)
A = A[(A.pattern == "phase_symmetric") & A.demand.isin(["medium", "high"])]

fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.35), sharey=False)
ctrls = ["std_mp_q", "std_mp_recall", "std_mp_maxrecall", "webster_fallback_mp", "pasa_cg_mp"]
for ax, dem in zip(axes, ["medium", "high"]):
    x0 = np.arange(len(GUARDS))
    for j, c in enumerate(ctrls):
        xs, ys, es = [], [], []
        for i, (g, _) in enumerate(GUARDS):
            v = A[(A.g == g) & (A.demand == dem) & (A.controller == c) & (A.fault_mode == "HZ")].time_loss
            if len(v) == 0:
                continue
            mu, ci = mean_ci(v); xs.append(i + (j - 2) * 0.07); ys.append(mu); es.append(ci)
        ax.errorbar(xs, ys, yerr=es, color=COLOR[c], marker=MARK[c], ms=3.5, lw=0.9, capsize=1.8,
                    elinewidth=0.6, label=LABEL[c], zorder=3 if c == "pasa_cg_mp" else 2)
    hv = [mean_ci(A[(A.g == g) & (A.demand == dem) & (A.controller == "std_mp_q") & (A.fault_mode == "NONE")].time_loss)[0]
          for g, _ in GUARDS]
    ax.plot(x0, hv, color="black", ls=":", lw=0.9, marker="_", ms=6, label="MP-Q, healthy detectors")
    ft = mean_ci(m[(m.profile == "symmetric") & (m.demand == dem) & (m.controller == "fixed_time") & (m.fault_mode == "NONE")].time_loss)[0]
    ax.axhline(ft, color=COLOR["fixed_time"], lw=0.8, ls="--", zorder=1)
    ax.text(-0.38, ft + 1.0, "Fixed time", fontsize=6.5, va="bottom", ha="left", color="#666666")
    ax.set_xticks(x0); ax.set_xticklabels([f"{g}\n{s}" for g, s in GUARDS])
    ax.set_xlim(-0.4, len(GUARDS) - 0.5)
    ax.set_title(f"{dem.capitalize()} demand", pad=3)
    ax.set_ylabel("Delay per trip (s)")
    ax.set_ylim(0, 135 if dem == "high" else 105)
axes[0].set_xlabel("Minimum green / max red", labelpad=2); axes[1].set_xlabel("Minimum green / max red", labelpad=2)
h, l = axes[0].get_legend_handles_labels()
h, l = h[1:] + h[:1], l[1:] + l[:1]
fig.legend(h, l, loc="upper center", ncol=6, frameon=False, bbox_to_anchor=(0.5, 1.07), handlelength=1.6, columnspacing=1.0)
fig.tight_layout(w_pad=1.5)
save(fig, "fig_rev_guards")

# Diagnosis delay
K2 = ["demand", "pattern", "fault_mode", "controller", "seed", "time_loss"]
g9 = r[r.set.str.startswith("R9_diagdelay")].copy(); g9["d"] = g9.set.str.extract(r"(\d+)$")[0].astype(int)
g0 = r[(r.set == "R1_field") & (r.profile == "symmetric")].assign(d=0)
G = pd.concat([g9, g0]); G = G[(G.pattern == "phase_symmetric") & (G.fault_mode == "HZ")]
c9 = r[r.set.str.startswith("R9_c1")].copy(); c9["d"] = c9.set.str.extract(r"(\d+)$")[0].astype(int)
c0 = r[r.set == "R8_c1_field"].assign(d=0)
C = pd.concat([c9, c0]); C = C[(C.pattern == "phase_symmetric") & (C.fault_mode == "HZ")]
panels = [("Grid, medium demand", G[G.demand == "medium"],
           m[(m.profile == "symmetric") & (m.demand == "medium") & (m.pattern == "phase_symmetric") & (m.fault_mode == "HZ")]),
          ("Grid, high demand", G[G.demand == "high"],
           m[(m.profile == "symmetric") & (m.demand == "high") & (m.pattern == "phase_symmetric") & (m.fault_mode == "HZ")]),
          ("Cologne1", C, c1[(c1.pattern == "phase_symmetric") & (c1.fault_mode == "HZ")])]
DL = [0, 5, 15, 30]
fig, axes = plt.subplots(1, 3, figsize=(COL2, 2.2))
for ax, (title, D, base) in zip(axes, panels):
    for c in ["std_mp_maxrecall", "webster_fallback_mp"]:
        mu = [mean_ci(D[(D.controller == c) & (D.d == d * 60)].time_loss) for d in DL]
        ax.errorbar(DL, [a for a, _ in mu], yerr=[b for _, b in mu], color=COLOR[c], marker=MARK[c], ms=3.5,
                    lw=0.9, capsize=1.8, elinewidth=0.6, label=LABEL[c])
    mu, ci = mean_ci(base[base.controller == "pasa_cg_mp"].time_loss)
    ax.axhspan(mu - ci, mu + ci, color=COLOR["pasa_cg_mp"], alpha=0.15, lw=0)
    ax.axhline(mu, color=COLOR["pasa_cg_mp"], lw=1.1, label="PASA-CG (no diagnosis)")
    mq = mean_ci(base[base.controller == "std_mp_q"].time_loss)[0]
    ax.axhline(mq, color=COLOR["std_mp_q"], lw=0.9, ls="--", label="MP-Q")
    ax.set_xticks(DL); ax.set_xlabel("Diagnosis delay (min)", labelpad=2)
    ax.set_title(title, pad=3); ax.set_ylim(0, 135)
axes[0].set_ylabel("Delay per trip (s)")
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.08), handlelength=1.8)
fig.tight_layout(w_pad=1.2)
save(fig, "fig_rev_diagdelay")
