"""
Paper figures for PASA-CG (IEEE T-ITS style). Input: episodes_main.csv and
episodes_ablation.csv from analyse.py. Output: PDF + 600-dpi PNG per figure.

  fig_headline      both N-S detectors dead: network total delay by controller, demand, profile
  fig_heatmap_sym   % change in network total delay vs queue-only MP (symmetric)
  fig_heatmap_asym  same, asymmetric (with v/c variants)
  fig_ablation      % change vs full PASA-CG for each ablation variant
  fig_detection     PASA-CG detection rate by fault and pattern; healthy false-alarm rate
  fig_fairness      asymmetric demand: delay by entry side, healthy detectors

Usage: python figures.py <analysis_out_dir> <fig_dir>
"""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from scipy import stats

IN, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
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
         "pasa_mean_vc_mp": "PASA-mean (v/c)", "pasa_max_vc_mp": "PASA-max (v/c)", "pasa_cg_mp": "PASA-CG",
         "pasa_cg_nolo_mp": "no under-reporting test", "pasa_cg_nohi_mp": "no over-reporting test",
         "pasa_cg_nofrozen_mp": "no frozen test", "pasa_cg_nohyst_mp": "no hysteresis",
         "pasa_cg_nopartner_mp": "no partner replacement"}
# Paul Tol colour-blind-safe; PASA-CG red, baselines muted
COLOR = {"fixed_time": "#BBBBBB", "std_mp": "#4477AA", "std_mp_q": "#66CCEE", "std_mp_recall": "#228833",
         "pasa_max_mp": "#CCBB44", "pasa_mean_vc_mp": "#AA3377", "pasa_max_vc_mp": "#EE99AA", "pasa_cg_mp": "#CC3311"}
HATCH = {"fixed_time": "", "std_mp": "", "std_mp_q": "////", "std_mp_recall": "xxx", "pasa_max_mp": "...",
         "pasa_mean_vc_mp": "\\\\\\\\", "pasa_max_vc_mp": "--", "pasa_cg_mp": ""}
DEM = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
PAT = [("single_approach", "A: one approach"), ("cross_phase", "C: cross-phase"),
       ("phase_symmetric", "B: both N-S"), ("distributed", "D: distributed")]
FAULTS = ["HZ", "SL", "GN", "ID", "DR"]
FAULT_NAME = {"HZ": "dead", "SL": "stuck", "GN": "noise", "ID": "dropout", "DR": "drift"}
METRIC = "total_delay_vh"

main = pd.read_csv(IN / "episodes_main.csv"); abl = pd.read_csv(IN / "episodes_ablation.csv")


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf"); fig.savefig(OUT / f"{name}.png", dpi=600); plt.close(fig)
    print("saved", name)


def mean_ci(v):
    v = np.asarray(v, float); n = len(v)
    return v.mean(), (stats.t.ppf(0.975, n - 1) * v.std(ddof=1) / math.sqrt(n) if n > 1 else 0.0)


def holm(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); adj = np.empty(n); run = 0
    for r, i in enumerate(o):
        run = max(run, (n - r) * p[i]); adj[i] = min(run, 1)
    return adj


def rel_vs(df, ref, ctrls, metric=METRIC):
    """Per scenario: % change of each controller vs ref, paired by seed, Holm within scenario."""
    out = []
    for key, g in df.groupby(["profile", "demand", "pattern", "fault_mode"]):
        B = g[g.controller == ref].set_index("seed")[metric]
        fam = []
        for c in ctrls:
            A = g[g.controller == c].set_index("seed")[metric]
            s = A.index.intersection(B.index)
            if len(s) < 2:
                continue
            d = (A[s] - B[s]).to_numpy(float)
            p = stats.ttest_rel(A[s], B[s]).pvalue if d.std() > 0 else (1.0 if d.mean() == 0 else 0.0)
            fam.append(dict(profile=key[0], demand=key[1], pattern=key[2], fault=key[3], controller=c,
                            rel=100 * d.mean() / B[s].mean(), p=p))
        for r, pa in zip(fam, holm([r["p"] for r in fam]) if fam else []):
            r["sig"] = pa < 0.05
        out += fam
    return pd.DataFrame(out)


# Fig 1: headline, both N-S detectors dead
def fig_headline():
    # aggregation variants (PASA-max, v/c) are reported in the companion ITSC paper, not here
    ctrl_sets = {"symmetric": ["fixed_time", "std_mp", "std_mp_q", "std_mp_recall", "pasa_cg_mp"],
                 "asymmetric": ["fixed_time", "std_mp", "std_mp_q", "std_mp_recall", "pasa_cg_mp"]}
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.35), sharey=True)
    for ax, prof in zip(axes, ["symmetric", "asymmetric"]):
        ctrls = ctrl_sets[prof]; w = 0.84 / len(ctrls)
        for k, c in enumerate(ctrls):
            for j, (dm, _) in enumerate(DEM):
                g = main[(main.profile == prof) & (main.demand == dm) & (main.pattern == "phase_symmetric")
                         & (main.fault_mode == "HZ") & (main.controller == c)]
                h = main[(main.profile == prof) & (main.demand == dm) & (main.pattern == "phase_symmetric")
                         & (main.fault_mode == "NONE") & (main.controller == "std_mp_q")]
                m, ci = mean_ci(g[METRIC])
                x = j + (k - (len(ctrls) - 1) / 2) * w
                ax.bar(x, m, w * 0.92, yerr=ci, color=COLOR[c], hatch=HATCH[c], edgecolor="black", linewidth=0.4,
                       error_kw=dict(lw=0.6, capsize=1.2), label=LABEL[c] if j == 0 else None, zorder=2)
                if k == 0:
                    hm, _ = mean_ci(h[METRIC])
                    ax.plot([j - 0.44, j + 0.44], [hm, hm], color="black", lw=0.7, ls=":", zorder=3,
                            label="MP-Q, healthy detectors" if j == 0 else None)
        ax.set_xticks(range(3)); ax.set_xticklabels([f"{n} demand" for _, n in DEM])
        ax.set_title(f"{prof.capitalize()} demand", pad=3)
        ax.yaxis.grid(True, lw=0.3, color="#DDDDDD", zorder=0); ax.set_axisbelow(True)
    axes[0].set_ylabel("Network total delay (veh-h)")
    h, l = axes[1].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.13), handlelength=1.6)
    save(fig, "fig_headline_both_NS_dead")


# Fig 2/3: heatmaps vs queue-only MP
CMAP = LinearSegmentedColormap.from_list("bw", ["#2166AC", "#92C5DE", "#F7F7F7", "#F4A582", "#B2182B"])


def heatmap(df, ref, ctrls, profiles, name, demands=DEM, title_fmt="{prof}, {dem} demand", lim=30):
    R = rel_vs(df, ref, ctrls)
    panels = [(p, d) for p in profiles for d in demands]
    row_h = 0.16 * len(ctrls) + 0.42
    fig = plt.figure(figsize=(COL2, row_h * len(panels) + 0.55))
    gs = fig.add_gridspec(len(panels), 2, width_ratios=[60, 1], hspace=0.55, wspace=0.02)
    cols = [(p, f) for p, _ in PAT for f in FAULTS]
    for r_i, (prof, (dm, dname)) in enumerate(panels):
        ax = fig.add_subplot(gs[r_i, 0])
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
        last = r_i == len(panels) - 1
        ax.set_xticklabels([FAULT_NAME[f] for _, f in cols] if last else [], rotation=90)
        for k in range(1, len(PAT)):
            ax.axvline(k * len(FAULTS) - 0.5, color="black", lw=0.8)
        for k, (_, pn) in enumerate(PAT):
            ax.text(k * len(FAULTS) + (len(FAULTS) - 1) / 2, -0.62, pn, ha="center", va="bottom", fontsize=6.5)
        ax.text(-0.01, 1.0, title_fmt.format(prof=prof.capitalize(), dem=dname.lower()), transform=ax.transAxes,
                ha="right", va="bottom", fontsize=7.5, fontweight="bold")
        ax.tick_params(length=0); [s_.set_visible(False) for s_ in ax.spines.values()]
    cax = fig.add_subplot(gs[:, 1])
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=TwoSlopeNorm(0, -lim, lim))
    cb = fig.colorbar(sm, cax=cax)
    cb.set_label(f"Change in network total delay vs {LABEL[ref]} (%)", fontsize=7)
    cb.set_ticks([-lim, -lim/2, 0, lim/2, lim]); cb.set_ticklabels([f"≤{-lim}", f"{-lim//2}", "0", f"+{lim//2}", f"≥+{lim}"])
    cb.ax.tick_params(labelsize=6)
    save(fig, name)
    return R


# Fig 5: detection
DEM_COLOR = {"low": "#EECC66", "medium": "#6699CC", "high": "#004488"}   # light -> dark, reads in greyscale


def fig_detection():
    g = main[(main.controller == "pasa_cg_mp") & (main.profile == "symmetric")]
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.0), gridspec_kw=dict(width_ratios=[4, 1.1]))
    ax = axes[0]; w = 0.27
    for k in range(len(PAT)):                       # shade alternate pattern groups
        if k % 2 == 1:
            ax.axvspan(k * 6 - 0.6, k * 6 + 4.6, color="#F2F2F2", zorder=0, lw=0)
    for j, (dm, dn) in enumerate(DEM):
        xs, ms, cs = [], [], []
        for k, (p, _) in enumerate(PAT):
            for i, f in enumerate(FAULTS):
                v = g[(g.demand == dm) & (g.pattern == p) & (g.fault_mode == f)]["cg_tpr"].dropna()
                m, ci = mean_ci(v); xs.append(k * 6 + i + (j - 1) * w); ms.append(m); cs.append(ci)
        ax.bar(xs, ms, w * 0.95, yerr=cs, color=DEM_COLOR[dm], edgecolor="black", linewidth=0.3,
               error_kw=dict(lw=0.5, capsize=0.8), label=f"{dn} demand", zorder=2)
    ax.set_xticks([k * 6 + i for k in range(4) for i in range(5)])
    ax.set_xticklabels([FAULT_NAME[f] for _ in PAT for f in FAULTS], rotation=90)
    for k, (_, pn) in enumerate(PAT):
        ax.text(k * 6 + 2, 1.03, pn, ha="center", fontsize=7, transform=ax.get_xaxis_transform())
    ax.set_xlim(-0.8, 22.8); ax.set_ylim(0, 1); ax.set_ylabel("Detection rate\n(faulted lane-decisions flagged)")
    ax.yaxis.grid(True, lw=0.3, color="#DDDDDD", zorder=1); ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.30))
    ax = axes[1]
    for j, (dm, dn) in enumerate(DEM):
        for k, prof in enumerate(["symmetric", "asymmetric"]):
            v = main[(main.controller == "pasa_cg_mp") & (main.profile == prof) & (main.demand == dm)
                     & (main.fault_mode == "NONE")]["cg_fpr"]
            m, ci = mean_ci(v)
            ax.bar(j + (k - 0.5) * 0.38, 100 * m, 0.36, yerr=100 * ci, color=DEM_COLOR[dm], edgecolor="black",
                   linewidth=0.4, hatch=["", "////"][k], error_kw=dict(lw=0.5, capsize=1), zorder=2)
    from matplotlib.patches import Patch
    ax.legend([Patch(facecolor="white", edgecolor="black"), Patch(facecolor="white", edgecolor="black", hatch="////")],
              ["symmetric", "asymmetric"], frameon=False, fontsize=6, loc="upper right")
    ax.set_xticks(range(3)); ax.set_xticklabels([n for _, n in DEM])
    ax.set_ylabel("False-alarm rate,\nhealthy detectors (%)")
    ax.yaxis.grid(True, lw=0.3, color="#DDDDDD", zorder=1); ax.set_axisbelow(True)
    fig.subplots_adjust(wspace=0.35)
    save(fig, "fig_detection")


# Fig 6: fairness (paired bars: major vs minor entries per controller)
SHORT = {"fixed_time": "Fixed\ntime", "std_mp": "Std-MP", "std_mp_q": "Queue-\nonly MP", "pasa_max_mp": "PASA-\nmax",
         "pasa_mean_vc_mp": "PASA-mean\n(v/c)", "pasa_max_vc_mp": "PASA-max\n(v/c)", "pasa_cg_mp": "PASA-\nCG"}


def fig_fairness():
    ctrls = ["fixed_time", "std_mp", "std_mp_q", "pasa_max_mp", "pasa_mean_vc_mp", "pasa_max_vc_mp", "pasa_cg_mp"]
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.5), sharey=True)
    for ax, (dm, dn) in zip(axes, [("medium", "Medium"), ("high", "High")]):
        g = main[(main.profile == "asymmetric") & (main.demand == dm) & (main.fault_mode == "NONE")
                 & (main.pattern == "single_approach")]
        for k, c in enumerate(ctrls):
            e = g[g.controller == c]
            maj = (e.delay_S + e.delay_W) / 2; mino = (e.delay_N + e.delay_E) / 2
            m1, c1 = mean_ci(maj); m2, c2 = mean_ci(mino)
            ax.bar(k - 0.19, m1, 0.36, yerr=c1, color=COLOR[c], edgecolor="black", lw=0.4, error_kw=dict(lw=0.5, capsize=1))
            ax.bar(k + 0.19, m2, 0.36, yerr=c2, color="white", edgecolor=COLOR[c], hatch="////", lw=0.6,
                   error_kw=dict(lw=0.5, capsize=1))
            # Jain's index on one fixed row above the bars, clear of error bars
            ax.text(k, 42, f"{e.delay_jain.mean():.2f}", ha="center", va="center", fontsize=6.5)
        ax.text(-0.75, 42, "Jain", ha="right", va="center", fontsize=6.5, style="italic")
        ax.axhline(39.5, color="#BBBBBB", lw=0.4)
        ax.set_ylim(0, 44); ax.set_yticks(range(0, 40, 5))
        ax.set_xticks(range(len(ctrls))); ax.set_xticklabels([LABEL[c] for c in ctrls], rotation=35, ha="right", rotation_mode="anchor")
        ax.set_title(f"Asymmetric, {dn.lower()} demand, healthy detectors", pad=3)
        ax.yaxis.grid(True, lw=0.3, color="#DDDDDD"); ax.set_axisbelow(True)
    axes[0].set_ylabel("Mean time loss per vehicle (s)")
    from matplotlib.patches import Patch
    fig.legend([Patch(facecolor="#777777", edgecolor="black"), Patch(facecolor="white", edgecolor="#777777", hatch="////")],
               ["major entries (S, W; 1.4x demand)", "minor entries (N, E; 0.6x demand)"], frameon=False,
               loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.06))
    fig.subplots_adjust(wspace=0.12)
    save(fig, "fig_fairness_asymmetric")


fig_headline()
Rs = heatmap(main, "std_mp_q", ["std_mp", "std_mp_recall", "pasa_cg_mp"], ["symmetric"], "fig_heatmap_symmetric")
Ra = heatmap(main, "std_mp_q", ["std_mp", "std_mp_recall", "pasa_cg_mp"],
             ["asymmetric"], "fig_heatmap_asymmetric")
Rab = heatmap(abl, "pasa_cg_mp", ["pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp", "pasa_cg_nohyst_mp",
                                  "pasa_cg_nopartner_mp"], ["symmetric"], "fig_ablation",
              demands=[("medium", "Medium"), ("high", "High")])
fig_detection()  # fig_fairness moved to the companion paper
pd.concat([Rs.assign(fig="heatmap_sym"), Ra.assign(fig="heatmap_asym"), Rab.assign(fig="ablation")]).to_csv(
    OUT / "figure_data_relative_changes.csv", index=False)
