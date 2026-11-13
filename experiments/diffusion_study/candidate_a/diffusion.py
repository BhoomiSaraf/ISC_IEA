"""Candidate A: Improved Bidirectional ARX-S Diffusion.

Mathematical Specification:
  Forward pass (k = 0..n-1):
    x_k = ((q_k ^ a_k) + u_{k-1}) mod 256
    u_k = S[((x_k <<< 3) + (a_k ^ 0x55)) mod 256], with u_{-1} = iv_f

  Backward pass (k = n-1..0):
    y_k = ((u_k ^ b_k) + c_{k+1}) mod 256
    c_k = S[((y_k <<< 5) + (b_k ^ 0xAA)) mod 256], with c_n    = iv_b

Inversion:
  Backward inverse (all k):
    arg_k = S_inv[c_k]
    rot_y = (arg_k - (b_k ^ 0xAA)) mod 256
    y_k   = rotr8(rot_y, 5)
    u_k   = ((y_k - c_{k+1}) mod 256) ^ b_k

  Forward inverse (all k):
    arg_k = S_inv[u_k]
    rot_x = (arg_k - (a_k ^ 0x55)) mod 256
    x_k   = rotr8(rot_x, 3)
    q_k   = ((x_k - u_{k-1}) mod 256) ^ a_k
"""


def rotl8(x: int, r: int) -> int:
    return ((x << r) | (x >> (8 - r))) & 0xFF


def rotr8(x: int, r: int) -> int:
    return ((x >> r) | (x << (8 - r))) & 0xFF


def forward_pass(q: bytes, a: bytes, S: list, iv_f: int) -> bytes:
    n = len(q)
    u = bytearray(n)
    prev = iv_f
    for k in range(n):
        x_k = ((q[k] ^ a[k]) + prev) & 0xFF
        prev = S[(rotl8(x_k, 3) + (a[k] ^ 0x55)) & 0xFF]
        u[k] = prev
    return bytes(u)


def backward_pass(u: bytes, b: bytes, S: list, iv_b: int) -> bytes:
    n = len(u)
    c = bytearray(n)
    nxt = iv_b
    for k in range(n - 1, -1, -1):
        y_k = ((u[k] ^ b[k]) + nxt) & 0xFF
        nxt = S[(rotl8(y_k, 5) + (b[k] ^ 0xAA)) & 0xFF]
        c[k] = nxt
    return bytes(c)


def forward_inverse(u: bytes, a: bytes, S_inv: list, iv_f: int) -> bytes:
    n = len(u)
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        arg_k = S_inv[u[k]]
        rot_x = (arg_k - (a[k] ^ 0x55)) & 0xFF
        x_k = rotr8(rot_x, 3)
        q[k] = ((x_k - u_prev) & 0xFF) ^ a[k]
    return bytes(q)


def backward_inverse(c: bytes, b: bytes, S_inv: list, iv_b: int) -> bytes:
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        arg_k = S_inv[c[k]]
        rot_y = (arg_k - (b[k] ^ 0xAA)) & 0xFF
        y_k = rotr8(rot_y, 5)
        u[k] = ((y_k - c_next) & 0xFF) ^ b[k]
    return bytes(u)


def encrypt(q: bytes, a: bytes, b: bytes, S: list, iv_f: int, iv_b: int, rounds: int = 1) -> bytes:
    data = q
    for r in range(rounds):
        u = forward_pass(data, a, S, (iv_f + r) & 0xFF)
        data = backward_pass(u, b, S, (iv_b + r) & 0xFF)
    return data


def decrypt(c: bytes, a: bytes, b: bytes, S_inv: list, iv_f: int, iv_b: int, rounds: int = 1) -> bytes:
    data = c
    for r in range(rounds - 1, -1, -1):
        u = backward_inverse(data, b, S_inv, (iv_b + r) & 0xFF)
        data = forward_inverse(u, a, S_inv, (iv_f + r) & 0xFF)
    return data

