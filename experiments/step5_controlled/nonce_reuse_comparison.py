"""Step 5: Nonce-reuse attack comparison across all baselines.

Tests B3/B4: Does ISC-IMG degrade more gracefully under nonce reuse than AEADs?

Experiments:
1. XOR leakage: encrypt p1 and p2 with same (key, nonce), XOR ciphertext bodies.
   For stream ciphers: ct1 ^ ct2 = p1 ^ p2 exactly.
   For diffusion-based: ct1 ^ ct2 != p1 ^ p2 (diffusion scrambles the relationship).

2. Equality detection: encrypt identical plaintext twice with same (key, nonce).
   All deterministic variants produce identical ciphertext.

3. Structural information leakage: given ct1 ^ ct2 from nonce reuse, how much
   information about p1 ^ p2 can be recovered? Measure correlation.

4. Integrity: does authentication survive nonce reuse? (GCM is known to break.)
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from isc_cipher.cipher import _encrypt
from isc_cipher.generator import EXTRACTION_MANTISSA8_V1, EXTRACTION_K14_SCALED_MODULO_V1
from isc_cipher.kdf import NONCE_LEN

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305, AESGCMSIV

from baselines import v_chacha_encrypt, v_stream_isc_encrypt

KEY = b"ab" * 16
NONCE = b"cd" * 8
NONCE_12 = NONCE[:12]
H, W, C = 64, 64, 1
N = H * W * C


def make_images(seed1=42, seed2=99):
    rng1 = np.random.RandomState(seed1)
    rng2 = np.random.RandomState(seed2)
    p1 = bytes(rng1.randint(0, 256, N, dtype=np.uint8))
    p2 = bytes(rng2.randint(0, 256, N, dtype=np.uint8))
    return p1, p2


def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def correlation_1d(a, b):
    x = np.frombuffer(a, dtype=np.uint8).astype(np.float64)
    y = np.frombuffer(b, dtype=np.uint8).astype(np.float64)
    mx, my = np.mean(x), np.mean(y)
    cov = np.mean((x - mx) * (y - my))
    sx, sy = np.std(x), np.std(y)
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return float(cov / (sx * sy))


def fraction_equal(a, b):
    return float(np.mean(np.frombuffer(a, dtype=np.uint8) == np.frombuffer(b, dtype=np.uint8)))


# ---- Encrypt with fixed nonce (nonce reuse scenario) ----

def enc_isc_v1(p):
    ct = _encrypt(KEY, p, H, W, C, NONCE, "numpy", 1, extraction=EXTRACTION_MANTISSA8_V1)
    return ct[36:-32]  # body only

def enc_isc_v2(p):
    ct = _encrypt(KEY, p, H, W, C, NONCE, "numpy", 1, extraction=EXTRACTION_K14_SCALED_MODULO_V1)
    return ct[37:-32]

def enc_v_chacha(p):
    return v_chacha_encrypt(KEY, p, H, W, C, NONCE)

def enc_v_stream(p):
    return v_stream_isc_encrypt(KEY, p, H, W, C, NONCE)

def enc_aes_gcm(p):
    return AESGCM(KEY).encrypt(NONCE_12, bytes(p), None)

def enc_chacha_poly(p):
    return ChaCha20Poly1305(KEY).encrypt(NONCE_12, bytes(p), None)

def enc_aes_gcm_siv(p):
    return AESGCMSIV(KEY).encrypt(NONCE_12, bytes(p), None)


VARIANTS = [
    ("ISC-IMG_v1",       enc_isc_v1,     lambda ct: ct,       "diffusion"),
    ("ISC-IMG_v2_k14",   enc_isc_v2,     lambda ct: ct,       "diffusion"),
    ("V-CHACHA",         enc_v_chacha,    lambda ct: ct,       "diffusion"),
    ("V-STREAM-ISC",     enc_v_stream,    lambda ct: ct,       "stream"),
    ("AES-256-GCM",      enc_aes_gcm,     lambda ct: ct[:-16], "stream"),
    ("ChaCha20-Poly1305",enc_chacha_poly, lambda ct: ct[:-16], "stream"),
    ("AES-256-GCM-SIV",  enc_aes_gcm_siv, lambda ct: ct[:-16], "nonce-misuse-resistant"),
]


def main():
    print("Step 5: Nonce-reuse comparison experiments")
    print(f"Image size: {H}x{W}x{C} = {N} bytes\n")

    p1, p2 = make_images()
    p1_xor_p2 = xor_bytes(p1, p2)

    results = []

    for name, enc_fn, body_fn, cipher_type in VARIANTS:
        print(f"=== {name} ({cipher_type}) ===")
        row = {"variant": name, "type": cipher_type}

        # Encrypt both plaintexts with the SAME key and nonce
        ct1_full = enc_fn(p1)
        ct2_full = enc_fn(p2)
        ct1 = body_fn(ct1_full)
        ct2 = body_fn(ct2_full)

        # Also encrypt p1 again (for equality detection)
        ct1_again_full = enc_fn(p1)
        ct1_again = body_fn(ct1_again_full)

        # 1. Equality detection: same plaintext, same key/nonce
        eq_frac = fraction_equal(ct1, ct1_again)
        is_deterministic = (ct1 == ct1_again)
        row["deterministic"] = is_deterministic
        row["ct_equality_fraction"] = round(eq_frac, 6)
        print(f"  Deterministic: {is_deterministic} (byte equality: {eq_frac*100:.2f}%)")

        # 2. XOR leakage: ct1 ^ ct2 vs p1 ^ p2
        minlen = min(len(ct1), len(ct2), N)
        ct_xor = xor_bytes(ct1[:minlen], ct2[:minlen])
        p_xor = p1_xor_p2[:minlen]

        xor_exact_match = (ct_xor == p_xor)
        xor_byte_match = fraction_equal(ct_xor, p_xor)
        xor_correlation = correlation_1d(ct_xor, p_xor)
        row["xor_exact_leak"] = xor_exact_match
        row["xor_byte_match_fraction"] = round(xor_byte_match, 6)
        row["xor_correlation"] = round(xor_correlation, 6)
        print(f"  XOR leak: exact={xor_exact_match}, byte_match={xor_byte_match*100:.2f}%, corr={xor_correlation:.4f}")

        # 3. Bit-level analysis of XOR leakage
        ct_xor_bits = np.unpackbits(np.frombuffer(ct_xor, dtype=np.uint8))
        p_xor_bits = np.unpackbits(np.frombuffer(p_xor, dtype=np.uint8))
        bit_agreement = float(np.mean(ct_xor_bits == p_xor_bits))
        row["xor_bit_agreement"] = round(bit_agreement, 6)
        print(f"  XOR bit agreement: {bit_agreement*100:.2f}% (random=50%)")

        # 4. Histogram analysis: is ct_xor uniformly distributed?
        ct_xor_arr = np.frombuffer(ct_xor, dtype=np.uint8)
        ct_xor_chi2 = float(np.sum((np.bincount(ct_xor_arr, minlength=256) - minlen/256)**2 / (minlen/256)))
        row["ct_xor_chi2_255"] = round(ct_xor_chi2, 2)
        print(f"  ct1^ct2 chi²(255): {ct_xor_chi2:.2f}")

        # 5. For stream ciphers: verify that ct1 ^ ct2 = p1 ^ p2 exactly
        if xor_exact_match:
            print(f"  ** FULL p1 XOR p2 LEAKAGE under nonce reuse **")
        elif xor_byte_match > 0.01:
            print(f"  ** PARTIAL leakage: {xor_byte_match*100:.1f}% byte match **")
        else:
            print(f"  No direct XOR leakage (byte match at random baseline ~0.39%)")

        results.append(row)
        print()

    # ---- Summary table ----
    print("=" * 80)
    print("SUMMARY: Nonce-reuse degradation comparison")
    print("=" * 80)
    print(f"{'Variant':<22} {'Determ.':<8} {'XOR leak':<10} {'XOR corr':<10} {'ct^ct chi2':<10}")
    print("-" * 80)
    for r in results:
        print(f"{r['variant']:<22} {str(r['deterministic']):<8} "
              f"{str(r['xor_exact_leak']):<10} {r['xor_correlation']:<10.4f} "
              f"{r['ct_xor_chi2_255']:<10.1f}")

    # ---- GCM forgery note ----
    print("\n--- GCM integrity note ---")
    print("AES-GCM under nonce reuse: Joux's forbidden attack recovers the GHASH key H")
    print("from two (ciphertext, tag) pairs, enabling universal forgery. This is a known,")
    print("published, practical attack [bock2016nonce, joux2006gcm].")
    print("ISC-IMG under nonce reuse: HMAC-SHA-256 integrity holds (HMAC is a PRF, not a")
    print("polynomial MAC), but the cipher becomes deterministic — identical plaintexts")
    print("produce identical ciphertexts, leaking equality.")

    out = {
        "test_image_size": f"{H}x{W}x{C}",
        "n_bytes": N,
        "nonce_reuse_results": results,
        "notes": {
            "xor_exact_leak": "True means ct1⊕ct2 = p1⊕p2 exactly — complete plaintext-difference leakage",
            "xor_correlation": "Pearson correlation between ct1⊕ct2 and p1⊕p2; >0.1 indicates structural leakage",
            "deterministic": "Same plaintext + same key/nonce → identical ciphertext",
            "random_baseline_byte_match": "~1/256 ≈ 0.39%",
            "random_baseline_bit_agreement": "~50%",
        },
    }

    out_path = os.path.join(os.path.dirname(__file__), "results", "nonce_reuse_comparison.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
