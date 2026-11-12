"""Experiment A: exact image recovery (round trip) across the synthetic dataset,
both extraction profiles, both backends, and a few explicit edge-case input shapes.
"""

import csv
import json
import os
import time

import numpy as np

import config
from common import PROFILE_NAMES, checksum
from generate_dataset import GENERATORS, build_dataset
from isc_cipher.cipher import decrypt_bytes, encrypt_bytes
from isc_cipher.errors import InvalidImage


def mae_mse_psnr(orig, dec):
    o = orig.astype(np.float64)
    d = dec.astype(np.float64)
    diff = o - d
    mae = float(np.mean(np.abs(diff)))
    mse = float(np.mean(diff ** 2))
    max_err = float(np.max(np.abs(diff))) if diff.size else 0.0
    n_diff = int(np.sum(o != d))
    if mse == 0:
        psnr = float("inf")
    else:
        psnr = float(10 * np.log10((255.0 ** 2) / mse))
    return mae, mse, max_err, n_diff, psnr


def run_recovery(images, backends=("numpy",), extractions=(1,)):
    from isc_cipher.generator import EXTRACTION_K14_SCALED_MODULO_V1, EXTRACTION_MANTISSA8_V1
    extraction_map = {1: EXTRACTION_MANTISSA8_V1, 2: EXTRACTION_K14_SCALED_MODULO_V1}
    rows = []
    key = config.BASE_KEY
    for (name, size, c), img in images.items():
        for backend in backends:
            for ext_code in extractions:
                extraction = extraction_map[ext_code]
                data = img.tobytes()
                h, w = size, size
                try:
                    ct = encrypt_bytes(key, data, h, w, c, backend=backend, extraction=extraction)
                    plain, hh, ww, cc = decrypt_bytes(key, ct, backend=backend)
                    dec_arr = np.frombuffer(plain, dtype=np.uint8).reshape(img.shape)
                    mae, mse, max_err, n_diff, psnr = mae_mse_psnr(img, dec_arr)
                    exact = (n_diff == 0) and (hh, ww, cc) == (h, w, c)
                    rows.append({
                        "image_id": f"{name}_{size}x{size}_c{c}", "backend": backend,
                        "extraction": PROFILE_NAMES[extraction], "dims_ok": (hh, ww, cc) == (h, w, c),
                        "exact_equality": exact, "mae": mae, "mse": mse, "max_abs_error": max_err,
                        "n_differing_elements": n_diff, "psnr_db": psnr, "error": "",
                    })
                except Exception as e:  # noqa: BLE001 -- recorded deliberately, never silently dropped
                    rows.append({
                        "image_id": f"{name}_{size}x{size}_c{c}", "backend": backend,
                        "extraction": PROFILE_NAMES[extraction], "dims_ok": False,
                        "exact_equality": False, "mae": "", "mse": "", "max_abs_error": "",
                        "n_differing_elements": "", "psnr_db": "", "error": f"{type(e).__name__}: {e}",
                    })
    return rows


def run_edge_case_shapes():
    """Explicit non-dataset edge cases: 1x1 image, non-contiguous array, dtype checks."""
    key = config.BASE_KEY
    results = []

    # 1x1 grayscale
    img = np.array([[200]], dtype=np.uint8)
    try:
        ct = encrypt_bytes(key, img.tobytes(), 1, 1, 1)
        plain, h, w, c = decrypt_bytes(key, ct)
        ok = plain == img.tobytes()
        results.append({"case": "1x1_grayscale", "supported": True, "exact": ok, "note": ""})
    except Exception as e:
        results.append({"case": "1x1_grayscale", "supported": False, "exact": False, "note": str(e)})

    # non-contiguous array (transpose view) via the image-level API, which explicitly
    # calls np.ascontiguousarray before tobytes() (isc_cipher/cipher.py:_image_to_bytes)
    from isc_cipher.cipher import encrypt, decrypt
    base = np.arange(64 * 64, dtype=np.uint8).reshape(64, 64)
    non_contig = base.T  # view, not contiguous
    assert not non_contig.flags["C_CONTIGUOUS"]
    try:
        ct = encrypt(key, non_contig)
        dec = decrypt(key, ct)
        ok = np.array_equal(dec, non_contig)
        results.append({"case": "non_contiguous_transpose_view", "supported": True, "exact": bool(ok), "note":
                         "encrypt() calls np.ascontiguousarray() internally, so a transposed view is accepted and correctly materialized before flattening"})
    except Exception as e:
        results.append({"case": "non_contiguous_transpose_view", "supported": False, "exact": False, "note": str(e)})

    # RGBA rejected
    rgba = np.zeros((16, 16, 4), dtype=np.uint8)
    try:
        encrypt(key, rgba)
        results.append({"case": "rgba_4channel", "supported": True, "exact": False, "note": "UNEXPECTED: RGBA was accepted"})
    except InvalidImage as e:
        results.append({"case": "rgba_4channel", "supported": False, "exact": False, "note": f"correctly rejected: {e}"})
    except Exception as e:
        results.append({"case": "rgba_4channel", "supported": False, "exact": False, "note": f"rejected with unexpected exception type {type(e).__name__}: {e}"})

    # non-uint8 dtype rejected
    img16 = np.zeros((8, 8), dtype=np.uint16)
    try:
        encrypt(key, img16)
        results.append({"case": "uint16_dtype", "supported": True, "exact": False, "note": "UNEXPECTED: non-uint8 dtype was accepted"})
    except InvalidImage as e:
        results.append({"case": "uint16_dtype", "supported": False, "exact": False, "note": f"correctly rejected: {e}"})
    except Exception as e:
        results.append({"case": "uint16_dtype", "supported": False, "exact": False, "note": f"rejected with unexpected exception type {type(e).__name__}: {e}"})

    # empty plaintext (h*w*c would be 0, structurally impossible via check_dims since h,w>=1 required
    # and the smallest valid n is 1); test via encrypt_bytes with h=w=c=0 is not meaningful, so instead
    # directly probe _validate_dims behavior through encrypt_bytes with 0-length data vs mismatched dims.
    try:
        encrypt_bytes(key, b"", 0, 0, 1)
        results.append({"case": "empty_plaintext_h0w0", "supported": True, "exact": False, "note": "UNEXPECTED: accepted"})
    except InvalidImage as e:
        results.append({"case": "empty_plaintext_h0w0", "supported": False, "exact": False, "note": f"correctly rejected (h,w>=1 required): {e}"})
    except Exception as e:
        results.append({"case": "empty_plaintext_h0w0", "supported": False, "exact": False, "note": f"rejected with unexpected exception type {type(e).__name__}: {e}"})

    return results


def run():
    t0 = time.time()
    images, _ = build_dataset(sizes=config.PRIMARY_SIZES)
    rows = run_recovery(images, backends=("numpy", "reference"), extractions=(1,))
    # profile 2 (k14) recovery check restricted to the numpy backend + the 256x256 subset for
    # time (P1 priority); k14 is NOT currently exercised on the reference backend in this phase.
    images_256 = {k: v for k, v in images.items() if k[1] == 256}
    rows += run_recovery(images_256, backends=("numpy",), extractions=(2,))
    edge_rows = run_edge_case_shapes()

    out_csv = os.path.join(config.RESULTS_DIR, "experiment_A_recovery.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    out_edge = os.path.join(config.RESULTS_DIR, "experiment_A_recovery_edgecases.csv")
    with open(out_edge, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(edge_rows[0].keys()))
        w.writeheader(); w.writerows(edge_rows)

    n_fail = sum(1 for r in rows if not r["exact_equality"])
    elapsed = time.time() - t0
    summary = {"n_trials": len(rows), "n_failures": n_fail, "elapsed_sec": elapsed,
               "edge_cases": edge_rows}
    with open(os.path.join(config.RESULTS_DIR, "experiment_A_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Recovery: {len(rows)} trials, {n_fail} failures, {elapsed:.1f}s")
    for r in edge_rows:
        print(" edge:", r["case"], "supported=" + str(r["supported"]), r["note"][:90])
    return rows, edge_rows


if __name__ == "__main__":
    run()
