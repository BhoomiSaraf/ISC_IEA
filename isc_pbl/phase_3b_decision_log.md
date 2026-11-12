# Phase 3B — Decision Log

**Document ID:** `ISC-PHASE3B-DECISION-2026-01`
**Date:** 11 November 2026
**Status:** FINAL. All Stage A/B experiments executed; see `phase_3b_experiment_report.md` for
full numbers and methodology.

Per Section 9 of the task, the final recommendation on extraction must be exactly one of:
*retain `mantissa8_v1`*, *recommend `k14_scaled_modulo_v1`*, *treat both as statistically
comparable*, or *inconclusive*. On burn-in: retain 1,024 unless the experiment gives a compelling,
reproducible reason otherwise.

## Evidence checklist (filled in from `phase_3b_experiment_report.md` Sections 3-4)

| Evidence axis | mantissa8_v1 | k14_scaled_modulo_v1 | Distinguishable? |
|---|---|---|---|
| Per-lane entropy (256 lanes x 3 seeds) | 7.998524 ± 0.000126 | 7.998519 ± 0.000134 | **No** — differ in 5th decimal, within each other's std |
| Per-lane chi-square (mean p, frac p<0.05) | 0.4932, 5.34% | 0.4792, 5.60% | **No** — both consistent with uniform null (~5% expected) |
| Per-lane ACF vs. Bonferroni bound (±0.010536) | 17/768 lanes exceed (2.2%) | 13/768 exceed (1.7%) | **No** — both small, consistent with chance exceedance under 256 simultaneous tests |
| Per-stream chi2_p (pooled 8M bytes, 4 streams) | 0.0002-0.068 (sbox, bwd below 0.0125 Bonferroni-4 bound) | 0.238-0.359 (none below bound) | **Yes, mild** — mantissa8_v1's sbox/bwd streams show low pooled-level uniformity p-values; k14 does not |
| Round-vs-cross-round correlation | ~0.003-0.007 magnitude | ~0.003-0.007 magnitude | **No** — both small, no sign pattern |
| Cross-stream adjusted MI (6 pairs) | 0.0209-0.0233 bits, p=0.19-0.76 | 0.0206-0.0228 bits, p=0.25-0.64 | **No** — both within permutation/shift null range at this (reduced) sample size |
| 256-lane collision check | min Hamming 250/256, 0 duplicates | min Hamming 249/256, 0 duplicates | **No** — both consistent with the random-byte null's expected minimum-of-6048-trials order statistic |
| NIST pass proportions, lanes (seedA, M=64) | 0/48 cells fail proportion bound | 0/48 cells fail | **No** — both fully pass |
| NIST pass proportions, stream-chunks (seedA, M=64) | **1/48 cells fail** (bwd, LongestRun, 0.9375 vs 0.9527 required) | 0/48 cells fail | **Yes, weak** — one isolated failure for mantissa8_v1, consistent in direction with the chi2_p finding above (same `bwd` stream) |
| Cross-seed stability (seedB/C, reduced M) | stable (see `phase_3b_results.json`) | stable | **No** — no seed-dependent anomaly surfaced for either profile |
| Throughput (pilot, single trial) | 138,963 B/s | 114,147 B/s | **Yes** — k14 ≈18% slower |

## Extraction decision

**VERDICT: Treat `mantissa8_v1` and `k14_scaled_modulo_v1` as statistically comparable within the
tested scope**, with one disclosed, mild, directionally-consistent signal favoring `k14` at the
pooled-stream level that is not yet strong enough to recommend a switch.

**What is supported by the evidence:**
- At the individual-lane level — the population carrying the most statistical power in this
  experiment (256 lanes x 3 seeds, N=1,000,000 bits/lane) — the two profiles are indistinguishable
  on entropy, chi-square uniformity, autocorrelation, and NIST pass proportions. This is the
  primary comparison population, run at full strength for both profiles.
- At the pooled-stream level, `mantissa8_v1`'s `sbox` stream shows low chi-square p-values
  **reproducibly across all 3 independent seeds** (0.000352, 0.000012, 0.000222) while `k14`'s
  `sbox` is consistently high across all 3 seeds (0.372, 0.281, 0.425) — this is the one clean,
  seed-reproducible signal in the whole experiment. `bwd` is noisier: `mantissa8_v1`'s `bwd` is
  low across all 3 seeds (0.0076, 0.00014, 0.0056), but `k14`'s `bwd` is only clearly high for 2
  of 3 seeds (0.568, 0.134) and borderline for the third (seedA: 0.0126, just above the
  Bonferroni-4 bound of 0.0125) — so `bwd` alone would not be strong evidence, but combined with
  `sbox`'s clean result it points the same direction. One isolated NIST proportion failure also
  appears for `mantissa8_v1`/`bwd`/`LongestRun` at the stream-chunk population (seedA) that does
  not appear for `k14` anywhere. Taken together this is not pure noise, but it is also only 2 of 11
  evidence axes, from a single stream, under a single extraction, observed at a population
  (pooled 8,000,000-byte sequences) known from Step 1.1's own methodology to have very high
  statistical power that can detect practically small deviations (Step 1.1 itself noted
  `p~10^-847`-type underflow from sheer sample size at N=10^6; the same phenomenon can produce a
  "significant" p-value for a real but tiny, possibly practically irrelevant, deviation at
  N=8,000,000). Per the task's explicit instruction not to declare a profile superior from a
  marginal metric difference, this signal is reported and flagged for follow-up, not acted on.
- Cross-stream dependence, lane collisions, and cross-seed stability show no difference between
  profiles for either extraction.
- Throughput measurably favors `mantissa8_v1` by ≈18% (single-trial pilot measurement, not
  repeated — Limitation 4 in the experiment report).

**What is NOT supported / remains unknown:**
- The official NIST STS confirmatory tier (template matching, linear complexity, random
  excursions variant) was not run for either profile (WSL dependency, out of scope this session).
- The cross-stream MI comparison used a 5x smaller sample than Step 1.1's own protocol, so a true
  dependence at Step-1.1-reported magnitude (~0.0138 bits) could exist undetected for either
  profile.
- No claim is made, for either profile, about cryptographic security, unpredictability, or
  resistance to any attack — every result above is a statistical uniformity/independence
  characterization only.
- Whether the `bwd`/`sbox` stream-level signal is a stable property of `mantissa8_v1`'s extraction
  method specifically, or an artifact of this particular seed set / sample size, is not resolved
  — it was observed consistently across all 3 seeds for the chi-square result but the NIST
  proportion failure was observed only at seedA's full-M stream-chunk run.

## Burn-in decision

**VERDICT: RETAIN the existing 1,024-step burn-in default.** No compelling, reproducible reason
to change it was found.

- Mean per-lane entropy across all 4 streams varied by at most **0.00013 bits** across
  burn_in ∈ {1024, 2048, 5000, 10000} for either extraction profile — an order of magnitude
  smaller than normal lane-to-lane sampling spread at this sample size, and not a monotonic trend
  (e.g. `mantissa8_v1`'s entropy peaks at T=5000 then drops at T=10000: 7.990763 → 7.990818 →
  7.990873 → 7.990745 — not a "longer is better" pattern).
- Mean per-lane chi-square stayed within normal sampling variation of its df=255 expectation at
  every T for both profiles (252.6-257.2, all centered near 255).
- Initial-condition divergence onset (Section 4.1) was **identical across all 4 burn-in values**
  for 3 of 4 streams (onset at step 0 in every case) — burn-in length has no measurable effect on
  how fast a post-burn-in perturbation diverges, consistent with the task's own warning that
  "a longer burn-in is not automatically better."
- Generation cost scales measurably with burn-in in isolation (pilot: 1.5s @ T=1024 to 11.8s
  @ T=10000, build-only), so a longer default would add measurable latency for no observed
  statistical benefit.
- This conclusion applies to **both** extraction profiles — burn-in sensitivity was not found to
  differ by extraction method in this experiment, answering `burn_in_experiment_protocol.md §2`'s
  open question ("burn-in sensitivity could plausibly differ by extraction method... should not be
  assumed identical without testing") in the negative, within the tested scope (seedA only, 20,000
  bytes/lane — Limitation: not cross-checked against seedB/C or the full 125,000-byte sample).

## What remains open for a future phase (explicitly not claimed here)

1. Official NIST STS (`third_party/nist_sts`, via WSL) confirmatory run on `k14_scaled_modulo_v1` —
   not performed; `isc_eval/exp_nist.py::a12` remains hardwired to `mantissa8_v1`.
2. Full 256-choose-2 cross-lane MI (vs. this report's within-stream-pair cross-STREAM MI) —
   not performed; `multi_lane_statistical_validation_protocol.md §2.4` proposed this only as a
   confirmatory follow-up if within-stream anomalies appeared.
3. Cross-validation between `isc_seq.nist.py`'s reimplementation and the `nistrng` package Step 1.1
   used, and against the official STS, on an identical bitstream — not performed.
4. No statistical test here constitutes or implies a cryptographic security proof, for either
   extraction profile, per the task's non-negotiable Section 10/12 restriction.
5. `mantissa8_v1`'s `sbox` stream showing a clean, 3-seed-reproducible low chi-square p-value
   while `k14`'s does not (Section 3.3) is flagged but not root-caused — a direct follow-up would
   compare `sbox`'s byte histogram shape between the two profiles to see whether the deviation is
   structural (e.g. a specific byte-value bias) or a borderline large-N statistical-power artifact
   (Step 1.1 itself documented this exact phenomenon for its own single-orbit KS tests).
6. The `bwd`-lane-0 exact floating-point trajectory merge after one step (Section 4.1) is reported
   as a directly observed, verified numerical fact for one specific seed/lane/perturbation; its
   general prevalence is unknown (Limitation 7 in the experiment report) and it was not found to
   correlate with the `sbox`/`bwd` chi-square finding above (the merge test is extraction-
   independent; the chi-square finding is extraction-dependent).
