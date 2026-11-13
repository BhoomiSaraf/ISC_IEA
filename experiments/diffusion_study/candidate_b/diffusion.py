"""Candidate B: Nonlinear Multi-Stream Coupled Diffusion.

Couples all 4 independently derived ISC streams:
  - a from fwd stream
  - b from bwd stream
  - d from perm stream
  - e from sbox stream

Maintains dual nonlinear state accumulators (mu, nu) driven by ciphertext feedback
and chaotic streams, ensuring Infinite Impulse Response (IIR) in both encryption
and decryption.

Forward Pass (k = 0..n-1):
  c_k = S[ ((q_k ^ a_k) + (mu_{k-1} <<< 3) + (nu_{k-1} ^ b_k)) mod 256 ]
  mu_k = S[ (mu_{k-1} + c_k + d_k) mod 256 ]
  nu_k = S[ (nu_{k-1} ^ c_k + e_k) mod 256 ]

Backward Pass (k = n-1..0):
  c'_k = S[ ((u_k ^ b_k) + (mu'_{k+1} <<< 5) + (nu'_{k+1} ^ a_k)) mod 256 ]
  mu'_k = S[ (mu'_{k+1} + c'_k + e_k) mod 256 ]
  nu'_k = S[ (nu'_{k+1} ^ c'_k + d_k) mod 256 ]
"""


def rotl8(x: int, r: int) -> int:
    return ((x << r) | (x >> (8 - r))) & 0xFF


def rotr8(x: int, r: int) -> int:
    return ((x >> r) | (x << (8 - r))) & 0xFF


def forward_coupled(q: bytes, a: bytes, b: bytes, d: bytes, e: bytes, S: list, iv_mu: int, iv_nu: int) -> bytes:
    n = len(q)
    out = bytearray(n)
    mu = iv_mu
    nu = iv_nu
    for k in range(n):
        feedback = (rotl8(mu, 3) + (nu ^ b[k])) & 0xFF
        val = S[((q[k] ^ a[k]) + feedback) & 0xFF]
        out[k] = val
        mu = S[(mu + val + d[k]) & 0xFF]
        nu = S[((nu ^ val) + e[k]) & 0xFF]
    return bytes(out)


def forward_coupled_inv(out: bytes, a: bytes, b: bytes, d: bytes, e: bytes, S_inv: list, S: list, iv_mu: int, iv_nu: int) -> bytes:
    n = len(out)
    q = bytearray(n)
    mu = iv_mu
    nu = iv_nu
    for k in range(n):
        val = out[k]
        feedback = (rotl8(mu, 3) + (nu ^ b[k])) & 0xFF
        arg = S_inv[val]
        q[k] = ((arg - feedback) & 0xFF) ^ a[k]
        # State update identical to forward pass (uses known ciphertext val)
        mu = S[(mu + val + d[k]) & 0xFF]
        nu = S[((nu ^ val) + e[k]) & 0xFF]
    return bytes(q)


def backward_coupled(u: bytes, a: bytes, b: bytes, d: bytes, e: bytes, S: list, iv_mu: int, iv_nu: int) -> bytes:
    n = len(u)
    out = bytearray(n)
    mu = iv_mu
    nu = iv_nu
    for k in range(n - 1, -1, -1):
        feedback = (rotl8(mu, 5) + (nu ^ a[k])) & 0xFF
        val = S[((u[k] ^ b[k]) + feedback) & 0xFF]
        out[k] = val
        mu = S[(mu + val + e[k]) & 0xFF]
        nu = S[((nu ^ val) + d[k]) & 0xFF]
    return bytes(out)


def backward_coupled_inv(out: bytes, a: bytes, b: bytes, d: bytes, e: bytes, S_inv: list, S: list, iv_mu: int, iv_nu: int) -> bytes:
    n = len(out)
    u = bytearray(n)
    mu = iv_mu
    nu = iv_nu
    for k in range(n - 1, -1, -1):
        val = out[k]
        feedback = (rotl8(mu, 5) + (nu ^ a[k])) & 0xFF
        arg = S_inv[val]
        u[k] = ((arg - feedback) & 0xFF) ^ b[k]
        mu = S[(mu + val + e[k]) & 0xFF]
        nu = S[((nu ^ val) + d[k]) & 0xFF]
    return bytes(u)


def encrypt(q: bytes, a: bytes, b: bytes, d: bytes, e: bytes, S: list, iv_f: tuple, iv_b: tuple) -> bytes:
    u = forward_coupled(q, a, b, d, e, S, iv_f[0], iv_f[1])
    return backward_coupled(u, a, b, d, e, S, iv_b[0], iv_b[1])


def decrypt(c: bytes, a: bytes, b: bytes, d: bytes, e: bytes, S: list, S_inv: list, iv_f: tuple, iv_b: tuple) -> bytes:
    u = backward_coupled_inv(c, a, b, d, e, S_inv, S, iv_b[0], iv_b[1])
    return forward_coupled_inv(u, a, b, d, e, S_inv, S, iv_f[0], iv_f[1])

