"""Step 4 candidate 3: Multi-round diffusion to close the 99.58% propagation gap.

Current: single round of forward + backward chained diffusion with S-box.
Known gap: 0.42% of byte positions can remain uninfluenced (modular-addition cancellation).

Candidate: run R rounds (R=1,2,3,4) of the same forward+backward chain, measuring
byte-dependency coverage (fraction of (input, output) pairs where flipping input byte i
changes output byte j) for each round count.

This does NOT modify the cipher — it measures the effect of round count on an isolated
diffusion function using the actual cipher's S-box and stream bytes.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from isc_cipher.diffusion import forward, backward
from isc_cipher.generator import build_streams
from isc_cipher.kdf import Derivation, context
from isc_cipher.sampling import build_sbox


def multi_round_encrypt(plaintext, a_bytes, b_bytes, S, iv_f, iv_b, rounds):
    """Apply rounds of forward+backward diffusion."""
    data = plaintext
    for _ in range(rounds):
        u = forward(data, a_bytes, S, iv_f)
        data = backward(u, b_bytes, S, iv_b)
    return data


def measure_propagation(n, a_bytes, b_bytes, S, iv_f, iv_b, rounds, sample_positions=None):
    """Measure byte-dependency by flipping each sampled input byte and checking which
    output bytes change. Returns the fraction of (i,j) pairs with dependency."""
    base_plain = bytes(range(n)) if n <= 256 else bytes(np.random.RandomState(42).randint(0, 256, n, dtype=np.uint8))
    base_ct = multi_round_encrypt(base_plain, a_bytes, b_bytes, S, iv_f, iv_b, rounds)

    if sample_positions is None:
        positions = range(n)
    else:
        positions = sorted(np.random.RandomState(99).choice(n, min(sample_positions, n), replace=False))

    deps = 0
    total = 0
    for i in positions:
        flipped = bytearray(base_plain)
        flipped[i] ^= 0x01
        ct2 = multi_round_encrypt(bytes(flipped), a_bytes, b_bytes, S, iv_f, iv_b, rounds)
        for j in range(n):
            total += 1
            if ct2[j] != base_ct[j]:
                deps += 1

    return deps / total if total > 0 else 0.0


def main():
    key = b"ab" * 32
    nonce = b"cd" * 8

    # Test at two sizes: small (64 bytes) for exhaustive, medium (1024) sampled
    test_configs = [
        (8, 8, 1, None),       # 64 bytes, exhaustive
        (32, 32, 1, 64),       # 1024 bytes, sample 64 positions
    ]
    round_counts = [1, 2, 3, 4]

    results = []

    for h, w, c, sample in test_configs:
        n = h * w * c
        ctx = context(1, 0, h, w, c)
        der = Derivation(key, nonce, ctx)
        streams = build_streams(der.seeds(), backend="numpy", profile=1)
        S, _ = build_sbox(streams["sbox"])
        a = streams["fwd"].take(n)
        b = streams["bwd"].take(n)
        iv_f = der.ivs()[0]
        iv_b = der.ivs()[1]

        for r in round_counts:
            label = f"n={n}, rounds={r}"
            print(f"  {label} ...", end=" ", flush=True)
            t0 = time.time()
            prop = measure_propagation(n, a, b, S, iv_f, iv_b, r, sample_positions=sample)
            t1 = time.time()
            row = {
                "n_bytes": n,
                "rounds": r,
                "propagation": round(prop, 6),
                "sample_positions": sample or n,
                "wall_time_s": round(t1 - t0, 3),
            }
            results.append(row)
            full = "FULL" if prop >= 1.0 else f"{prop*100:.2f}%"
            print(f"propagation={full}  time={t1-t0:.1f}s")

    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "diffusion_rounds.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
