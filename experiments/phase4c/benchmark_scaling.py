"""Track C: clean end-to-end encrypt/decrypt scaling benchmark (full public
API calls only, no internal instrumentation) -- a confirmatory re-measurement
independent of Phase 4B's experiment_H, run in isolation (no other phase4c
script running concurrently).

Sizes limited to 64/128/256 gray (skips 512 and RGB): on this run's hardware
state, 256x256 RGB alone measured ~26s/encrypt in pilot_timing.py (see
README.md), so a full 512x512 RGB x REPS sweep here would cost several
minutes per size for marginal additional evidence beyond Phase 4B's
experiment_H (which already covered 64-512 at reps 3-7). This benchmark's
purpose is a smaller isolated CONFIRMATORY check, not a re-run of Phase 4B.
"""
import time

import numpy as np
import pandas as pd

import config
from isc_cipher import encrypt_bytes, decrypt_bytes

KEY = config.BASE_KEY
SIZES = [64, 128, 256]
REPS = {64: 5, 128: 5, 256: 3}
WARMUP = 1


def run():
    rows = []
    for size in SIZES:
        n = size * size
        data = (np.arange(n, dtype=np.uint32) % 256).astype(np.uint8).tobytes()
        reps = REPS[size]

        for _ in range(WARMUP):
            ct = encrypt_bytes(KEY, data, size, size, 1)
            decrypt_bytes(KEY, ct)

        enc_times, dec_times = [], []
        for _ in range(reps):
            t0 = time.perf_counter()
            ct = encrypt_bytes(KEY, data, size, size, 1)
            enc_times.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            decrypt_bytes(KEY, ct)
            dec_times.append(time.perf_counter() - t0)

        rows.append({
            "size": size, "n_bytes": n, "reps": reps,
            "enc_mean_sec": np.mean(enc_times), "enc_median_sec": np.median(enc_times),
            "enc_std_sec": np.std(enc_times), "enc_min_sec": np.min(enc_times), "enc_max_sec": np.max(enc_times),
            "dec_mean_sec": np.mean(dec_times), "dec_median_sec": np.median(dec_times),
            "dec_std_sec": np.std(dec_times), "dec_min_sec": np.min(dec_times), "dec_max_sec": np.max(dec_times),
            "enc_throughput_KBps": (n / 1000.0) / np.mean(enc_times),
            "dec_throughput_KBps": (n / 1000.0) / np.mean(dec_times),
        })
        print(f"size={size}: enc_mean={np.mean(enc_times):.3f}s dec_mean={np.mean(dec_times):.3f}s "
              f"throughput={(n/1000.0)/np.mean(enc_times):.2f} KB/s")

    df = pd.DataFrame(rows)
    df.to_csv(f"{config.RESULTS_DIR}/benchmark_scaling.csv", index=False)
    return df


if __name__ == "__main__":
    run()
