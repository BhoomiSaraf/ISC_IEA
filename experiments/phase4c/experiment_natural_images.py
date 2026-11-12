"""Track A: natural-image correctness, entropy, histogram, correlation.

mantissa8_v1 runs on the FULL natural-image dataset (18 gray/rgb variants).
k14_scaled_modulo_v1 runs on a representative 2-image subset only (see
pilot_timing.py decision + README.md). All statistics are computed on the
ciphertext BODY bytes only (common.body_bytes strips header/nonce/KCV/tag).
"""
import time

import numpy as np
import pandas as pd
from scipy import stats as sps

import config
import common
from isc_cipher import encrypt_bytes, decrypt_bytes

KEY = config.BASE_KEY
K14_SUBSET = {"astronaut_gray", "hubble_deep_field_gray", "astronaut_rgb", "hubble_deep_field_rgb"}


def _run_one(image_id, arr, profile):
    h, w = arr.shape[0], arr.shape[1]
    c = arr.shape[2] if arr.ndim == 3 else 1
    data = np.ascontiguousarray(arr).tobytes()

    t0 = time.perf_counter()
    ct = encrypt_bytes(KEY, data, h, w, c, extraction=profile)
    t_enc = time.perf_counter() - t0
    t0 = time.perf_counter()
    rec, rh, rw, rc = decrypt_bytes(KEY, ct)
    t_dec = time.perf_counter() - t0

    exact = (rec == data) and (rh, rw, rc) == (h, w, c)
    body = common.body_bytes(ct)
    body_arr = np.frombuffer(body, dtype=np.uint8)

    orig_entropy = common.shannon_entropy(np.frombuffer(data, dtype=np.uint8))
    enc_entropy = common.shannon_entropy(body_arr)

    counts = np.bincount(body_arr, minlength=256)
    expected = len(body_arr) / 256.0
    chi2, pvalue = sps.chisquare(counts, f_exp=np.full(256, expected))

    # Correlation: reshape body bytes using original (h, w, c) for the
    # ciphertext-as-"image" comparison (explicitly NOT a decrypted/valid
    # image -- just the byte layout used for the correlation statistic,
    # matching what the plaintext layout would be).
    if len(body_arr) == h * w * c:
        body_img = body_arr.reshape(h, w, c) if c > 1 else body_arr.reshape(h, w)
        orig_img = arr
        corr_rows = []
        channels = range(c) if c > 1 else [None]
        for ch in channels:
            o = orig_img[..., ch] if ch is not None else orig_img
            e = body_img[..., ch] if ch is not None else body_img
            oh, ov, od = common.adjacent_correlation(o)
            eh, ev, ed = common.adjacent_correlation(e)
            corr_rows.append({
                "channel": ch if ch is not None else "gray",
                "orig_r_h": oh, "orig_r_v": ov, "orig_r_d": od,
                "enc_r_h": eh, "enc_r_v": ev, "enc_r_d": ed,
            })
    else:
        corr_rows = []  # should not happen; body length is always h*w*c

    return {
        "image_id": image_id, "profile": profile, "h": h, "w": w, "c": c,
        "n_bytes": h * w * c, "exact_recovery": exact,
        "enc_time_sec": t_enc, "dec_time_sec": t_dec,
        "orig_entropy": orig_entropy, "enc_entropy": enc_entropy,
        "chi2": chi2, "chi2_pvalue": pvalue,
        "expected_freq_per_bin": expected,
        "corr_rows": corr_rows,
    }


def run():
    manifest = pd.read_csv(f"{config.RESULTS_DIR}/natural_image_manifest.csv")
    main_rows, corr_rows, failures = [], [], []

    for _, row in manifest.iterrows():
        image_id = row["image_id"]
        arr = np.load(row["npy_path"])
        profiles = [config.PROFILE_MANTISSA8]
        if image_id in K14_SUBSET:
            profiles.append(config.PROFILE_K14)
        for profile in profiles:
            try:
                res = _run_one(image_id, arr, profile)
            except Exception as ex:  # noqa: BLE001 -- recorded, never hidden
                failures.append({"image_id": image_id, "profile": profile,
                                  "error": f"{type(ex).__name__}: {ex}"})
                continue
            for cr in res.pop("corr_rows"):
                cr.update({"image_id": image_id, "profile": profile})
                corr_rows.append(cr)
            main_rows.append(res)
            print(f"  {image_id:28s} profile={profile} exact={res['exact_recovery']} "
                  f"enc_entropy={res['enc_entropy']:.4f} chi2_p={res['chi2_pvalue']:.4f} "
                  f"t_enc={res['enc_time_sec']:.2f}s")

    df = pd.DataFrame(main_rows)
    df.to_csv(f"{config.RESULTS_DIR}/natural_image_results.csv", index=False)
    pd.DataFrame(corr_rows).to_csv(f"{config.RESULTS_DIR}/natural_image_correlation.csv", index=False)
    pd.DataFrame(failures).to_csv(f"{config.RESULTS_DIR}/natural_image_failures.csv", index=False)

    n_fail_exact = int((~df["exact_recovery"]).sum()) if len(df) else 0
    print(f"\n{len(df)} runs completed, {n_fail_exact} exact-recovery failures, {len(failures)} errored runs.")
    return df


if __name__ == "__main__":
    run()
