"""Aggregate all raw CSVs into phase_3b_results.json and print the key summary numbers that go
into phase_3b_experiment_report.md / phase_3b_decision_log.md (written by hand from this output,
per the task's instruction not to fabricate or auto-write conclusions)."""
import json
import math

import numpy as np
import pandas as pd

from common import bonferroni_bound, BYTES_PER_LANE_PRIMARY

lane = pd.read_csv("raw/stage_a_lane_metrics.csv")
stream = pd.read_csv("raw/stage_a_stream_metrics.csv")
cross = pd.read_csv("raw/stage_a_cross_stream_metrics.csv")
nist_lane = pd.read_csv("raw/stage_a_nist_lane.csv")
nist_stream = pd.read_csv("raw/stage_a_nist_stream.csv")
coll = pd.read_csv("raw/stage_a_collision.csv")
burnin = pd.read_csv("raw/stage_b_burnin_comparison.csv")
initcond = pd.read_csv("raw/stage_b_initial_condition_sensitivity.csv")

with open("raw/stage_a_meta.json") as f:
    meta = json.load(f)

# recompute the correct Bonferroni bound (stage_a_primary.py had a units bug for the stored
# column, fixed in source post-hoc; recomputed here from the real sequence length instead of
# trusting the possibly-buggy stored value)
bonf_256_correct = bonferroni_bound(BYTES_PER_LANE_PRIMARY, 256)

summary = {"meta": meta, "bonferroni_bound_256tests_corrected": bonf_256_correct}

print("=" * 70)
print("REPRODUCIBILITY CHECK:", meta.get("reproducibility_check_byte_exact"))
print("=" * 70)

print("\n--- PER-LANE ENTROPY/CHI2, by extraction (all 256 lanes x 3 seeds = 768 rows/extraction) ---")
g = lane.groupby("extraction").agg(
    H_mean=("shannon_entropy_bits", "mean"), H_std=("shannon_entropy_bits", "std"),
    H_min=("shannon_entropy_bits", "min"), H_max=("shannon_entropy_bits", "max"),
    chi2p_mean=("chi2_p", "mean"),
    frac_chi2p_lt_05=("chi2_p", lambda s: float((s < 0.05).mean())),
    acf_mean=("max_abs_acf_lag1_100", "mean"), acf_max=("max_abs_acf_lag1_100", "max"),
    n_exceed_bonf=("max_abs_acf_lag1_100", lambda s: int((s > bonf_256_correct).sum())),
    n_lanes=("lane", "count"),
)
print(g)
summary["per_lane_by_extraction"] = g.reset_index().to_dict(orient="records")
summary["bonferroni_bound_used"] = bonf_256_correct

print("\n--- PER-STREAM ENTROPY/CHI2/ACF, by extraction and stream ---")
g2 = stream.groupby(["extraction", "stream"]).agg(
    H=("shannon_entropy_bits", "mean"), chi2_p=("chi2_p", "mean"),
    acf=("max_abs_acf_lag1_100", "mean"),
    within_round=("within_round_mean_abs_corr", "mean"),
    across_round=("across_round_boundary_corr", "mean"),
)
print(g2)
summary["per_stream_by_extraction"] = g2.reset_index().to_dict(orient="records")

print("\n--- CROSS-STREAM ADJUSTED MI, by extraction and pair (mean over 3 seeds) ---")
g3 = cross.groupby(["extraction", "stream_1", "stream_2"]).agg(
    adj_mi=("adjusted_mi_bits", "mean"), raw_mi=("raw_mi_bits", "mean"),
    perm_p=("perm_empirical_p", "mean"), shift_p=("shift_empirical_p", "mean"),
    perm_std=("perm_null_std_bits", "mean"),
)
print(g3)
summary["cross_stream_mi_by_extraction"] = g3.reset_index().to_dict(orient="records")

print("\n--- LANE COLLISION CHECK, min Hamming distance (256 bytes, 2016 pairs/stream) ---")
g4 = coll.groupby(["extraction", "stream"]).agg(
    min_hamming=("min_hamming_distance", "min"), dupes=("exact_duplicate_pairs", "sum"))
print(g4)
summary["collision_check"] = g4.reset_index().to_dict(orient="records")
# expected min hamming under a null random-byte model, for comparison (binomial argument)
n_pairs_per_stream = 64 * 63 // 2
expected_frac_identical_byte = 1 / 256
summary["collision_null_note"] = (
    f"Under an i.i.d.-random-byte null, P(two independent 256-byte strings share a given byte)"
    f"={expected_frac_identical_byte:.4f}; expected Hamming distance per pair ~ Binomial(256,255/256),"
    f" mean~{256*255/256:.1f}, std~{math.sqrt(256*(255/256)*(1/256)):.2f}. "
    f"{n_pairs_per_stream} pairs/stream/extraction/seed."
)

print("\n--- NIST LANE BATTERY (seedA, M=64 lanes), pass proportions ---")
g5 = nist_lane[nist_lane.seed == "seedA"].pivot_table(
    index="test", columns=["extraction", "stream"], values="proportion")
print(g5)
summary["nist_lane_seedA"] = nist_lane[nist_lane.seed == "seedA"].to_dict(orient="records")
summary["nist_lane_all_seeds"] = nist_lane.to_dict(orient="records")

print("\n--- NIST STREAM-CHUNK BATTERY (seedA, M=64 chunks), pass proportions ---")
g6 = nist_stream[nist_stream.seed == "seedA"].pivot_table(
    index="test", columns=["extraction", "stream"], values="proportion")
print(g6)
summary["nist_stream_seedA"] = nist_stream[nist_stream.seed == "seedA"].to_dict(orient="records")
summary["nist_stream_all_seeds"] = nist_stream.to_dict(orient="records")

print("\n--- BURN-IN SWEEP ---")
g7 = burnin.groupby(["extraction", "burn_in"]).agg(
    H=("lane_entropy_mean", "mean"), H_std=("lane_entropy_std", "mean"),
    chi2=("lane_chi2_mean", "mean"), t=("generation_time_seconds", "mean"))
print(g7)
summary["burnin_sweep"] = g7.reset_index().to_dict(orient="records")

print("\n--- INITIAL CONDITION SENSITIVITY (1-bit seed flip, divergence onset step) ---")
print(initcond.groupby(["extraction", "burn_in"]).agg(
    onset_mean=("divergence_onset_step", "mean"), onset_max=("divergence_onset_step", "max")))
summary["initial_condition_sensitivity"] = initcond.to_dict(orient="records")

with open("../../phase_3b_results_build.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)
print("\nwrote ../../phase_3b_results_build.json (intermediate; final phase_3b_results.json written by hand)")
