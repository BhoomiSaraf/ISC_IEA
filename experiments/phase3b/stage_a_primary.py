"""Stage A: primary mantissa8_v1 vs k14_scaled_modulo_v1 comparison at the existing burn_in=1024.

Populations covered: 2 (individual lanes, all 256, full descriptive stats; NIST on subsamples),
3 (interleaved per-stream output, full descriptive stats + round-vs-cross-round correlation;
NIST on chunked subsamples), 4 (cross-stream MI, all 6 pairs), 5 (256-lane collision/duplicate
check), plus an output-reproducibility sanity check (Section 3, item 9).

Three independent seed configurations (seedA/B/C). Full-cost NIST multi-sequence testing (M=256
lanes, M=64 stream-chunks) is run once, on seedA only, for both extraction profiles -- the
direct, maximal-power primary comparison. seedB/seedC use a fixed M=32 lane / M=16 chunk
subsample to check cross-seed stability without re-paying the full NIST cost three times; this
reduction is a deliberate, disclosed runtime bound (pilot_benchmark.py showed ~0.52s per
run_battery call), not a silent change to the primary comparison's sample size.
"""
import json
import time

import numpy as np

from common import (
    BYTES_PER_LANE_PRIMARY, SEED_CONFIGS, generate, lane_subsequence, shannon_entropy_bytes,
    chisquare_uniform, acf_biased, bonferroni_bound, mutual_information_bytes, STREAMS,
)
from isc_seq import nist as isc_nist

RUN_LOG = []


def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line, flush=True)
    RUN_LOG.append(line)


def lane_nist_subset(stream_bytes_by_g, extraction, seed_label, lane_indices):
    out = {}
    for g in STREAMS:
        rows = []
        for l in lane_indices:
            seq = lane_subsequence(stream_bytes_by_g[g], l)
            bits = np.unpackbits(seq)
            res = isc_nist.run_battery(bits)
            rows.append(res)
        out[g] = rows
    return out


def stream_chunk_nist_subset(stream_bytes_by_g, n_chunks, chunk_bytes=BYTES_PER_LANE_PRIMARY):
    out = {}
    for g in STREAMS:
        arr = np.frombuffer(stream_bytes_by_g[g], dtype=np.uint8)
        max_chunks = arr.size // chunk_bytes
        use = min(n_chunks, max_chunks)
        rows = []
        for i in range(use):
            chunk = arr[i * chunk_bytes:(i + 1) * chunk_bytes]
            bits = np.unpackbits(chunk)
            rows.append(isc_nist.run_battery(bits))
        out[g] = rows
    return out


def round_vs_cross_round_correlation(stream_bytes):
    """Section 2.2: correlation of consecutive bytes WITHIN a 128-byte round vs ACROSS the
    round boundary (byte 127 of round r vs byte 0 of round r+1)."""
    arr = np.frombuffer(stream_bytes, dtype=np.uint8).astype(np.float64)
    n_rounds = arr.size // 128
    arr = arr[: n_rounds * 128].reshape(n_rounds, 128)
    within = np.array([np.corrcoef(arr[:, i], arr[:, i + 1])[0, 1] for i in range(0, 127, 2)])
    boundary_a = arr[:-1, 127]
    boundary_b = arr[1:, 0]
    across = float(np.corrcoef(boundary_a, boundary_b)[0, 1]) if n_rounds > 1 else float("nan")
    return {"within_round_mean_abs_corr": float(np.nanmean(np.abs(within))),
            "within_round_n_pairs": int(within.size),
            "across_round_boundary_corr": across}


def collision_check(stream_bytes_by_g, prefix_len=256):
    """Population 5: pairwise Hamming distance of each lane's first prefix_len bytes, within
    each stream (64 lanes, 2016 pairs) -- direct empirical test of architecture_discrepancies.md
    section 4's theoretical 'could two lanes collide' concern."""
    out = {}
    for g in STREAMS:
        lanes = np.stack([lane_subsequence(stream_bytes_by_g[g], l)[:prefix_len] for l in range(64)])
        n = lanes.shape[0]
        min_hamming = 10 ** 9
        min_pair = None
        total_pairs = 0
        exact_dupe_pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                d = int(np.count_nonzero(lanes[i] != lanes[j]))
                total_pairs += 1
                if d == 0:
                    exact_dupe_pairs += 1
                if d < min_hamming:
                    min_hamming = d
                    min_pair = (i, j)
        out[g] = {"n_pairs": total_pairs, "min_hamming_distance": min_hamming,
                  "min_pair": min_pair, "exact_duplicate_pairs": exact_dupe_pairs,
                  "prefix_len_bytes": prefix_len,
                  "expected_min_hamming_if_random": "see report (binomial argument)"}
    return out


def main():
    results = {"bytes_per_lane": BYTES_PER_LANE_PRIMARY, "burn_in": 1024, "seeds": {}}
    lane_rows = []
    stream_rows = []
    cross_stream_rows = []
    nist_lane_rows = []
    nist_stream_rows = []
    collision_rows = []

    # n_samples = the actual length of the sequence the ACF is computed on: BYTES_PER_LANE_PRIMARY
    # for a lane's own subsequence, BYTES_PER_LANE_PRIMARY*64 for a stream's pooled sequence.
    bonf_256 = bonferroni_bound(BYTES_PER_LANE_PRIMARY, 256)
    bonf_4 = bonferroni_bound(BYTES_PER_LANE_PRIMARY * 64, 4)

    for extraction in (1, 2):
        for seed_label in ("seedA", "seedB", "seedC"):
            t0 = time.perf_counter()
            log(f"generating extraction={extraction} seed={seed_label} "
                f"({BYTES_PER_LANE_PRIMARY} bytes/lane, 4 streams, burn_in=1024)")
            data = generate(seed_label, extraction, burn_in=1024, bytes_per_lane=BYTES_PER_LANE_PRIMARY)
            dt_gen = time.perf_counter() - t0
            log(f"  generation done in {dt_gen:.1f}s")

            # ---- reproducibility sanity check (seedA, extraction=1 only, cheap) ----
            if seed_label == "seedA" and extraction == 1:
                data2 = generate(seed_label, extraction, burn_in=1024, bytes_per_lane=2000)
                data2b = generate(seed_label, extraction, burn_in=1024, bytes_per_lane=2000)
                repro_ok = all(data2[g] == data2b[g] for g in STREAMS)
                results["reproducibility_check_byte_exact"] = bool(repro_ok)
                log(f"  reproducibility check (independent re-run, byte-exact): {repro_ok}")

            # ---- population 2: per-lane descriptive stats, all 256 lanes ----
            for g in STREAMS:
                for l in range(64):
                    seq = lane_subsequence(data[g], l)
                    H, counts = shannon_entropy_bytes(seq)
                    chi2, chi2_p = chisquare_uniform(counts)
                    acf = acf_biased(seq, max_lag=100)
                    max_abs_acf = float(np.max(np.abs(acf)))
                    lane_rows.append({
                        "extraction": extraction, "seed": seed_label, "stream": g, "lane": l,
                        "n_bytes": int(seq.size), "shannon_entropy_bits": H,
                        "chi2": chi2, "chi2_p": chi2_p,
                        "acf_lag1": float(acf[0]), "max_abs_acf_lag1_100": max_abs_acf,
                        "bonferroni_bound_256tests": bonf_256,
                        "within_bonferroni_bound": bool(max_abs_acf <= bonf_256),
                    })

            # ---- population 3: per-stream (interleaved) descriptive stats ----
            for g in STREAMS:
                arr = np.frombuffer(data[g], dtype=np.uint8)
                H, counts = shannon_entropy_bytes(arr)
                chi2, chi2_p = chisquare_uniform(counts)
                acf = acf_biased(arr.astype(np.float64)[:200000], max_lag=100)  # cap for speed
                rc = round_vs_cross_round_correlation(data[g])
                stream_rows.append({
                    "extraction": extraction, "seed": seed_label, "stream": g,
                    "n_bytes": int(arr.size), "shannon_entropy_bits": H,
                    "chi2": chi2, "chi2_p": chi2_p, "max_abs_acf_lag1_100": float(np.max(np.abs(acf))),
                    **rc,
                })

            # ---- population 4: cross-stream MI, 6 pairs ----
            pairs = [("sbox", "perm"), ("sbox", "fwd"), ("sbox", "bwd"),
                     ("perm", "fwd"), ("perm", "bwd"), ("fwd", "bwd")]
            # bound runtime: use first 200,000 bytes of each stream for the MI estimate (disclosed)
            mi_n = 200_000
            for (g1, g2) in pairs:
                a = np.frombuffer(data[g1][:mi_n], dtype=np.uint8)
                b = np.frombuffer(data[g2][:mi_n], dtype=np.uint8)
                mi = mutual_information_bytes(a, b, n_perm=200, n_shift=100)
                cross_stream_rows.append({"extraction": extraction, "seed": seed_label,
                                           "stream_1": g1, "stream_2": g2, **mi})
            log(f"  cross-stream MI (6 pairs, n={mi_n}) done")

            # ---- population 5: lane collision check ----
            coll = collision_check(data, prefix_len=256)
            for g, row in coll.items():
                collision_rows.append({"extraction": extraction, "seed": seed_label, "stream": g, **row})

            # ---- NIST: full cost on seedA, subsample on seedB/seedC ----
            if seed_label == "seedA":
                lane_idx = list(range(64))
                n_chunks = 64
            else:
                lane_idx = list(range(0, 64, 2))  # 32 lanes
                n_chunks = 16
            t0 = time.perf_counter()
            lane_nist = lane_nist_subset(data, extraction, seed_label, lane_idx)
            for g, rows in lane_nist.items():
                pvt = {test: [r[test] for r in rows if test in r] for test in rows[0]}
                ev = isc_nist.evaluate(pvt)
                for test, summ in ev.items():
                    nist_lane_rows.append({"extraction": extraction, "seed": seed_label,
                                            "stream": g, "test": test, "m_sequences": len(lane_idx), **summ})
            dt_lane_nist = time.perf_counter() - t0

            t0 = time.perf_counter()
            stream_nist = stream_chunk_nist_subset(data, n_chunks=n_chunks)
            for g, rows in stream_nist.items():
                pvt = {test: [r[test] for r in rows if test in r] for test in rows[0]}
                ev = isc_nist.evaluate(pvt)
                for test, summ in ev.items():
                    nist_stream_rows.append({"extraction": extraction, "seed": seed_label,
                                              "stream": g, "test": test, "m_sequences": len(rows), **summ})
            dt_stream_nist = time.perf_counter() - t0
            log(f"  NIST lane battery ({len(lane_idx)} lanes/stream): {dt_lane_nist:.1f}s; "
                f"stream-chunk battery ({n_chunks} chunks/stream): {dt_stream_nist:.1f}s")

    import pandas as pd
    pd.DataFrame(lane_rows).to_csv("raw/stage_a_lane_metrics.csv", index=False)
    pd.DataFrame(stream_rows).to_csv("raw/stage_a_stream_metrics.csv", index=False)
    pd.DataFrame(cross_stream_rows).to_csv("raw/stage_a_cross_stream_metrics.csv", index=False)
    pd.DataFrame(nist_lane_rows).to_csv("raw/stage_a_nist_lane.csv", index=False)
    pd.DataFrame(nist_stream_rows).to_csv("raw/stage_a_nist_stream.csv", index=False)
    pd.DataFrame(collision_rows).to_csv("raw/stage_a_collision.csv", index=False)
    with open("raw/stage_a_meta.json", "w") as f:
        json.dump(results, f, indent=2)
    with open("raw/stage_a_run_log.txt", "w") as f:
        f.write("\n".join(RUN_LOG))
    log("Stage A complete. Wrote raw/stage_a_*.csv, stage_a_meta.json, stage_a_run_log.txt")


if __name__ == "__main__":
    main()
