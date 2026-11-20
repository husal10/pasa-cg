"""
Fig. 1 of the ITSC companion paper: the 2x2 SUMO grid drawn from its network file, with the
faulted junction (I_SE) and the four spatial fault patterns A-D at that junction.

Lane geometry, junction outlines and lane indices are read from grid2x2.net.xml with sumolib,
so the drawing is the simulated network itself. Fault sets follow pasa_itsc/env/sumo_env.py:
  A single_approach  N            (odd seeds: W)
  B phase_symmetric  N + S        (odd seeds: W + E)
  C cross_phase      N + W        (same set for both orientations)
  D distributed      N lane 0, S lane 1, E lane 0, W lane 1   (lane 0 = rightmost)

Usage: SUMO_HOME=... python fig_conf_network.py <grid2x2.net.xml> <fig_dir>
"""
import os, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyArrowPatch, Rectangle, ConnectionPatch

if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402  (from SUMO_HOME/tools or pip install sumolib)

NET, OUT = sys.argv[1], Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 8, "axes.titlesize": 8, "legend.fontsize": 7,
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "hatch.linewidth": 0.6,
})
ROAD, JUNC, EDGE = "#D9D9D9", "#BDBDBD", "#9E9E9E"
DET, FAULT, TXT = "#0077BB", "#CC3311", "#222222"
FJ = "I_SE"

net = sumolib.net.readNet(NET)
xmin, ymin, xmax, ymax = net.getBoundary()


def lane_poly(lane):
    (x0, y0), (x1, y1) = lane.getShape()[0], lane.getShape()[-1]
    d = np.array([x1 - x0, y1 - y0]); d /= np.linalg.norm(d); n = np.array([-d[1], d[0]]) * lane.getWidth() / 2
    p0, p1 = np.array([x0, y0]), np.array([x1, y1])
    return [p0 + n, p1 + n, p1 - n, p0 - n]


# approach of each lane entering the faulted junction, from its direction of travel
def approach(edge):
    (x0, y0), (x1, y1) = edge.getLanes()[0].getShape()[0], edge.getLanes()[0].getShape()[-1]
    dx, dy = x1 - x0, y1 - y0
    if abs(dy) > abs(dx):
        return "N" if dy < 0 else "S"
    return "E" if dx < 0 else "W"


incoming = {approach(e): e for e in net.getEdges() if e.getToNode().getID() == FJ}
PATTERNS = [("A", "One approach", {("N", i) for i in range(3)}),
            ("B", "Both N–S approaches", {(a, i) for a in "NS" for i in range(3)}),
            ("C", "Cross-phase", {(a, i) for a in "NW" for i in range(3)}),
            ("D", "One lane per arm", {("N", 0), ("S", 1), ("E", 0), ("W", 1)})]


def draw_net(ax, fault=None, zoom=False):
    for e in net.getEdges():
        into_fj = e.getToNode().getID() == FJ
        for ln in e.getLanes():
            fc, hatch, ec = ROAD, None, "white"
            if into_fj:
                key = (approach(e), ln.getIndex())
                if fault is not None and key in fault:
                    fc, hatch, ec = FAULT, "////", "white"
                elif zoom or fault is None:
                    fc = DET
            ax.add_patch(Polygon(lane_poly(ln), closed=True, fc=fc, ec=ec, lw=0.25 if zoom else 0.15,
                                 hatch=hatch, zorder=2))
    for nd in net.getNodes():
        shp = nd.getShape()
        if len(shp) >= 3:
            ax.add_patch(Polygon(shp, closed=True, fc=JUNC, ec="none", zorder=3))


# layout
fig = plt.figure(figsize=(7.16, 3.0))
gs = fig.add_gridspec(2, 4, width_ratios=[2.15, 0.12, 1, 1], wspace=0.06, hspace=0.18)
ax = fig.add_subplot(gs[:, 0])
draw_net(ax)
ax.set_xlim(xmin - 20, xmax + 20); ax.set_ylim(ymin - 20, ymax + 25); ax.set_aspect("equal"); ax.axis("off")

# junction labels and signal markers
lab_off = {"I_NW": (-14, 14), "I_NE": (14, 14), "I_SW": (-14, -14), "I_SE": (-30, -30)}
for jid, (ox, oy) in lab_off.items():
    x, y = net.getNode(jid).getCoord()
    ax.text(x + ox, y + oy, jid.replace("_", "\\_") if False else jid, ha="left" if ox > 0 else "right",
            va="bottom" if oy > 0 else "top", fontsize=7, color=TXT, zorder=6,
            fontweight="bold" if jid == FJ else "normal")
fx, fy = net.getNode(FJ).getCoord()
ax.add_patch(Rectangle((fx - 32, fy - 32), 64, 64, fill=False, ec=FAULT, lw=1.0, ls="--", zorder=7))

# demand entries: arrows into the network at the 8 boundary stubs, with asymmetric multipliers
for nd in net.getNodes():
    if nd.getType() != "dead_end":
        continue
    x, y = nd.getCoord()
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    side = ("S" if y < cy - 150 else "N" if y > cy + 150 else "W" if x < cx else "E")
    v = {"N": (0, -1), "S": (0, 1), "E": (-1, 0), "W": (1, 0)}[side]
    mult = {"N": "0.6", "E": "0.6", "S": "1.4", "W": "1.4"}[side]
    # offset to the inbound carriageway (right-hand traffic)
    off = {"N": (-5, 0), "S": (5, 0), "E": (0, 5), "W": (0, -5)}[side]
    sx, sy = x + off[0] - v[0] * 4, y + off[1] - v[1] * 4
    ax.add_patch(FancyArrowPatch((sx, sy), (sx + v[0] * 46, sy + v[1] * 46), arrowstyle="-|>",
                                 mutation_scale=6, lw=0.8, color=TXT, zorder=6))
    tx, ty = sx - v[0] * 6 + (-v[1]) * 0, sy - v[1] * 6
    ax.text(tx + (14 if side in "NS" else 0), ty + (0 if side in "NS" else -12),
            f"×{mult}", fontsize=6, ha="center", va="center", color="#555555", zorder=6)

# north arrow and scale bar
ax.annotate("", xy=(xmin + 10, ymax - 5), xytext=(xmin + 10, ymax - 45),
            arrowprops=dict(arrowstyle="-|>", lw=0.8, color=TXT, mutation_scale=6))
ax.text(xmin + 10, ymax + 2, "N", ha="center", va="bottom", fontsize=7)
for x0 in (xmin + 30, xmin + 130):
    ax.plot([x0, x0], [ymin + 25, ymin + 35], color=TXT, lw=0.8)
ax.plot([xmin + 30, xmin + 130], [ymin + 30, ymin + 30], color=TXT, lw=1.2)
ax.text(xmin + 80, ymin + 38, "100 m", ha="center", va="bottom", fontsize=6.5)
ax.text(xmin + 205, ymin + 300, "", fontsize=6)

# zoom panels
for k, (pid, name, fset) in enumerate(PATTERNS):
    a = fig.add_subplot(gs[k // 2, 2 + k % 2])
    draw_net(a, fault=fset, zoom=True)
    a.set_xlim(fx - 62, fx + 62); a.set_ylim(fy - 62, fy + 62); a.set_aspect("equal")
    a.set_xticks([]); a.set_yticks([])
    for s in a.spines.values():
        s.set_color(FAULT); s.set_linestyle("--"); s.set_linewidth(0.7)
    a.set_title(f"{pid}: {name}", fontsize=7, pad=2)
    for arm, (dx, dy) in {"N": (-22, 55), "S": (22, -55), "E": (55, 22), "W": (-55, -22)}.items():
        a.text(fx + dx, fy + dy, arm, fontsize=6.5, ha="center", va="center", color=TXT,
               bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85), zorder=8)

# connector from the dashed box to the zoom panels
for (xa, ya), (xb, yb), axb in [((fx + 32, fy + 32), (0, 0), fig.axes[1]), ((fx + 32, fy - 32), (0, 1), fig.axes[3])]:
    con = ConnectionPatch(xyA=(xa, ya), coordsA=ax.transData, xyB=(xb, yb), coordsB=axb.transAxes,
                          color=FAULT, lw=0.5, ls="--", zorder=1)
    fig.add_artist(con)

# legend
from matplotlib.patches import Patch
handles = [Patch(fc=DET, ec="white", label="Approach lane at I_SE, healthy detector"),
           Patch(fc=FAULT, ec="white", hatch="////", label="Faulty detector"),
           Patch(fc=ROAD, ec="white", label="Other lane")]
fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.52, 0.0),
           handlelength=1.6, columnspacing=1.4)
fig.savefig(OUT / "fig_conf_network.pdf"); fig.savefig(OUT / "fig_conf_network.png", dpi=600)
print("saved fig_conf_network")
