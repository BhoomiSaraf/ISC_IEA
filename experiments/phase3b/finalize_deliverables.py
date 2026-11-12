"""Copy/rename the raw CSVs into the exact deliverable filenames required by Section 8, in
ISC_PBL (where every other phase_2_*/phase_3a_* report already lives)."""
import json
import shutil

import pandas as pd

ISC_PBL = r"C:\Users\bhoom\Desktop\ISC_PBL"

shutil.copy("raw/stage_a_lane_metrics.csv", f"{ISC_PBL}\\phase_3b_lane_metrics.csv")
shutil.copy("raw/stage_a_cross_stream_metrics.csv", f"{ISC_PBL}\\phase_3b_cross_stream_metrics.csv")
shutil.copy("raw/stage_b_burnin_comparison.csv", f"{ISC_PBL}\\phase_3b_burnin_comparison.csv")

with open("../../phase_3b_results_build.json") as f:
    results = json.load(f)
with open(f"{ISC_PBL}\\phase_3b_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print("copied lane_metrics, cross_stream_metrics, burnin_comparison CSVs and results.json to", ISC_PBL)
