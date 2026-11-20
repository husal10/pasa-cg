"""
pasa_itsc.evaluation.experiment
===============================
Sweep runner: every controller x fault mode x seed for one scenario (network,
demand profile and level, fault pattern and severity). Each finished
controller x fault cell is written as it completes, so an interrupted sweep
resumes where it stopped; the scenario is written to all_results.json with the
settings, the analysis plan and a provenance record (code hash, SUMO version).

    from pasa_itsc.evaluation.experiment import run_fault_sweep
    run_fault_sweep(network="grid2x2", demand_profile="symmetric", demand_level="medium",
                    fault_pattern="phase_symmetric", n_seeds=10, output_dir="results/example")
"""

from __future__ import annotations

import json
import time
import numpy as np
from pathlib import Path
from dataclasses import asdict
from typing import Callable

from pasa_itsc.sensors.fault_modes     import ALL_FAULT_MODES
from pasa_itsc.evaluation.metrics      import EpisodeResult, aggregate_results, format_results_table
from pasa_itsc.network.build_network   import DEMAND_LEVELS, demand_prob


# Default sweep settings

DEFAULT_FAULT_MODES  = ["NONE", "HZ", "SL", "GN", "ID", "DR"]   # MX removed from the study
# Main sweep. pasa_mean_mp is decision-identical to std_mp_q (checked by
# `verify`), and L1 alters no reading at the fault magnitudes studied, so the
# L1 / PASA+ variants are kept as input cleaners (sensors/obs_filters.py) and
# in SUPPLEMENT_CONTROLLERS, not swept.
MAIN_CONTROLLERS = [
    "fixed_time",      # Webster fixed time -- detector-free reference
    "std_mp",          # Varaiya max-pressure on raw readings
    "std_mp_q",        # queue-only MP (PASA's pressure form, no aggregation)
    "std_mp_recall",   # Std-MP + detector-failure recall (field-practice baseline)
    "pasa_max_mp",     # instantaneous nonlinear phase-pair aggregation
    "pasa_cg_mp",      # consistency-gated PASA
]
ASYM_CONTROLLERS = ["pasa_mean_vc_mp", "pasa_max_vc_mp"]   # v/c-scaled PASA, asymmetric demand only
ABLATION_CONTROLLERS = ["pasa_cg_mp", "pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp",
                        "pasa_cg_nohyst_mp", "pasa_cg_nopartner_mp"]
SUPPLEMENT_CONTROLLERS = ["pasa_mean_mp", "l1_mp", "pasa_mean_l1_mp", "pasa_max_l1_mp", "pasa_plus_mp"]


def controller_set(name: str, demand_profile: str = "symmetric") -> list[str]:
    """main (default; + v/c variants under asymmetric demand) | ablation | supplement | all."""
    main = MAIN_CONTROLLERS + (ASYM_CONTROLLERS if demand_profile == "asymmetric" else [])
    sets = {"main": main, "ablation": ABLATION_CONTROLLERS, "supplement": SUPPLEMENT_CONTROLLERS,
            "all": main + [c for c in ABLATION_CONTROLLERS + SUPPLEMENT_CONTROLLERS if c not in main]}
    if name not in sets:
        raise ValueError(f"controller set must be one of {list(sets)}")
    return list(sets[name])


DEFAULT_CONTROLLERS = MAIN_CONTROLLERS
DEFAULT_N_SEEDS      = 10
DEFAULT_FAULT_FRAC   = 0.25
DEFAULT_NETWORKS     = ["grid2x2", "cologne1"]
DEFAULT_DEMANDS      = ["low", "medium", "high"]


# run_fault_sweep

def run_fault_sweep(
    fault_modes:        list[str]             = DEFAULT_FAULT_MODES,
    controllers:        list[str] | None      = None,   # None -> controller_set("main", demand_profile)
    n_seeds:            int                   = DEFAULT_N_SEEDS,
    fault_fraction:     float                 = DEFAULT_FAULT_FRAC,
    output_dir:         str | Path            = "results",
    net_dir:            str | Path            = "data/net",
    use_gui:            bool                  = False,
    rl_model_path:      str | Path | None     = None,
    skip_existing:      bool                  = True,
    progress_cb:        Callable | None       = None,
    network:            str                   = "grid2x2",
    demand_level:       str                   = "low",
    # Fault site: one junction and approach; fault_intersection=-1 faults every junction.
    fault_intersection: int | str             = "I_SE",
    fault_approach:     str                   = "N",
    fault_n_lanes:      int                   = 0,     # 0 = whole approach
    fault_pattern:      str                   = "single_approach",
    balance_orientation: bool                 = True,
    # True: odd seeds fault the opposite-phase orientation (N<->W, S<->E) so
    # neither signal phase is systematically the faulted one.
    max_red:            float                 = 90.0,
    recall_interval:    float                 = 60.0,
    demand_profile:     str                   = "symmetric",
    warmup:             float                 = 900.0,
    fault_severity:     str                   = "medium",
    emissions:          bool                  = False,   # SUMO emissions device (CO2, fuel, NOx, PMx)
    # additional options (defaults reproduce the main sweep)
    min_green:          float                 = 0.0,
    max_green:          float                 = 40.0,
    fault_start:        float                 = 0.0,
    fault_end:          float | None          = None,
    plan_scale:         float                 = 1.0,
    plan_noise:         float                 = 0.0,
    cg_params:          dict | None           = None,
    diag_delay:         float                 = 0.0,
    # Cologne1 first-time setup: source file paths for the SUMO network/routes
    net_src:            str | Path | None     = None,
    rou_src:            str | Path | None     = None,
) -> dict:
    """Run the full fault-mode x controller x seed experiment matrix.

    Parameters
    ----------
    fault_modes     : list of fault mode strings to sweep
    controllers     : list of controller names to evaluate
    n_seeds         : number of seeds per (controller, fault_mode) cell
    fault_fraction  : fraction of lanes that are faulty
    output_dir      : directory for JSON result files
    net_dir         : SUMO network directory (net/rou/cfg files stored here)
    use_gui         : open SUMO-GUI (set False for batch runs)
    rl_model_path   : path to a trained DQN model (.zip); required for "rl"
    skip_existing   : skip cells that already have a result file
    progress_cb     : optional callback(ctrl, fault_mode, seed, result)
    network         : ``"grid2x2"`` (default) or ``"cologne1"``
    demand_level    : ``"low"`` / ``"medium"`` / ``"high"`` - departure
                      probability and v/c ratio (see DEMAND_LEVELS).
                      **Cologne1 note (W2)**: this parameter controls only the
                      grid2x2 route-file generation.  When ``network="cologne1"``
                      the fixed ``cologne1.rou.xml`` route file is used unchanged,
                      so the v/c ratio is determined by that file and is *not*
                      adjusted by ``demand_level``.  Cologne1 results are therefore
                      labelled *exploratory / external-validity* only: they confirm
                      that PASA+ generalises to a real-world network at its natural
                      demand, but do not constitute a controlled demand-matched
                      comparison.  For a fair cross-network comparison, provide a
                      re-scaled Cologne1 route file matched to the target v/c.
    net_src         : source path for ``cologne1.net.xml`` (cologne1 first run)
    rou_src         : source path for ``cologne1.rou.xml`` (cologne1 first run)

    Returns
    -------
    dict with keys "network", "demand_level", "flow_prob",
    "episodes" (list of EpisodeResult dicts) and
    "summary" (per (ctrl, fault) aggregate stats dicts).
    """
    if demand_level not in DEMAND_LEVELS:
        raise ValueError(
            f"Unknown demand_level {demand_level!r}. "
            f"Choose from: {list(DEMAND_LEVELS)}"
        )
    flow_prob = demand_prob(demand_level, demand_profile)
    if controllers is None:
        controllers = controller_set("main", demand_profile)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Lazily import env to avoid SUMO import errors in dry runs
    from pasa_itsc.env.sumo_env import SumoTrafficEnv

    # Build / verify network once before the sweep loop
    _ensure_network(network, net_dir, net_src, rou_src,
                    demand_level=demand_level, flow_prob=flow_prob)

    # Load RL agent if needed
    rl_agent = None
    if "rl" in controllers:
        if rl_model_path is None:
            raise ValueError(
                "rl_model_path must be provided when 'rl' is in controllers. "
                "Train first with: python -m pasa_itsc.main train-rl"
            )
        from pasa_itsc.controllers.rl_agent import DQNAgent
        # cologne1 obs: 4 PASA aggs + 1 phase = 5-dim (C1_OBS_DIM)
        # grid2x2 obs : 8 PASA aggs + 1 phase = 9-dim (OBS_DIM x 1 junction)
        _rl_obs_dim = 5 if network == "cologne1" else 9
        rl_agent = DQNAgent.load(rl_model_path, obs_dim=_rl_obs_dim)

    all_episodes: list[EpisodeResult] = []
    # fixed_time ignores detectors -> its NONE episodes are reused for every
    # other fault mode (identical traffic for the same seed, no sensor input).
    ft_reference: dict[int, EpisodeResult] = {}

    total_cells = len(controllers) * len(fault_modes) * n_seeds
    done_cells  = 0

    for ctrl in controllers:
        for fault_mode in fault_modes:
            cell_key  = f"{network}__{ctrl}__{fault_mode}"
            cell_file = output_dir / f"{cell_key}.json"

            # Seed-level resume: reuse saved seeds < n_seeds, run only the missing
            # ones (so a 5-seed run can later be topped up with --n-seeds 10).
            cell_episodes: list[EpisodeResult] = []
            done_seeds: set[int] = set()
            if skip_existing and cell_file.exists():
                saved = json.loads(cell_file.read_text())
                for ep in saved["episodes"]:
                    if ep["seed"] < n_seeds and ep["seed"] not in done_seeds:
                        cell_episodes.append(EpisodeResult(**ep))
                        all_episodes.append(cell_episodes[-1])
                        done_seeds.add(ep["seed"])
                done_cells += len(done_seeds)
                if len(done_seeds) >= n_seeds:
                    print(f"[experiment] Skipping {cell_key} ({len(done_seeds)} seeds exist)")
                    if ctrl == "fixed_time" and fault_mode == "NONE":
                        ft_reference = {e.seed: e for e in cell_episodes}
                    continue
                print(f"[experiment] {cell_key}: reusing seeds {sorted(done_seeds)}, "
                      f"running {n_seeds - len(done_seeds)} more")

            if ctrl == "fixed_time" and fault_mode != "NONE" and ft_reference:
                from dataclasses import replace as _dc_replace
                reused = 0
                for seed in range(n_seeds):
                    if seed in done_seeds or seed not in ft_reference:
                        continue
                    ep = _dc_replace(ft_reference[seed], fault_mode=fault_mode)
                    cell_episodes.append(ep)
                    all_episodes.append(ep)
                    done_seeds.add(seed)
                    done_cells += 1
                    reused += 1
                print(f"[experiment] {cell_key}: reused {reused} fixed_time x NONE "
                      f"episodes (fixed-time does not read detectors)")

            for seed in range(n_seeds):
                if seed in done_seeds:
                    continue
                _swap = {"N": "W", "W": "N", "S": "E", "E": "S"}
                approach_this = (_swap.get(fault_approach, fault_approach)
                                 if balance_orientation and seed % 2 == 1 else fault_approach)
                print(
                    f"[experiment] {network:8s} | {ctrl:16s} x {fault_mode:6s} "
                    f"seed={seed:2d}/{n_seeds}  ({done_cells}/{total_cells})"
                )

                env = SumoTrafficEnv(
                    network             = network,
                    use_gui             = use_gui,
                    fault_mode          = fault_mode,
                    fault_fraction      = fault_fraction,
                    controller          = ctrl,
                    rl_agent            = rl_agent,
                    seed                = seed,
                    net_dir             = net_dir,
                    demand_level        = demand_level,
                    fault_intersection  = fault_intersection,
                    fault_approach      = approach_this,
                    max_red             = max_red,
                    recall_interval     = recall_interval,
                    demand_profile      = demand_profile,
                    warmup              = warmup,
                    fault_severity      = fault_severity,
                    fault_n_lanes       = fault_n_lanes,
                    fault_pattern       = fault_pattern,
                    emissions           = emissions,
                    min_green           = min_green,
                    max_green           = max_green,
                    fault_start         = fault_start,
                    fault_end           = fault_end,
                    plan_scale          = plan_scale,
                    plan_noise          = plan_noise,
                    cg_params           = cg_params,
                    diag_delay          = diag_delay,
                )

                try:
                    ep_result = _run_episode(env, ctrl, fault_mode, seed)
                finally:
                    env.close()
                _tries = 1
                while getattr(env, "trip_check_failed", False) and _tries < 3:
                    print(f"[experiment] {ctrl}/{fault_mode}/seed {seed}: trip file inconsistent "
                          f"{getattr(env, '_trip_check', None)}; rerunning episode")
                    try:
                        ep_result = _run_episode(env, ctrl, fault_mode, seed)
                    finally:
                        env.close()
                    _tries += 1
                if getattr(env, "trip_check_failed", False):
                    raise RuntimeError(f"{ctrl}/{fault_mode}/seed {seed}: trip file inconsistent after 3 attempts")

                for _k, _v in (env.cg_detect_stats() if hasattr(env, "cg_detect_stats") else {}).items():
                    setattr(ep_result, _k, _v)
                for _k, _v in (getattr(env, "last_trip_stats", None) or {}).items():

                    setattr(ep_result, _k, _v)

                ep_result.fault_approach = getattr(env, "fault_approach", "")

                cell_episodes.append(ep_result)
                all_episodes.append(ep_result)
                done_cells += 1

                if progress_cb is not None:
                    progress_cb(ctrl, fault_mode, seed, ep_result)

            # Save per-cell JSON
            cell_file.parent.mkdir(parents=True, exist_ok=True)  # folder may be removed mid-run
            cell_file.write_text(
                json.dumps({"episodes": [asdict(e) for e in cell_episodes]}, indent=2)
            )
            print(f"[experiment] -> saved {cell_file}")
            if ctrl == "fixed_time" and fault_mode == "NONE":
                ft_reference = {e.seed: e for e in cell_episodes}

    # Aggregate
    summary = aggregate_results(all_episodes)
    summary_serialisable = {
        f"{k[0]}__{k[1]}": {
            "mean":    v.mean,
            "std":     v.std,
            "ci_low":  v.ci_low,
            "ci_high": v.ci_high,
            "n_seeds": v.n_seeds,
        }
        for k, v in summary.items()
    }

    master = {
        "network":        network,
        # cologne1: demand is the real 07:00-08:00 route file; no demand level applies
        "demand_level":   demand_level if network != "cologne1" else "route file 07:00-08:00",
        "flow_prob":      flow_prob if network != "cologne1" else None,
        "fault_pattern":  fault_pattern,
        "fault_site":     {"junction": fault_intersection, "approach": fault_approach,
                           "n_lanes": fault_n_lanes,
                           "orientation_balanced": balance_orientation},
        "control":        {"max_red_s": max_red, "recall_interval_s": recall_interval,
                           "tie_break": "keep current phase", "min_green_s": min_green,
                           "max_green_s": max_green},
        "fault_window_s": [fault_start, fault_end],
        "planning_error": {"scale": plan_scale, "arm_lognormal_sd": plan_noise},
        "cg_params":      dict(cg_params or {}),
        "diag_delay_s":   diag_delay,
        "demand_profile": demand_profile,
        "warmup_s":       warmup,
        "fault_severity": fault_severity,
        "emissions":      emissions,
        "analysis_plan":  {
            "primary_outcome": "network total delay (veh-h) = time_loss * n_trips / 3600",
            "confirmatory": ["pasa_cg_mp vs std_mp_q", "pasa_cg_mp vs std_mp",
                             "pasa_cg_mp vs std_mp_recall", "pasa_cg_mp vs pasa_max_mp",
                             "pasa_max_mp vs std_mp_q",
                             "pasa_mean_vc_mp vs std_mp_q (asymmetric)",
                             "pasa_max_vc_mp vs std_mp_q (asymmetric)"],
            "ablation": "pasa_cg_<variant>_mp vs pasa_cg_mp (exploratory, separate sweep)",
            "equivalence": "pasa_mean_mp == std_mp_q decision by decision (checked by verify, not swept)",
            "controllers": list(controllers),
            "secondary": ["travel_time", "fault-junction queue", "delay_jain",
                          "waiting_p95", "minor/major delay ratio (delay_by_side)",
                          "j0_approach_jain"],
            "correction": "Holm across confirmatory comparisons; all else exploratory",
        },
        "provenance":     _provenance(),
        "episodes": [asdict(e) for e in all_episodes],
        "summary":  summary_serialisable,
    }
    out_file = output_dir / "all_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)  # folder may be removed mid-run
    out_file.write_text(json.dumps(master, indent=2))
    print(f"\n[experiment] Complete. Results -> {out_file}")

    print("\n" + format_results_table(
        summary, fault_modes=fault_modes, controllers=controllers
    ))

    return master


# Single-episode runner

SIM_DURATION = 3600   # seconds (keep in sync with sumo_env.py)


def _provenance() -> dict:
    """Code hash, SUMO version and platform, stored with every result file."""
    import hashlib, os, platform, shutil, subprocess
    pkg = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for f in sorted(pkg.rglob("*.py")):
        if "__pycache__" in f.parts or "_before" in f.name or "_old" in f.name:
            continue
        h.update(f.relative_to(pkg).as_posix().encode())
        h.update(f.read_bytes())
    sumo = shutil.which("sumo") or os.path.join(os.environ.get("SUMO_HOME", ""), "bin", "sumo")
    try:
        ver = subprocess.run([sumo, "--version"], capture_output=True, text=True,
                             timeout=30).stdout.splitlines()[0]
    except Exception as e:
        ver = f"unknown ({type(e).__name__})"
    return {"code_sha256": h.hexdigest(), "sumo_version": ver,
            "python": platform.python_version(), "platform": platform.platform()}


def _run_episode(
    env,
    controller: str,
    fault_mode: str,
    seed: int,
) -> EpisodeResult:
    """Run one episode and return an EpisodeResult."""
    obs, info = env.reset(seed=seed)
    done         = False
    queue_sum    = 0.0
    jain_sum     = 0.0
    j0_s_sum     = 0.0    # time-sum of S-approach mean queue at junction 0
    j0_jain_sum  = 0.0    # time-sum of per-junction Jain at junction 0
    j0_q_sum     = 0.0    # time-sum of mean queue over the whole fault junction
    j0_aj_sum    = 0.0    # time-sum of approach-level Jain at the fault junction
    forced_sum   = 0      # junction-decisions overridden by max-red / recall
    cg_tot       = [0, 0, 0, 0]   # PASA-CG flag confusion counts after warm-up
    arrived_tot  = 0
    step_count   = 0

    while not done:
        action = env.get_controller_action(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        queue_sum   += info["mean_queue"]
        jain_sum    += info.get("jain_fairness", float("nan"))
        j0_s_sum    += info.get("j0_s_queue",    float("nan"))
        j0_jain_sum += info.get("j0_jain",        float("nan"))
        j0_q_sum    += info.get("j0_queue",       float("nan"))
        j0_aj_sum   += info.get("j0_approach_jain", float("nan"))
        forced_sum  += info.get("forced",         0)
        if info.get("cg") is not None and not info.get("warmup", False):
            cg_tot = [a + b for a, b in zip(cg_tot, info["cg"])]
        arrived_tot += info.get("arrived", 0)
        step_count  += 1
        done = terminated or truncated
        if info.get("warmup", False):      # undo: warm-up is not measured
            queue_sum   -= info["mean_queue"]
            jain_sum    -= info.get("jain_fairness", float("nan"))
            j0_s_sum    -= info.get("j0_s_queue",    float("nan"))
            j0_jain_sum -= info.get("j0_jain",        float("nan"))
            j0_q_sum    -= info.get("j0_queue",       float("nan"))
            j0_aj_sum   -= info.get("j0_approach_jain", float("nan"))
            forced_sum  -= info.get("forced",         0)
            arrived_tot -= info.get("arrived", 0)
            step_count  -= 1

    mean_queue    = queue_sum    / max(step_count, 1)
    jain_fairness = jain_sum     / max(step_count, 1)   # time-averaged network Jain
    j0_s_queue    = j0_s_sum    / max(step_count, 1)   # time-averaged j0 S-approach queue
    j0_jain       = j0_jain_sum / max(step_count, 1)   # time-averaged j0 per-junction Jain
    # throughput in veh/h: total arrived vehicles scaled to 1-hour episode
    throughput    = float(arrived_tot) * (3600.0 / SIM_DURATION)

    return EpisodeResult(
        controller    = controller,
        fault_mode    = fault_mode,
        seed          = seed,
        mean_queue    = mean_queue,
        throughput    = throughput,
        jain_fairness = jain_fairness,
        j0_s_queue    = j0_s_queue,
        j0_jain       = j0_jain,
        j0_queue      = j0_q_sum / max(step_count, 1),
        j0_approach_jain = j0_aj_sum / max(step_count, 1),
        cg_tpr        = cg_tot[0] / (cg_tot[0] + cg_tot[1]) if cg_tot[0] + cg_tot[1] else float("nan"),
        cg_fpr        = cg_tot[2] / (cg_tot[2] + cg_tot[3]) if cg_tot[2] + cg_tot[3] else float("nan"),
        forced_frac   = forced_sum / max(step_count * max(len(getattr(env, "_tl_ids", [])), 1), 1),
    )


def _ensure_network(
    network:      str,
    net_dir:      str | Path,
    net_src:      str | Path | None,
    rou_src:      str | Path | None,
    demand_level: str   = "low",
    flow_prob:    float = 0.10,
) -> None:
    """Build / verify network files before the sweep starts."""
    if network == "grid2x2":
        from pasa_itsc.network.build_network import build_2x2_grid
        build_2x2_grid(output_dir=net_dir,
                        demand_level=demand_level, flow_prob=flow_prob)
    elif network == "cologne1":
        from pasa_itsc.network.cologne_network import build_cologne1
        build_cologne1(output_dir=net_dir, net_src=net_src, rou_src=rou_src)
    else:
        raise ValueError(f"Unknown network {network!r}")


# Convenience: single run (for quick testing)

def find_worst_fault_location(
    fault_mode:   str      = "DR",
    n_seeds:      int      = 3,
    net_dir:      str|Path = "data/net",
    demand_level: str      = "medium",
    fault_n_lanes: int     = 2,
) -> tuple[int, str]:
    """Find the junction x approach pair that maximises mean-queue degradation.

    For the 2x2 grid network, runs a quick sweep over all 4 intersections x
    {N, S, E, W} approach directions, evaluating each with *n_seeds* episodes
    of std_mp (most fault-sensitive controller) under *fault_mode*.

    Returns
    -------
    (intersection_idx, approach_direction)
        The worst-case fault location to use for targeted injection.

    Usage
    -----
        from pasa_itsc.evaluation.experiment import find_worst_fault_location
        idx, approach = find_worst_fault_location()
        # Then pass fault_intersection=idx, fault_approach=approach to run_fault_sweep
    """
    from pasa_itsc.env.sumo_env import SumoTrafficEnv

    approaches   = ["N", "S", "E", "W"]
    n_junctions  = 4
    scores: dict[tuple[int, str], float] = {}

    print(f"[find_worst_fault_location] Sweeping {n_junctions} junctions x "
          f"{len(approaches)} approaches x {n_seeds} seeds  (fault_mode={fault_mode})")

    for inj_idx in range(n_junctions):
        for approach in approaches:
            queue_sum = 0.0
            for seed in range(n_seeds):
                env = SumoTrafficEnv(
                    network             = "grid2x2",
                    fault_mode          = fault_mode,
                    controller          = "std_mp",
                    fault_intersection  = inj_idx,
                    fault_approach      = approach,
                    fault_n_lanes       = fault_n_lanes,
                    net_dir             = net_dir,
                    demand_level        = demand_level,
                    seed                = seed,
                )
                try:
                    result     = _run_episode(env, "std_mp", fault_mode, seed)
                    queue_sum += result.mean_queue
                finally:
                    env.close()
            mean_q = queue_sum / n_seeds
            scores[(inj_idx, approach)] = mean_q
            print(f"  junction={inj_idx}  approach={approach}  "
                  f"mean_queue={mean_q:.3f}")

    # pick the combination with the highest queue (worst impact)
    worst = max(scores.items(), key=lambda kv: kv[1])
    best_idx, best_approach = worst[0]

    print(f"\n[find_worst_fault_location] -> junction {best_idx}, "
          f"approach {best_approach}  (mean_queue={worst[1]:.3f})\n"
          f"Full ranking:")
    for (idx, app), q in sorted(scores.items(), key=lambda kv: -kv[1]):
        marker = " <- WORST" if (idx, app) == (best_idx, best_approach) else ""
        print(f"  junction={idx}  approach={app}  mean_queue={q:.3f}{marker}")

    return best_idx, best_approach


def run_single(
    controller:  str       = "pasa_plus_mp",
    fault_mode:  str       = "NONE",
    seed:        int       = 0,
    use_gui:     bool      = False,
    net_dir:     str|Path  = "data/net",
    network:     str       = "grid2x2",
) -> EpisodeResult:
    """Run a single (controller, fault_mode, seed) episode and return result."""
    from pasa_itsc.env.sumo_env import SumoTrafficEnv

    env = SumoTrafficEnv(
        network    = network,
        use_gui    = use_gui,
        fault_mode = fault_mode,
        controller = controller,
        seed       = seed,
        net_dir    = net_dir,
    )
    try:
        result = _run_episode(env, controller, fault_mode, seed)
    finally:
        env.close()
    return result
