"""Controlled Byte-Extraction Study on Identical ISC Trajectories.

Evaluates 4 candidate extraction methods on the exact same double-precision states:
1. mantissa8_v1: (bits 8..15 of Float64) - Baseline
2. k14_scaled_modulo_v1: floor(|v| * 10^14) mod 256
3. mantissa_mid_xor: (bits 16..23) ^ (bits 24..31)
4. uint64_folded_whitening: (u64 ^ (u64 >> 32) ^ (u64 >> 16)) & 0xFF
"""

import json
import math
import os
import struct
import sys
import time
import numpy as np
from scipy import stats

sys.path.insert(0, os.path.abspath("."))
from isc_seq.isc_map import isc_step


def extract_mantissa8(val: float) -> int:
    u = struct.unpack(">Q", struct.pack(">d", val))[0]
    return (u >> 8) & 0xFF


def extract_k14(val: float) -> int:
    return int(math.floor(abs(val) * 1e14)) % 256


def extract_mid_xor(val: float) -> int:
    u = struct.unpack(">Q", struct.pack(">d", val))[0]
    b1 = (u >> 16) & 0xFF
    b2 = (u >> 24) & 0xFF
    return b1 ^ b2


def extract_u64_fold(val: float) -> int:
    u = struct.unpack(">Q", struct.pack(">d", val))[0]
    folded = u ^ (u >> 32) ^ (u >> 16)
    return folded & 0xFF


def chi2_metrics(byte_arr):
    arr = np.array(byte_arr, dtype=np.uint8)
    n = len(arr)
    # Full byte chi2 (df = 255)
    counts = np.bincount(arr, minlength=256)
    exp = n / 256.0
    chi2_full = float(np.sum((counts - exp) ** 2 / exp))
    p_full = float(stats.chi2.sf(chi2_full, 255))

    # Low nibble chi2 (df = 15)
    lo_counts = np.bincount(arr & 0x0F, minlength=16)
    exp_nib = n / 16.0
    chi2_lo = float(np.sum((lo_counts - exp_nib) ** 2 / exp_nib))
    p_lo = float(stats.chi2.sf(chi2_lo, 15))

    # High nibble chi2 (df = 15)
    hi_counts = np.bincount((arr >> 4) & 0x0F, minlength=16)
    chi2_hi = float(np.sum((hi_counts - exp_nib) ** 2 / exp_nib))
    p_hi = float(stats.chi2.sf(chi2_hi, 15))

    # Lag-1 Autocorrelation
    centered = arr.astype(np.float64) - np.mean(arr)
    var = np.var(arr)
    autocorr = float(np.mean(centered[:-1] * centered[1:]) / var) if var > 0 else 0.0

    return {
        "chi2_full": round(chi2_full, 2),
        "p_full": p_full,
        "chi2_lo": round(chi2_lo, 2),
        "p_lo": p_lo,
        "chi2_hi": round(chi2_hi, 2),
        "p_hi": p_hi,
        "lag1_autocorr": round(autocorr, 6),
    }


def run_study():
    print("=== Generating 1,000,000 ISC Trajectory States ===")
    N_STATES = 1_000_000
    x = 0.123456789
    y = 0.987654321

    # Burn-in 1024
    for _ in range(1024):
        x, y = isc_step(x, y)

    # Harvest states
    states = []
    for _ in range(N_STATES):
        x, y = isc_step(x, y)
        states.append(x)

    extractors = {
        "mantissa8_v1 (Baseline)": extract_mantissa8,
        "k14_scaled_modulo_v1": extract_k14,
        "mantissa_mid_xor": extract_mid_xor,
        "u64_folded_whitening": extract_u64_fold,
    }

    results = {}
    print("\n=== Evaluating Extraction Candidates on Identical Trajectories ===")
    for name, fn in extractors.items():
        t0 = time.perf_counter()
        byte_data = [fn(v) for v in states]
        t1 = time.perf_counter()
        speed_mbps = (N_STATES / (1024 * 1024)) / (t1 - t0)

        metrics = chi2_metrics(byte_data)
        metrics["throughput_mbps"] = round(speed_mbps, 2)
        results[name] = metrics

        flag = " [ANOMALY DETECTED]" if metrics["p_lo"] < 0.001 else " [CLEAN]"
        print(f"  {name:26s}: Full chi2={metrics['chi2_full']:6.2f} (p={metrics['p_full']:.4f}) | "
              f"Lo-nib={metrics['chi2_lo']:5.2f} (p={metrics['p_lo']:.4f}){flag} | "
              f"Autocorr={metrics['lag1_autocorr']:+.5f} | {speed_mbps:5.2f} MB/s")

    out_file = "experiments/diffusion_study/results/extraction_study.json"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_file}")


if __name__ == "__main__":
    run_study()

