"""Comprehensive S-Box Redesign Benchmark and Cryptographic Metrics.

Evaluates:
1. Bijectivity
2. Differential Distribution Table (DDT) & max differential probability
3. Linear Approximation Table (LAT) & max linear bias
4. Minimum Nonlinearity (NL)
5. Number of Fixed Points (S[x] == x) and Opposite Fixed Points (S[x] == ~x & 0xFF)
6. Generation cost / stream bytes consumed
"""

import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath("."))
from isc_cipher.sampling import build_sbox
from isc_cipher.generator import build_streams
from isc_cipher.kdf import Derivation, context


# AES S-box table
AES_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5e, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]


def gf_inv(a):
    """Inversion in GF(2^8) modulo 0x11B."""
    if a == 0:
        return 0
    # a^254 in GF(2^8)
    res = 1
    base = a
    for _ in range(7):
        # square base
        p = 0
        b = base
        for _ in range(8):
            if b & 1: p ^= base
            hi = base & 0x80
            base = (base << 1) & 0xFF
            if hi: base ^= 0x1B
            b >>= 1
        base = p
        # mul res
        p = 0
        b = base
        r = res
        for _ in range(8):
            if b & 1: p ^= r
            hi = r & 0x80
            r = (r << 1) & 0xFF
            if hi: r ^= 0x1B
            b >>= 1
        res = p
    return res


def build_dynamic_galois_sbox(seed_c: int, seed_d: int):
    """Candidate S2: S(x) = (x ^ c)^(-1) ^ d in GF(2^8)."""
    s = [0] * 256
    for x in range(256):
        s[x] = gf_inv(x ^ seed_c) ^ seed_d
    return s


def compute_ddt_max(sbox):
    ddt = np.zeros((256, 256), dtype=np.int32)
    s = np.array(sbox, dtype=np.int32)
    for dx in range(1, 256):
        for x in range(256):
            dy = s[x] ^ s[x ^ dx]
            ddt[dx, dy] += 1
    return int(ddt[1:].max())


PARITY = np.array([bin(i).count("1") % 2 for i in range(256)], dtype=np.int8)

def compute_lat_max_and_nonlinearity(sbox):
    s = np.array(sbox, dtype=np.uint8)
    x = np.arange(256, dtype=np.uint8)
    
    # a_dot_x parity for all (a, x): shape (256, 256)
    # (-1)^(a . x): map 0 -> +1, 1 -> -1
    A = 1 - 2 * PARITY[np.bitwise_and.outer(np.arange(256), x)].astype(np.float32)
    # (-1)^(b . S(x)): shape (256, 256)
    B = 1 - 2 * PARITY[np.bitwise_and.outer(np.arange(256), s[x])].astype(np.float32)
    
    # LAT[a, b] = sum_x (-1)^(a.x) * (-1)^(b.S(x)) = (A @ B.T)[a, b]
    lat = A @ B.T
    lat[0, 0] = 0
    max_bias = int(np.abs(lat).max())
    nl = 128 - (max_bias // 2)
    return max_bias, nl


def analyze_sbox(sbox, name: str, cost_bytes: int):
    # Bijectivity
    is_bijective = len(set(sbox)) == 256
    # Fixed points: S[x] == x
    fixed_pts = sum(1 for x in range(256) if sbox[x] == x)
    # Opposite fixed points: S[x] == ~x & 0xFF
    opp_fixed_pts = sum(1 for x in range(256) if sbox[x] == (~x & 0xFF))

    max_ddt = compute_ddt_max(sbox)
    max_lat, nl = compute_lat_max_and_nonlinearity(sbox)

    return {
        "name": name,
        "is_bijective": is_bijective,
        "max_ddt_count": max_ddt,
        "max_ddt_prob": round(max_ddt / 256.0, 6),
        "max_lat_bias": round(max_lat / 256.0, 6),
        "min_nonlinearity": nl,
        "fixed_points": fixed_pts,
        "opposite_fixed_points": opp_fixed_pts,
        "stream_bytes_consumed": cost_bytes,
    }


def main():
    print("=== Benchmarking S-Box Architectures ===")
    key = b"ab" * 32
    nonce = b"cd" * 8
    ctx = context(1, 0, 256, 256, 3)
    der = Derivation(key, nonce, ctx)
    streams = build_streams(der.seeds(), backend="numpy", profile=1)

    results = []

    # 1. Baseline Fisher-Yates (N=1)
    s_base, _ = build_sbox(streams["sbox"])
    r_base = analyze_sbox(s_base, "Baseline Generated (Fisher-Yates N=1)", 1020)
    results.append(r_base)
    print(f"  {r_base['name']:38s}: DDT={r_base['max_ddt_prob']:.4f} | LAT={r_base['max_lat_bias']:.4f} | NL={r_base['min_nonlinearity']:3d} | Fixed={r_base['fixed_points']}")

    # 2. Selection-based Fisher-Yates (N=16)
    best_s, best_ddt = None, 256
    for _ in range(16):
        s_cand, _ = build_sbox(streams["sbox"])
        d = compute_ddt_max(s_cand)
        if d < best_ddt:
            best_ddt = d
            best_s = s_cand
    r_sel = analyze_sbox(best_s, "Candidate S1 (Selection N=16)", 16320)
    results.append(r_sel)
    print(f"  {r_sel['name']:38s}: DDT={r_sel['max_ddt_prob']:.4f} | LAT={r_sel['max_lat_bias']:.4f} | NL={r_sel['min_nonlinearity']:3d} | Fixed={r_sel['fixed_points']}")

    # 3. Dynamic Galois Inversion (Candidate S2)
    s_galois = build_dynamic_galois_sbox(0x3C, 0xA5)
    r_gal = analyze_sbox(s_galois, "Candidate S2 (Dynamic Galois Inversion)", 2)
    results.append(r_gal)
    print(f"  {r_gal['name']:38s}: DDT={r_gal['max_ddt_prob']:.4f} | LAT={r_gal['max_lat_bias']:.4f} | NL={r_gal['min_nonlinearity']:3d} | Fixed={r_gal['fixed_points']}")

    # 4. AES S-box (Fixed Control)
    r_aes = analyze_sbox(AES_SBOX, "AES S-box (Fixed Standard Control)", 0)
    results.append(r_aes)
    print(f"  {r_aes['name']:38s}: DDT={r_aes['max_ddt_prob']:.4f} | LAT={r_aes['max_lat_bias']:.4f} | NL={r_aes['min_nonlinearity']:3d} | Fixed={r_aes['fixed_points']}")

    out_file = "experiments/diffusion_study/results/sbox_study.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_file}")


if __name__ == "__main__":
    main()
