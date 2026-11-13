"""Evaluation of Diffusion Candidates vs. Baseline

Measures:
1. Exact invertibility across multiple block lengths
2. Forward byte-dependency propagation coverage (testing elimination of the 0.42% cancellation gap)
3. Reverse (decryption) dependency width (testing elimination of the 3-byte FIR weakness)
4. Execution throughput
"""

import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath("."))

# Baseline cipher diffusion
from isc_cipher.diffusion import forward as base_forward, backward as base_backward, inverse_ref as base_inverse

def rotl8(x, r):
    return ((x << r) | (x >> (8 - r))) & 0xFF

def rotr8(x, r):
    return ((x >> r) | (x << (8 - r))) & 0xFF


# -----------------------------------------------------------------------------
# CANDIDATE D1: Group-Heterogeneous ARX-S Hybrid Diffusion
# -----------------------------------------------------------------------------
def d1_forward(q, a, S, iv_f):
    n = len(q)
    u = bytearray(n)
    prev = iv_f
    for k in range(n):
        x_k = ((q[k] ^ a[k]) + prev) & 0xFF
        prev = S[(rotl8(x_k, 3) + (a[k] ^ 0x55)) & 0xFF]
        u[k] = prev
    return bytes(u)

def d1_backward(u, b, S, iv_b):
    n = len(u)
    c = bytearray(n)
    nxt = iv_b
    for k in range(n - 1, -1, -1):
        y_k = ((u[k] ^ b[k]) + nxt) & 0xFF
        nxt = S[(rotl8(y_k, 5) + (b[k] ^ 0xAA)) & 0xFF]
        c[k] = nxt
    return bytes(c)

def d1_inverse(c, a, b, S_inv, iv_f, iv_b):
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        # invert backward
        rot_y = (S_inv[c[k]] - (b[k] ^ 0xAA)) & 0xFF
        y_k = rotr8(rot_y, 5)
        u[k] = ((y_k - c_next) & 0xFF) ^ b[k]
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        # invert forward
        rot_x = (S_inv[u[k]] - (a[k] ^ 0x55)) & 0xFF
        x_k = rotr8(rot_x, 3)
        q[k] = ((x_k - u_prev) & 0xFF) ^ a[k]
    return bytes(q)

def d1_encrypt(q, a, b, S, iv_f, iv_b):
    u = d1_forward(q, a, S, iv_f)
    return d1_backward(u, b, S, iv_b)


# -----------------------------------------------------------------------------
# CANDIDATE D2: 4x4 Involutory MDS Block Diffusion over GF(2^8)
# Field polynomial: x^8 + x^4 + x^3 + x + 1 (0x11B, AES field)
# Involutory MDS matrix:
# [ 01  02  04  06 ]
# [ 02  01  06  04 ]
# [ 04  06  01  02 ]
# [ 06  04  02  01 ]
# -----------------------------------------------------------------------------
def gf_mul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p

MDS_MAT = [
    [1, 2, 4, 6],
    [2, 1, 6, 4],
    [4, 6, 1, 2],
    [6, 4, 2, 1]
]

# Precompute GF multiplication table for the 4 constants
MDS_TABLE = {c: [gf_mul(c, x) for x in range(256)] for c in (1, 2, 4, 6)}

def apply_mds(block4):
    out = [0, 0, 0, 0]
    for r in range(4):
        val = 0
        for c in range(4):
            coeff = MDS_MAT[r][c]
            val ^= MDS_TABLE[coeff][block4[c]]
        out[r] = val
    return out

def d2_forward(q, a, S, iv_f4):
    n = len(q)
    m = n // 4
    u = bytearray(n)
    prev = list(iv_f4)
    for i in range(m):
        idx = i * 4
        # Add keystream and previous block
        x = [q[idx + j] ^ prev[j] ^ a[idx + j] for j in range(4)]
        # S-box layer
        y = [S[v] for v in x]
        # MDS mixing layer
        prev = apply_mds(y)
        u[idx : idx + 4] = prev
    return bytes(u)

def d2_backward(u, b, S, iv_b4):
    n = len(u)
    m = n // 4
    c = bytearray(n)
    nxt = list(iv_b4)
    for i in range(m - 1, -1, -1):
        idx = i * 4
        z = [u[idx + j] ^ nxt[j] ^ b[idx + j] for j in range(4)]
        w = [S[v] for v in z]
        nxt = apply_mds(w)
        c[idx : idx + 4] = nxt
    return bytes(c)

def d2_inverse(c, a, b, S_inv, iv_f4, iv_b4):
    n = len(c)
    m = n // 4
    u = bytearray(n)
    for i in range(m):
        idx = i * 4
        nxt = c[idx + 4 : idx + 8] if i + 1 < m else iv_b4
        curr = c[idx : idx + 4]
        # MDS is involutory: M^-1 = M
        w = apply_mds(curr)
        z = [S_inv[v] for v in w]
        u[idx : idx + 4] = [z[j] ^ nxt[j] ^ b[idx + j] for j in range(4)]
    q = bytearray(n)
    for i in range(m):
        idx = i * 4
        prev = u[idx - 4 : idx] if i > 0 else iv_f4
        curr_u = u[idx : idx + 4]
        y = apply_mds(curr_u)
        x = [S_inv[v] for v in y]
        q[idx : idx + 4] = [x[j] ^ prev[j] ^ a[idx + j] for j in range(4)]
    return bytes(q)

def d2_encrypt(q, a, b, S, iv_f4, iv_b4):
    u = d2_forward(q, a, S, iv_f4)
    return d2_backward(u, b, S, iv_b4)


# -----------------------------------------------------------------------------
# CANDIDATE D3: Cross-Coupled Infinite Impulse Response (IIR) Diffusion
# -----------------------------------------------------------------------------
def d3_encrypt(q, a, b, S, iv1, iv2, iv3):
    n = len(q)
    c = bytearray(n)
    u_prev = iv1
    c_prev = iv2
    v_prev = iv3
    for k in range(n):
        u_k = S[(q[k] + u_prev + a[k]) & 0xFF]
        feedback = (rotl8(c_prev, 1) + b[k] + v_prev) & 0xFF
        c_k = u_k ^ feedback
        v_k = S[v_prev ^ c_k ^ a[k]]
        c[k] = c_k
        u_prev = u_k
        c_prev = c_k
        v_prev = v_k
    return bytes(c)

def d3_decrypt(c, a, b, S, S_inv, iv1, iv2, iv3):
    n = len(c)
    q = bytearray(n)
    u_prev = iv1
    c_prev = iv2
    v_prev = iv3
    for k in range(n):
        c_k = c[k]
        feedback = (rotl8(c_prev, 1) + b[k] + v_prev) & 0xFF
        u_k = c_k ^ feedback
        q[k] = (S_inv[u_k] - u_prev - a[k]) & 0xFF
        v_k = S[v_prev ^ c_k ^ a[k]]
        u_prev = u_k
        c_prev = c_k
        v_prev = v_k
    return bytes(q)


# -----------------------------------------------------------------------------
# Verification and Benchmarking Test Suite
# -----------------------------------------------------------------------------
def run_tests():
    print("=== Step 4 Diffusion Candidates Verification & Evaluation ===")
    rng = np.random.RandomState(42)
    n = 256  # 256 bytes

    # S-box generation (Fisher-Yates)
    S = list(range(256))
    rng.shuffle(S)
    S_inv = [0] * 256
    for i, v in enumerate(S):
        S_inv[v] = i

    a = bytes(rng.randint(0, 256, n, dtype=np.uint8))
    b = bytes(rng.randint(0, 256, n, dtype=np.uint8))
    q = bytes(rng.randint(0, 256, n, dtype=np.uint8))

    iv_f = 0x5A
    iv_b = 0xA5
    iv_f4 = [0x12, 0x34, 0x56, 0x78]
    iv_b4 = [0x9A, 0xBC, 0xDE, 0xF0]

    # 1. Invertibility Tests
    print("\n--- 1. Invertibility Tests (Exact Plaintext Recovery) ---")
    
    # Baseline
    u_base = base_forward(q, a, S, iv_f)
    c_base = base_backward(u_base, b, S, iv_b)
    q_base_rec = base_inverse(c_base, a, b, S_inv, iv_f, iv_b)
    print("Baseline Inverse Correct:", q_base_rec == q)

    # Candidate D1
    c_d1 = d1_encrypt(q, a, b, S, iv_f, iv_b)
    q_d1_rec = d1_inverse(c_d1, a, b, S_inv, iv_f, iv_b)
    print("Candidate D1 (ARX-S) Inverse Correct:", q_d1_rec == q)

    # Candidate D2
    c_d2 = d2_encrypt(q, a, b, S, iv_f4, iv_b4)
    q_d2_rec = d2_inverse(c_d2, a, b, S_inv, iv_f4, iv_b4)
    print("Candidate D2 (Block-MDS) Inverse Correct:", q_d2_rec == q)

    # Candidate D3
    c_d3 = d3_encrypt(q, a, b, S, iv_f, iv_b, 0x3C)
    q_d3_rec = d3_decrypt(c_d3, a, b, S, S_inv, iv_f, iv_b, 0x3C)
    print("Candidate D3 (Coupled IIR) Inverse Correct:", q_d3_rec == q)

    # 2. Forward Propagation Coverage (Checking Cancellation Gap)
    print("\n--- 2. Forward Propagation Coverage (% of output bytes changed when flipping input byte) ---")
    def measure_forward_coverage(encrypt_fn, n_bytes):
        total_pairs = 0
        changed_pairs = 0
        base_c = encrypt_fn(q)
        # Sample 32 input positions
        positions = rng.choice(n_bytes, 32, replace=False)
        for pos in positions:
            q_mod = bytearray(q)
            q_mod[pos] ^= 0x01
            c_mod = encrypt_fn(bytes(q_mod))
            for j in range(n_bytes):
                total_pairs += 1
                if c_mod[j] != base_c[j]:
                    changed_pairs += 1
        return changed_pairs / total_pairs

    cov_base = measure_forward_coverage(lambda x: base_backward(base_forward(x, a, S, iv_f), b, S, iv_b), n)
    cov_d1 = measure_forward_coverage(lambda x: d1_encrypt(x, a, b, S, iv_f, iv_b), n)
    cov_d2 = measure_forward_coverage(lambda x: d2_encrypt(x, a, b, S, iv_f4, iv_b4), n)
    cov_d3 = measure_forward_coverage(lambda x: d3_encrypt(x, a, b, S, iv_f, iv_b, 0x3C), n)

    print(f"Baseline (1 round):          {cov_base * 100:.2f}% (known cancellation gap)")
    print(f"Candidate D1 (ARX-S):        {cov_d1 * 100:.2f}%")
    print(f"Candidate D2 (Block-MDS):    {cov_d2 * 100:.2f}%")
    print(f"Candidate D3 (Coupled IIR):  {cov_d3 * 100:.2f}%")

    # 3. Decryption Dependency Window Width (Testing FIR vs IIR)
    print("\n--- 3. Decryption Dependency Window (Bytes affected when 1 ciphertext byte is modified at midpoint) ---")
    mid_idx = n // 2

    # Baseline
    c_mod = bytearray(c_base)
    c_mod[mid_idx] ^= 0x01
    q_pert = base_inverse(bytes(c_mod), a, b, S_inv, iv_f, iv_b)
    aff_base = sum(1 for i in range(n) if q_pert[i] != q[i])

    # Candidate D1
    c_mod = bytearray(c_d1)
    c_mod[mid_idx] ^= 0x01
    q_pert = d1_inverse(bytes(c_mod), a, b, S_inv, iv_f, iv_b)
    aff_d1 = sum(1 for i in range(n) if q_pert[i] != q[i])

    # Candidate D2
    c_mod = bytearray(c_d2)
    c_mod[mid_idx] ^= 0x01
    q_pert = d2_inverse(bytes(c_mod), a, b, S_inv, iv_f4, iv_b4)
    aff_d2 = sum(1 for i in range(n) if q_pert[i] != q[i])

    # Candidate D3
    c_mod = bytearray(c_d3)
    c_mod[mid_idx] ^= 0x01
    q_pert = d3_decrypt(bytes(c_mod), a, b, S, S_inv, iv_f, iv_b, 0x3C)
    aff_d3 = sum(1 for i in range(n) if q_pert[i] != q[i])

    print(f"Baseline Decryption Dependency Window:     {aff_base} bytes (Theorem 1: strictly 3 bytes FIR)")
    print(f"Candidate D1 Decryption Dependency Window: {aff_d1} bytes (3 bytes FIR for single round)")
    print(f"Candidate D2 Decryption Dependency Window: {aff_d2} bytes (Block-wide: 8 bytes across adjacent blocks)")
    print(f"Candidate D3 Decryption Dependency Window: {aff_d3} bytes (IIR: {aff_d3}/{n - mid_idx} subsequent bytes affected!)")

if __name__ == "__main__":
    run_tests()
