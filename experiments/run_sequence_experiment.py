"""Run a reproducible ISC sequence-generation experiment.

Usage (from the project root):
    python experiments/run_sequence_experiment.py --config experiments/configs/default.json
    python experiments/run_sequence_experiment.py --config experiments/configs/quick.json

Outputs go to results/sequence_generation/<run_id>/; an existing run directory is never overwritten.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isc_seq.experiment import load_config, run_experiment  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="JSON config (missing keys fall back to isc_seq.experiment.DEFAULT_CONFIG)")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "sequence_generation"))
    ap.add_argument("--run-id", help="run directory name (default: <name>_<timestamp>)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_experiment(cfg, args.out, args.run_id, base_dir=ROOT)


if __name__ == "__main__":
    main()
