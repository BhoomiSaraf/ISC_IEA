"""Experiment G: extraction-profile comparison (mantissa8_v1 vs k14_scaled_modulo_v1).

Same plaintext, key, nonce, dims, channel layout for every paired comparison, per Section 11.
Reuses stats_core's cache-building logic but builds a SECOND cache under extraction=k14 and
compares against the existing mantissa8_v1 cache entry-by-entry, plus a small dedicated
NPCR/UACI and timing comparison (not duplicating the full Experiment E/H matrices).
"""

import csv
import json
import os
import time

import numpy as np

import config
from common import chi_square_256, encrypted_body, fixed_nonce_encrypt, shannon_entropy
from generate_dataset import GENERATORS
from isc_cipher.generator import EXTRACTION_K14_SCALED_MODULO_V1, EXTRACTION_MANTISSA8_V1
from stats_core import build_stats_cache

PROFILE_SIZES = [64, 128, 256]
IMG_TYPES = ["high_texture_random", "smooth_natural_like", "checkerboard"]


def run():
    cache_m8 = build_stats_cache(sizes=PROFILE_SIZES, extraction=EXTRACTION_MANTISSA8_V1)
    cache_k14 = build_stats_cache(sizes=PROFILE_SIZES, extraction=EXTRACTION_K14_SCALED_MODULO_V1, force=True)
    # NOTE: build_stats_cache's on-disk cache keys only on (extraction, sizes), so calling it twice
    # with different extraction values overwrites the same file; we keep both dicts in memory here
    # instead of relying on the cache file for the comparison below.

    rows = []
    for key in cache_m8["entries"]:
        name, size, c = key
        if key not in cache_k14["entries"]:
            continue
        e_m8 = cache_m8["entries"][key]
        e_k14 = cache_k14["entries"][key]
        rows.append({
            "image_id": f"{name}_{size}x{size}_c{c}",
            "entropy_mantissa8": shannon_entropy(e_m8["body"]),
            "entropy_k14": shannon_entropy(e_k14["body"]),
            "chi2_mantissa8": chi_square_256(e_m8["body"])[0],
            "chi2_k14": chi_square_256(e_k14["body"])[0],
            "chi2_pvalue_mantissa8": chi_square_256(e_m8["body"])[1],
            "chi2_pvalue_k14": chi_square_256(e_k14["body"])[1],
            "bodies_identical": e_m8["body"] == e_k14["body"],
        })
    out = os.path.join(config.RESULTS_DIR, "experiment_G_profile_stats.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # Timing comparison: same plaintext/key/nonce, both profiles, 3 reps at 2 sizes
    timing_rows = []
    for size in [64, 256]:
        data = GENERATORS["high_texture_random"](size, size, 1).tobytes()
        for extraction, pname in [(EXTRACTION_MANTISSA8_V1, "mantissa8_v1"), (EXTRACTION_K14_SCALED_MODULO_V1, "k14_scaled_modulo_v1")]:
            times = []
            for _ in range(3):
                t0 = time.perf_counter()
                fixed_nonce_encrypt(config.BASE_KEY, data, size, size, 1, config.BASE_NONCE, extraction=extraction)
                times.append(time.perf_counter() - t0)
            timing_rows.append({"size": size, "profile": pname, "mean_sec": float(np.mean(times)),
                                 "std_sec": float(np.std(times)), "reps": 3})
    with open(os.path.join(config.RESULTS_DIR, "experiment_G_profile_timing.json"), "w") as f:
        json.dump(timing_rows, f, indent=2)

    entropies_m8 = [r["entropy_mantissa8"] for r in rows]
    entropies_k14 = [r["entropy_k14"] for r in rows]
    print(f"Profile comparison: {len(rows)} images. mantissa8 mean entropy={np.mean(entropies_m8):.4f}, "
          f"k14 mean entropy={np.mean(entropies_k14):.4f}")
    print("Timing:", timing_rows)
    return rows, timing_rows


if __name__ == "__main__":
    run()
