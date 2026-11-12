"""Run directories, environment records, public experiment keys, logging and manifests."""

import datetime as dt
import hashlib
import json
import os
import platform
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(ROOT, "results", "encryption_experiments")
PUBLIC_SEED_SALT = b"ISC-IMG Gate A public experiment seed"


def public_key(label):
    """Deterministic PUBLIC test key for experiment `label` (reproducible; never a real secret)."""
    from isc_cipher.kdf import hkdf_expand, hkdf_extract
    return hkdf_expand(hkdf_extract(PUBLIC_SEED_SALT, label.encode()), b"key", 32)


def public_nonce(label, length=16):
    from isc_cipher.kdf import hkdf_expand, hkdf_extract
    return hkdf_expand(hkdf_extract(PUBLIC_SEED_SALT, label.encode()), b"nonce", length)


def source_hashes():
    out = {}
    for pkg in ("isc_cipher", "isc_eval"):
        d = os.path.join(ROOT, pkg)
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                out[f"{pkg}/{name}"] = hashlib.sha256(open(os.path.join(d, name), "rb").read()).hexdigest()
    return out


def environment():
    env = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
           "processor": platform.processor(), "source_sha256": source_hashes(),
           "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    for mod in ("numpy", "cryptography", "scipy", "sklearn", "skimage", "mpmath"):
        try:
            env[mod] = __import__(mod).__version__
        except Exception:
            env[mod] = None
    return env


def _default(o):
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bool_):
            return bool(o)
    except ImportError:
        pass
    if isinstance(o, bytes):
        return o.hex()
    raise TypeError(type(o))


class Run:
    """A fresh output directory results/encryption_experiments/<id>_<mode>_<UTC>/ (never reused)."""

    def __init__(self, exp_id, mode, config):
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.dir = os.path.join(OUT_ROOT, f"{exp_id}_{mode}_{ts}")
        os.makedirs(self.dir)
        self.t0 = time.time()
        self.exp_id, self.mode = exp_id, mode
        self._log = open(os.path.join(self.dir, "log.txt"), "x", encoding="utf-8")
        self.write_json("config.json", dict(config, experiment=exp_id, mode=mode))
        self.write_json("environment.json", environment())
        with open(os.path.join(self.dir, "command.txt"), "x", encoding="utf-8") as f:
            f.write(" ".join(sys.argv) + "\n")
        self.log(f"start {exp_id} mode={mode}")

    def path(self, *parts):
        p = os.path.join(self.dir, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def log(self, msg):
        line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line, flush=True)
        self._log.write(line + "\n")
        self._log.flush()

    def write_json(self, name, obj):
        with open(self.path(name), "x", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, default=_default)

    def finish(self, summary):
        summary = dict(summary, elapsed_seconds=round(time.time() - self.t0, 2))
        self.write_json("summary.json", summary)
        self.log(f"finished in {summary['elapsed_seconds']} s")
        self._log.close()
        man = {}
        for dp, _, fs in os.walk(self.dir):
            for fn in fs:
                p = os.path.join(dp, fn)
                man[os.path.relpath(p, self.dir).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        with open(os.path.join(self.dir, "manifest.json"), "x", encoding="utf-8") as f:
            json.dump(man, f, indent=1)
        return summary


def cli(default_modes=("diagnostic", "full")):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=default_modes, required=True)
    return ap.parse_args()
