"""ISC Image Encryption Pipeline adhering to the Standard 9-Stage Workflow.

Workflow Stages Implemented:
  Stage 1: Frozen ISC Hyperchaotic Map (a=0.9, c=0.4, d=6, w=10)
  Stage 2: Key & Nonce Handling (256-bit key + 128-bit nonce via HKDF-SHA-256 + SIV Plaintext Coupling)
  Stage 3: Sequence Generation & Burn-in (T=1024 transient removal, 16 parallel orbits)
  Stage 4: Quantization / Discretization (mantissa_mid_xor uniform byte extraction)
  Stage 5: Confusion (Adaptive Fisher-Yates Permutation per round)
  Stage 6: Diffusion (ARX-S with Candidate S2 Dynamic Galois Inversion S-box)
  Stage 7: Two Encryption Rounds with 2D Inter-Round Matrix Transposition
  Stage 8: Exact Decryption Pipeline (Bit-exact mathematical inverse with AEAD Verification)
"""

import hashlib
import hmac
import math
import struct
import numpy as np

# -----------------------------------------------------------------------------
# STAGE 1: FROZEN ISC MAP
# -----------------------------------------------------------------------------
def isc_step(x: float, y: float, a: float = 0.9, c: float = 0.4, d: float = 6.0, w: float = 10.0) -> tuple:
    denom = 1.0 + x * x + y * y
    t = c - (d / denom)
    cos_t = math.cos(t)
    sin_t = math.sin(t)
    X = 1.0 + a * (x * cos_t - y * sin_t)
    Y = a * (x * sin_t + y * cos_t)
    sin_wX = math.sin(w * X)
    sin_wY = math.sin(w * Y)
    x_next = 2.0 * sin_wX * sin_wX - 1.0
    y_next = 2.0 * sin_wY * sin_wY - 1.0
    return x_next, y_next


# -----------------------------------------------------------------------------
# STAGE 4: UNIFORM QUANTIZATION / EXTRACTION
# -----------------------------------------------------------------------------
def extract_byte(val: float) -> int:
    """mantissa_mid_xor: extracts bits 16..23 ^ bits 24..31 of double-precision float."""
    u = struct.unpack(">Q", struct.pack(">d", val))[0]
    b1 = (u >> 16) & 0xFF
    b2 = (u >> 24) & 0xFF
    return b1 ^ b2


# -----------------------------------------------------------------------------
# DYNAMIC GALOIS INVERSION S-BOX (CANDIDATE S2)
# -----------------------------------------------------------------------------
def _gf_inv(a: int) -> int:
    if a == 0:
        return 0
    res, base = 1, a
    for _ in range(7):
        p, b, hi = 0, base, 0
        for _ in range(8):
            if b & 1: p ^= base
            hi = base & 0x80
            base = (base << 1) & 0xFF
            if hi: base ^= 0x1B
            b >>= 1
        base = p
        p, b = 0, base
        for _ in range(8):
            if b & 1: p ^= res
            hi = res & 0x80
            res = (res << 1) & 0xFF
            if hi: res ^= 0x1B
            b >>= 1
        res = p
    return res

GF_INV_TABLE = [_gf_inv(x) for x in range(256)]

def build_dynamic_sbox(seed_c: int, seed_d: int):
    """S(x) = (x ^ seed_c)^(-1) ^ seed_d in GF(2^8). Returns S, S_inv."""
    S = [0] * 256
    S_inv = [0] * 256
    for x in range(256):
        y = GF_INV_TABLE[x ^ seed_c] ^ seed_d
        S[x] = y
        S_inv[y] = x
    return S, S_inv


# -----------------------------------------------------------------------------
# STAGE 2 & 3: KEY DERIVATION, SIV & ORBIT GENERATION
# -----------------------------------------------------------------------------
def compute_siv_nonce(key: bytes, nonce: bytes, plain_bytes: bytes) -> bytes:
    """Computes Synthetic IV: N_synth = HMAC-SHA256(K, nonce || len(P) || P)[:16]."""
    h = hmac.new(key, digestmod=hashlib.sha256)
    h.update(nonce)
    h.update(len(plain_bytes).to_bytes(8, "big"))
    h.update(plain_bytes)
    return h.digest()[:16]


def derive_initial_states(key: bytes, effective_nonce: bytes, num_orbits: int = 16):
    """HKDF-SHA256 derivation of initial states and parameters using effective nonce."""
    prk = hmac.new(effective_nonce, key, hashlib.sha256).digest()
    orbits = []
    for i in range(num_orbits):
        info = f"isc/orbit/{i:04d}".encode("ascii")
        t = hmac.new(prk, info + b"\x01", hashlib.sha256).digest()
        u1 = int.from_bytes(t[:8], "big") / (2**64)
        u2 = int.from_bytes(t[8:16], "big") / (2**64)
        x0 = 0.01 + 0.98 * u1
        y0 = 0.01 + 0.98 * u2
        orbits.append((x0, y0))
    return orbits, prk


def generate_keystream(orbits: list, num_bytes: int, burn_in: int = 1024) -> bytes:
    """Iterate orbits through burn-in and generate uniform bytes using vectorized NumPy."""
    from isc_cipher.isc_step import step_vec
    k = len(orbits)
    xs = np.array([o[0] for o in orbits], dtype=np.float64)
    ys = np.array([o[1] for o in orbits], dtype=np.float64)

    # Vectorized Burn-in
    for _ in range(burn_in):
        xs, ys = step_vec(xs, ys, profile=2)

    # Harvest
    steps_needed = (num_bytes + 2 * k - 1) // (2 * k)
    all_x = np.empty((steps_needed, k), dtype=np.float64)
    all_y = np.empty((steps_needed, k), dtype=np.float64)
    for j in range(steps_needed):
        xs, ys = step_vec(xs, ys, profile=2)
        all_x[j] = xs
        all_y[j] = ys

    # Vectorized extraction (mantissa_mid_xor)
    u_x = all_x.view(np.uint64)
    u_y = all_y.view(np.uint64)
    b_x = ((u_x >> np.uint64(16)) ^ (u_x >> np.uint64(24))) & np.uint64(0xFF)
    b_y = ((u_y >> np.uint64(16)) ^ (u_y >> np.uint64(24))) & np.uint64(0xFF)

    raw = np.stack([b_x, b_y], axis=-1).astype(np.uint8).tobytes()
    return raw[:num_bytes]


# -----------------------------------------------------------------------------
# STAGE 5: CONFUSION (ADAPTIVE PERMUTATION)
# -----------------------------------------------------------------------------
def build_permutation(stream_bytes: bytes, n: int) -> tuple:
    """Adaptive unbiased Fisher-Yates permutation.
    Uses 2 bytes per swap if n <= 65536, else 4 bytes. Returns (pi, pi_inv).
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


def apply_permutation(data: bytes, pi: list) -> bytes:
    p_arr = np.frombuffer(data, dtype=np.uint8)
    return p_arr[pi].tobytes()


def invert_permutation(data: bytes, pi_inv: list) -> bytes:
    c_arr = np.frombuffer(data, dtype=np.uint8)
    return c_arr[pi_inv].tobytes()


# -----------------------------------------------------------------------------
# 2D INTER-ROUND MATRIX TRANSPOSITION
# -----------------------------------------------------------------------------
def transpose_intermediate(data_bytes: bytes, shape: tuple) -> bytes:
    """Applies 2D transposition (H, W) -> (W, H)."""
    if shape is None:
        return data_bytes
    arr = np.frombuffer(data_bytes, dtype=np.uint8).reshape(shape)
    if len(shape) == 2:
        return arr.T.tobytes()
    elif len(shape) == 3:
        # (H, W, C) -> (W, H, C)
        return np.transpose(arr, (1, 0, 2)).tobytes()
    return data_bytes


def transpose_inverse(data_bytes: bytes, shape: tuple) -> bytes:
    """Inverts 2D transposition (W, H) -> (H, W)."""
    if shape is None:
        return data_bytes
    if len(shape) == 2:
        H, W = shape
        arr = np.frombuffer(data_bytes, dtype=np.uint8).reshape(W, H)
        return arr.T.tobytes()
    elif len(shape) == 3:
        H, W, C = shape
        arr = np.frombuffer(data_bytes, dtype=np.uint8).reshape(W, H, C)
        return np.transpose(arr, (1, 0, 2)).tobytes()
    return data_bytes


# -----------------------------------------------------------------------------
# STAGE 6: DIFFUSION (IMPROVED ARX-S HYBRID)
# -----------------------------------------------------------------------------
def rotl8(x: int, r: int) -> int:
    return ((x << r) | (x >> (8 - r))) & 0xFF

def rotr8(x: int, r: int) -> int:
    return ((x >> r) | (x << (8 - r))) & 0xFF

def forward_arx(q: bytes, a: bytes, S: list, iv_f: int) -> bytes:
    n = len(q)
    u = bytearray(n)
    prev = iv_f
    for k in range(n):
        x_k = ((q[k] ^ a[k]) + prev) & 0xFF
        prev = S[(rotl8(x_k, 3) + (a[k] ^ 0x55)) & 0xFF]
        u[k] = prev
    return bytes(u)

def backward_arx(u: bytes, b: bytes, S: list, iv_b: int) -> bytes:
    n = len(u)
    c = bytearray(n)
    nxt = iv_b
    for k in range(n - 1, -1, -1):
        y_k = ((u[k] ^ b[k]) + nxt) & 0xFF
        nxt = S[(rotl8(y_k, 5) + (b[k] ^ 0xAA)) & 0xFF]
        c[k] = nxt
    return bytes(c)

def backward_arx_inv(c: bytes, b: bytes, S_inv: list, iv_b: int) -> bytes:
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        rot_y = (S_inv[c[k]] - (b[k] ^ 0xAA)) & 0xFF
        y_k = rotr8(rot_y, 5)
        u[k] = ((y_k - c_next) & 0xFF) ^ b[k]
    return bytes(u)

def forward_arx_inv(u: bytes, a: bytes, S_inv: list, iv_f: int) -> bytes:
    n = len(u)
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        rot_x = (S_inv[u[k]] - (a[k] ^ 0x55)) & 0xFF
        x_k = rotr8(rot_x, 3)
        q[k] = ((x_k - u_prev) & 0xFF) ^ a[k]
    return bytes(q)


# -----------------------------------------------------------------------------
# STAGE 7 & 8: COMPLETE 2-ROUND ENCRYPTION & DECRYPTION
# -----------------------------------------------------------------------------
class ISCImageCipher:
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
        pi1, pi1_inv = build_permutation(stream[offset : offset + p_len], n)
        offset += p_len
        a1 = stream[offset : offset + n]
        offset += n
        b1 = stream[offset : offset + n]
        offset += n

        # Round 2 materials
        pi2, pi2_inv = build_permutation(stream[offset : offset + p_len], n)
        offset += p_len
        a2 = stream[offset : offset + n]
        offset += n
        b2 = stream[offset : offset + n]
        offset += n

        # S-box 1 and 2
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

        # 2D Transposition (Swap rows and columns for cross-directional diffusion)
        c1_t = transpose_intermediate(c1, shape)

        # ROUND 2:
        # Confusion: Permutation 2
        q2 = apply_permutation(c1_t, m["pi2"])
        # Diffusion: Forward + Backward ARX-S (Vertical pass)
        u2 = forward_arx(q2, m["a2"], m["s2"], m["iv_f2"])
        c2 = backward_arx(u2, m["b2"], m["s2"], m["iv_b2"])

        # Final Transposition back to original orientation
        c_final = transpose_inverse(c2, shape)

        if raw or not self.use_siv:
            return c_final, n_synth
        # Default authenticated container format: 16-byte synthetic nonce prepended
        return n_synth + c_final

    def decrypt(self, cipher_data: bytes, shape: tuple = None, synth_nonce: bytes = None, verify_auth: bool = True) -> bytes:
        if self.use_siv and synth_nonce is None:
            n_synth = cipher_data[:16]
            cipher_bytes = cipher_data[16:]
        else:
            n_synth = synth_nonce if synth_nonce is not None else self.nonce
            cipher_bytes = cipher_data

        n = len(cipher_bytes)
        m = self._prepare_materials(n, n_synth)

        # Transposition to Round 2 orientation
        c2 = transpose_intermediate(cipher_bytes, shape)

        # ROUND 2 INVERSE:
        u2 = backward_arx_inv(c2, m["b2"], m["s2_inv"], m["iv_b2"])
        q2 = forward_arx_inv(u2, m["a2"], m["s2_inv"], m["iv_f2"])
        c1_t = invert_permutation(q2, m["pi2_inv"])

        # Transposition Inverse back to Round 1 orientation
        c1 = transpose_inverse(c1_t, shape)

        # ROUND 1 INVERSE:
        u1 = backward_arx_inv(c1, m["b1"], m["s1_inv"], m["iv_b1"])
        q1 = forward_arx_inv(u1, m["a1"], m["s1_inv"], m["iv_f1"])
        plain = invert_permutation(q1, m["pi1_inv"])

        # Misuse-Resistant AEAD verification
        if self.use_siv and verify_auth:
            expected_n_synth = compute_siv_nonce(self.key, self.nonce, plain)
            if expected_n_synth != n_synth:
                raise ValueError("Authentication failed: ciphertext corrupted or wrong key/nonce!")

        return plain
