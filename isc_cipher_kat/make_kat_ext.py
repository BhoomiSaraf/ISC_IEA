"""KAT 1 extension (approved revision-3 Change 3): 26,000 sin/cos arguments from real ISC orbits.

    python isc_cipher_kat/make_kat_ext.py        (E1, project root; runs the C oracle through WSL)

* Arguments: the C oracle re-runs the burn-in trajectories (traj mode) of the 256 stream-KAT lanes
  (public test key, nonce, 64x64x3). For every burn-in state s_i (the state before step i+1, starting
  with the initial state), in lane order then step order, the next step's arguments t, omega*X and
  omega*Y are computed with the specified arithmetic (sin/cos of t from R1; this only selects the
  arguments). The first 26,000 arguments are kept.
* Expected sin/cos: the C oracle (trig mode), i.e. independent of the Python implementations.
* Accuracy: the deviation from mpmath (200-bit) in ulps is recorded for every argument of BOTH files
  (74,063 + 26,000), per fdlibm branch.
Writes vectors/trig_kat_ext.txt.gz and vectors/trig_accuracy_by_branch.json; refuses to overwrite.
The existing vector files are not modified.
"""

import gzip
import hashlib
import json
import math
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "isc_cipher_kat"))

from make_kat import run_oracle, d2h, h2d, traj_from_oracle  # noqa: E402
from isc_cipher import fdlibm_ref as F  # noqa: E402
from isc_cipher.isc_step import A, C, D, W  # noqa: E402

VEC = os.path.join(ROOT, "isc_cipher_kat", "vectors")
N_EXT = 26000


def step_args(x, y):
    """Arguments t, omega*X, omega*Y of the step from (x, y), with the §6.1 operation order."""
    t = C - D / (1.0 + (x * x + y * y))
    ct, st = F.cos(t), F.sin(t)
    X = 1.0 + A * ((x * ct) - (y * st))
    Y = A * ((x * st) + (y * ct))
    return [t, W * X, W * Y]


def branch_of(x):
    """fdlibm branch taken for argument x (identical for sin and cos)."""
    ix = F.hi(x) & 0x7FFFFFFF
    if ix <= 0x3FE921FB:
        return "direct |x|<=pi/4"
    if ix < 0x4002D97C:
        return "n=+-1 (near pi/2)" if ix == 0x3FF921FB else "n=+-1"
    if ix > 0x413921FB:
        return "large (unreachable)"
    t = abs(x)
    n = int(t * F.invpio2 + F.half)
    fn = float(n)
    r = t - fn * F.pio2_1
    w = fn * F.pio2_1t
    if n < 32 and ix != F.NPIO2_HW[n - 1]:
        return "medium, 1 reduction"
    j = ix >> 20
    y0 = r - w
    if j - ((F.hi(y0) >> 20) & 0x7FF) <= 16:
        return "medium, 1 reduction"
    tt = r
    w = fn * F.pio2_2
    r = tt - w
    w = fn * F.pio2_2t - ((tt - r) - w)
    y0 = r - w
    if j - ((F.hi(y0) >> 20) & 0x7FF) <= 49:
        return "medium, 2 reductions"
    return "medium, 3 reductions"


def ulp_dev(got, exact, mpmath):
    e = float(exact)
    u = math.ulp(e) if e != 0.0 else 5e-324
    return float(abs(mpmath.mpf(got) - exact) / u)


def main():
    import mpmath
    out_vec = os.path.join(VEC, "trig_kat_ext.txt.gz")
    out_acc = os.path.join(VEC, "trig_accuracy_by_branch.json")
    for p in (out_vec, out_acc):
        if os.path.exists(p):
            sys.exit(f"refusing to overwrite {p}")
    kat = json.load(open(os.path.join(VEC, "stream_kat.json")))
    ics = [(h2d(a), h2d(b)) for g in ("sbox", "perm", "fwd", "bwd") for a, b in kat["streams"][g]["initial_states"]]
    args = []
    for lane_ic in ics:
        res = traj_from_oracle([lane_ic], 1024, 0)[0]
        states = [lane_ic] + [(h2d(xh), h2d(yh)) for xh, yh in res["B"][:-1]]
        for x, y in states:
            args.extend(step_args(x, y))
            if len(args) >= N_EXT:
                break
        if len(args) >= N_EXT:
            break
    args = args[:N_EXT]
    out = run_oracle("trig", "".join(d2h(a) + "\n" for a in args))
    lines = out.splitlines()
    assert len(lines) == N_EXT and all(l.split()[0] == d2h(a) for l, a in zip(lines, args))
    with gzip.open(out_vec, "xt", encoding="ascii") as f:
        f.write("# arg_hex sin_hex cos_hex  (C oracle, fdlibm 5.3); arguments t, wX, wY from real ISC orbits "
                "(burn-in of stream-KAT lanes, lane order then step order)\n")
        f.write("\n".join(lines) + "\n")
    print("extension vectors:", len(lines))
    # per-branch accuracy over both files
    mpmath.mp.prec = 200
    rows = [l.split() for l in gzip.open(os.path.join(VEC, "trig_kat.txt.gz"), "rt") if not l.startswith("#")]
    rows += [l.split() for l in lines]
    acc = {}
    for a, s, c in rows:
        x = h2d(a)
        b = branch_of(x)
        ent = acc.setdefault(b, {"arguments": 0, "sin_max_ulp": 0.0, "cos_max_ulp": 0.0,
                                 "sin_not_correctly_rounded": 0, "cos_not_correctly_rounded": 0})
        ent["arguments"] += 1
        for name, got_h, f in (("sin", s, mpmath.sin), ("cos", c, mpmath.cos)):
            exact = f(mpmath.mpf(x))
            got = h2d(got_h)
            dev = ulp_dev(got, exact, mpmath)
            ent[f"{name}_max_ulp"] = max(ent[f"{name}_max_ulp"], dev)
            if got != float(exact):
                ent[f"{name}_not_correctly_rounded"] += 1
    total = {"arguments": len(rows), "files": ["trig_kat.txt.gz", "trig_kat_ext.txt.gz"],
             "reference": "mpmath 200-bit, rounded to binary64 for the correctly-rounded comparison",
             "ulp_definition": "|fdlibm - exact| / ulp(round(exact))",
             "by_branch": acc,
             "ext_sha256": hashlib.sha256(open(out_vec, "rb").read()).hexdigest()}
    json.dump(total, open(out_acc, "x"), indent=1)
    print(json.dumps(acc, indent=1))


if __name__ == "__main__":
    main()
