"""Experiment E: NPCR / UACI (plaintext differential sensitivity).

Validity rules enforced here:
 - same master key, same FIXED nonce (TEST-ONLY mechanism), same extraction profile for both
   images in every trial;
 - only the encrypted BODY bytes (via isc_cipher.container.parse) are compared, never header/
   nonce/tag;
 - a pilot timing run (see README.md "Pilot-based runtime decisions" / logs/pilot_timing.json)
   was used to size the trial matrix in config.py BEFORE this script was run at full scale.
"""

import csv
import json
import os
import time

import numpy as np

import config
from common import (encrypted_body, fixed_nonce_encrypt, npcr_uaci,
                     npcr_uaci_reference_expectation, PROFILE_NAMES)
from generate_dataset import GENERATORS

KEY = config.BASE_KEY
NONCE = config.BASE_NONCE


def flip_one_pixel(img, position):
    out = img.copy()
    flat = out.reshape(-1, out.shape[-1]) if out.ndim == 3 else out.reshape(-1, 1)
    n = flat.shape[0]
    idx = {"begin": 1, "middle": n // 2, "end": n - 2}[position]
    flat[idx, 0] = np.uint8((int(flat[idx, 0]) + 97) % 256)  # deterministic, non-zero-mod change
    return out.reshape(img.shape)


def flip_one_channel_pixel(img, channel_index, position="middle"):
    out = img.copy()
    h, w, c = out.shape
    flat = out.reshape(-1, c)
    n = flat.shape[0]
    idx = {"begin": 1, "middle": n // 2, "end": n - 2}[position]
    flat[idx, channel_index] = np.uint8((int(flat[idx, channel_index]) + 97) % 256)
    return out.reshape(img.shape)


def one_trial(img1, img2, size, c, extraction, label):
    data1, data2 = img1.tobytes(), img2.tobytes()
    assert data1 != data2, "trial constructed a no-op pixel change"
    ct1 = fixed_nonce_encrypt(KEY, data1, size, size, c, NONCE, extraction=extraction)
    ct2 = fixed_nonce_encrypt(KEY, data2, size, size, c, NONCE, extraction=extraction)
    body1, _ = encrypted_body(ct1)
    body2, _ = encrypted_body(ct2)
    stats = npcr_uaci(body1, body2)
    stats.update({"trial": label, "size": size, "channels": c, "extraction": PROFILE_NAMES[extraction]})
    return stats


def run():
    from isc_cipher.generator import EXTRACTION_K14_SCALED_MODULO_V1, EXTRACTION_MANTISSA8_V1
    t0 = time.time()
    rows = []

    # (1) grayscale sweep: full sizes x positions x image types, mantissa8_v1
    for size in config.NPCR_UACI_SIZES_GRAY:
        for img_type in config.NPCR_UACI_IMAGE_TYPES:
            base = GENERATORS[img_type](size, size, 1)
            for pos in config.NPCR_UACI_POSITIONS:
                img2 = flip_one_pixel(base, pos)
                rows.append(one_trial(base, img2, size, 1, EXTRACTION_MANTISSA8_V1,
                                       f"gray_{img_type}_{size}_{pos}"))

    # (2) reduced grayscale sweep at the larger size (positions only, 1 image type)
    size = config.NPCR_UACI_SIZE_GRAY_REDUCED
    for img_type in config.NPCR_UACI_IMAGE_TYPES_REDUCED:
        base = GENERATORS[img_type](size, size, 1)
        for pos in config.NPCR_UACI_POSITIONS:
            img2 = flip_one_pixel(base, pos)
            rows.append(one_trial(base, img2, size, 1, EXTRACTION_MANTISSA8_V1,
                                   f"gray_{img_type}_{size}_{pos}"))

    # (3) RGB channel-separate trials at the small size
    size = config.NPCR_UACI_RGB_SIZE
    base = GENERATORS["high_texture_random"](size, size, 3)
    for ci, cname in enumerate("RGB"):
        img2 = flip_one_channel_pixel(base, ci, "middle")
        rows.append(one_trial(base, img2, size, 3, EXTRACTION_MANTISSA8_V1,
                               f"rgb_channel_{cname}_{size}_middle"))

    # (4) reduced k14 profile subset for cross-profile comparison
    size = config.NPCR_UACI_SIZES_GRAY[0]
    img_type = config.NPCR_UACI_IMAGE_TYPES_REDUCED[0]
    base = GENERATORS[img_type](size, size, 1)
    for pos in config.NPCR_UACI_POSITIONS:
        img2 = flip_one_pixel(base, pos)
        rows.append(one_trial(base, img2, size, 1, EXTRACTION_K14_SCALED_MODULO_V1,
                               f"k14_gray_{img_type}_{size}_{pos}"))

    elapsed = time.time() - t0

    out = os.path.join(config.RESULTS_DIR, "experiment_E_npcr_uaci.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    npcr_vals = [r["npcr_pct"] for r in rows]
    uaci_vals = [r["uaci_pct"] for r in rows]
    ref = npcr_uaci_reference_expectation()
    summary = {
        "n_trials": len(rows), "elapsed_sec": elapsed,
        "npcr_pct": {"mean": float(np.mean(npcr_vals)), "std": float(np.std(npcr_vals)),
                     "min": float(np.min(npcr_vals)), "max": float(np.max(npcr_vals))},
        "uaci_pct": {"mean": float(np.mean(uaci_vals)), "std": float(np.std(uaci_vals)),
                     "min": float(np.min(uaci_vals)), "max": float(np.max(uaci_vals))},
        "reference_expectation_for_iid_uniform_bytes": ref,
        "note": "reference_expectation is a descriptive 'ideal random cipher' baseline (Wu/Noonan/Agaian "
                "closed-form), NOT a security threshold or proof.",
    }
    with open(os.path.join(config.RESULTS_DIR, "experiment_E_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"NPCR/UACI: {len(rows)} trials in {elapsed:.1f}s. "
          f"NPCR mean={summary['npcr_pct']['mean']:.3f}% (ref~{ref['npcr_expected_pct']:.3f}%), "
          f"UACI mean={summary['uaci_pct']['mean']:.3f}% (ref~{ref['uaci_expected_pct']:.3f}%)")
    return rows, summary


if __name__ == "__main__":
    run()
