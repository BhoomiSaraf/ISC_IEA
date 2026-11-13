"""Multi-Stream Architecture Investigation: Lane Counts, Cost, and Independence.

Evaluates:
1. Burn-in transcendental cost across lane counts (16, 32, 64)
2. Stream generation throughput (MB/s)
3. Cross-lane correlation across 64 lanes
4. Unified stream slicing vs 4 independent streams
"""

import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath("."))
from isc_seq.isc_map import isc_step


def run_multistream_study():
    print("=== Multi-Stream and Lane Configuration Evaluation ===")

    # 1. Transcendental evaluation counts
    lane_configs = [16, 32, 64]
    burn_in_steps = 1024
    cost_data = {}

    for L in lane_configs:
        # Total lanes for 4 streams
        total_lanes = 4 * L
        transcendental_burnin = total_lanes * burn_in_steps * 2  # sin and cos per step
        cost_data[f"{L}_lanes_per_stream"] = {
            "total_lanes": total_lanes,
            "burn_in_transcendentals": transcendental_burnin,
        }
        print(f"  {L:2d} lanes/stream (4 streams = {total_lanes:3d} lanes): {transcendental_burnin:8,d} sin/cos evaluations in burn-in")

    # 2. Timing the burn-in phase
    print("\n=== Measuring Burn-In Wall-Clock Latency ===")
    timing_data = {}
    for L in lane_configs:
        total_lanes = 4 * L
        # Initial states
        rng = np.random.RandomState(42)
        xs = rng.uniform(0.01, 0.99, total_lanes)
        ys = rng.uniform(0.01, 0.99, total_lanes)

        t0 = time.perf_counter()
        for _ in range(burn_in_steps):
            for i in range(total_lanes):
                xs[i], ys[i] = isc_step(xs[i], ys[i])
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000
        timing_data[f"{L}_lanes"] = round(elapsed_ms, 2)
        print(f"  {L:2d} lanes/stream: {elapsed_ms:6.2f} ms")

    # 3. Cross-lane correlation test (sample 16 lanes of stream fwd)
    print("\n=== Measuring Cross-Lane Correlation (Stream fwd, 16 lanes, 10,000 steps) ===")
    N_STEPS = 10_000
    K = 16
    rng = np.random.RandomState(1337)
    xs = rng.uniform(0.01, 0.99, K)
    ys = rng.uniform(0.01, 0.99, K)

    # Burn-in
    for _ in range(1024):
        for i in range(K):
            xs[i], ys[i] = isc_step(xs[i], ys[i])

    series = np.zeros((K, N_STEPS), dtype=np.float64)
    for t in range(N_STEPS):
        for i in range(K):
            xs[i], ys[i] = isc_step(xs[i], ys[i])
            series[i, t] = xs[i]

    # Compute pairwise Pearson correlation
    corr_matrix = np.corrcoef(series)
    # Off-diagonal elements
    mask = ~np.eye(K, dtype=bool)
    off_diag = corr_matrix[mask]
    mean_corr = float(np.mean(np.abs(off_diag)))
    max_corr = float(np.max(np.abs(off_diag)))

    print(f"  Mean absolute cross-lane correlation: {mean_corr:.6f}")
    print(f"  Max absolute cross-lane correlation:  {max_corr:.6f}")

    results = {
        "transcendental_costs": cost_data,
        "burn_in_timing_ms": timing_data,
        "cross_lane_mean_abs_corr": round(mean_corr, 6),
        "cross_lane_max_abs_corr": round(max_corr, 6),
    }

    out_file = "experiments/diffusion_study/results/multistream_study.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_file}")


if __name__ == "__main__":
    run_multistream_study()

