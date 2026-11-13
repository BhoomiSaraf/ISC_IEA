"""Step 5: Controlled experiments — run all baselines on the same metrics.

Baselines:
  ISC-IMG v1 (mantissa8) — the production cipher
  ISC-IMG v2 (k14)       — extraction switch only
  V-CHACHA               — ChaCha20 replaces ISC generator, same envelope
  V-STREAM-ISC           — ISC XOR stream only, no envelope
  AES-256-GCM            — established AEAD reference
  ChaCha20-Poly1305      — established AEAD reference

Metrics (on the same 256x256 grayscale test image):
  1. Ciphertext statistics: entropy, chi-square, horizontal/vertical/diagonal correlation
  2. NPCR / UACI (sensitivity to one-pixel change)
  3. S-box quality: DDT max prob, LAT max bias (where applicable)
  4. Diffusion propagation (where applicable)
  5. Runtime (encrypt + decrypt cycle)
"""

import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from isc_cipher.cipher import encrypt_bytes, decrypt_bytes
from isc_cipher.cipher import _materials
from isc_cipher import diffusion, sampling, container
from isc_cipher.generator import (
    EXTRACTION_MANTISSA8_V1, EXTRACTION_K14_SCALED_MODULO_V1,
    build_streams,
)
from isc_cipher.kdf import Derivation, context, NONCE_LEN

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305

from baselines import (
    v_chacha_encrypt, v_chacha_materials,
    v_stream_isc_encrypt,
)


KEY = b"ab" * 16
NONCE = b"cd" * 8
H, W, C = 256, 256, 1
N = H * W * C


def make_test_image(seed=42):
    rng = np.random.RandomState(seed)
    return rng.randint(0, 256, N, dtype=np.uint8)


# ---- Ciphertext statistics ----

def entropy(data):
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
    p = counts / len(data)
    p = p[p > 0]
    return -float(np.sum(p * np.log2(p)))


def chi_square(data):
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
    expected = len(data) / 256
    return float(np.sum((counts - expected) ** 2 / expected))


def correlation(data, h, w, direction="horizontal"):
    """Correlation coefficient between adjacent pixels."""
    img = np.frombuffer(data, dtype=np.uint8).reshape(h, w).astype(np.float64)
    if direction == "horizontal":
        x, y = img[:, :-1].ravel(), img[:, 1:].ravel()
    elif direction == "vertical":
        x, y = img[:-1, :].ravel(), img[1:, :].ravel()
    elif direction == "diagonal":
        x, y = img[:-1, :-1].ravel(), img[1:, 1:].ravel()
    else:
        raise ValueError(direction)
    n = len(x)
    mx, my = np.mean(x), np.mean(y)
    cov = np.sum((x - mx) * (y - my)) / n
    sx = math.sqrt(np.sum((x - mx) ** 2) / n)
    sy = math.sqrt(np.sum((y - my) ** 2) / n)
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return float(cov / (sx * sy))


def npcr_uaci(ct1, ct2):
    """NPCR and UACI between two ciphertexts (same length)."""
    a = np.frombuffer(ct1, dtype=np.uint8).astype(np.float64)
    b = np.frombuffer(ct2, dtype=np.uint8).astype(np.float64)
    npcr = float(np.mean(a != b)) * 100
    uaci = float(np.mean(np.abs(a - b) / 255)) * 100
    return npcr, uaci


# ---- S-box metrics (reused from step4) ----

def ddt_max_prob(sbox):
    n = 256
    ddt = np.zeros((n, n), dtype=np.int32)
    s = np.array(sbox, dtype=np.int32)
    for dx in range(1, n):
        for x in range(n):
            dy = s[x] ^ s[x ^ dx]
            ddt[dx, dy] += 1
    return float(ddt[1:].max()) / n


def lat_max_bias(sbox):
    n = 256
    s = np.array(sbox, dtype=np.uint8)
    parity = np.array([bin(i).count("1") % 2 for i in range(n)], dtype=np.int32)
    xs = np.arange(n, dtype=np.uint8)
    sx = s[xs]
    best = 0
    for a in range(n):
        ax_par = parity[a & xs]
        for b in range(n):
            if a == 0 and b == 0:
                continue
            bsx_par = parity[b & sx]
            val = abs(int(np.sum(1 - 2 * (ax_par ^ bsx_par))))
            if val > best:
                best = val
    return float(best) / n


# ---- Diffusion propagation ----

def measure_propagation(fwd_fn, bwd_fn, S, a, b, iv_f, iv_b, n, sample_positions=64):
    base_plain = bytes(np.random.RandomState(42).randint(0, 256, n, dtype=np.uint8))
    u = fwd_fn(base_plain, a, S, iv_f)
    base_ct = bwd_fn(u, b, S, iv_b)
    positions = sorted(np.random.RandomState(99).choice(n, min(sample_positions, n), replace=False))
    deps, total = 0, 0
    for i in positions:
        flipped = bytearray(base_plain)
        flipped[i] ^= 0x01
        u2 = fwd_fn(bytes(flipped), a, S, iv_f)
        ct2 = bwd_fn(u2, b, S, iv_b)
        for j in range(n):
            total += 1
            if ct2[j] != base_ct[j]:
                deps += 1
    return deps / total if total > 0 else 0.0


# ---- Encrypt functions for each baseline ----

def encrypt_isc_v1(data):
    from isc_cipher.cipher import _encrypt
    return _encrypt(KEY, data, H, W, C, NONCE, "numpy", 1, extraction=EXTRACTION_MANTISSA8_V1)


def encrypt_isc_v2(data):
    from isc_cipher.cipher import _encrypt
    return _encrypt(KEY, data, H, W, C, NONCE, "numpy", 1, extraction=EXTRACTION_K14_SCALED_MODULO_V1)


def encrypt_v_chacha(data):
    return v_chacha_encrypt(KEY, data, H, W, C, NONCE)


def encrypt_v_stream_isc(data):
    return v_stream_isc_encrypt(KEY, data, H, W, C, NONCE)


def encrypt_aes_gcm(data):
    aes_key = KEY  # 32 bytes = AES-256
    nonce_12 = NONCE[:12]
    aesgcm = AESGCM(aes_key)
    return aesgcm.encrypt(nonce_12, bytes(data), None)


def encrypt_chacha20_poly1305(data):
    nonce_12 = NONCE[:12]
    cc = ChaCha20Poly1305(KEY)
    return cc.encrypt(nonce_12, bytes(data), None)


# ---- Extract body from full ciphertext ----

def body_isc_v1(ct):
    return ct[36:-32]


def body_isc_v2(ct):
    return ct[37:-32]


def body_aead(ct):
    return ct[:-16]  # 16-byte tag


def body_identity(ct):
    return ct


# ---- Main ----

def run_ciphertext_stats(name, body, h, w):
    ent = entropy(body)
    chi2 = chi_square(body)
    corr_h = correlation(body, h, w, "horizontal")
    corr_v = correlation(body, h, w, "vertical")
    corr_d = correlation(body, h, w, "diagonal")
    return {
        "variant": name,
        "entropy": round(ent, 6),
        "chi_square_255": round(chi2, 2),
        "correlation_h": round(corr_h, 6),
        "correlation_v": round(corr_v, 6),
        "correlation_d": round(corr_d, 6),
    }


def run_npcr_uaci(name, encrypt_fn, body_fn, data):
    data2 = bytearray(data)
    pos = len(data2) // 2
    data2[pos] ^= 0x01
    ct1 = encrypt_fn(bytes(data))
    ct2 = encrypt_fn(bytes(data2))
    b1, b2 = body_fn(ct1), body_fn(ct2)
    if len(b1) != len(b2):
        minlen = min(len(b1), len(b2))
        b1, b2 = b1[:minlen], b2[:minlen]
    npcr, uaci = npcr_uaci(b1, b2)
    return {"variant": name, "npcr_pct": round(npcr, 4), "uaci_pct": round(uaci, 4)}


def run_timing(name, encrypt_fn, data, n_trials=5):
    times = []
    for _ in range(n_trials):
        t0 = time.perf_counter()
        encrypt_fn(bytes(data))
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {
        "variant": name,
        "encrypt_time_ms_median": round(sorted(times)[len(times) // 2] * 1000, 2),
        "encrypt_time_ms_min": round(min(times) * 1000, 2),
    }


def main():
    print("Step 5: Controlled experiments")
    print(f"Test image: {H}x{W}x{C} = {N} bytes\n")

    data = bytes(make_test_image())

    # Plaintext stats for reference
    print("=== Plaintext statistics ===")
    p_stats = run_ciphertext_stats("plaintext", data, H, W)
    print(f"  Entropy: {p_stats['entropy']}")
    print(f"  Chi²: {p_stats['chi_square_255']}")
    print(f"  Correlation H/V/D: {p_stats['correlation_h']}, {p_stats['correlation_v']}, {p_stats['correlation_d']}")

    variants = [
        ("ISC-IMG_v1", encrypt_isc_v1, body_isc_v1),
        ("ISC-IMG_v2_k14", encrypt_isc_v2, body_isc_v2),
        ("V-CHACHA", encrypt_v_chacha, body_identity),
        ("V-STREAM-ISC", encrypt_v_stream_isc, body_identity),
        ("AES-256-GCM", encrypt_aes_gcm, body_aead),
        ("ChaCha20-Poly1305", encrypt_chacha20_poly1305, body_aead),
    ]

    all_stats = [p_stats]
    all_npcr = []
    all_timing = []

    for name, enc_fn, body_fn in variants:
        print(f"\n=== {name} ===")

        # Encrypt
        ct = enc_fn(data)
        body = body_fn(ct)
        print(f"  Ciphertext: {len(ct)} bytes, body: {len(body)} bytes")

        # Ciphertext stats
        stats = run_ciphertext_stats(name, body, H, W)
        all_stats.append(stats)
        print(f"  Entropy: {stats['entropy']}")
        print(f"  Chi²(255): {stats['chi_square_255']}")
        print(f"  Corr H/V/D: {stats['correlation_h']}, {stats['correlation_v']}, {stats['correlation_d']}")

        # NPCR/UACI (skip for V-STREAM-ISC with fixed nonce — XOR stream doesn't depend on plaintext)
        nu = run_npcr_uaci(name, enc_fn, body_fn, data)
        all_npcr.append(nu)
        print(f"  NPCR: {nu['npcr_pct']}%  UACI: {nu['uaci_pct']}%")

        # Timing
        t = run_timing(name, enc_fn, data)
        all_timing.append(t)
        print(f"  Time: {t['encrypt_time_ms_median']} ms (median)")

    # ---- S-box quality comparison ----
    print("\n=== S-box quality comparison ===")
    sbox_results = []

    # ISC S-box
    ctx = context(1, container.DTYPE_UINT8, H, W, C)
    der = Derivation(KEY, NONCE, ctx)
    streams = build_streams(der.seeds(), backend="numpy", profile=1)
    S_isc, _ = sampling.build_sbox(streams["sbox"])
    ddt_isc = ddt_max_prob(S_isc)
    print(f"  ISC S-box DDT: {ddt_isc:.4f} ... computing LAT", end="", flush=True)
    lat_isc = lat_max_bias(S_isc)
    print(f" LAT: {lat_isc:.4f}")
    sbox_results.append({"source": "ISC", "ddt_max_prob": round(ddt_isc, 6), "lat_max_bias": round(lat_isc, 6)})

    # V-CHACHA S-box
    mats = v_chacha_materials(KEY, NONCE, H, W, C)
    ddt_ch = ddt_max_prob(mats["S"])
    print(f"  V-CHACHA S-box DDT: {ddt_ch:.4f} ... computing LAT", end="", flush=True)
    lat_ch = lat_max_bias(mats["S"])
    print(f" LAT: {lat_ch:.4f}")
    sbox_results.append({"source": "V-CHACHA", "ddt_max_prob": round(ddt_ch, 6), "lat_max_bias": round(lat_ch, 6)})

    # AES S-box reference
    AES_SBOX = [
        0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
        0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
        0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
        0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
        0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
        0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
        0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
        0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
        0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
        0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
        0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
        0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
        0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
        0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
        0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
        0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
    ]
    ddt_aes = ddt_max_prob(AES_SBOX)
    lat_aes = lat_max_bias(AES_SBOX)
    print(f"  AES S-box DDT: {ddt_aes:.4f}  LAT: {lat_aes:.4f}")
    sbox_results.append({"source": "AES", "ddt_max_prob": round(ddt_aes, 6), "lat_max_bias": round(lat_aes, 6)})

    # ---- Diffusion propagation comparison ----
    print("\n=== Diffusion propagation comparison ===")
    prop_results = []

    # ISC diffusion
    print("  ISC diffusion ...", end=" ", flush=True)
    ctx_isc = context(1, container.DTYPE_UINT8, H, W, C)
    der_isc = Derivation(KEY, NONCE, ctx_isc)
    streams_isc = build_streams(der_isc.seeds(), backend="numpy", profile=1)
    S_isc2, _ = sampling.build_sbox(streams_isc["sbox"])
    a_isc = streams_isc["fwd"].take(N)
    b_isc = streams_isc["bwd"].take(N)
    iv_f_isc, iv_b_isc = der_isc.ivs()
    prop_isc = measure_propagation(diffusion.forward, diffusion.backward,
                                     S_isc2, a_isc, b_isc, iv_f_isc, iv_b_isc, N)
    print(f"{prop_isc*100:.4f}%")
    prop_results.append({"variant": "ISC", "propagation_pct": round(prop_isc * 100, 4)})

    # V-CHACHA diffusion (same code, different S-box and stream bytes)
    print("  V-CHACHA diffusion ...", end=" ", flush=True)
    prop_ch = measure_propagation(diffusion.forward, diffusion.backward,
                                    mats["S"], mats["a"], mats["b"], mats["iv_f"], mats["iv_b"], N)
    print(f"{prop_ch*100:.4f}%")
    prop_results.append({"variant": "V-CHACHA", "propagation_pct": round(prop_ch * 100, 4)})

    # ---- Compile results ----
    results = {
        "test_image": f"{H}x{W}x{C}",
        "n_bytes": N,
        "ciphertext_statistics": all_stats,
        "npcr_uaci": all_npcr,
        "timing": all_timing,
        "sbox_quality": sbox_results,
        "diffusion_propagation": prop_results,
        "ideal_references": {
            "entropy": 8.0,
            "npcr_pct": 99.6094,
            "uaci_pct": 33.4635,
            "ddt_max_prob_aes": 0.015625,
            "lat_max_bias_aes": 0.125,
        },
    }

    out_path = os.path.join(os.path.dirname(__file__), "results", "controlled_experiments.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
