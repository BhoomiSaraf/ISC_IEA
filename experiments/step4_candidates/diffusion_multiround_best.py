"""Test 2-round D_xorrot (the best single-round candidate) for propagation at n=64 and n=1024."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from isc_cipher.generator import build_streams
from isc_cipher.kdf import Derivation, context
from isc_cipher.sampling import build_sbox

from diffusion_candidates import forward_xorrot, backward_xorrot, inverse_xorrot, rol8


def multi_round_encrypt(p, a, b, S, iv_f, iv_b, rounds):
    data = p
    for _ in range(rounds):
        u = forward_xorrot(data, a, S, iv_f)
        data = backward_xorrot(u, b, S, iv_b)
    return data


def multi_round_decrypt(c, a, b, S_inv, iv_f, iv_b, rounds):
    data = c
    for _ in range(rounds):
        data = inverse_xorrot(data, a, b, S_inv, iv_f, iv_b)
    return data


def measure_propagation(a, b, S, iv_f, iv_b, n, rounds, sample_positions=None):
    base_plain = bytes(range(n)) if n <= 256 else bytes(np.random.RandomState(42).randint(0, 256, n, dtype=np.uint8))
    base_ct = multi_round_encrypt(base_plain, a, b, S, iv_f, iv_b, rounds)

    positions = range(n) if sample_positions is None else sorted(
        np.random.RandomState(99).choice(n, min(sample_positions, n), replace=False))

    deps = 0
    total = 0
    for i in positions:
        flipped = bytearray(base_plain)
        flipped[i] ^= 0x01
        ct2 = multi_round_encrypt(bytes(flipped), a, b, S, iv_f, iv_b, rounds)
        for j in range(n):
            total += 1
            if ct2[j] != base_ct[j]:
                deps += 1
    return deps / total if total > 0 else 0.0


def main():
    key = b"ab" * 32
    nonce = b"cd" * 8

    for (h, w, c, sample) in [(8, 8, 1, None), (32, 32, 1, 64)]:
        n = h * w * c
        ctx = context(1, 0, h, w, c)
        der = Derivation(key, nonce, ctx)
        streams = build_streams(der.seeds(), backend="numpy", profile=1)
        S, S_inv = build_sbox(streams["sbox"])
        a = streams["fwd"].take(n)
        b = streams["bwd"].take(n)
        iv_f, iv_b = der.ivs()

        # Verify round-trip first
        p = bytes(range(n)) if n <= 256 else bytes(np.random.RandomState(42).randint(0, 256, n, dtype=np.uint8))
        for r in [1, 2, 3]:
            ct = multi_round_encrypt(p, a, b, S, iv_f, iv_b, r)
            rec = multi_round_decrypt(ct, a, b, S_inv, iv_f, iv_b, r)
            assert p == rec, f"Round-trip FAIL at n={n}, rounds={r}"

        print(f"\nn={n}:")
        for r in [1, 2, 3]:
            prop = measure_propagation(a, b, S, iv_f, iv_b, n, r, sample_positions=sample)
            full = "FULL (100%)" if prop >= 1.0 else f"{prop*100:.4f}%"
            print(f"  D_xorrot, rounds={r}: {full}")


if __name__ == "__main__":
    main()
