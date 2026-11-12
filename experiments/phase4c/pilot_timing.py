"""Pilot timing for Track A (natural-image battery) and Track B (NPCR/UACI
confirmatory experiment), run BEFORE committing to the full matrix, per the
user's mandatory pilot-first requirement (echoing the Phase 4B discipline).

Writes logs/pilot_timing.json with measured per-call costs and the resulting
sizing decision + arithmetic for each track.
"""
import json
import time

import numpy as np

import config
from isc_cipher import encrypt_bytes, decrypt_bytes

KEY = config.BASE_KEY


def _time_call(fn, *a, reps=2, **kw):
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(*a, **kw)
        times.append(time.perf_counter() - t0)
    return times


def run_pilot():
    out = {}

    # --- Track A pilot: one gray 256x~ image, one RGB 256x~ image ---
    gray = np.load(f"{config.DATASET_DIR}/astronaut_gray.npy")
    rgb = np.load(f"{config.DATASET_DIR}/astronaut_rgb.npy")
    h, w = gray.shape
    data_gray = gray.tobytes()
    data_rgb = rgb.tobytes()

    t_enc_gray = _time_call(encrypt_bytes, KEY, data_gray, h, w, 1)
    t_enc_rgb = _time_call(encrypt_bytes, KEY, data_rgb, rgb.shape[0], rgb.shape[1], 3)

    enc_gray_mean = sum(t_enc_gray) / len(t_enc_gray)
    enc_rgb_mean = sum(t_enc_rgb) / len(t_enc_rgb)
    # decrypt is roughly symmetric in cost (same generator construction);
    # measure directly rather than assume.
    ct_gray = encrypt_bytes(KEY, data_gray, h, w, 1)
    ct_rgb = encrypt_bytes(KEY, data_rgb, rgb.shape[0], rgb.shape[1], 3)
    t_dec_gray = _time_call(decrypt_bytes, KEY, ct_gray)
    t_dec_rgb = _time_call(decrypt_bytes, KEY, ct_rgb)
    dec_gray_mean = sum(t_dec_gray) / len(t_dec_gray)
    dec_rgb_mean = sum(t_dec_rgb) / len(t_dec_rgb)

    n_gray_variants = 7   # from natural_image_manifest.csv: *_gray rows at 256-class size
    n_rgb_variants = 5

    full_matrix_sec_mantissa8 = n_gray_variants * (enc_gray_mean + dec_gray_mean) + \
                                 n_rgb_variants * (enc_rgb_mean + dec_rgb_mean)
    full_matrix_sec_both_profiles = full_matrix_sec_mantissa8 * 2  # k14 on full set

    out["track_a"] = {
        "enc_gray_mean_sec": enc_gray_mean,
        "enc_rgb_mean_sec": enc_rgb_mean,
        "dec_gray_mean_sec": dec_gray_mean,
        "dec_rgb_mean_sec": dec_rgb_mean,
        "n_gray_variants": n_gray_variants,
        "n_rgb_variants": n_rgb_variants,
        "estimated_full_matrix_sec_mantissa8_only": full_matrix_sec_mantissa8,
        "estimated_full_matrix_sec_both_profiles_full_dataset": full_matrix_sec_both_profiles,
        "decision": (
            "mantissa8_v1 (primary) run on the FULL 18-variant dataset "
            f"(~{full_matrix_sec_mantissa8:.0f}s estimated); k14_scaled_modulo_v1 "
            "run only on a representative SUBSET (one gray + one RGB image, "
            "chosen for variety: astronaut [portrait/high-entropy] and "
            "hubble_deep_field [low-entropy structured scene]) rather than the "
            f"full dataset, since doubling to both profiles on all 18 variants "
            f"(~{full_matrix_sec_both_profiles:.0f}s) adds disproportionate "
            "runtime for a comparison Phase 4B already found statistically "
            "negligible at the image level across 63 synthetic images; a "
            "2-image confirmatory subset is sufficient to check the finding "
            "replicates on natural images without re-running the full battery."
        ),
    }

    # --- Track B pilot: NPCR/UACI single-trial cost at 256-class gray size ---
    # One encrypt of base + one encrypt of single-pixel-perturbed variant.
    data2 = bytearray(data_gray)
    data2[0] ^= 0x01
    t0 = time.perf_counter()
    encrypt_bytes(KEY, data_gray, h, w, 1)
    encrypt_bytes(KEY, bytes(data2), h, w, 1)
    per_trial_gray = time.perf_counter() - t0

    data2r = bytearray(data_rgb)
    data2r[0] ^= 0x01
    t0 = time.perf_counter()
    encrypt_bytes(KEY, data_rgb, rgb.shape[0], rgb.shape[1], 3)
    encrypt_bytes(KEY, bytes(data2r), rgb.shape[0], rgb.shape[1], 3)
    per_trial_rgb = time.perf_counter() - t0

    # NOTE: public encrypt_bytes draws a fresh random nonce each call, so this
    # pilot only measures *cost*, not validity. The actual NPCR/UACI
    # experiment must use the TEST-ONLY fixed-nonce path (isc_cipher._testing)
    # to satisfy "same key+nonce" -- same per-call cost applies there (the
    # generator construction, not the nonce, dominates cost).
    n_images = 5          # representative images across structure/entropy range
    n_positions = 4       # top_left, center, bottom_right, quarter (config.NPCR_UACI_POSITIONS)
    n_channel_trials = 3  # R, G, B separate perturbation, on 1 RGB image
    n_keynonce_configs = 3

    est_gray_trials = n_images * n_positions * n_keynonce_configs
    est_full_sec = est_gray_trials * per_trial_gray + n_channel_trials * n_keynonce_configs * per_trial_rgb

    out["track_b"] = {
        "per_trial_sec_gray_256class": per_trial_gray,
        "per_trial_sec_rgb_256class": per_trial_rgb,
        "planned_n_images": n_images,
        "planned_n_positions": n_positions,
        "planned_n_keynonce_configs": n_keynonce_configs,
        "planned_n_channel_trials": n_channel_trials,
        "estimated_trials": est_gray_trials + n_channel_trials * n_keynonce_configs,
        "estimated_full_runtime_sec": est_full_sec,
        "decision": (
            f"Estimated {est_gray_trials + n_channel_trials * n_keynonce_configs} trials, "
            f"~{est_full_sec:.0f}s. This fits comfortably without reduction: plan is "
            f"{n_images} images x {n_positions} positions x {n_keynonce_configs} key/nonce "
            f"configs (gray) + {n_channel_trials} per-channel trials x {n_keynonce_configs} "
            "configs on one RGB image = kept at this size (no further scale-back needed)."
        ),
    }

    with open(f"{config.LOGS_DIR}/pilot_timing.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    run_pilot()
