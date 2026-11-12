"""Experiment H: performance benchmarking (encrypt/decrypt time, throughput, scaling).

Per Section 12's "do not modify production cipher code to add instrumentation": phase
decomposition (key-derivation+generator vs transform vs container/auth) is obtained by calling
the existing internal functions (isc_cipher.cipher._materials, .kdf.Derivation, etc.) from
OUTSIDE the package -- i.e. by composing already-exposed internal entry points at the call site,
not by editing isc_cipher/*.py. This is still read-only against the package.
"""

import json
import os
import time

import numpy as np

import config
from generate_dataset import GENERATORS
from isc_cipher import container, diffusion, sampling
from isc_cipher.cipher import DEFAULT_BACKEND, _build_generators, _kcv, decrypt_bytes, encrypt_bytes
from isc_cipher.generator import EXTRACTION_MANTISSA8_V1
from isc_cipher.kdf import Derivation, NONCE_LEN, check_key, context
from isc_cipher.selftest import ensure_selftest

KEY = config.BASE_KEY


def timed_phases(key, data, h, w, c, nonce, profile=1, extraction=EXTRACTION_MANTISSA8_V1, backend="numpy"):
    """Reproduces isc_cipher.cipher._encrypt()'s stage sequence, with timers between stages,
    WITHOUT modifying any isc_cipher source. Returns (ciphertext, phase_times_dict)."""
    t = {}
    t0 = time.perf_counter()
    key_checked = check_key(key)
    ensure_selftest(profile, backend)
    t["selftest_and_keycheck"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    der = Derivation(key_checked, nonce, context(profile, container.DTYPE_UINT8, h, w, c, extraction=None))
    iv_f, iv_b = der.ivs()
    streams = _build_generators(der.seeds(), backend, profile, extraction)
    t["kdf_and_burnin"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    S, S_inv = sampling.build_sbox(streams["sbox"])
    pi = sampling.build_permutation(streams["perm"], h * w * c)
    a = streams["fwd"].take(h * w * c)
    b = streams["bwd"].take(h * w * c)
    t["sbox_perm_stream_build"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    q = sampling.apply_permutation(data, pi)
    u = diffusion.forward(q, a, S, iv_f)
    body = diffusion.backward(u, b, S, iv_b)
    t["permute_and_diffuse"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    kcv = _kcv(der.kcv_key(), streams)
    hdr = container.Header(profile=profile, c=c, h=h, w=w, nonce=bytes(nonce), kcv=kcv, version=1, extraction=extraction).pack()
    import hashlib, hmac
    tag = hmac.new(der.mac_key(), hdr + body, hashlib.sha256).digest()
    t["container_and_hmac"] = time.perf_counter() - t0

    return hdr + body + tag, t


def run():
    rows = []
    phase_rows = []
    for size in config.PERF_SIZES:
        reps = config.PERF_REPS[size]
        data = GENERATORS["high_texture_random"](size, size, 1).tobytes()
        enc_times, dec_times = [], []
        for i in range(config.PERF_WARMUP + reps):
            t0 = time.perf_counter()
            ct = encrypt_bytes(KEY, data, size, size, 1, backend=DEFAULT_BACKEND)
            t1 = time.perf_counter()
            _ = decrypt_bytes(KEY, ct, backend=DEFAULT_BACKEND)
            t2 = time.perf_counter()
            if i >= config.PERF_WARMUP:
                enc_times.append(t1 - t0)
                dec_times.append(t2 - t1)
        n_bytes = size * size
        rows.append({
            "size": size, "n_bytes": n_bytes, "reps": reps,
            "enc_mean_sec": float(np.mean(enc_times)), "enc_median_sec": float(np.median(enc_times)),
            "enc_std_sec": float(np.std(enc_times)), "enc_min_sec": float(np.min(enc_times)), "enc_max_sec": float(np.max(enc_times)),
            "dec_mean_sec": float(np.mean(dec_times)), "dec_median_sec": float(np.median(dec_times)),
            "dec_std_sec": float(np.std(dec_times)), "dec_min_sec": float(np.min(dec_times)), "dec_max_sec": float(np.max(dec_times)),
            "enc_throughput_MBps": float(n_bytes / np.mean(enc_times) / 1e6),
            "dec_throughput_MBps": float(n_bytes / np.mean(dec_times) / 1e6),
        })

        # phase decomposition, single rep per size (expensive to repeat; representative only)
        nonce = os.urandom(NONCE_LEN)
        _, phases = timed_phases(KEY, data, size, size, 1, nonce)
        phases["size"] = size
        phase_rows.append(phases)

    out_csv = os.path.join(config.RESULTS_DIR, "experiment_H_performance.csv")
    import csv
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(config.RESULTS_DIR, "experiment_H_phase_breakdown.json"), "w") as f:
        json.dump(phase_rows, f, indent=2)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sizes = [r["size"] for r in rows]
    enc_t = [r["enc_mean_sec"] for r in rows]
    dec_t = [r["dec_mean_sec"] for r in rows]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.plot(sizes, enc_t, "o-", label="encrypt (mean)")
    ax.plot(sizes, dec_t, "s-", label="decrypt (mean)")
    ax.set_xlabel("image edge length (pixels, square grayscale)")
    ax.set_ylabel("time (s)")
    ax.set_title("Phase 4B: encryption/decryption time vs. image size")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(config.PLOTS_DIR, "performance_scaling.png"), dpi=110)
    plt.close(fig)

    print("Performance:")
    for r in rows:
        print(f"  size={r['size']}: enc={r['enc_mean_sec']:.3f}s dec={r['dec_mean_sec']:.3f}s "
              f"enc_throughput={r['enc_throughput_MBps']:.3f} MB/s")
    return rows, phase_rows


if __name__ == "__main__":
    run()
