"""Test prototype for enhanced ISCImageCipher incorporating:
  1. Recommendation A: SIV Plaintext-Coupled Nonce (Misuse-Resistant Authenticated Encryption)
  2. Recommendation B: 2D Matrix Transposition between Round 1 and Round 2
  3. Recommendation C: Adaptive Permutation Sizing
"""

import hashlib
import hmac
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath("."))
from experiments.paper_workflow_study.cipher_pipeline import (
    _gf_inv, GF_INV_TABLE, build_dynamic_sbox,
    derive_initial_states, generate_keystream,
    apply_permutation, invert_permutation,
    rotl8, rotr8, forward_arx, backward_arx,
    backward_arx_inv, forward_arx_inv
)


def compute_siv_nonce(key: bytes, nonce: bytes, plain_bytes: bytes) -> bytes:
    """Computes Synthetic IV: N_synth = HMAC-SHA256(K, nonce || len(P) || P)[:16]."""
    h = hmac.new(key, digestmod=hashlib.sha256)
    h.update(nonce)
    h.update(len(plain_bytes).to_bytes(8, "big"))
    h.update(plain_bytes)
    return h.digest()[:16]


def build_permutation_adaptive(stream_bytes: bytes, n: int) -> tuple:
    """Adaptive unbiased Fisher-Yates permutation.
    Uses 2 bytes per swap if n <= 65536, else 4 bytes.
    """
    pi = list(range(n))
    pos = 0
    if n <= 65536:
        for i in range(n - 1, 0, -1):
            bound = i + 1
            w = int.from_bytes(stream_bytes[pos : pos + 2], "big")
            pos += 2
            j = (w * bound) >> 16
            pi[i], pi[j] = pi[j], pi[i]
    else:
        for i in range(n - 1, 0, -1):
            bound = i + 1
            w = int.from_bytes(stream_bytes[pos : pos + 4], "big")
            pos += 4
            j = (w * bound) >> 32
            pi[i], pi[j] = pi[j], pi[i]

    pi_inv = [0] * n
    for i, p in enumerate(pi):
        pi_inv[p] = i
    return pi, pi_inv


def transpose_intermediate(data_bytes: bytes, shape: tuple) -> bytes:
    """Applies 2D transposition (H, W) -> (W, H)."""
    arr = np.frombuffer(data_bytes, dtype=np.uint8).reshape(shape)
    if len(shape) == 2:
        return arr.T.tobytes()
    elif len(shape) == 3:
        # (H, W, C) -> (W, H, C)
        return np.transpose(arr, (1, 0, 2)).tobytes()
    return data_bytes


def transpose_inverse(data_bytes: bytes, shape: tuple) -> bytes:
    """Inverts 2D transposition (W, H) -> (H, W)."""
    if len(shape) == 2:
        H, W = shape
        arr = np.frombuffer(data_bytes, dtype=np.uint8).reshape(W, H)
        return arr.T.tobytes()
    elif len(shape) == 3:
        H, W, C = shape
        arr = np.frombuffer(data_bytes, dtype=np.uint8).reshape(W, H, C)
        return np.transpose(arr, (1, 0, 2)).tobytes()
    return data_bytes


class EnhancedISCImageCipher:
    def __init__(self, key: bytes, nonce: bytes, use_siv: bool = True):
        if len(key) != 32:
            raise ValueError("Key must be 256 bits (32 bytes)")
        if len(nonce) != 16:
            raise ValueError("Nonce must be 128 bits (16 bytes)")
        self.key = key
        self.nonce = nonce
        self.use_siv = use_siv

    def _prepare_materials(self, n: int, effective_nonce: bytes):
        orbits, _ = derive_initial_states(self.key, effective_nonce, num_orbits=16)

        perm_bytes_per_elem = 2 if n <= 65536 else 4
        total_stream_bytes = (2 * perm_bytes_per_elem + 4) * n + 32
        stream = generate_keystream(orbits, total_stream_bytes, burn_in=1024)

        offset = 0
        p_len = perm_bytes_per_elem * n
        # Round 1 materials
        pi1, pi1_inv = build_permutation_adaptive(stream[offset : offset + p_len], n)
        offset += p_len
        a1 = stream[offset : offset + n]
        offset += n
        b1 = stream[offset : offset + n]
        offset += n

        # Round 2 materials
        pi2, pi2_inv = build_permutation_adaptive(stream[offset : offset + p_len], n)
        offset += p_len
        a2 = stream[offset : offset + n]
        offset += n
        b2 = stream[offset : offset + n]
        offset += n

        # S-boxes
        s1, s1_inv = build_dynamic_sbox(stream[offset], stream[offset + 1])
        s2, s2_inv = build_dynamic_sbox(stream[offset + 2], stream[offset + 3])
        offset += 4

        iv_f1, iv_b1 = stream[offset], stream[offset + 1]
        iv_f2, iv_b2 = stream[offset + 2], stream[offset + 3]

        return {
            "pi1": pi1, "pi1_inv": pi1_inv, "a1": a1, "b1": b1, "s1": s1, "s1_inv": s1_inv, "iv_f1": iv_f1, "iv_b1": iv_b1,
            "pi2": pi2, "pi2_inv": pi2_inv, "a2": a2, "b2": b2, "s2": s2, "s2_inv": s2_inv, "iv_f2": iv_f2, "iv_b2": iv_b2,
        }

    def encrypt(self, plain_bytes: bytes, shape: tuple = None, raw: bool = False):
        n = len(plain_bytes)
        if self.use_siv:
            n_synth = compute_siv_nonce(self.key, self.nonce, plain_bytes)
        else:
            n_synth = self.nonce

        m = self._prepare_materials(n, n_synth)

        # ROUND 1:
        # Confusion: Permutation 1
        q1 = apply_permutation(plain_bytes, m["pi1"])
        # Diffusion: Forward + Backward ARX-S (Horizontal pass)
        u1 = forward_arx(q1, m["a1"], m["s1"], m["iv_f1"])
        c1 = backward_arx(u1, m["b1"], m["s1"], m["iv_b1"])

        # 2D TRANSPOSITION (Swap rows and columns)
        if shape is not None:
            c1_t = transpose_intermediate(c1, shape)
        else:
            c1_t = c1

        # ROUND 2:
        # Confusion: Permutation 2
        q2 = apply_permutation(c1_t, m["pi2"])
        # Diffusion: Forward + Backward ARX-S (Vertical pass)
        u2 = forward_arx(q2, m["a2"], m["s2"], m["iv_f2"])
        c2 = backward_arx(u2, m["b2"], m["s2"], m["iv_b2"])

        # Final transposition back to original orientation
        if shape is not None:
            c_final = transpose_inverse(c2, shape)
        else:
            c_final = c2

        if raw or not self.use_siv:
            return c_final, n_synth
        # Prepend 16-byte synthetic nonce container
        return n_synth + c_final

    def decrypt(self, cipher_data: bytes, shape: tuple = None, synth_nonce: bytes = None):
        if self.use_siv and synth_nonce is None:
            n_synth = cipher_data[:16]
            cipher_bytes = cipher_data[16:]
        else:
            n_synth = synth_nonce if synth_nonce is not None else self.nonce
            cipher_bytes = cipher_data

        n = len(cipher_bytes)
        m = self._prepare_materials(n, n_synth)

        # Transposition to Round 2 orientation
        if shape is not None:
            c2 = transpose_intermediate(cipher_bytes, shape)
        else:
            c2 = cipher_bytes

        # ROUND 2 INVERSE:
        u2 = backward_arx_inv(c2, m["b2"], m["s2_inv"], m["iv_b2"])
        q2 = forward_arx_inv(u2, m["a2"], m["s2_inv"], m["iv_f2"])
        c1_t = invert_permutation(q2, m["pi2_inv"])

        # Transposition Inverse back to Round 1 orientation
        if shape is not None:
            c1 = transpose_inverse(c1_t, shape)
        else:
            c1 = c1_t

        # ROUND 1 INVERSE:
        u1 = backward_arx_inv(c1, m["b1"], m["s1_inv"], m["iv_b1"])
        q1 = forward_arx_inv(u1, m["a1"], m["s1_inv"], m["iv_f1"])
        plain = invert_permutation(q1, m["pi1_inv"])

        # Authenticated verification
        if self.use_siv:
            expected_n_synth = compute_siv_nonce(self.key, self.nonce, plain)
            if expected_n_synth != n_synth:
                raise ValueError("Authentication failed: ciphertext corrupted or wrong key/nonce!")

        return plain


if __name__ == "__main__":
    print("=== Testing Enhanced ISCImageCipher ===")
    k = b"ISC_ENCRYPTION_MASTER_KEY_256B!!"
    nonce = b"ISC_NONCE_128BIT"
    cipher = EnhancedISCImageCipher(k, nonce, use_siv=True)

    # 1. Test 256x256 Grayscale (Couple 5.1.12)
    img_gray = np.load("experiments/paper_workflow_study/standard_dataset/5.1.12.npy")
    b_gray = img_gray.tobytes()
    print("1. Testing 5.1.12 Grayscale (256x256)...")
    t0 = time.perf_counter()
    c_pkg = cipher.encrypt(b_gray, shape=img_gray.shape)
    t_enc = time.perf_counter() - t0
    t0 = time.perf_counter()
    p_rec = cipher.decrypt(c_pkg, shape=img_gray.shape)
    t_dec = time.perf_counter() - t0
    assert p_rec == b_gray, "Decryption failure on 5.1.12!"
    print(f"   [PASS] Exact Bit-for-Bit Recovery! (Enc: {t_enc*1000:.1f}ms, Dec: {t_dec*1000:.1f}ms)")

    # 2. Test 512x512x3 RGB (Baboon)
    img_rgb = np.load("experiments/paper_workflow_study/standard_dataset/baboon_512_rgb.npy")
    b_rgb = img_rgb.tobytes()
    print("2. Testing Baboon RGB (512x512x3)...")
    t0 = time.perf_counter()
    c_rgb_pkg = cipher.encrypt(b_rgb, shape=img_rgb.shape)
    t_enc_rgb = time.perf_counter() - t0
    t0 = time.perf_counter()
    p_rgb_rec = cipher.decrypt(c_rgb_pkg, shape=img_rgb.shape)
    t_dec_rgb = time.perf_counter() - t0
    assert p_rgb_rec == b_rgb, "Decryption failure on Baboon RGB!"
    print(f"   [PASS] Exact Bit-for-Bit Recovery! (Enc: {t_enc_rgb*1000:.1f}ms, Dec: {t_dec_rgb*1000:.1f}ms)")

    # 3. Test Authentication Tamper Detection
    print("3. Testing Authentication Tamper Detection...")
    c_tampered = bytearray(c_pkg)
    c_tampered[30] ^= 0x01
    try:
        cipher.decrypt(bytes(c_tampered), shape=img_gray.shape)
        print("   [FAIL] Tampered ciphertext was accepted!")
    except ValueError as e:
        print(f"   [PASS] Tampered ciphertext correctly rejected: {e}")

    # 4. Test SIV Nonce-Misuse Resistance
    print("4. Testing SIV Nonce-Misuse Resistance (2 distinct images, same key+nonce)...")
    b_gray2 = bytearray(b_gray)
    b_gray2[100] ^= 0xFF
    c1, n1 = cipher.encrypt(b_gray, shape=img_gray.shape, raw=True)
    c2, n2 = cipher.encrypt(bytes(b_gray2), shape=img_gray.shape, raw=True)
    assert n1 != n2, "Synthetic nonces collided!"
    diff_rate = np.sum(np.frombuffer(c1, dtype=np.uint8) != np.frombuffer(c2, dtype=np.uint8)) / len(c1) * 100
    print(f"   [PASS] SIV Nonce Diversity Verified: Diff Rate = {diff_rate:.2f}% (Ideal: 99.61%)")

