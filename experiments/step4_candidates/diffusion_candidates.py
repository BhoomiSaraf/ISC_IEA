"""Step 4 candidate 3b: Alternative diffusion operations to close the propagation gap.

The current diffusion uses: u_k = S[(q_k + prev + a_k) mod 256]
The modular addition has structural cancellation paths that persist regardless of round count.

Candidates:
A) XOR-based: u_k = S[q_k ^ prev ^ a_k]  — no modular cancellation
B) Pre-S-box nonlinearity: u_k = S[(S[q_k] + prev + a_k) mod 256]  — breaks cancellation with early nonlinearity
C) Bit-rotation mixing: u_k = S[(q_k + ROL(prev, 3) + a_k) mod 256]  — spreads bit influence

Each is measured for:
1. Byte-dependency propagation (target: 100%)
2. Round-trip correctness (invertible?)
3. Avalanche (bit-flip → output change fraction, target: ~50%)
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from isc_cipher.generator import build_streams
from isc_cipher.kdf import Derivation, context
from isc_cipher.sampling import build_sbox


def rol8(v, r):
    """Rotate left an 8-bit value by r positions."""
    return ((v << r) | (v >> (8 - r))) & 0xFF


# --- Candidate A: XOR-based ---

def forward_xor(q, a, S, iv):
    u = bytearray(len(q))
    prev = iv
    for k in range(len(q)):
        prev = S[q[k] ^ prev ^ a[k]]
        u[k] = prev
    return bytes(u)

def backward_xor(u, b, S, iv):
    n = len(u)
    c = bytearray(n)
    nxt = iv
    for k in range(n - 1, -1, -1):
        nxt = S[u[k] ^ nxt ^ b[k]]
        c[k] = nxt
    return bytes(c)

def inverse_xor(c, a, b, S_inv, iv_f, iv_b):
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        u[k] = S_inv[c[k]] ^ c_next ^ b[k]
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        q[k] = S_inv[u[k]] ^ u_prev ^ a[k]
    return bytes(q)


# --- Candidate B: Pre-S-box nonlinearity ---

def forward_presbox(q, a, S, iv):
    u = bytearray(len(q))
    prev = iv
    for k in range(len(q)):
        prev = S[(S[q[k]] + prev + a[k]) & 0xFF]
        u[k] = prev
    return bytes(u)

def backward_presbox(u, b, S, iv):
    n = len(u)
    c = bytearray(n)
    nxt = iv
    for k in range(n - 1, -1, -1):
        nxt = S[(S[u[k]] + nxt + b[k]) & 0xFF]
        c[k] = nxt
    return bytes(c)

def inverse_presbox(c, a, b, S_inv, iv_f, iv_b):
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        u[k] = S_inv[(S_inv[c[k]] - c_next - b[k]) % 256]
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        q[k] = S_inv[(S_inv[u[k]] - u_prev - a[k]) % 256]
    return bytes(q)


# --- Candidate C: Bit-rotation mixing ---

def forward_rotmix(q, a, S, iv):
    u = bytearray(len(q))
    prev = iv
    for k in range(len(q)):
        prev = S[(q[k] + rol8(prev, 3) + a[k]) & 0xFF]
        u[k] = prev
    return bytes(u)

def backward_rotmix(u, b, S, iv):
    n = len(u)
    c = bytearray(n)
    nxt = iv
    for k in range(n - 1, -1, -1):
        nxt = S[(u[k] + rol8(nxt, 3) + b[k]) & 0xFF]
        c[k] = nxt
    return bytes(c)

def inverse_rotmix(c, a, b, S_inv, iv_f, iv_b):
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        u[k] = (S_inv[c[k]] - rol8(c_next, 3) - b[k]) % 256
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        q[k] = (S_inv[u[k]] - rol8(u_prev, 3) - a[k]) % 256
    return bytes(q)


# --- Candidate D: XOR + rotation (combines A and C) ---

def forward_xorrot(q, a, S, iv):
    u = bytearray(len(q))
    prev = iv
    for k in range(len(q)):
        prev = S[q[k] ^ rol8(prev, 3) ^ a[k]]
        u[k] = prev
    return bytes(u)

def backward_xorrot(u, b, S, iv):
    n = len(u)
    c = bytearray(n)
    nxt = iv
    for k in range(n - 1, -1, -1):
        nxt = S[u[k] ^ rol8(nxt, 3) ^ b[k]]
        c[k] = nxt
    return bytes(c)

def inverse_xorrot(c, a, b, S_inv, iv_f, iv_b):
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        u[k] = S_inv[c[k]] ^ rol8(c_next, 3) ^ b[k]
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        q[k] = S_inv[u[k]] ^ rol8(u_prev, 3) ^ a[k]
    return bytes(q)


CANDIDATES = {
    "original": {
        "forward": None, "backward": None, "inverse": None,  # filled from isc_cipher.diffusion
    },
    "A_xor": {
        "forward": forward_xor, "backward": backward_xor, "inverse": inverse_xor,
    },
    "B_presbox": {
        "forward": forward_presbox, "backward": backward_presbox, "inverse": inverse_presbox,
    },
    "C_rotmix": {
        "forward": forward_rotmix, "backward": backward_rotmix, "inverse": inverse_rotmix,
    },
    "D_xorrot": {
        "forward": forward_xorrot, "backward": backward_xorrot, "inverse": inverse_xorrot,
    },
}


def test_roundtrip(fwd_fn, bwd_fn, inv_fn, S, S_inv, a, b, iv_f, iv_b, n):
    """Verify encrypt→decrypt round-trip."""
    plaintext = bytes(range(n)) if n <= 256 else bytes(np.random.RandomState(42).randint(0, 256, n, dtype=np.uint8))
    u = fwd_fn(plaintext, a, S, iv_f)
    ct = bwd_fn(u, b, S, iv_b)
    recovered = inv_fn(ct, a, b, S_inv, iv_f, iv_b)
    return plaintext == recovered


def measure_propagation(fwd_fn, bwd_fn, S, a, b, iv_f, iv_b, n, sample_positions=None):
    """Byte-dependency propagation measurement."""
    base_plain = bytes(range(n)) if n <= 256 else bytes(np.random.RandomState(42).randint(0, 256, n, dtype=np.uint8))
    u = fwd_fn(base_plain, a, S, iv_f)
    base_ct = bwd_fn(u, b, S, iv_b)

    if sample_positions is None:
        positions = range(n)
    else:
        positions = sorted(np.random.RandomState(99).choice(n, min(sample_positions, n), replace=False))

    deps = 0
    total = 0
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


def measure_avalanche(fwd_fn, bwd_fn, S, a, b, iv_f, iv_b, n, n_trials=100):
    """Bit-level avalanche: flip one bit in plaintext, measure fraction of output bits that change."""
    rng = np.random.RandomState(42)
    fracs = []
    for _ in range(n_trials):
        p = bytes(rng.randint(0, 256, n, dtype=np.uint8))
        u = fwd_fn(p, a, S, iv_f)
        ct1 = bwd_fn(u, b, S, iv_b)

        pos = rng.randint(0, n)
        bit = rng.randint(0, 8)
        p2 = bytearray(p)
        p2[pos] ^= (1 << bit)
        u2 = fwd_fn(bytes(p2), a, S, iv_f)
        ct2 = bwd_fn(u2, b, S, iv_b)

        ct1_bits = np.unpackbits(np.frombuffer(ct1, dtype=np.uint8))
        ct2_bits = np.unpackbits(np.frombuffer(ct2, dtype=np.uint8))
        fracs.append(float(np.mean(ct1_bits != ct2_bits)))
    return float(np.mean(fracs)), float(np.std(fracs))


def main():
    from isc_cipher import diffusion

    CANDIDATES["original"]["forward"] = diffusion.forward
    CANDIDATES["original"]["backward"] = diffusion.backward
    CANDIDATES["original"]["inverse"] = diffusion.inverse_ref

    key = b"ab" * 32
    nonce = b"cd" * 8
    h, w, c = 8, 8, 1
    n = h * w * c  # 64 bytes

    ctx = context(1, 0, h, w, c)
    der = Derivation(key, nonce, ctx)
    streams = build_streams(der.seeds(), backend="numpy", profile=1)
    S, S_inv = build_sbox(streams["sbox"])
    a = streams["fwd"].take(n)
    b = streams["bwd"].take(n)
    iv_f, iv_b = der.ivs()

    results = []

    for name, fns in CANDIDATES.items():
        print(f"\n=== {name} ===")
        fwd, bwd, inv = fns["forward"], fns["backward"], fns["inverse"]

        # Round-trip
        rt = test_roundtrip(fwd, bwd, inv, S, S_inv, a, b, iv_f, iv_b, n)
        print(f"  Round-trip: {'PASS' if rt else 'FAIL'}")

        # Propagation
        t0 = time.time()
        prop = measure_propagation(fwd, bwd, S, a, b, iv_f, iv_b, n)
        t1 = time.time()
        full = "FULL (100%)" if prop >= 1.0 else f"{prop*100:.2f}%"
        print(f"  Propagation: {full} ({t1-t0:.2f}s)")

        # Avalanche
        aval_mean, aval_std = measure_avalanche(fwd, bwd, S, a, b, iv_f, iv_b, n)
        print(f"  Avalanche: {aval_mean*100:.2f}% ± {aval_std*100:.2f}% (target: ~50%)")

        results.append({
            "candidate": name,
            "n_bytes": n,
            "roundtrip_pass": rt,
            "propagation": round(prop, 6),
            "propagation_pct": f"{prop*100:.2f}",
            "avalanche_mean": round(aval_mean, 4),
            "avalanche_std": round(aval_std, 4),
        })

    # Also test at larger size (n=1024) for propagation only
    print("\n--- Larger size (n=1024) ---")
    h2, w2, c2 = 32, 32, 1
    n2 = h2 * w2 * c2
    ctx2 = context(1, 0, h2, w2, c2)
    der2 = Derivation(key, nonce, ctx2)
    streams2 = build_streams(der2.seeds(), backend="numpy", profile=1)
    S2, S_inv2 = build_sbox(streams2["sbox"])
    a2 = streams2["fwd"].take(n2)
    b2 = streams2["bwd"].take(n2)
    iv_f2, iv_b2 = der2.ivs()

    for name, fns in CANDIDATES.items():
        fwd, bwd = fns["forward"], fns["backward"]
        prop = measure_propagation(fwd, bwd, S2, a2, b2, iv_f2, iv_b2, n2, sample_positions=64)
        full = "FULL (100%)" if prop >= 1.0 else f"{prop*100:.2f}%"
        print(f"  {name}: propagation={full}")
        results.append({
            "candidate": name,
            "n_bytes": n2,
            "propagation": round(prop, 6),
            "propagation_pct": f"{prop*100:.2f}",
            "note": "sampled 64 positions",
        })

    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "diffusion_candidates.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
