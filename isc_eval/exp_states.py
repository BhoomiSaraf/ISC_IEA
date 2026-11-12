"""A6: weak, cyclic and merging lane states (profile 1, V1).

(a) vectorised Brent cycle detection over L random grid states for up to the maximum lane length
(b) merges: duplicates among L random states after burn-in; subset continued with periodic duplicate checks
(c) neighbour divergence: initial states 1 ulp apart -> steps until max(|dx|,|dy|) > 0.1
(d) lane independence: chi-square independence of top-nibble pairs across lanes and across streams
"""

import numpy as np
from scipy.stats import chi2

from isc_cipher.generator import BURN_IN, build_streams
from isc_cipher.isc_step import step_vec
from isc_cipher.kdf import Derivation, context

from .common import Run, public_key, public_nonce

MAX_LANE_STEPS = BURN_IN + 524288          # n = 2^24: perm stream needs about 2^19 output steps


def grid_states(rng, n):
    a = rng.integers(0, 2 ** 53, n, dtype=np.int64).astype(np.float64)
    b = rng.integers(0, 2 ** 53, n, dtype=np.int64).astype(np.float64)
    return a * 2.0 ** -52 - 1.0, b * 2.0 ** -52 - 1.0


def bits_eq(a, b):
    return a.view(np.uint64) == b.view(np.uint64)


def brent_vectorised(x, y, max_steps, log=None):
    tx, ty = x.copy(), y.copy()
    hx, hy = step_vec(x, y, 1)
    L = len(x)
    power = np.ones(L, np.int64)
    lam = np.ones(L, np.int64)
    found = np.zeros(L, bool)
    lam_found = np.full(L, -1, np.int64)
    found_at = np.full(L, -1, np.int64)
    for s in range(1, max_steps):
        eq = bits_eq(hx, tx) & bits_eq(hy, ty) & ~found
        if eq.any():
            found |= eq
            lam_found[eq] = lam[eq]
            found_at[eq] = s
        reset = (power == lam) & ~found
        tx = np.where(reset, hx, tx)
        ty = np.where(reset, hy, ty)
        power = np.where(reset, power * 2, power)
        lam = np.where(reset, 0, lam)
        hx, hy = step_vec(hx, hy, 1)
        lam += 1
        if log and s % 50000 == 0:
            log(f"  brent step {s}/{max_steps}, cycles found {int(found.sum())}")
    return found, lam_found, found_at


def duplicates(x, y):
    pairs = np.stack([x.view(np.uint64), y.view(np.uint64)], axis=1)
    return int(len(pairs) - len(np.unique(pairs, axis=0)))


def a6(mode):
    full = mode == "full"
    cfg = {"a_lanes": 10000 if full else 64, "a_max_steps": MAX_LANE_STEPS if full else 3000,
           "b_lanes": 2 ** 20 if full else 2 ** 12, "b_subset": 2 ** 12 if full else 2 ** 8,
           "b_subset_steps": 2 ** 19 if full else 2 ** 10, "b_check_every": 2 ** 14 if full else 2 ** 8,
           "c_pairs": 10000 if full else 100, "d_steps": 62500 if full else 2000, "seed": 606}
    run = Run("A6_states", mode, cfg)
    rng = np.random.default_rng(cfg["seed"])
    out = {}
    # (a)
    x, y = grid_states(rng, cfg["a_lanes"])
    found, lam_f, at = brent_vectorised(x, y, cfg["a_max_steps"], run.log)
    out["a_cycles"] = {"lanes": cfg["a_lanes"], "max_steps": cfg["a_max_steps"], "cycles_found": int(found.sum()),
                       "periods": sorted(set(lam_f[found].tolist()))[:50], "first_detection_steps": sorted(at[found].tolist())[:50],
                       "finding": bool(found.any())}
    run.log(f"(a) {out['a_cycles']}")
    # (b)
    x, y = grid_states(rng, cfg["b_lanes"])
    d0 = duplicates(x, y)
    for _ in range(BURN_IN):
        x, y = step_vec(x, y, 1)
    d1 = duplicates(x, y)
    sx, sy = x[:cfg["b_subset"]].copy(), y[:cfg["b_subset"]].copy()
    checks = []
    for s in range(1, cfg["b_subset_steps"] + 1):
        sx, sy = step_vec(sx, sy, 1)
        if s % cfg["b_check_every"] == 0:
            checks.append([s, duplicates(sx, sy)])
    out["b_merges"] = {"lanes": cfg["b_lanes"], "duplicate_initial_states": d0, "duplicates_after_burn_in": d1,
                       "subset": cfg["b_subset"], "subset_checks": checks,
                       "finding": d1 > d0 or any(c[1] > 0 for c in checks)}
    run.log(f"(b) dup initial {d0}, after burn-in {d1}, subset checks max {max((c[1] for c in checks), default=0)}")
    # (c)
    x, y = grid_states(rng, cfg["c_pairs"])
    res = {}
    for which in ("x", "y"):
        ax, ay = x.copy(), y.copy()
        bx, by = (np.nextafter(x, 2.0), y.copy()) if which == "x" else (x.copy(), np.nextafter(y, 2.0))
        div = np.full(len(x), -1, np.int64)
        for s in range(1, BURN_IN + 1):
            ax, ay = step_vec(ax, ay, 1)
            bx, by = step_vec(bx, by, 1)
            hit = (np.maximum(np.abs(ax - bx), np.abs(ay - by)) > 0.1) & (div < 0)
            div[hit] = s
        res[which] = {"not_diverged_by_T": int((div < 0).sum()), "min": int(div[div > 0].min()) if (div > 0).any() else None,
                      "median": float(np.median(div[div > 0])) if (div > 0).any() else None,
                      "max": int(div.max()), "pairs": len(x)}
    out["c_neighbour_divergence"] = dict(res, finding=any(v["not_diverged_by_T"] > 0 for v in res.values()))
    run.log(f"(c) {out['c_neighbour_divergence']}")
    # (d)
    seeds = Derivation(public_key("A6/d"), public_nonce("A6/d"), context(1, 1, 64, 64, 3)).seeds()
    st = build_streams(seeds, backend="numpy", profile=1)
    steps = cfg["d_steps"]
    fwd = np.frombuffer(st["fwd"].take(steps * 128), np.uint8).reshape(steps, 64, 2).transpose(1, 0, 2).reshape(64, -1) >> 4
    bwd = np.frombuffer(st["bwd"].take(steps * 128), np.uint8).reshape(steps, 64, 2).transpose(1, 0, 2).reshape(64, -1) >> 4

    def indep_p(a, b):
        t = np.zeros((16, 16))
        np.add.at(t, (a, b), 1)
        e = t.sum(1, keepdims=True) * t.sum(0, keepdims=True) / t.sum()
        return float(chi2.sf(((t - e) ** 2 / e).sum(), 225))
    pv = [indep_p(fwd[i], fwd[j]) for i in range(64) for j in range(i + 1, 64)] + [indep_p(fwd[l], bwd[l]) for l in range(64)]
    alpha = 0.01 / len(pv)
    out["d_lane_independence"] = {"tests": len(pv), "bonferroni_alpha": alpha, "min_p": min(pv),
                                  "rejections": int(sum(p < alpha for p in pv)), "bytes_per_lane": 2 * steps,
                                  "finding": any(p < alpha for p in pv)}
    run.log(f"(d) {out['d_lane_independence']}")
    return run.finish(out)
