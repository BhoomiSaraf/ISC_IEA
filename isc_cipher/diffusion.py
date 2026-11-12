"""Stage 6: two-pass chained diffusion with S-box and its inverse (algorithm_design.md §9).

Forward,  k = 0..n-1 :  u_k = S[(q_k + u_{k-1} + a_k) mod 256],  u_{-1} = iv_f
Backward, k = n-1..0 :  c_k = S[(u_k + c_{k+1} + b_k) mod 256],  c_n    = iv_b
Inverse (every k independently):
    u_k = (S_inv[c_k] - c_{k+1} - b_k) mod 256
    q_k = (S_inv[u_k] - u_{k-1} - a_k) mod 256
Encryption is necessarily sequential. Decryption is implemented twice, as a scalar loop
(reference) and vectorised (numpy), so that the two backends do not share inverse code.
"""


def forward(q, a, S, iv_f):
    u = bytearray(len(q))
    prev = iv_f
    for k in range(len(q)):
        prev = S[(q[k] + prev + a[k]) & 0xFF]
        u[k] = prev
    return bytes(u)


def backward(u, b, S, iv_b):
    n = len(u)
    c = bytearray(n)
    nxt = iv_b
    for k in range(n - 1, -1, -1):
        nxt = S[(u[k] + nxt + b[k]) & 0xFF]
        c[k] = nxt
    return bytes(c)


def inverse_ref(c, a, b, S_inv, iv_f, iv_b):
    """Scalar inverse of backward then forward. Returns q."""
    n = len(c)
    u = bytearray(n)
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        u[k] = (S_inv[c[k]] - c_next - b[k]) % 256
    q = bytearray(n)
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        q[k] = (S_inv[u[k]] - u_prev - a[k]) % 256
    return bytes(q)


def inverse_np(c, a, b, S_inv, iv_f, iv_b):
    """Vectorised inverse (int16 arithmetic, explicit mod 256). Returns q."""
    import numpy as np
    sinv = np.array(S_inv, dtype=np.int16)
    cc = np.frombuffer(c, dtype=np.uint8).astype(np.int16)
    aa = np.frombuffer(a, dtype=np.uint8).astype(np.int16)
    bb = np.frombuffer(b, dtype=np.uint8).astype(np.int16)
    c_next = np.append(cc[1:], np.int16(iv_b))
    u = np.mod(sinv[cc] - c_next - bb, 256)
    u_prev = np.insert(u[:-1], 0, np.int16(iv_f))
    q = np.mod(sinv[u] - u_prev - aa, 256)
    return q.astype(np.uint8).tobytes()
