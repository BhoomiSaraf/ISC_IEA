"""Stage 7 (Part I) -- SMT-based nonce-reuse structural-recovery attempt against the ACTUAL
ISC cipher's confusion/diffusion equations (not a reduced-alphabet toy model).

Runs inside the ISOLATED venv `.venv_z3` (only dependency: z3-solver). Reads the JSON files
written by nonce_reuse_generate_data.py (run in the main project environment); does not import
isc_cipher and does not need numpy.

Model (must match isc_cipher/diffusion.py + isc_cipher/sampling.py -- see the verbatim replica
functions in nonce_reuse_generate_data.py, whose fidelity against the real modules is checked
there before any data here is produced):
  Unknowns shared across all M known pairs (the nonce-reuse premise -- same key,nonce,H,W,C):
    S   : bijection on Z_256                       (256 BitVec(8), Distinct)
    pi  : permutation of {0..n-1}                  (n Int vars in [0,n), Distinct)
    a,b : n bytes each                             (BitVec(8))
    iv_f, iv_b : 1 byte each                        (BitVec(8))
  Per message i (M of them): q^i_k = p^i[pi(k)]; u^i_k = S[(q^i_k + u^i_{k-1} + a_k) mod 256]
  (u^i_{-1}=iv_f); c^i_k = S[(u^i_k + c^i_{k+1} + b_k) mod 256] (c^i_n=iv_b). BitVec(8) addition
  wraps mod 256 natively, matching the real code's explicit `& 0xFF`.

For each n, sweeps M (number of known pairs given to the solver) with a wall-clock timeout per
instance, and on SAT, validates the extracted candidate against held-out pairs NOT given to the
solver (both directions: predicting ciphertext from a held-out plaintext, and decrypting a
held-out ciphertext), exactly mirroring Phase 4E's E5 success criterion. Records n, M, status
(sat/unsat/unknown-timeout), wall time, held-out accuracy, and whether the candidate equals the
ground-truth material (kept in the data file only for this analysis, never given to the solver).

Usage (inside .venv_z3): python nonce_reuse_solve.py --data-dir ../results/nonce_reuse
  --out ../results/nonce_reuse_experiments.csv --timeout-ms 90000
"""
import argparse
import csv
import glob
import json
import os
import time

from z3 import BitVec, BitVecVal, Int, Distinct, Solver, sat, If


def replica_forward(q, a, S, iv_f):
    u = [0] * len(q)
    prev = iv_f
    for k in range(len(q)):
        prev = S[(q[k] + prev + a[k]) & 0xFF]
        u[k] = prev
    return u


def replica_backward(u, b, S, iv_b):
    n = len(u)
    c = [0] * n
    nxt = iv_b
    for k in range(n - 1, -1, -1):
        nxt = S[(u[k] + nxt + b[k]) & 0xFF]
        c[k] = nxt
    return c


def replica_apply_permutation(p, pi):
    return [p[i] for i in pi]


def replica_invert_permutation(q, pi):
    n = len(q)
    p = [0] * n
    for k, i in enumerate(pi):
        p[i] = q[k]
    return p


def replica_inverse(c, a, b, S_inv, iv_f, iv_b):
    n = len(c)
    u = [0] * n
    for k in range(n):
        c_next = c[k + 1] if k + 1 < n else iv_b
        u[k] = (S_inv[c[k]] - c_next - b[k]) % 256
    q = [0] * n
    for k in range(n):
        u_prev = u[k - 1] if k > 0 else iv_f
        q[k] = (S_inv[u[k]] - u_prev - a[k]) % 256
    return q


def build_and_solve(n, pairs, timeout_ms):
    s = Solver()
    s.set("timeout", timeout_ms)
    S = [BitVec(f"S_{i}", 8) for i in range(256)]
    s.add(Distinct(S))
    pi = [Int(f"pi_{k}") for k in range(n)]
    for k in range(n):
        s.add(pi[k] >= 0, pi[k] < n)
    s.add(Distinct(pi))
    a = [BitVec(f"a_{k}", 8) for k in range(n)]
    b = [BitVec(f"b_{k}", 8) for k in range(n)]
    iv_f = BitVec("iv_f", 8)
    iv_b = BitVec("iv_b", 8)

    def sel_byte_array(vals, idx):
        """vals: python list of known ints; idx: z3 Int expr in [0,len(vals)). Builds an ite chain."""
        expr = BitVecVal(vals[-1], 8)
        for j in range(len(vals) - 2, -1, -1):
            expr = If(idx == j, BitVecVal(vals[j], 8), expr)
        return expr

    for p, c in pairs:
        q = [sel_byte_array(p, pi[k]) for k in range(n)]
        u = []
        prev = iv_f
        for k in range(n):
            idx = q[k] + prev + a[k]
            # S lookup by symbolic 8-bit index: use an ite-chain over the 256 S vars.
            # Cost grows O(256) terms per application; acceptable for the n,M scales tested here.
            expr = S[255]
            for j in range(254, -1, -1):
                expr = If(idx == BitVecVal(j, 8), S[j], expr)
            u.append(expr)
            prev = u[-1]
        nxt = iv_b
        for k in range(n - 1, -1, -1):
            idx = u[k] + nxt + b[k]
            expr = S[255]
            for j in range(254, -1, -1):
                expr = If(idx == BitVecVal(j, 8), S[j], expr)
            s.add(expr == BitVecVal(c[k], 8))
            nxt = expr

    t0 = time.time()
    res = s.check()
    dt = time.time() - t0
    out = {"status": str(res), "solve_seconds": dt}
    if res == sat:
        model = s.model()
        out["S"] = [model.eval(S[i]).as_long() for i in range(256)]
        out["pi"] = [model.eval(pi[k]).as_long() for k in range(n)]
        out["a"] = [model.eval(a[k]).as_long() for k in range(n)]
        out["b"] = [model.eval(b[k]).as_long() for k in range(n)]
        out["iv_f"] = model.eval(iv_f).as_long()
        out["iv_b"] = model.eval(iv_b).as_long()
    return out


def validate_candidate(cand, n, heldout):
    """Returns (enc_correct_count, dec_correct_count, total) applying the candidate material to
    held-out pairs the solver never saw, in both directions (mirrors Phase 4E's E5 criterion)."""
    S, pi, a, b, iv_f, iv_b = cand["S"], cand["pi"], cand["a"], cand["b"], cand["iv_f"], cand["iv_b"]
    S_inv = [0] * 256
    for v, sv in enumerate(S):
        S_inv[sv] = v
    enc_ok, dec_ok = 0, 0
    for p, c in heldout:
        q = replica_apply_permutation(p, pi)
        u = replica_forward(q, a, S, iv_f)
        c_pred = replica_backward(u, b, S, iv_b)
        if c_pred == c:
            enc_ok += 1
        q_dec = replica_inverse(c, a, b, S_inv, iv_f, iv_b)
        p_dec = replica_invert_permutation(q_dec, pi)
        if p_dec == p:
            dec_ok += 1
    return enc_ok, dec_ok, len(heldout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout-ms", type=int, default=90000)
    ap.add_argument("--m-values", default="")  # optional override "n:ms;n:ms" e.g. "1:1,2,4,8"
    a = ap.parse_args()

    default_ms = {1: [1, 2, 4, 8, 16, 32], 2: [1, 2, 4, 8, 16], 4: [2, 4, 8],
                  8: [2, 4], 16: [2], 32: [1], 64: [1]}

    rows = []
    for path in sorted(glob.glob(os.path.join(a.data_dir, "n*.json"))):
        d = json.load(open(path))
        n = d["n"]
        pool, heldout = d["pool"], d["heldout"]
        gt = d["ground_truth"]
        heldout_pairs = [([x for x in r["p"]], [x for x in r["c"]]) for r in heldout]
        for M in default_ms.get(n, [1]):
            if M > len(pool):
                continue
            pairs = [([x for x in r["p"]], [x for x in r["c"]]) for r in pool[:M]]
            print(f"n={n} M={M}: solving (timeout={a.timeout_ms}ms)...", flush=True)
            res = build_and_solve(n, pairs, a.timeout_ms)
            row = {"n": n, "M": M, "status": res["status"], "solve_seconds": round(res["solve_seconds"], 2)}
            if res["status"] == "sat":
                enc_ok, dec_ok, tot = validate_candidate(res, n, heldout_pairs)
                row["heldout_total"] = tot
                row["heldout_enc_correct"] = enc_ok
                row["heldout_dec_correct"] = dec_ok
                row["heldout_fully_correct"] = (enc_ok == tot and dec_ok == tot)
                row["S_equals_ground_truth"] = (res["S"] == gt["S"])
                row["pi_equals_ground_truth"] = (res["pi"] == gt["pi"])
            print(" ", row, flush=True)
            rows.append(row)

    with open(a.out, "w", newline="") as f:
        cols = ["n", "M", "status", "solve_seconds", "heldout_total", "heldout_enc_correct",
                "heldout_dec_correct", "heldout_fully_correct", "S_equals_ground_truth", "pi_equals_ground_truth"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print("wrote", a.out)


if __name__ == "__main__":
    main()
