"""
pasa_cg.env.sumo_env
======================
SUMO environment (TraCI) for one episode: builds or loads the network, injects
detector faults at the chosen junction, runs the chosen controller every
DECISION_STEP seconds and records per-episode metrics from the trip files.

Networks
--------
grid2x2   four two-phase junctions (I_NW, I_NE, I_SW, I_SE), three lanes per approach
cologne1  one junction from the RESCO benchmark, run with two phases

Signal timing
-------------
Decisions every 10 s; a phase change inserts a 3 s yellow. Guards: min_green
(default 0, i.e. one decision) and max_red (default 90 s, the red phase is then
forced to green).

Controllers (VALID_CONTROLLERS)
-------------------------------
fixed_time               fixed-time plan, no detectors
std_mp                   max-pressure with downstream queues (Varaiya 2013)
std_mp_q                 queue-only max-pressure: sum of clipped lane queues per phase
pasa_mean_mp, pasa_max_mp, pasa_mean_vc_mp, pasa_max_vc_mp
                         queue-only max-pressure on opposing-arm aggregates
pasa_cg_mp               queue-only max-pressure on PASA-CG readings
pasa_cg_<ablation>_mp    PASA-CG with one test or rule switched off
std_mp_recall, std_mp_maxrecall, webster_fallback_mp, oracle_cg_mp
                         field responses to a diagnosed detector, given an oracle
                         diagnosis (optionally delayed by diag_delay)
l1_mp, pasa_mean_l1_mp, pasa_max_l1_mp, pasa_plus_mp, rl, pasa_mp
                         earlier variants, kept for completeness; not used in the papers
"""

from __future__ import annotations

import os
import sys
import random
import tempfile
import numpy as np
from pathlib import Path
from typing import Any

import gymnasium as gym
from gymnasium import spaces

from pasa_cg.network.build_network import build_2x2_grid, DEMAND_LEVELS, _edge_flows, demand_prob
from pasa_cg.sensors.fault_modes   import FaultInjector, FaultMode
from pasa_cg.sensors.pasa          import PASAPreprocessor
from pasa_cg.sensors.pasa_plus     import PASAPlusPreprocessor
from pasa_cg.sensors.pasa_cg       import ConsistencyGatedPASA, CG_VARIANTS
from pasa_cg.sensors.obs_filters   import make_filter

# PASA-CG controllers: full method + ablations (pasa_cg_<variant>_mp)
CG_CONTROLLERS = {f"{v}_mp": kw for v, kw in CG_VARIANTS.items()}
from pasa_cg.controllers.max_pressure import MaxPressureController


# ---------------------------------------------------------------------------
# Constants  (keep in sync with build_network.py and rl_agent.py)
# ---------------------------------------------------------------------------

DECISION_STEP   = 10     # seconds between controller decisions
SIM_DURATION    = 3600   # seconds per episode

# Grid geometry
LANES_PER_ARM   = 3
N_ARMS          = 4
N_LANES         = LANES_PER_ARM * N_ARMS      # 12 per intersection
N_INTERSECTIONS = 4                            # 2x2 grid
N_PHASES        = 2                            # NS (0) / EW (1)
Q_MAX           = 20.0

# PASA aggregates per intersection = LANES_PER_ARM x N_PHASES = 6
N_AGG           = LANES_PER_ARM * N_PHASES     # 6

# RL observation = N_AGG + 1 (phase) = 7 per intersection
OBS_DIM         = N_AGG + 1                   # 7

# 4-phase TL: RL action -> SUMO phase via stride 2
PHASE_STRIDE    = 2

# Yellow-phase transition duration and sub-steps
YELLOW_DURATION = 3.0                             # seconds (must match TL program)
SUB_STEP        = 0.1                             # seconds per simulationStep()
YELLOW_STEPS    = int(YELLOW_DURATION / SUB_STEP) # 30 sub-steps
STEPS_PER_DEC   = int(DECISION_STEP  / SUB_STEP) # 100 sub-steps per decision

# No NEMA phase-time bounds: pure Varaiya (2013) argmax evaluated every step.
# Yellow insertion (YELLOW_STEPS) is applied by the environment whenever the
# selected phase differs from the previous one (see step()).

# ---------------------------------------------------------------------------
# Cologne1 network constants (single real-world junction, 8-phase TL)
# ---------------------------------------------------------------------------

# TL geometry
C1_LANES_PER_ARM   = 2    # 2 through+turn lanes per approach
C1_N_ARMS          = 4    # E, S, W, N
C1_N_LANES         = C1_LANES_PER_ARM * C1_N_ARMS   # 8 incoming lanes
C1_N_INTERSECTIONS = 1
C1_N_PHASES        = 2    # NS (action 0 -> phase 0) / EW (action 1 -> phase 4)
C1_PHASE_STRIDE    = 4    # action -> SUMO phase: action * 4
C1_N_AGG           = C1_LANES_PER_ARM * C1_N_PHASES  # 4 aggregates
C1_OBS_DIM         = C1_N_AGG + 1                    # 5 (4 agg + phase)

# Sim window (must match depart times in cologne1.rou.xml)
C1_SIM_BEGIN     = 25200
C1_SIM_END       = 28800
C1_SIM_DURATION  = C1_SIM_END - C1_SIM_BEGIN  # 3600 s

# Lane reordering: getControlledLanes() dedup order = [E0,E1, S0,S1, W0,W1, N0,N1]
# (indices 0-7 of the 8 unique incoming lanes, raw order: east, south, west, north)
# MaxPressureController needs [NS_lanes | EW_lanes]:
#   NS  = south (2,3) + north (6,7) -> reorder indices [2, 3, 6, 7]
#   EW  = east  (0,1) + west  (4,5) -> reorder indices [0, 1, 4, 5]
C1_NS_INDICES = [2, 3, 6, 7]   # south_0, south_1, north_0, north_1
C1_EW_INDICES = [0, 1, 4, 5]   # east_0,  east_1,  west_0,  west_1

# Vehicles per approach in the 07:00-08:00 route file (routed by shortest path;
# 4 of 2,015 trips do not cross the junction). Planning v/c for PASA-CG / v/c PASA.
C1_APPROACH_FLOW = {"N": 313, "S": 688, "E": 572, "W": 438}   # veh/h
C1_DEPART_OFFSET = 60     # s, uniform random depart offset per vehicle (seeded): seed variation
C1_WARMUP_MAX    = 900.0  # s, warm-up inside the one-hour demand window
# raw Cologne1 lane index (E0,E1,S0,S1,W0,W1,N0,N1) -> canonical (N0,N1,S0,S1,E0,E1,W0,W1)
C1_RAW_TO_CANON = {0: 4, 1: 5, 2: 2, 3: 3, 4: 6, 5: 7, 6: 0, 7: 1}
# PASA-CG under-reporting thresholds calibrated for this site on a healthy
# historical day (PASA-CG with healthy detectors, seed 999, outside the sweep
# seeds): least strict setting with healthy false-alarm rate <= 1 %.
# (grid defaults k_lo 0.5 / h_lo 4 / h_lo_min 3 gave 55 % false alarms here)
C1_CG_PARAMS = {"k_lo": 0.8, "h_lo": 6.0, "h_lo_min": 4.0}

# Approach direction -> raw lane indices (for cologne1 fault targeting)
C1_APPROACH_LANE_IDX: dict = {
    "E": [0, 1],
    "S": [2, 3],
    "W": [4, 5],
    "N": [6, 7],
}

# All valid controller names (including legacy alias)
# Fault injection spatial patterns
# Fault severity, scaled to the observed queue range (0.1-1 veh/lane mean,
# a few veh at peaks) instead of the 20-veh capacity used before.
#   noise_sigma  : GN std (veh)            drift_total : DR offset after 1 h (veh)
#   dropout_rate : ID P(drop) per decision
FAULT_SEVERITY = {
    "low":    {"noise_sigma": 0.5, "drift_total": 1.0, "dropout_rate": 0.1},
    "medium": {"noise_sigma": 1.0, "drift_total": 2.0, "dropout_rate": 0.3},
    "high":   {"noise_sigma": 2.0, "drift_total": 4.0, "dropout_rate": 0.5},
}

VALID_FAULT_PATTERNS = frozenset({
    "single_approach",   # A: all fault_n_lanes on one approach arm
    "phase_symmetric",   # B: fault_n_lanes on BOTH arms of the same phase (N+S or E+W)
    "distributed",       # D: 1 lane per approach, all 4 arms (uniform spread)
    "cross_phase",       # C: one whole approach per phase (N+W or S+E)
})

# Cross-phase partner for pattern C: the faulted arm plus one arm of the OTHER
# phase, so every phase pair keeps one clean arm (N+W, S+E).
_CROSS_PARTNER: dict[str, str] = {"N": "W", "W": "N", "S": "E", "E": "S"}

# Phase partner map for pattern B (phase_symmetric)
_PHASE_PARTNER: dict[str, str] = {"N": "S", "S": "N", "E": "W", "W": "E"}

VALID_CONTROLLERS = frozenset({
    "std_mp",
    "std_mp_recall",  # Std-MP + detector-failure fallback (ignore + phase recall)
    "std_mp_maxrecall",    # Std-MP + maximum recall on the diagnosed phase (field practice)
    "webster_fallback_mp", # MP-Q; a junction with a diagnosed detector reverts to its fixed-time plan
    "oracle_cg_mp",        # PASA-CG replacement with oracle flags (perfect detection, no tests)
    "pasa_cg_clip_mp",     # PASA-CG, full lanes exempt from the under-reporting test
    "std_mp_q",       # queue-only MP: PASA's pressure form, no aggregation (reference for PASA)
    "l1_mp",          # L1 plausibility filter per lane + queue-only MP (separates L1 from L2)
    "pasa_mean_vc_mp",  # PASA-mean on v/c-normalised queues (asymmetric demand)
    "pasa_max_vc_mp",   # PASA-max  on v/c-normalised queues (asymmetric demand)
    "pasa_cg_mp",       # consistency-gated PASA: detect faulty lanes from the signal rhythm, replace only those
    "pasa_cg_nolo_mp", "pasa_cg_nohi_mp", "pasa_cg_nofrozen_mp",   # PASA-CG ablations
    "pasa_cg_nohyst_mp", "pasa_cg_nopartner_mp",
    "pasa_mean_mp",
    "pasa_max_mp",
    "pasa_mean_l1_mp",
    "pasa_max_l1_mp",
    "pasa_plus_mp",
    "rl",
    "pasa_mp",        # legacy alias for pasa_mean_mp
    "fixed_time",     # SUMO default TLS program - no Python control
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sumo_home() -> Path:
    sh = os.environ.get("SUMO_HOME", "")
    if sh:
        return Path(sh)
    for p in ["/usr/share/sumo", "/usr/local/share/sumo", "/opt/sumo"]:
        if Path(p).exists():
            return Path(p)
    raise EnvironmentError(
        "SUMO_HOME is not set and SUMO was not found at common paths. "
        "Please set the SUMO_HOME environment variable."
    )


def _traci():
    """Lazy import of traci (only needed when env is actually used)."""
    try:
        import traci
        return traci
    except ImportError as e:
        raise ImportError(
            "traci not found. Install SUMO and ensure $SUMO_HOME/tools "
            "is on PYTHONPATH, or: pip install traci"
        ) from e


# ---------------------------------------------------------------------------
# SumoTrafficEnv
# ---------------------------------------------------------------------------

class SumoTrafficEnv(gym.Env):
    """SUMO-based 2x2 grid traffic environment for PASA+ experiments.

    Observation space
    -----------------
    Box(0, 1, shape=(28,)) -- 4 intersections x 7 features each:
        [agg_0/Q_max, ..., agg_5/Q_max, phase_idx]
    (Aggregates always computed with PASA mean, no L1, for all controllers --
    this is what the RL agent was trained on.)

    Action space
    ------------
    MultiDiscrete([2, 2, 2, 2]) -- one binary phase choice per intersection:
        0 -> NS green (SUMO phase 0), 1 -> EW green (SUMO phase 2)

    Parameters
    ----------
    network : str
        Network identifier: "grid2x2" (default).  Extend for "cologne1".
    use_gui : bool
        Open SUMO-GUI for live visualisation.
    fault_mode : FaultMode
        Sensor fault mode injected at each intersection.
    fault_fraction : float
        Fraction of lanes per intersection that are faulty (0 to 1).
        **Targeted-mode note (W1)**: when ``fault_intersection >= 0``, this
        parameter is *ignored* for the target junction.  The injector for that
        junction is always constructed with ``fault_fraction=1.0`` internally
        so that the FaultInjector corrupts all 12 lane slots; ``_apply_injection``
        then restores every slot *not* in ``fault_target_lanes``, so the net
        effect is 100 % corruption on exactly ``fault_n_lanes`` lanes of the
        target approach.  ``fault_fraction`` continues to govern the legacy
        all-junctions path (``fault_intersection=-1``) unchanged.
    controller : str
        One of the VALID_CONTROLLERS strings.
    rl_agent : DQNAgent | None
        Pre-trained RL agent (required when controller="rl").
    seed : int | None
        RNG seed for demand and fault stochasticity.
    net_dir : str | Path
        Directory for SUMO network/route files.  Auto-generated if absent.
    step_log : bool
        Print per-step stats to stdout.
    """

    metadata = {"render_modes": ["human"]}

    # Lane indices by approach direction (SUMO ordering for 2x2 grid).
    # N lanes are first (phase-0 arm 0), S next, then E, W.
    APPROACH_LANE_IDX: dict[str, list[int]] = {
        "N": [0, 1, 2],
        "S": [3, 4, 5],
        "E": [6, 7, 8],
        "W": [9, 10, 11],
    }

    def __init__(
        self,
        network:            str        = "grid2x2",
        use_gui:            bool       = False,
        fault_mode:         FaultMode  = "NONE",
        fault_fraction:     float      = 0.25,
        controller:         str        = "pasa_plus_mp",
        rl_agent                       = None,
        seed:               int | None = 42,
        net_dir:            str | Path = "data/net",
        step_log:           bool       = False,
        demand_level:       str        = "low",
        # targeted fault injection
        fault_intersection: int | str  = -1,
        # -1 = legacy (all intersections), >=0 = single-intersection targeted mode
        fault_approach:     str        = "N",
        # Which approach direction within the target intersection: "N","S","E","W"
        # Default "S": junction 0 / S approach was selected empirically by
        # find_worst_fault_location() as the site yielding the highest mean-queue
        # degradation under MX fault at medium demand.
        fault_n_lanes:      int        = 0,
        # 0 = every lane of the approach (one sensor per approach); k>0 = first k lanes
        # How many lanes on that approach to corrupt (<= LANES_PER_ARM = 3)
        fault_pattern:      str        = "single_approach",
        # Spatial pattern for which lanes to fault:
        #   "single_approach" (A) - all fault_n_lanes on one approach [default]
        #   "phase_symmetric" (B) - fault_n_lanes on BOTH arms of same phase
        #   "distributed"     (D) - 1 lane per approach, all 4 arms
        max_red:            float      = 90.0,
        # Maximum red time (s) for adaptive controllers; a phase red this long is
        # served for one decision. Standard in field controllers. 0 = off.
        recall_interval:    float      = 60.0,
        # std_mp_recall only: phases with diagnosed detector faults are served at
        # least every recall_interval seconds (detector-failure recall).
        demand_profile:     str        = "symmetric",   # or "asymmetric" (70/30 split)
        warmup:             float      = 900.0,
        # s of healthy warm-up before faults start; excluded from all metrics
        fault_severity:     str        = "medium",      # low / medium / high
        flow_prob:          float | None = None,
        # overrides the demand level's departure probability (demand calibration)
        emissions:          bool       = False,
        # record CO2 / fuel / NOx / PMx and stops per trip (SUMO emissions
        # device, deterministic assignment; does not change vehicle movement)
        obs_filter:         str        = "pasa_mean",
        # cleaner applied to the faulted readings in the observation (RL input);
        # see sensors/obs_filters.py. Default keeps the original PASA-mean obs.
        # additional options (defaults reproduce the main sweep exactly)
        min_green:          float      = 0.0,
        # s; a green (including its 3 s yellow) is held at least this long. 0 = off
        max_green:          float      = 40.0,
        # s; std_mp_maxrecall: green of the recalled phase, and max-out of the other phase
        fault_start:        float      = 0.0,
        fault_end:          float | None = None,
        # s after the warm-up: faults are active in [fault_start, fault_end)
        plan_scale:         float      = 1.0,
        plan_noise:         float      = 0.0,
        # planning-volume error: all design volumes x plan_scale, each arm x
        # exp(N(0, plan_noise)) (seeded). Affects only controllers that use them.
        cg_params:          dict | None = None,
        # PASA-CG parameter overrides (threshold sensitivity)
        diag_delay:         float      = 0.0,
        # s; oracle diagnosis (recall, fallback, oracle flags) starts this long after fault onset
    ):
        super().__init__()
        self.network        = network
        self.use_gui        = use_gui
        self.fault_mode     = fault_mode
        self.fault_fraction = fault_fraction
        self.controller_type= controller
        self.rl_agent       = rl_agent
        self.seed           = seed
        self.net_dir        = Path(net_dir)
        self.step_log       = step_log
        self.demand_level        = demand_level
        # targeted fault injection
        self.fault_intersection  = fault_intersection  # -1 = all, >=0 = single junction
        # Original spec (int index or junction ID such as "I_SE"); resolved to an
        # index in _init_components() once TraCI reports the TL ids.
        self._fault_site_spec    = fault_intersection
        self.fault_approach      = fault_approach.upper()  # "N","S","E","W"
        self.fault_n_lanes       = fault_n_lanes       # number of lanes to corrupt
        self.fault_pattern       = fault_pattern       # single_approach / phase_symmetric / cross_phase / distributed
        self.max_red             = float(max_red)
        self.recall_interval     = float(recall_interval)
        self.min_green           = float(min_green)
        self.max_green           = float(max_green)
        self.fault_start         = float(fault_start)
        self.fault_end           = None if fault_end is None else float(fault_end)
        self.plan_scale          = float(plan_scale)
        self.plan_noise          = float(plan_noise)
        self.cg_params           = dict(cg_params or {})
        self.diag_delay          = float(diag_delay)
        self._fallback_active: set = set()
        self.demand_profile      = demand_profile
        self.warmup              = min(float(warmup), C1_WARMUP_MAX) if network == "cologne1" else float(warmup)
        if fault_severity not in FAULT_SEVERITY:
            raise ValueError(f"fault_severity must be one of {list(FAULT_SEVERITY)}")
        self.fault_severity      = fault_severity
        self.obs_filter          = obs_filter
        self.emissions           = bool(emissions)
        make_filter(obs_filter)                       # fail early on an unknown name
        self._obs_filters: list = []
        self._obs_cache          = None
        self.flow_prob           = flow_prob
        self._vc_w: list = []
        self._inj_cache          = None
        self.last_trip_stats: dict | None = None
        self._tripinfo_path: Path | None = None
        self._forced_this_step   = 0
        if fault_pattern not in VALID_FAULT_PATTERNS:
            raise ValueError(
                f"Unknown fault_pattern {fault_pattern!r}. "
                f"Choose from: {sorted(VALID_FAULT_PATTERNS)}"
            )
        # Filled by _init_components(); one list[int] or [] per injector slot
        self._fault_target_lanes: list[list[int]] = []

        if controller not in VALID_CONTROLLERS:
            raise ValueError(
                f"Unknown controller {controller!r}. "
                f"Choose from: {sorted(VALID_CONTROLLERS)}"
            )

        # Network-specific geometry constants
        # Set instance-level constants so all helpers use the right values
        # regardless of which network is active.
        self._is_cologne1 = (network == "cologne1")

        if self._is_cologne1:
            # Single real-world junction, 8-phase TL, 8 incoming lanes
            self._lanes_per_arm   = C1_LANES_PER_ARM    # 2
            self._n_arms          = C1_N_ARMS            # 4
            self._net_lanes       = C1_N_LANES           # 8
            self._n_phases        = C1_N_PHASES          # 2
            self._n_intersections = C1_N_INTERSECTIONS   # 1
            self._phase_stride    = C1_PHASE_STRIDE      # 4
            self._n_agg           = C1_N_AGG             # 4
            self._obs_dim_net     = C1_OBS_DIM           # 5
            self._sim_duration    = C1_SIM_DURATION      # 3600 s
            self._approach_idx    = C1_APPROACH_LANE_IDX
        else:
            # 2x2 synthetic grid, 4 junctions, 12 lanes each
            self._lanes_per_arm   = LANES_PER_ARM        # 3
            self._n_arms          = N_ARMS               # 4
            self._net_lanes       = N_LANES              # 12
            self._n_phases        = N_PHASES             # 2
            self._n_intersections = N_INTERSECTIONS      # 4
            self._phase_stride    = PHASE_STRIDE         # 2
            self._n_agg           = N_AGG               # 6
            self._obs_dim_net     = make_filter(obs_filter, LANES_PER_ARM).out_dim + 1   # 7 for pasa_mean
            self._sim_duration    = SIM_DURATION         # 3600 s
            self._approach_idx    = {
                k: v for k, v in self.APPROACH_LANE_IDX.items()
            }

        # Expose geometry for external callers (e.g. main.py rl training)
        self.lanes_per_arm   = self._lanes_per_arm
        self.n_arms          = self._n_arms
        self.n_lanes         = self._net_lanes
        self.n_phases        = self._n_phases
        self.obs_dim         = self._obs_dim_net
        self.n_intersections = self._n_intersections

        # Gymnasium spaces (network-specific shapes)
        self.observation_space = spaces.Box(
            low   = 0.0,
            high  = 1.0,
            shape = (self._n_intersections * self._obs_dim_net,),
            dtype = np.float32,
        )
        self.action_space = spaces.MultiDiscrete(
            [self._n_phases] * self._n_intersections
        )

        # Internal components (created at reset)
        self._traci         = None
        self._traci_label: str | None                 = None
        self._tl_ids:       list[str]                 = []
        self._injectors:    list[FaultInjector]       = []

        # Preprocessors for each ablation variant
        # _pasa       : mean, no-L1  -- also used by _get_obs() for RL
        # _pasa_max   : max,  no-L1
        # _pasa_mean_l1: mean, L1
        # _pasa_max_l1 : max,  L1
        # _pasa_plus  : max, L1, EWMA  (PASAPlusPreprocessor)
        self._pasa:          list[PASAPreprocessor]        = []
        self._pasa_max:      list[PASAPreprocessor]        = []
        self._pasa_mean_l1:  list[PASAPreprocessor]        = []
        self._pasa_max_l1:   list[PASAPreprocessor]        = []
        self._pasa_plus:     list[PASAPlusPreprocessor]    = []
        self._mp_ctrls:      list[MaxPressureController]   = []

        self._step       = 0
        self._episode_queue: list[float] = []

        # Network setup (build / copy files)
        if self._is_cologne1:
            # cologne1 files must already exist in net_dir (use build_cologne1()
            # or pass net_src/rou_src to run_fault_sweep to copy them first).
            # We only set cfg/net/rou paths here; validation happens in
            # _ensure_network() inside experiment.py before the sweep.
            self._net_path = self.net_dir / "cologne1.net.xml"
            self._rou_path = self.net_dir / "cologne1.rou.xml"
            self._cfg_path = self.net_dir / "cologne1.sumocfg"
        else:
            # Build 2x2 grid with the correct demand level.
            # (must pass demand_level explicitly; default would silently use "low")
            self._net_path, self._rou_path = build_2x2_grid(
                output_dir=self.net_dir,
                demand_level=self.demand_level,
                demand_profile=self.demand_profile,
                flow_prob=self.flow_prob,
            )
            self._cfg_path = self.net_dir / "grid2x2.sumocfg"

    # -- Gymnasium API --------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        if seed is not None:
            self.seed = seed

        self._close_sumo()
        self._start_sumo()
        self._init_components()

        self._step = 0
        self._episode_queue = []

        # Lane-order diagnostic (enabled by step_log=True)
        # Prints the actual SUMO lane IDs for junction 0 in the order that
        # _unique_lanes() / _get_raw_readings() will use them.  Cross-check
        # against APPROACH_LANE_IDX to verify that [3,4,5] really are S lanes.
        if self.use_gui:
            self._highlight_fault_lanes()

        if self.step_log:
            tc  = _traci()
            fi  = max(self.fault_intersection, 0)
            tl  = self._tl_ids[fi]
            lanes = self._approach_lanes(tl)
            tgt = set((self._fault_target_lanes[fi] or []) if self._fault_target_lanes else [])
            print(f"\n[LANE DIAG] junction {fi} = {tl}   fault={self.fault_mode}  "
                  f"pattern={self.fault_pattern}  demand={self.demand_level}")
            print(f"[LANE DIAG] {'idx':>4}  {'label':>5}  {'heading':>7}  {'fault':>5}  lane_id")
            for idx, lid in enumerate(lanes):
                label   = next((d for d, ix in self._approach_idx.items() if idx in ix), "?")
                heading = self._lane_heading(tc.lane.getShape(lid))
                mark    = "X" if idx in tgt else ""
                print(f"[LANE DIAG] {idx:4d}  {label:>5}  {heading:>7}  {mark:>5}  {lid}")
            print("[LANE DIAG] check: label N must head south, S north, E west, W east\n")

        obs = self._get_obs()
        return obs.astype(np.float32), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        tc = _traci()
        if self._traci_label:
            tc.switch(self._traci_label)

        # Throughput accumulator
        # getArrivedNumber() reports arrivals since the LAST simulationStep() call,
        # so calling it once after the loop captures only the final 0.1 s sub-step
        # (~100x undercount).  Accumulate across every sub-step here instead.
        arrived_this_step = 0
        self._forced_this_step = 0

        def _sub_step() -> None:
            nonlocal arrived_this_step
            tc.simulationStep()
            try:
                _n_arr = int(tc.simulation.getArrivedNumber())
                arrived_this_step += _n_arr
                self._arrived_all += _n_arr
            except Exception:
                pass

        # fixed_time: let SUMO's built-in TLS program run - no Python override.
        # MP controllers: set green phase directly.
        #   grid2x2: insert a 3 s yellow transition (YELLOW_STEPS sub-steps)
        #            whenever the phase changes (external yellow insertion).
        #   cologne1: yellow phases are baked into the 8-phase TL program;
        #            set target green phase directly - SUMO cycles through
        #            yellow automatically.  NO external yellow insertion.
        if self.controller_type != "fixed_time":
            # Resolve requested phases for every junction
            new_phases = [
                int(action[i]) if hasattr(action, "__len__") else int(action)
                for i in range(len(self._tl_ids))
            ]
            if self.controller_type == "webster_fallback_mp":
                self._update_fallback(tc)
            new_phases = self._apply_max_red(new_phases)

            if self._is_cologne1:
                # cologne1: same yellow insertion as the grid, using the program's
                # yellow phase of the outgoing direction (raw phase = 4*phase + 1)
                switching = {i for i, (new, old) in enumerate(zip(new_phases, self._prev_phases)) if new != old}
                for i, tl_id in enumerate(self._tl_ids):
                    if i in self._fallback_active:
                        continue
                    if i in switching:
                        self._set_phase(tl_id, self._prev_phases[i] * self._phase_stride + 1)
                    else:
                        self._set_phase(tl_id, new_phases[i] * self._phase_stride)
                if switching:
                    for _ in range(YELLOW_STEPS):
                        _sub_step()
                    for i in switching:
                        self._set_phase(self._tl_ids[i], new_phases[i] * self._phase_stride)
                    for _ in range(STEPS_PER_DEC - YELLOW_STEPS):
                        _sub_step()
                else:
                    for _ in range(STEPS_PER_DEC):
                        _sub_step()
            else:
                # grid2x2: external yellow insertion on phase transitions
                # Identify junctions that are switching phase this step
                switching = {
                    i for i, (new, old) in enumerate(zip(new_phases, self._prev_phases))
                    if new != old
                }

                # Set initial SUMO phase for every junction:
                #   switching   -> yellow phase of the OUTGOING direction
                #   non-switch  -> green phase (continuing or same)
                for i, tl_id in enumerate(self._tl_ids):
                    if i in self._fallback_active:
                        continue
                    if i in switching:
                        yellow_sumo = self._prev_phases[i] * PHASE_STRIDE + 1
                        self._set_phase(tl_id, yellow_sumo)
                    else:
                        self._set_phase(tl_id, new_phases[i] * PHASE_STRIDE)

                if switching:
                    # Run yellow sub-steps, then switch to new green for remainder
                    for _ in range(YELLOW_STEPS):
                        _sub_step()
                    for i in switching:
                        self._set_phase(self._tl_ids[i],
                                                 new_phases[i] * PHASE_STRIDE)
                    for _ in range(STEPS_PER_DEC - YELLOW_STEPS):
                        _sub_step()
                else:
                    for _ in range(STEPS_PER_DEC):
                        _sub_step()

            # Remember phases for next step's yellow-transition check
            for i in self._fallback_active:      # fixed-time plan: follow SUMO's own phase
                new_phases[i] = self._get_phase(i)
            self._prev_phases = new_phases

        else:
            for _ in range(STEPS_PER_DEC):
                _sub_step()

        self._step += 1

        obs    = self._get_obs()
        reward, intersection_queues = self._get_reward_with_per_intersection()
        self._episode_queue.append(-reward)

        done = (self._step * DECISION_STEP) >= self._sim_duration + (0.0 if self._is_cologne1 else self.warmup)
        if done:
            try:   # vehicles still waiting to enter: invisible in tripinfo
                self._pending_end = len(tc.simulation.getPendingVehicles())
            except Exception:
                self._pending_end = float("nan")

        # Network-wide Jain's fairness index (secondary metric)
        # Uses junction-level mean queues as inputs.  Range [1/n, 1].
        # J = (sum q_i)^2 / (n * sum q_i^2);  1 = perfectly fair
        n_int = len(intersection_queues)
        sum_q  = sum(intersection_queues)
        sum_q2 = sum(q * q for q in intersection_queues)
        jain = (sum_q ** 2) / (n_int * sum_q2) if sum_q2 > 0 else 1.0

        # Per-junction metrics at junction 0 (primary equity metric, W3)
        # Obtain individual lane queues at junction 0 via ground-truth TraCI
        # (uses raw readings, not faulted observations, so the metric reflects
        # actual physical queues irrespective of sensor corruption).
        # "j0" = the fault-site junction (index fault_intersection; 0 if legacy).
        j0_raw: np.ndarray = self._get_raw_readings(max(self.fault_intersection, 0))
        n_j0_lanes = len(j0_raw)

        # S-approach mean queue: targeted fault lanes (approach-index aware).
        # Uses the actually-faulted lanes at the target junction when in
        # targeted mode (so patterns B/D are measured at their own fault site);
        # falls back to the S approach otherwise. Identical to before for A/S.
        S_IDX_local = self._approach_idx.get("S", [])[:self.fault_n_lanes]
        if (self.fault_intersection >= 0
                and self.fault_intersection < len(self._fault_target_lanes)
                and self._fault_target_lanes[self.fault_intersection]):
            S_IDX_local = list(self._fault_target_lanes[self.fault_intersection])
        j0_s_queue  = float(np.mean(j0_raw[S_IDX_local])) if S_IDX_local else 0.0

        # Per-junction Jain's index at junction 0 using all approach lanes.
        # Captures within-junction equity at the fault site.
        # Compare with network-wide jain to isolate the fault-site effect.
        q_j0      = j0_raw
        sum_q_j0  = float(np.sum(q_j0))
        sum_q_j02 = float(np.sum(q_j0 ** 2))
        j0_jain   = (sum_q_j0 ** 2) / (n_j0_lanes * sum_q_j02) if sum_q_j02 > 0 else 1.0

        info = {
            "step":               self._step,
            "mean_queue":         self._episode_queue[-1],
            "fault_mode":         self.fault_mode,
            "intersection_queues": intersection_queues,   # list[float], one per TL
            "jain_fairness":      jain,                   # network-wide equity (n=4)  in  [0,1]
            "arrived":            arrived_this_step,       # veh completed trip
            # junction-0 metrics (fault injection site)
            "j0_s_queue":         j0_s_queue,             # S-approach mean queue (lanes 3-4)
            "j0_jain":            j0_jain,                # per-junction Jain (n=12)  in  [0,1]
            "j0_queue":           float(np.mean(j0_raw)), # mean true queue, whole fault junction
            "forced":             self._forced_this_step, # junctions overridden by max-red/recall
            "warmup":             (self._step - 1) * DECISION_STEP < self.warmup,  # excluded from metrics
            "j0_approach_jain":   self._jain([float(np.mean(j0_raw[ix])) for ix in self._approach_idx.values() if len(ix)]),
            "cg":                 self._cg_counts(),     # [tp, fn, fp, tn] lane flags (pasa_cg_mp only)
        }

        if self.step_log:
            if self._step % 36 == 0:
                print(f"[step {self._step:4d}] queue={self._episode_queue[-1]:.2f}")
            # Every 36 steps (~6 min sim-time) dump the j0 S-approach queue so
            # we can verify the lane-index mapping during a live run.
            if self._step % 36 == 0:
                s_idx = S_IDX_local
                print(f"[J0 DIAG]   step={self._step:4d}  "
                      f"j0_raw[S_IDX={s_idx}]={j0_raw[s_idx]}  "
                      f"j0_s_queue={j0_s_queue:.3f}  "
                      f"j0_raw_all={j0_raw}")

        return obs.astype(np.float32), float(reward), done, False, info

    def render(self):
        pass  # SUMO-GUI is opened via use_gui flag at reset

    def close(self):
        self._close_sumo()

    # -- internal helpers -----------------------------------------------------

    def _start_sumo(self):
        tc = _traci()
        sumo_home = _sumo_home()
        binary = "sumo-gui" if self.use_gui else "sumo"

        binary_path = sumo_home / "bin" / binary
        if not binary_path.exists():
            binary_path = binary

        cmd = [
            str(binary_path),
            "-c", str(self._cfg_path),
            "--no-step-log",
            "--no-warnings",
            "--start",
        ]
        if self.seed is not None:
            cmd += ["--seed", str(self.seed)]
        if not self._is_cologne1:
            cmd += ["--end", str(int(self.warmup + self._sim_duration))]
        else:
            # cologne1.sumocfg sets no step length (SUMO default 1 s), but the env
            # advances STEPS_PER_DEC sub-steps of SUB_STEP s per decision: without
            # this, one 10 s decision ran 100 s of traffic and the hour ended
            # after 36 decisions.
            cmd += ["--step-length", str(SUB_STEP),
                    "--random-depart-offset", str(C1_DEPART_OFFSET)]

        # Episode isolation: OS-assigned free port, unique label and trip file.
        import uuid
        try:
            from sumolib.miscutils import getFreeSocketPort
            port = int(getFreeSocketPort())
        except Exception:
            port = random.randint(20000, 60000)
        label = f"pasa_{os.getpid()}_{uuid.uuid4().hex[:10]}"
        # Trip-level metrics (travel time, delay). write-unfinished keeps vehicles
        # still in the network at the end, so starvation is not hidden.
        self.last_trip_stats = None
        self.trip_check_failed = False
        self._trip_check = None
        self._arrived_all = 0
        self._tripinfo_path = Path(tempfile.gettempdir()) / f"pasa_trip_{label}.xml"
        try:
            self._tripinfo_path.unlink()
        except OSError:
            pass
        cmd += ["--tripinfo-output", str(self._tripinfo_path),
                "--tripinfo-output.write-unfinished", "true"]
        if getattr(self, "emissions", False):
            cmd += ["--device.emissions.probability", "1",
                    "--device.emissions.deterministic", "true"]
        tc.start(cmd, port=port, label=label)
        self._traci_label = label
        self._traci = tc
        # the connected SUMO must be the one we launched (it writes our trip file)
        try:
            got = tc.simulation.getOption("tripinfo-output")
        except Exception:
            got = None
        if got and os.path.basename(str(got)) != self._tripinfo_path.name:
            raise RuntimeError(f"TraCI connected to a foreign SUMO instance (its tripinfo: {got})")

    def _close_sumo(self):
        try:
            if self._traci is not None:
                label = getattr(self, "_traci_label", None)
                if label:
                    self._traci.switch(label)
                try:   # vehicles still waiting to enter when the run stops
                    self._pending_end = len(self._traci.simulation.getPendingVehicles())
                except Exception:
                    pass
                self._traci.close()
        except Exception:
            pass
        self._collect_tripinfo()
        self._traci = None
        self._traci_label = None

    def _init_components(self):
        tc = _traci()
        label = getattr(self, "_traci_label", None)
        if label:
            tc.switch(label)

        self._tl_ids = list(tc.trafficlight.getIDList())
        if not self._tl_ids:
            raise RuntimeError(
                "TraCI returned no traffic-light IDs -- SUMO may have crashed "
                "during startup."
            )
        n = len(self._tl_ids)

        # Canonical lane order per junction (N,S,E,W for grid2x2), derived from
        # lane geometry. SUMO lists lanes clockwise from north (N,E,S,W), which
        # does NOT match APPROACH_LANE_IDX / the [NS | EW] phase split.
        self._lane_order = {tl: self._compute_lane_order(tl) for tl in self._tl_ids}

        # Resolve a junction-ID fault site (e.g. "I_SE") to its TL index.
        spec = self._fault_site_spec
        if isinstance(spec, str):
            if spec in self._tl_ids:
                self.fault_intersection = self._tl_ids.index(spec)
            elif self._is_cologne1:
                # single-junction network: grid IDs such as "I_SE" map to its only TL
                self.fault_intersection = 0
            else:
                raise ValueError(f"fault_intersection {spec!r} is not a traffic light; "
                                 f"choose one of {self._tl_ids} or an index")
        else:
            self.fault_intersection = int(spec)

        rng_seed = self.seed if self.seed is not None else 42

        # Fault injectors
        # Two modes:
        #   fault_intersection == -1 : legacy - all n intersections get
        #       fault_fraction of their 12 lanes faulted (original behaviour)
        #   fault_intersection >= 0  : targeted - only ONE junction is faulted,
        #       on a single approach direction, for fault_n_lanes lanes only;
        #       all other junctions see clean (NONE) readings.
        #
        # _fault_target_lanes[i]:
        #   None  -> legacy (inject to whichever lanes FaultInjector picks internally)
        #   []    -> intersection not targeted; return raw readings unchanged
        #   [a,b] -> inject at whole-junction level but mask result to only those lane indices
        self._injectors          = []
        self._fault_target_lanes = []

        for i in range(n):
            if self.fault_intersection == -1:
                # Legacy: all intersections, random fault_fraction of lanes
                self._injectors.append(FaultInjector(
                    **self._fault_kwargs(),
                    n_lanes        = self._net_lanes,
                    fault_mode     = self.fault_mode,
                    fault_fraction = self.fault_fraction,
                    seed           = rng_seed + i,
                ))
                self._fault_target_lanes.append(None)   # None -> no masking

            elif i == self.fault_intersection:
                # Target intersection: set fraction=1.0 so the injector corrupts
                # ALL lane slots; _apply_injection() then masks to target_lanes only.
                # fault_pattern decides WHICH lanes are in target_lanes.
                # Approach-level patterns (A, B, C) fault whole approaches by
                # default (fault_n_lanes = 0): one camera / radar per approach.
                nl = (self.fault_n_lanes if self.fault_n_lanes and self.fault_n_lanes > 0
                      else self._lanes_per_arm)
                ap = self.fault_approach
                arms = {
                    "single_approach": [ap],                      # A
                    "phase_symmetric": [ap, _PHASE_PARTNER[ap]],  # B: both arms of one phase
                    "cross_phase":     [ap, _CROSS_PARTNER[ap]],  # C: one arm per phase
                }.get(self.fault_pattern)
                fault_groups = None
                if arms is not None:
                    groups = [list(self._approach_idx.get(a, []))[:nl] for a in arms]
                    target_lanes = [l for g in groups for l in g]
                    if nl >= self._lanes_per_arm:
                        fault_groups = groups   # whole approach = one shared sensor
                else:
                    # Pattern D (lane-level, loop detectors): 1 lane per approach,
                    # all 4 arms, lane index alternating inside each phase pair
                    # (N0,S1,E0,W1) -> every L2 aggregate keeps one clean input.
                    target_lanes = []
                    for pair in (("N", "S"), ("E", "W")):
                        for k, arm in enumerate(pair):
                            lanes = list(self._approach_idx.get(arm, []))
                            if lanes:
                                target_lanes.append(lanes[k % len(lanes)])
                self._injectors.append(FaultInjector(
                    **self._fault_kwargs(),
                    n_lanes        = self._net_lanes,
                    fault_mode     = self.fault_mode,
                    fault_fraction = 1.0,          # corrupt all internally; masked below
                    seed           = rng_seed + i,
                    groups         = fault_groups,
                ))
                self._fault_target_lanes.append(target_lanes)

            else:
                # Non-target intersections: clean readings (NONE injector)
                self._injectors.append(FaultInjector(
                    **self._fault_kwargs(),
                    n_lanes        = self._net_lanes,
                    fault_mode     = "NONE",
                    fault_fraction = 0.0,
                    seed           = rng_seed + i,
                ))
                self._fault_target_lanes.append([])    # [] -> passthrough

        # -- Preprocessors ----------------------------------------------------
        # pasa_mean_mp / obs / pasa_mp-alias: mean, no L1 (stateless)
        self._pasa = [
            PASAPreprocessor(
                lanes_per_arm = self._lanes_per_arm,
                aggregation   = "mean",
                use_l1        = False,
            )
            for _ in range(n)
        ]

        # pasa_max_mp: max, no L1 (stateless)
        self._pasa_max = [
            PASAPreprocessor(
                lanes_per_arm = self._lanes_per_arm,
                aggregation   = "max",
                use_l1        = False,
            )
            for _ in range(n)
        ]

        # pasa_mean_l1_mp: mean, L1 (stateful -- needs reset)
        self._pasa_mean_l1 = [
            PASAPreprocessor(
                lanes_per_arm = self._lanes_per_arm,
                aggregation   = "mean",
                use_l1        = True,
            )
            for _ in range(n)
        ]

        # pasa_max_l1_mp: max, L1 (stateful -- needs reset)
        self._pasa_max_l1 = [
            PASAPreprocessor(
                lanes_per_arm = self._lanes_per_arm,
                aggregation   = "max",
                use_l1        = True,
            )
            for _ in range(n)
        ]

        # pasa_plus_mp: max, L1, EWMA (stateful -- needs reset)
        self._pasa_plus = [
            PASAPlusPreprocessor(lanes_per_arm=self._lanes_per_arm)
            for _ in range(n)
        ]

        # Max-pressure controllers (shared across all MP variants).
        # Pure Varaiya (2013): no min/max green constraints.
        self._mp_ctrls = [
            MaxPressureController(
                lanes_per_arm = self._lanes_per_arm,
                n_phases      = self._n_phases,
                n_arms        = self._n_arms,
            )
            for _ in range(n)
        ]

        # Track previous green phase per junction for yellow-transition logic
        self._prev_phases: list[int] = [0] * n
        # decision step at which each phase was last green (max-red / recall)
        self._last_green: list[list[int]] = [[0] * self._n_phases for _ in range(n)]
        self._inj_cache = None
        # Planning v/c per approach (N,S,E,W) from design volumes -- the same
        # information Webster timing uses; never from the (faulty) detectors.
        self._vc_w = []
        if not self._is_cologne1:
            p = self.flow_prob if self.flow_prob is not None else demand_prob(self.demand_level, self.demand_profile)
            ef = _edge_flows(p, self.demand_profile)
            for tl in self._tl_ids:
                lanes, w = self._approach_lanes(tl), []
                for a in ("N", "S", "E", "W"):
                    ix = self._approach_idx.get(a, [])
                    edge = lanes[ix[0]].rsplit("_", 1)[0] if ix and ix[0] < len(lanes) else None
                    w.append(ef.get(edge, 0.0) * 3600.0 / self._lanes_per_arm / 1800.0)
                self._vc_w.append(np.maximum(np.array(w), 1e-3))
        else:
            self._vc_w = [np.maximum(np.array([C1_APPROACH_FLOW[a] / self._lanes_per_arm / 1800.0
                                               for a in ("N", "S", "E", "W")]), 1e-3)]
        # planning-volume error (only controllers that use design volumes)
        if self.plan_scale != 1.0 or self.plan_noise > 0:
            _r = np.random.default_rng(10_000 + (self.seed if self.seed is not None else 42))
            self._vc_w = [np.maximum(w * self.plan_scale * np.exp(_r.normal(0.0, self.plan_noise, size=len(w))), 1e-3)
                          for w in self._vc_w]
        # pasa_cg_mp: consistency-gated PASA, one detector state per junction
        _cg_kw = dict(C1_CG_PARAMS if self._is_cologne1 else {})
        _cg_kw.update(CG_CONTROLLERS.get(self.controller_type, {}))
        _cg_kw.update(self.cg_params)
        self._cg = [
            ConsistencyGatedPASA(lanes_per_arm=self._lanes_per_arm, dt=DECISION_STEP,
                                 max_red=self.max_red if self.max_red > 0 else 90.0, **_cg_kw)
            for _ in range(n)
        ]
        # bookkeeping for the additional options
        self._green_start: list[int] = [0] * n
        self._phase_load: list[list[float]] = [[0.0] * self._n_phases for _ in range(n)]
        self._fallback_active = set()
        self._tl_prog = [_traci().trafficlight.getProgram(t) for t in self._tl_ids]
        self._cg_first_flag: dict = {}
        # observation cleaners (one per junction, reset each episode)
        self._obs_filters = [make_filter(self.obs_filter, self._lanes_per_arm) for _ in range(n)]
        for f in self._obs_filters:
            f.reset()
        self._obs_cache = None
        # l1_mp: L1 filter per lane, no aggregation (stateful)
        self._l1_only = [
            PASAPreprocessor(lanes_per_arm=self._lanes_per_arm, aggregation="mean", use_l1=True)
            for _ in range(n)
        ]
        for pp in self._l1_only:
            pp.reset()

        # Reset all stateful components
        for pp in self._pasa_mean_l1:
            pp.reset()
        for pp in self._pasa_max_l1:
            pp.reset()
        for pp in self._pasa_plus:
            pp.reset()
        for mp in self._mp_ctrls:
            mp.reset()

    # -- detector diagnosis / max-red / recall ----------------------------------

    def _set_phase(self, tl_id: str, phase: int) -> None:
        """Set a phase for an adaptive controller. On grid2x2 the programme's own
        duration is overridden so SUMO never advances the phase by itself
        (Webster greens can be shorter than the 10 s decision interval)."""
        tl_api = _traci().trafficlight
        tl_api.setPhase(tl_id, phase)
        tl_api.setPhaseDuration(tl_id, 1e5)

    def _cg_counts(self):
        """Detection confusion counts of PASA-CG flags at this decision (all junctions).
        Positives are the injected fault lanes once faults are active."""
        if self.controller_type not in CG_CONTROLLERS or not getattr(self, "_cg", None):
            return None
        active = self._fault_active(self._step - 1)
        tp = fn = fp = tn = 0
        for i, cg in enumerate(self._cg):
            t = self._fault_target_lanes[i] if i < len(self._fault_target_lanes) else None
            tgt = set(t) if (active and t) else set()
            if self._is_cologne1:
                tgt = {C1_RAW_TO_CANON[l] for l in tgt}
            for l, f in enumerate(cg.flag):
                if l in tgt:
                    tp += int(f); fn += int(not f)
                    if f:
                        raw_l = next((r for r, c in C1_RAW_TO_CANON.items() if c == l), l) if self._is_cologne1 else l
                        self._cg_first_flag.setdefault((i, raw_l), self._step - 1)
                else:
                    fp += int(f); tn += int(not f)
        return [tp, fn, fp, tn]

    @staticmethod
    def _jain(x) -> float:
        x = np.asarray(x, dtype=float)
        s2 = float(np.sum(x ** 2))
        return float(np.sum(x)) ** 2 / (len(x) * s2) if s2 > 0 else 1.0

    def _update_fallback(self, tc) -> None:
        """webster_fallback_mp: a junction with a diagnosed (oracle) detector fault
        hands control back to its fixed-time programme (Webster plan on the grid,
        the real 8-phase plan on Cologne1), from its current green; it resumes
        adaptive control when the fault ends."""
        for i, tl in enumerate(self._tl_ids):
            diag = bool(self._diagnosed_lanes(i))
            if diag and i not in self._fallback_active:
                tc.trafficlight.setPhase(tl, self._prev_phases[i] * self._phase_stride)
                self._fallback_active.add(i)
            elif not diag and i in self._fallback_active:
                self._fallback_active.discard(i)
                self._prev_phases[i] = self._get_phase(i)
                self._green_start[i] = self._step
                for p in range(self._n_phases):
                    self._last_green[i][p] = self._step

    def _fault_active(self, step: int | None = None) -> bool:
        """Faults are injected in [warmup + fault_start, warmup + fault_end)."""
        t = (self._step if step is None else step) * DECISION_STEP - self.warmup
        return self.fault_mode != "NONE" and t >= self.fault_start and (self.fault_end is None or t < self.fault_end)

    def cg_detect_stats(self) -> dict:
        """Time to first flag per faulty lane after fault onset (PASA-CG variants)."""
        tgt = [(i, l) for i, t in enumerate(self._fault_target_lanes or []) if t for l in t]
        if self.fault_mode == "NONE" or not tgt or self.controller_type not in CG_CONTROLLERS:
            return {}
        onset = (self.warmup + self.fault_start) / DECISION_STEP
        ttd = [(self._cg_first_flag[k] - onset) * DECISION_STEP for k in tgt if k in self._cg_first_flag]
        return {"cg_ttd_s": float(np.mean(ttd)) if ttd else float("nan"),
                "cg_detected_frac": len(ttd) / len(tgt)}

    def _diagnosed_lanes(self, i: int) -> list[int]:
        """Lane indices (raw order) whose detectors are faulty at junction i (oracle)."""
        if (self.fault_mode == "NONE" or i >= len(self._fault_target_lanes)
                or not self._fault_active()):
            return []
        if self.diag_delay > 0 and (self._step * DECISION_STEP - self.warmup - self.fault_start) < self.diag_delay:
            return []      # diagnosis not yet available
        t = self._fault_target_lanes[i]
        if t is None:      # legacy all-junction mode: injector picked the lanes
            return [int(k) for k in np.flatnonzero(self._injectors[i].faulty_indices)]
        return [int(k) for k in t]

    def _phase_of_lane(self, idx: int) -> int:
        if self._is_cologne1:
            return 0 if idx in C1_NS_INDICES else 1
        return 0 if idx < self._net_lanes // 2 else 1     # canonical [NS | EW]

    def _apply_max_red(self, phases: list[int]) -> list[int]:
        """Enforce max red (all adaptive controllers) and detector-failure recall
        (std_mp_recall). A phase whose red time would exceed its limit is served
        for this decision. Keeps the MP controllers' current phase in sync."""
        out = list(phases)
        inf = float("inf")
        for i in range(len(out)):
            cur = self._prev_phases[i]
            if i in self._fallback_active:          # junction runs its own fixed-time plan
                out[i] = cur
                continue
            el = (self._step - self._green_start[i]) * DECISION_STEP   # green so far (incl. yellow)
            if self.min_green > 0 and out[i] != cur and el < self.min_green:
                out[i] = cur                                            # minimum green
                self._last_green[i][out[i]] = self._step
                if i < len(self._mp_ctrls):
                    self._mp_ctrls[i]._current_phase = out[i]
                continue
            if self.controller_type == "std_mp_maxrecall":
                # maximum recall on the phase(s) of diagnosed detectors: the recalled
                # phase is served every cycle for max_green; the other phase runs
                # while it has demand, up to max_green (constant conflicting call).
                rec = {self._phase_of_lane(ix) for ix in self._diagnosed_lanes(i)}
                if rec:
                    others = [p for p in range(self._n_phases) if p not in rec]
                    if cur in rec:
                        if el < self.max_green:
                            out[i] = cur
                        else:
                            out[i] = others[0] if others else (cur + 1) % self._n_phases
                    elif el >= self.max_green or self._phase_load[i][cur] <= 0:
                        out[i] = min(rec)
            limits = [self.max_red if self.max_red > 0 else inf] * self._n_phases
            if self.controller_type == "std_mp_recall" and self.recall_interval > 0:
                for idx in self._diagnosed_lanes(i):
                    p = self._phase_of_lane(idx)
                    limits[p] = min(limits[p], self.recall_interval)
            overdue = [((self._step - self._last_green[i][p]) * DECISION_STEP - limits[p], p)
                       for p in range(self._n_phases) if p != out[i]]
            overdue = [(o, p) for o, p in overdue if o >= 0]
            if overdue:
                out[i] = max(overdue)[1]
                self._forced_this_step += 1
            if out[i] != cur:
                self._green_start[i] = self._step
            self._last_green[i][out[i]] = self._step
            if i < len(self._mp_ctrls):
                self._mp_ctrls[i]._current_phase = out[i]
        return out

    def _collect_tripinfo(self) -> None:
        """Parse the episode's tripinfo file into last_trip_stats, then delete it."""
        p, self._tripinfo_path = getattr(self, "_tripinfo_path", None), None
        if not p or not Path(p).exists():
            return
        try:
            import xml.etree.ElementTree as ET
            _all = list(ET.parse(p).getroot().iter("tripinfo"))
            n_arr_file = sum(1 for t in _all if float(t.get("arrival", "-1")) >= 0)
            self._trip_check = (n_arr_file, getattr(self, "_arrived_all", None))
            if self._trip_check[1] is not None and n_arr_file != self._trip_check[1]:
                self.trip_check_failed = True
                print(f"[tripinfo] arrivals in trip file {n_arr_file} != live count {self._trip_check[1]}")
            trips = [t for t in _all
                     if float(t.get("depart", "0")) >= self.warmup + (C1_SIM_BEGIN if self._is_cologne1 else 0)]   # measured period only
            if trips:
                m = lambda k: float(np.mean([float(t.get(k, "nan")) for t in trips]))
                self.last_trip_stats = dict(
                    travel_time  = m("duration"),
                    waiting_time = m("waitingTime"),
                    time_loss    = m("timeLoss"),
                    depart_delay = m("departDelay"),
                    n_trips      = len(trips),
                    n_unfinished = sum(1 for t in trips if float(t.get("arrival", "-1")) < 0),
                )
                import re as _re
                tl_ = np.array([float(t.get("timeLoss", "nan")) for t in trips])
                wt_ = np.array([float(t.get("waitingTime", "nan")) for t in trips])
                self.last_trip_stats["delay_jain"] = self._jain(np.nan_to_num(tl_))
                self.last_trip_stats["insertion_backlog"] = getattr(self, "_pending_end", float("nan"))
                self.last_trip_stats["waiting_p95"] = float(np.nanpercentile(wt_, 95))
                by_side: dict = {}
                for t, d in zip(trips, tl_):
                    m_ = _re.search(r"_I_\w\w_([NSEW])_", t.get("id", ""))
                    if m_:
                        by_side.setdefault(m_.group(1), []).append(d)
                self.last_trip_stats["delay_by_side"] = {k: float(np.nanmean(v)) for k, v in sorted(by_side.items())}
                self.last_trip_stats["stops_per_trip"] = m("waitingCount")
                if getattr(self, "emissions", False):
                    tot = {"CO2_abs": 0.0, "fuel_abs": 0.0, "NOx_abs": 0.0, "PMx_abs": 0.0}
                    n_em = 0
                    for t in trips:
                        em = t.find("emissions")
                        if em is not None:
                            n_em += 1
                            for k in tot:
                                tot[k] += float(em.get(k, "0"))
                    # SUMO reports mg per trip (fuel in mg as well)
                    self.last_trip_stats.update(
                        co2_g          = tot["CO2_abs"] / 1e3 / max(n_em, 1),   # mean g per trip
                        fuel_g         = tot["fuel_abs"] / 1e3 / max(n_em, 1),
                        nox_g          = tot["NOx_abs"] / 1e3 / max(n_em, 1),
                        pmx_mg         = tot["PMx_abs"] / max(n_em, 1),
                        co2_total_kg   = tot["CO2_abs"] / 1e6,                  # network total, measured trips
                        fuel_total_kg  = tot["fuel_abs"] / 1e6,
                        n_emission_trips = n_em,
                    )
        except Exception as e:
            print(f"[tripinfo] could not parse {p}: {e}")
        finally:
            try:
                os.remove(p)
            except OSError:
                pass

    # -- targeted fault injection helper ----------------------------------------

    def _vc_aggregate(self, i: int, q: np.ndarray, how: str) -> np.ndarray:
        """PASA aggregation on v/c-normalised lane queues (grid2x2, canonical order).

        a_i = agg(q_a1,i / w_a1, q_a2,i / w_a2) * (w_a1 + w_a2) / 2
        With equal v/c this is plain PASA; with queues proportional to demand
        the mean variant equals the plain mean exactly.
        """
        q = np.clip(np.asarray(q, dtype=float), 0.0, self._pasa[i].q_max)
        w = self._vc_w[i] if i < len(self._vc_w) else np.ones(4)
        r = {a: q[self._approach_idx[a]] / w[k] for k, a in enumerate(("N", "S", "E", "W"))}
        out = []
        for k1, a1, k2, a2 in ((0, "N", 1, "S"), (2, "E", 3, "W")):
            pair = np.vstack([r[a1], r[a2]])
            agg = pair.mean(axis=0) if how == "mean" else pair.max(axis=0)
            out.append(agg * (w[k1] + w[k2]) / 2.0)
        return np.concatenate(out)

    def _fault_kwargs(self) -> dict:
        """Severity-scaled fault magnitudes + balanced MX index for this episode."""
        sev = FAULT_SEVERITY[self.fault_severity]
        n_fault_steps = max(int(self._sim_duration / DECISION_STEP), 1)
        return dict(
            noise_sigma  = sev["noise_sigma"],
            drift_rate   = sev["drift_total"] / n_fault_steps,
            dropout_rate = sev["dropout_rate"],
            mx_index     = None if self.seed is None else int(self.seed) // 2,
        )

    def _apply_injection(self, i: int, raw: np.ndarray) -> np.ndarray:
        """Faulted readings for junction i, computed ONCE per decision step.

        _get_obs() and get_controller_action() both request readings; without
        the cache every stochastic fault was drawn twice per step and drift
        accumulated at twice its rate. No faults during the warm-up.
        """
        if not self._fault_active():
            return raw.copy()
        cache = self._inj_cache
        if cache is not None and cache[0] == self._step and i in cache[1]:
            return cache[1][i].copy()
        out = self._apply_injection_uncached(i, raw)
        if cache is None or cache[0] != self._step:
            self._inj_cache = cache = (self._step, {})
        cache[1][i] = out.copy()
        return out

    def _apply_injection_uncached(self, i: int, raw: np.ndarray) -> np.ndarray:
        """Return (possibly faulted) lane readings for intersection index *i*.

        Behaviour controlled by ``_fault_target_lanes[i]``:

        * ``None``   - legacy mode: the FaultInjector chooses which lanes to
                       corrupt according to ``fault_fraction``; no extra masking.
        * ``[]``     - this intersection is not targeted; return *raw* unchanged.
        * ``[a, b]`` - targeted mode: the FaultInjector corrupts *all* lanes
                       (fraction=1.0) but we restore the non-target slots back
                       to *raw*, so only the specified lane indices are faulted.
        """
        targets = self._fault_target_lanes[i]

        if targets is None:
            # Legacy: let the injector decide which lanes are faulty
            return self._injectors[i].inject(raw, step=self._step)

        if not targets:
            # Non-target intersection -> clean readings
            return raw.copy()

        # Targeted: corrupt all 12 lanes internally, then restore non-targets
        faulted_all = self._injectors[i].inject(raw, step=self._step)
        result = raw.copy()
        for idx in targets:
            result[idx] = faulted_all[idx]
        return result

    @staticmethod
    def _lane_heading(shape) -> str:
        """Travel direction of a lane from its shape: 'north','south','east','west'."""
        (x0, y0), (x1, y1) = shape[0], shape[-1]
        dx, dy = x1 - x0, y1 - y0
        if abs(dy) >= abs(dx):
            return "south" if dy < 0 else "north"
        return "west" if dx < 0 else "east"

    _HEADING_TO_APPROACH = {"south": "N", "north": "S", "west": "E", "east": "W"}

    def _compute_lane_order(self, tl_id: str) -> list[str]:
        """Unique incoming lanes of *tl_id* in canonical order.

        grid2x2: [N0,N1,N2, S0,S1,S2, E0,E1,E2, W0,W1,W2] so that
        APPROACH_LANE_IDX and the [NS | EW] phase split used by MP / PASA are
        correct. The approach is inferred from each lane's direction of travel
        (a lane heading south belongs to the N approach, etc.).
        cologne1: raw SUMO order (its own C1 reorder is applied downstream).
        """
        tc  = _traci()
        raw = self._unique_lanes(tc.trafficlight.getControlledLanes(tl_id),
                                 self._net_lanes)
        if self._is_cologne1:
            return raw
        groups: dict[str, list[str]] = {"N": [], "S": [], "E": [], "W": []}
        for lane in raw:
            d = self._HEADING_TO_APPROACH[self._lane_heading(tc.lane.getShape(lane))]
            groups[d].append(lane)
        if not all(len(v) == self._lanes_per_arm for v in groups.values()):
            print(f"[lane-order] WARNING {tl_id}: unexpected approach sizes "
                  f"{ {k: len(v) for k, v in groups.items()} } -- using raw SUMO order")
            return raw
        lane_num = lambda l: int(l.rsplit("_", 1)[1])
        return [l for d in ("N", "S", "E", "W") for l in sorted(groups[d], key=lane_num)]

    def _approach_lanes(self, tl_id: str) -> list[str]:
        """Cached canonical lane list for *tl_id* (see _compute_lane_order)."""
        order = getattr(self, "_lane_order", None) or {}
        if tl_id not in order:
            order[tl_id] = self._compute_lane_order(tl_id)
            self._lane_order = order
        return order[tl_id]

    def _highlight_fault_lanes(self) -> None:
        """SUMO-GUI only: outline the faulted lanes in red and centre the view."""
        i = self.fault_intersection
        if i < 0 or i >= len(self._tl_ids):
            return
        tc      = _traci()
        tl_id   = self._tl_ids[i]
        lanes   = self._approach_lanes(tl_id)
        targets = self._fault_target_lanes[i] or []
        for idx in targets:
            if idx >= len(lanes):
                continue
            lane  = lanes[idx]
            shape = tc.lane.getShape(lane)
            try:
                tc.polygon.add(f"fault_{lane}", shape, (220, 30, 30, 255),
                               fill=False, polygonType="fault", layer=100,
                               lineWidth=2.5)
            except TypeError:   # older SUMO without lineWidth
                tc.polygon.add(f"fault_{lane}", shape, (220, 30, 30, 255),
                               fill=False, polygonType="fault", layer=100)
            except Exception as e:
                print(f"[gui] could not highlight {lane}: {e}")
        try:
            x, y = tc.junction.getPosition(tl_id)
            tc.gui.setOffset("View #0", x, y)
            tc.gui.setZoom("View #0", 600)
        except Exception:
            pass
        print(f"[gui] fault site: junction {i} ({tl_id}), lanes {targets} outlined in red")

    @staticmethod
    def _unique_lanes(controlled_lanes, n: int) -> list[str]:
        """Return up to *n* unique lane IDs in first-seen order.

        tc.trafficlight.getControlledLanes() returns one entry per TL movement
        (link), so the same physical lane appears multiple times when it serves
        more than one turning movement (e.g. a shared through+right lane).
        Deduplication prevents double-counting queues in both the observation
        and the reward.

        For the grid2x2 network with 4 arms x 3 lanes, the first-seen order
        follows SUMO's internal movement ordering:
            N lane 0, N lane 1, N lane 2,  <- phase-0 arm 0
            S lane 0, S lane 1, S lane 2,  <- phase-0 arm 1
            E lane 0, E lane 1, E lane 2,  <- phase-1 arm 0
            W lane 0, W lane 1, W lane 2,  <- phase-1 arm 1
        yielding 12 unique lanes split evenly: first 6 -> phase 0 (NS),
        last 6 -> phase 1 (EW).  This ordering is assumed by std_mp's
        MaxPressureController in full mode (inputs_per_phase = 12 // 2 = 6).
        """
        seen: set[str]  = set()
        out:  list[str] = []
        for lane in controlled_lanes:
            if lane not in seen:
                seen.add(lane)
                out.append(lane)
            if len(out) == n:
                break
        return out

    def _get_raw_readings(self, tl_idx: int) -> np.ndarray:
        """Get raw queue readings for intersection tl_idx (self._net_lanes values).

        Uses _unique_lanes() to deduplicate SUMO's movement-indexed lane list
        before reading halting counts.
        """
        tc    = _traci()
        tl_id = self._tl_ids[tl_idx]
        lanes = self._approach_lanes(tl_id)
        readings = [tc.lane.getLastStepHaltingNumber(l) for l in lanes]
        while len(readings) < self._net_lanes:
            readings.append(0)
        return np.array(readings, dtype=float)

    def _get_downstream_queues(self, lanes: list[str]) -> np.ndarray:
        """Downstream queue per approach lane (Varaiya 2013 x_out term).

        For each approach lane, reads the halting count on its successor
        outgoing lane(s) using tc.lane.getLinks().  Uniform turning
        proportions: if a lane connects to k successor lanes, x_out for
        that approach lane = mean of their halting counts (1/k weight each).

        Uses TraCI ground truth -- faults affect upstream approach readings
        only (stop-line detectors), not the downstream outgoing readings.

        This is geometry-agnostic: works for any SUMO network by following
        the actual link topology rather than assuming a fixed lane layout.

        Parameters
        ----------
        lanes : list[str]
            Unique approach lane IDs (output of _unique_lanes()).

        Returns
        -------
        np.ndarray, shape (len(lanes),)
            Downstream queue count per approach lane.
        """
        tc = _traci()
        downstream: list[float] = []
        for lane in lanes:
            try:
                # getLinks returns list of (to_lane, via_lane, ...) tuples
                links = tc.lane.getLinks(lane)
                if links:
                    # Uniform turning proportions: weight = 1 / n_successors
                    q_out = float(np.mean([
                        tc.lane.getLastStepHaltingNumber(link[0])
                        for link in links
                    ]))
                else:
                    q_out = 0.0
            except Exception:
                q_out = 0.0
            downstream.append(q_out)
        return np.array(downstream, dtype=float)

    def _get_phase(self, tl_idx: int) -> int:
        """Map current SUMO raw phase index to RL phase (0=NS, 1=EW).

        Uses self._phase_stride (2 for grid2x2, 4 for cologne1) to map
        from raw SUMO phase number to the binary action-space phase index.
        """
        tc = _traci()
        tl_id  = self._tl_ids[tl_idx]
        raw_ph = tc.trafficlight.getPhase(tl_id)
        return int(raw_ph // self._phase_stride) % self._n_phases

    def _get_obs(self) -> np.ndarray:
        """Build observation vector for all intersections.

        grid2x2 : shape (28,) - 4 junctions x 7-dim each
                  [agg_0/Q_max, ..., agg_5/Q_max, phase]

        cologne1 : shape (5,)  - 1 junction x 5-dim
                  [agg_0/Q_max, ..., agg_3/Q_max, phase]
                  Raw 8-lane readings are reordered to [NS_lanes | EW_lanes]
                  before PASA aggregation so the per-arm blocking aligns with
                  MaxPressureController's contiguous-phase-block assumption.

        ALWAYS uses PASA mean (no L1) aggregates for all controllers.
        This keeps the RL observation space consistent with training.
        """
        # stateful filters must advance once per decision: reuse this step's obs
        if self._obs_cache is not None and self._obs_cache[0] == self._step:
            return self._obs_cache[1].copy()
        all_obs = []
        for i in range(len(self._tl_ids)):
            raw     = self._get_raw_readings(i)
            phase   = self._get_phase(i)
            faulted = self._apply_injection(i, raw)

            if self._is_cologne1:
                # Reorder: [E0,E1,S0,S1,W0,W1,N0,N1] -> [S0,S1,N0,N1,E0,E1,W0,W1]
                # = [NS_lanes (C1_NS_INDICES) | EW_lanes (C1_EW_INDICES)]
                reorder_idx = C1_NS_INDICES + C1_EW_INDICES   # [2,3,6,7,0,1,4,5]
                faulted = faulted[reorder_idx]

            if self._is_cologne1 or not self._obs_filters:
                pasa_agg = self._pasa[i].aggregate(faulted)   # mean, no-L1
                obs_i    = np.append(pasa_agg / Q_MAX, float(phase))
            else:
                f  = self._obs_filters[i]
                y  = f(faulted, phase, self._vc_w[i] if i < len(self._vc_w) else None)
                nq = f.out_dim - f.n_flags                    # queues first, then 0/1 flags
                y[:nq] = np.clip(y[:nq] / Q_MAX, 0.0, 1.0)
                obs_i  = np.append(y, float(phase))
            all_obs.append(obs_i)

        obs = np.concatenate(all_obs)
        self._obs_cache = (self._step, obs.copy())
        return obs   # shape: (28,) grid2x2 or (5,) cologne1

    def _get_reward_with_per_intersection(self) -> tuple[float, list[float]]:
        """Reward = negative mean halting vehicles + per-intersection breakdown.

        Returns
        -------
        reward : float  - scalar reward (negative mean queue across all lanes)
        intersection_queues : list[float]  - mean halting veh per TL (len = N_INTERSECTIONS)
        """
        tc = _traci()
        total, count = 0.0, 0
        intersection_queues: list[float] = []
        for tl_id in self._tl_ids:
            unique = self._approach_lanes(tl_id)
            tl_total, tl_count = 0.0, 0
            for lane in unique:
                h = tc.lane.getLastStepHaltingNumber(lane)
                tl_total += h
                tl_count += 1
                total    += h
                count    += 1
            intersection_queues.append(tl_total / max(tl_count, 1))
        return -(total / max(count, 1)), intersection_queues

    def _get_reward(self) -> float:
        """Scalar reward only (backward-compat; not used in step())."""
        reward, _ = self._get_reward_with_per_intersection()
        return reward

    # -- controller helpers (used by experiment.py) ---------------------------

    def get_controller_action(self, obs: np.ndarray) -> np.ndarray:
        """Select actions according to the configured controller type.

        Controller logic per type
        -------------------------
        std_mp :
            Exact Varaiya (2013) MP with spillback prevention.
            Receives the raw (possibly faulted) per-lane upstream readings
            (n_lanes=12) with no PASA preprocessing, plus the downstream
            queue counts read from TraCI (ground truth, not faulted).
            W_l = max(0, faulted_l - x_out_l)
            P_S = sum_{l in S} c_l * W_l  (active phase only)
            MaxPressureController auto-detects full mode from input length
            (inputs_per_phase = 12 // 2 = 6).

        pasa_mean_mp  (and legacy alias pasa_mp) :
            L2 mean aggregation on the faulted upstream readings -> 6
            aggregates -> simplified MP (downstream_queues = None).
            No L1 filter.  Pure domain-knowledge baseline.

        pasa_max_mp :
            L2 max aggregation on the faulted upstream readings -> 6
            aggregates -> simplified MP.
            No L1 filter.  G1 (HZ exact recovery) + G2 (noise 36%).

        pasa_mean_l1_mp :
            L1 plausibility filter + L2 mean aggregation -> 6 aggregates
            -> simplified MP.

        pasa_max_l1_mp :
            L1 plausibility filter + L2 max aggregation -> 6 aggregates
            -> simplified MP.

        pasa_plus_mp :
            L1 + L2 max + L3 phase-conditional EWMA -> 6 smooth aggregates
            -> simplified MP.

        rl :
            Pre-trained DQN agent.  Requires self.rl_agent to be set.
        """
        tc      = _traci()
        actions = np.zeros(len(self._tl_ids), dtype=int)

        for i in range(len(self._tl_ids)):
            raw     = self._get_raw_readings(i)
            phase   = self._get_phase(i)
            faulted = self._apply_injection(i, raw)

            # cologne1: reorder [E0,E1,S0,S1,W0,W1,N0,N1] -> [NS_block|EW_block]
            # so MaxPressureController's phase-block slicing is correct.
            # grid2x2: lanes are already in [NS_block|EW_block] order; no-op.
            if self._is_cologne1:
                _c1_reorder = C1_NS_INDICES + C1_EW_INDICES   # [2,3,6,7,0,1,4,5]
                faulted_raw = faulted
                faulted     = faulted[_c1_reorder]

            if self.controller_type in ("std_mp_recall", "std_mp_maxrecall"):
                # Detector-failure fallback used by field controllers: diagnosed
                # detectors are ignored (no call) and their phase is placed on
                # recall (served at least every recall_interval s, see
                # _apply_max_red). Diagnosis is an oracle, i.e. an upper bound
                # for this baseline.
                diag = self._diagnosed_lanes(i)
                if diag:
                    mask = np.zeros(self._net_lanes, dtype=bool)
                    mask[diag] = True
                    if self._is_cologne1:
                        mask = mask[_c1_reorder]
                    faulted = np.where(mask, 0.0, faulted)

            if self.controller_type in ("std_mp", "std_mp_recall", "std_mp_maxrecall"):
                # -- Exact Varaiya (2013) MP ----------------------------------
                # Upstream  : faulted per-lane readings (reordered for cologne1).
                #             No PASA preprocessing -- corrupted values reach
                #             MP directly, demonstrating fault vulnerability.
                # Downstream: TraCI oracle queue on outgoing lanes (x_out).
                #             Not subject to sensor faults (exit detectors).
                # Formula   : W_l = max(0, faulted_l - x_out_l)
                tl_id      = self._tl_ids[i]
                lanes      = self._approach_lanes(tl_id)
                downstream = self._get_downstream_queues(lanes)
                if self._is_cologne1:
                    # downstream was fetched in raw lane order; reorder to match
                    # the reordered faulted array so MP's W_l pairs are correct.
                    downstream = downstream[_c1_reorder]
                # Pass full upstream + downstream;
                # MP auto-groups inputs_per_phase = n_inputs // 2 per phase.
                actions[i] = self._mp_ctrls[i].select_phase(faulted, downstream)
                h = self._net_lanes // 2          # phase loads for max-recall gap-out
                self._phase_load[i] = [float(np.sum(faulted[:h])), float(np.sum(faulted[h:]))]

            elif self.controller_type in ("webster_fallback_mp",):
                # MP-Q while all detectors are healthy; see _update_fallback
                q = np.clip(faulted, 0.0, self._pasa[i].q_max)
                actions[i] = self._mp_ctrls[i].select_phase(q)

            elif self.controller_type == "oracle_cg_mp":
                # PASA-CG replacement ladder driven by oracle flags (no tests)
                diag = self._diagnosed_lanes(i)
                flags = np.zeros(self._net_lanes, dtype=bool)
                for ix in diag:
                    flags[C1_RAW_TO_CANON[ix] if self._is_cologne1 else ix] = True
                if self._is_cologne1:
                    L = self._lanes_per_arm
                    canon = np.concatenate([faulted[L:2*L], faulted[:L], faulted[2*L:]])
                    out = self._cg[i].process(canon, phase, self._vc_w[i], oracle_flags=flags)
                    q = np.concatenate([out[L:2*L], out[:L], out[2*L:]])
                else:
                    q = self._cg[i].process(faulted, phase, self._vc_w[i], oracle_flags=flags)
                actions[i] = self._mp_ctrls[i].select_phase(q)

            elif self.controller_type == "std_mp_q":
                # -- Queue-only MP: the same pressure form as the PASA variants
                # (sum of clipped lane queues, no downstream term) but without
                # aggregation. With healthy sensors it chooses exactly the same
                # phase as PASA-mean (verify.py), so differences isolate the aggregation.
                q = np.clip(faulted, 0.0, self._pasa[i].q_max)
                actions[i] = self._mp_ctrls[i].select_phase(q)

            elif self.controller_type == "l1_mp":
                # -- L1 plausibility filter per lane + queue-only MP ----------
                q = self._l1_only[i].filter_lanes(faulted, phase)
                actions[i] = self._mp_ctrls[i].select_phase(q)

            elif self.controller_type in CG_CONTROLLERS:
                # -- Consistency-gated PASA: unflagged lanes pass through unchanged
                # (exact queue-only MP when nothing is flagged); flagged lanes are
                # replaced by the opposite lane scaled by v/c, or by planning arrivals.
                if self._is_cologne1:
                    L = self._lanes_per_arm          # faulted = [S, N, E, W] blocks
                    canon = np.concatenate([faulted[L:2*L], faulted[:L], faulted[2*L:]])
                    out = self._cg[i].process(canon, phase, self._vc_w[i])
                    q = np.concatenate([out[L:2*L], out[:L], out[2*L:]])
                else:
                    q = self._cg[i].process(faulted, phase, self._vc_w[i])
                actions[i] = self._mp_ctrls[i].select_phase(q)

            elif self.controller_type in ("pasa_mean_vc_mp", "pasa_max_vc_mp"):
                # -- v/c-scaled PASA: aggregate queue-per-unit-demand, then
                # rescale by the pair's mean v/c. Opposing arms with unequal
                # demand become comparable; a failed major-arm detector is
                # replaced by the minor arm's queue scaled up to major demand.
                how = "mean" if self.controller_type == "pasa_mean_vc_mp" else "max"
                agg = self._vc_aggregate(i, faulted_raw if self._is_cologne1 else faulted, how)
                actions[i] = self._mp_ctrls[i].select_phase(agg)

            elif self.controller_type in ("pasa_mean_mp", "pasa_mp"):
                # -- PASA-mean-MP (and backward-compat alias pasa_mp) ---------
                # L2 mean aggregation only (no L1 filter, stateless).
                # pasa_mp is kept as a legacy alias so old result files remain
                # comparable.
                agg        = self._pasa[i].aggregate(faulted)
                actions[i] = self._mp_ctrls[i].select_phase(agg)

            elif self.controller_type == "pasa_max_mp":
                # -- PASA-max-MP ----------------------------------------------
                # L2 max aggregation (no L1 filter, stateless).
                # G1: healthy-side hard-zero exact recovery.
                # G2: noise variance reduced to ~36%.
                agg        = self._pasa_max[i].aggregate(faulted)
                actions[i] = self._mp_ctrls[i].select_phase(agg)

            elif self.controller_type == "pasa_mean_l1_mp":
                # -- PASA-mean-L1-MP ------------------------------------------
                # L1 plausibility filter (stateful) + L2 mean aggregation.
                agg        = self._pasa_mean_l1[i].process(
                    faulted, phase=phase, step=self._step
                )
                actions[i] = self._mp_ctrls[i].select_phase(agg)

            elif self.controller_type == "pasa_max_l1_mp":
                # -- PASA-max-L1-MP -------------------------------------------
                # L1 plausibility filter (stateful) + L2 max aggregation.
                agg        = self._pasa_max_l1[i].process(
                    faulted, phase=phase, step=self._step
                )
                actions[i] = self._mp_ctrls[i].select_phase(agg)

            elif self.controller_type == "pasa_plus_mp":
                # -- PASA+-MP (full system) ------------------------------------
                # L1 + L2 max + L3 phase-conditional EWMA -> smooth aggregates
                # -> simplified MP.
                agg        = self._pasa_plus[i].process(
                    faulted, phase=phase, step=self._step
                )
                actions[i] = self._mp_ctrls[i].select_phase(agg)

            elif self.controller_type == "rl":
                if self.rl_agent is None:
                    raise ValueError(
                        "rl_agent must be provided when controller='rl'"
                    )
                if i == 0:
                    full_obs      = self._get_obs()
                    joint_actions = self.rl_agent.predict(
                        full_obs, n_intersections=len(self._tl_ids)
                    )
                actions[i] = int(joint_actions[i])

            elif self.controller_type == "fixed_time":
                # step() does not call setPhase for fixed_time; return 0 placeholder
                actions[i] = 0

        return actions

    def __repr__(self) -> str:
        return (
            f"SumoTrafficEnv(controller={self.controller_type!r}, "
            f"fault_mode={self.fault_mode!r}, "
            f"fault_fraction={self.fault_fraction}, "
            f"use_gui={self.use_gui})"
        )
