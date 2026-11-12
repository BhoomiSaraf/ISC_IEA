"""Track B: NPCR/UACI confirmatory experiment on natural images, using the
TEST-ONLY fixed-nonce path (same key+nonce required for a valid plaintext-
differential comparison; the public API always draws a fresh random nonce
and cannot be used here).

Trial budget: see config.py's documented scale-back from the pilot
measurement in logs/pilot_timing.json (21 trials total: 18 gray + 3 rgb).
"""
import numpy as np
import pandas as pd

import config
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY as enc_fixed
import common

KEY = config.BASE_KEY


def _keynonce(idx):
    # Deterministic, distinct (key, nonce) pairs per configuration index.
    key = bytes((KEY[i] ^ (idx * 7 + i)) % 256 for i in range(32))
    nonce = bytes((config.BASE_NONCE[i] ^ (idx * 11 + i)) % 256 for i in range(16))
    return key, nonce


def _npcr_uaci(body1: bytes, body2: bytes):
    a = np.frombuffer(body1, dtype=np.uint8).astype(np.int32)
    b = np.frombuffer(body2, dtype=np.uint8).astype(np.int32)
    diff = a != b
    npcr = 100.0 * diff.sum() / len(a)
    uaci = 100.0 * np.abs(a - b).sum() / (255.0 * len(a))
    hamming_bits = int(np.unpackbits((a ^ b).astype(np.uint8)).sum())
    return npcr, uaci, int(diff.sum()), len(a), hamming_bits


def _flip_pixel(arr, h, w, c, position, channel=None):
    arr2 = arr.copy()
    if position == "top_left":
        yx = (0, 0)
    elif position == "center":
        yx = (h // 2, w // 2)
    elif position == "bottom_right":
        yx = (h - 1, w - 1)
    else:
        raise ValueError(position)
    if c > 1:
        ch = channel if channel is not None else 0
        arr2[yx[0], yx[1], ch] = (int(arr2[yx[0], yx[1], ch]) + 1) % 256
    else:
        arr2[yx[0], yx[1]] = (int(arr2[yx[0], yx[1]]) + 1) % 256
    return arr2


def run():
    rows = []

    # --- Gray trials ---
    for image_id in config.NPCR_UACI_IMAGES_GRAY:
        arr = np.load(f"{config.DATASET_DIR}/{image_id}.npy")
        h, w = arr.shape[0], arr.shape[1]
        for pos in config.NPCR_UACI_POSITIONS:
            arr2 = _flip_pixel(arr, h, w, 1, pos)
            for kn_idx in range(config.NPCR_UACI_KEYNONCE_CONFIGS_GRAY):
                key, nonce = _keynonce(kn_idx)
                ct1 = enc_fixed(key, arr.tobytes(), h, w, 1, nonce)
                ct2 = enc_fixed(key, arr2.tobytes(), h, w, 1, nonce)
                npcr, uaci, nchg, ntot, hamming = _npcr_uaci(
                    common.body_bytes(ct1), common.body_bytes(ct2))
                rows.append({
                    "track": "plaintext_diff_gray", "image_id": image_id, "channel": "gray",
                    "position": pos, "keynonce_config": kn_idx, "n_bytes_changed": nchg,
                    "n_bytes_total": ntot, "npcr_pct": npcr, "uaci_pct": uaci,
                    "hamming_bits": hamming, "hamming_frac": hamming / (8 * ntot),
                })
                print(f"  gray {image_id} pos={pos} kn={kn_idx} NPCR={npcr:.4f} UACI={uaci:.4f}")

    # --- RGB per-channel trials ---
    rgb_id = config.NPCR_UACI_RGB_IMAGE
    arr = np.load(f"{config.DATASET_DIR}/{rgb_id}.npy")
    h, w = arr.shape[0], arr.shape[1]
    for ch in range(3):
        arr2 = _flip_pixel(arr, h, w, 3, "center", channel=ch)
        for kn_idx in range(config.NPCR_UACI_KEYNONCE_CONFIGS_RGB):
            key, nonce = _keynonce(100 + kn_idx)
            ct1 = enc_fixed(key, arr.tobytes(), h, w, 3, nonce)
            ct2 = enc_fixed(key, arr2.tobytes(), h, w, 3, nonce)
            npcr, uaci, nchg, ntot, hamming = _npcr_uaci(
                common.body_bytes(ct1), common.body_bytes(ct2))
            rows.append({
                "track": "plaintext_diff_rgb_channel", "image_id": rgb_id,
                "channel": ["R", "G", "B"][ch], "position": "center",
                "keynonce_config": kn_idx, "n_bytes_changed": nchg, "n_bytes_total": ntot,
                "npcr_pct": npcr, "uaci_pct": uaci, "hamming_bits": hamming,
                "hamming_frac": hamming / (8 * ntot),
            })
            print(f"  rgb {rgb_id} ch={['R','G','B'][ch]} kn={kn_idx} NPCR={npcr:.4f} UACI={uaci:.4f}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{config.RESULTS_DIR}/npcr_uaci_natural.csv", index=False)
    print(f"\n{len(df)} NPCR/UACI trials completed.")
    return df


if __name__ == "__main__":
    run()
