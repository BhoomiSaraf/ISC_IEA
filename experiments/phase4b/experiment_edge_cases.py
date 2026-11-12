"""Experiment I: structural edge cases and plaintext-structure-leakage investigation.

Shape/dtype edge cases (1x1, non-contiguous, RGBA, uint16, empty) are already covered by
experiment_recovery.py's run_edge_case_shapes() to avoid duplicating that work; this script
covers:
 - very small but non-trivial dimensions (2x2, 3x3, 5x5),
 - whether highly-structured plaintext (all-zero, uniform, checkerboard, repeated-pattern)
   leaves any visible trace in the ciphertext BODY's histogram/entropy/adjacent-correlation,
   compared against a high-entropy random baseline of the same size.
"""

import csv
import json
import os

import numpy as np

import config
from common import adjacent_pixel_correlation, chi_square_256, encrypted_body, shannon_entropy
from isc_cipher.cipher import decrypt_bytes, encrypt_bytes

KEY = config.BASE_KEY


def run_small_dims():
    rows = []
    for h, w, c in [(2, 2, 1), (3, 3, 1), (5, 5, 1), (2, 2, 3), (3, 3, 3)]:
        rng = np.random.default_rng(config.MASTER_SEED + h * 1000 + w * 10 + c)
        img = rng.integers(0, 256, size=(h, w) if c == 1 else (h, w, c), dtype=np.uint8)
        try:
            ct = encrypt_bytes(KEY, img.tobytes(), h, w, c)
            plain, hh, ww, cc = decrypt_bytes(KEY, ct)
            exact = plain == img.tobytes()
            rows.append({"dims": f"{h}x{w}x{c}", "supported": True, "exact": exact, "note": ""})
        except Exception as e:
            rows.append({"dims": f"{h}x{w}x{c}", "supported": False, "exact": False, "note": f"{type(e).__name__}: {e}"})
    return rows


def run_structure_leakage():
    from generate_dataset import GENERATORS
    size = 128
    rows = []
    structured_types = ["all_zero", "all_255", "uniform_gray127", "checkerboard", "low_entropy", "binary_bw"]
    baseline_body = None
    for name in structured_types + ["high_texture_random"]:
        img = GENERATORS[name](size, size, 1)
        ct = encrypt_bytes(KEY, img.tobytes(), size, size, 1)
        body, _ = encrypted_body(ct)
        ent = shannon_entropy(body)
        chi2, p = chi_square_256(body)
        body_img = np.frombuffer(body, dtype=np.uint8).reshape(size, size)
        corr = adjacent_pixel_correlation(body_img)
        row = {
            "image_type": name, "encrypted_entropy": ent, "encrypted_chi2": chi2, "encrypted_chi2_pvalue": p,
            "encrypted_corr_horizontal": corr["horizontal"]["r"], "encrypted_corr_vertical": corr["vertical"]["r"],
            "encrypted_corr_diagonal": corr["diagonal"]["r"],
        }
        rows.append(row)
        if name == "high_texture_random":
            baseline_body = row
    # relative comparison column: how far each structured image's encrypted stats deviate from
    # the random-plaintext baseline encrypted under the same cipher
    for row in rows:
        row["entropy_delta_from_random_baseline"] = row["encrypted_entropy"] - baseline_body["encrypted_entropy"]
        row["chi2_delta_from_random_baseline"] = row["encrypted_chi2"] - baseline_body["encrypted_chi2"]
    return rows


def run():
    small = run_small_dims()
    leak = run_structure_leakage()
    with open(os.path.join(config.RESULTS_DIR, "experiment_I_small_dims.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(small[0].keys()))
        w.writeheader(); w.writerows(small)
    with open(os.path.join(config.RESULTS_DIR, "experiment_I_structure_leakage.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(leak[0].keys()))
        w.writeheader(); w.writerows(leak)
    print(f"Edge cases: {len(small)} small-dim trials, {len(leak)} structure-leakage rows.")
    for r in small:
        print(" dims:", r)
    for r in leak:
        print(" leak:", r["image_type"], "entropy_delta=%.5f" % r["entropy_delta_from_random_baseline"],
              "chi2_delta=%.3f" % r["chi2_delta_from_random_baseline"])
    return small, leak


if __name__ == "__main__":
    run()
