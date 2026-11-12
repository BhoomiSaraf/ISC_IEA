"""A12: official NIST STS 2.1.2 on the NEW generator G_v1 (profile 1, HKDF seeds, 64 lanes, T = 1024).

Batches (gate_a_plan.md): (i) `fwd` stream of 100 messages, (ii) `perm` stream of 100 messages,
(iii) 100 single-lane sequences (64 lanes from each of 2 messages, first 100). Each sequence = 10^6 bits.
Also provides `run_sts_batches` for the ciphertext NIST part of A7.
Uses the unchanged official-STS tooling (isc_seq.sts_official, experiments/analyze_official_sts.py).
"""

import concurrent.futures as cf
import importlib.util
import os

import numpy as np

from isc_cipher.generator import BYTES_PER_STEP, build_streams
from isc_cipher.kdf import Derivation, context
from isc_seq import sts_official as so

from .common import ROOT, Run, public_key, public_nonce

SEQ_BYTES = 125000                                   # 10^6 bits
STS_BUILD = os.path.join(ROOT, "third_party", "nist_sts", "build_linux")


def _analyzer():
    spec = importlib.util.spec_from_file_location("aos", os.path.join(ROOT, "experiments", "analyze_official_sts.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def message_streams(label):
    """Streams of one public-test message (dims chosen so the stream bytes needed are exactly one sequence)."""
    key, nonce = public_key(label), public_nonce(label)
    seeds = Derivation(key, nonce, context(1, 1, 250, 500, 1)).seeds()
    return build_streams(seeds, backend="numpy", profile=1)


def single_lane_sequences(label, lanes=64):
    st = message_streams(label)["fwd"]
    steps = SEQ_BYTES // 2
    data = np.frombuffer(st.take(steps * BYTES_PER_STEP), np.uint8).reshape(steps, 64, 2)
    return [data[:, l, :].reshape(-1).tobytes() for l in range(lanes)]


def run_sts_batches(run, batches, log):
    """batches: {name: path_to_bin (concatenated 125000-byte sequences)} -> per-batch STS summary."""
    an = _analyzer()
    assess = os.path.join(STS_BUILD, "assess")
    results = {}

    def one(name, path):
        n_streams = os.path.getsize(path) // SEQ_BYTES
        wd = run.path("sts", name)
        so.prepare_workdir(wd, STS_BUILD)
        rc, out = so.run_assess(wd, assess, path, SEQ_BYTES * 8, n_streams, True, log_path=os.path.join(wd, "assess_stdout.log"))
        complete = "Statistical Testing Complete" in out

        def bits(i):
            with open(path, "rb") as f:
                f.seek(i * SEQ_BYTES)
                return np.unpackbits(np.frombuffer(f.read(SEQ_BYTES), np.uint8))
        ev = so.evaluate_workdir(wd, n_streams, bits, SEQ_BYTES * 8)
        far = os.path.join(wd, "experiments", "AlgorithmTesting", "finalAnalysisReport.txt")
        mism = so.verify_against_report(ev, so.parse_final_analysis_report(far)) if os.path.exists(far) else ["no report"]
        tests = an.test_level({"method": name, "evaluation": ev, "n_streams": n_streams})
        return name, {"n_streams": n_streams, "returncode": rc, "complete": complete, "problems": ev["problems"],
                      "report_mismatches": mism, "tests": tests}
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        for name, res in pool.map(lambda kv: one(*kv), batches.items()):
            results[name] = res
            flagged = {t["test"]: t.get("verdict") for t in res["tests"]}
            log(f"STS {name}: complete={res['complete']} problems={len(res['problems'])} verdicts={flagged}")
    return results


def a12(mode):
    m = 100 if mode == "full" else 2
    cfg = {"generator": "G_v1 (profile 1, HKDF seeds, 4 streams x 64 lanes, T = 1024)", "sequences_per_batch": m,
           "bits_per_sequence": SEQ_BYTES * 8, "message_dims_for_ctx": [250, 500, 1],
           "batches": ["fwd stream", "perm stream (raw bytes)", "single-lane sequences"]}
    run = Run("A12_nist_gv1", mode, cfg)
    paths = {k: run.path("raw", f"{k}.bin") for k in ("fwd", "perm", "single_lane")}
    with open(paths["fwd"], "xb") as ff, open(paths["perm"], "xb") as fp:
        for i in range(m):
            st = message_streams(f"A12/msg/{i:03d}")
            ff.write(st["fwd"].take(SEQ_BYTES))
            fp.write(st["perm"].take(SEQ_BYTES))
            if i % 10 == 0:
                run.log(f"generated message {i}")
    seqs = []
    k = 0
    while len(seqs) < m:
        seqs += single_lane_sequences(f"A12/lanes/{k}")
        k += 1
    with open(paths["single_lane"], "xb") as f:
        for s in seqs[:m]:
            f.write(s)
    run.log("generation done; running official STS")
    res = run_sts_batches(run, paths, run.log)
    return run.finish({"batches": res, "criterion": "flagged series beyond chance (chance tail p < 0.01) or a uniformity failure in any single-series test",
                       "note": "statistical evaluation of G_v1 only; not evidence of security"})
