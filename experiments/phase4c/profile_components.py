"""Track C: component-level timing breakdown of the real production pipeline.

This harness calls isc_cipher's actual internal functions directly (same
functions cipher.py's _encrypt/decrypt_bytes call) to time each of the 15
listed stages independently. It does NOT modify any isc_cipher file; it is a
standalone, read-only caller of the existing internals, mirroring exactly
the call sequence in isc_cipher/cipher.py:71-102 (encrypt) and :119-145
(decrypt).

Run in isolation (no other experiment running concurrently) per the user's
explicit requirement, since Phase 4B found concurrent-track CPU contention
distorted timing.
"""
import gc
import hashlib
import hmac
import os
import time

import numpy as np
import pandas as pd

import config
from isc_cipher import container, diffusion, sampling
from isc_cipher.generator import EXTRACTION_MANTISSA8_V1, build_streams, kcv_state_bytes
from isc_cipher.kdf import NONCE_LEN, Derivation, check_key, context

KEY = config.BASE_KEY
REPS = 3
WARMUP = 1


def _time(fn, reps=REPS, warmup=WARMUP):
    # gc.collect() before each timed call: an earlier run of this script
    # found 14_complete_encryption/15_complete_decryption measuring ~2.2x
    # higher than the sum of the individual component stages (3.65s vs
    # 1.69s at size 64). A direct isolated re-check of encrypt_bytes() in a
    # fresh process measured ~1.4s/call, matching the component sum -- so
    # the inflated number was a measurement artifact of this harness
    # accumulating many large NumPy arrays from earlier stage measurements
    # in the same process (GC/memory pressure), not a real property of the
    # cipher. Explicit gc.collect() calls here fix the harness; this is
    # documented, not silently patched over.
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(reps):
        gc.collect()
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return {
        "mean_sec": float(np.mean(times)), "median_sec": float(np.median(times)),
        "std_sec": float(np.std(times)), "min_sec": float(np.min(times)), "max_sec": float(np.max(times)),
        "reps": reps,
    }


def profile_size(h, w, c, backend="numpy"):
    n = h * w * c
    data = os.urandom(n)
    nonce = os.urandom(NONCE_LEN)
    profile = 1
    extraction = EXTRACTION_MANTISSA8_V1
    results = {}

    # 1. key validation
    results["1_key_validation"] = _time(lambda: check_key(KEY))

    # 2. HKDF derivation (Derivation object construction, which runs extract+expand for mac/kcv/iv)
    ctx = context(profile, container.DTYPE_UINT8, h, w, c, extraction=None)
    results["2_hkdf_derivation"] = _time(lambda: Derivation(KEY, nonce, ctx))

    der = Derivation(KEY, nonce, ctx)
    seeds = der.seeds()

    # 3+4. initial-state construction + burn-in are both inside build_streams;
    # build_streams does not expose them separately without touching
    # production code, so they are profiled together and the sub-split is
    # marked UNKNOWN (cannot be isolated without modifying isc_cipher).
    results["3_4_state_construction_and_burnin_combined"] = _time(
        lambda: build_streams(seeds, backend=backend, profile=profile))
    results["3_4_NOTE"] = ("state construction (seed_to_state) and burn-in are both internal to "
                            "build_streams and not separately callable without modifying "
                            "isc_cipher/generator.py; reported as one combined stage, not estimated.")

    streams = build_streams(seeds, backend=backend, profile=profile)

    # 5. stream generation / consumption time is implicit in build_sbox /
    # build_permutation / .take() below (lazy pull-based generation, per
    # Phase 4A); there is no standalone "generate the stream" call to time
    # in isolation from its consumer.

    # 6. S-box construction
    results["6_sbox_construction"] = _time(lambda: sampling.build_sbox(streams["sbox"]))
    streams2 = build_streams(seeds, backend=backend, profile=profile)
    S, S_inv = sampling.build_sbox(streams2["sbox"])

    # 7. Fisher-Yates permutation construction
    results["7_fisher_yates_permutation"] = _time(lambda: sampling.build_permutation(streams2["perm"], n), reps=max(1, REPS))
    streams3 = build_streams(seeds, backend=backend, profile=profile)
    pi = sampling.build_permutation(streams3["perm"], n)

    # 8. permutation application
    results["8_permutation_application"] = _time(lambda: sampling.apply_permutation(data, pi))
    q = sampling.apply_permutation(data, pi)

    a = streams3["fwd"].take(n)
    b = streams3["bwd"].take(n)
    iv_f, iv_b = der.ivs()

    # 9. forward diffusion
    results["9_forward_diffusion"] = _time(lambda: diffusion.forward(q, a, S, iv_f))
    u = diffusion.forward(q, a, S, iv_f)

    # 10. backward diffusion
    results["10_backward_diffusion"] = _time(lambda: diffusion.backward(u, b, S, iv_b))
    body = diffusion.backward(u, b, S, iv_b)

    # 11. KCV generation
    results["11_kcv_generation"] = _time(
        lambda: hmac.new(der.kcv_key(), kcv_state_bytes(streams3), hashlib.sha256).digest()[:8])
    kcv = hmac.new(der.kcv_key(), kcv_state_bytes(streams3), hashlib.sha256).digest()[:8]

    # 12. HMAC authentication (tag computation over header+body)
    hdr_obj = container.Header(profile=profile, c=c, h=h, w=w, nonce=bytes(nonce), kcv=kcv, version=1,
                                extraction=extraction)
    hdr_bytes = hdr_obj.pack()
    results["12_hmac_tag_computation"] = _time(
        lambda: hmac.new(der.mac_key(), hdr_bytes + body, hashlib.sha256).digest())
    tag = hmac.new(der.mac_key(), hdr_bytes + body, hashlib.sha256).digest()

    # 13. container serialization/parsing
    results["13a_container_pack"] = _time(lambda: hdr_obj.pack())
    full_ct = hdr_bytes + body + tag
    results["13b_container_parse"] = _time(lambda: container.parse(full_ct))

    # 14. complete encryption (full public API call)
    from isc_cipher import encrypt_bytes
    results["14_complete_encryption"] = _time(lambda: encrypt_bytes(KEY, data, h, w, c), reps=max(1, REPS - 1))

    # 15. complete decryption
    from isc_cipher import decrypt_bytes
    ct_for_dec = encrypt_bytes(KEY, data, h, w, c)
    results["15_complete_decryption"] = _time(lambda: decrypt_bytes(KEY, ct_for_dec), reps=max(1, REPS - 1))

    return results


def run():
    sizes = [(64, 64, 1), (128, 128, 1), (256, 256, 1)]
    rows = []
    for h, w, c in sizes:
        print(f"Profiling h={h} w={w} c={c} (n={h*w*c} bytes)...")
        res = profile_size(h, w, c)
        for stage, stats in res.items():
            if stage.endswith("_NOTE"):
                continue
            row = {"h": h, "w": w, "c": c, "n_bytes": h * w * c, "stage": stage}
            row.update(stats)
            rows.append(row)
            print(f"  {stage:40s} mean={stats['mean_sec']*1000:8.3f}ms median={stats['median_sec']*1000:8.3f}ms")

    df = pd.DataFrame(rows)
    df.to_csv(f"{config.RESULTS_DIR}/component_profiling.csv", index=False)
    return df


if __name__ == "__main__":
    run()
