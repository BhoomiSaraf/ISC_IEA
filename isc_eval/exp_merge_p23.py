"""A6(e) Parts 2-3: POST-HOC, memory-bounded follow-up run (replaces the interrupted Parts 2-3 of
A6e_merge_posthoc_full_20261026T080320Z; Part 1 of that run is complete and is not repeated).
Labelled post-hoc; no pass/fail criterion. Profile 1, V1 (NumPy), frozen map, v1 unchanged.

  Part 2  local compression: blocks of B = 1024 CONSECUTIVE grid values along x (resp. y), the other
          coordinate a fixed random grid value per block. EXACT distinct (x, y) bit patterns per block
          at checkpoints 1, 2, 4, ..., 1024 steps (1024 = burn-in), then distinct 16-byte output
          sequences of the first 8 post-burn-in output steps.
  Part 3  collisions among states from the REAL v1 key -> state mapping: Derivation(K_j, N_j, ctx).seeds()
          (256 lane seeds per message) -> isc_cipher.state_map; public keys K_j, nonces N_j from the
          harness public seed salt. EXACT duplicates of initial states, after 1 step, after burn-in;
          within-message and overall; x-only / y-only coincidences; grid-neighbour statistics.

Memory bounds: at most MAX_LANES lanes per step_vec call (measured peak working set ~62 MB at 2^16);
results are streamed to raw/*.jsonl per batch; a free-RAM guard stops the run cleanly at a batch or
step boundary and records it as incomplete.
"""

import json
import time

import numpy as np
from scipy.stats import t as student_t

from isc_cipher.generator import BURN_IN
from isc_cipher.isc_step import step_vec
from isc_cipher.kdf import Derivation, STREAMS, LANES, context
from isc_cipher.state_map import seed_to_ints

from . import memwatch
from .common import Run, public_key, public_nonce

G = 2.0 ** -52
MAX_LANES = 1 << 16
GUARD_MB = 300
CHECKPOINTS = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
OUTPUT_STEPS = 8
PART1_SOURCE = "results/encryption_experiments/A6e_merge_posthoc_full_20261026T080320Z/raw/part1_local_merging.json"


class MemoryGuardStop(Exception):
    pass


def guard(where):
    _, avail = memwatch.system_mb()
    if avail is not None and avail < GUARD_MB:
        raise MemoryGuardStop(f"available RAM {avail:.0f} MB < {GUARD_MB} MB at {where}")


def mem_record():
    ws, peak = memwatch.process_mb()
    tot, avail = memwatch.system_mb()
    return {"working_set_mb": round(ws, 1), "peak_working_set_mb": round(peak, 1), "system_available_mb": round(avail, 1)}


def bits(v):
    return v.view(np.uint64)


def mbyte(v):
    return ((bits(v) >> np.uint64(8)) & np.uint64(0xFF)).astype(np.uint8)


def block_distinct(xb, yb):
    """Exact per-row distinct (x, y) bit patterns and the largest multiplicity; xb, yb: (nb, B) uint64."""
    nd, mx = [], []
    for i in range(xb.shape[0]):
        _, cnt = np.unique(np.stack([xb[i], yb[i]], axis=1), axis=0, return_counts=True)
        nd.append(len(cnt))
        mx.append(int(cnt.max()))
    return nd, mx


def mean_ci(v):
    v = np.asarray(v, float)
    n = len(v)
    m = float(v.mean())
    if n < 2:
        return {"n": n, "mean": m, "sd": None, "se": None, "ci95_t": None}
    sd = float(v.std(ddof=1))
    se = sd / np.sqrt(n)
    h = float(student_t.ppf(0.975, n - 1)) * se
    return {"n": n, "mean": m, "sd": sd, "se": se, "ci95_t": [m - h, m + h]}


# ---------------------------------------------------------------- Part 2

def part2(run, rng, blocks, B, batch_blocks, coords=("x", "y")):
    out = {}
    jl = open(run.path("raw", "part2_blocks.jsonl"), "x", encoding="utf-8")
    for coord in coords:
        t0 = time.time()
        rows = []
        for b0 in range(0, blocks, batch_blocks):
            guard(f"part2 {coord} batch {b0}")
            nb = min(batch_blocks, blocks - b0)
            tb = time.time()
            start = rng.integers(0, 2 ** 53 - B + 1, nb, dtype=np.int64)
            other = rng.integers(0, 2 ** 53, nb, dtype=np.int64)
            line = ((start[:, None] + np.arange(B, dtype=np.int64)[None, :]).ravel()).astype(np.float64) * G - 1.0
            oth = np.repeat(other.astype(np.float64) * G - 1.0, B)
            x, y = (line, oth) if coord == "x" else (oth, line)
            del line, oth
            per_cp = {}
            for s in range(1, BURN_IN + 1):
                x, y = step_vec(x, y, 1)
                if s in CHECKPOINTS:
                    per_cp[s] = block_distinct(bits(x).reshape(nb, B), bits(y).reshape(nb, B))
                if s % 128 == 0:
                    guard(f"part2 {coord} batch {b0} step {s}")
            outb = np.empty((nb * B, 2 * OUTPUT_STEPS), np.uint8)
            for j in range(OUTPUT_STEPS):
                x, y = step_vec(x, y, 1)
                outb[:, 2 * j], outb[:, 2 * j + 1] = mbyte(x), mbyte(y)
            outb = outb.reshape(nb, B, 2 * OUTPUT_STEPS)
            out_distinct = [len(np.unique(outb[i], axis=0)) for i in range(nb)]
            del x, y, outb
            for i in range(nb):
                r = {"coord": coord, "block": b0 + i, "start_grid_index": int(start[i]), "other_grid_index": int(other[i]),
                     "distinct_states": {str(s): per_cp[s][0][i] for s in CHECKPOINTS},
                     "max_multiplicity": {str(s): per_cp[s][1][i] for s in CHECKPOINTS},
                     f"distinct_output_seq_{2 * OUTPUT_STEPS}B_after_burn_in": out_distinct[i]}
                rows.append(r)
                jl.write(json.dumps(r) + "\n")
            jl.flush()
            run.log(f"P2 {coord} batch blocks {b0}..{b0 + nb - 1}: {time.time() - tb:.1f} s, {mem_record()}")
        res = {"blocks": len(rows), "block_size": B, "total_states": len(rows) * B, "seconds": round(time.time() - t0, 1),
               "by_step": {}}
        for s in CHECKPOINTS:
            d = np.array([r["distinct_states"][str(s)] for r in rows])
            merged = B - d
            res["by_step"][str(s)] = {
                "distinct_total": int(d.sum()), "merged_total": int(merged.sum()),
                "distinct_per_block": mean_ci(d), "merge_fraction_per_block": mean_ci(merged / B),
                "distinct_min_max": [int(d.min()), int(d.max())],
                "distinct_quantiles_5_50_95": np.quantile(d, [0.05, 0.5, 0.95]).tolist(),
                "log2_compression_per_block": mean_ci(np.log2(B / d)),
                "max_multiplicity_overall": int(max(r["max_multiplicity"][str(s)] for r in rows))}
        od = np.array([r[f"distinct_output_seq_{2 * OUTPUT_STEPS}B_after_burn_in"] for r in rows])
        db = np.array([r["distinct_states"][str(BURN_IN)] for r in rows])
        res["output_sequences_after_burn_in"] = {
            "bytes_per_lane": 2 * OUTPUT_STEPS, "distinct_per_block": mean_ci(od),
            "blocks_where_distinct_outputs_equal_distinct_states": int((od == db).sum()),
            "blocks_where_distinct_outputs_lt_distinct_states": int((od < db).sum())}
        out[coord] = res
        b1, bb = res["by_step"]["1"], res["by_step"][str(BURN_IN)]
        run.log(f"P2 {coord}: distinct mean after 1 step {b1['distinct_per_block']['mean']:.2f}, "
                f"after burn-in {bb['distinct_per_block']['mean']:.2f} of {B}")
    jl.close()
    return out


# ---------------------------------------------------------------- Part 3

def dup_stats(xb, yb, group=None):
    """Exact duplicate counts of (x, y) bit pairs (optionally within groups)."""
    keys = (yb, xb) if group is None else (yb, xb, group)
    o = np.lexsort(keys)
    eq = (xb[o][1:] == xb[o][:-1]) & (yb[o][1:] == yb[o][:-1])
    if group is not None:
        eq &= group[o][1:] == group[o][:-1]
    # number of states that equal an earlier state = m - distinct; colliding pairs from run lengths
    pairs = 0
    if eq.any():
        e = np.concatenate([[False], eq, [False]]).astype(np.int8)
        starts, ends = np.flatnonzero(np.diff(e) == 1), np.flatnonzero(np.diff(e) == -1)
        runs = ends - starts + 1
        pairs = int((runs * (runs - 1) // 2).sum())
    return {"duplicate_states": int(eq.sum()), "colliding_pairs": pairs}


def coord_dups(v):
    s = np.sort(v)
    eq = s[1:] == s[:-1]
    return int(eq.sum())


def close_pairs(a, b, D):
    """All pairs with |da| <= D on integer grid coords a, b; returns counts and min Chebyshev distance among them."""
    o = np.argsort(a, kind="stable")
    sa, sb = a[o], b[o]
    nx, nboth, cheb_min = 0, 0, None
    k = 1
    while k < len(sa):
        da = sa[k:] - sa[:-k]
        m = da <= D
        if not m.any():
            break
        db = np.abs(sb[k:][m] - sb[:-k][m])
        nx += int(m.sum())
        nboth += int((db <= D).sum())
        ch = int(np.maximum(da[m], db).min())
        cheb_min = ch if cheb_min is None else min(cheb_min, ch)
        k += 1
    return {"pairs_within_D_in_x": nx, "pairs_within_D_in_both": nboth, "min_chebyshev_among_x_close_pairs": cheb_min}


def part3(run, base, target, batch, budget_s):
    t0 = time.time()
    ctx = context(1, 1, 256, 256, 1)
    per_msg = len(STREAMS) * LANES
    msgs_per_batch = batch // per_msg
    A, Bv, X1, Y1, XB, YB, MSG = [], [], [], [], [], [], []
    jl = open(run.path("raw", "part3_batches.jsonl"), "x", encoding="utf-8")
    done, stop_reason = 0, "target reached"
    while done < target:
        if done >= base and time.time() - t0 > budget_s:
            stop_reason = f"time budget {budget_s} s exceeded after {done} states (pre-registered stop rule)"
            break
        guard(f"part3 batch at {done}")
        tb = time.time()
        j0 = done // per_msg
        a = np.empty(batch, np.int64)
        b = np.empty(batch, np.int64)
        for j in range(j0, j0 + msgs_per_batch):
            lab = f"A6e23/part3/message/{j}"
            seeds = Derivation(public_key(lab), public_nonce(lab), ctx).seeds()
            flat = [s for g in STREAMS for s in seeds[g]]
            for i, s in enumerate(flat):
                a[(j - j0) * per_msg + i], b[(j - j0) * per_msg + i] = seed_to_ints(s)
        x = a.astype(np.float64) * G - 1.0
        y = b.astype(np.float64) * G - 1.0
        x, y = step_vec(x, y, 1)
        x1, y1 = bits(x).copy(), bits(y).copy()
        for s in range(2, BURN_IN + 1):
            x, y = step_vec(x, y, 1)
            if s % 128 == 0:
                guard(f"part3 batch at {done} step {s}")
        A.append(a); Bv.append(b); X1.append(x1); Y1.append(y1); XB.append(bits(x).copy()); YB.append(bits(y).copy())
        MSG.append(np.arange(j0, j0 + msgs_per_batch, dtype=np.int64).repeat(per_msg))
        del x, y
        done += batch
        rec = {"states_done": done, "messages": [j0, j0 + msgs_per_batch - 1], "seconds": round(time.time() - tb, 1), **mem_record()}
        jl.write(json.dumps(rec) + "\n"); jl.flush()
        run.log(f"P3 batch -> {done} states: {rec}")
    jl.close()
    a, b = np.concatenate(A), np.concatenate(Bv)
    xi, yi = bits(a.astype(np.float64) * G - 1.0), bits(b.astype(np.float64) * G - 1.0)
    x1, y1, xb, yb, msg = map(np.concatenate, (X1, Y1, XB, YB, MSG))
    m = len(a)
    P = m * (m - 1) // 2
    res = {"states": m, "messages": int(msg.max()) + 1, "lanes_per_message": per_msg, "stop_reason": stop_reason,
           "seed_source": "Derivation(public_key('A6e23/part3/message/<j>'), public_nonce(same), context(1,1,256,256,1)).seeds(), "
                          "canonical stream order sbox, perm, fwd, bwd x lanes 0..63 -> state_map.seed_to_ints",
           "exact_duplicates": {}, "coordinate_only_coincidences": {},
           "unordered_pairs": P}
    for name, (u, v) in (("initial", (xi, yi)), ("after_1_step", (x1, y1)), ("after_burn_in_1024", (xb, yb))):
        res["exact_duplicates"][name] = {"overall": dup_stats(u, v), "within_message": dup_stats(u, v, msg)}
        res["coordinate_only_coincidences"][name] = {"equal_x_bits_pairs_or_more": coord_dups(u), "equal_y_bits_pairs_or_more": coord_dups(v)}
    res["grid_neighbours_initial"] = {
        "min_abs_alpha_gap": int(np.diff(np.sort(a)).min()), "min_abs_beta_gap": int(np.diff(np.sort(b)).min()),
        "D_128": close_pairs(a, b, 128), "D_2^20": close_pairs(a, b, 2 ** 20),
        "expected_pairs_within_D_in_x_uniform": {"D_128": P * (2 * 128 + 1) / 2 ** 53, "D_2^20": P * (2 * 2 ** 20 + 1) / 2 ** 53}}
    k = res["exact_duplicates"]["after_burn_in_1024"]["overall"]["colliding_pairs"]
    res["per_pair_collision_after_burn_in_95pct_upper_bound_if_zero"] = (3.0 / P) if k == 0 else None
    res["seconds"] = round(time.time() - t0, 1)
    run.log(f"P3: {m} states, duplicates {res['exact_duplicates']}")
    return res


def a6e(mode):
    full = mode == "full"
    cfg = {"label": "POST-HOC A6(e) Parts 2-3 follow-up run (memory-bounded); no pass/fail criterion; "
                    "diagnostic mode = PILOT at production batch size, not a result",
           "replaces_incomplete_parts_of": "A6e_merge_posthoc_full_20261026T080320Z (Parts 2-3; Part 1 complete there)",
           "part1_source": PART1_SOURCE,
           "seed_part2": 6023, "profile": 1, "backend": "V1 (NumPy)", "burn_in": BURN_IN,
           "max_lanes_per_step_vec": MAX_LANES, "memory_guard_available_mb": GUARD_MB,
           "part2_block_size": 1024, "part2_blocks_per_coordinate": 100 if full else 64,
           "part2_batch_blocks": MAX_LANES // 1024, "part2_checkpoints": CHECKPOINTS,
           "part2_output_steps_after_burn_in": OUTPUT_STEPS,
           "part2_selection_rule": "per block: start ~ U{0..2^53-1024}, other coordinate ~ U{0..2^53-1}, numpy default_rng(seed_part2), x blocks first then y",
           "part2_original_target": "1000 blocks after burn-in and 10^4 after 1 step (A6e full config); this run uses 100 blocks per coordinate by instruction",
           "part3_base_states": 2 ** 16, "part3_target_states": 2 ** 20 if full else 2 ** 16, "part3_batch_states": MAX_LANES,
           "part3_time_budget_seconds": 3600 if full else 0,
           "part3_stop_rule": "complete batches only; stop when target reached, or after the base size once the time budget is exceeded, or on the memory guard"}
    run = Run("A6e23_merge_posthoc", mode, cfg)
    print("RUN_DIR " + run.dir, flush=True)
    run.log(f"memory at start: {mem_record()}")
    status, p2, p3 = "complete", None, None
    try:
        # the pilot runs one production-size batch (64 blocks) along x only
        p2 = part2(run, np.random.default_rng(cfg["seed_part2"]), cfg["part2_blocks_per_coordinate"], cfg["part2_block_size"],
                   cfg["part2_batch_blocks"], ("x", "y") if full else ("x",))
        run.write_json("raw/part2_summary.json", p2)
        p3 = part3(run, cfg["part3_base_states"], cfg["part3_target_states"], cfg["part3_batch_states"], cfg["part3_time_budget_seconds"])
        run.write_json("raw/part3_summary.json", p3)
    except MemoryGuardStop as e:
        status = f"INCOMPLETE: memory guard stop ({e})"
        run.log(status)
    return run.finish({"label": cfg["label"], "status": status, "memory_at_end": mem_record(), "part2": p2, "part3": p3})

