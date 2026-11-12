"""A14 (performance and ablation) and A10 (API misuse check).

Times: time.perf_counter around one encrypt and one decrypt; peak memory: tracemalloc (covers Python and
NumPy allocations). Fresh random nonces. Machine details in environment.json.
"""

import inspect
import os
import time
import tracemalloc

import numpy as np

import isc_cipher

from .common import Run, public_key
from .constructions import AEADS, aead_open, aead_seal, seal, unseal


TRACE = {"on": False}


def measure(fn):
    """Timing runs are untraced (tracemalloc slowed Python-heavy code about 10x in the diagnostic run);
    peak memory comes from one separate traced repetition (TRACE['on'] = True), whose time is discarded."""
    if TRACE["on"]:
        tracemalloc.start()
        r = fn()
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return r, None, peak
    t0 = time.perf_counter()
    r = fn()
    return r, time.perf_counter() - t0, None


def a14(mode):
    full = mode == "full"
    sizes = [64, 128, 256, 512, 1024] if full else [64]
    cfg = {"sizes": sizes, "channels": [1, 3] if full else [1],
           "reps": "10 if n <= 2^18 else 3" if full else 1,
           "constructions": ["V-FULL (isc_cipher, V1)", "V-CHACHA"] + list(AEADS)}
    run = Run("A14_perf", mode, cfg)
    key = public_key("A14")
    rows = []
    for s in sizes:
        for c in cfg["channels"]:
            n = s * s * c
            reps = (10 if n <= 2 ** 18 else 3) if full else 1
            p = bytes(np.random.default_rng(n).integers(0, 256, n, dtype=np.uint8))
            for cons in ["V-FULL", "V-CHACHA"] + list(AEADS):
                te, td, me, md = [], [], [], []
                for rep in range(reps + 1):                 # last repetition: traced, memory only
                    TRACE["on"] = rep == reps
                    if cons == "V-FULL":
                        z, t, m = measure(lambda: isc_cipher.encrypt_bytes(key, p, s, s, c))
                        out, t2, m2 = measure(lambda: isc_cipher.decrypt_bytes(key, z)[0])
                    elif cons == "V-CHACHA":
                        z, t, m = measure(lambda: seal(cons, key, os.urandom(16), p, s, s, c))
                        out, t2, m2 = measure(lambda: unseal(cons, key, z))
                    else:
                        k32 = os.urandom(32)
                        z, t, m = measure(lambda: aead_seal(cons, k32, p, s, s, c, os.urandom(12)))
                        out, t2, m2 = measure(lambda: aead_open(cons, k32, z, s, s, c))
                    assert out == p
                    if TRACE["on"]:
                        me.append(m)
                        md.append(m2)
                    else:
                        te.append(t)
                        td.append(t2)
                TRACE["on"] = False
                rows.append({"size": [s, s, c], "n": n, "construction": cons, "reps": reps,
                             "encrypt_s_median": float(np.median(te)), "encrypt_s_min": min(te), "encrypt_s_max": max(te),
                             "decrypt_s_median": float(np.median(td)), "decrypt_s_min": min(td), "decrypt_s_max": max(td),
                             "peak_mem_MB_encrypt": max(me) / 2 ** 20, "peak_mem_MB_decrypt": max(md) / 2 ** 20})
                run.log(f"{s}x{s}x{c} {cons}: enc {rows[-1]['encrypt_s_median']:.4f} s, dec {rows[-1]['decrypt_s_median']:.4f} s")
    run.write_json("raw/perf.json", rows)
    return run.finish({"rows": rows})


def a10(mode):
    run = Run("A10_api", mode, {})
    sig = {f: list(inspect.signature(getattr(isc_cipher, f)).parameters) for f in ("encrypt", "decrypt", "encrypt_bytes", "decrypt_bytes")}
    nonce_params = {f: [p for p in v if "nonce" in p] for f, v in sig.items()}
    return run.finish({"public_signatures": sig, "nonce_parameters_in_public_api": nonce_params,
                       "public_api_accepts_nonce": any(nonce_params.values()),
                       "replay_protection": "not provided (stateless), as documented in threat_model.md §5",
                       "test_only_fixed_nonce_entry_point": "isc_cipher._testing.encrypt_bytes_with_nonce_TEST_ONLY"})
