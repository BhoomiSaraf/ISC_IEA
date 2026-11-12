"""Phase 3B pilot benchmark (Section 2.4 of the task spec).

Measures real wall-clock cost of build_streams()+take() for both extraction profiles at
burn_in=1024, on THIS machine, before committing to a final per-lane sample size for the
full multi-lane/multi-profile/burn-in experiment matrix. Read-only w.r.t. production code:
imports isc_cipher only, writes no file outside experiments/phase3b/.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isc_cipher.kdf import Derivation, context
from isc_cipher.generator import build_streams, BYTES_PER_STEP

KEY = bytes.fromhex("a1" * 32)
NONCE = bytes.fromhex("b2" * 16)
CTX = context(profile=1, dtype=1, h=0, w=0, c=1)  # pilot only; real experiment uses per-config ctx


def seeds_for(key, nonce):
    d = Derivation(key, nonce, CTX)
    return d.seeds()


def time_build(extraction, burn_in=1024, n_bytes_per_lane=20000, reps=1):
    seeds = seeds_for(KEY, NONCE)
    t0 = time.perf_counter()
    streams = build_streams(seeds, backend="numpy", profile=1, burn_in=burn_in, extraction=extraction)
    t_build = time.perf_counter() - t0

    m_total = n_bytes_per_lane * 64  # bytes per stream = bytes/lane * 64 lanes
    t0 = time.perf_counter()
    out = {g: st.take(m_total) for g, st in streams.items()}
    t_take = time.perf_counter() - t0
    for g, b in out.items():
        assert len(b) == m_total, (g, len(b), m_total)
    return t_build, t_take, m_total


if __name__ == "__main__":
    results = {}
    for extraction in (1, 2):
        t_build, t_take, m_total = time_build(extraction, burn_in=1024, n_bytes_per_lane=20000)
        bytes_per_sec = (4 * m_total) / t_take if t_take > 0 else float("inf")
        results[f"extraction_{extraction}"] = {
            "burn_in": 1024,
            "bytes_per_lane_requested": 20000,
            "bytes_per_stream": m_total,
            "t_build_seconds": t_build,
            "t_take_seconds": t_take,
            "total_bytes_all_4_streams": 4 * m_total,
            "throughput_bytes_per_sec": bytes_per_sec,
        }
        print(f"extraction={extraction}: build={t_build:.3f}s take={t_take:.3f}s "
              f"({4*m_total} bytes total, {bytes_per_sec:.0f} B/s)")

    # burn-in cost scaling (profile 1, extraction=1, build only, no take)
    burnin_times = {}
    for T in (1024, 2048, 5000, 10000):
        seeds = seeds_for(KEY, NONCE)
        t0 = time.perf_counter()
        build_streams(seeds, backend="numpy", profile=1, burn_in=T, extraction=1)
        dt = time.perf_counter() - t0
        burnin_times[T] = dt
        print(f"burn_in={T}: {dt:.3f}s")
    results["burn_in_scaling_seconds"] = burnin_times

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw", "pilot_benchmark.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print("wrote", out_path)
