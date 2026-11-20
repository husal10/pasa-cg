"""
pasa_itsc.main
==============
Command-line entry point.

Sub-commands
------------
build-net   generate the 2x2 SUMO grid
run-sweep   run a fault x controller x seed sweep for one scenario and write all_results.json
verify      end-to-end checks in SUMO (run before a sweep)
demo        run one episode, with SUMO-GUI or headless
train-rl    train the DQN baseline on healthy detectors (not used in the papers)

Examples
--------
    python -m pasa_itsc.main build-net --output-dir data/net
    python -m pasa_itsc.main verify --net-dir data/net
    python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric \
        --demand-level medium --fault-pattern phase_symmetric --fault-severity high \
        --n-seeds 10 --net-dir data/net_sym --output-dir results/example
    python -m pasa_itsc.main demo --controller pasa_cg_mp --fault HZ --fault-pattern phase_symmetric
"""

from __future__ import annotations

import argparse
import sys


# Sub-command handlers

def _junction_arg(value: str):
    """--fault-intersection accepts an index (0, 2, -1) or a junction ID (I_SE)."""
    v = value.strip()
    return int(v) if v.lstrip("-").isdigit() else v


def _run_preview(*, controller, fault, fault_fraction, fault_intersection,
                 fault_approach, fault_n_lanes, fault_pattern, demand_level,
                 net_dir, seed, use_gui=True, max_steps=0,
                 demand_profile="symmetric", fault_severity="medium", flow_prob=None):
    """Run one episode (optionally in SUMO-GUI) and report whether the
    fault-site lanes actually carry traffic. Returns True if they do."""
    import numpy as np
    from pasa_itsc.env.sumo_env import SumoTrafficEnv

    print(f"[preview] controller={controller}  fault={fault}  pattern={fault_pattern}  "
          f"demand={demand_level}  junction={fault_intersection}  approach={fault_approach}  "
          f"gui={'on' if use_gui else 'off'}")
    env = SumoTrafficEnv(
        use_gui=use_gui, fault_mode=fault, fault_fraction=fault_fraction,
        controller=controller, net_dir=net_dir, seed=seed, step_log=True,
        demand_level=demand_level, fault_intersection=fault_intersection,
        fault_approach=fault_approach, fault_n_lanes=fault_n_lanes,
        fault_pattern=fault_pattern,
        demand_profile=demand_profile, fault_severity=fault_severity,
        flow_prob=flow_prob,
    )
    obs, info = env.reset()
    fi = env.fault_intersection          # resolved to an index by reset()
    jx = max(fi, 0)
    raw_sum, steps, q_sum, site_sum = None, 0, 0.0, 0.0
    if use_gui:
        print("[preview] running -- close the SUMO-GUI window (or Ctrl+C) to stop early")
    try:
        while True:
            action = env.get_controller_action(obs)
            obs, _, term, trunc, info = env.step(action)
            raw = env._get_raw_readings(jx)
            raw_sum = raw if raw_sum is None else raw_sum + raw
            q_sum += info["mean_queue"]
            site_sum += info["j0_s_queue"]
            steps += 1
            if term or trunc or (max_steps and steps >= max_steps):
                break
    except KeyboardInterrupt:
        print("\n[preview] interrupted")
    except Exception as e:  # closing the GUI window drops the TraCI connection
        print(f"[preview] stopped: {type(e).__name__}: {e}")
    finally:
        env.close()

    ts = env.last_trip_stats or {}
    if ts:
        print(f"[preview] trips (after warm-up): {ts['n_trips']}  unfinished {ts['n_unfinished']}  "
              f"travel time {ts['travel_time']:.1f}s  time loss {ts['time_loss']:.1f}s  "
              f"depart delay {ts['depart_delay']:.1f}s  p95 wait {ts.get('waiting_p95', float('nan')):.1f}s  "
              f"waiting to enter {ts.get('insertion_backlog', float('nan'))}")
        print(f"[preview] time loss by entry side: {ts.get('delay_by_side', {})}")
    if not steps:
        print("[preview] no steps completed")
        return False
    m = raw_sum / steps
    print(f"\n[preview] {steps} decision steps  |  network mean queue {q_sum/steps:.3f} veh/lane")
    print(f"[preview] mean true queue per approach at junction {jx} ({env._tl_ids[jx]}):")
    for d, ix in env._approach_idx.items():
        print(f"           {d}: " + "  ".join(f"{m[i]:5.2f}" for i in ix))
    targets = (env._fault_target_lanes[jx] or []) if fi >= 0 else []
    if not targets:
        print("[preview] no targeted fault lanes (fault_intersection = -1)")
        return True
    busy = [t for t in targets if m[t] >= 0.05]
    print(f"[preview] fault-site lanes {targets}: mean true queue {site_sum/steps:.3f} veh/lane")
    if len(busy) == len(targets):
        print("[preview] OK -- every faulted lane carries traffic")
    elif busy:
        print(f"[preview] PARTIAL -- only lanes {busy} carry traffic; down-faults "
              f"(HZ/SL/ID) on the others will have no effect")
    else:
        print("[preview] WARNING -- faulted lanes carry no traffic; HZ/SL/ID faults "
              "will be no-ops. Pick another --fault-approach/--fault-intersection.")
    return len(busy) > 0


def cmd_verify(args):
    from pasa_itsc.evaluation.verify import run_all
    ok = run_all(net_dir=args.net_dir, warmup=args.warmup, n_post=args.steps)
    sys.exit(0 if ok else 1)


def cmd_build_net(args):
    from pasa_itsc.network.build_network import build_2x2_grid
    net, rou = build_2x2_grid(output_dir=args.output_dir, overwrite=args.overwrite)
    print(f"\nOK Network ready\n  net : {net}\n  rou : {rou}")


def cmd_train_rl(args):
    from pasa_itsc.network.build_network import build_2x2_grid
    from pasa_itsc.env.sumo_env         import SumoTrafficEnv
    from pasa_itsc.controllers.rl_agent  import DQNAgent

    print(f"[train-rl] Building network in {args.net_dir}...")
    build_2x2_grid(output_dir=args.net_dir)

    print(f"[train-rl] Creating clean environment...")
    env = SumoTrafficEnv(
        use_gui      = False,
        fault_mode   = "NONE",    # train on healthy data
        controller   = "rl",
        net_dir      = args.net_dir,
        seed         = args.seed,
    )

    agent = DQNAgent(obs_dim=9, n_phases=2, seed=args.seed)
    print(f"[train-rl] Training for {args.steps:,} steps...")
    agent.learn(env, total_timesteps=args.steps, progress_bar=True)
    env.close()

    agent.save(args.model_path)
    print(f"\nOK RL model saved -> {args.model_path}.zip")


def cmd_run_sweep(args):
    from pasa_itsc.evaluation.experiment import run_fault_sweep

    if args.preview or args.preview_only:
        _run_preview(
            controller=args.preview_controller, fault=args.preview_fault,
            fault_fraction=args.fault_fraction,
            fault_intersection=args.fault_intersection,
            fault_approach=args.fault_approach, fault_n_lanes=args.fault_n_lanes,
            fault_pattern=args.fault_pattern, demand_level=args.demand_level,
            net_dir=args.net_dir, seed=0, use_gui=True,
            demand_profile=args.demand_profile, fault_severity=args.fault_severity,
        )
        if args.preview_only:
            return
        print("\n[run-sweep] preview finished -- starting sweep\n")

    # Pass None to let run_fault_sweep use its DEFAULT_CONTROLLERS /
    # DEFAULT_FAULT_MODES; only override when the user explicitly listed values.
    controllers = args.controllers or None
    if controllers is None and args.controller_set:
        from pasa_itsc.evaluation.experiment import controller_set
        controllers = controller_set(args.controller_set, args.demand_profile)
    fault_modes = args.fault_modes  or None

    kw = {}
    if controllers is not None:
        kw["controllers"] = controllers
    if fault_modes is not None:
        kw["fault_modes"] = fault_modes

    run_fault_sweep(
        **kw,
        n_seeds             = args.n_seeds,
        fault_fraction      = args.fault_fraction,
        output_dir          = args.output_dir,
        net_dir             = args.net_dir,
        use_gui             = args.use_gui,
        rl_model_path       = args.rl_model_path,
        skip_existing       = not args.no_skip,
        fault_intersection  = args.fault_intersection,
        fault_approach      = args.fault_approach,
        fault_n_lanes       = args.fault_n_lanes,
        fault_pattern       = args.fault_pattern,
        demand_level        = args.demand_level,
        balance_orientation = not args.no_balance_orientation,
        max_red             = args.max_red,
        recall_interval     = args.recall_interval,
        demand_profile      = args.demand_profile,
        network             = args.network,
        warmup              = args.warmup,
        fault_severity      = args.fault_severity,
        emissions           = args.emissions,
        min_green           = args.min_green,
        max_green           = args.max_green,
        fault_start         = args.fault_start,
        fault_end           = args.fault_end,
        plan_scale          = args.plan_scale,
        plan_noise          = args.plan_noise,
        cg_params           = _cg_params(args.cg_param),
        diag_delay          = args.diag_delay,
    )


def _cg_params(items):
    out = {}
    for it in items or []:
        k, v = it.split("=", 1)
        out[k.strip()] = float(v)
    return out


def cmd_demo(args):
    _run_preview(
        controller=args.controller, fault=args.fault,
        fault_fraction=args.fault_fraction,
        fault_intersection=args.fault_intersection,
        fault_approach=args.fault_approach, fault_n_lanes=args.fault_n_lanes,
        fault_pattern=args.fault_pattern, demand_level=args.demand_level,
        net_dir=args.net_dir, seed=args.seed,
        use_gui=not args.no_gui, max_steps=args.steps,
        demand_profile=args.demand_profile,
        flow_prob=args.flow_prob,
    )


# Argument parser

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pasa_itsc",
        description="Max-pressure under detector faults: SUMO experiments",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # build-net
    bn = sub.add_parser("build-net", help="Generate 2x2 SUMO grid network")
    bn.add_argument("--output-dir",  default="data/net")
    bn.add_argument("--overwrite",   action="store_true")

    # train-rl
    tr = sub.add_parser("train-rl", help="Train DQN RL baseline on clean data")
    tr.add_argument("--steps",       type=int,   default=200_000)
    tr.add_argument("--model-path",  default="models/dqn_clean")
    tr.add_argument("--net-dir",     default="data/net")
    tr.add_argument("--seed",        type=int,   default=42)
    tr.add_argument("--use-gui",     action="store_true",
                    help="Open SUMO-GUI during training (slow)")

    # run-sweep
    rs = sub.add_parser("run-sweep", help="Run a fault x controller x seed sweep for one scenario")
    rs.add_argument("--n-seeds",        type=int,   default=10)
    rs.add_argument("--fault-fraction", type=float, default=0.25)
    rs.add_argument("--output-dir",     default="results")
    rs.add_argument("--net-dir",        default="data/net")
    rs.add_argument("--use-gui",        action="store_true")
    rs.add_argument("--no-skip",        action="store_true",
                    help="Re-run even if result files exist")
    rs.add_argument("--rl-model-path",  default=None,
                    help="Path to trained DQN model (.zip) for RL baseline")
    rs.add_argument(
        "--controllers", nargs="+",
        choices=[
            "std_mp", "std_mp_recall", "std_mp_maxrecall", "webster_fallback_mp", "oracle_cg_mp",
            "pasa_cg_clip_mp", "std_mp_q", "l1_mp", "pasa_mp", "pasa_mean_mp", "pasa_max_mp",
            "pasa_mean_vc_mp",
            "pasa_max_vc_mp",
            "pasa_cg_mp", "pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp", "pasa_cg_nohyst_mp", "pasa_cg_nopartner_mp",
            "pasa_mean_l1_mp", "pasa_max_l1_mp", "pasa_plus_mp",
            "rl", "fixed_time",
        ],
        default=None,
        help="Controllers to evaluate (overrides --controller-set)",
    )
    rs.add_argument("--controller-set", default=None,
                    choices=["main", "ablation", "supplement", "all"],
                    help="main (default; adds v/c variants under asymmetric demand), "
                         "ablation (PASA-CG variants), supplement (PASA-mean, L1, PASA+), all")
    rs.add_argument(
        "--fault-modes", nargs="+",
        choices=["NONE", "HZ", "SL", "GN", "ID", "DR", "SH", "ND", "GA"],
        default=None,
        help="Fault modes to sweep (default: NONE HZ SL GN ID DR)",
    )
    rs.add_argument("--fault-intersection", type=_junction_arg, default="I_SE",
                    help="Fault junction: ID (I_NE, I_NW, I_SE, I_SW) or index; "
                         "-1 = all junctions (default I_SE)")
    rs.add_argument("--fault-approach", default="N",
                    choices=["N","S","E","W"],
                    help="Primary faulted approach (default N: at I_SE it is the "
                         "internal link from I_NE, so its queue can spill back)")
    rs.add_argument("--fault-n-lanes", type=int, default=0,
                    help="Lanes per faulted approach: 0 = all lanes (one sensor per "
                         "approach, default); k = first k lanes (per-lane loops)")
    rs.add_argument("--fault-pattern", default="single_approach",
                    choices=["single_approach", "phase_symmetric", "cross_phase", "distributed"],
                    help="Spatial fault pattern: single_approach (A, default), "
                         "phase_symmetric (B -- both arms of one phase), "
                         "cross_phase (C -- one arm per phase, e.g. N+W), "
                         "distributed (D -- 1 lane per arm, loop detectors)")
    rs.add_argument("--demand-level", default="medium",
                    choices=["low", "medium", "high"],
                    help="Traffic demand level: low (p=0.10), medium (p=0.20, default), "
                         "high (p=0.30)")
    rs.add_argument("--preview", action="store_true",
                    help="Show one episode in SUMO-GUI with the fault site outlined, "
                         "then run the sweep")
    rs.add_argument("--preview-only", action="store_true",
                    help="Show the SUMO-GUI preview episode and exit without sweeping")
    rs.add_argument("--preview-controller", default="pasa_cg_mp",
                    choices=["std_mp", "std_mp_recall", "std_mp_q", "l1_mp", "pasa_mp", "pasa_mean_mp", "pasa_max_mp",
                             "pasa_mean_vc_mp",
                             "pasa_max_vc_mp",
                             "pasa_cg_mp", "pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp", "pasa_cg_nohyst_mp", "pasa_cg_nopartner_mp",
                             "pasa_mean_l1_mp", "pasa_max_l1_mp", "pasa_plus_mp",
                             "fixed_time"],
                    help="Controller used in the preview episode (default pasa_plus_mp)")
    rs.add_argument("--preview-fault", default="HZ",
                    choices=["NONE", "HZ", "SL", "GN", "ID", "DR"],
                    help="Fault mode used in the preview episode (default HZ)")
    rs.add_argument("--max-red", type=float, default=90.0,
                    help="Maximum red time (s) for adaptive controllers, 0 = off (default 90)")
    rs.add_argument("--recall-interval", type=float, default=60.0,
                    help="std_mp_recall: serve phases with failed detectors at least "
                         "every N s (default 60)")
    rs.add_argument("--no-balance-orientation", action="store_true",
                    help="Fault the same orientation on every seed (default: odd seeds "
                         "use the opposite-phase orientation)")
    rs.add_argument("--demand-profile", default="symmetric", choices=["symmetric", "asymmetric"],
                    help="symmetric, or asymmetric 70/30 directional split (same total demand)")
    rs.add_argument("--warmup", type=float, default=900.0,
                    help="Healthy warm-up (s) before faults start; not measured (default 900)")
    rs.add_argument("--network", default="grid2x2", choices=["grid2x2", "cologne1"],
                    help="grid2x2 (synthetic 2x2 grid) or cologne1 (real junction, 07:00-08:00 demand)")
    rs.add_argument("--min-green", type=float, default=0.0,
                    help="minimum green incl. yellow (s); 0 = off (main sweep)")
    rs.add_argument("--max-green", type=float, default=40.0,
                    help="std_mp_maxrecall: green of the recalled phase and max-out of the other (s)")
    rs.add_argument("--fault-start", type=float, default=0.0, help="fault onset, s after warm-up")
    rs.add_argument("--fault-end", type=float, default=None, help="fault end (recovery), s after warm-up")
    rs.add_argument("--plan-scale", type=float, default=1.0, help="design volumes x this factor")
    rs.add_argument("--plan-noise", type=float, default=0.0,
                    help="per-arm lognormal sd of design-volume error (seeded)")
    rs.add_argument("--diag-delay", type=float, default=0.0,
                    help="oracle diagnosis (recall, fallback, oracle flags) starts this many s after fault onset")
    rs.add_argument("--cg-param", action="append", default=None,
                    help="PASA-CG parameter override, e.g. --cg-param h_lo=6 (repeatable)")
    rs.add_argument("--emissions", action="store_true",
                    help="Record CO2, fuel, NOx and PMx per trip (SUMO emissions device; traffic unchanged)")
    rs.add_argument("--fault-severity", default="medium", choices=["low", "medium", "high"],
                    help="Fault magnitude: GN sigma 0.5/1/2 veh, DR 1/2/4 veh per hour, "
                         "ID dropout 0.1/0.3/0.5 (default medium)")

    # verify
    vf = sub.add_parser("verify", help="End-to-end methodology checks in SUMO (run before a sweep)")
    vf.add_argument("--net-dir", default="data/net")
    vf.add_argument("--warmup",  type=float, default=300.0, help="warm-up per check episode (s)")
    vf.add_argument("--steps",   type=int,   default=60,    help="decisions after warm-up per episode")

    # demo
    dm = sub.add_parser("demo", help="Run one episode (SUMO-GUI or headless)")
    dm.add_argument("--controller",
                    choices=[
                        "std_mp","std_mp_recall","std_mp_q","l1_mp","pasa_mp","pasa_mean_mp","pasa_max_mp",
                        "pasa_mean_vc_mp",
                        "pasa_max_vc_mp",
                        "pasa_cg_mp", "pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp", "pasa_cg_nohyst_mp", "pasa_cg_nopartner_mp",
                        "pasa_mean_l1_mp","pasa_max_l1_mp","pasa_plus_mp",
                        "rl","fixed_time",
                    ],
                    default="pasa_cg_mp")
    dm.add_argument("--fault",
                    choices=["NONE", "HZ", "SL", "GN", "ID", "DR"],
                    default="NONE")
    dm.add_argument("--fault-fraction",    type=float, default=0.25)
    dm.add_argument("--fault-intersection", type=_junction_arg, default="I_SE",
                    help="Fault junction: ID (I_NE, I_NW, I_SE, I_SW) or index; "
                         "-1 = all junctions (default I_SE)")
    dm.add_argument("--fault-approach",    default="N",
                    choices=["N","S","E","W"],
                    help="Primary faulted approach (default N)")
    dm.add_argument("--fault-n-lanes",     type=int,   default=0,
                    help="Lanes per faulted approach: 0 = all lanes (default)")
    dm.add_argument("--fault-pattern",     default="single_approach",
                    choices=["single_approach", "phase_symmetric", "cross_phase", "distributed"])
    dm.add_argument("--demand-level",      default="medium",
                    choices=["low", "medium", "high"])
    dm.add_argument("--demand-profile",    default="symmetric",
                    choices=["symmetric", "asymmetric"])
    dm.add_argument("--flow-prob",         type=float, default=None,
                    help="Override departure probability per entry (veh/s) for demand calibration")
    dm.add_argument("--no-gui",            action="store_true",
                    help="Run headless (fast lane check, no SUMO-GUI window)")
    dm.add_argument("--steps",             type=int,   default=0,
                    help="Stop after N decision steps (0 = full episode, 360 steps)")
    dm.add_argument("--net-dir",           default="data/net")
    dm.add_argument("--seed",              type=int,   default=42)

    return p


# Entry point

def main():
    parser = _build_parser()
    args   = parser.parse_args()

    dispatch = {
        "build-net": cmd_build_net,
        "train-rl":  cmd_train_rl,
        "run-sweep": cmd_run_sweep,
        "demo":      cmd_demo,
        "verify":    cmd_verify,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
