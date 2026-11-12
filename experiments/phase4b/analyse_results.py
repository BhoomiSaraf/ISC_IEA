"""Collects all Phase 4B result files into one JSON summary for the final report. Read-only
against the results already produced by the individual experiment_*.py scripts."""

import csv
import glob
import json
import os

import config


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    summary = {"results_dir": config.RESULTS_DIR, "files": {}}
    for path in sorted(glob.glob(os.path.join(config.RESULTS_DIR, "*.csv"))):
        rows = load_csv(path)
        summary["files"][os.path.basename(path)] = {"n_rows": len(rows)}
    for path in sorted(glob.glob(os.path.join(config.RESULTS_DIR, "*.json"))):
        if path.endswith("master_summary.json"):
            continue
        with open(path) as f:
            try:
                summary["files"][os.path.basename(path)] = json.load(f)
            except json.JSONDecodeError:
                summary["files"][os.path.basename(path)] = {"error": "could not parse"}
    out = os.path.join(config.RESULTS_DIR, "master_summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {out} covering {len(summary['files'])} result files.")


if __name__ == "__main__":
    main()
