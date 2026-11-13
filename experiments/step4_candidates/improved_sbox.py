"""Step 4 candidate 2: Selection-based S-box construction.

Current approach: single Fisher-Yates shuffle → S-box. DDT max prob = 0.0469 (vs AES 0.0156).

Candidate: generate N S-box candidates from the same stream, select the one with the
lowest max differential probability. This uses more stream bytes but produces a stronger
S-box without changing the ISC map or the generation method — only the selection criterion.

Measures: DDT max prob, LAT max bias, and stream-byte cost for N = 1, 4, 8, 16, 32.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from isc_cipher.generator import build_streams
from isc_cipher.kdf import Derivation, context
from isc_cipher.sampling import build_sbox, WordSource, bounded


def ddt_max_prob(sbox):
    """Compute the maximum differential probability of an 8-bit S-box."""
    n = 256
    ddt = np.zeros((n, n), dtype=np.int32)
    s = np.array(sbox, dtype=np.int32)
    for dx in range(n):
        for x in range(n):
            dy = s[x] ^ s[x ^ dx]
            ddt[dx, dy] += 1
    # exclude the trivial row dx=0
    return float(ddt[1:].max()) / n


def lat_max_bias(sbox):
    """Compute the maximum linear approximation bias via vectorized Walsh-Hadamard."""
    n = 256
    s = np.array(sbox, dtype=np.uint8)

    # Precompute parity lookup: parity[v] = popcount(v) mod 2
    parity = np.array([bin(i).count("1") % 2 for i in range(n)], dtype=np.int32)

    # For each input mask a, compute the vector of a·x parities for all x
    # Then for each output mask b, compute b·S(x) parities, XOR, sum
    # lat[a,b] = sum_x (-1)^(parity(a&x) ^ parity(b&S(x)))

    xs = np.arange(n, dtype=np.uint8)
    sx = s[xs]  # S(x) for all x

    best = 0
    for a in range(n):
        ax_par = parity[a & xs]  # shape (256,)
        for b in range(n):
            if a == 0 and b == 0:
                continue
            bsx_par = parity[b & sx]  # shape (256,)
            val = abs(int(np.sum(1 - 2 * (ax_par ^ bsx_par))))
            if val > best:
                best = val
    return float(best) / n


def build_sbox_selected(stream, n_candidates):
    """Generate n_candidates S-boxes, return the one with the lowest DDT max prob."""
    best_s, best_inv, best_ddt = None, None, 1.0
    for _ in range(n_candidates):
        s, s_inv = build_sbox(stream)
        d = ddt_max_prob(s)
        if d < best_ddt:
            best_s, best_inv, best_ddt = s, s_inv, d
    return best_s, best_inv, best_ddt


def main():
    key = b"ab" * 32
    nonce = b"cd" * 8
    h, w, c = 256, 256, 3
    ctx = context(1, 0, h, w, c)
    der = Derivation(key, nonce, ctx)
    streams = build_streams(der.seeds(), backend="numpy", profile=1)

    results = []
    candidates_list = [1, 4, 8, 16, 32]

    for n_cand in candidates_list:
        print(f"  N={n_cand} candidates ...", end=" ", flush=True)
        # Fresh streams for each trial to ensure independence
        trial_nonce = bytearray(nonce); trial_nonce[0] ^= n_cand
        der2 = Derivation(key, bytes(trial_nonce), ctx)
        streams2 = build_streams(der2.seeds(), backend="numpy", profile=1)

        t0 = time.time()
        s, s_inv, best_ddt = build_sbox_selected(streams2["sbox"], n_cand)
        t1 = time.time()

        # Compute LAT only for the selected box (expensive)
        bias = lat_max_bias(s)

        consumed = streams2["sbox"].consumed
        row = {
            "n_candidates": n_cand,
            "ddt_max_prob": round(best_ddt, 6),
            "lat_max_bias": round(bias, 6),
            "stream_bytes_consumed": consumed,
            "wall_time_s": round(t1 - t0, 3),
            "aes_ddt_reference": 0.015625,
            "aes_lat_reference": 0.125,
        }
        results.append(row)
        print(f"DDT={best_ddt:.4f}  LAT={bias:.4f}  bytes={consumed}  time={t1-t0:.2f}s")

    # Also measure the current (N=1) baseline with the actual cipher key
    print("\n  Baseline (actual cipher S-box) ...", end=" ", flush=True)
    streams_base = build_streams(der.seeds(), backend="numpy", profile=1)
    s_base, s_inv_base = build_sbox(streams_base["sbox"])
    ddt_base = ddt_max_prob(s_base)
    lat_base = lat_max_bias(s_base)
    print(f"DDT={ddt_base:.4f}  LAT={lat_base:.4f}")
    results.append({
        "n_candidates": "baseline_actual",
        "ddt_max_prob": round(ddt_base, 6),
        "lat_max_bias": round(lat_base, 6),
        "note": "actual cipher S-box from the standard key/nonce",
    })

    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "sbox_selection.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
