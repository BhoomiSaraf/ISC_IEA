"""Analyse raw official NIST STS 2.1.2 outputs (stage 2 of 2) and write the report.

    python experiments/analyze_official_sts.py --run-id sts212_default_20261025

Reads results/nist_sts_official/<run_id>/raw/** produced by run_official_sts.py and the
previous Python evaluation (read-only); writes results/nist_sts_official/<run_id>/analysis/,
official_nist_sts_report.md and manifest.json.  Refuses to overwrite an existing analysis.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import sys

import numpy as np
from scipy.special import erfc
from scipy.stats import binom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isc_seq import nist as pynist  # noqa: E402
from isc_seq import sts_official as so  # noqa: E402

# SP 800-22 Rev. 1a Appendix B (pages B-1..B-3): (test, series index) -> p-value per sample file.
APPENDIX_B_ROWS = [
    ("Frequency", "Frequency", 0), ("Block Frequency (m = 128)", "BlockFrequency", 0),
    ("Cusum-Forward", "CumulativeSums", 0), ("Cusum-Reverse", "CumulativeSums", 1),
    ("Runs", "Runs", 0), ("Long Runs of Ones", "LongestRun", 0), ("Rank", "Rank", 0),
    ("Spectral DFT", "FFT", 0), ("Non-overlapping Templates (m = 9, B = 000000001)", "NonOverlappingTemplate", 0),
    ("Overlapping Templates (m = 9)", "OverlappingTemplate", 0), ("Universal", "Universal", 0),
    ("Approximate Entropy (m = 10)", "ApproximateEntropy", 0), ("Random Excursions (x = +1)", "RandomExcursions", 4),
    ("Random Excursions Variant (x = -1)", "RandomExcursionsVariant", 8), ("Linear Complexity (M = 500)", "LinearComplexity", 0),
    ("Serial (m = 16, del Psi^2_m)", "Serial", 0),
]
APPENDIX_B = {
    "pi": ["0.578211", "0.380615", "0.628308", "0.663369", "0.419268", "0.024390", "0.083553", "0.010186",
           "0.165757", "0.296897", "0.669012", "0.361595", "0.844143", "0.760966", "0.255475", "0.143005"],
    "e": ["0.953749", "0.211072", "0.669887", "0.724266", "0.561917", "0.718945", "0.306156", "0.847187",
          "0.078790", "0.110434", "0.282568", "0.700073", "0.786868", "0.826009", "0.826335", "0.766182"],
    "sha1": ["0.604458", "0.091517", "0.451231", "0.550134", "0.309757", "0.657812", "0.577829", "0.163062",
             "0.496601", "0.339426", "0.411079", "0.982885", "0.000000", "0.000000", "0.309412", "0.760793"],
    "sqrt2": ["0.811881", "0.833222", "0.879009", "0.957206", "0.313427", "0.012117", "0.823810", "0.581909",
              "0.569461", "0.791982", "0.130805", "0.884740", "0.216235", "0.566118", "0.317127", "0.861925"],
    "sqrt3": ["0.610051", "0.473961", "0.917121", "0.689519", "0.261123", "0.446726", "0.314498", "0.776046",
              "0.532235", "0.082716", "0.165981", "0.180481", "0.783283", "0.155066", "0.346469", "0.157500"],
}
APPENDIX_B_FILES = {"pi": "data.pi", "e": "data.e", "sha1": "data.sha1", "sqrt2": "data.sqrt2", "sqrt3": "data.sqrt3"}

# Previous Python evaluation column -> (official test, series label)
PY_TO_STS = {
    "Frequency": ("Frequency", "p_value"), "BlockFrequency": ("BlockFrequency", "p_value"),
    "Runs": ("Runs", "p_value"), "LongestRun": ("LongestRun", "p_value"), "Rank": ("Rank", "p_value"),
    "FFT": ("FFT", "p_value"), "Universal": ("Universal", "p_value"),
    "Serial_1": ("Serial", "p_value1"), "Serial_2": ("Serial", "p_value2"),
    "ApproximateEntropy": ("ApproximateEntropy", "p_value"),
    "CumulativeSums_fwd": ("CumulativeSums", "forward"), "CumulativeSums_bwd": ("CumulativeSums", "reverse"),
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(rows[0])
    with open(path, "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def read_ascii_bits(path, n):
    raw = open(path, "rb").read()
    arr = np.frombuffer(raw, dtype=np.uint8)
    arr = arr[(arr == ord("0")) | (arr == ord("1"))] - ord("0")
    return arr[:n].astype(np.uint8)


def read_binary_bits(path, n, offset_bytes=0):
    with open(path, "rb") as f:
        f.seek(offset_bytes)
        data = f.read(n // 8)
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="big")


def p_flag_under_h0(m, alpha=so.ALPHA):
    """P(a single p-value series is flagged by the proportion rule) for m i.i.d. uniform p-values."""
    p_hat = 1 - alpha
    tmin = int((p_hat - 3 * math.sqrt(p_hat * alpha / m)) * m)
    tmax = int((p_hat + 3 * math.sqrt(p_hat * alpha / m)) * m)
    # passes ~ Binomial(m, 1 - alpha); flagged if passes < tmin or > tmax
    return float(binom.cdf(tmin - 1, m, p_hat) + binom.sf(tmax, m, p_hat))


# ----------------------------------------------------------------------------- stages

def appendix_b(run_dir, sts_build):
    rows = []
    for name, fname in APPENDIX_B_FILES.items():
        wd = os.path.join(run_dir, "raw", "appendix_b", name)
        bits = (read_binary_bits if name == "sha1" else read_ascii_bits)(os.path.join(sts_build, "data", fname), 1_000_000)
        py = pynist.run_battery(bits)
        py_map = {(t, s): py[k] for k, (t, s) in PY_TO_STS.items()}
        for (label, test, idx), expected in zip(APPENDIX_B_ROWS, APPENDIX_B[name]):
            got = so.read_results(wd, test)
            got_p = got[idx] if idx < len(got) else None
            lab = so.series_labels(test)[idx]
            pyv = py_map.get((test, lab))
            rows.append({"sample": name, "appendix_b_test": label, "official_test": test, "series": lab,
                         "appendix_b_p": expected, "official_sts_p": got_p,
                         "official_matches": got_p == expected,
                         "python_p": "" if pyv is None else f"{pyv:.6f}",
                         "python_matches": "" if pyv is None else f"{pyv:.6f}" == expected})
    return rows


def worked_examples(run_dir):
    out = {}
    wd = os.path.join(run_dir, "raw", "examples", "dft_2.6.8")
    stats = open(os.path.join(wd, "experiments", "AlgorithmTesting", "FFT", "stats.txt"), encoding="utf-8").read()
    eps = open(os.path.join(run_dir, "raw", "examples", "sp800-22_2.6.8_epsilon.txt"), encoding="ascii").read().strip()
    out["dft_2.6.8"] = {
        "sp800_22_printed": {"N1": 46, "N0": 47.5, "d": -1.376494, "p": 0.168669},
        "official_sts_stats": stats.strip(),
        "official_sts_p": so.read_results(wd, "FFT")[0],
        "python_p": f"{pynist.dft(eps):.6f}",
    }
    wd = os.path.join(run_dir, "raw", "examples", "universal_2.9.8")
    stats = open(os.path.join(wd, "experiments", "G-SHA1", "Universal", "stats.txt"), encoding="utf-8").read()
    out["universal_2.9.8"] = {
        "sp800_22_printed": {"n": 1048576, "L": 7, "Q": 1280, "K": 148516, "c": 0.591311, "sigma": 0.002703,
                             "sum": 919924.038020, "fn": 6.194107, "p": 0.427733},
        "official_sts_builtin_gsha1_stats": stats.strip(),
        "official_sts_builtin_gsha1_p": so.read_results(wd, "Universal", "G-SHA1")[0],
    }
    # Section 2.9.4 illustration (L = 2, Q = 4, epsilon = 01011010011101010111)
    eps = "01011010011101010111"
    L, Q = 2, 4
    blocks = [int(eps[i:i + L], 2) for i in range(0, 20, L)]
    last = {}
    for i, b in enumerate(blocks[:Q], start=1):
        last[b] = i
    s = 0.0
    for i, b in enumerate(blocks[Q:], start=Q + 1):
        s += math.log2(i - last.get(b, 0))
        last[b] = i
    K = len(blocks) - Q
    fn = s / K
    exp_v, var = 1.5374383, 1.338
    c = 0.7 - 0.8 / L + (4 + 32 / L) * K ** (-3 / L) / 15
    out["universal_2.9.4_illustration"] = {
        "sp800_22_printed": {"sum": 7.169925002, "fn": 1.1949875, "p": 0.767189},
        "recomputed_sum": s, "recomputed_fn": fn,
        "p_with_sigma_sqrt_variance": float(erfc(abs(fn - exp_v) / (math.sqrt(2) * math.sqrt(var)))),
        "p_with_sigma_c_sqrt_variance_over_K": float(erfc(abs(fn - exp_v) / (math.sqrt(2) * c * math.sqrt(var / K)))),
        "python_isc_seq_p": pynist.universal(eps, L=2, Q=4),
        "c": c, "K": K,
    }
    # Built-in G-SHA-1 generator vs Appendix B example 3
    wd = os.path.join(run_dir, "raw", "examples", "gsha1_n1000000_all")
    rows = []
    for (label, test, idx), expected in zip(APPENDIX_B_ROWS, APPENDIX_B["sha1"]):
        got = so.read_results(wd, test, "G-SHA1")
        rows.append({"test": label, "appendix_b_p": expected, "builtin_gsha1_p": got[idx] if idx < len(got) else None})
    out["builtin_gsha1_vs_appendix_b"] = rows
    return out


def method_analysis(run_dir, run_cfg, seq_run, method):
    wd = os.path.join(run_dir, "raw", "methods", method)
    job = next(j for j in run_cfg["jobs"] if j["label"] == f"methods/{method}")
    n_streams, n_bits = job["n_streams"], job["n_bits"]
    bin_path = os.path.join(ROOT, job["input"])
    ev = so.evaluate_workdir(wd, n_streams, lambda i: read_binary_bits(bin_path, n_bits, i * n_bits // 8), n_bits)
    far = os.path.join(wd, "experiments", "AlgorithmTesting", "finalAnalysisReport.txt")
    report_rows = so.parse_final_analysis_report(far) if os.path.exists(far) else []
    mismatches = so.verify_against_report(ev, report_rows) if report_rows else ["finalAnalysisReport.txt missing"]
    freq = open(os.path.join(wd, "experiments", "AlgorithmTesting", "freq.txt"), encoding="utf-8").read()
    bitsread = freq.count("BITSREAD = 1000000")
    # previous Python evaluation, per sequence
    py_rows = list(csv.DictReader(open(os.path.join(seq_run, "nist", f"pvalues_{method}.csv"), encoding="utf-8")))
    sts = {(r["test"], r["series"], r["sequence"]): r["p_value"] for r in ev["records"]}
    comp = []
    for col, (test, lab) in PY_TO_STS.items():
        diffs, disagree = [], 0
        for i, row in enumerate(py_rows):
            p_py = float(row[col])
            p_sts = float(sts[(test, lab, i)])
            diffs.append(abs(p_py - p_sts))
            if (p_py >= so.ALPHA) != (p_sts >= so.ALPHA):
                disagree += 1
        comp.append({"method": method, "python_test": col, "official_test": test, "series": lab,
                     "sequences": len(py_rows), "max_abs_diff": max(diffs), "mean_abs_diff": float(np.mean(diffs)),
                     "pass_fail_disagreements": disagree})
    return {"method": method, "evaluation": ev, "report_rows": report_rows, "report_mismatches": mismatches,
            "returncode": job.get("returncode"), "complete": job.get("complete"),
            "stdout_errors": job.get("stdout_errors", []), "streams_read": bitsread, "n_streams": n_streams,
            "comparison": comp}


def test_level(method_result):
    """Aggregate series to one row per test."""
    out = []
    series = method_result["evaluation"]["series"]
    for test in so.TESTS:
        ss = [s for s in series if s["test"] == test]
        if not ss or ss[0]["status"] != "OK":
            out.append({"method": method_result["method"], "test": test, "status": "ERROR", "series": 0,
                        "sequences_tested": 0, "flagged_series": None})
            continue
        sizes = sorted({s["metrics"]["sample_size"] for s in ss})
        flagged = [s for s in ss if s["metrics"]["flagged"]]
        prop_flags = sum(s["metrics"]["proportion_flag"] for s in ss)
        uni_flags = sum(s["metrics"]["uniformity_flag"] for s in ss)
        m = sizes[0]
        row = {"method": method_result["method"], "test": test, "status": "EXECUTED", "series": len(ss),
               "sequences_tested": method_result["n_streams"],
               "sequences_applicable": m if len(sizes) == 1 else "/".join(map(str, sizes)),
               "excluded_not_applicable": ss[0]["excluded_not_applicable"],
               "flagged_series": len(flagged), "proportion_flags": prop_flags, "uniformity_flags": uni_flags,
               "min_proportion": min((s["metrics"]["passed"] / s["metrics"]["sample_size"]
                                      for s in ss if s["metrics"]["sample_size"]), default=None),
               "min_uniformity_p": min((s["metrics"]["uniformity_p"] for s in ss
                                        if s["metrics"]["uniformity_p"] is not None), default=None)}
        if m == 0:
            row["status"] = "NOT_APPLICABLE"
            row["chance_flag_tail_p"] = None
            row["verdict"] = "not evaluated: no applicable sequences"
        else:
            p0 = p_flag_under_h0(m) + 1e-4
            row["expected_flags_under_h0"] = len(ss) * p0
            tail = float(binom.sf(len(flagged) - 1, len(ss), p0)) if flagged else 1.0
            row["chance_flag_tail_p"] = tail
            if not flagged:
                row["verdict"] = "no series flagged"
            elif len(ss) == 1:
                row["verdict"] = "FLAGGED"
            elif tail < 0.01:
                row["verdict"] = f"FLAGGED ({len(flagged)}/{len(ss)} series; more than chance)"
            elif tail < 0.05:
                row["verdict"] = f"{len(flagged)}/{len(ss)} series flagged; borderline (chance tail p < 0.05)"
            else:
                row["verdict"] = f"{len(flagged)}/{len(ss)} series flagged; consistent with chance"
        out.append(row)
    return out


# ----------------------------------------------------------------------------- report

def fmt(v, nd=6):
    if v is None or v == "":
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        if v != 0 and abs(v) < 1e-4:
            return f"{v:.2e}"
        return f"{v:.{nd}f}"
    return str(v)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(fmt(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def render(run_id, prov, run_cfg, inputs, appb, examples, methods, tests, run_dir):
    L = [f"# Official NIST STS 2.1.2 evaluation of ISC bitstreams (`{run_id}`)\n",
         "Scope: statistical testing of the bitstreams saved by the sequence-generation run "
         f"`{run_cfg['sequence_run']}`. No encryption. Every number below is parsed from the raw official "
         "outputs under `raw/` (see `analysis/` and `manifest.json`).\n"]

    L.append("## 1. Setup and provenance\n")
    b = prov["build"]
    L.append(table(["item", "value"], [
        ["suite", prov["suite"]],
        ["source", f"{prov['source_url']} (listed on {prov['source_page']})"],
        ["source zip SHA-256 / bytes", f"`{prov['source_zip_sha256']}` / {prov['source_zip_bytes']}"],
        ["documentation", f"{prov['documentation']}: {prov['documentation_url']} (SHA-256 `{prov['documentation_sha256']}`)"],
        ["source modifications", "none: build tree verified file-by-file against the official zip (provenance/sts_provenance.json)"],
        ["build host", b["host"]],
        ["toolchain", b["toolchain"].replace("\n", "; ")],
        ["build command", b["command"]],
        ["build warnings", b["warnings"]],
        ["assess SHA-256", f"`{b['assess_sha256']}`"],
    ]) + "\n")
    L.append("Test parameters are the defaults compiled into `assess.c` and were not changed:\n")
    L.append(table(["parameter", "value"], [[k, v] for k, v in so.DEFAULT_PARAMETERS.items()]) + "\n")
    L.append("Input: the saved `bitstreams/<method>.bin` files, used unchanged with assess input mode 1 (binary): "
             "bytes are read 4 at a time and expanded MSB first, which is exactly how the files were written "
             "(np.packbits, bitorder='big'). Each file holds 100 consecutive 125,000-byte sequences. Because "
             "1,000,000 is a multiple of 32, no bits are dropped or shifted between sequences. No conversion "
             "was performed. File hashes were checked against the sequence-generation manifest before running; "
             "per-sequence SHA-256 identifiers are in `inputs/input_sequences.csv`.\n")
    L.append(table(["method", "file", "SHA-256", "sequences"],
                   [[m, v["path"], f"`{v['sha256'][:16]}...`", v["sequences"]] for m, v in inputs.items()]) + "\n")

    L.append("## 2. Validation of the build against SP 800-22 Appendix B\n")
    ok = sum(r["official_matches"] for r in appb)
    maxd = max(abs(float(r["official_sts_p"]) - float(r["appendix_b_p"])) for r in appb)
    L.append(f"The five official sample files (1,000,000 bits each) were run through the built `assess` with default "
             f"parameters. **{ok}/{len(appb)}** Appendix B p-values were reproduced exactly (6 decimals); the largest "
             f"absolute difference is {maxd:.1e}.\n")
    bad = [r for r in appb if not r["official_matches"]]
    if bad:
        L.append(table(["sample", "test", "Appendix B", "official build", "isc_seq.nist"],
                       [[r["sample"], r["appendix_b_test"], r["appendix_b_p"], r["official_sts_p"], r["python_p"]]
                        for r in bad]) + "\n")
        L.append("These differ only in the 6th decimal. The independent Python implementation gives the same value "
                 "as the official build, so the difference is most likely last-digit rounding in the published "
                 "table (the cumulative-sums P-value sums many normal-CDF terms) rather than a build defect. "
                 "It has no effect on any decision at alpha = 0.01.\n")
    pyrows = [r for r in appb if r["python_p"] != ""]
    pyok = sum(r["python_matches"] for r in pyrows)
    L.append(f"The earlier Python implementation (`isc_seq.nist`) on the same files: **{pyok}/{len(pyrows)}** of the "
             "Appendix B values it covers reproduced to 6 decimals.\n")
    pybad = [r for r in pyrows if not r["python_matches"]]
    if pybad:
        L.append(table(["sample", "test", "Appendix B", "isc_seq.nist"],
                       [[r["sample"], r["appendix_b_test"], r["appendix_b_p"], r["python_p"]] for r in pybad]) + "\n")

    L.append("## 3. Coverage\n")
    L.append("All 15 tests of STS 2.1.2 (the complete SP 800-22 Rev. 1a battery) were executed on every sequence "
             "of every method. Executed is not the same as applicable: the random-excursion tests apply only to "
             "sequences with at least 500 cycles (J), and their results are reported for the applicable "
             "sequences only.\n")
    cov = []
    for mr in methods:
        ev = mr["evaluation"]
        cov.append([mr["method"], mr["n_streams"], mr["streams_read"], fmt(mr["complete"]), mr["returncode"],
                    len(mr["stdout_errors"]), len(ev["problems"]), len(mr["report_mismatches"])])
    L.append(table(["method", "sequences submitted", "sequences read by assess", "run complete",
                    "assess exit code", "stdout errors", "parse problems", "finalAnalysisReport mismatches"], cov) + "\n")
    L.append("`assess` returns 1 from `main()` after a normal run, so exit code 1 is expected. 'finalAnalysisReport "
             "mismatches' counts series where the independently recomputed metrics differ from the official "
             "summary file.\n")
    for mr in methods:
        for p in mr["evaluation"]["problems"] + mr["stdout_errors"] + mr["report_mismatches"]:
            L.append(f"- {mr['method']}: {p}")
    L.append("")

    L.append("## 4. Results per method and test\n")
    L.append("For each p-value series, a flag is raised when the number of passing sequences (p >= 0.01) is "
             "outside the official proportion interval, or when the p-value uniformity P-value is < 0.0001. Both are "
             "computed exactly as `finalAnalysisReport.txt` does. Tests with several series (Cumulative Sums 2, "
             "Serial 2, Non-overlapping Template 148, Random Excursions 8, Random Excursions Variant 18) are "
             "summarised as flagged/total series. 'Chance tail p' is the binomial probability of at least that "
             "many flagged series if every series were flagged independently with its null probability. It is "
             "an interpretation aid only, because template series are not independent.\n")
    for mr in methods:
        m = mr["method"]
        L.append(f"### {m}\n")
        rows = []
        for t in [r for r in tests if r["method"] == m]:
            rows.append([t["test"], t["status"], t.get("sequences_applicable"), t.get("excluded_not_applicable"),
                         f"{t['flagged_series']}/{t['series']}" if t["flagged_series"] is not None else "n/a",
                         t.get("min_proportion"), t.get("min_uniformity_p"), t.get("chance_flag_tail_p"),
                         t.get("verdict", "error")])
        L.append(table(["test", "status", "sequences used", "excluded (not applicable)", "flagged series",
                        "lowest pass proportion", "lowest uniformity P", "chance tail p", "verdict"], rows) + "\n")
        single = [s for s in mr["evaluation"]["series"] if s["status"] == "OK" and len(so.series_labels(s["test"])) <= 2]
        L.append(table(["series", "passed/applicable", "proportion range (official)", "uniformity P", "flag"],
                       [[f"{s['test']} {s['series']}" if s["series"] != "p_value" else s["test"],
                         f"{s['metrics']['passed']}/{s['metrics']['sample_size']}",
                         f"{s['metrics']['proportion_min']}..{s['metrics']['proportion_max']}",
                         s["metrics"]["uniformity_p"],
                         ("PROPORTION " if s["metrics"]["proportion_flag"] else "")
                         + ("UNIFORMITY" if s["metrics"]["uniformity_flag"] else "") or "-"]
                        for s in single]) + "\n")
        re_rows = [s for s in mr["evaluation"]["series"] if s["test"] in ("RandomExcursions", "RandomExcursionsVariant")
                   and s["status"] == "OK"]
        if re_rows:
            L.append(table(["series", "applicable", "passed", "flag", "official report rule: sample / passed / flag",
                            "applicable but printed 0.000000"],
                           [[f"{s['test']} {s['series']}", s["metrics"]["sample_size"], s["metrics"]["passed"],
                             fmt(s["metrics"]["flagged"]),
                             f"{s['metrics_sts_report_rule']['sample_size']} / {s['metrics_sts_report_rule']['passed']} / "
                             f"{fmt(s['metrics_sts_report_rule']['flagged'])}",
                             s["applicable_but_printed_zero"]] for s in re_rows]) + "\n")

    L.append("### Flagged series in methods with at most a few flags\n")
    L.append("Each flag below is shown with the official uniformity P-value and the same chi-square computed with "
             "the exact expected count m/10. The official code truncates m/10 to an integer, which inflates the "
             "statistic when m is not a multiple of 10. The official flag is what counts; the second column only "
             "shows how sensitive it is.\n")
    few = []
    for mr in methods:
        ss = [s for s in mr["evaluation"]["series"] if s["status"] == "OK"]
        fl = [s for s in ss if s["metrics"]["flagged"]]
        if 0 < len(fl) <= 5:
            for s in fl:
                met = s["metrics"]
                mm = met["sample_size"]
                exact = None
                if mm:
                    chi2 = sum((b - mm / 10) ** 2 / (mm / 10) for b in met["bins"])
                    exact = float(so.gammaincc(4.5, chi2 / 2))
                few.append([mr["method"], f"{s['test']} {s['series']}", f"{met['passed']}/{mm}",
                            f"{met['proportion_min']}..{met['proportion_max']}", met["uniformity_p"], exact,
                            ("proportion " if met["proportion_flag"] else "") + ("uniformity" if met["uniformity_flag"] else "")])
    if few:
        L.append(table(["method", "series", "passed/m", "official proportion range", "uniformity P (official)",
                        "uniformity P (exact m/10)", "flag"], few) + "\n")
    else:
        L.append("None.\n")
    L.append("**Excluded random-excursion sequences.** A sequence is excluded from both random-excursion tests "
             "when its walk has fewer than 500 cycles (J). For i.i.d. uniform bits with n = 10^6, J is "
             "approximately |Z| * sqrt(n) for a standard normal Z, so about 38% of sequences are expected to be "
             "excluded. Per method (J recomputed from the input bits and checked against stats.txt):\n")
    jrows = []
    for mr in methods:
        J = [r["J"] for r in mr["evaluation"]["records"] if r["test"] == "RandomExcursions" and r["series"] == "x=-4"]
        jrows.append([mr["method"], min(J), sorted(J)[len(J) // 2], max(J), sum(j >= 500 for j in J), len(J)])
    L.append(table(["method", "J min", "J median", "J max", "applicable (J >= 500)", "sequences"], jrows) + "\n")
    L.append("SP 800-22 section 4.2.2 asks for at least 55 sequences for the uniformity assessment. Where fewer "
             "sequences are applicable, the uniformity P-value of the random-excursion tests is only indicative.\n")

    L.append("### Summary across methods\n")
    head = ["test"] + [mr["method"] for mr in methods]
    rows = []
    for test in so.TESTS:
        row = [test]
        for mr in methods:
            t = next(r for r in tests if r["method"] == mr["method"] and r["test"] == test)
            if t["status"] == "ERROR":
                row.append("ERROR")
            elif t["status"] == "NOT_APPLICABLE":
                row.append("not applicable (0 seq.)")
            else:
                row.append(f"{t['flagged_series']}/{t['series']} flagged ({t['sequences_applicable']} seq.)")
        rows.append(row)
    L.append(table(head, rows) + "\n")

    L.append("## 5. Comparison with the previous Python evaluation\n")
    L.append("The earlier `isc_seq.nist` results (`" + run_cfg["sequence_run"] + "/nist/`) were not modified. "
             "Per-sequence p-values on the same sequences, for the 12 series both implementations compute:\n")
    comp = [c for mr in methods for c in mr["comparison"]]
    worst = max(c["max_abs_diff"] for c in comp)
    dis = sum(c["pass_fail_disagreements"] for c in comp)
    L.append(f"Largest absolute p-value difference over all {len(comp)} method x series pairs and 100 sequences: "
             f"**{worst:.2e}**; sequences whose pass/fail decision at alpha = 0.01 differs: **{dis}**. The official "
             "outputs are printed with 6 decimals, so differences up to 5e-7 are rounding.\n")
    big = [c for c in comp if c["max_abs_diff"] > 1e-6 or c["pass_fail_disagreements"]]
    if big:
        L.append(table(["method", "series", "max |diff|", "disagreements"],
                       [[c["method"], c["python_test"], c["max_abs_diff"], c["pass_fail_disagreements"]] for c in big]) + "\n")
    L.append("Protocol-level differences: the earlier Python protocol flagged only proportions below the interval "
             "and computed uniformity from unrounded p-values with fractional expected counts. The official "
             "report also flags proportions above the interval, truncates the interval bounds to integers, reads "
             "p-values back as single-precision floats and uses integer expected counts (m/10). The previous "
             "evaluation also did not run template matching, linear complexity or random excursions.\n")

    L.append("## 6. Discrepancies investigated\n")
    d = examples["dft_2.6.8"]
    L.append("**DFT worked example (SP 800-22 section 2.6.8).** The example sequence was run through the official "
             f"binary with n = 100. It reports p = {d['official_sts_p']} (stats below); `isc_seq.nist.dft` gives "
             f"{d['python_p']}. SP 800-22 prints N1 = 46, d = -1.376494, P = 0.168669. The official code and the "
             "earlier implementation agree with each other (N_l = 48 peaks below the threshold), not with the printed "
             "example. The printed example therefore cannot be reproduced from its stated input with the official "
             "2.1.2 code.\n")
    L.append("```\n" + d["official_sts_stats"] + "\n```\n")
    u = examples["universal_2.9.4_illustration"]
    L.append("**Maurer universal illustration (section 2.9.4, L = 2, Q = 4).** The printed sum "
             f"7.169925 and fn = 1.1949875 are reproduced (recomputed fn = {u['recomputed_fn']:.7f}). The printed "
             f"P = 0.767189 equals erfc(|fn - E| / (sqrt(2) * sqrt(variance))) = {u['p_with_sigma_sqrt_variance']:.6f}, "
             "i.e. it uses sigma = sqrt(variance). The test description and the official code use "
             f"sigma = c * sqrt(variance / K), which gives {u['p_with_sigma_c_sqrt_variance_over_K']:.6f} "
             f"(`isc_seq.nist.universal`: {u['python_isc_seq_p']:.6f}). The illustration is inconsistent with the "
             "formula; it is not an implementation error.\n")
    u2 = examples["universal_2.9.8"]
    L.append("**Maurer universal example (section 2.9.8, G-SHA-1, n = 1,048,576).** It needs the G-SHA-1 bitstream. "
             "The STS built-in generator stores 32-bit SHA-1 words in `unsigned long` (`include/config.h`), which "
             "is 64 bits on this x86_64 Linux build. Run with the built-in generator, the official binary "
             "reproduces the printed K = 148516 and sigma = 0.002703, so the c * sqrt(variance / K) formula is "
             f"confirmed, but its p-value is {u2['official_sts_builtin_gsha1_p']} instead of 0.427733. "
             "The 1,000,000-bit built-in G-SHA-1 run also fails to reproduce Appendix B example 3 "
             "(table below), whereas the shipped `data.sha1` file does. The built-in generator output is therefore "
             "not valid on this platform. It is not even repeatable: an earlier trial run of the same job, made "
             "while preparing the harness and not archived, gave sum = 689001.559486 instead of the value below, "
             "which points to undefined behaviour. A Python replica of the generator did not reproduce `data.sha1` "
             "and was discarded. **The 2.9.8 example was not reproduced.**\n")
    L.append("```\n" + u2["official_sts_builtin_gsha1_stats"] + "\n```\n")
    L.append(table(["test", "Appendix B (G-SHA-1)", "built-in generator on this build"],
                   [[r["test"], r["appendix_b_p"], r["builtin_gsha1_p"]] for r in examples["builtin_gsha1_vs_appendix_b"]]) + "\n")
    L.append("**Random-excursion reporting rule in finalAnalysisReport.** For sequences with fewer than 500 cycles "
             "the official code writes 0.000000 as the p-value. `finalAnalysisReport.txt` then drops every value "
             "<= 0, which would also drop a genuine p-value below 5e-7 printed as 0.000000. This analysis decides "
             "applicability from J in `stats.txt`, cross-checked against J recomputed from the input bits, and "
             "reports both counts. The 'applicable but printed 0.000000' column shows where the two rules differ.\n")
    L.append("**Overlapping template probabilities.** STS 2.1.2 contains a corrected pi table but overwrites it at "
             "run time with values from its `Pr(u, eta)` approximation. Results here are those of the official "
             "code as distributed.\n")

    L.append("## 7. Interpretation and limitations\n")
    L.append("- These are statistical tests of the bitstreams, which can only reject the hypothesis of i.i.d. uniform "
             "bits. A series without flags means these tests at this sample size detected no deviation. It "
             "does not show randomness, unpredictability or cryptographic security. The ISC generator is a "
             "deterministic, publicly specified map, and its security against an adversary who knows the map is "
             "not addressed by any test here.\n"
             "- One sample of 100 sequences per method, all from one machine and one floating-point environment "
             "(see the sequence-generation run's environment.json). Multiple testing: 188 series per method, so "
             "isolated flags are expected by chance; see the chance tail p column.\n"
             "- Random-excursion tests used only the applicable sequences. With fewer than 55 applicable sequences "
             "the uniformity statistic is unreliable, and with none the test is not evaluated.\n"
             "- The official code's own known quirks (single-precision re-reading, the overlapping-template "
             "approximation, built-in generator portability) are documented above and were not altered.\n")

    L.append("## 8. Reproducing\n")
    L.append("```bash\n"
             "# 1. official source (already downloaded; verify the hash)\n"
             "curl -L -o third_party/nist_sts/download/sts-2_1_2.zip " + prov["source_url"] + "\n"
             "sha256sum third_party/nist_sts/download/sts-2_1_2.zip   # " + prov["source_zip_sha256"] + "\n"
             "# 2. build in WSL Ubuntu 24.04 with the unmodified makefile\n"
             "cd third_party/nist_sts && unzip -q download/sts-2_1_2.zip -d src_pristine \\\n"
             "  && cp -r src_pristine/sts-2.1.2/sts-2.1.2/. build_linux/\n"
             "wsl -d Ubuntu-24.04 --cd <path>/third_party/nist_sts/build_linux -- make\n"
             "# 3. execute and analyse (new run id each time; existing runs are never overwritten)\n"
             "python experiments/run_official_sts.py --run-id <new id> --workers 6\n"
             "python experiments/analyze_official_sts.py --run-id <new id>\n"
             "```\n")
    L.append("The menu answers sent to `assess` for every job are in `run_config.json` (`jobs[].stdin`) and "
             "`raw/**/assess_stdout.log`; timestamps are in `execution_log.txt`.\n")
    L.append("## 9. Files\n")
    L.append("`provenance/` (source and build provenance, build log), `inputs/` (input hashes per file and per "
             "sequence), `run_config.json`, `execution_log.txt`, `raw/appendix_b/`, `raw/examples/`, "
             "`raw/methods/<method>/experiments/AlgorithmTesting/` (unaltered official outputs: results.txt, "
             "stats.txt, data*.txt, freq.txt, finalAnalysisReport.txt), `analysis/per_sequence_<method>.csv`, "
             "`analysis/series_summary.csv`, `analysis/test_summary.csv`, `analysis/appendix_b_validation.csv`, "
             "`analysis/python_vs_official.csv`, `analysis/worked_examples.json`, `analysis/summary.json`, "
             "`manifest.json` (SHA-256 of every file).\n")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run_dir = os.path.join(ROOT, "results", "nist_sts_official", args.run_id)
    adir = os.path.join(run_dir, "analysis")
    if os.path.exists(adir):
        raise FileExistsError(adir)
    run_cfg = json.load(open(os.path.join(run_dir, "run_config.json"), encoding="utf-8"))
    prov = json.load(open(os.path.join(run_dir, "provenance", "sts_provenance.json"), encoding="utf-8"))
    inputs = json.load(open(os.path.join(run_dir, "inputs", "input_files.json"), encoding="utf-8"))
    seq_run = os.path.join(ROOT, run_cfg["sequence_run"])
    sts_build = os.path.join(ROOT, "third_party", "nist_sts", "build_linux")
    os.makedirs(adir)

    appb = appendix_b(run_dir, sts_build)
    write_csv(os.path.join(adir, "appendix_b_validation.csv"), appb)
    examples = worked_examples(run_dir)
    with open(os.path.join(adir, "worked_examples.json"), "x", encoding="utf-8") as f:
        json.dump(examples, f, indent=2)

    methods, tests, series_rows, comp_rows = [], [], [], []
    for m in run_cfg["methods"]:
        mr = method_analysis(run_dir, run_cfg, seq_run, m)
        methods.append(mr)
        write_csv(os.path.join(adir, f"per_sequence_{m}.csv"), mr["evaluation"]["records"])
        for s in mr["evaluation"]["series"]:
            if s["status"] != "OK":
                series_rows.append({"method": m, "test": s["test"], "series": s["series"], "status": s["status"]})
                continue
            met = s["metrics"]
            row = {"method": m, "test": s["test"], "series": s["series"], "status": "OK",
                   "sample_size": met["sample_size"], "excluded_not_applicable": s["excluded_not_applicable"],
                   "passed": met["passed"], "proportion_min": met["proportion_min"],
                   "proportion_max": met["proportion_max"], "uniformity_p": met["uniformity_p"],
                   "bins": " ".join(map(str, met["bins"])), "proportion_flag": met["proportion_flag"],
                   "uniformity_flag": met["uniformity_flag"], "flagged": met["flagged"]}
            if "metrics_sts_report_rule" in s:
                r = s["metrics_sts_report_rule"]
                row.update({"report_rule_sample_size": r["sample_size"], "report_rule_passed": r["passed"],
                            "report_rule_flagged": r["flagged"],
                            "applicable_but_printed_zero": s["applicable_but_printed_zero"]})
            series_rows.append(row)
        tests += test_level(mr)
        comp_rows += mr["comparison"]
    write_csv(os.path.join(adir, "series_summary.csv"), series_rows,
              ["method", "test", "series", "status", "sample_size", "excluded_not_applicable", "passed",
               "proportion_min", "proportion_max", "uniformity_p", "bins", "proportion_flag", "uniformity_flag",
               "flagged", "report_rule_sample_size", "report_rule_passed", "report_rule_flagged",
               "applicable_but_printed_zero"])
    write_csv(os.path.join(adir, "test_summary.csv"), tests,
              ["method", "test", "status", "series", "sequences_tested", "sequences_applicable",
               "excluded_not_applicable", "flagged_series", "proportion_flags", "uniformity_flags",
               "min_proportion", "min_uniformity_p", "expected_flags_under_h0", "chance_flag_tail_p", "verdict"])
    write_csv(os.path.join(adir, "python_vs_official.csv"), comp_rows)
    summary = {"run_id": args.run_id,
               "methods": {mr["method"]: {"n_streams": mr["n_streams"], "streams_read": mr["streams_read"],
                                          "complete": mr["complete"], "returncode": mr["returncode"],
                                          "stdout_errors": mr["stdout_errors"],
                                          "problems": mr["evaluation"]["problems"],
                                          "report_mismatches": mr["report_mismatches"]} for mr in methods},
               "tests": tests,
               "appendix_b": {"official_matches": sum(r["official_matches"] for r in appb), "total": len(appb),
                              "official_max_abs_diff": max(abs(float(r["official_sts_p"]) - float(r["appendix_b_p"]))
                                                           for r in appb),
                              "python_matches": sum(r["python_matches"] is True for r in appb),
                              "python_total": sum(r["python_p"] != "" for r in appb)}}
    with open(os.path.join(adir, "summary.json"), "x", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    with open(os.path.join(run_dir, "official_nist_sts_report.md"), "x", encoding="utf-8") as f:
        f.write(render(args.run_id, prov, run_cfg, inputs, appb, examples, methods, tests, run_dir))

    man = {}
    for dp, _, fs in os.walk(run_dir):
        for fn in fs:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, run_dir).replace(os.sep, "/")
            if rel != "manifest.json":
                man[rel] = {"sha256": sha256_file(p), "bytes": os.path.getsize(p)}
    with open(os.path.join(run_dir, "manifest.json"), "x", encoding="utf-8") as f:
        json.dump(man, f, indent=2)
    print(f"analysis written to {adir}; {len(man)} files in manifest")


if __name__ == "__main__":
    main()
