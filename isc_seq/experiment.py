"""Config-driven sequence-generation experiment for the frozen ISC map.

Every run writes into a new directory results/sequence_generation/<run_id>/ and
refuses to reuse an existing one.  All numbers in report.md are computed in the
same run and also stored in results.json; manifest.json lists SHA-256 hashes of
every output file.
"""

import csv
import datetime as _dt
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np
import scipy

from . import __version__, nist
from .extract import METHODS
from .isc_map import FROZEN_PARAMS, ISCParams, legacy_step
from .periodicity import as_state, brent, floyd_meeting_index, make_map
from .stats import bit_stats, entropy_vs_n, raw_trajectory_stats
from .trajectory import generate_trajectory, initial_conditions, save_trajectory

DEFAULT_CONFIG = {
    "name": "default",
    "params": FROZEN_PARAMS.as_dict(),
    "seed": 20261025,
    "n_sequences": 100,
    "bits_per_sequence": 1_000_000,
    "transient": 5000,
    "batch_size": 10,
    "methods": list(METHODS),
    "nist": {"alpha": 0.01, "serial_m": 16, "apen_m": 10, "block_M": 128},
    "raw_stats": {"max_lag": 10, "entropy_ns": [10_000, 50_000, 100_000, 200_000, 500_000]},
    "periodicity": {
        "float32_ics": 10, "float32_max_steps": 4_000_000,
        "float64_ics": 3, "float64_max_steps": 2_000_000,
        "quant_bits": [8, 10, 12, 14, 16], "quant_ics": 10, "quant_max_steps": 4_000_000,
        "legacy_check": True, "legacy_floyd_max_iter": 1_000_000,
    },
    "legacy_reproduction": True,
    "save": {"raw_trajectory_first_sequence": True, "bitstreams": True},
}


def load_config(path=None, overrides=None):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    if overrides:
        cfg.update(overrides)
    if ISCParams(**cfg["params"]) != FROZEN_PARAMS:
        raise ValueError(f"config params {cfg['params']} differ from the frozen ISC parameters")
    if cfg["bits_per_sequence"] % 8:
        raise ValueError("bits_per_sequence must be a multiple of 8")
    unknown = set(cfg["methods"]) - set(METHODS)
    if unknown:
        raise ValueError(f"unknown extraction methods: {sorted(unknown)}")
    return cfg


def source_hashes():
    """SHA-256 of every isc_seq source file, so a run can be tied to the exact code."""
    here = os.path.dirname(os.path.abspath(__file__))
    out = {}
    for name in sorted(os.listdir(here)):
        if name.endswith(".py"):
            with open(os.path.join(here, name), "rb") as f:
                out[name] = hashlib.sha256(f.read()).hexdigest()
    return out


def environment():
    return {
        "source_sha256": source_hashes(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "isc_seq": __version__,
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }


class Run:
    def __init__(self, out_root, run_id):
        self.dir = os.path.join(out_root, run_id)
        if os.path.exists(self.dir):
            raise FileExistsError(f"run directory already exists: {self.dir}")
        os.makedirs(self.dir)
        self.files = []

    def path(self, *parts):
        p = os.path.join(self.dir, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.exists(p):
            raise FileExistsError(p)
        self.files.append(p)
        return p

    def write_json(self, name, obj):
        with open(self.path(name), "x", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, default=_json_default)

    def write_csv(self, name, rows, fieldnames=None):
        rows = list(rows)
        fieldnames = fieldnames or list(rows[0].keys())
        with open(self.path(name), "x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    def manifest(self):
        out = {}
        for p in self.files:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[os.path.relpath(p, self.dir).replace(os.sep, "/")] = {"sha256": h.hexdigest(), "bytes": os.path.getsize(p)}
        with open(os.path.join(self.dir, "manifest.json"), "x", encoding="utf-8") as f:
            json.dump(out, f, indent=2)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_sequences(cfg, run):
    """Generate trajectories, extract bits per method, run NIST battery per sequence."""
    m, n_bits, T = cfg["n_sequences"], cfg["bits_per_sequence"], cfg["transient"]
    methods = cfg["methods"]
    n_iter = max(METHODS[name].iterations_for(n_bits) for name in methods)
    x0s, y0s = initial_conditions(cfg["seed"], m)
    run.write_csv("initial_conditions.csv",
                  [{"sequence": i, "x0": repr(float(x0s[i])), "y0": repr(float(y0s[i]))} for i in range(m)])

    nc = cfg["nist"]
    pvals = {name: [] for name in methods}
    bit_rows = {name: [] for name in methods}
    bit_files = {}
    if cfg["save"]["bitstreams"]:
        for name in methods:
            bit_files[name] = open(run.path("bitstreams", f"{name}.bin"), "xb")
    raw_stats = entropy_rows = None
    try:
        for start in range(0, m, cfg["batch_size"]):
            idx = np.arange(start, min(start + cfg["batch_size"], m))
            _log(f"sequences {idx[0]}..{idx[-1]}: iterating {n_iter} steps after {T} transient")
            X, Y = generate_trajectory(x0s[idx], y0s[idx], n_iter, transient=T)
            for j, s in enumerate(idx):
                xs, ys = X[:, j], Y[:, j]
                if s == 0:
                    rs = cfg["raw_stats"]
                    raw_stats = raw_trajectory_stats(xs, ys, max_lag=rs["max_lag"])
                    entropy_rows = entropy_vs_n(xs, ys, rs["entropy_ns"])
                    if cfg["save"]["raw_trajectory_first_sequence"]:
                        save_trajectory(run.path("raw_trajectory_seq000.npz"), xs, ys,
                                        {"x0": float(x0s[0]), "y0": float(y0s[0]), "transient": T,
                                         "params": cfg["params"], "first_index": T + 1})
                for name in methods:
                    bits = METHODS[name](xs[: METHODS[name].iterations_for(n_bits)],
                                         ys[: METHODS[name].iterations_for(n_bits)])[:n_bits]
                    if name in bit_files:
                        bit_files[name].write(np.packbits(bits, bitorder="big").tobytes())
                    if s < 10:
                        bit_rows[name].append(bits)
                    pvals[name].append(nist.run_battery(bits, nc["serial_m"], nc["apen_m"], nc["block_M"]))
            del X, Y
    finally:
        for f in bit_files.values():
            f.close()

    summary, bits_summary = {}, {}
    for name in methods:
        tests = list(pvals[name][0])
        run.write_csv(f"nist/pvalues_{name}.csv",
                      [dict(sequence=i, **row) for i, row in enumerate(pvals[name])],
                      ["sequence"] + tests)
        table = {t: [row[t] for row in pvals[name]] for t in tests}
        summary[name] = nist.evaluate(table, nc["alpha"])
        bits_summary[name] = bit_stats(np.concatenate(bit_rows[name]))
        bits_summary[name]["sequences_used"] = len(bit_rows[name])
    rows = [dict(method=name, test=t, **v) for name in methods for t, v in summary[name].items()]
    run.write_csv("nist/summary.csv", rows)
    run.write_csv("bit_stats.csv", [dict(method=k, **v) for k, v in bits_summary.items()])
    run.write_json("raw_stats_seq000.json", raw_stats)
    run.write_csv("entropy_vs_n_seq000.csv", entropy_rows)
    return {"nist": summary, "bit_stats": bits_summary, "raw_stats": raw_stats,
            "entropy_vs_n": entropy_rows, "iterations_per_sequence": n_iter}


def run_periodicity(cfg, run):
    pc = cfg["periodicity"]
    rows = []

    def record(label, dtype, quant, x0, y0, res, budget):
        rows.append({"case": label, "dtype": np.dtype(dtype).name, "quant_bits": quant,
                     "x0": repr(float(x0)), "y0": repr(float(y0)),
                     "mu": None if res is None else res[0], "lambda": None if res is None else res[1],
                     "budget_steps": budget, "cycle_found": res is not None})

    x0s, y0s = initial_conditions(cfg["seed"] + 1, max(pc["float32_ics"], pc["float64_ics"], pc["quant_ics"]))
    legacy = {}
    if pc["legacy_check"]:
        _log("periodicity: legacy float32 orbit from (0.1, 0.1)")
        f = make_map(np.float32, step=legacy_step)
        s0 = as_state(0.1, 0.1, np.float32)
        res = brent(f, s0, pc["float32_max_steps"])
        record("legacy_step float32 (0.1,0.1)", np.float32, None, 0.1, 0.1, res, pc["float32_max_steps"])
        legacy["brent"] = res
        legacy["floyd_meeting_index"] = floyd_meeting_index(f, s0, pc["legacy_floyd_max_iter"])
        res = brent(make_map(np.float32), s0, pc["float32_max_steps"])
        record("isc_step float32 (0.1,0.1)", np.float32, None, 0.1, 0.1, res, pc["float32_max_steps"])
    for i in range(pc["float32_ics"]):
        _log(f"periodicity: float32 IC {i}")
        res = brent(make_map(np.float32), as_state(x0s[i], y0s[i], np.float32), pc["float32_max_steps"])
        record("isc_step float32", np.float32, None, np.float32(x0s[i]), np.float32(y0s[i]), res, pc["float32_max_steps"])
    for k in pc["quant_bits"]:
        _log(f"periodicity: {k}-bit quantised state")
        for i in range(pc["quant_ics"]):
            res = brent(make_map(np.float64, quant_bits=k), as_state(x0s[i], y0s[i], np.float64), pc["quant_max_steps"])
            record(f"isc_step float64 quantised {k} bits", np.float64, k, x0s[i], y0s[i], res, pc["quant_max_steps"])
    for i in range(pc["float64_ics"]):
        _log(f"periodicity: float64 IC {i}")
        res = brent(make_map(np.float64), as_state(x0s[i], y0s[i], np.float64), pc["float64_max_steps"])
        record("isc_step float64", np.float64, None, x0s[i], y0s[i], res, pc["float64_max_steps"])
    run.write_csv("periodicity.csv", rows)
    return {"rows": rows, "legacy": legacy}


def run_legacy_reproduction(base_dir):
    """Recompute legacy lag-1 ACF of x with legacy_step and compare with the stored CSV (read-only)."""
    xs, _ = generate_trajectory(0.1, 0.1, 100_000, transient=5000, step=legacy_step)
    s = xs - xs.mean()
    acf1 = float(s[1:] @ s[:-1] / (s @ s))
    stored = None
    path = os.path.join(base_dir, "plots", "final_validation", "validation_report.csv")
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["Metric"] == "ACF_Lag1_X":
                    stored = float(row["Value"])
    return {"acf1_x_recomputed": acf1, "acf1_x_stored": stored, "source": "plots/final_validation/validation_report.csv"}


def run_experiment(cfg, out_root, run_id=None, base_dir=None):
    run_id = run_id or f"{cfg['name']}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run = Run(out_root, run_id)
    t0 = time.time()
    run.write_json("config.json", cfg)
    env = environment()
    run.write_json("environment.json", env)

    results = {"run_id": run_id, "config": cfg, "environment": env}
    results.update(run_sequences(cfg, run))
    results["periodicity"] = run_periodicity(cfg, run)
    if cfg.get("legacy_reproduction") and base_dir:
        _log("legacy reproduction check")
        results["legacy_reproduction"] = run_legacy_reproduction(base_dir)
    results["elapsed_seconds"] = time.time() - t0
    run.write_json("results.json", results)

    from .report import render_report
    with open(run.path("report.md"), "x", encoding="utf-8") as f:
        f.write(render_report(results))
    run.manifest()
    _log(f"done in {results['elapsed_seconds']:.0f} s -> {run.dir}")
    return run.dir, results
