"""
Collect the per-episode records of the revision sweeps into one table.

Input : results_rev/<set>/.../all_results.json   (one file per set x profile x demand x pattern)
Output: rev_episodes.csv                          (one row per episode; used by analyse_rev.py,
                                                   figures_revision.py and the ITSC conf_stats.py)

The set name is the first folder below results_rev. Cologne1 runs get demand = "c1".
total_delay_vh = time_loss * n_trips / 3600 (network total delay, vehicle-hours).

Usage: python extract_rev_episodes.py <results_rev dir> <out csv>
"""
import sys, json
from pathlib import Path
import pandas as pd


def main(root, out):
    root = Path(root); rows = []
    for f in sorted(root.rglob("all_results.json")):
        d = json.loads(f.read_text())
        s = f.relative_to(root).parts[0]
        c1 = d.get("network") == "cologne1"
        for ep in d["episodes"]:
            r = dict(ep)
            r.update(set=s, profile=d.get("demand_profile"),
                     demand="c1" if c1 else d.get("demand_level"), pattern=d.get("fault_pattern"))
            rows.append(r)
    df = pd.DataFrame(rows)
    df = df.drop(columns=["delay_by_side"], errors="ignore")   # nested dict; per-side delay is not used from this table
    df["total_delay_vh"] = df.time_loss * df.n_trips / 3600
    df.to_csv(out, index=False)
    print(f"{len(df)} episodes from {df.set.nunique()} sets -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
