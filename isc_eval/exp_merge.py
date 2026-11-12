"""A6(e): POST-HOC investigation of the A6(c) diagnostic finding (state merging). Labelled post-hoc;
no pass/fail criterion. Profile 1, V1 (NumPy), frozen map, v1 unchanged.

Concepts measured separately (never inferred from one another):
  Part 1  local merging of neighbouring starting states, at two spacings:
            "grid":  d * 2^-52 (the spacing of states the key mapping can produce)
            "float": d binary64 ulps (finer than the grid for |v| < 1; mostly NOT reachable from keys)
          for d = 2^0 .. 2^20, separately for x and y: merge after 1 step (all samples) and by 64 steps
          (sub-sample), plus steps until the first differing output byte for pairs that did not merge
  Part 2  local compression: distinct one-step images (and post-burn-in images) of blocks of 1024
          consecutive grid values along x and along y
  Part 3  collisions among states produced by the ACTUAL seed -> initial-state mapping (HKDF outputs)
          before and after the 1024-step burn-in
Part 4 (impact on output bytes / predictability / state recovery) is reported from these data plus
analysis; A4 and A15 are not run here.
"""

import time

import numpy as np
from scipy.stats import beta

from isc_cipher.generator import BURN_IN
from isc_cipher.isc_step import step_vec
from isc_cipher.kdf import hkdf_expand, hkdf_extract
from isc_cipher.state_map import seed_to_state

from .common import PUBLIC_SEED_SALT, Run

G = 2.0 ** -52


def cp(k, n):
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return [lo, hi]


def grid_ints(rng, n):
    return rng.integers(0, 2 ** 53, n, dtype=np.int64)


def to_coord(m):
    return m.astype(np.float64) * G - 1.0


def same(ax, ay, bx, by):
    return (ax.view(np.uint64) == bx.view(np.uint64)) & (ay.view(np.uint64) == by.view(np.uint64))


def mbytes(v):
    return (v.view(np.uint64) >> np.uint64(8)) & np.uint64(0xFF)


def perturb(base_m, base_v, d, spacing):
    """Neighbour at distance d (grid steps or float ulps). Returns (values, valid mask)."""
    if spacing == "grid":
        m2 = base_m + d
        valid = m2 < 2 ** 53
        return to_coord(np.where(valid, m2, base_m)), valid
    bits = base_v.view(np.uint64) + np.uint64(d)          # d ulps away from zero (sign kept)
    v2 = bits.view(np.float64)
    valid = np.isfinite(v2) & (np.abs(v2) < 1.0) & (base_v != 0.0)
    return np.where(valid, v2, base_v), valid


def part1(run, rng, n1, n_multi, ds, multi_ds, steps_multi):
    rows = []
    base_mx, base_my = grid_ints(rng, n1), grid_ints(rng, n1)
    bx, by = to_coord(base_mx), to_coord(base_my)
    b1x, b1y = step_vec(bx, by, 1)
    mag_bins = [(0.0, 0.25), (0.25, 0.5), (0.5, 1.0)]
    for spacing in ("grid", "float"):
        for coord in ("x", "y"):
            for d in ds:
                t0 = time.time()
                if coord == "x":
                    px, valid = perturb(base_mx, bx, d, spacing)
                    py = by
                    mag = np.abs(bx)
                else:
                    py, valid = perturb(base_my, by, d, spacing)
                    px = bx
                    mag = np.abs(by)
                p1x, p1y = step_vec(px, py, 1)
                merged1 = same(b1x, b1y, p1x, p1y) & valid
                nv = int(valid.sum())
                k = int(merged1.sum())
                row = {"spacing": spacing, "coord": coord, "d": d, "valid_pairs": nv, "merged_step1": k,
                       "rate_step1": k / nv, "ci95_step1": cp(k, nv),
                       "rate_step1_by_magnitude": {f"[{lo},{hi})": (float(merged1[(mag >= lo) & (mag < hi)].sum() / max(1, (valid & (mag >= lo) & (mag < hi)).sum())))
                                                   for lo, hi in mag_bins}}
                if d in multi_ds:
                    sl = slice(0, n_multi)
                    ax, ay = b1x[sl].copy(), b1y[sl].copy()
                    cx, cy = p1x[sl].copy(), p1y[sl].copy()
                    v = valid[sl]
                    merged_by = same(ax, ay, cx, cy)
                    first_out = np.where(merged_by, -1, np.where((mbytes(ax) != mbytes(cx)) | (mbytes(ay) != mbytes(cy)), 1, 0)).astype(np.int64)
                    for s in range(2, steps_multi + 1):
                        ax, ay = step_vec(ax, ay, 1)
                        cx, cy = step_vec(cx, cy, 1)
                        merged_by |= same(ax, ay, cx, cy)
                        diff_out = (mbytes(ax) != mbytes(cx)) | (mbytes(ay) != mbytes(cy))
                        first_out = np.where((first_out == 0) & diff_out, s, first_out)
                    km = int((merged_by & v).sum())
                    nonm = v & ~merged_by
                    fo = first_out[nonm & (first_out > 0)]
                    row.update({"multi_pairs": int(v.sum()), "merged_by_step_%d" % steps_multi: km,
                                "rate_by_step_%d" % steps_multi: km / int(v.sum()), "ci95_by_step": cp(km, int(v.sum())),
                                "later_merges_after_step1": km - int((merged1[sl] & v).sum()),
                                "nonmerged_first_output_byte_difference_step": {
                                    "min": int(fo.min()) if fo.size else None, "median": float(np.median(fo)) if fo.size else None,
                                    "max": int(fo.max()) if fo.size else None,
                                    "never_within_%d" % steps_multi: int((nonm & (first_out == 0)).sum())}})
                row["seconds"] = round(time.time() - t0, 1)
                rows.append(row)
                run.log(f"P1 {spacing} {coord} d={d}: step1 rate {row['rate_step1']:.4f}"
                        + (f", by {steps_multi}: {row['rate_by_step_%d' % steps_multi]:.4f}" if d in multi_ds else ""))
    return rows


def count_distinct_rows(kx, ky):
    key = (kx.view(np.uint64) * np.uint64(0x9E3779B97F4A7C15)) ^ ky.view(np.uint64)   # 64-bit hash of the pair
    s = np.sort(key, axis=1)
    return 1 + (s[:, 1:] != s[:, :-1]).sum(axis=1)


def part2(run, rng, blocks1, blocks_burn, B=1024):
    out = {}
    for coord in ("x", "y"):
        res = {}
        for label, nb, steps in (("after_1_step", blocks1, 1), ("after_burn_in_1024", blocks_burn, BURN_IN)):
            t0 = time.time()
            distinct = []
            chunk = max(1, (1 << 20) // B)
            for b0 in range(0, nb, chunk):
                nbc = min(chunk, nb - b0)
                start = rng.integers(0, 2 ** 53 - B, nbc, dtype=np.int64)
                other = to_coord(grid_ints(rng, nbc))
                line = to_coord((start[:, None] + np.arange(B)[None, :]).ravel())
                oth = np.repeat(other, B)
                x, y = (line, oth) if coord == "x" else (oth, line)
                for _ in range(steps):
                    x, y = step_vec(x, y, 1)
                distinct.append(count_distinct_rows(x.reshape(nbc, B), y.reshape(nbc, B)))
            dist = np.concatenate(distinct)
            comp = np.log2(B / dist)
            res[label] = {"blocks": int(nb), "block_size": B, "distinct_mean": float(dist.mean()),
                          "distinct_min": int(dist.min()), "distinct_quantiles_5_50_95": np.quantile(dist, [0.05, 0.5, 0.95]).tolist(),
                          "log2_compression_mean": float(comp.mean()), "log2_compression_max": float(comp.max()),
                          "seconds": round(time.time() - t0, 1)}
            run.log(f"P2 {coord} {label}: distinct mean {dist.mean():.1f}/{B}, log2 compression mean {comp.mean():.3f}")
        out[coord] = res
    return out


def part3(run, m):
    t0 = time.time()
    prk = hkdf_extract(PUBLIC_SEED_SALT, b"A6e/part3")
    st = [seed_to_state(hkdf_expand(prk, f"seed/{i}".encode(), 16)) for i in range(m)]
    x = np.array([s[0] for s in st])
    y = np.array([s[1] for s in st])

    def dup(a, b):
        pairs = np.stack([a.view(np.uint64), b.view(np.uint64)], axis=1)
        return int(len(pairs) - len(np.unique(pairs, axis=0)))
    d0 = dup(x, y)
    for _ in range(BURN_IN):
        x, y = step_vec(x, y, 1)
    d1 = dup(x, y)
    # lower bound on the effective number E of post-burn-in states under a uniform-model ASSUMPTION:
    # P(no collision) ~ exp(-m^2 / (2E)); zero collisions => E >= m^2 / (2 ln(1/0.05)) at 95%
    bound = (m * m) / (2 * np.log(20)) if d1 == 0 else None
    res = {"seeds": m, "seed_source": "HKDF-SHA-256(salt = public seed salt, IKM = 'A6e/part3'), labels seed/<i>, 16 bytes -> isc_cipher.state_map",
           "duplicate_initial_states": d0, "duplicate_states_after_burn_in": d1,
           "uniform_model_95pct_lower_bound_on_distinct_post_burn_in_states": bound,
           "log2_bound": float(np.log2(bound)) if bound else None, "seconds": round(time.time() - t0, 1)}
    run.log(f"P3: {res}")
    return res


def a6e(mode):
    full = mode == "full"
    cfg = {"label": "POST-HOC investigation of the A6(c) diagnostic finding; no pass/fail criterion",
           "seed": 6005, "part1_samples": 10 ** 6 if full else 2000, "part1_multi_samples": 10 ** 5 if full else 500,
           "distances": [2 ** j for j in range(21)] if full else [1, 2, 1024],
           "multi_step_distances": [1, 2, 4, 16, 256, 2 ** 20] if full else [1],
           "multi_steps": 64, "part2_blocks_after_1_step": 10 ** 4 if full else 20, "part2_blocks_after_burn_in": 1000 if full else 4,
           "part3_seeds": 2 ** 18 if full else 2 ** 10, "profile": 1, "backend": "V1 (NumPy)"}
    run = Run("A6e_merge_posthoc", mode, cfg)
    rng = np.random.default_rng(cfg["seed"])
    p1 = part1(run, rng, cfg["part1_samples"], cfg["part1_multi_samples"], cfg["distances"], cfg["multi_step_distances"], cfg["multi_steps"])
    run.write_json("raw/part1_local_merging.json", p1)
    p2 = part2(run, rng, cfg["part2_blocks_after_1_step"], cfg["part2_blocks_after_burn_in"])
    run.write_json("raw/part2_block_compression.json", p2)
    p3 = part3(run, cfg["part3_seeds"])
    run.write_json("raw/part3_seed_mapped_collisions.json", p3)
    return run.finish({"label": cfg["label"], "part1_rows": len(p1), "part2": p2, "part3": p3})
