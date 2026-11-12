"""PROPOSED portable replacement for experiments/phase3b/finalize_deliverables.py (not applied).

Same semantics as the original (copy the three raw CSVs to the phase_3b_* deliverable names and
rewrite the results JSON with indent=2) but with a configurable destination instead of
C:\\Users\\bhoom\\Desktop\\ISC_PBL.

Usage: python finalize_deliverables_portable.py [--dest DIR] [--build-json FILE]
Defaults: --dest <repo>/isc_pbl ; --build-json <repo>/phase_3b_results_build.json
(the build JSON is not tracked on GitHub; supply it explicitly or use isc_pbl/phase_3b_results.json)
"""
import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2] if (HERE.parent.name == "proposed") else HERE.parents[1]
RAW = REPO / "experiments" / "phase3b" / "raw"

ap = argparse.ArgumentParser()
ap.add_argument("--dest", type=Path, default=REPO / "isc_pbl")
ap.add_argument("--build-json", type=Path, default=REPO / "phase_3b_results_build.json")
a = ap.parse_args()

a.dest.mkdir(parents=True, exist_ok=True)
for src, name in (("stage_a_lane_metrics.csv", "phase_3b_lane_metrics.csv"),
                  ("stage_a_cross_stream_metrics.csv", "phase_3b_cross_stream_metrics.csv"),
                  ("stage_b_burnin_comparison.csv", "phase_3b_burnin_comparison.csv")):
    shutil.copy(RAW / src, a.dest / name)

results = json.loads(a.build_json.read_text())
(a.dest / "phase_3b_results.json").write_text(json.dumps(results, indent=2, default=str))
print("copied deliverables to", a.dest)
