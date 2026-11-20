"""Writes run_rev_w1.bat .. run_rev_w4.bat (one per terminal window) for the revision sweeps."""
from pathlib import Path

PROFILE_NET = {"symmetric": "sym", "asymmetric": "asym"}
FAULTS5 = "HZ SL GN ID DR"
FAULTS6 = "NONE HZ SL GN ID DR"
NEW_BASE = "std_mp_maxrecall webster_fallback_mp oracle_cg_mp"
ALL8 = "std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp oracle_cg_mp pasa_max_mp pasa_cg_mp"
PATS = ["single_approach", "cross_phase", "phase_symmetric", "distributed"]


def grid(w, out, profile, demand, pattern, ctrls, faults, extra=""):
    return (f"python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile {profile} "
            f"--demand-level {demand} --fault-pattern {pattern} --fault-severity high "
            f"--controllers {ctrls} --fault-modes {faults} --n-seeds 10 "
            f"--net-dir data/net_rev_w{w} --output-dir {out} {extra}").strip()


def c1(w, out, pattern, ctrls, faults, extra=""):
    return (f"python -m pasa_cg.main run-sweep --network cologne1 --demand-profile asymmetric "
            f"--fault-pattern {pattern} --fault-severity high --emissions "
            f"--controllers {ctrls} --fault-modes {faults} --n-seeds 10 "
            f"--net-dir data/net_c1_rev_w{w} --output-dir {out} {extra}").strip()


W = {1: [], 2: [], 3: [], 4: []}

# R1 field baselines with the main-sweep guards (no min green, max-red 90 s)
for w, prof in ((1, "symmetric"), (2, "asymmetric")):
    for dem in ("low", "medium", "high"):
        for pat in PATS:
            if dem == "low" and pat != "phase_symmetric":
                continue
            W[w].append(grid(w, f"results_rev/R1_field/{prof}/{dem}/{pat}", prof, dem, pat, NEW_BASE, FAULTS5))

# R2 minimum green 20 s, patterns A and B, symmetric medium/high
for dem in ("medium", "high"):
    for pat in ("phase_symmetric", "single_approach"):
        W[3].append(grid(3, f"results_rev/R2_mingreen20/symmetric/{dem}/{pat}", "symmetric", dem, pat,
                         ALL8, FAULTS6, "--min-green 20"))

# R3 max-red 60 / 120 s with min green 20 s, pattern B, dead detectors
for mr in (60, 120):
    for dem in ("medium", "high"):
        W[1].append(grid(1, f"results_rev/R3_maxred{mr}/symmetric/{dem}/phase_symmetric", "symmetric", dem,
                         "phase_symmetric", "std_mp_q std_mp_recall pasa_cg_mp", "NONE HZ",
                         f"--min-green 20 --max-red {mr}"))

# R4 planning-volume error (PASA-CG), patterns A and B
R4 = [("scale050", "--plan-scale 0.5"), ("scale080", "--plan-scale 0.8"), ("scale125", "--plan-scale 1.25"),
      ("scale200", "--plan-scale 2.0"), ("armnoise030", "--plan-noise 0.3")]
for name, flag in R4:
    for dem in ("medium", "high"):
        for pat, w in (("phase_symmetric", 3), ("single_approach", 2)):
            W[w].append(grid(w, f"results_rev/R4_plan_{name}/symmetric/{dem}/{pat}", "symmetric", dem, pat,
                             "pasa_cg_mp", "NONE HZ SL DR", flag))

# R5 threshold sensitivity (PASA-CG), medium symmetric, patterns A and B
R5 = [("hlo2", "--cg-param h_lo=2"), ("hlo8", "--cg-param h_lo=8"), ("klo03", "--cg-param k_lo=0.3"),
      ("klo07", "--cg-param k_lo=0.7"), ("hhi2", "--cg-param h_hi=2"), ("hhi5", "--cg-param h_hi=5"),
      ("khi025", "--cg-param k_hi=0.25"), ("khi10", "--cg-param k_hi=1.0")]
for name, flag in R5:
    for pat in ("phase_symmetric", "single_approach"):
        W[4].append(grid(4, f"results_rev/R5_cg_{name}/symmetric/medium/{pat}", "symmetric", "medium", pat,
                         "pasa_cg_mp", FAULTS6, flag))

# R6 fault realism: stuck at maximum, negative drift, gain 0.5; dead detectors that recover
R6C = "std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp"
for dem in ("medium", "high"):
    for pat in ("single_approach", "phase_symmetric"):
        W[4].append(grid(4, f"results_rev/R6_newfaults/symmetric/{dem}/{pat}", "symmetric", dem, pat, R6C, "SH ND GA"))
        W[1].append(grid(1, f"results_rev/R6_window/symmetric/{dem}/{pat}", "symmetric", dem, pat, R6C, "HZ",
                         "--fault-start 600 --fault-end 2100"))

# R7 full-lane exemption (high demand, all patterns)
for w, prof in ((1, "symmetric"), (2, "asymmetric")):
    for pat in PATS:
        W[w].append(grid(w, f"results_rev/R7_clip/{prof}/high/{pat}", prof, "high", pat, "pasa_cg_clip_mp", FAULTS6))

# R8 Cologne1: field baselines (main guards) and min green 20 s
for pat in PATS:
    W[2].append(c1(2, f"results_rev/R8_c1_field/{pat}", pat, NEW_BASE, FAULTS5))
W[3].append(c1(3, "results_rev/R8_c1_mingreen20/phase_symmetric", "phase_symmetric", ALL8, FAULTS6, "--min-green 20"))
W[3].append(c1(3, "results_rev/R8_c1_mingreen20/cross_phase", "cross_phase", ALL8, FAULTS6, "--min-green 20"))

here = Path(__file__).parent
for w, cmds in W.items():
    lines = ["@echo off", "setlocal", f"rem Revision sweeps, window {w}: {len(cmds)} runs.",
             "rem Run from the pasa_cg_code folder. Finished cells are skipped, so it can be restarted.",
             "if not exist results_rev mkdir results_rev",
             f"if not exist data\\net_c1_rev_w{w} xcopy /I /Y /Q data\\net_c1_phase_symmetric data\\net_c1_rev_w{w} >nul", ""]
    for k, c in enumerate(cmds, 1):
        lines += [f"echo [w{w} {k}/{len(cmds)}] {c.split('--output-dir ')[1].split()[0]}", c,
                  f"if errorlevel 1 echo FAILED w{w} run {k}: {c} >> results_rev\\failures_w{w}.txt", ""]
    lines += [f"echo Window {w} finished.", ""]
    (here / f"run_rev_w{w}.bat").write_text("\r\n".join(lines))


def eps(c):
    n_c = len(c.split("--controllers ")[1].split(" --fault-modes")[0].split())
    n_f = len(c.split("--fault-modes ")[1].split(" --n-seeds")[0].split())
    return n_c * n_f * 10


for w, cmds in W.items():
    g = sum(eps(c) for c in cmds if "grid2x2" in c)
    k = sum(eps(c) for c in cmds if "cologne1" in c)
    print(f"window {w}: {len(cmds)} runs, {g} grid episodes, {k} Cologne1 episodes")
