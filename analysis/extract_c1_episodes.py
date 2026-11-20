"""
Collect the per-episode records of the Cologne1 main sweep into one table.

Input : results_c1/<pattern>/all_results.json
Output: c1_episodes.csv  (pattern, controller, fault, seed, time_loss, n_trips, co2_g, cg_tpr, cg_fpr);
        used by analysis_revision.py, analyse_rev.py, figures_revision.py and the ITSC conf_stats.py

Usage: python extract_c1_episodes.py <results_c1 dir> <out csv>
"""
import sys, json
from pathlib import Path
import pandas as pd

COLS = ["time_loss", "n_trips", "co2_g", "cg_tpr", "cg_fpr"]


def main(root, out):
    rows = []
    for f in sorted(Path(root).glob("*/all_results.json")):
        d = json.loads(f.read_text())
        for ep in d["episodes"]:
            rows.append(dict(pattern=d.get("fault_pattern", f.parent.name), controller=ep["controller"],
                             fault=ep["fault_mode"], seed=ep["seed"], **{c: ep.get(c) for c in COLS}))
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    print(f"{len(df)} episodes -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
