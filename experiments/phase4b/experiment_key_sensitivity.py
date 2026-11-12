"""Experiment F: key sensitivity (one-bit key flip, fixed plaintext + fixed nonce)."""

import csv
import json
import os
import time

import numpy as np

import config
from common import encrypted_body, fixed_nonce_encrypt, flip_key_bit, hamming_distance_bits, npcr_uaci
from generate_dataset import GENERATORS

KEY = config.BASE_KEY
NONCE = config.BASE_NONCE


def one_trial(data, size, c, bit_index):
    key2 = flip_key_bit(KEY, bit_index)
    ct1 = fixed_nonce_encrypt(KEY, data, size, size, c, NONCE)
    ct2 = fixed_nonce_encrypt(key2, data, size, size, c, NONCE)
    body1, _ = encrypted_body(ct1)
    body2, _ = encrypted_body(ct2)
    stats = npcr_uaci(body1, body2)
    stats["hamming_bits"] = hamming_distance_bits(body1, body2)
    stats["hamming_frac"] = stats["hamming_bits"] / (8 * stats["n_bytes"])
    stats["bit_index"] = bit_index
    stats["size"] = size
    stats["channels"] = c
    return stats


def run():
    t0 = time.time()
    rows = []
    img_type = "high_texture_random"

    for size in config.KEY_SENS_SIZES_GRAY:
        data = GENERATORS[img_type](size, size, 1).tobytes()
        for bit in config.KEY_SENS_BIT_POSITIONS:
            rows.append(one_trial(data, size, 1, bit))

    size = config.KEY_SENS_SIZE_GRAY_REDUCED
    data = GENERATORS[img_type](size, size, 1).tobytes()
    for bit in config.KEY_SENS_BIT_POSITIONS_REDUCED:
        rows.append(one_trial(data, size, 1, bit))

    elapsed = time.time() - t0
    out = os.path.join(config.RESULTS_DIR, "experiment_F_key_sensitivity.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    npcr_vals = [r["npcr_pct"] for r in rows]
    uaci_vals = [r["uaci_pct"] for r in rows]
    hamming_frac = [r["hamming_frac"] for r in rows]
    summary = {
        "n_trials": len(rows), "elapsed_sec": elapsed,
        "npcr_pct": {"mean": float(np.mean(npcr_vals)), "std": float(np.std(npcr_vals))},
        "uaci_pct": {"mean": float(np.mean(uaci_vals)), "std": float(np.std(uaci_vals))},
        "hamming_frac": {"mean": float(np.mean(hamming_frac)), "std": float(np.std(hamming_frac)),
                          "ideal_random": 0.5},
    }
    with open(os.path.join(config.RESULTS_DIR, "experiment_F_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Key sensitivity: {len(rows)} trials in {elapsed:.1f}s. "
          f"NPCR mean={summary['npcr_pct']['mean']:.3f}%, UACI mean={summary['uaci_pct']['mean']:.3f}%, "
          f"Hamming-bit-fraction mean={summary['hamming_frac']['mean']:.4f} (ideal random=0.5)")
    return rows, summary


if __name__ == "__main__":
    run()
