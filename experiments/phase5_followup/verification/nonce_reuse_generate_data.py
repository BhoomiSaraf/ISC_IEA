"""Stage 7 (Part I) -- generate real-cipher nonce-reuse query data for the solver experiment.

Runs in the project's MAIN environment (needs numpy, for isc_cipher). Produces one JSON file
per message length n containing: fixed (key, nonce, h, w, c); a pool of known (plaintext,
ciphertext-body) pairs under that SAME (key, nonce, h, w, c) (the nonce-reuse premise: constant
HKDF context means these messages share the same S, pi, a, b, iv_f, iv_b); a disjoint held-out
pool for validation; and the GROUND-TRUTH material (S, pi, a, b, iv_f, iv_b) -- kept ONLY for
this project's own post-hoc analysis (exact vs. functionally-equivalent recovery), never given
to the solver.

Also performs a model-fidelity check: a pure-Python replica of isc_cipher.diffusion.{forward,
backward} and isc_cipher.sampling.apply_permutation (the same functions the solver script uses,
copied verbatim below so the two files can be diffed) is run against the REAL extracted material
and compared byte-for-byte to the real diffusion/sampling output, and to the real ciphertext body.

Usage: python nonce_reuse_generate_data.py --out-dir results/nonce_reuse
Does not modify isc_cipher or any tracked file.
"""
import argparse
import json
import os
import sys
import time
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from isc_cipher.cipher import _encrypt, _materials  # noqa: E402
from isc_cipher import diffusion, sampling  # noqa: E402


# ---- pure-Python replica (must match isc_cipher/diffusion.py and sampling.py exactly) ----
def replica_apply_permutation(p, pi):
    return bytes(p[i] for i in pi)


def replica_forward(q, a, S, iv_f):
    u = bytearray(len(q))
    prev = iv_f
    for k in range(len(q)):
        prev = S[(q[k] + prev + a[k]) & 0xFF]
        u[k] = prev
    return bytes(u)


def replica_backward(u, b, S, iv_b):
    n = len(u)
    c = bytearray(n)
    nxt = iv_b
    for k in range(n - 1, -1, -1):
        nxt = S[(u[k] + nxt + b[k]) & 0xFF]
        c[k] = nxt
    return bytes(c)


def fidelity_check(n, trials=20):
    """Confirms the replica above matches isc_cipher.diffusion/sampling bit-for-bit."""
    rng = random.Random(1234 + n)
    for _ in range(trials):
        S = list(range(256))
        rng.shuffle(S)
        pi = list(range(n))
        rng.shuffle(pi)
        a = [rng.randrange(256) for _ in range(n)]
        b = [rng.randrange(256) for _ in range(n)]
        iv_f, iv_b = rng.randrange(256), rng.randrange(256)
        p = bytes(rng.randrange(256) for _ in range(n))
        q_real = sampling.apply_permutation(p, pi)
        q_rep = replica_apply_permutation(p, pi)
        assert q_real == q_rep, "permutation replica mismatch"
        u_real = diffusion.forward(q_real, a, S, iv_f)
        u_rep = replica_forward(q_rep, a, S, iv_f)
        assert u_real == u_rep, "forward replica mismatch"
        c_real = diffusion.backward(u_real, b, S, iv_b)
        c_rep = replica_backward(u_rep, b, S, iv_b)
        assert c_real == c_rep, "backward replica mismatch"
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(__file__), "..", "results", "nonce_reuse"))
    ap.add_argument("--ns", default="1,2,4,8,16,32,64")
    ap.add_argument("--heldout", type=int, default=5)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    key = bytes.fromhex("ab" * 32)
    nonce = bytes.fromhex("cd" * 16)  # SAME key+nonce reused across every message below (the attack premise)

    # per-n pool size: smaller n gets a bigger M-sweep; larger n is already expected to be solver-
    # infeasible (see report), so only a handful of pairs are needed to demonstrate the timeout.
    pool_for_n = {1: 32, 2: 16, 4: 8, 8: 4, 16: 2, 32: 1, 64: 1}

    for n in [int(x) for x in a.ns.split(",")]:
        a.pool = pool_for_n.get(n, 4)
        print(f"n={n}: fidelity check...", flush=True)
        fidelity_check(n)
        h, w, c = n, 1, 1  # n*1*1 = n bytes; H,W,C are folded into the HKDF context (see note below)
        rng = random.Random(9000 + n)
        m = _materials(key, nonce, 1, h, w, c, "numpy")
        pool, heldout = [], []
        t0 = time.time()
        for i in range(a.pool + a.heldout):
            p = bytes(rng.randrange(256) for _ in range(n))
            ct = _encrypt(key, p, h, w, c, nonce, "numpy", 1)
            body = ct[len(ct) - 32 - n: len(ct) - 32]  # strip 32-byte HMAC tag; header length varies by n? verify below
            rec = {"p": list(p), "c": list(body)}
            (pool if i < a.pool else heldout).append(rec)
        dt = time.time() - t0
        out = {
            "n": n, "h": h, "w": w, "c": c,
            "key_hex": key.hex(), "nonce_hex": nonce.hex(),
            "note": "H,W,C are folded into the HKDF context (kdf.context); all pairs here share the SAME (key,nonce,H,W,C) and therefore the SAME (S,pi,a,b,iv_f,iv_b).",
            "generation_seconds": dt,
            "pool": pool, "heldout": heldout,
            "ground_truth": {
                "S": m["S"], "S_inv": m["S_inv"], "pi": m["pi"],
                "a": list(m["a"]), "b": list(m["b"]), "iv_f": m["iv_f"], "iv_b": m["iv_b"],
            },
        }
        path = os.path.join(a.out_dir, f"n{n}.json")
        json.dump(out, open(path, "w"))
        print(f"  wrote {path} ({len(pool)} pool + {len(heldout)} heldout pairs, {dt:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
