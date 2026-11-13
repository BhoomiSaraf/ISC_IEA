"""Baseline Original Diffusion (Stage 6 of ISC-IMG v1).

Equations:
  Forward:   u_k = S[(q_k + u_{k-1} + a_k) mod 256], u_{-1} = iv_f
  Backward:  c_k = S[(u_k + c_{k+1} + b_k) mod 256], c_n    = iv_b

Decryption / Inversion:
  u_k = (S_inv[c_k] - c_{k+1} - b_k) mod 256
  q_k = (S_inv[u_k] - u_{k-1} - a_k) mod 256
"""

from isc_cipher.diffusion import forward, backward, inverse_ref, inverse_np


def encrypt(q: bytes, a: bytes, b: bytes, S: list, iv_f: int, iv_b: int) -> bytes:
    u = forward(q, a, S, iv_f)
    return backward(u, b, S, iv_b)


def decrypt(c: bytes, a: bytes, b: bytes, S_inv: list, iv_f: int, iv_b: int, backend: str = "reference") -> bytes:
    if backend == "numpy":
        return inverse_np(c, a, b, S_inv, iv_f, iv_b)
    return inverse_ref(c, a, b, S_inv, iv_f, iv_b)

