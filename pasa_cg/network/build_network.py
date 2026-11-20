"""
pasa_cg.network.build_network
===============================
Builds the 2x2 signalised grid with netconvert and writes its route file.

* four junctions I_NW, I_NE, I_SW, I_SE; 200 m links, 50 km/h, three lanes per approach
* eight boundary entries; turning split 70/15/15 (through/right/left)
* two-phase signal program (N+S, E+W) with 3 s yellows
* demand: departure probability per entry and second (DEMAND_LEVELS), equal
  at all entries (symmetric) or scaled 0.6 (N, E) and 1.4 (S, W) (asymmetric)

       B_N_NW     B_N_NE
         |           |
B_W_NW--I_NW--I_NE--B_E_NE
         |      |
B_W_SW--I_SW--I_SE--B_E_SE
         |      |
       B_S_SW  B_S_SE

    from pasa_cg.network.build_network import build_2x2_grid
    net_path, rou_path = build_2x2_grid(output_dir="data/net", demand_level="medium")
"""

from __future__ import annotations

import re
import subprocess
import textwrap
import argparse
from pathlib import Path


# Constants (keep in sync with sumo_env.py)

GRID_N        = 2
LANE_LENGTH   = 200      # metres (internal + stub edges)
NUM_LANES     = 3        # lanes per approach arm  (12 sensors per junction)
SPEED_MS      = 13.89    # 50 km/h

# SUMO-RL compatible 8-phase TL timing
GREEN_MAIN    = 33       # NS/EW straight + left green (s)
GREEN_TURN    = 6        # NS/EW right-turn green (s)
YELLOW_TIME   = 3        # yellow transition (s)

# Demand (matches SUMO-RL 2x2 benchmark: 4 flows at p=0.10)
FLOW_PROB     = 0.10     # departure probability per second (Low-demand default)

# Demand levels: departure probability -> approximate v/c ratio.
# Calibrated empirically on the 2x2 SUMO-RL benchmark grid (3 lanes/arm,
# 33 s green / 3 s yellow, saturation flow ~ 1800 veh/h/lane).
# v/c is estimated as cycle-average lane queue / saturation occupancy.
#   p = 0.10 -> v/c ~ 29 %   (SUMO-RL baseline demand)
#   p = 0.20 -> v/c ~ 58 %   (linear 2x scale)
#   p = 0.31 -> v/c ~ 90 %   (p=0.30 gives ~87 %; +0.01 targets 90 %)
DEMAND_LEVELS: dict[str, float] = {
    "low":    0.10,
    "medium": 0.20,
    "high":   0.26,   # legacy table; recalibrated 2026-11-09 (was 0.38)
}

# Departure probability per entry (veh/s) by demand profile. "high" is the
# highest demand at which queue-based max-pressure still keeps up (vehicles
# waiting to enter < 1 % of trips), calibrated with healthy sensors
# (2026-11-08): symmetric 0.38 (70 waiting / 10,889 trips; 0.45 -> 480),
# asymmetric 0.31 (13 waiting; 0.38 -> 1,252). The asymmetric profile loads
# its major entries 1.4x, so it reaches capacity at a lower p.
# 2026-11-09 recalibration: max-pressure with 10 s decisions switches phase at
# almost every decision and, with a 3 s yellow per switch, loses to Webster
# fixed time above p ~0.32 (symmetric) / ~0.28 (asymmetric); at the old high
# levels (0.38 / 0.31) faults had no effect. High is now p = 0.26 for both
# profiles: MP still beats fixed time (18.8 vs 26.5 s symmetric, 23.1 vs 26.4 s
# asymmetric, healthy, seed 0) and both profiles carry the same total demand.
DEMAND_LEVELS_BY_PROFILE: dict[str, dict[str, float]] = {
    "symmetric":  {"low": 0.10, "medium": 0.20, "high": 0.26},
    "asymmetric": {"low": 0.10, "medium": 0.20, "high": 0.26},
}


def demand_prob(demand_level: str, demand_profile: str = "symmetric") -> float:
    """Departure probability per entry for a named level under a demand profile."""
    levels = DEMAND_LEVELS_BY_PROFILE.get(demand_profile, DEMAND_LEVELS)
    if demand_level not in levels:
        raise ValueError(f"Unknown demand_level {demand_level!r}. Choose from: {list(levels)}")
    return levels[demand_level]
SIM_END_FLOW  = 100_000  # route file end time (well beyond episode)
SIM_DURATION  = 3600     # seconds per episode
SIM_STEP      = 0.1      # seconds

# Fixed flow paths: (from_edge_id, to_edge_id)
# Entry edges come from boundary stubs; exit edges go to boundary stubs.
FLOW_PAIRS = [
    # SUMO-RL 2x2 benchmark flows (northbound / eastbound)
    ("B_S_SW_I_SW", "I_NW_B_N_NW"),   # NS through left column  (northbound)
    ("B_S_SE_I_SE", "I_NE_B_N_NE"),   # NS through right column (northbound)
    ("B_W_SW_I_SW", "I_SE_B_E_SE"),   # EW through bottom row   (eastbound)
    ("B_W_NW_I_NW", "I_NE_B_E_NE"),   # EW through top row      (eastbound)
    # Reverse flows (southbound / westbound) -- added so that BOTH arms of every
    # phase pair carry traffic. Without them the partner arm of every busy arm
    # is empty and PASA's L2 phase-pair redundancy (G1) cannot operate.
    ("B_N_NW_I_NW", "I_SW_B_S_SW"),   # NS through left column  (southbound)
    ("B_N_NE_I_NE", "I_SE_B_S_SE"),   # NS through right column (southbound)
    ("B_E_SE_I_SE", "I_SW_B_W_SW"),   # EW through bottom row   (westbound)
    ("B_E_NE_I_NE", "I_NW_B_W_NW"),   # EW through top row      (westbound)
]


# Network builder

def _net_needs_regeneration(net_path: Path) -> bool:
    """Return True if net_path was generated with the wrong number of lanes.

    Checks the first regular (non-internal) edge's lane count.
    """
    try:
        text = net_path.read_text(encoding="utf-8")
        for m in re.finditer(r'<edge\b([^>]+)>', text):
            attrs = m.group(1)
            id_m = re.search(r'\bid="([^":][^"]*)"', attrs)
            if not id_m:
                continue
            pos = m.end()
            end = text.find("</edge>", pos)
            if end == -1:
                continue
            block = text[pos:end]
            lane_count = len(re.findall(r'<lane\b', block))
            if lane_count > 0:
                return lane_count != NUM_LANES
        return False
    except Exception:
        return True


def build_2x2_grid(
    output_dir:   str | Path  = "data/net",
    overwrite:    bool        = False,
    demand_level: str | None  = None,
    flow_prob:    float | None = None,
    demand_profile: str = "symmetric",
) -> tuple[Path, Path]:
    """Generate SUMO 2x2 grid network files with SUMO-RL-compatible demand.

    Parameters
    ----------
    output_dir : str | Path
        Directory where network, route and config files are written.
    overwrite : bool
        Re-generate even if files already exist.
    demand_level : str | None
        One of ``"low"``, ``"medium"``, ``"high"`` (see ``DEMAND_LEVELS``).
        Determines departure probability when *flow_prob* is not supplied.
        Defaults to ``"low"`` (p=0.10, v/c~29 %).
    flow_prob : float | None
        Override departure probability per second directly.  When supplied,
        *demand_level* is ignored.  Values > 0.35 risk insertion failures at
        network boundaries (SUMO will warn).

    Returns
    -------
    net_path : Path   -- SUMO network file (.net.xml)
    rou_path : Path   -- Route / demand file (.rou.xml)
    """
    # Resolve effective departure probability
    if flow_prob is not None:
        effective_prob = float(flow_prob)
    elif demand_level is not None:
        if demand_level not in DEMAND_LEVELS:
            raise ValueError(
                f"Unknown demand_level {demand_level!r}. "
                f"Choose from: {list(DEMAND_LEVELS)}"
            )
        effective_prob = demand_prob(demand_level, demand_profile)
    else:
        effective_prob = FLOW_PROB   # backward-compatible default
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    net_path = output_dir / "grid2x2.net.xml"
    rou_path = output_dir / "grid2x2.rou.xml"
    cfg_path = output_dir / "grid2x2.sumocfg"

    if not overwrite and net_path.exists() and rou_path.exists():
        need_regen = _net_needs_regeneration(net_path)
        if need_regen:
            print(
                f"[build_network] Existing net.xml has wrong lane count "
                f"-- regenerating with {NUM_LANES} lanes per arm..."
            )
        else:
            print(f"[build_network] Reusing existing net -- re-patching TL + route "
                  f"(p={effective_prob})...")
            _patch_tl_logic(net_path)
            _write_route_file(rou_path, flow_prob=effective_prob, demand_profile=demand_profile)
            _apply_webster_timing(net_path, effective_prob, demand_profile)
            _write_sumo_config(cfg_path, net_path, rou_path)
            print(f"[build_network] Network files up to date in {output_dir}")
            return net_path, rou_path

    # -- 1. Write plain-XML node and edge files, then run netconvert ----------
    node_path = output_dir / "grid2x2.nod.xml"
    edge_path = output_dir / "grid2x2.edg.xml"
    _write_node_xml(node_path)
    _write_edge_xml(edge_path)

    cmd = [
        "netconvert",
        f"--node-files={node_path}",
        f"--edge-files={edge_path}",
        "--no-turnarounds",
        "--tls.guess=true",
        "--tls.green.time=33",
        "--tls.yellow.time=3",
        f"--output-file={net_path}",
    ]
    print(f"[build_network] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"netconvert failed:\n{result.stderr}")
    print(f"[build_network] Network written -> {net_path}")

    # -- 2. Patch TL programs -> safe 4-phase default (NS / EW) ---------------
    _patch_tl_logic(net_path)
    print(f"[build_network] 4-phase TL programs patched in {net_path.name}")

    # -- 3. Route file (demand: 4 flows at effective_prob) --------------------
    _write_route_file(rou_path, flow_prob=effective_prob, demand_profile=demand_profile)
    _apply_webster_timing(net_path, effective_prob, demand_profile)
    print(f"[build_network] Routes written  -> {rou_path}  (p={effective_prob})")

    # -- 4. SUMO config --------------------------------------------------------
    _write_sumo_config(cfg_path, net_path, rou_path)
    print(f"[build_network] Config written  -> {cfg_path}")

    return net_path, rou_path


# Plain-XML network files (node + edge) for netconvert

def _write_node_xml(path: Path) -> None:
    """Write SUMO plain-XML node file for 2x2 grid with boundary dead-end stubs."""
    L = LANE_LENGTH
    xml = textwrap.dedent(f"""\
    <?xml version="1.0" encoding="UTF-8"?>
    <nodes>
      <!-- 4 traffic-light intersections (2x2 grid) -->
      <node id="I_SW" x="0"   y="0"   type="traffic_light"/>
      <node id="I_SE" x="{L}" y="0"   type="traffic_light"/>
      <node id="I_NW" x="0"   y="{L}" type="traffic_light"/>
      <node id="I_NE" x="{L}" y="{L}" type="traffic_light"/>

      <!-- 8 boundary dead-end stubs (entry/exit points) -->
      <node id="B_S_SW" x="0"    y="{-L}"   type="dead_end"/>
      <node id="B_S_SE" x="{L}"  y="{-L}"   type="dead_end"/>
      <node id="B_N_NW" x="0"    y="{2*L}"  type="dead_end"/>
      <node id="B_N_NE" x="{L}"  y="{2*L}"  type="dead_end"/>
      <node id="B_W_SW" x="{-L}" y="0"      type="dead_end"/>
      <node id="B_W_NW" x="{-L}" y="{L}"    type="dead_end"/>
      <node id="B_E_SE" x="{2*L}" y="0"     type="dead_end"/>
      <node id="B_E_NE" x="{2*L}" y="{L}"   type="dead_end"/>
    </nodes>
    """)
    path.write_text(xml, encoding="utf-8")


def _write_edge_xml(path: Path) -> None:
    """Write SUMO plain-XML edge file for 2x2 grid with boundary dead-end stubs."""
    n = NUM_LANES
    s = SPEED_MS
    L = LANE_LENGTH

    def edge(eid: str, frm: str, to: str) -> str:
        return (f'  <edge id="{eid}" from="{frm}" to="{to}"'
                f' numLanes="{n}" speed="{s}" length="{L}"/>')

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<edges>",
             "  <!-- Internal edges (bidirectional) -->"]
    # EW internal
    lines += [
        edge("I_SW_I_SE", "I_SW", "I_SE"),
        edge("I_SE_I_SW", "I_SE", "I_SW"),
        edge("I_NW_I_NE", "I_NW", "I_NE"),
        edge("I_NE_I_NW", "I_NE", "I_NW"),
    ]
    # NS internal
    lines += [
        edge("I_SW_I_NW", "I_SW", "I_NW"),
        edge("I_NW_I_SW", "I_NW", "I_SW"),
        edge("I_SE_I_NE", "I_SE", "I_NE"),
        edge("I_NE_I_SE", "I_NE", "I_SE"),
    ]
    lines.append("  <!-- Boundary stub edges (from dead-end INTO network) -->")
    # South stubs
    lines += [
        edge("B_S_SW_I_SW", "B_S_SW", "I_SW"),
        edge("I_SW_B_S_SW", "I_SW", "B_S_SW"),
        edge("B_S_SE_I_SE", "B_S_SE", "I_SE"),
        edge("I_SE_B_S_SE", "I_SE", "B_S_SE"),
    ]
    # North stubs
    lines += [
        edge("B_N_NW_I_NW", "B_N_NW", "I_NW"),
        edge("I_NW_B_N_NW", "I_NW", "B_N_NW"),
        edge("B_N_NE_I_NE", "B_N_NE", "I_NE"),
        edge("I_NE_B_N_NE", "I_NE", "B_N_NE"),
    ]
    # West stubs
    lines += [
        edge("B_W_SW_I_SW", "B_W_SW", "I_SW"),
        edge("I_SW_B_W_SW", "I_SW", "B_W_SW"),
        edge("B_W_NW_I_NW", "B_W_NW", "I_NW"),
        edge("I_NW_B_W_NW", "I_NW", "B_W_NW"),
    ]
    # East stubs
    lines += [
        edge("B_E_SE_I_SE", "B_E_SE", "I_SE"),
        edge("I_SE_B_E_SE", "I_SE", "B_E_SE"),
        edge("B_E_NE_I_NE", "B_E_NE", "I_NE"),
        edge("I_NE_B_E_NE", "I_NE", "B_E_NE"),
    ]
    lines.append("</edges>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# TL patcher: safe 4-phase default (NS green -> NS yellow -> EW green -> EW yellow)

def _make_phase_state(n_links: int, green_idxs: list[int],
                      yellow_idxs: list[int],
                      permissive_idxs: list[int] | None = None) -> str:
    """Build a phase state string.

    'G' = protected green (clear right-of-way, straight movements)
    'g' = permissive green (yield - right/left turns, avoids SUMO unsafe warnings)
    'y' = yellow
    'r' = red
    Application order: g first, then G (overrides g), then y (overrides G/g).
    """
    chars = ["r"] * n_links
    for i in (permissive_idxs or []):
        if 0 <= i < n_links:
            chars[i] = "g"
    for i in green_idxs:
        if 0 <= i < n_links:
            chars[i] = "G"
    for i in yellow_idxs:
        if 0 <= i < n_links:
            chars[i] = "y"
    return "".join(chars)


def _patch_tl_logic(net_path: Path) -> None:
    """Replace all tlLogic blocks in net_path with a safe 4-phase program.

    Phase 0 (GREEN_MAIN s): NS straight=G, NS right/left turns=g, EW=r
    Phase 1 (YELLOW_TIME s): NS yellow, EW red
    Phase 2 (GREEN_MAIN s): EW straight=G, EW right/left turns=g, NS=r
    Phase 3 (YELLOW_TIME s): EW yellow, NS red

    RL action mapping (PHASE_STRIDE=2 in sumo_env.py):
        action 0 --> SUMO phase 0  (NS green)
        action 1 --> SUMO phase 2  (EW green)

    NS vs EW direction is determined from junction coordinates in net.xml:
    an edge whose from-junction and to-junction share the same x-coordinate
    (same grid column) is a N-S approach; same y-coordinate means E-W.
    This works with any SUMO attribute ordering or netconvert version.

    Within each phase, straight movements use protected green ('G') while
    right and left turns use permissive green ('g') to prevent SUMO's
    "unsafe green phase" warning when opposite turns share an output lane.
    """
    text = net_path.read_text(encoding="utf-8")

    # 1. Parse junction x,y coordinates
    junc_x: dict[str, float] = {}
    junc_y: dict[str, float] = {}
    for m in re.finditer(r'<junction\b([^>]+)>', text):
        a    = m.group(1)
        id_m = re.search(r'\bid="([^"]+)"', a)
        x_m  = re.search(r'\bx="([^"]+)"',  a)
        y_m  = re.search(r'\by="([^"]+)"',  a)
        if id_m and x_m and y_m:
            junc_x[id_m.group(1)] = float(x_m.group(1))
            junc_y[id_m.group(1)] = float(y_m.group(1))

    # 2. Parse edge from/to junction for non-internal edges (id has no ':')
    edge_ep: dict[str, tuple[str, str]] = {}
    for m in re.finditer(r'<edge\b([^>]+)>', text):
        a      = m.group(1)
        id_m   = re.search(r'\bid="([^":][^"]*)"', a)
        from_m = re.search(r'\bfrom="([^"]+)"',    a)
        to_m   = re.search(r'\bto="([^"]+)"',      a)
        if id_m and from_m and to_m:
            edge_ep[id_m.group(1)] = (from_m.group(1), to_m.group(1))

    def is_ns(edge_id: str) -> bool:
        """True if edge is a N-S approach (from/to junctions share x-column)."""
        ep = edge_ep.get(edge_id)
        if not ep:
            return False
        fx = junc_x.get(ep[0])
        tx = junc_x.get(ep[1])
        return fx is not None and tx is not None and abs(fx - tx) < 1.0

    # 3. Group linkIndex by TL and direction; distinguish straight vs turns
    #    straight movements get protected G; right/left turns get permissive g
    ns_straight: dict[str, list[int]] = {}
    ns_turns:    dict[str, list[int]] = {}
    ew_straight: dict[str, list[int]] = {}
    ew_turns:    dict[str, list[int]] = {}
    max_idx:     dict[str, int]       = {}

    for m in re.finditer(r'<connection\b([^>]+)>', text):
        a      = m.group(1)
        tl_m   = re.search(r'\btl="([^"]+)"',      a)
        li_m   = re.search(r'\blinkIndex="(\d+)"',  a)
        from_m = re.search(r'\bfrom="([^"]+)"',     a)
        dir_m  = re.search(r'\bdir="([^"]+)"',      a)
        if not (tl_m and li_m and from_m):
            continue
        tl_id     = tl_m.group(1)
        idx       = int(li_m.group(1))
        from_edge = from_m.group(1)
        direction = dir_m.group(1) if dir_m else "s"

        max_idx[tl_id] = max(max_idx.get(tl_id, -1), idx)
        ns       = is_ns(from_edge)
        straight = (direction == "s")

        if ns:
            (ns_straight if straight else ns_turns).setdefault(tl_id, []).append(idx)
        else:
            (ew_straight if straight else ew_turns).setdefault(tl_id, []).append(idx)

    link_counts: dict[str, int] = {tl: v + 1 for tl, v in max_idx.items()}

    # 4. Build 4-phase program for each tlLogic block
    tl_id_pat  = re.compile(r'\bid="([^"]+)"')
    tl_blk_pat = re.compile(r'<tlLogic\b.*?</tlLogic>', re.DOTALL)

    def replacement(m: re.Match) -> str:
        blk   = m.group(0)
        tid_m = tl_id_pat.search(blk)
        if tid_m is None:
            return blk
        tl_id = tid_m.group(1)
        n     = link_counts.get(tl_id, 20)
        ns_s  = sorted(ns_straight.get(tl_id, []))
        ns_t  = sorted(ns_turns.get(tl_id,    []))
        ew_s  = sorted(ew_straight.get(tl_id, []))
        ew_t  = sorted(ew_turns.get(tl_id,    []))
        ns_all = ns_s + ns_t
        ew_all = ew_s + ew_t

        phases = [
            # Phase 0: NS green - N+S approaches only; E+W remain red
            (GREEN_MAIN,  _make_phase_state(n, ns_s, [],     ns_t)),
            # Phase 1: NS yellow
            (YELLOW_TIME, _make_phase_state(n, [],   ns_all)),
            # Phase 2: EW green - E+W approaches only; N+S remain red
            (GREEN_MAIN,  _make_phase_state(n, ew_s, [],     ew_t)),
            # Phase 3: EW yellow
            (YELLOW_TIME, _make_phase_state(n, [],   ew_all)),
        ]

        lines = [f'<tlLogic id="{tl_id}" type="static" programID="0" offset="0">']
        for dur, state in phases:
            lines.append(f'  <phase duration="{dur}" state="{state}"/>')
        lines.append("</tlLogic>")
        return "\n".join(lines)

    patched = tl_blk_pat.sub(replacement, text)
    net_path.write_text(patched, encoding="utf-8")


# Route file: 4 uniform demand flows (SUMO-RL 2x2 benchmark pattern)

# Turning proportions applied at each vehicle's ENTRY junction (sum = 1).
# Afterwards the vehicle continues straight to the grid boundary, so every
# junction sees through, right-turn (lane 0, shared) and left-turn (lane 2,
# shared, permissive -- yields to oncoming through traffic) movements.
TURN_SPLIT = {"through": 0.70, "right": 0.15, "left": 0.15}

_GRID_POS  = {"I_SW": (0, 0), "I_SE": (1, 0), "I_NW": (0, 1), "I_NE": (1, 1)}
_POS_GRID  = {v: k for k, v in _GRID_POS.items()}
_BOUNDARY  = {("I_SW", "S"): "B_S_SW", ("I_SE", "S"): "B_S_SE",
              ("I_NW", "N"): "B_N_NW", ("I_NE", "N"): "B_N_NE",
              ("I_SW", "W"): "B_W_SW", ("I_NW", "W"): "B_W_NW",
              ("I_SE", "E"): "B_E_SE", ("I_NE", "E"): "B_E_NE"}
_VEC       = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
_OPPOSITE  = {"N": "S", "S": "N", "E": "W", "W": "E"}
_LEFT_OF   = {"N": "W", "W": "S", "S": "E", "E": "N"}
_RIGHT_OF  = {"N": "E", "E": "S", "S": "W", "W": "N"}


def _turn_route(entry_j: str, side: str, turn: str) -> list[str]:
    """Edge list for a vehicle entering *entry_j* from the boundary on *side*,
    making *turn* there, then driving straight until it leaves the grid."""
    heading = _OPPOSITE[side]                       # entering from S -> heading N
    d = {"through": heading, "left": _LEFT_OF[heading], "right": _RIGHT_OF[heading]}[turn]
    edges = [f"{_BOUNDARY[(entry_j, side)]}_{entry_j}"]
    j = entry_j
    while True:
        x, y = _GRID_POS[j]
        dx, dy = _VEC[d]
        nxt = _POS_GRID.get((x + dx, y + dy))
        if nxt is None:
            edges.append(f"{j}_{_BOUNDARY[(j, d)]}")
            return edges
        edges.append(f"{j}_{nxt}")
        j = nxt


def _write_route_file(rou_path: Path, flow_prob: float = FLOW_PROB,
                      demand_profile: str = "symmetric") -> None:
    """Write turning-movement demand for the 2x2 grid.

    Every one of the 8 boundary entries injects vehicles with total departure
    probability *flow_prob* per second (same per-entry demand as the original
    SUMO-RL straight-through benchmark), split by TURN_SPLIT into through /
    right / left routes. 8 entries x 3 movements = 24 flows.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<routes>",
             f"  <!-- 8 entries x (through/right/left = "
             f"{TURN_SPLIT['through']:.2f}/{TURN_SPLIT['right']:.2f}/{TURN_SPLIT['left']:.2f}),"
             f" p={flow_prob} per entry, profile={demand_profile} -->"]
    flows = []
    for (entry_j, side) in sorted(_BOUNDARY):
        for turn, share in TURN_SPLIT.items():
            if share <= 0:
                continue
            rid = f"r_{entry_j}_{side}_{turn}"
            lines.append(f'  <route id="{rid}" edges="{" ".join(_turn_route(entry_j, side, turn))}"/>')
            flows.append((rid, round(flow_prob * share * DEMAND_PROFILES[demand_profile][side], 6)))
    for rid, prob in flows:
        lines.append(
            f'  <flow id="f{rid[1:]}" route="{rid}" begin="0" end="{SIM_END_FLOW}"'
            f' probability="{prob}" departSpeed="max" departPos="base" departLane="best"/>'
        )
    lines.append("</routes>")
    rou_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Demand profiles: multiplier on each entry's departure probability, keyed by
# the boundary side the vehicle enters from. "asymmetric" = 70/30 directional
# split (northbound + eastbound major) with the same total network demand.
DEMAND_PROFILES = {
    "symmetric":  {"N": 1.0, "S": 1.0, "E": 1.0, "W": 1.0},
    "asymmetric": {"N": 0.6, "S": 1.4, "E": 0.6, "W": 1.4},
}

# Webster (1958) fixed-time timing for the fixed_time reference controller.
WEBSTER_SAT_FLOW   = 1800.0   # veh/h/lane
WEBSTER_LOST_PHASE = 4.0      # s lost per phase (3 s yellow + ~1 s start-up)
WEBSTER_C_MIN      = 40.0     # s, practical minimum cycle
WEBSTER_C_MAX      = 120.0    # s
WEBSTER_G_MIN      = 7.0      # s


def _edge_flows(flow_prob: float, demand_profile: str) -> dict[str, float]:
    """Mean flow (veh/s) on every edge implied by the route generator."""
    flows: dict[str, float] = {}
    for (entry_j, side) in _BOUNDARY:
        for turn, share in TURN_SPLIT.items():
            q = flow_prob * share * DEMAND_PROFILES[demand_profile][side]
            for e in _turn_route(entry_j, side, turn):
                flows[e] = flows.get(e, 0.0) + q
    return flows


def _apply_webster_timing(net_path: Path, flow_prob: float,
                          demand_profile: str = "symmetric") -> None:
    """Set each junction's NS / EW green to Webster's optimal split.

    y_phase = max critical lane flow ratio over the phase's approaches
    (approach flow spread over NUM_LANES lanes, saturation WEBSTER_SAT_FLOW);
    C0 = (1.5 L + 5) / (1 - Y), clamped to [WEBSTER_C_MIN, WEBSTER_C_MAX];
    g_i = (C0 - 2 * YELLOW_TIME) * y_i / Y. Only fixed_time uses these timings.
    """
    flows = _edge_flows(flow_prob, demand_profile)
    text = net_path.read_text(encoding="utf-8")
    report = []
    for j, (x, _y) in _GRID_POS.items():
        y_ph = [0.0, 0.0]
        for e, q in flows.items():
            if not e.endswith("_" + j):
                continue
            frm = e[: -len(j) - 1]
            vertical = frm[2] in "NS" if frm.startswith("B_") else _GRID_POS[frm][0] == x
            k = 0 if vertical else 1
            y_ph[k] = max(y_ph[k], q * 3600.0 / NUM_LANES / WEBSTER_SAT_FLOW)
        Y = sum(y_ph)
        C = (1.5 * 2 * WEBSTER_LOST_PHASE + 5.0) / max(1.0 - Y, 0.05)
        C = min(max(C, WEBSTER_C_MIN), WEBSTER_C_MAX)
        g_tot = C - 2 * YELLOW_TIME
        g = [int(round(max(WEBSTER_G_MIN, g_tot * yi / Y if Y > 0 else g_tot / 2))) for yi in y_ph]
        m = re.search(rf'(<tlLogic id="{j}"[^>]*>)(.*?)(</tlLogic>)', text, re.S)
        if not m:
            continue
        count = [0]

        def _dur(mm):
            idx = count[0]; count[0] += 1
            return f'duration="{g[0]}"' if idx == 0 else f'duration="{g[1]}"' if idx == 2 else mm.group(0)

        body = re.sub(r'duration="[\d.]+"', _dur, m.group(2))
        text = text[:m.start(2)] + body + text[m.end(2):]
        report.append(f"{j} C={g[0] + g[1] + 2 * YELLOW_TIME}s ({g[0]}/{g[1]})")
    net_path.write_text(text, encoding="utf-8")
    print(f"[build_network] Webster fixed-time ({demand_profile}): " + "; ".join(report))


# SUMO config

def _write_sumo_config(cfg_path: Path, net_path: Path, rou_path: Path) -> None:
    xml = textwrap.dedent(f"""\
    <configuration>
      <input>
        <net-file value="{net_path.name}"/>
        <route-files value="{rou_path.name}"/>
      </input>
      <time>
        <begin value="0"/>
        <end value="{SIM_DURATION}"/>
        <step-length value="{SIM_STEP}"/>
      </time>
      <report>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
      </report>
    </configuration>
    """)
    cfg_path.write_text(xml, encoding="utf-8")


# CLI

def _cli():
    parser = argparse.ArgumentParser(
        description="Build 2x2 SUMO grid (3 lanes, 8-phase TL, SUMO-RL demand)"
    )
    parser.add_argument("--output-dir", default="data/net",
                        help="Directory for generated files")
    parser.add_argument("--overwrite", action="store_true",
                        help="Regenerate even if files already exist")
    parser.add_argument(
        "--demand-level", default="low",
        choices=list(DEMAND_LEVELS),
        help=f"Demand level (default: low). Levels: {DEMAND_LEVELS}",
    )
    args = parser.parse_args()
    build_2x2_grid(
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        demand_level=args.demand_level,
    )


if __name__ == "__main__":
    _cli()
