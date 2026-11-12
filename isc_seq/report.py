"""Render results.json of a sequence-generation run as a Markdown report.

The report only restates numbers computed in the run; it adds no external claims.
"""

import math


def _f(v, nd=6):
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        if v != 0 and (abs(v) < 1e-4 or abs(v) >= 1e6):
            return f"{v:.3e}"
        return f"{v:.{nd}f}"
    return str(v)


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_f(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _setup(r, L):
    cfg, env = r["config"], r["environment"]
    nc = cfg["nist"]
    p = cfg["params"]
    L.append("## Setup\n")
    L.append("Frozen ISC map:\n")
    L.append("```\nt_n = c - d/(1 + x_n^2 + y_n^2)\nX_n = 1 + a(x_n cos t_n - y_n sin t_n)\n"
             "Y_n = a(x_n sin t_n + y_n cos t_n)\nx_{n+1} = 2 sin^2(w X_n) - 1\ny_{n+1} = 2 sin^2(w Y_n) - 1\n```\n")
    L.append(_table(["parameter", "value"], [["a", repr(p["a"])], ["c", repr(p["c"])], ["d", repr(p["d"])],
                                            ["omega", repr(p["omega"])]]) + "\n")
    L.append(_table(["setting", "value"], [
        ["sequences (independent initial conditions)", cfg["n_sequences"]],
        ["initial conditions", f"PCG64(seed={cfg['seed']}), uniform in [-1, 1)^2 (initial_conditions.csv)"],
        ["transient iterations discarded", cfg["transient"]],
        ["bits per sequence", cfg["bits_per_sequence"]],
        ["map iterations per sequence", r["iterations_per_sequence"]],
        ["extraction methods", ", ".join(cfg["methods"])],
        ["NIST alpha / serial m / ApEn m / block M", f"{nc['alpha']} / {nc['serial_m']} / {nc['apen_m']} / {nc['block_M']}"],
        ["python / numpy / scipy / isc_seq", f"{env['python']} / {env['numpy']} / {env['scipy']} / {env['isc_seq']}"],
        ["platform", f"{env['platform']} ({env['machine']})"],
        ["started (UTC)", env["timestamp_utc"]],
        ["run time (s)", round(r["elapsed_seconds"])],
    ]) + "\n")


def _evaluation(L):
    L.append("## Floating-point evaluation: canonical vs legacy\n")
    L.append("Two evaluations of the same frozen equations exist in `isc_seq.isc_map`:\n")
    L.append(_table(["", "`isc_step` (canonical)", "`legacy_step` (legacy-exact)"], [
        ["squares", "`x*x`, `s*s` (IEEE exactly rounded)", "`x**2`, `np.sin(.)**2` (C `pow()` on NumPy scalars)"],
        ["scalar vs vectorised", "bit-identical (tested)", "can differ by 1 ulp"],
        ["matches `script/*.py`", "per step to < 1e-13; orbits separate after tens of iterations", "bit-identical (tested)"],
        ["used in this run for", "all sequences, bitstreams, NIST, raw statistics, all periodicity rows not labelled legacy",
         "periodicity row `legacy_step float32 (0.1,0.1)` and the legacy reproduction check"],
    ]) + "\n")
    L.append("Because the map is chaotic, any 1-ulp difference grows to O(1) within tens of iterations, so a bitstream is "
             "reproducible only for the same evaluation, the same `sin`/`cos` implementation (platform C library / NumPy "
             "build) and the same float precision. Numbers here are reproducible on the recorded environment; on another "
             "platform compare `bitstreams/*.bin` by SHA-256 (`manifest.json`) before assuming identity. Statistical "
             "conclusions should not depend on that, but exact bit identity can.\n")


def _completeness(r, L):
    cfg = r["config"]
    m_expected = cfg["n_sequences"]
    L.append("## Completeness\n")
    rows, problems = [], []
    for name in cfg["methods"]:
        tests = r["nist"].get(name)
        if tests is None:
            rows.append([name, m_expected, 0, 0, "MISSING"])
            problems.append(f"method `{name}` produced no NIST results")
            continue
        ms = {v["m"] for v in tests.values()}
        complete = ms == {m_expected}
        rows.append([name, m_expected, ",".join(map(str, sorted(ms))), len(tests), "complete" if complete else "INCOMPLETE"])
        if not complete:
            problems.append(f"method `{name}`: sequences per test {sorted(ms)} != {m_expected}")
    L.append(_table(["method", "sequences expected", "sequences with p-values", "p-values per sequence", "status"], rows) + "\n")
    if cfg["bits_per_sequence"] < 387840:
        L.append("Maurer's universal test was not run: it needs n >= 387 840 bits per sequence.\n")
    unfound = [row for row in r["periodicity"]["rows"] if not row["cycle_found"]]
    if unfound:
        problems.append(f"{len(unfound)} periodicity orbit(s) reached the step budget without a detected cycle "
                        "(recorded as such in periodicity.csv; this is a search limit, not an error)")
    L.append("Recorded failures / incomplete items: " + ("none." if not problems else "") + "\n")
    for p in problems:
        L.append(f"- {p}")
    L.append("")


def _raw(r, L):
    rs = r["raw_stats"]
    L.append("## Raw trajectory (sequence 0)\n")
    L.append(_table(["metric", "x", "y"], [
        ["min", rs["min_x"], rs["min_y"]], ["max", rs["max_x"], rs["max_y"]],
        ["mean", rs["mean_x"], rs["mean_y"]], ["P(value > 0)", rs["p_x_gt_0"], rs["p_y_gt_0"]],
        ["Shannon entropy, 256 bins (bits)", rs["H_x_bits"], rs["H_y_bits"]],
    ]) + "\n")
    L.append(f"N = {rs['n']}; lag-0 correlation(x, y) = {_f(rs['corr_xy_lag0'])}; "
             f"joint entropy H(x,y) on 256x256 bins = {_f(rs['H_xy_bits'])} bits.\n")
    band = rs["acf_band_95"]
    acf_rows = [[k + 1, rs["acf_x"][k], rs["acf_y"][k]] for k in range(len(rs["acf_x"]))]
    L.append(f"Autocorrelation (white-noise 95% band: +/-{_f(band)}):\n")
    L.append(_table(["lag", "ACF x", "ACF y"], acf_rows) + "\n")
    out_x = sum(abs(v) > band for v in rs["acf_x"])
    out_y = sum(abs(v) > band for v in rs["acf_y"])
    L.append(f"Lags outside the band: x {out_x}/{len(rs['acf_x'])}, y {out_y}/{len(rs['acf_y'])} "
             "(about 1 in 20 is expected by chance for white noise).\n")
    L.append("2-D histogram entropy versus sample size (the estimate is bounded by log2 N and rises with N, "
             "so values are comparable only at equal N and binning):\n")
    L.append(_table(["N", "H(x,y) bits", "normalised", "log2 N"],
                    [[e["n"], e["H_xy_bits"], e["H_xy_normalized"], e["log2_n_bound"]] for e in r["entropy_vs_n"]]) + "\n")


def _bits(r, L):
    L.append("## Extraction methods: descriptive bit statistics\n")
    L.append("Computed on the concatenation of the first "
             f"{next(iter(r['bit_stats'].values()))['sequences_used']} sequences (single pooled sample, not the NIST protocol).\n")
    bs_rows = []
    for name, b in r["bit_stats"].items():
        bs_rows.append([name, b["n_bits"], b["ones_fraction"], b["monobit_p"], b["p_bit_equals_next"],
                        b["byte_chi2_p"], b["byte_entropy_bits"]])
    L.append(_table(["method", "bits", "ones fraction", "monobit p", "P(b_i = b_i+1)", "byte chi2 p (255 dof)",
                     "byte entropy (bits)"], bs_rows) + "\n")


def _nist(r, L):
    nc = r["config"]["nist"]
    L.append("## NIST SP 800-22 (implemented subset, multi-sequence protocol)\n")
    any_name = next(iter(r["nist"]))
    first = next(iter(r["nist"][any_name].values()))
    m, lo = first["m"], first["proportion_min"]
    L.append(f"m = {m} sequences of {r['config']['bits_per_sequence']} bits per method, each sequence from its own "
             f"initial condition. A test passes when the proportion of sequences with p >= {nc['alpha']} is at least "
             f"{_f(lo, 4)} and, for m >= 55, the uniformity of the p-values gives P_T >= 0.0001. Cells show "
             "`PASS/FAIL (sequences passing/m, P_T)`. Template-matching, linear-complexity and random-excursion tests are "
             "not implemented here; `bitstreams/*.bin` can be given to the official NIST STS for those.\n")
    tests = list(r["nist"][any_name])
    rows = []
    for t in tests:
        row = [t]
        for name in r["nist"]:
            v = r["nist"][name].get(t)
            if v is None:
                row.append("n/a")
            else:
                u = "" if v["uniformity_p"] is None else f", P_T={_f(v['uniformity_p'], 4)}"
                row.append(f"{'PASS' if v['pass'] else 'FAIL'} ({v['passed']}/{v['m']}{u})")
        rows.append(row)
    L.append(_table(["test"] + list(r["nist"]), rows) + "\n")
    tot = []
    for name, tv in r["nist"].items():
        failed = [t for t, v in tv.items() if not v["pass"]]
        tot.append([name, sum(v["pass"] for v in tv.values()), len(tv), ", ".join(failed) or "-"])
    L.append("Aggregate (number of p-value series meeting both protocol criteria):\n")
    L.append(_table(["method", "passed", "of", "failed tests"], tot) + "\n")
    L.append("Interpretation limits: these tests can reject a generator but cannot certify one. Passing the "
             "implemented subset means no deviation from i.i.d. uniform bits was detected by these statistics at this "
             "sample size; it is not evidence of cryptographic security (unpredictability, key-recovery resistance, "
             "resistance to attacks exploiting the known deterministic map). With many series evaluated, an isolated "
             "marginal failure can occur by chance; a method that fails several tests decisively is non-random.\n")


def _periodicity(r, L):
    per = r["periodicity"]
    pc = r["config"]["periodicity"]
    L.append("## Finite-precision periodicity (Brent's algorithm)\n")
    L.append("Each orbit is iterated in the stated precision, with the state cast back to that precision after every step. "
             "'quantised k bits' means float64 arithmetic with x and y rounded to multiples of 2^-k after every step "
             "(a finite state of about (2^(k+1)+1)^2 points). mu = pre-period (index of the first state on the cycle; the "
             "initial condition is index 0), lambda = period. The step budget bounds the number of map evaluations "
             "in Brent's period-finding phase; when it is exhausted the orbit is reported as 'no cycle within budget', "
             "which is a lower-bound statement only. Initial conditions: PCG64(seed + 1) in [-1, 1)^2, cast to the "
             "stated precision.\n")
    groups = {}
    for row in per["rows"]:
        groups.setdefault(row["case"], []).append(row)
    g_rows = []
    for case, rows_ in groups.items():
        found = [x for x in rows_ if x["cycle_found"]]
        lams = sorted(x["lambda"] for x in found)
        mus = sorted(x["mu"] for x in found)
        g_rows.append([case, rows_[0]["dtype"], rows_[0]["quant_bits"] if rows_[0]["quant_bits"] is not None else "-",
                       len(rows_), len(found),
                       "-" if not mus else f"{mus[0]} .. {mus[-1]}",
                       "-" if not lams else f"{lams[0]} .. {lams[-1]}",
                       "-" if not lams else round(math.exp(sum(math.log(v) for v in lams) / len(lams))),
                       rows_[0]["budget_steps"]])
    L.append(_table(["case", "dtype", "quant bits", "orbits", "cycles found", "mu range", "lambda range",
                     "lambda geo. mean", "step budget"], g_rows) + "\n")
    L.append("Per-orbit values (also in `periodicity.csv`):\n")
    L.append(_table(["case", "x0", "y0", "mu", "lambda", "budget"],
                    [[x["case"], x["x0"], x["y0"], x["mu"] if x["cycle_found"] else "no cycle within budget",
                      x["lambda"] if x["cycle_found"] else "-", x["budget_steps"]] for x in per["rows"]]) + "\n")
    lg = per.get("legacy") or {}
    if lg.get("brent"):
        mu, lam = lg["brent"]
        fi = lg.get("floyd_meeting_index")
        L.append(f"Legacy reconciliation: with `legacy_step` in float32 from (0.1, 0.1), Brent gives mu = {mu}, "
                 f"lambda = {lam}. Floyd's meeting index as computed by `find_cycle` in `script/final_validation.py` "
                 f"(max_iter = {pc['legacy_floyd_max_iter']}) = {_f(fi)}"
                 + (f" = {fi // lam} x lambda" if fi and fi % lam == 0 else "") +
                 ". The value previously reported as 'Cycle_Length_Float32' is this meeting index, not the period.\n")


def _legacy(r, L):
    lr = r.get("legacy_reproduction")
    if not lr:
        return
    L.append("## Legacy reproduction check\n")
    same = lr["acf1_x_stored"] is not None and abs(lr["acf1_x_recomputed"] - lr["acf1_x_stored"]) < 1e-12
    L.append(f"Lag-1 ACF of x recomputed with `legacy_step` (x0 = y0 = 0.1, transient 5000, N = 100000): "
             f"{lr['acf1_x_recomputed']!r}; value stored in `{lr['source']}`: {lr['acf1_x_stored']!r} "
             f"({'agree to < 1e-12' if same else 'DO NOT AGREE'}).\n")


def _reproduce(r, L):
    L.append("## Reproducing this run\n")
    L.append("```bash\npython experiments/run_sequence_experiment.py --config <run dir>/config.json --run-id <new id>\n```\n")
    L.append("`config.json` holds the full merged configuration (seed, sizes, methods, NIST and periodicity settings); "
             "`environment.json` the interpreter, library versions and platform; `initial_conditions.csv` the exact "
             "initial conditions (repr of float64). Compare the new run's `manifest.json` hashes with this one.\n")
    L.append("## Files\n")
    L.append("`config.json`, `environment.json`, `initial_conditions.csv`, `raw_trajectory_seq000.npz`, "
             "`raw_stats_seq000.json`, `entropy_vs_n_seq000.csv`, `bit_stats.csv`, `nist/summary.csv`, "
             "`nist/pvalues_<method>.csv`, `bitstreams/<method>.bin` (packed MSB-first, sequences concatenated in "
             "initial-condition order), `periodicity.csv`, `results.json`, `report.md`, `manifest.json` "
             "(SHA-256 of every other file).\n")


def render_report(r):
    L = [f"# ISC sequence-generation experiment `{r['run_id']}`\n",
         "Generated automatically by `isc_seq.experiment`; every number below was computed in this run "
         "(see `results.json`, `manifest.json`). Scope: sequence generation only; no encryption.\n"]
    _setup(r, L)
    _evaluation(L)
    _completeness(r, L)
    _raw(r, L)
    _bits(r, L)
    _nist(r, L)
    _periodicity(r, L)
    _legacy(r, L)
    _reproduce(r, L)
    return "\n".join(L)
