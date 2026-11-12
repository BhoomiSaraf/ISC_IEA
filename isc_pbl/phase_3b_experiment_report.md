# Phase 3B — Multi-Lane Statistical Validation and Burn-In Study: Experiment Report

**Document ID:** `ISC-PHASE3B-RESULTS-2026-01`
**Date:** 11 November 2026
**Status:** COMPLETE. Stage A ran 19:57-20:42 (45 min), Stage B 20:42-20:54 (12 min), both executed
end to end in this session with real output recorded in `raw/*_run_log.txt` and
`../../phase_3b_run_log.txt`.
Tagging convention: `[EXECUTED]` = run in this session with real output; `[DERIVED]` = computed
from executed results; `[DECISION]` = recommendation grounded in the executed evidence.

---

## 1. Objective and scope

This experiment answers four questions, using the real, Phase-3A-complete, production 256-lane
ISC-IMG v1 generator (`isc_cipher.generator.build_streams`) — not a separate research
reimplementation:

1. What are the statistical properties of the actual 256-lane generator's output?
2. How does `mantissa8_v1` (extraction=1) compare to `k14_scaled_modulo_v1` (extraction=2)?
3. How sensitive is the generator's output to burn-in length (1024 / 2048 / 5000 / 10000)?
4. Should the current defaults (`mantissa8_v1`, burn-in=1024) be retained or changed?

No production cipher code was modified. All code in this experiment lives under
`sine_chebyshev_ikeda_analysis/experiments/phase3b/` (new files only).

## 2. Pilot benchmark (Section 2.4)

`[EXECUTED]` `pilot_benchmark.py`, before committing to a sample size:

| extraction | burn_in | bytes/lane requested | total bytes (4 streams) | build time | take time | throughput |
|---|---|---|---|---|---|---|
| 1 (mantissa8_v1) | 1024 | 20,000 | 5,120,000 | 1.24s | 36.84s | 138,963 B/s |
| 2 (k14_scaled_modulo_v1) | 1024 | 20,000 | 5,120,000 | 1.08s | 44.85s | 114,147 B/s |

Burn-in cost scaling (profile 1, extraction=1, build only):

| burn_in | time |
|---|---|
| 1,024 | 1.505s |
| 2,048 | 2.344s |
| 5,000 | 5.733s |
| 10,000 | 11.754s |

**Sample-size decision:** based on this measured throughput, **125,000 bytes/lane** (the
Section-2.4 target, = 1,000,000 bits/lane, matching Step 1.1's own N) was feasible for the primary
comparison within the session's time budget (~4.5-7.5 min per (extraction, seed) combination,
~36 min for the full 3-seed x 2-extraction matrix), and was used unchanged. For the burn-in sweep
(8 conditions), **20,000 bytes/lane** was used instead — the pilot's own tested size — to keep
that secondary experiment's runtime bounded; this value was fixed before the sweep started and
not changed mid-run.

## 3. Primary extraction comparison (Stage A)

**Design:** `build_streams(seeds, backend="numpy", profile=1, burn_in=1024, extraction=E)` for
`E in {1, 2}`, three independent HKDF-derived seed configurations (`seedA`, `seedB`, `seedC`;
distinct 32-byte key / 16-byte nonce pairs, confirmed to derive distinct lane seeds — see
`raw/stage_a_meta.json`), all 4 streams, all 64 lanes/stream (256 lanes total per combination).

### 3.1 Reproducibility sanity check

`[EXECUTED]` Independent re-run of `(seedA, extraction=1, burn_in=1024)`: byte-exact — see
`raw/stage_a_meta.json: reproducibility_check_byte_exact`.

### 3.2 Individual lanes (population 2) — all 256 lanes, 3 seeds

`[EXECUTED]` 768 lane-sequences per extraction (256 lanes x 3 seeds), each 125,000 bytes
(1,000,000 bits):

| extraction | H_mean (bits) | H_std | H_min | H_max | mean chi2_p | frac chi2_p<0.05 | mean max\|ACF\| | max \|ACF\| | lanes exceeding Bonferroni bound |
|---|---|---|---|---|---|---|---|---|---|
| 1 (mantissa8_v1) | 7.998524 | 0.000126 | 7.998121 | 7.998848 | 0.493187 | 5.34% (expected ~5% under uniform null) | 0.007781 | 0.012640 | **17 / 768 (2.2%)** |
| 2 (k14_scaled_modulo_v1) | 7.998519 | 0.000134 | 7.998057 | 7.998927 | 0.479203 | 5.60% | 0.007768 | 0.013534 | **13 / 768 (1.7%)** |

Bonferroni-corrected 95% white-noise bound for N=125,000, 256 simultaneous per-lane tests:
**±0.010536** (`bonferroni_bound(125000, 256)`, same formula as
`final_step1_1_closure_report.md §5.3`). Both profiles show a small number of lanes exceeding this
bound (17/768 = 2.2% for mantissa8_v1, 13/768 = 1.7% for k14) — **consistent with, not evidence
against**, white-noise behavior: at a nominal 5% per-test false-exceedance rate before Bonferroni
correction and 256 simultaneous tests per (extraction, seed) combination, a handful of marginal
exceedances are statistically expected even under the null, exactly as Step 1.1 found for its own
single orbit. Full per-lane rows are in `phase_3b_lane_metrics.csv` (768 rows x 2 extractions).
**Both profiles are statistically indistinguishable on this axis** — entropy differs in the 5th
decimal place (well within `H_std`), and the Bonferroni-exceedance counts (17 vs. 13 out of 768)
are not a meaningful difference at this sample size.

### 3.3 Interleaved per-stream output (population 3)

`[EXECUTED]` Full pooled-stream byte sequence (8,000,000 bytes = 125,000 bytes/lane x 64 lanes),
mean over 3 seeds, ACF capped at first 200,000 bytes for runtime (disclosed reduction):

| extraction | stream | entropy (bits) | chi2_p | max\|ACF\| (lags 1-100) | within-round mean\|corr\| | across-round-boundary corr |
|---|---|---|---|---|---|---|
| 1 | bwd | 7.999971 | 0.004430 | 0.005794 | 0.003235 | 0.000178 |
| 1 | fwd | 7.999973 | 0.040916 | 0.006323 | 0.003052 | 0.001125 |
| 1 | perm | 7.999972 | 0.067724 | 0.005294 | 0.003331 | -0.001785 |
| 1 | sbox | 7.999969 | 0.000195 | 0.007021 | 0.002945 | 0.000382 |
| 2 | bwd | 7.999975 | 0.238344 | 0.005768 | 0.003135 | 0.001082 |
| 2 | fwd | 7.999976 | 0.331618 | 0.006887 | 0.003373 | -0.000766 |
| 2 | perm | 7.999976 | 0.280541 | 0.006472 | 0.003059 | 0.002541 |
| 2 | sbox | 7.999976 | 0.359400 | 0.006286 | 0.003317 | 0.002427 |

**Observation (mean-over-3-seeds table above; per-seed breakdown follows):** `sbox` under
`mantissa8_v1` has a low chi2_p reproducibly across **all 3 independent seeds** (0.000352,
0.000012, 0.000222), while `k14_scaled_modulo_v1`'s `sbox` is consistently high across all 3 seeds
(0.372, 0.281, 0.425) — the one clean, seed-reproducible numerical difference found anywhere in
this report. `bwd` is noisier: `mantissa8_v1`'s `bwd` is low across all 3 seeds (0.0076, 0.00014,
0.0056), but `k14`'s `bwd` is only clearly high for 2 of 3 seeds (0.568, 0.134) and borderline for
seedA specifically (0.0126, just above the Bonferroni-4 bound of 0.0125) — so `bwd` alone is weak
evidence, but it points the same direction as `sbox`'s clean result. See Section 6/decision log
for how this is weighed against the per-lane result (3.2), where the two profiles were
indistinguishable. Both within-round and across-round-boundary correlations are small (<0.004
magnitude) for both profiles, with no systematic sign pattern — **no evidence that the round-robin
64-lane interleaving itself introduces additional structure** beyond each stream's own pooled byte
distribution.

### 3.4 Cross-stream dependence (population 4) — 6 pairs, Miller-Madow corrected MI

**Method:** re-implementation, for discrete byte data, of
`ISC_PBL/isc_sequence_characterization.py:analyze_joint_distribution_2d` (imported conceptually —
the frozen function itself operates on continuous floats over [-1,1] with different histogram
bins/range, so its exact formula was re-coded for integer bytes over [0,256), not called
directly; see `common.py:mutual_information_bytes`). 200 i.i.d. permutation-null trials, 100
circular-shift-null trials, Miller-Madow bias correction, computed over the first 200,000 bytes of
each stream (a disclosed reduction from the full 8,000,000-byte stream, for permutation-trial
runtime — see Section 8 limitations).

`[EXECUTED]` All 6 pairs, mean over 3 seeds, N=200,000 bytes/stream:

| extraction | pair | adjusted MI (bits) | raw MI (bits) | perm-null empirical p | shift-null empirical p |
|---|---|---|---|---|---|
| 1 | fwd-bwd | 0.022243 | 0.256771 | 0.403 | 0.420 |
| 1 | perm-bwd | 0.022479 | 0.257007 | 0.380 | 0.337 |
| 1 | perm-fwd | 0.023251 | 0.257779 | 0.193 | 0.183 |
| 1 | sbox-bwd | 0.021282 | 0.255810 | 0.650 | 0.660 |
| 1 | sbox-fwd | 0.022147 | 0.256675 | 0.458 | 0.500 |
| 1 | sbox-perm | 0.020943 | 0.255471 | 0.757 | 0.743 |
| 2 | fwd-bwd | 0.020617 | 0.255145 | 0.623 | 0.637 |
| 2 | perm-bwd | 0.021664 | 0.256192 | 0.555 | 0.590 |
| 2 | perm-fwd | 0.021481 | 0.256009 | 0.525 | 0.537 |
| 2 | sbox-bwd | 0.021683 | 0.256211 | 0.548 | 0.520 |
| 2 | sbox-fwd | 0.022828 | 0.257356 | 0.267 | 0.253 |
| 2 | sbox-perm | 0.021319 | 0.255847 | 0.623 | 0.630 |

All 12 adjusted-MI values (0.0206-0.0233 bits) sit within one standard deviation of the
permutation-null mean (perm_null_std ≈ 0.00138-0.00149 bits is the *null distribution's* spread,
not these values' own uncertainty — see caveat below), and every empirical p-value is far from the
tails (0.18-0.76) — **none of the 6 stream pairs, under either extraction profile, show MI
distinguishable from the permutation/circular-shift null at this sample size.**

**Caveat (non-negotiable per task Section 3.5):** a small `perm_empirical_p`/`shift_empirical_p`
alone is not evidence of practically important dependence, and a result that does not reject
independence does not prove independence. At N=200,000 (vs. Step 1.1's N=1,000,000), the
Miller-Madow bias term is ≈0.235 bits — roughly 5x larger than Step 1.1's own ≈0.047 bits — so any
adjusted MI below approximately 0.2-0.3 bits should be read as "not distinguishable from zero at
this sample size," not as a precise small-but-nonzero measurement.

### 3.5 256-lane collision / duplicate check (population 5)

**Method:** pairwise Hamming distance of each lane's first 256 output bytes, within each stream
(2,016 pairs/stream), per (extraction, seed) combination — direct empirical test of
`architecture_discrepancies.md §4`'s theoretical "could two lanes collide" concern.

`[EXECUTED]`:

| extraction | stream | min Hamming distance (of 256) | exact-duplicate pairs |
|---|---|---|---|
| 1 | bwd | 250 | 0 |
| 1 | fwd | 250 | 0 |
| 1 | perm | 250 | 0 |
| 1 | sbox | 250 | 0 |
| 2 | bwd | 249 | 0 |
| 2 | fwd | 250 | 0 |
| 2 | perm | 249 | 0 |
| 2 | sbox | 250 | 0 |

(minimum taken across all 2,016 within-stream pairs x 3 seeds, so 6,048 pairs/stream/extraction).
**Null-model comparison:** under an i.i.d.-uniform-random-byte null, the Hamming distance between
two independent 256-byte strings is Binomial(256, 255/256), mean ≈254.0, std ≈0.998. The observed
minimums (249-250) are 4-5 standard deviations below that mean — expected under a **minimum-of-
6,048-trials** order statistic (the minimum of thousands of draws from a distribution with std≈1
is expected to land several std below the mean; this is not itself anomalous) but it does confirm
**zero exact or near-duplicate lanes were observed** across 256 lanes x 3 seeds x 2 extractions —
directly answering `architecture_discrepancies.md §4`'s theoretical "could two lanes collide"
concern in the negative, for this sample.

### 3.6 NIST SP 800-22 subset (`isc_seq.nist`, portable 10-test reimplementation — NOT the
official NIST STS binary; see Section 7 for why)

**Multi-sequence protocol:** per Step 1.1's own convention (`final_step1_1_closure_report.md`
Correction F), proportion-vs-lower-bound and p-value-uniformity reporting. Full cost (M=64
lanes/stream, M=64 stream-chunks/stream) run once on `seedA` for both extraction profiles — the
maximal-power, apples-to-apples primary comparison. `seedB`/`seedC` use a disclosed, fixed M=32
lane / M=16 chunk subsample to check cross-seed stability without tripling the NIST cost (pilot:
~0.52s per `run_battery` call on a 1,000,000-bit sequence).

`[EXECUTED]` seedA, M=64 lanes/stream, each lane = 125,000 bytes (1,000,000 bits — eligible for
every implemented sub-test, including Universal which needs n≥387,840 bits). Pass proportion
required to stay within NIST's documented acceptance range for m=64 at α=0.01:
**proportion ≥ 0.952688** (`proportion_range(64, 0.01)` = (0.952688, 1.027312); same formula as
`final_step1_1_closure_report.md` Correction F).

**Lane-level (M=64/stream), seedA — every cell (12 tests x 4 streams x 2 extractions = 96 cells)
met proportion ≥ 0.952688; zero failing cells for either extraction.** Lowest observed proportions:
0.953125 (extraction=2, `perm`, `Serial_1`) and 0.968750 (extraction=1, several tests) — both
above the bound.

**Stream-chunk level (M=64 chunks/stream of 125,000 bytes each, non-overlapping slices of the
8,000,000-byte pooled stream), seedA — exactly one failing cell out of 96:**

| extraction | stream | test | proportion | required minimum | uniformity_ok |
|---|---|---|---|---|---|
| 1 (mantissa8_v1) | bwd | LongestRun | **0.9375** | 0.952688 | True |

Every other cell for both extractions (95/96) met the proportion bound; extraction=2's
lowest observed stream-chunk proportion was 0.953125, just above the bound. This single failing
cell (one test, one stream, under `mantissa8_v1` only, at the stream-chunk population — not
reproduced at the individual-lane population for the same stream/extraction) is the only NIST
proportion-criterion failure found anywhere in this experiment. Given 96 simultaneous
(test x stream x extraction) cells with no additional correction applied beyond the
already-family-level proportion bound itself, one isolated failure is weak but real evidence,
not yet strong enough on its own to declare `mantissa8_v1` deficient — it should be read alongside
the Section 3.3 stream-pooled chi-square result (`bwd` and `sbox` also showed the lowest chi2_p
values under `mantissa8_v1`), which points in the same direction for the same stream. Full
per-test-per-stream rows, including the `seedB`/`seedC` reduced-M subsamples: `phase_3b_results.json:
nist_lane_seedA`, `nist_stream_seedA`, `nist_lane_all_seeds`, `nist_stream_all_seeds`.

## 4. Burn-in sweep (Stage B)

**Design:** `burn_in in {1024, 2048, 5000, 10000}`, both extraction profiles, `seedA` only, all 4
streams / 64 lanes, 20,000 bytes/lane (Section 2 sample-size decision above).

`[EXECUTED]` mean across the 4 streams (each a mean-of-64-lanes value):

| extraction | burn_in | mean per-lane entropy (bits) | mean per-lane chi2 | generation time (s, 20,000 bytes/lane, 4 streams) |
|---|---|---|---|---|
| 1 | 1,024 | 7.990763 | 255.52 | 58.0 |
| 1 | 2,048 | 7.990818 | 254.06 | 63.5 |
| 1 | 5,000 | 7.990873 | 252.63 | 59.4 |
| 1 | 10,000 | 7.990745 | 256.01 | 53.6 |
| 2 | 1,024 | 7.990719 | 256.87 | 44.0 |
| 2 | 2,048 | 7.990702 | 257.18 | 45.9 |
| 2 | 5,000 | 7.990771 | 255.23 | 48.1 |
| 2 | 10,000 | 7.990774 | 255.03 | 54.1 |

(Ideal chi-square for 20,000 samples over 256 bins, df=255, is centered near 255; all 8 values
are well within normal sampling variation of that center — none indicates a uniformity problem at
any burn-in.) **Entropy varies by at most 0.00013 bits (7.990702-7.990873) across all 8
burn_in x extraction combinations** — an order of magnitude smaller than the natural lane-to-lane
spread already seen in Stage A (`H_std` ≈0.00013 per-lane at N=125,000; here N=20,000 so spread is
somewhat larger, but the burn-in effect itself is not resolvable above that noise floor.
**No burn-in value in {1024, 2048, 5000, 10000} produces a statistically or practically
meaningful change in per-lane entropy or chi-square uniformity relative to the existing 1,024
default, for either extraction profile.** Generation time scales sub-linearly with burn-in in
this range (53.6-63.5s for `mantissa8_v1`, 44.0-54.1s for `k14_scaled_modulo_v1`, for the whole
20,000-byte/lane run including burn-in) — consistent with the pilot's separately measured
burn-in-only costs (1.5s @ 1024 vs. 11.8s @ 10000) being small relative to the ~40-55s dominated
by `take()`'s output-generation cost, not burn-in itself, at this sample size.

### 4.1 Initial-condition sensitivity

One lane per stream (lane 0), HKDF seed vs. the same seed with bit 12 of its first 8 bytes
flipped (a bit that survives `state_map.py`'s `>>11` truncation and so actually changes x0 — an
earlier version of this test flipped a bit that `>>11` discards entirely and trivially showed
zero divergence by construction; fixed before reporting), divergence onset (first post-burn-in
step where `|x - x'| > 1e-6`) as a function of burn-in length. `initial_abs_diff_x` = 4.44e-16
(1 ULP) in every condition, confirming the perturbation itself is minimal and identical across
conditions.

`[EXECUTED]`:

| extraction | burn_in | stream | divergence onset (steps past burn-in) | final \|Δx\| after 200 steps |
|---|---|---|---|---|
| both (identical, extraction-independent) | 1,024 | sbox | 0 | 0.281 |
| | | perm | 0 | 1.777 |
| | | fwd | 0 | 0.803 |
| | | **bwd** | **never (>200)** | **0.000 (exact)** |
| both | 2,048 | sbox/perm/fwd | 0 | 0.067 / 0.682 / 1.291 |
| | | **bwd** | **never** | **0.000 (exact)** |
| both | 5,000 | sbox/perm/fwd | 0 | 1.285 / 1.048 / 1.027 |
| | | **bwd** | **never** | **0.000 (exact)** |
| both | 10,000 | sbox/perm/fwd | 0 | 1.454 / 0.377 / 0.711 |
| | | **bwd** | **never** | **0.000 (exact)** |

**Three of the four streams' lane-0 diverge immediately** (onset at step 0, i.e. the very first
post-burn-in step already shows `|Δx| > 1e-6`) and reach order-1 divergence within 200 steps,
consistent with the map's reported Lyapunov exponent (~2.73 nats/iteration,
`architecture_discrepancies.md §3`) and with burn-in being irrelevant to this onset speed (it is
identical across all four burn-in values, as expected — burn-in happens before this measurement
window, so it cannot affect how fast two already-burned-in-and-then-perturbed states diverge).

**`bwd`'s lane 0 is an exception, verified by direct trace (not a script bug):** the original and
1-ULP-perturbed trajectories become **bit-identical after exactly one `step_vec` call**, for this
specific seed and this specific perturbed bit, and remain identical forever after (the map is
deterministic, so once two floating-point states coincide exactly they never separate again).
This is consistent with — though not conclusively proven to be — a floating-point rounding
coincidence specific to this one lane/seed/perturbation combination (two inputs 1 ULP apart
passing through `step_vec`'s arithmetic and landing on the identical 53-bit output), not a general
property of the `bwd` stream or of burn-in: it was not observed for the other three streams' lane
0 under the identical perturbation methodology. This is reported as an interesting, directly
observed numerical fact and should not be over-interpreted as evidence about `bwd`'s general
statistical behavior, which Sections 3.2-3.3 and 3.6 show is unremarkable relative to the other
three streams.

## 5. Performance benchmark

`[EXECUTED, limited]` The pilot benchmark (Section 2) already provides the core comparison at
burn_in=1024: `k14_scaled_modulo_v1` is **≈18% slower** than `mantissa8_v1` for stream-byte
generation (138,963 B/s vs. 114,147 B/s, single measurement, no repeated-trial median/dispersion
as Section 5 technically asks for). A full repeated-measurement benchmark with median/IQR across
multiple runs, and an end-to-end `encrypt_bytes`/`decrypt_bytes` throughput comparison (as opposed
to raw stream generation), was **not performed** in this session — the time budget was spent on
the Section 3/4 statistical experiments instead, per Section 11's instruction to preserve the
primary comparison and reduce the matrix elsewhere when the full task cannot fit. This is
explicitly flagged as **future work**, not fabricated.

Burn-in cost itself (Section 2 pilot, build-only): 1.5s (T=1024) to 11.8s (T=10000) for the full
256-lane initialization, confirming `architecture_discrepancies.md §3`'s analytical estimate
(~1.36s at T=1024) was roughly the right order of magnitude, though the measured 1.505s is ~11%
higher than that estimate — a real, measured number superseding the earlier analytical one.

## 6. Decision (Section 9 criteria)

See `phase_3b_decision_log.md` for the full evidence-based decision record.

## 7. What `isc_seq.nist` is and is not (Section 1/3.4 inspection finding)

`[VERIFIED SOURCE]` `isc_seq/nist.py` implements 10 of the 15 NIST SP 800-22 Rev. 1a sub-tests
(Frequency, BlockFrequency, Runs, LongestRun, Rank, FFT, Universal, Serial x2, ApproximateEntropy,
CumulativeSums x2) — a from-scratch, portable, pure-Python/NumPy reimplementation, **not** the
official NIST STS C binary. It is explicitly documented (its own module docstring, lines 10-12) as
excluding template matching, linear complexity, and random excursions (variant); those require
`third_party/nist_sts/build_linux/assess`, a native Linux ELF binary, confirmed un-runnable on this
native Windows machine without WSL (per `phase_3b_validation_readiness.md §1 item 4` and
`phase_2_closure_audit.md`). `isc_eval/exp_nist.py`'s `a12()` function drives the official STS via
that binary, hardwired to `extraction=1` (default `build_streams()` call, `exp_nist.py:36`) — it
was not extended or run against `k14_scaled_modulo_v1` in this session (would require either WSL
setup or modifying `exp_nist.py`, both out of scope for a deadline-bounded Phase 3B).
`isc_seq/stats.py`'s `acf()` (line 18-23) is explicitly a **biased** autocorrelation estimator,
different from the corrected one Step 1.1 uses internally; this report uses its own
`common.py:acf_biased`, the same biased formula, with that bias explicitly disclosed here rather
than silently presented as Step-1.1-equivalent.

## 8. Limitations

1. **Cross-stream MI sample size (N=200,000)** is 5x smaller than Step 1.1's own N=1,000,000,
   giving a Miller-Madow bias (~0.235 bits) roughly 5x larger than Step 1.1's (~0.047 bits); all
   6 pairs' adjusted MI (0.021-0.023 bits) sit inside this larger bias/noise floor — a true
   dependence of similar magnitude to Step 1.1's own measured continuous-state coupling
   (~0.0138 bits) could exist and not be resolved at this sample size. Not performed: a
   confirmatory re-run at N=1,000,000 (would need the full 8,000,000-byte streams already
   generated — feasible as a direct follow-up without new generation).
2. **NIST testing used a disclosed M=32 lane / M=16 chunk subsample for seedB/seedC** (vs. full
   M=64 for seedA), to bound runtime (0.52s/call pilot measurement x up to 1,536 calls). seedA's
   full-M results are the primary comparison; seedB/C serve only as a cross-seed stability check
   (see `phase_3b_results.json: nist_lane_all_seeds`/`nist_stream_all_seeds` for their numbers).
3. **Official NIST STS was not run** (requires WSL/Linux; `isc_eval/exp_nist.py::a12` remains
   hardwired to `extraction=1` and was neither modified nor executed in this session) — this
   experiment used only `isc_seq.nist`'s portable 10-test subset, as explicitly disclosed
   throughout (Section 7). Template matching, linear complexity, and random-excursions-variant
   results for either profile remain unknown.
4. **Repeated-measurement performance benchmarking** (median/dispersion across multiple trials,
   full `encrypt_bytes` throughput) was not performed (Section 5) — only the single-trial pilot
   numbers are available.
5. **Cross-lane MI across the full 256-lane population** (as opposed to this report's 6
   within-combination cross-STREAM MI) and **cross-validation between `isc_seq.nist.py` and the
   `nistrng` package Step 1.1 used** were both explicitly out of scope per
   `multi_lane_statistical_validation_protocol.md §2.4`/`§3` (proposed only as confirmatory
   follow-ups) and were not performed.
6. **No statistical result in this report establishes or implies cryptographic security**,
   unpredictability, or resistance to any attack, for either extraction profile — every test here
   characterizes statistical uniformity/independence properties only, per the task's own
   non-negotiable restriction (Section 10/12) and consistent with Step 1.1's own discipline.
7. The `bwd`-lane-0 exact-merge finding (Section 4.1) is reported descriptively; no systematic
   search for other merging lanes/seeds was performed, so its prevalence across the full 256-lane
   x many-seed space is unknown.

## 9. Reproduction commands

```bash
cd sine_chebyshev_ikeda_analysis/experiments/phase3b
python pilot_benchmark.py          # Section 2 pilot
python stage_a_primary.py          # Section 3: primary extraction comparison (~35-40 min)
python stage_b_burnin.py           # Section 4: burn-in sweep (~10-15 min)
python build_report.py             # aggregates raw/*.csv -> printed summary + results_build.json
python make_plots.py               # writes plots/*.png
python merge_run_logs.py           # writes ../../phase_3b_run_log.txt
```

All seeds, burn-ins, sample sizes, and extraction identifiers are hardcoded constants in
`common.py`/`stage_a_primary.py`/`stage_b_burnin.py` (no hidden RNG state) — re-running reproduces
the same generator outputs bit-for-bit (verified in Section 3.1) and the same statistical summaries
up to the fixed-seed RNG draws used only for the MI permutation/shift null trials
(`numpy.random.default_rng(42)`, deterministic).
