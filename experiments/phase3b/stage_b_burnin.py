"""Stage B: burn-in sweep (1024 / 2048 / 5000 / 10000), both extraction profiles, seedA only.

Smaller sample size (BYTES_PER_LANE_BURNIN = 20,000 bytes/lane, per pilot_benchmark.py measured
throughput) to bound runtime for an 8-condition sweep (4 burn-ins x 2 extractions), per Section 4's
"use a smaller but consistent sample size if required by the pilot" -- this is a deliberate,
disclosed, fixed reduction from Stage A's 125,000 bytes/lane, applied identically to all 8
conditions (never changed silently mid-sweep). All 4 streams, all 64 lanes/stream used.
"""
import json
import time

import numpy as np

from common import (
    BYTES_PER_LANE_BURNIN, SEED_CONFIGS, get_seeds, generate, lane_subsequence,
    shannon_entropy_bytes, chisquare_uniform, acf_biased, STREAMS, bonferroni_bound,
)
from isc_cipher.generator import build_streams
from isc_cipher.state_map import seed_to_state
from isc_cipher.isc_step import step_vec

BURNINS = (1024, 2048, 5000, 10000)
RUN_LOG = []


def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line, flush=True)
    RUN_LOG.append(line)


def initial_condition_sensitivity(seed_label, extraction, burn_in, n_post_steps=200):
    """Section 3 item 8: for one lane per stream, compare output under the HKDF seed vs. the
    same seed with its lowest bit flipped, as a function of #steps past burn-in, for this T."""
    key, nonce = SEED_CONFIGS[seed_label]
    seeds = get_seeds(key, nonce)
    out = {}
    for g in STREAMS:
        seed0 = seeds[g][0]
        # state_map.seed_to_state computes alpha = BE64(seed[0:8]) >> 11, so the low 11 bits of
        # seed[0:8] are discarded entirely and have NO effect on x0; flipping byte[-1] (part of
        # seed[8:16], which only ever affects y0) was a test-authoring bug in an earlier version
        # of this script -- it left x0 bit-identical by construction, so divergence_onset was
        # always None. Flip bit 12 of the first 8 bytes (seed[0:8]) instead: this bit survives
        # the >>11 shift and changes alpha (hence x0) by exactly 1 ULP-of-alpha.
        s0_int = int.from_bytes(seed0[0:8], "big") ^ (1 << 12)
        seed_flipped = s0_int.to_bytes(8, "big") + seed0[8:16]

        x0, y0 = seed_to_state(seed0)
        x1, y1 = seed_to_state(seed_flipped)
        xs0 = np.array([x0]); ys0 = np.array([y0])
        xs1 = np.array([x1]); ys1 = np.array([y1])
        for _ in range(burn_in):
            xs0, ys0 = step_vec(xs0, ys0, 1)
            xs1, ys1 = step_vec(xs1, ys1, 1)
        divergence_onset = None
        hamming_at_step = []
        for step in range(n_post_steps):
            xs0, ys0 = step_vec(xs0, ys0, 1)
            xs1, ys1 = step_vec(xs1, ys1, 1)
            d = abs(float(xs0[0]) - float(xs1[0]))
            hamming_at_step.append(d)
            if divergence_onset is None and d > 1e-6:
                divergence_onset = step
        out[g] = {"divergence_onset_step": divergence_onset,
                  "final_abs_diff_x": hamming_at_step[-1] if hamming_at_step else None,
                  "initial_abs_diff_x": abs(x0 - x1)}
    return out


def main():
    rows = []
    initcond_rows = []
    for extraction in (1, 2):
        for T in BURNINS:
            t0 = time.perf_counter()
            log(f"generating extraction={extraction} burn_in={T} seed=seedA "
                f"({BYTES_PER_LANE_BURNIN} bytes/lane)")
            data = generate("seedA", extraction, burn_in=T, bytes_per_lane=BYTES_PER_LANE_BURNIN)
            dt = time.perf_counter() - t0
            log(f"  done in {dt:.1f}s")

            for g in STREAMS:
                arr = np.frombuffer(data[g], dtype=np.uint8)
                H, counts = shannon_entropy_bytes(arr)
                chi2, chi2_p = chisquare_uniform(counts)
                acf = acf_biased(arr.astype(np.float64), max_lag=100)
                # per-lane aggregate (mean entropy/chi2 across the stream's 64 lanes)
                lane_H = []
                lane_chi2 = []
                for l in range(64):
                    seq = lane_subsequence(data[g], l)
                    h_l, c_l = shannon_entropy_bytes(seq)
                    chi2_l, _ = chisquare_uniform(c_l)
                    lane_H.append(h_l)
                    lane_chi2.append(chi2_l)
                rows.append({
                    "extraction": extraction, "burn_in": T, "stream": g,
                    "generation_time_seconds": dt,
                    "stream_entropy_bits": H, "stream_chi2": chi2, "stream_chi2_p": chi2_p,
                    "stream_max_abs_acf_lag1_100": float(np.max(np.abs(acf))),
                    "lane_entropy_mean": float(np.mean(lane_H)), "lane_entropy_std": float(np.std(lane_H)),
                    "lane_entropy_min": float(np.min(lane_H)), "lane_entropy_max": float(np.max(lane_H)),
                    "lane_chi2_mean": float(np.mean(lane_chi2)), "lane_chi2_std": float(np.std(lane_chi2)),
                    "lane_chi2_min": float(np.min(lane_chi2)), "lane_chi2_max": float(np.max(lane_chi2)),
                })

            ic = initial_condition_sensitivity("seedA", extraction, T)
            for g, d in ic.items():
                initcond_rows.append({"extraction": extraction, "burn_in": T, "stream": g, **d})

    import pandas as pd
    pd.DataFrame(rows).to_csv("raw/stage_b_burnin_comparison.csv", index=False)
    pd.DataFrame(initcond_rows).to_csv("raw/stage_b_initial_condition_sensitivity.csv", index=False)
    with open("raw/stage_b_run_log.txt", "w") as f:
        f.write("\n".join(RUN_LOG))
    log("Stage B complete. Wrote raw/stage_b_burnin_comparison.csv, "
        "stage_b_initial_condition_sensitivity.csv, stage_b_run_log.txt")


if __name__ == "__main__":
    main()
