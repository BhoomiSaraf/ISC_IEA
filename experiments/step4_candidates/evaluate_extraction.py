"""Step 4 candidate 1: Validate k14_scaled_modulo_v1 under the v1 generator.

The Phase 3B chi-square investigation showed mantissa8_v1 has a low-nibble bias
(chi²(15) ≈ 63-91 vs expected 15) while k14 was clean — but that was tested on
the prior generator (G_prior). This script validates k14 under the actual v1
generator (HKDF-seeded, 64 lanes, burn_in=1024) used by the cipher.

Outputs: per-extraction chi-square statistics (full byte + nibble decomposition)
at multiple sample sizes, comparing mantissa8 vs k14 head-to-head.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
from scipy import stats

from isc_cipher.generator import (
    EXTRACTION_K14_SCALED_MODULO_V1,
    EXTRACTION_MANTISSA8_V1,
    build_streams,
)
from isc_cipher.kdf import Derivation, context, STREAMS


def generate_bytes(extraction, n_bytes, key=b"ab" * 32, nonce=b"cd" * 8):
    """Generate n_bytes from the sbox stream of the v1 generator."""
    h, w, c = 256, 256, 3  # typical image dims
    ctx = context(1, 0, h, w, c)
    der = Derivation(key, nonce, ctx)
    streams = build_streams(der.seeds(), backend="numpy", profile=1, extraction=extraction)
    return streams["sbox"].take(n_bytes)


def chi2_full(data):
    """Chi-square test on full bytes (df=255)."""
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
    expected = len(data) / 256.0
    chi2 = float(np.sum((counts - expected) ** 2 / expected))
    p = float(stats.chi2.sf(chi2, 255))
    return chi2, p


def chi2_nibble(data, which):
    """Chi-square on high (which='high') or low (which='low') nibble, df=15."""
    arr = np.frombuffer(data, dtype=np.uint8)
    if which == "high":
        nibbles = (arr >> 4) & 0x0F
    else:
        nibbles = arr & 0x0F
    counts = np.bincount(nibbles, minlength=16)
    expected = len(data) / 16.0
    chi2 = float(np.sum((counts - expected) ** 2 / expected))
    p = float(stats.chi2.sf(chi2, 15))
    return chi2, p


def main():
    sample_sizes = [125_000, 1_000_000, 8_000_000]
    results = []

    for extraction, name in [
        (EXTRACTION_MANTISSA8_V1, "mantissa8_v1"),
        (EXTRACTION_K14_SCALED_MODULO_V1, "k14_scaled_modulo_v1"),
    ]:
        for n in sample_sizes:
            print(f"  {name}, n={n:,} ...", end=" ", flush=True)
            data = generate_bytes(extraction, n)
            full_chi2, full_p = chi2_full(data)
            hi_chi2, hi_p = chi2_nibble(data, "high")
            lo_chi2, lo_p = chi2_nibble(data, "low")
            row = {
                "extraction": name,
                "n_bytes": n,
                "full_byte_chi2": round(full_chi2, 2),
                "full_byte_p": full_p,
                "high_nibble_chi2": round(hi_chi2, 2),
                "high_nibble_p": hi_p,
                "low_nibble_chi2": round(lo_chi2, 2),
                "low_nibble_p": lo_p,
            }
            results.append(row)
            flag = " *** ANOMALY" if lo_p < 0.001 else ""
            print(f"full={full_chi2:.1f} (p={full_p:.4f})  lo_nib={lo_chi2:.1f} (p={lo_p:.4f}){flag}")

    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "extraction_validation.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
