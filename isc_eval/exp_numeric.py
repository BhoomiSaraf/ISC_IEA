"""A11: (i) cross-platform correctness of profile 1 (E1 V1 <-> E2 R1), (ii) host-math-library PROXY
(not NumPy profile 2), (iii) KCV outcome rates under single-ulp sin perturbations."""

import gzip
import hashlib
import json
import math
import os
import subprocess

import numpy as np

import isc_cipher
from isc_cipher import NumericalDivergenceError, cipher, fdlibm_np
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY
from isc_cipher.generator import kcv_state_bytes
from isc_seq.sts_official import to_wsl_path

from .common import ROOT, Run, public_key, public_nonce

DISTRO = "Ubuntu-24.04"


def wsl(*args):
    # run the worker as a script: "-I -m" would drop the project root from sys.path (diagnostic-run bug)
    p = subprocess.run(["wsl", "-d", DISTRO, "--cd", to_wsl_path(ROOT), "--", "python3", "-I",
                        to_wsl_path(os.path.join(ROOT, "isc_eval", "xplat_worker.py")), *args],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode(errors="replace")


def a11_xplat(mode):
    count = 100 if mode == "full" else 2
    run = Run("A11_xplat", mode, {"images_per_direction": count, "dims": "16x16, C in {1,3}", "profile": 1,
                                  "E1": "Windows, V1 (NumPy)", "E2": "WSL Ubuntu, R1 (pure Python)"})
    key = public_key("A11/xplat")
    rng = np.random.default_rng(11)
    d1 = run.path("raw", "e1_to_e2")
    os.makedirs(d1)
    plain = {}
    for i in range(count):
        c = int(rng.choice([1, 3]))
        p = bytes(rng.integers(0, 256, 256 * c, dtype=np.uint8))
        open(os.path.join(d1, f"img{i:03d}.isci"), "wb").write(isc_cipher.encrypt_bytes(key, p, 16, 16, c, backend="numpy"))
        plain[f"img{i:03d}.isci"] = hashlib.sha256(p).hexdigest()
    rc, out = wsl("decrypt", to_wsl_path(d1))
    run.log(f"E2 decrypt rc={rc} {out[-300:]}")
    res = json.load(open(os.path.join(d1, "decrypt_results.json")))
    e1_to_e2_fail = [k for k, v in res["results"].items() if not v["ok"] or v["sha256"] != plain[k]]
    d2 = run.path("raw", "e2_to_e1")
    rc, out = wsl("encrypt", to_wsl_path(d2), str(count))
    run.log(f"E2 encrypt rc={rc} {out[-300:]}")
    e2_to_e1_fail = []
    for name in sorted(os.listdir(d2)):
        if name.endswith(".isci"):
            z = open(os.path.join(d2, name), "rb").read()
            try:
                p = isc_cipher.decrypt_bytes(key, z, backend="numpy")[0]
                if p != open(os.path.join(d2, name[:-5] + ".plain"), "rb").read():
                    e2_to_e1_fail.append(name)
            except isc_cipher.ISCError as e:
                e2_to_e1_fail.append(f"{name}:{type(e).__name__}")
    return run.finish({"e1_to_e2": {"images": count, "failures": e1_to_e2_fail, "e2": res["platform"]},
                       "e2_to_e1": {"images": count, "failures": e2_to_e1_fail},
                       "test_failed": bool(e1_to_e2_fail or e2_to_e1_fail)})


def a11_hostlibm_proxy(mode):
    run = Run("A11_hostlibm_proxy", mode, {"label": "HOST-MATH-LIBRARY PROXY: Python math.sin/math.cos on E1 (MSVC CRT) "
                                           "vs E2 (glibc). Does NOT test NumPy profile 2 and does NOT establish its "
                                           "cross-platform reproducibility. NumPy is not installed on E2."})
    from . import xplat_worker
    o1 = run.path("raw", "E1")
    xplat_worker.cmd_mathproxy(o1)
    o2 = run.path("raw", "E2")
    rc, out = wsl("mathproxy", to_wsl_path(o2))
    run.log(f"E2 rc={rc} {out[-300:]}")
    l1 = gzip.open(os.path.join(o1, "math_trig.txt.gz"), "rt").read().split("\n")
    l2 = gzip.open(os.path.join(o2, "math_trig.txt.gz"), "rt").read().split("\n")
    diff = sum(1 for a, b in zip(l1, l2) if a != b)
    t1 = np.fromfile(os.path.join(o1, "math_traj.bin"), dtype=">f8").reshape(10, -1, 2)
    t2 = np.fromfile(os.path.join(o2, "math_traj.bin"), dtype=">f8").reshape(10, -1, 2)
    first = []
    for k in range(10):
        neq = np.nonzero(np.any(t1[k].view(np.uint64) != t2[k].view(np.uint64), axis=1))[0]
        first.append(int(neq[0]) + 1 if len(neq) else None)
    return run.finish({"arguments": len(l1) - 1, "sin_or_cos_results_differing_E1_vs_E2": diff,
                       "trajectory_first_divergence_step": first, "label": "proxy measurement only"})


def a11_kcv(mode):
    trials = 1000 if mode == "full" else 5
    run = Run("A11_kcv", mode, {"trials": trials, "image": [4, 6, 3], "backend": "numpy (V1)",
                                "perturbation": "one sin call uniform over all sin calls of one decryption; one element "
                                "uniform over that call's array; +-1 ulp uniform; public seed 1103"})
    key, nonce = public_key("A11/kcv"), public_nonce("A11/kcv")
    data = bytes((i * 37 + 11) % 256 for i in range(72))
    z = encrypt_bytes_with_nonce_TEST_ONLY(key, data, 4, 6, 3, nonce)
    real_sin = fdlibm_np.sin
    real_kcv = cipher._kcv
    lengths = []

    def counting(x):
        out = real_sin(x)
        lengths.append(len(out))
        return out
    fdlibm_np.sin = counting
    try:
        assert isc_cipher.decrypt_bytes(key, z)[0] == data
    finally:
        fdlibm_np.sin = real_sin
    ref_states = {}

    def spy(k, streams):
        ref_states["s"] = kcv_state_bytes(streams)
        return real_kcv(k, streams)
    cipher._kcv = spy
    isc_cipher.decrypt_bytes(key, z)
    reference = ref_states["s"]
    rng = np.random.default_rng(1103)
    counts = {"identical_states_correct_plaintext": 0, "detected_by_kcv": 0, "WRONG_PLAINTEXT_RELEASED": 0,
              "states_differ_but_correct_plaintext": 0}
    raw = []
    try:
        for t in range(trials):
            call = int(rng.integers(1, len(lengths) + 1))
            elem = int(rng.integers(0, lengths[call - 1]))
            direction = 1.0 if rng.random() < 0.5 else -1.0
            n = {"c": 0}

            def pert(x, call=call, elem=elem, direction=direction, n=n):
                out = real_sin(x)
                n["c"] += 1
                if n["c"] == call:
                    out = out.copy()
                    out[elem] = math.nextafter(out[elem], direction * math.inf)
                return out
            fdlibm_np.sin = pert
            try:
                p = isc_cipher.decrypt_bytes(key, z)[0]
                same = ref_states["s"] == reference
                if p != data:
                    cls = "WRONG_PLAINTEXT_RELEASED"
                elif same:
                    cls = "identical_states_correct_plaintext"
                else:
                    cls = "states_differ_but_correct_plaintext"
            except NumericalDivergenceError:
                cls = "detected_by_kcv"
            finally:
                fdlibm_np.sin = real_sin
            counts[cls] += 1
            raw.append({"trial": t, "call": call, "element": elem, "direction": direction, "outcome": cls})
    finally:
        cipher._kcv = real_kcv
        fdlibm_np.sin = real_sin
    from scipy.stats import beta

    def cp(k, n):
        lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
        hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
        return [lo, hi]
    run.write_json("raw/trials.json", raw)
    return run.finish({"sin_calls_per_decryption": len(lengths), "counts": counts,
                       "rates_clopper_pearson_95": {k: [v / trials, cp(v, trials)] for k, v in counts.items()},
                       "test_failed": counts["WRONG_PLAINTEXT_RELEASED"] > 0})
