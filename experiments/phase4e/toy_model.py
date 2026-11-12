"""Part C: reduced toy model preserving the ESSENTIAL algebraic structure of the real cipher's
confusion+diffusion core, at a tractable alphabet size A and message length n.

Preserved: modular-additive chaining through an unknown bijective S-box (forward then backward
pass), unknown byte-position permutation, unknown IVs, identical recurrence structure to
isc_cipher/diffusion.py and isc_cipher/sampling.py (re-read directly from source for this phase).

NOT preserved (explicitly, and this does not affect the algebraic-identifiability question being
tested): the ISC chaotic map itself, HKDF, burn-in, Lemire rejection sampling. Those produce the
*values* of S/pi/a/b/iv from a (key,nonce) pair; this toy model instead draws a uniformly random
instance of each (which is what the real generator is designed to approximate for the ATTACKER's
purposes -- the attacker in all threat models considered has no way to distinguish "chaotic-map
output" from "uniform random" short of attacking the generator itself, which is out of scope for
a nonce-reuse structural question). The identifiability question asked here ("given M known
(p,c) pairs sharing the same secret tuple, can the tuple -- or an equivalent one -- be
recovered") depends only on the modular-additive/S-box/permutation algebra, not on how the
secret tuple's values were drawn.
"""
import random


def random_permutation(n, rng):
    p = list(range(n))
    rng.shuffle(p)
    return p


def invert(perm):
    inv = [0] * len(perm)
    for i, v in enumerate(perm):
        inv[v] = i
    return inv


def make_secret(A, n, seed):
    rng = random.Random(seed)
    S = random_permutation(A, rng)
    S_inv = invert(S)
    pi = random_permutation(n, rng)
    a = [rng.randrange(A) for _ in range(n)]
    b = [rng.randrange(A) for _ in range(n)]
    iv_f = rng.randrange(A)
    iv_b = rng.randrange(A)
    return {"S": S, "S_inv": S_inv, "pi": pi, "a": a, "b": b, "iv_f": iv_f, "iv_b": iv_b, "A": A, "n": n}


def apply_permutation(p, pi):
    return [p[i] for i in pi]


def invert_permutation(q, pi):
    n = len(q)
    p = [0] * n
    for k, i in enumerate(pi):
        p[i] = q[k]
    return p


def forward(q, a, S, iv_f, A):
    n = len(q)
    u = [0] * n
    prev = iv_f
    for k in range(n):
        prev = S[(q[k] + prev + a[k]) % A]
        u[k] = prev
    return u


def backward(u, b, S, iv_b, A):
    n = len(u)
    c = [0] * n
    nxt = iv_b
    for k in range(n - 1, -1, -1):
        nxt = S[(u[k] + nxt + b[k]) % A]
        c[k] = nxt
    return c


def encrypt(secret, p):
    A = secret["A"]
    q = apply_permutation(p, secret["pi"])
    u = forward(q, secret["a"], secret["S"], secret["iv_f"], A)
    c = backward(u, secret["b"], secret["S"], secret["iv_b"], A)
    return c


def decrypt(secret, c):
    A, n = secret["A"], secret["n"]
    S_inv = secret["S_inv"]
    a, b = secret["a"], secret["b"]
    iv_f, iv_b = secret["iv_f"], secret["iv_b"]
    u = [0] * n
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        u[k] = (S_inv[c[k]] - c_next - b[k]) % A
    q = [0] * n
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        q[k] = (S_inv[u[k]] - u_prev - a[k]) % A
    return invert_permutation(q, secret["pi"])


if __name__ == "__main__":
    sec = make_secret(8, 4, seed=1)
    p = [1, 2, 3, 4]
    c = encrypt(sec, p)
    assert decrypt(sec, c) == p, "toy model round-trip failed"
    print("toy model self-check OK:", p, "->", c, "-> decrypt ->", decrypt(sec, c))
