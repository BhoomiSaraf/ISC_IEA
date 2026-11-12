"""A15 (statistical predictability, gate_a_plan.md §2.2, finalised before data) and A4 (exploratory,
known-plaintext state recovery on reduced-precision ISC)."""

import time

import numpy as np

from isc_cipher.generator import BURN_IN, m_byte
from isc_cipher.isc_step import step_ref, step_vec
from isc_cipher.kdf import Derivation, context
from isc_cipher.state_map import seed_to_state
from isc_seq.extract import arccos_byte

from .common import Run, public_key, public_nonce
from .constructions import ChaChaStream

Z_THRESHOLD = 3.54           # Bonferroni: 51 ISC tests, family alpha 0.01, one-sided
LC_SEG_THRESHOLD = 10        # |L_N - N/2| > 10
LC_PROFILE_THRESHOLD = 14    # max_n |L_n - n/2| > 14


def lane_bytes(seed, n_steps):
    """R1: one lane after burn-in; returns (bytes M(x),M(y) per step, list of x values)."""
    x, y = seed_to_state(seed)
    for _ in range(BURN_IN):
        x, y = step_ref(x, y)
    out = bytearray()
    xs = []
    for _ in range(n_steps):
        x, y = step_ref(x, y)
        out.append(m_byte(x))
        out.append(m_byte(y))
        xs.append(x)
    return bytes(out), xs


def berlekamp_massey_profile(bits):
    n = len(bits)
    s = np.asarray(bits, dtype=np.uint8)
    c = np.zeros(n + 1, np.uint8)
    b = np.zeros(n + 1, np.uint8)
    c[0] = b[0] = 1
    L, m = 0, -1
    prof = np.zeros(n, np.int64)
    for i in range(n):
        d = s[i] ^ (int(np.dot(c[1:L + 1], s[i - 1::-1][:L]) & 1) if L else 0)
        if d:
            t = c.copy()
            shift = i - m
            c[shift:] ^= b[:n + 1 - shift]
            if 2 * L <= i:
                L, m, b = i + 1 - L, i, t
        prof[i] = L
    return prof


def windows(data, start, count, k=32):
    a = np.frombuffer(data, np.uint8)
    idx = np.arange(start, start + count)
    X = np.stack([a[idx - k + j] for j in range(k)], axis=1)
    return X, a[idx]


def evaluate_source(data, n_train, n_test, n_seg, seg_bits, log):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression, Ridge
    Xtr, ytr = windows(data, 32, n_train)
    Xte, yte = windows(data, len(data) - n_test, n_test)
    res = {}
    m1 = Ridge(alpha=1.0).fit(Xtr.astype(np.float32), ytr.astype(np.float32))
    pred = np.clip(np.rint(m1.predict(Xte.astype(np.float32))), 0, 255).astype(np.uint8)
    acc = float(np.mean(pred == yte))
    p0 = 1 / 256
    res["M1_byte"] = {"acc": acc, "z": (acc - p0) / np.sqrt(p0 * (1 - p0) / n_test)}
    Btr = np.unpackbits(Xtr, axis=1).astype(np.float32)
    Bte = np.unpackbits(Xte, axis=1).astype(np.float32)
    for bit in range(8):
        ttr = (ytr >> (7 - bit)) & 1
        tte = (yte >> (7 - bit)) & 1
        lr = LogisticRegression(C=1.0, max_iter=200).fit(Btr, ttr)
        a2 = float(np.mean(lr.predict(Bte) == tte))
        res[f"M2_bit{bit}"] = {"acc": a2, "z": (a2 - 0.5) / np.sqrt(0.25 / n_test)}
        hg = HistGradientBoostingClassifier(max_iter=100, random_state=0).fit(Xtr, ttr)
        a3 = float(np.mean(hg.predict(Xte) == tte))
        res[f"M3_bit{bit}"] = {"acc": a3, "z": (a3 - 0.5) / np.sqrt(0.25 / n_test)}
    bits = np.unpackbits(np.frombuffer(data[len(data) - n_test:], np.uint8))
    lc = []
    for sgm in range(n_seg):
        prof = berlekamp_massey_profile(bits[sgm * seg_bits:(sgm + 1) * seg_bits])
        nn = np.arange(1, seg_bits + 1)
        lc.append({"L_N": int(prof[-1]), "dev_final": float(prof[-1] - seg_bits / 2),
                   "profile_max_dev": float(np.max(np.abs(prof - nn / 2)))})
    res["linear_complexity"] = lc
    zmax = max(v["z"] for k, v in res.items() if k != "linear_complexity")
    lc_flag = any(abs(s["dev_final"]) > LC_SEG_THRESHOLD or s["profile_max_dev"] > LC_PROFILE_THRESHOLD for s in lc)
    res["max_z"] = zmax
    res["z_flag"] = zmax > Z_THRESHOLD
    res["lc_flag"] = lc_flag
    log(f"  max z = {zmax:.2f}, LC flag = {lc_flag}")
    return res


def a15(mode):
    full = mode == "full"
    n_bytes = 2_200_000 if full else 22_000
    n_train = 1_000_000 if full else 10_000
    n_test = 1_000_000 if full else 10_000
    n_seg, seg_bits = (20, 10_000) if full else (2, 2_000)
    cfg = {"bytes_per_source": n_bytes, "train": n_train, "test": n_test, "lc_segments": n_seg, "lc_segment_bits": seg_bits,
           "z_threshold": Z_THRESHOLD, "lc_thresholds": [LC_SEG_THRESHOLD, LC_PROFILE_THRESHOLD],
           "spec": "research/gate_a_plan.md §2.2 (revision B)"}
    run = Run("A15_predict", mode, cfg)
    der = Derivation(public_key("A15"), public_nonce("A15"), context(1, 1, 64, 64, 3))
    seeds = der.seeds()
    t0 = time.time()
    l1, xs = lane_bytes(seeds["fwd"][0], n_bytes)        # n_bytes steps: x values for the positive control
    sources = {"ISC fwd lane 0": l1[:n_bytes], "ISC perm lane 31": lane_bytes(seeds["perm"][31], n_bytes // 2)[0],
               "ISC bwd lane 63": lane_bytes(seeds["bwd"][63], n_bytes // 2)[0],
               "CONTROL- ChaCha20 fwd": ChaChaStream(der.derive("chacha/fwd", 32)).take(n_bytes),
               "CONTROL+ arccos8 of lane 0 x": arccos_byte(np.array(xs[:n_bytes])).tobytes()}
    run.log(f"data generated in {time.time() - t0:.1f} s")
    res = {}
    for name, d in sources.items():
        run.log(f"evaluating {name}")
        res[name] = evaluate_source(d, n_train, n_test, n_seg, seg_bits, run.log)
    isc = [v for k, v in res.items() if k.startswith("ISC")]
    neg, pos = res["CONTROL- ChaCha20 fwd"], res["CONTROL+ arccos8 of lane 0 x"]
    verdict = {"method_valid": not (neg["z_flag"] or neg["lc_flag"]), "method_sensitive": pos["z_flag"] or pos["lc_flag"],
               "isc_predictability_finding": any(v["z_flag"] or v["lc_flag"] for v in isc)}
    run.write_json("raw/results.json", res)
    return run.finish({"verdict": verdict, "max_z": {k: v["max_z"] for k, v in res.items()},
                       "lc_flags": {k: v["lc_flag"] for k, v in res.items()}})


# ------------------------------------------------------------------------- A4 (exploratory)
def a4(mode):
    ks = [8] if mode == "diagnostic" else [12, 14, 16]
    run = Run("A4_state", mode, {"type": "EXPLORATORY", "model": "ISC on a k-bit grid: after every step x, y are rounded to "
                                 "multiples of 2^-(k-1); output per step = b = k//4 middle bits of each coordinate index",
                                 "ks": ks, "cap_seconds": 6 * 3600})
    rows = []
    for k in ks:
        q = 2.0 ** (k - 1)
        b = max(1, k // 4)
        shift = (k + 1 - b) // 2

        def quant(v):
            return np.round((v + 1.0) * q) / q - 1.0

        def out(v):
            idx = np.round((v + 1.0) * q).astype(np.int64)
            return (idx >> shift) & ((1 << b) - 1)

        def stepq(x, y):
            nx, ny = step_vec(x, y, 1)
            return quant(nx), quant(ny)
        rng = np.random.default_rng(400 + k)
        sx = quant(np.array([rng.uniform(-1, 1)]))
        sy = quant(np.array([rng.uniform(-1, 1)]))
        obs = []
        x, y = sx, sy
        for _ in range(64):
            x, y = stepq(x, y)
            obs.append((int(out(x)[0]), int(out(y)[0])))
        t0 = time.time()
        grid = np.arange(-1.0 * q, q + 1) / q
        # first filter step streamed over chunks of rows of the (2q+1)^2 candidate grid (bounded memory)
        keep_x, keep_y = [], []
        evals = 0
        rows_per_chunk = max(1, (1 << 20) // len(grid))
        for i0 in range(0, len(grid), rows_per_chunk):
            gy = np.repeat(grid[i0:i0 + rows_per_chunk], len(grid))
            gx = np.tile(grid, min(rows_per_chunk, len(grid) - i0))
            nx, ny = stepq(gx, gy)
            evals += len(gx)
            m = (out(nx) == obs[0][0]) & (out(ny) == obs[0][1])
            keep_x.append(nx[m])
            keep_y.append(ny[m])
            if time.time() - t0 > 6 * 3600:
                raise RuntimeError("A4 cap reached")
        cx, cy = np.concatenate(keep_x), np.concatenate(keep_y)
        r = 1
        while len(cx) > 1 and r < len(obs):
            cx, cy = stepq(cx, cy)
            evals += len(cx)
            keep = (out(cx) == obs[r][0]) & (out(cy) == obs[r][1])
            cx, cy = cx[keep], cy[keep]
            r += 1
        ok = False
        if len(cx) >= 1:
            x, y = cx[:1], cy[:1]
            ok = True
            for j in range(r, len(obs)):
                x, y = stepq(x, y)
                ok &= (int(out(x)[0]), int(out(y)[0])) == obs[j]
        rows.append({"k": k, "bits_per_coordinate_output": b, "candidates_initial": int((2 * q + 1) ** 2),
                     "steps_used": r, "candidates_left": int(len(cx)), "map_evaluations": evals,
                     "predicts_remaining_outputs": bool(ok), "seconds": round(time.time() - t0, 2)})
        run.log(f"k={k}: {rows[-1]}")
    return run.finish({"type": "EXPLORATORY", "rows": rows,
                       "note": "reduced-precision model only; says nothing directly about full binary64 ISC lanes"})
