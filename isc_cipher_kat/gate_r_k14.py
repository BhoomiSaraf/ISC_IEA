"""Gate R, k14 extension: reproducibility checks of the new VERSION=2 / k14_scaled_modulo_v1
extraction profile against vectors/stream_kat_k14.json and vectors/cipher_kat_k14.json.

    python isc_cipher_kat/gate_r_k14.py --backend reference      (R1)
    python isc_cipher_kat/gate_r_k14.py --backend numpy          (V1)
    python isc_cipher_kat/gate_r_k14.py --backend both           (runs both backends and cross-checks
                                                                    that they produce identical bytes)

This does not re-check R-fdlibm-hashes, R-trig-KAT, or R-trajectory-KAT: those vectors (trig_kat,
traj_kat) are extraction-independent and are already checked, unmodified, by gate_r.py. Running
gate_r.py and gate_r_k14.py together covers both extraction profiles under both container
versions without altering gate_r.py's own checks in any way.

Writes results/cipher_validation/gate_r_k14_<label>_<backend>_<UTC>/report.json and log.txt.
"""

import argparse
import datetime as dt
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
from isc_cipher.generator import EXTRACTION_K14_SCALED_MODULO_V1 as E2  # noqa: E402
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


def check_streams_k14(backend):
    kat = json.load(open(os.path.join(VEC, "stream_kat_k14.json")))
    key, nonce = bytes.fromhex(kat["key_hex"]), bytes.fromhex(kat["nonce_hex"])
    h, w, c = kat["shape"]
    ctx = kdf.context(1, 1, h, w, c, extraction=E2)
    assert ctx.hex() == kat["ctx_hex"], "k14 VERSION=2 ctx encoding drifted from the vectors"
    der = kdf.Derivation(key, nonce, ctx)
    seeds = der.seeds()
    res = {}
    ok = True
    for g in kdf.STREAMS:
        e = kat["streams"][g]
        seeds_ok = [s.hex() for s in seeds[g]] == e["seeds_hex"]
        init_ok = [[d2h(a), d2h(b)] for a, b in (seed_to_state(s) for s in seeds[g])] == e["initial_states"]
        res[g] = {"seeds": seeds_ok, "initial_states": init_ok}
        ok &= seeds_ok and init_ok
    streams = build_streams(seeds, backend=backend, profile=1, extraction=E2)
    for g in kdf.STREAMS:
        e = kat["streams"][g]
        st = streams[g]
        after = [[d2h(a), d2h(b)] for a, b in (st.states if backend == "reference" else zip(st.x, st.y))]
        by = st.take(1024)
        final = [[d2h(a), d2h(b)] for a, b in (st.states if backend == "reference" else zip(st.x, st.y))]
        r = {"after_burn_in": after == e["after_burn_in"], "first_1024_bytes": by.hex() == e["first_1024_bytes_hex"],
             "states_after_8_steps": final == e["states_after_8_steps"], "steps": st.steps}
        res[g].update(r)
        ok &= r["after_burn_in"] and r["first_1024_bytes"] and r["states_after_8_steps"] and st.steps == 8
    return ok, res


def check_cipher_k14(backend):
    kat = json.load(open(os.path.join(VEC, "cipher_kat_k14.json")))
    key, nonce = bytes.fromhex(kat["key_hex"]), bytes.fromhex(kat["nonce_hex"])
    res = []
    ok = True
    for case in kat["cases"]:
        h, w, c = case["shape"]
        n = h * w * c
        data = bytes((i * 37 + 11) % 256 for i in range(n))
        m = materials_TEST_ONLY(key, nonce, h, w, c, backend=backend, extraction=E2)
        z = encrypt_bytes_with_nonce_TEST_ONLY(key, data, h, w, c, nonce, backend=backend, extraction=E2)
        pi_bytes = b"".join(i.to_bytes(4, "big") for i in m["pi"])
        r = {
            "shape": case["shape"],
            "header": z[4] == 2 and z[36] == E2,
            "sbox": bytes(m["S"]).hex() == case["sbox_hex"],
            "ivs": (m["iv_f"], m["iv_b"]) == (case["iv_f"], case["iv_b"]),
            "pi": hashlib.sha256(pi_bytes).hexdigest() == case["pi_sha256"] and (case["pi"] is None or m["pi"] == case["pi"]),
            "a_b_prefix": m["a"][:1024].hex() == case["a_prefix_hex"] and m["b"][:1024].hex() == case["b_prefix_hex"],
            "steps": {g: m["streams"][g].steps for g in kdf.STREAMS} == case["steps"],
            "kcv": z[28:36].hex() == case["kcv_hex"],
            "body": hashlib.sha256(z[37:37 + n]).hexdigest() == case["body_sha256"],
            "ciphertext": hashlib.sha256(z).hexdigest() == case["ciphertext_sha256"]
            and (case["ciphertext_hex"] is None or z.hex() == case["ciphertext_hex"]),
        }
        p, hh, ww, cc = decrypt_bytes(key, z, backend=backend)
        r["decrypt_roundtrip"] = p == data and (hh, ww, cc) == (h, w, c)
        k_kcv = kdf.Derivation(key, nonce, kdf.context(1, 1, h, w, c, extraction=E2)).kcv_key()
        r["kcv_recomputed_from_states"] = hmac.new(k_kcv, kcv_state_bytes(m["streams"]), hashlib.sha256).digest()[:8].hex() == case["kcv_hex"]
        ok &= all(v for k, v in r.items() if k != "shape")
        res.append(r)
    return ok, res


def check_backend_cross_equal():
    """Reference and numpy backends must produce byte-identical VERSION=2/k14 ciphertexts."""
    kat = json.load(open(os.path.join(VEC, "cipher_kat_k14.json")))
    key, nonce = bytes.fromhex(kat["key_hex"]), bytes.fromhex(kat["nonce_hex"])
    res = []
    ok = True
    for case in kat["cases"]:
        h, w, c = case["shape"]
        n = h * w * c
        data = bytes((i * 37 + 11) % 256 for i in range(n))
        z_ref = encrypt_bytes_with_nonce_TEST_ONLY(key, data, h, w, c, nonce, backend="reference", extraction=E2)
        z_np = encrypt_bytes_with_nonce_TEST_ONLY(key, data, h, w, c, nonce, backend="numpy", extraction=E2)
        same = z_ref == z_np
        ok &= same
        res.append({"shape": case["shape"], "reference_equals_numpy": same})
    return ok, res


def run_checks(backend):
    checks = {}
    for name, fn in [("R-k14-stream-KAT", lambda: check_streams_k14(backend)),
                      ("R-k14-cipher-KAT", lambda: check_cipher_k14(backend))]:
        t0 = time.time()
        try:
            ok, detail = fn()
            status = "PASS" if ok else "FAIL"
        except Exception as exc:
            status, detail = "FAIL", {"exception": repr(exc)}
        checks[name] = {"status": status, "seconds": round(time.time() - t0, 1), "detail": detail}
        log(f"{name} ({backend}): {status} ({checks[name]['seconds']} s)")
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["reference", "numpy", "both"], required=True)
    ap.add_argument("--label", default=platform.node() or "host")
    args = ap.parse_args()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(ROOT, "results", "cipher_validation", f"gate_r_k14_{args.label}_{args.backend}_{ts}")
    os.makedirs(out)
    log(f"Gate R (k14 extension), backend={args.backend}, Python {sys.version.split()[0]}")
    checks = {}
    backends = ["reference", "numpy"] if args.backend == "both" else [args.backend]
    for b in backends:
        checks.update({f"{k} [{b}]": v for k, v in run_checks(b).items()})
    if args.backend == "both":
        t0 = time.time()
        try:
            ok, detail = check_backend_cross_equal()
            status = "PASS" if ok else "FAIL"
        except Exception as exc:
            status, detail = "FAIL", {"exception": repr(exc)}
        checks["R-k14-backend-cross-equal"] = {"status": status, "seconds": round(time.time() - t0, 1), "detail": detail}
        log(f"R-k14-backend-cross-equal: {status}")
    report = {"gate": "R (k14 extension)", "backend": args.backend, "checks": checks,
              "overall": "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"}
    json.dump(report, open(os.path.join(out, "report.json"), "x"), indent=1, default=str)
    open(os.path.join(out, "log.txt"), "x").write("\n".join(LOG) + "\n")
    log(f"overall: {report['overall']}  -> {out}")


if __name__ == "__main__":
    main()
