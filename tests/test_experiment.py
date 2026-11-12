import json
import os

import pytest

from isc_seq.experiment import load_config, run_experiment

SMALL = {
    "name": "t", "n_sequences": 3, "bits_per_sequence": 4096, "transient": 50, "batch_size": 2,
    "raw_stats": {"max_lag": 3, "entropy_ns": [500, 1000]},
    "periodicity": {"float32_ics": 1, "float32_max_steps": 200, "float64_ics": 1, "float64_max_steps": 200,
                    "quant_bits": [4], "quant_ics": 2, "quant_max_steps": 50000, "legacy_check": False},
    "legacy_reproduction": False,
}


def test_rejects_non_frozen_params():
    with pytest.raises(ValueError):
        load_config(overrides={"params": {"a": 0.8, "c": 0.4, "d": 6.0, "omega": 10.0}})


def test_rejects_unknown_method():
    with pytest.raises(ValueError):
        load_config(overrides={"methods": ["nope"]})


def test_small_run_outputs_and_reproducibility(tmp_path):
    cfg = load_config(overrides=SMALL)
    d1, r1 = run_experiment(cfg, str(tmp_path), "a")
    d2, r2 = run_experiment(cfg, str(tmp_path), "b")
    for name in ["config.json", "environment.json", "initial_conditions.csv", "raw_trajectory_seq000.npz",
                 "bit_stats.csv", "nist/summary.csv", "periodicity.csv", "results.json", "report.md",
                 "manifest.json", "bitstreams/sign.bin"]:
        assert os.path.exists(os.path.join(d1, name)), name
    assert os.path.getsize(os.path.join(d1, "bitstreams", "arccos8.bin")) == 3 * 4096 // 8
    m1 = json.load(open(os.path.join(d1, "manifest.json")))
    m2 = json.load(open(os.path.join(d2, "manifest.json")))
    for f in ["bitstreams/mantissa8.bin", "raw_trajectory_seq000.npz", "nist/summary.csv", "periodicity.csv"]:
        assert m1[f]["sha256"] == m2[f]["sha256"], f
    assert r1["nist"] == r2["nist"]
    with pytest.raises(FileExistsError):
        run_experiment(cfg, str(tmp_path), "a")
