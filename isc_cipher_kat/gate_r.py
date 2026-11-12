"""Gate R: reproducibility checks of ISC-IMG v1 profile 1 against the stored known-answer vectors.

    python isc_cipher_kat/gate_r.py --backend reference      (R1; needs only the standard library)
    python isc_cipher_kat/gate_r.py --backend numpy          (V1)

Writes results/cipher_validation/gate_r_<host>_<backend>_<UTC>/report.json and log.txt (new directory).
Each check is PASS or FAIL; nothing is skipped silently (a check that cannot run is BLOCKED with a reason).
"""

import argparse
import datetime as dt
import gzip
import hashlib
import hmac
import json
import os
import platform
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isc_cipher import kdf  # noqa: E402
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY, materials_TEST_ONLY  # noqa: E402
from isc_cipher.cipher import decrypt_bytes  # noqa: E402
from isc_cipher.generator import build_streams, kcv_state_bytes  # noqa: E402
from isc_cipher.state_map import seed_to_state  # noqa: E402

VEC = os.path.join(ROOT, "isc_cipher_kat", "vectors")
LOG = []


def log(msg):
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    LOG.append(line)


def d2h(v):
    return struct.pack(">d", float(v)).hex()


def h2d(h):
    return struct.unpack(">d", bytes.fromhex(h))[0]


def environment(backend):
    env = {"python": sys.version, "implementation": platform.python_implementation(),
           "platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
           "float_info": repr(sys.float_info), "byteorder": sys.byteorder, "backend": backend}
    try:
        with open("/proc/cpuinfo") as f:
            flags = next((l for l in f if l.startswith("flags")), "")
        env["cpu_flags_subset"] = sorted(x for x in flags.split() if x in ("sse2", "avx", "avx2", "fma", "avx512f"))
    except OSError:
        env["cpu_flags_subset"] = "unavailable (not Linux)"
    if backend == "numpy":
        import numpy as np
        env["numpy"] = np.__version__
        try:
            cfg = np.show_config(mode="dicts")
            env["numpy_build"] = {"compilers": cfg.get("Compilers"), "simd": cfg.get("SIMD Extensions")}
        except Exception as exc:  # recorded, not hidden
            env["numpy_build"] = f"unavailable: {exc!r}"
    return env


def check_fdlibm_hashes():
    base = os.path.join(ROOT, "third_party", "fdlibm", "netlib_5.3")
    bad = []
    for line in open(os.path.join(base, "SHA256SUMS.txt")):
        digest, name = line.split()
        name = name.lstrip("*")
        if hashlib.sha256(open(os.path.join(base, name), "rb").read()).hexdigest() != digest:
            bad.append(name)
    return not bad, {"mismatched_files": bad}


def check_trig(backend):
    rows = [l.split() for l in gzip.open(os.path.join(VEC, "trig_kat.txt.gz"), "rt") if not l.startswith("#")]
    if backend == "reference":
        from isc_cipher import fdlibm_ref as F
        got = [(d2h(F.sin(h2d(a))), d2h(F.cos(h2d(a)))) for a, _, _ in rows]
    else:
        import numpy as np
        from isc_cipher import fdlibm_np as F
        x = np.array([h2d(a) for a, _, _ in rows])
        got = list(zip([d2h(v) for v in F.sin(x)], [d2h(v) for v in F.cos(x)]))
    bad = [(r[0], r[1], r[2], g[0], g[1]) for r, g in zip(rows, got) if (r[1], r[2]) != g]
    return not bad, {"vectors": len(rows), "mismatches": len(bad), "first_mismatches": bad[:5]}


def check_traj(backend):
    kat = json.load(open(os.path.join(VEC, "traj_kat.json")))["trajectories"]
    details = []
    ok = True
    if backend == "reference":
        from isc_cipher.isc_step import step_ref
        for t in kat:
            x, y = h2d(t["x0"]), h2d(t["y0"])
            h = hashlib.sha256()
            cps = {}
            for i in range(1, t["steps"] + 1):
                x, y = step_ref(x, y)
                h.update(struct.pack(">dd", x, y))
                if str(i) in t["checkpoints"]:
                    cps[str(i)] = [d2h(x), d2h(y)]
            same = h.hexdigest() == t["sha256_all_states"] and cps == t["checkpoints"]
            ok &= same
            details.append({"x0": t["x0"], "y0": t["y0"], "match": same})
    else:
        import numpy as np
        from isc_cipher.isc_step import step_vec
        x = np.array([h2d(t["x0"]) for t in kat])
        y = np.array([h2d(t["y0"]) for t in kat])
        hs = [hashlib.sha256() for _ in kat]
        cps = [{} for _ in kat]
        steps = kat[0]["steps"]
        for i in range(1, steps + 1):
            x, y = step_vec(x, y, 1)
            rec = np.stack([x, y], axis=-1).astype(">f8")
            for k in range(len(kat)):
                hs[k].update(rec[k].tobytes())
                if str(i) in kat[k]["checkpoints"]:
                    cps[k][str(i)] = [d2h(x[k]), d2h(y[k])]
        for k, t in enumerate(kat):
            same = hs[k].hexdigest() == t["sha256_all_states"] and cps[k] == t["checkpoints"]
            ok &= same
            details.append({"x0": t["x0"], "y0": t["y0"], "match": same})
    return ok, {"trajectories": details}


def check_streams(backend):
    kat = json.load(open(os.path.join(VEC, "stream_kat.json")))
    key, nonce = bytes.fromhex(kat["key_hex"]), bytes.fromhex(kat["nonce_hex"])
    h, w, c = kat["shape"]
    der = kdf.Derivation(key, nonce, kdf.context(1, 1, h, w, c))
    seeds = der.seeds()
    res = {}
    ok = True
    for g in kdf.STREAMS:
        e = kat["streams"][g]
        seeds_ok = [s.hex() for s in seeds[g]] == e["seeds_hex"]
        init_ok = [[d2h(a), d2h(b)] for a, b in (seed_to_state(s) for s in seeds[g])] == e["initial_states"]
        res[g] = {"seeds": seeds_ok, "initial_states": init_ok}
        ok &= seeds_ok and init_ok
    streams = build_streams(seeds, backend=backend, profile=1)
    for g in kdf.STREAMS:
        e = kat["streams"][g]
        st = streams[g]
        if backend == "reference":
            after = [[d2h(a), d2h(b)] for a, b in st.states]
        else:
            after = [[d2h(a), d2h(b)] for a, b in zip(st.x, st.y)]
        by = st.take(1024)
        if backend == "reference":
            final = [[d2h(a), d2h(b)] for a, b in st.states]
        else:
            final = [[d2h(a), d2h(b)] for a, b in zip(st.x, st.y)]
        r = {"after_burn_in": after == e["after_burn_in"], "first_1024_bytes": by.hex() == e["first_1024_bytes_hex"],
             "states_after_8_steps": final == e["states_after_8_steps"], "steps": st.steps}
        res[g].update(r)
        ok &= r["after_burn_in"] and r["first_1024_bytes"] and r["states_after_8_steps"] and st.steps == 8
    return ok, res


def check_cipher(backend):
    kat = json.load(open(os.path.join(VEC, "cipher_kat.json")))
    key, nonce = bytes.fromhex(kat["key_hex"]), bytes.fromhex(kat["nonce_hex"])
    res = []
    ok = True
    for case in kat["cases"]:
        h, w, c = case["shape"]
        n = h * w * c
        data = bytes((i * 37 + 11) % 256 for i in range(n))
        m = materials_TEST_ONLY(key, nonce, h, w, c, backend=backend)
        z = encrypt_bytes_with_nonce_TEST_ONLY(key, data, h, w, c, nonce, backend=backend)
        pi_bytes = b"".join(i.to_bytes(4, "big") for i in m["pi"])
        r = {
            "shape": case["shape"],
            "sbox": bytes(m["S"]).hex() == case["sbox_hex"],
            "ivs": (m["iv_f"], m["iv_b"]) == (case["iv_f"], case["iv_b"]),
            "pi": hashlib.sha256(pi_bytes).hexdigest() == case["pi_sha256"] and (case["pi"] is None or m["pi"] == case["pi"]),
            "a_b_prefix": m["a"][:1024].hex() == case["a_prefix_hex"] and m["b"][:1024].hex() == case["b_prefix_hex"],
            "steps": {g: m["streams"][g].steps for g in kdf.STREAMS} == case["steps"],
            "kcv": z[28:36].hex() == case["kcv_hex"],
            "body": hashlib.sha256(z[36:36 + n]).hexdigest() == case["body_sha256"],
            "ciphertext": hashlib.sha256(z).hexdigest() == case["ciphertext_sha256"]
            and (case["ciphertext_hex"] is None or z.hex() == case["ciphertext_hex"]),
        }
        p, hh, ww, cc = decrypt_bytes(key, z, backend=backend)
        r["decrypt_roundtrip"] = p == data and (hh, ww, cc) == (h, w, c)
        k_kcv = kdf.Derivation(key, nonce, kdf.context(1, 1, h, w, c)).kcv_key()
        r["kcv_recomputed_from_states"] = hmac.new(k_kcv, kcv_state_bytes(m["streams"]), hashlib.sha256).digest()[:8].hex() == case["kcv_hex"]
        ok &= all(v for k, v in r.items() if k != "shape")
        res.append(r)
    return ok, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["reference", "numpy"], required=True)
    ap.add_argument("--label", default=platform.node() or "host")
    args = ap.parse_args()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(ROOT, "results", "cipher_validation", f"gate_r_{args.label}_{args.backend}_{ts}")
    os.makedirs(out)
    env = environment(args.backend)
    log(f"Gate R, backend={args.backend}, {env['platform']}, Python {sys.version.split()[0]}")
    checks = {}
    for name, fn in [("R-fdlibm-hashes", lambda: check_fdlibm_hashes()), ("R-trig-KAT", lambda: check_trig(args.backend)),
                     ("R-trajectory-KAT", lambda: check_traj(args.backend)), ("R-stream-KAT", lambda: check_streams(args.backend)),
                     ("R-cipher-KAT", lambda: check_cipher(args.backend))]:
        t0 = time.time()
        try:
            ok, detail = fn()
            status = "PASS" if ok else "FAIL"
        except Exception as exc:  # reported, not hidden
            status, detail = "FAIL", {"exception": repr(exc)}
        checks[name] = {"status": status, "seconds": round(time.time() - t0, 1), "detail": detail}
        log(f"{name}: {status} ({checks[name]['seconds']} s)")
    report = {"gate": "R", "backend": args.backend, "environment": env, "checks": checks,
              "vectors_provenance": json.load(open(os.path.join(VEC, "PROVENANCE.json"))),
              "overall": "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"}
    json.dump(report, open(os.path.join(out, "report.json"), "x"), indent=1, default=str)
    open(os.path.join(out, "log.txt"), "x").write("\n".join(LOG) + "\n")
    log(f"overall: {report['overall']}  -> {out}")


if __name__ == "__main__":
    main()
