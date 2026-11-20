"""
Flow chart of PASA-CG (consistency-gated phase-aware structural aggregation):
one decision step at one junction.  Mirrors pasa_cg/sensors/pasa_cg.py (v3.2)
and the pasa_cg_mp branch of env/sumo_env.py.

Output: fig_pasa_cg_flow.{pdf,svg,png}  (IEEE double column, 7.16 in wide)
Run:    python fig_pasa_cg_flow.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
from matplotlib.lines import Line2D

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "savefig.dpi": 600,
})

# palette: tints only, so the figure reads in greyscale; red reserved for faults
INK = "#1a1a1a"
C_DET = "#D9E6F2"   # detection (blue tint)
C_GATE = "#F5E2CB"  # gating (orange tint)
C_REP = "#D7ECE4"   # replacement (teal tint)
C_CTL = "#E4E4E4"   # control (grey)
C_FAULT = "#CC3311"
LW = 0.6

W, H = 7.16, 6.72
fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

X0, X1 = 0.50, 6.70          # content span
XC = (X0 + X1) / 2


def box(x0, y0, x1, y1, fc="white", ec=INK, lw=LW, ls="-", r=0.04, z=2):
    p = FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                       boxstyle=f"round,pad=0,rounding_size={r}",
                       fc=fc, ec=ec, lw=lw, ls=ls, zorder=z)
    ax.add_patch(p)
    return p


def card(x0, y0, x1, y1, title, fc, hh=0.20):
    """Box with a tinted header bar."""
    box(x0, y0, x1, y1)
    ax.add_patch(Rectangle((x0, y1 - hh), x1 - x0, hh, fc=fc, ec=INK, lw=LW, zorder=2.5))
    t(((x0 + x1) / 2), y1 - hh / 2, title, weight="bold", size=8)


def t(x, y, s, size=8, ha="center", va="center", z=5, **kw):
    return ax.text(x, y, s, size=size, ha=ha, va=va, zorder=z, color=kw.pop("color", INK), **kw)


def arrow(xy0, xy1, color=INK, lw=LW, z=3):
    ax.annotate("", xy=xy1, xytext=xy0, zorder=z,
                arrowprops=dict(arrowstyle="-|>,head_length=0.32,head_width=0.16",
                                lw=lw, color=color, shrinkA=0, shrinkB=0))


def line(xs, ys, color=INK, lw=LW, ls="-", z=3):
    ax.add_line(Line2D(xs, ys, color=color, lw=lw, ls=ls, zorder=z, solid_capstyle="butt"))


def diamond(xc, yc, w, h, s, size=8):
    ax.add_patch(Polygon([(xc - w / 2, yc), (xc, yc + h / 2), (xc + w / 2, yc), (xc, yc - h / 2)],
                         closed=True, fc="white", ec=INK, lw=LW, zorder=2))
    t(xc, yc, s, size=size)


def stage(y0, y1, label):
    xs = 0.30
    line([xs + 0.06, xs, xs, xs + 0.06], [y1, y1, y0, y0], lw=0.5, color="#555555")
    t(xs - 0.10, (y0 + y1) / 2, label, size=8, rotation=90, style="italic", color="#444444")


# 1  inputs
yi0, yi1 = 6.24, 6.60
box(1.55, yi0, X1, yi1)
t((1.55 + X1) / 2, yi1 - 0.11,
  r"Detector readings $q_l$, 12 lanes ($N,S,E,W\times3$)     current green phase $\phi_t$     planning v/c $w_a$ per arm")
t((1.55 + X1) / 2, yi0 + 0.10,
  r"lane $l$ on arm $a$;  partner lane $p$ = same lane index on the opposite arm, which shares the green",
  size=7.5, style="italic", color="#333333")
# faults enter the readings
fx = 0.62
t(0.92, yi1 - 0.09, "sensor faults", size=7.5, color=C_FAULT, weight="bold")
t(0.92, yi0 + 0.10, "HZ, SL, GN, ID, DR", size=7, color=C_FAULT)
arrow((1.33, (yi0 + yi1) / 2), (1.55, (yi0 + yi1) / 2), color=C_FAULT, lw=0.9)

# 2  preprocessing
yp0, yp1 = 5.68, 6.00
arrow((XC + 0.52, yi0), (XC + 0.52, yp1))
box(X0, yp0, X1, yp1, fc="white")
t(XC, (yp0 + yp1) / 2,
  r"Clip $q_l$ to $[0,q_{\max}]$     per arm: red time $r_a$, consecutive green decisions $g_a$"
  r"     expected arrivals per lane $\lambda_a\Delta t = w_a\, s\,\Delta t / 3600$")
stage(yp0, yi1, "Input")

# 3  detection: three consistency tests
yd0, yd1 = 3.88, 5.38
gap = 0.18
cw = (X1 - X0 - 2 * gap) / 3
cx = [X0 + k * (cw + gap) for k in range(3)]
mid = [c + cw / 2 for c in cx]
# fan-out from preprocessing
ysplit = (yp0 + yd1) / 2
line([XC, XC], [yp0, ysplit])
line([mid[0], mid[2]], [ysplit, ysplit])
for m in mid:
    arrow((m, ysplit), (m, yd1))

tests = [
    ("Under-reporting test",
     r"while arm $a$ is red at $t-1$ and $t$",
     [r"$C^{\mathrm{lo}}_l \leftarrow \max\{0,\ C^{\mathrm{lo}}_l$",
      r"$\qquad +\,(1-k_{\mathrm{lo}})\,\lambda_a\Delta t - \Delta q_l\}$"],
     "a red queue must grow with arrivals;\nshortfall accumulates",
     "dead, stuck-low, dropout"),
    ("Over-reporting test",
     r"from the 2nd green decision ($g_a \geq 2$)",
     [r"$C^{\mathrm{hi}}_l \leftarrow \max\{0,\ C^{\mathrm{hi}}_l + e_l\, q_l - k_{\mathrm{hi}}\}$",
      r"$e_l\!=\!1$: partner lane trusted and empty,",
      r"$q_l \geq 1$ and $q_l \geq q^{\mathrm{prev}}_l$"],
     "queue persists after the partner\nlane has discharged",
     "drift, positive bias, stuck-high"),
    ("Frozen-reading test",
     r"from the 2nd green decision; reset while red",
     [r"$n_l \leftarrow n_l + 1$  if  $q_l = q^{\mathrm{prev}}_l \geq 1$",
      r"$n_l \leftarrow 0$  otherwise"],
     "a discharging queue cannot keep\nthe same non-zero count",
     "stuck at a constant value"),
]
for k, (title, cond, eqs, why, catches) in enumerate(tests):
    x0, x1 = cx[k], cx[k] + cw
    card(x0, yd0, x1, yd1, title, C_DET)
    t(mid[k], yd1 - 0.33, cond, size=7.5, style="italic")
    ey = yd1 - 0.54
    for e in eqs:
        t(mid[k], ey, e, size=8)
        ey -= 0.165
    t(mid[k], yd0 + 0.37, why, size=7.5, linespacing=1.15, color="#333333")
    line([x0 + 0.08, x1 - 0.08], [yd0 + 0.20, yd0 + 0.20], lw=0.4, color="#888888")
    t(mid[k], yd0 + 0.10, "catches: " + catches, size=7.5, style="italic")
stage(yd0, yd1, "Detect")

# 4  gate: flags with hysteresis
yg0, yg1 = 2.83, 3.55
ymerge = (yd0 + yg1) / 2
for m in mid:
    line([m, m], [yd0, ymerge])
line([mid[0], mid[2]], [ymerge, ymerge])
arrow((XC, ymerge), (XC, yg1))
card(X0, yg0, X1, yg1, "Flag each lane, with hysteresis", C_GATE)
t(X0 + 0.15, yg1 - 0.33,
  r"$\mathbf{set}$    $C^{\mathrm{lo}}_l \geq \theta_a$   or   $C^{\mathrm{hi}}_l \geq h_{\mathrm{hi}}$   or   $n_l \geq n^{*}$,"
  r"      with   $\theta_a = \max\{h_{\mathrm{lo}}\,\lambda_a\Delta t,\ h^{\min}_{\mathrm{lo}}\}$",
  ha="left")
t(X0 + 0.15, yg1 - 0.55,
  r"$\mathbf{keep}$  already flagged and ( $C^{\mathrm{lo}}_l \geq \rho\,\theta_a$   or   $C^{\mathrm{hi}}_l \geq \rho\, h_{\mathrm{hi}}$   or   $n_l > 0$ );"
  r"     otherwise the lane is trusted",
  ha="left")
stage(yg0, yg1, "Gate")

# 5  replacement: decision tree
dy = 2.30
dw, dh = 1.10, 0.46
xd1, xd2, xd3 = 1.25, 2.95, 4.55
xb4 = 6.12
diamond(xd1, dy, dw, dh, r"lane $l$ flagged?")
diamond(xd2, dy, dw + 0.12, dh, r"partner $p$ trusted?")
diamond(xd3, dy, dw, dh, r"arm $a$ red?")
arrow((xd1, yg0), (xd1, dy + dh / 2))
arrow((xd1 + dw / 2, dy), (xd2 - (dw + 0.12) / 2, dy))
arrow((xd2 + (dw + 0.12) / 2, dy), (xd3 - dw / 2, dy))
t((xd1 + xd2) / 2 - 0.08, dy + 0.07, "yes", size=7.5, style="italic")
t((xd2 + xd3) / 2 + 0.03, dy + 0.07, "no", size=7.5, style="italic")

yr0, yr1 = 1.33, 1.75
bw = 1.22
repl = [
    (xd1, r"$\tilde q_l = q_l$", "pass through", "no"),
    (xd2, r"$\tilde q_l = q_p\, w_a / w_p$", "partner, scaled by v/c", "yes"),
    (xd3, r"$\tilde q_l = \min\{\lambda_a \min(r_a, r_{\max}),\, q_{\max}\}$", "planning arrivals over red", "yes"),
    (xb4 + 0.05, r"$\tilde q_l = \gamma\, \tilde q^{\,\mathrm{prev}}_l$", "decays while green", "no"),
]
for k, (x, eq, lab, yn) in enumerate(repl):
    w_ = bw + (0.58 if k == 2 else 0.0)
    if k == 2:
        x0b = x - w_ / 2 + 0.12
    else:
        x0b = x - w_ / 2
    if k == 2:
        x0b = xd3 - w_ / 2
    if k == 3:
        x0b = 5.62
        w_ = X1 - 5.62
    box(x0b, yr0, x0b + w_, yr1, fc=C_REP)
    xm = x0b + w_ / 2
    t(xm, yr1 - 0.14, eq, size=8)
    t(xm, yr0 + 0.10, lab, size=7.5, style="italic", color="#333333")
    if k < 3:
        arrow((x, dy - dh / 2), (x, yr1))
        t(x + 0.10, (dy - dh / 2 + yr1) / 2, yn, size=7.5, style="italic", ha="left")
    else:
        xe = (5.62 + X1) / 2
        line([xd3 + dw / 2, xe], [dy, dy])
        arrow((xe, dy), (xe, yr1))
        t(xe + 0.10, (dy - dh / 2 + yr1) / 2 + 0.12, yn, size=7.5, style="italic", ha="left")
stage(yr0, dy + dh / 2, "Replace")

# 6  control
yc0, yc1 = 0.40, 0.92
ymerge2 = (yr0 + yc1) / 2
xs_out = [xd1, xd2, xd3, (5.62 + X1) / 2]
for x in xs_out:
    line([x, x], [yr0, ymerge2])
line([xs_out[0], xs_out[-1]], [ymerge2, ymerge2])
arrow((XC, ymerge2), (XC, yc1))
card(X0, yc0, X1, yc1, "Queue-only max-pressure on the gated readings", C_CTL, hh=0.19)
t(XC, yc0 + 0.17,
  r"$\phi_{t+1} = \arg\max_{\phi}\ \sum_{l \in \phi} \tilde q_l$   (tie keeps $\phi_t$)"
  r"   $\rightarrow$   max-red guard $r_{\max}$   $\rightarrow$   signal for $\Delta t$")
stage(yc0, yc1, "Control")

# property callout
t(X0 + 0.02, (yc1 + yr0) / 2 - 0.0,
  "", size=7.5)
cx0, cy0 = X0 + 0.02, ymerge2 + 0.02
# feedback: state carried to the next decision
xf = 6.92
line([X1, xf], [(yc0 + yc1) / 2, (yc0 + yc1) / 2])
line([xf, xf], [(yc0 + yc1) / 2, (yi0 + yi1) / 2])
arrow((xf, (yi0 + yi1) / 2), (X1, (yi0 + yi1) / 2))
t(xf + 0.10, (yc1 + yi0) / 2,
  r"next decision $t+\Delta t$: carry $q^{\mathrm{prev}}$, $\tilde q^{\,\mathrm{prev}}$, $C^{\mathrm{lo}}$, $C^{\mathrm{hi}}$, $n$ and flags",
  size=7.5, rotation=90, style="italic")

# parameters
t(XC + 0.1, 0.16,
  r"$s=1800$ veh/h,  $\Delta t=10$ s,  $q_{\max}=20$ veh,  $k_{\mathrm{lo}}=0.5$,  $h_{\mathrm{lo}}=4$,  "
  r"$h^{\min}_{\mathrm{lo}}=3$ veh,  $k_{\mathrm{hi}}=0.5$ veh,  $h_{\mathrm{hi}}=3$ veh,  $n^{*}=3$,  "
  r"$\rho=0.25$,  $r_{\max}=90$ s,  $\gamma=0.3$",
  size=7.5, color="#333333")

# identity callout next to pass-through
box(2.05, 2.60, 5.95, 2.76, fc="white", ls=(0, (3, 2)), lw=0.5, r=0.02)
t(4.0, 2.68, r"no lane flagged $\Rightarrow\ \tilde q = q$:  exactly queue-only max-pressure",
  size=7.5, style="italic", color="#333333")

for ext in ("pdf", "svg", "png"):
    fig.savefig(f"fig_pasa_cg_flow.{ext}", facecolor="white")
print("saved")
