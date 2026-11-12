"""Parser and aggregate tests for the official NIST STS 2.1.2 driver (isc_seq.sts_official).

Synthetic fixtures reproduce the exact output formats written by assess (printf "%f"
p-values, stats.txt headers, finalAnalysisReport.txt rows).  The last tests check a real
official run when one is present.
"""

import json
import os

import numpy as np
import pytest

from isc_seq import sts_official as so
from conftest import ROOT

N_BITS = 1_000_000


def write_fixture(root, n_streams, pvals, re_J=None, rev_J=None, drop_lines=None):
    """pvals: test -> list (per sequence) of lists of floats."""
    for test in so.TESTS:
        d = os.path.join(root, "experiments", "AlgorithmTesting", test)
        os.makedirs(d, exist_ok=True)
        lines = [f"{p:f}" for seq in pvals[test] for p in seq]
        if drop_lines and test in drop_lines:
            lines = lines[:-drop_lines[test]]
        with open(os.path.join(d, "results.txt"), "w") as f:
            f.write("\n".join(lines) + "\n")
        if test in ("RandomExcursions", "RandomExcursionsVariant"):
            Js = re_J if test == "RandomExcursions" else rev_J
            header = "RANDOM EXCURSIONS TEST" if test == "RandomExcursions" else "RANDOM EXCURSIONS VARIANT TEST"
            fmt = "%04d" if test == "RandomExcursions" else "%d"
            with open(os.path.join(d, "stats.txt"), "w") as f:
                for J in Js:
                    f.write(f"\t\t\t  {header}\n\t\t(a) Number Of Cycles (J) = {fmt % J}\n"
                            f"\t\t(b) Sequence Length (n)  = {N_BITS}\n")
                    if J < 500:
                        f.write("\t\tWARNING:  TEST NOT APPLICABLE.  THERE ARE AN\n")
                    f.write("\n")


def uniform_pvals(n_streams, seed=0, re_applicable=None):
    rng = np.random.default_rng(seed)
    out = {}
    for t in so.TESTS:
        k = so.P_VALUES_PER_SEQUENCE[t]
        rows = [list(np.round(rng.uniform(0.0001, 0.9999, k), 6)) for _ in range(n_streams)]
        if t in ("RandomExcursions", "RandomExcursionsVariant") and re_applicable is not None:
            rows = [r if re_applicable[i] else [0.0] * k for i, r in enumerate(rows)]
        out[t] = rows
    return out


def test_menu_answers():
    assert so.menu_answers("/x/in.bin", 100, True) == "0\n/x/in.bin\n1\n0\n100\n1\n"
    assert so.menu_answers("/x/e.txt", 1, False, tests=["FFT"]) == "0\n/x/e.txt\n0\n000000100000000\n1\n0\n"
    # a parameterised test adds the "0 = keep defaults" answer
    assert so.menu_answers("/x/e", 1, False, tests=["Serial"]) == "0\n/x/e\n0\n000000000000010\n0\n1\n0\n"
    assert so.menu_answers(None, 1, False, tests=["Universal"], generator=9) == "9\n0\n000000000100000\n1\n"


def test_series_labels_match_counts():
    for t in so.TESTS:
        assert len(so.series_labels(t)) == so.P_VALUES_PER_SEQUENCE[t]
    assert so.series_labels("RandomExcursions")[4] == "x=+1"
    assert so.series_labels("RandomExcursionsVariant")[8] == "x=-1"


def test_wsl_path():
    assert so.to_wsl_path(r"C:\Users\a b\x.bin") == "/mnt/c/Users/a b/x.bin"


def test_sts_metrics_basic_and_thresholds():
    ps = ["0.500000"] * 96 + ["0.005000"] * 4
    m = so.sts_metrics(ps)
    assert m["sample_size"] == 100 and m["passed"] == 96 and m["failed"] == 4
    assert (m["proportion_min"], m["proportion_max"]) == (96, 101)  # int((0.99 -/+ 3 sqrt(.0099/100)) * 100)
    assert not m["proportion_flag"]
    m = so.sts_metrics(["0.500000"] * 95 + ["0.005000"] * 5)
    assert m["proportion_flag"] and m["flagged"]
    assert m["bins"][5] == 95 and m["bins"][0] == 5
    assert m["uniformity_flag"]  # everything in two bins


def test_sts_metrics_reproduces_float32_reading():
    # assess reads p-values with fscanf("%f"): 0.010000 becomes 0.0099999998 < ALPHA (counted as a failure)
    assert so.sts_metrics(["0.010000"])["failed"] == 1
    # and 0.700000 becomes 0.69999999 -> histogram bin 6, not 7
    assert so.sts_metrics(["0.700000"])["bins"][6] == 1
    # 1.000000 goes into the last bin
    assert so.sts_metrics(["1.000000"])["bins"][9] == 1


def test_sts_metrics_small_and_empty_samples():
    m = so.sts_metrics(["0.3"] * 9)
    assert m["uniformity_p"] is None and not m["uniformity_flag"]  # expCount = 9/10 = 0
    e = so.sts_metrics([])
    assert e["sample_size"] == 0 and e["passed"] == 0 and not e["flagged"]


def test_parse_counts_and_missing_lines(tmp_path):
    p = uniform_pvals(5)
    write_fixture(tmp_path, 5, p, re_J=[800] * 5, rev_J=[800] * 5, drop_lines={"RandomExcursions": 8})
    mat, probs = so.parse_test(str(tmp_path), "Frequency", 5)
    assert len(mat) == 5 and not probs
    mat, probs = so.parse_test(str(tmp_path), "RandomExcursions", 5)
    assert mat is None and "32 p-values" in probs[0]
    ev = so.evaluate_workdir(str(tmp_path), 5, n_bits=N_BITS)
    err = [s for s in ev["series"] if s["status"] == "ERROR"]
    assert [s["test"] for s in err] == ["RandomExcursions"]  # reported as an execution error, not a failure


def test_random_excursion_applicability_and_report_rule(tmp_path):
    n = 12
    applicable = [True] * 10 + [False] * 2
    p = uniform_pvals(n, seed=1, re_applicable=applicable)
    # an applicable sequence whose genuine p-value prints as 0.000000
    p["RandomExcursions"][0][4] = 0.0
    J = [900] * 10 + [300, 120]
    write_fixture(tmp_path, n, p, re_J=J, rev_J=J)
    ev = so.evaluate_workdir(str(tmp_path), n, n_bits=N_BITS)
    assert not ev["problems"]
    s = next(s for s in ev["series"] if s["test"] == "RandomExcursions" and s["series"] == "x=+1")
    assert s["excluded_not_applicable"] == 2
    assert s["metrics"]["sample_size"] == 10 and s["metrics"]["failed"] >= 1      # counted as a failure here
    assert s["metrics_sts_report_rule"]["sample_size"] == 9                         # dropped by the official rule
    assert s["applicable_but_printed_zero"] == 1
    recs = [r for r in ev["records"] if r["test"] == "RandomExcursions" and r["sequence"] == 11]
    assert {r["outcome"] for r in recs} == {"not_applicable"} and recs[0]["J"] == 120
    rec = next(r for r in ev["records"] if r["test"] == "RandomExcursions" and r["sequence"] == 0
               and r["series"] == "x=+1")
    assert rec["outcome"] == "fail"


def test_applicability_inconsistency_is_reported(tmp_path):
    p = uniform_pvals(2, seed=2)
    write_fixture(tmp_path, 2, p, re_J=[900, 900], rev_J=[900, 900])
    d = os.path.join(tmp_path, "experiments", "AlgorithmTesting", "RandomExcursions", "stats.txt")
    text = open(d).read().replace("(J) = 0900", "(J) = 0400", 1)  # J < 500 but no NOT APPLICABLE marker
    open(d, "w").write(text)
    ev = so.evaluate_workdir(str(tmp_path), 2, n_bits=N_BITS)
    assert any("inconsistent" in pr for pr in ev["problems"])


def test_cycle_count_matches_definition():
    bits = np.array([1, 0, 1, 1, 0, 0, 0, 1, 1, 1], dtype=np.uint8)  # walk 1,0,1,2,1,0,-1,0,1,2
    assert so.cycle_count(bits) == 3 + 1
    assert so.cycle_count(np.array([1, 0], dtype=np.uint8)) == 1


def far_text(rows):
    out = ["------------------------------------------------------------------------------",
           " C1  C2  C3  C4  C5  C6  C7  C8  C9 C10  P-VALUE  PROPORTION  STATISTICAL TEST",
           "------------------------------------------------------------------------------"]
    for r in rows:
        line = "".join(f"{b:3d} " for b in r["bins"])
        if r["uniformity_p"] is None:
            line += "    ----    "
        elif r["uniformity_flag"]:
            line += f" {r['uniformity_p']:8.6f} * "
        else:
            line += f" {r['uniformity_p']:8.6f}   "
        if r["sample_size"] == 0:
            line += f" ------     {r['test']}"
        elif r["proportion_flag"]:
            line += f"{r['passed']:4d}/{r['sample_size']:<4d} *  {r['test']}"
        else:
            line += f"{r['passed']:4d}/{r['sample_size']:<4d}    {r['test']}"
        out.append(line)
    out += ["", "- - - - -", "The minimum pass rate ... = 96 for a", "sample size = 100 binary sequences."]
    return "\n".join(out) + "\n"


def test_parse_final_analysis_report_and_verify(tmp_path):
    n = 100
    p = uniform_pvals(n, seed=3)
    p["Runs"] = [[0.001] for _ in range(n)]  # every sequence fails -> both flags
    write_fixture(tmp_path, n, p, re_J=[900] * n, rev_J=[900] * n)
    ev = so.evaluate_workdir(str(tmp_path), n, n_bits=N_BITS)
    rows = []
    for s in ev["series"]:
        m = s.get("metrics_sts_report_rule", s["metrics"])
        rows.append({"test": s["test"], "bins": m["bins"], "uniformity_p": m["uniformity_p"],
                     "uniformity_flag": m["uniformity_flag"], "passed": m["passed"],
                     "sample_size": m["sample_size"], "proportion_flag": m["proportion_flag"]})
    path = tmp_path / "finalAnalysisReport.txt"
    path.write_text(far_text(rows))
    parsed = so.parse_final_analysis_report(str(path))
    assert len(parsed) == 188
    runs = next(r for r in parsed if r["test"] == "Runs")
    assert runs["passed"] == 0 and runs["proportion_flag"] and runs["uniformity_flag"]
    assert so.verify_against_report(ev, parsed) == []
    parsed[0]["passed"] -= 1
    assert so.verify_against_report(ev, parsed)


def test_parse_report_handles_empty_sample(tmp_path):
    path = tmp_path / "far.txt"
    path.write_text(far_text([{"test": "RandomExcursions", "bins": [0] * 10, "uniformity_p": None,
                               "uniformity_flag": False, "passed": 0, "sample_size": 0, "proportion_flag": False}]))
    r = so.parse_final_analysis_report(str(path))[0]
    assert r["sample_size"] is None and r["uniformity_p"] is None and not r["proportion_flag"]


def test_verify_treats_empty_report_row_as_zero_sample(tmp_path):
    n = 3
    p = uniform_pvals(n, seed=4, re_applicable=[False] * n)
    write_fixture(tmp_path, n, p, re_J=[100] * n, rev_J=[100] * n)
    ev = so.evaluate_workdir(str(tmp_path), n, n_bits=N_BITS)
    rows = []
    for s in ev["series"]:
        m = s.get("metrics_sts_report_rule", s["metrics"])
        rows.append({"test": s["test"], "bins": m["bins"], "uniformity_p": m["uniformity_p"],
                     "uniformity_flag": m["uniformity_flag"], "passed": m["passed"],
                     "sample_size": m["sample_size"], "proportion_flag": m["proportion_flag"]})
    path = tmp_path / "far.txt"
    path.write_text(far_text(rows))
    parsed = so.parse_final_analysis_report(str(path))
    assert sum(r["sample_size"] is None for r in parsed) == 26  # 8 + 18 empty random-excursion rows
    assert so.verify_against_report(ev, parsed) == []


# ---------------------------------------------------------------- real official run, if present

RUN = os.path.join(ROOT, "results", "nist_sts_official", "sts212_default_20261025")


@pytest.mark.skipif(not os.path.exists(os.path.join(RUN, "analysis", "summary.json")), reason="official run not analysed")
def test_real_run_parses_and_matches_official_reports():
    summary = json.load(open(os.path.join(RUN, "analysis", "summary.json")))
    for m, info in summary["methods"].items():
        assert info["streams_read"] == info["n_streams"] == 100, m
        assert info["problems"] == [], m
        assert info["report_mismatches"] == [], m
    ab = summary["appendix_b"]
    assert ab["total"] == 80
    assert ab["official_max_abs_diff"] <= 1.0000001e-6  # two data.e cusum values differ in the 6th decimal


@pytest.mark.skipif(not os.path.exists(os.path.join(RUN, "analysis", "test_summary.csv")), reason="official run not analysed")
def test_real_run_test_summary_consistent_with_series():
    import csv
    series = list(csv.DictReader(open(os.path.join(RUN, "analysis", "series_summary.csv"))))
    tests = list(csv.DictReader(open(os.path.join(RUN, "analysis", "test_summary.csv"))))
    assert len(tests) == 5 * 15
    for t in tests:
        ss = [s for s in series if s["method"] == t["method"] and s["test"] == t["test"]]
        assert len(ss) == int(t["series"]) == so.P_VALUES_PER_SEQUENCE[t["test"]]
        if t["status"] == "EXECUTED":
            assert int(t["flagged_series"]) == sum(s["flagged"] == "True" for s in ss)
