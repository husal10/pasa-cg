"""
pasa_itsc.network.cologne_network
===================================
Setup helper for the Cologne1 single-intersection real-world network.

Network facts (from cologne1.net.xml)
--------------------------------------
* 1 TL junction  id: ``cluster_357187_359543``
  TL logic id:   ``GS_cluster_357187_359543``
* 20 controlled links  (linkIndex 0-19)
* 4 incoming approaches (2 lanes each):
    -32038056#3  -> linkIndex 0-4   (from east)
    23429231#1   -> linkIndex 5-9   (from south / NS arm)
    28198821#3   -> linkIndex 10-14 (from west)
    27115123#3   -> linkIndex 15-19 (from north / NS arm)
* 8-phase TL program (read-only; we do NOT patch it):
    phase 0 (29 s): NS straight + left green  (rrrrrGGGggrrrrrGGGgg)
    phase 1 ( 5 s): NS yellow
    phase 2 ( 6 s): NS right-turn green
    phase 3 ( 5 s): NS right yellow
    phase 4 (29 s): EW straight + left green  (GGGggrrrrrGGGggrrrrr)
    phase 5 ( 5 s): EW yellow
    phase 6 ( 6 s): EW right-turn green
    phase 7 ( 5 s): EW right yellow
* RL mapping: action 0 -> phase 0 (NS green), action 1 -> phase 4 (EW green)
  PHASE_STRIDE = 4

Demand (cologne1.rou.xml)
--------------------------
* Individual <trip> elements (not probability flows)
* Vehicle type: ``pkw`` (passenger car)
* Depart times: t  in  [25205, 28799] s  -> episode window 25200-28800 s (3 600 s)

Usage
-----
    from pasa_itsc.network.cologne_network import build_cologne1
    net_path, rou_path = build_cologne1(output_dir="data/net")

    # With explicit source files (first-time setup):
    net_path, rou_path = build_cologne1(
        output_dir="data/net",
        net_src="path/to/cologne1.net.xml",
        rou_src="path/to/cologne1.rou.xml",
    )
"""

from __future__ import annotations

import re
import shutil
import textwrap
from pathlib import Path


# Validation

# Fingerprints expected in a valid Cologne1 network
_COLOGNE1_TL_ID   = "cluster_357187_359543"
_COLOGNE1_MIN_PHASES = 4   # 8-phase program; at least 4 phases required
_COLOGNE1_MIN_TRIPS  = 10  # sanity: real demand file has 1000+ trips


def validate_cologne1(
    net_path: Path,
    rou_path: Path,
) -> None:
    """Validate that net/rou files are genuinely Cologne1 SUMO files.

    Raises
    ------
    ValueError
        If a file is missing, is not parseable XML, or lacks expected content.
    """
    errors: list[str] = []

    # Validate net.xml
    try:
        net_text = net_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"[cologne_network] Cannot read {net_path}: {exc}") from exc

    if "<net " not in net_text and "<network" not in net_text:
        errors.append(
            f"{net_path.name} does not look like a SUMO network file "
            "(missing <net> root element)"
        )

    if _COLOGNE1_TL_ID not in net_text:
        errors.append(
            f"{net_path.name} does not contain the expected Cologne1 TL junction id "
            f"'{_COLOGNE1_TL_ID}' - are you sure this is the correct file?"
        )

    phase_count = len(re.findall(r'<phase\b', net_text))
    if phase_count < _COLOGNE1_MIN_PHASES:
        errors.append(
            f"{net_path.name} has only {phase_count} TL phase(s); "
            f"expected >={_COLOGNE1_MIN_PHASES} for Cologne1's 8-phase program"
        )

    # Validate rou.xml
    try:
        rou_text = rou_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"[cologne_network] Cannot read {rou_path}: {exc}") from exc

    if "<routes" not in rou_text:
        errors.append(
            f"{rou_path.name} does not look like a SUMO route file "
            "(missing <routes> root element)"
        )

    # Count demand entries: <trip ...> or <vehicle ...>
    trip_count = (len(re.findall(r'<trip\b', rou_text))
                  + len(re.findall(r'<vehicle\b', rou_text)))
    if trip_count < _COLOGNE1_MIN_TRIPS:
        errors.append(
            f"{rou_path.name} contains only {trip_count} demand record(s); "
            f"expected >={_COLOGNE1_MIN_TRIPS} for the Cologne1 real-world demand"
        )

    # Check depart times are in the expected simulation window
    departs = [float(m.group(1))
               for m in re.finditer(r'\bdepart="([^"]+)"', rou_text)]
    if departs:
        d_min, d_max = min(departs), max(departs)
        if d_min < 0 or d_max > 100_000:
            errors.append(
                f"{rou_path.name}: depart times span [{d_min:.0f}, {d_max:.0f}] s, "
                "which looks unusual for Cologne1 (expected ~25205-28799 s)"
            )

    if errors:
        raise ValueError(
            "[cologne_network] Validation failed:\n  - " + "\n  - ".join(errors)
        )


# Network constants  (kept here for documentation; env reads them from the env)

# SUMO simulation window matching the real-world demand file
SIM_BEGIN     = 25200    # 5 s before first trip depart (t=25205)
SIM_END       = 28800    # 1 s after last trip depart (t=28799)
SIM_DURATION  = SIM_END - SIM_BEGIN   # 3600 s
SIM_STEP      = 0.1

# TL / sensor geometry for SumoTrafficEnv
LANES_PER_ARM   = 2    # 2 through+turn lanes per approach
N_INTERSECTIONS = 1    # single junction
PHASE_STRIDE    = 4    # action 0->phase 0, action 1->phase 4


# Public builder

def build_cologne1(
    output_dir: str | Path = "data/net",
    net_src:    str | Path | None = None,
    rou_src:    str | Path | None = None,
    overwrite:  bool = False,
) -> tuple[Path, Path]:
    """Set up the Cologne1 SUMO network files.

    Copies *cologne1.net.xml* and *cologne1.rou.xml* into *output_dir* (if
    *net_src* / *rou_src* are provided) and writes a ``cologne1.sumocfg`` with
    the correct simulation time window for the real-world demand.

    Parameters
    ----------
    output_dir : str | Path
        Destination directory for SUMO files.
    net_src : str | Path | None
        Source path of ``cologne1.net.xml``.  Required on first call when the
        file is not already in *output_dir*.
    rou_src : str | Path | None
        Source path of ``cologne1.rou.xml``.  Required on first call when the
        file is not already in *output_dir*.
    overwrite : bool
        Re-copy even if destination files already exist.

    Returns
    -------
    net_path : Path  - SUMO network file (.net.xml) inside *output_dir*
    rou_path : Path  - Route/demand file (.rou.xml)  inside *output_dir*
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    net_path = output_dir / "cologne1.net.xml"
    rou_path = output_dir / "cologne1.rou.xml"
    cfg_path = output_dir / "cologne1.sumocfg"

    # Copy source files if needed
    if net_src is not None:
        net_src = Path(net_src)
        if overwrite or not net_path.exists():
            shutil.copy2(net_src, net_path)
            print(f"[cologne_network] Copied {net_src.name} -> {net_path}")
    if rou_src is not None:
        rou_src = Path(rou_src)
        if overwrite or not rou_path.exists():
            shutil.copy2(rou_src, rou_path)
            print(f"[cologne_network] Copied {rou_src.name} -> {rou_path}")

    # Validate that files exist
    if not net_path.exists():
        raise FileNotFoundError(
            f"cologne1.net.xml not found in {output_dir}.\n"
            "Copy it there manually or pass net_src=<path> to build_cologne1().\n"
            "Example:\n"
            "  build_cologne1(output_dir='data/net',\n"
            "                 net_src='cologne1.net.xml',\n"
            "                 rou_src='cologne1.rou.xml')"
        )
    if not rou_path.exists():
        raise FileNotFoundError(
            f"cologne1.rou.xml not found in {output_dir}.\n"
            "Copy it there manually or pass rou_src=<path> to build_cologne1()."
        )

    # Validate XML structure (fingerprint check)
    validate_cologne1(net_path, rou_path)
    print("[cologne_network] OK Validation passed")

    # Write SUMO config
    _write_sumo_config(cfg_path, net_path, rou_path)
    print(f"[cologne_network] Config written -> {cfg_path}")

    return net_path, rou_path


# Internal helpers

def _write_sumo_config(cfg_path: Path, net_path: Path, rou_path: Path) -> None:
    """Write a SUMO config spanning the real-world demand window."""
    xml = textwrap.dedent(f"""\
    <configuration>
      <input>
        <net-file value="{net_path.name}"/>
        <route-files value="{rou_path.name}"/>
      </input>
      <time>
        <begin value="{SIM_BEGIN}"/>
        <end value="{SIM_END}"/>
        <step-length value="{SIM_STEP}"/>
      </time>
      <report>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
      </report>
    </configuration>
    """)
    cfg_path.write_text(xml, encoding="utf-8")


# CLI (python -m pasa_itsc.network.cologne_network)

def _cli():
    import argparse
    parser = argparse.ArgumentParser(
        description="Set up Cologne1 real-world SUMO network"
    )
    parser.add_argument("--output-dir", default="data/net")
    parser.add_argument("--net-src",  help="Source cologne1.net.xml")
    parser.add_argument("--rou-src",  help="Source cologne1.rou.xml")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    build_cologne1(
        output_dir=args.output_dir,
        net_src=args.net_src,
        rou_src=args.rou_src,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    _cli()
