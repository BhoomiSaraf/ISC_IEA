"""Gate R, revision-3 extension: the 26,000 real-orbit KAT-1 arguments (vectors/trig_kat_ext.txt.gz).

    python -I isc_cipher_kat/gate_r_ext.py --backend numpy|reference --label <env>

Also re-checks the original 74,063 vectors, so the full 100,063-argument KAT 1 passes or fails as one.
The Checkpoint-3 script gate_r.py and its reports are left unchanged. Output:
results/cipher_validation/gate_r_ext_<label>_<backend>_<UTC>/report.json + log.txt
"""

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import platform
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
VEC = os.path.join(ROOT, "isc_cipher_kat", "vectors")


def d2h(v):
    return struct.pack(">d", float(v)).hex()


def h2d(h):
    return struct.unpack(">d", bytes.fromhex(h))[0]


def check(path, backend):
    rows = [l.split() for l in gzip.open(path, "rt") if not l.startswith("#")]
    if backend == "reference":
        from isc_cipher import fdlibm_ref as F
        got = [(d2h(F.sin(h2d(a))), d2h(F.cos(h2d(a)))) for a, _, _ in rows]
    else:
        import numpy as np
        from isc_cipher import fdlibm_np as F
        x = np.array([h2d(a) for a, _, _ in rows])
        got = list(zip([d2h(v) for v in F.sin(x)], [d2h(v) for v in F.cos(x)]))
    bad = [r for r, g in zip(rows, got) if (r[1], r[2]) != g]
    return {"file": os.path.basename(path), "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
            "vectors": len(rows), "mismatches": len(bad), "first_mismatches": bad[:5],
            "status": "PASS" if not bad else "FAIL"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["reference", "numpy"], required=True)
    ap.add_argument("--label", default=platform.node() or "host")
    a = ap.parse_args()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(ROOT, "results", "cipher_validation", f"gate_r_ext_{a.label}_{a.backend}_{ts}")
    os.makedirs(out)
    res = [check(os.path.join(VEC, f), a.backend) for f in ("trig_kat.txt.gz", "trig_kat_ext.txt.gz")]
    env = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine()}
    if a.backend == "numpy":
        import numpy as np
        env["numpy"] = np.__version__
    report = {"gate": "R (revision-3 KAT-1 extension)", "backend": a.backend, "environment": env, "checks": res,
              "total_vectors": sum(r["vectors"] for r in res),
              "overall": "PASS" if all(r["status"] == "PASS" for r in res) else "FAIL"}
    json.dump(report, open(os.path.join(out, "report.json"), "x"), indent=1)
    msg = f"{a.label} {a.backend}: " + ", ".join(f"{r['file']} {r['status']} ({r['vectors']}, {r['mismatches']} mismatches)" for r in res) + f" -> {report['overall']}"
    open(os.path.join(out, "log.txt"), "x").write(msg + "\n")
    print(msg)
    print(out)


if __name__ == "__main__":
    main()
