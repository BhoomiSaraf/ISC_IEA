"""Driver and parser for the official NIST Statistical Test Suite (STS 2.1.2).

The official `assess` program is interactive and writes its outputs below
`experiments/AlgorithmTesting/<Test>/` relative to its working directory.  This
module prepares such a working directory, feeds the documented menu answers on
stdin, and parses the raw outputs.  It never modifies the official sources.

Output conventions of assess (from the STS 2.1.2 sources):

* results.txt holds one line per p-value, printf("%f") = 6 decimals.  The number
  of p-values written per sequence is fixed per test (P_VALUES_PER_SEQUENCE).
* RandomExcursions / RandomExcursionsVariant write 8 / 18 lines of 0.000000 when a
  sequence has fewer than max(0.005 sqrt(n), 500) cycles ("not applicable").
  finalAnalysisReport then drops every p <= 0 from these two tests, which would
  also drop a genuine p-value printed as 0.000000.  Applicability is therefore
  decided here from the cycle count J of each sequence (stats.txt, cross-checked
  against J recomputed from the input bits), not from the printed p-value.
* RandomExcursions writes nothing at all for a sequence with J > max(1000, n/100)
  and prints an ERROR on stdout; the line count check below detects this.
* finalAnalysisReport reads p-values back as C `float`, flags a proportion outside
  [floor(min), floor(max)] and computes uniformity with integer expected counts
  (sampleSize/10).  `sts_metrics` reproduces this exactly so the parsed report
  can be verified.
"""

import math
import os
import re
import shutil
import subprocess

import numpy as np
from scipy.special import gammaincc

ALPHA = 0.01

# Order of tests in assess (testVector index 1..15) and their output directories.
TESTS = [
    "Frequency", "BlockFrequency", "CumulativeSums", "Runs", "LongestRun", "Rank", "FFT",
    "NonOverlappingTemplate", "OverlappingTemplate", "Universal", "ApproximateEntropy",
    "RandomExcursions", "RandomExcursionsVariant", "Serial", "LinearComplexity",
]

P_VALUES_PER_SEQUENCE = {
    "Frequency": 1, "BlockFrequency": 1, "CumulativeSums": 2, "Runs": 1, "LongestRun": 1,
    "Rank": 1, "FFT": 1, "NonOverlappingTemplate": 148, "OverlappingTemplate": 1,
    "Universal": 1, "ApproximateEntropy": 1, "RandomExcursions": 8,
    "RandomExcursionsVariant": 18, "Serial": 2, "LinearComplexity": 1,
}

RE_STATES = [-4, -3, -2, -1, 1, 2, 3, 4]
REV_STATES = list(range(-9, 0)) + list(range(1, 10))

# Default parameters hard-coded in assess.c (used unchanged).
DEFAULT_PARAMETERS = {
    "blockFrequencyBlockLength": 128, "nonOverlappingTemplateBlockLength": 9,
    "overlappingTemplateBlockLength": 9, "approximateEntropyBlockLength": 10,
    "serialBlockLength": 16, "linearComplexitySequenceLength": 500, "ALPHA": ALPHA,
}


def series_labels(test):
    """Label of each p-value written per sequence, in output order."""
    if test == "CumulativeSums":
        return ["forward", "reverse"]
    if test == "Serial":
        return ["p_value1", "p_value2"]
    if test == "NonOverlappingTemplate":
        return [f"template{j:03d}" for j in range(148)]
    if test == "RandomExcursions":
        return [f"x={x:+d}" for x in RE_STATES]
    if test == "RandomExcursionsVariant":
        return [f"x={x:+d}" for x in REV_STATES]
    return ["p_value"]


# --------------------------------------------------------------------------- running

def to_wsl_path(path):
    path = os.path.abspath(path)
    drive, rest = os.path.splitdrive(path)
    if not drive:
        return path.replace("\\", "/")
    return f"/mnt/{drive[0].lower()}" + rest.replace("\\", "/")


PARAMETERISED = {"BlockFrequency", "NonOverlappingTemplate", "OverlappingTemplate", "ApproximateEntropy",
                 "Serial", "LinearComplexity"}


def prepare_workdir(workdir, sts_root, generator_dir="AlgorithmTesting"):
    """Create experiments/<generator_dir>/<Test>/ and templates/template9 in a new directory."""
    if os.path.exists(workdir):
        raise FileExistsError(workdir)
    for t in TESTS:
        os.makedirs(os.path.join(workdir, "experiments", generator_dir, t))
    os.makedirs(os.path.join(workdir, "templates"))
    shutil.copyfile(os.path.join(sts_root, "templates", "template9"),
                    os.path.join(workdir, "templates", "template9"))


def menu_answers(input_path, n_streams, binary, tests=None, generator=0):
    """stdin for assess.

    Menu order in STS 2.1.2: generator (0 = input file, then its path), test selection
    (1 = all, or 0 followed by a 15-digit 0/1 vector), parameter menu (only shown when a
    parameterised test is selected; 0 keeps the defaults), number of bitstreams, and for
    input files the format (0 = ASCII, 1 = packed binary).
    """
    parts = [str(generator)]
    if generator == 0:
        parts.append(input_path)
    if tests is None:
        parts.append("1")
        parts.append("0")
    else:
        parts.append("0")
        parts.append("".join("1" if t in tests else "0" for t in TESTS))
        if PARAMETERISED & set(tests):
            parts.append("0")
    parts.append(str(n_streams))
    if generator == 0:
        parts.append("1" if binary else "0")
    return "\n".join(parts) + "\n"


def run_assess(workdir, assess_path, input_path, n_bits, n_streams, binary, distro="Ubuntu-24.04",
               log_path=None, tests=None, generator=0):
    """Run official assess under WSL in `workdir`.  Returns (returncode, stdout).

    assess returns 1 from main() after a normal run, so the return code is recorded
    but completion is judged from the outputs.
    """
    stdin = menu_answers(to_wsl_path(input_path) if input_path else None, n_streams, binary, tests, generator)
    cmd = ["wsl", "-d", distro, "--cd", to_wsl_path(workdir), "--", to_wsl_path(assess_path), str(n_bits)]
    proc = subprocess.run(cmd, input=stdin.encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout.decode(errors="replace")
    if log_path:
        with open(log_path, "x", encoding="utf-8") as f:
            f.write("$ " + " ".join(cmd) + "\n")
            f.write("--- stdin ---\n" + stdin + "--- stdout/stderr ---\n" + out)
            f.write(f"\n--- returncode: {proc.returncode} ---\n")
    return proc.returncode, out


# --------------------------------------------------------------------------- parsing

def read_results(workdir, test, generator_dir="AlgorithmTesting"):
    path = os.path.join(workdir, "experiments", generator_dir, test, "results.txt")
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_test(workdir, test, n_streams):
    """Return (matrix of printed p-value strings [seq][series], problems list)."""
    lines = read_results(workdir, test)
    k = P_VALUES_PER_SEQUENCE[test]
    problems = []
    if len(lines) != n_streams * k:
        problems.append(f"{test}: {len(lines)} p-values in results.txt, expected {n_streams} x {k}")
        return None, problems
    return [lines[i * k:(i + 1) * k] for i in range(n_streams)], problems


_J_RE = re.compile(r"Number Of Cycles \(J\) = (\d+)")


def parse_cycle_counts(workdir, test):
    """Cycle count J per sequence and whether assess marked it NOT APPLICABLE, from stats.txt."""
    path = os.path.join(workdir, "experiments", "AlgorithmTesting", test, "stats.txt")
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    header = "RANDOM EXCURSIONS VARIANT TEST" if test == "RandomExcursionsVariant" else "RANDOM EXCURSIONS TEST"
    blocks = text.split(header)[1:]
    out = []
    for b in blocks:
        m = _J_RE.search(b)
        out.append({"J": int(m.group(1)) if m else None, "not_applicable": "NOT APPLICABLE" in b})
    return out


def cycle_count(bits):
    """J as computed by the official code: zeros of the +/-1 walk, plus one if it ends off zero."""
    s = np.cumsum(2 * np.asarray(bits, dtype=np.int64) - 1)
    return int(np.count_nonzero(s == 0)) + (1 if s[-1] != 0 else 0)


def re_constraint(n):
    return max(0.005 * math.sqrt(n), 500)


def sts_metrics(pvalue_strings, alpha=ALPHA):
    """Reproduce assess.c computeMetrics for one p-value series (already filtered for applicability).

    p-values are converted to C float, as assess reads them with fscanf("%f").
    """
    A = np.array([np.float32(s) for s in pvalue_strings], dtype=np.float32)
    sample = int(A.size)
    fails = int(np.sum(A.astype(np.float64) < alpha))  # C: float c promoted to double, compared with double ALPHA
    passed = sample - fails
    p_hat = 1.0 - alpha
    if sample:
        tmax = int((p_hat + 3.0 * math.sqrt(p_hat * alpha / sample)) * sample)
        tmin = int((p_hat - 3.0 * math.sqrt(p_hat * alpha / sample)) * sample)
    else:
        tmax = tmin = 0
    bins = [0] * 10
    for a in A.astype(np.float64):
        pos = int(math.floor(a * 10))
        if pos == 10:
            pos -= 1
        bins[pos] += 1
    exp_count = sample // 10
    if exp_count == 0:
        uniformity = None
    else:
        chi2 = sum((b - exp_count) ** 2 / exp_count for b in bins)
        uniformity = float(gammaincc(9.0 / 2.0, chi2 / 2.0))
    proportion_flag = sample > 0 and (passed < tmin or passed > tmax)
    uniformity_flag = uniformity is not None and uniformity < 0.0001
    return {
        "sample_size": sample, "passed": passed, "failed": fails,
        "proportion_min": tmin, "proportion_max": tmax, "bins": bins,
        "uniformity_p": uniformity,
        "proportion_flag": bool(proportion_flag), "uniformity_flag": bool(uniformity_flag),
        "flagged": bool(proportion_flag or uniformity_flag),
    }


_FAR_ROW = re.compile(
    r"^\s*((?:\d+\s+){10})(\d\.\d{6}\s*\*?|----)\s+(\d+/\d+\s*\*?|------)\s+(\S+)\s*$")


def parse_final_analysis_report(path):
    """Rows of finalAnalysisReport.txt in file order."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _FAR_ROW.match(line.rstrip("\n"))
            if not m:
                continue
            bins = [int(v) for v in m.group(1).split()]
            uni = m.group(2).strip()
            prop = m.group(3).strip()
            row = {"test": m.group(4), "bins": bins,
                   "uniformity_p": None if uni.startswith("-") else float(uni.rstrip("* ").strip()),
                   "uniformity_flag": uni.endswith("*"),
                   "passed": None, "sample_size": None, "proportion_flag": prop.endswith("*")}
            if not prop.startswith("-"):
                a, b = prop.rstrip("* ").split("/")
                row["passed"], row["sample_size"] = int(a), int(b)
            rows.append(row)
    return rows


def evaluate_workdir(workdir, n_streams, bitstreams=None, n_bits=None):
    """Parse every test of one assess run.

    bitstreams: optional callable i -> bits of sequence i, used to recompute J.
    Returns dict with per-sequence records, per-series metrics (two variants for the
    random-excursion tests) and a list of problems.
    """
    records, series, problems = [], [], []
    for test in TESTS:
        mat, probs = parse_test(workdir, test, n_streams)
        problems += probs
        if mat is None:
            series.append({"test": test, "series": "*", "status": "ERROR", "detail": "; ".join(probs)})
            continue
        labels = series_labels(test)
        applicable = [True] * n_streams
        J = [None] * n_streams
        if test in ("RandomExcursions", "RandomExcursionsVariant"):
            cyc = parse_cycle_counts(workdir, test)
            if len(cyc) != n_streams:
                problems.append(f"{test}: {len(cyc)} stats blocks, expected {n_streams}")
            for i in range(min(n_streams, len(cyc))):
                J[i] = cyc[i]["J"]
                applicable[i] = not cyc[i]["not_applicable"]
                if J[i] is not None and n_bits is not None:
                    expect_na = J[i] < (re_constraint(n_bits) if test == "RandomExcursions"
                                        else int(re_constraint(n_bits)))
                    if expect_na != cyc[i]["not_applicable"]:
                        problems.append(f"{test} seq {i}: applicability inconsistent with J={J[i]}")
                if bitstreams is not None:
                    jr = cycle_count(bitstreams(i))
                    if jr != J[i]:
                        problems.append(f"{test} seq {i}: J in stats.txt {J[i]} != recomputed {jr}")
        for i in range(n_streams):
            for k, lab in enumerate(labels):
                p = mat[i][k]
                records.append({"test": test, "series": lab, "sequence": i, "p_value": p,
                                "applicable": applicable[i], "J": J[i],
                                "outcome": ("not_applicable" if not applicable[i]
                                            else ("pass" if float(p) >= ALPHA else "fail"))})
        for k, lab in enumerate(labels):
            col = [mat[i][k] for i in range(n_streams)]
            app = [mat[i][k] for i in range(n_streams) if applicable[i]]
            entry = {"test": test, "series": lab, "status": "OK",
                     "excluded_not_applicable": n_streams - len(app),
                     "metrics": sts_metrics(app)}
            if test in ("RandomExcursions", "RandomExcursionsVariant"):
                # What finalAnalysisReport itself computes: every printed p <= 0 dropped.
                entry["metrics_sts_report_rule"] = sts_metrics([c for c in col if float(c) > 0])
                entry["applicable_but_printed_zero"] = sum(
                    1 for i in range(n_streams) if applicable[i] and float(mat[i][k]) <= 0)
            series.append(entry)
    return {"records": records, "series": series, "problems": problems}


def verify_against_report(evaluation, report_rows):
    """Compare our recomputed STS metrics with finalAnalysisReport rows (same order of series)."""
    ours = []
    for s in evaluation["series"]:
        if s["status"] != "OK":
            continue
        m = s.get("metrics_sts_report_rule", s["metrics"])
        ours.append((s["test"], m))
    mismatches = []
    if len(ours) != len(report_rows):
        mismatches.append(f"series count {len(ours)} != report rows {len(report_rows)}")
    for (test, m), r in zip(ours, report_rows):
        if test != r["test"]:
            mismatches.append(f"order: {test} vs {r['test']}")
            continue
        # finalAnalysisReport prints "------" (parsed as None) for an empty sample
        r_passed = 0 if r["sample_size"] is None else r["passed"]
        r_size = 0 if r["sample_size"] is None else r["sample_size"]
        same = (m["bins"] == r["bins"] and m["passed"] == r_passed and m["sample_size"] == r_size
                and m["proportion_flag"] == r["proportion_flag"] and m["uniformity_flag"] == r["uniformity_flag"]
                and ((m["uniformity_p"] is None and r["uniformity_p"] is None)
                     or (m["uniformity_p"] is not None and r["uniformity_p"] is not None
                         and abs(m["uniformity_p"] - r["uniformity_p"]) < 5e-7)))
        if not same:
            mismatches.append(f"{test}: ours {m} vs report {r}")
    return mismatches
