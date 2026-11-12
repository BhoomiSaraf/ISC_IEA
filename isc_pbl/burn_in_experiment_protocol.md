# Burn-In Experiment Protocol — 1,024 vs. 2,048 vs. 5,000 vs. 10,000 Iterations in the Actual 256-Lane Architecture

**Document ID:** `ISC-PHASE2-BURNIN-2026-01`
**Date:** 11 November 2026
**Status:** Experiment design only. No experiment has been executed. No numerical results are reported
in this document — any number below is a parameter of the proposed protocol, not a finding.

---

## 1. Why the two existing burn-in values are not directly comparable

`[VERIFIED SOURCE + ANALYSIS]`: Step 1.1's `T=5000` (`results/sequence_characterization/configuration.json:15`)
was applied to **one single orbit** (`x0=y0=0.1`, one trajectory, `N=1,000,000` retained samples after
burn-in). The cipher's `T=1024` (`generator.py:19, BURN_IN = 1024`) is applied **independently to all 256
HKDF-seeded lanes simultaneously** (`generator.py:131-132`, one shared burn-in loop over a length-256
vector). These differ in at least three confounded ways simultaneously: (a) the burn-in length itself, (b)
the initial condition (one fixed `(0.1, 0.1)` vs. 256 HKDF-derived points scattered over the `2^106`-point
grid), and (c) the arithmetic profile (Step 1.1 used host NumPy libm per
`architecture_discrepancies.md §5`; the cipher uses fdlibm profile 1). **Any comparison that changes only
the burn-in count while holding the lane architecture, seeds, and profile fixed is required to isolate
burn-in's own effect** — this is the controlling design principle below.

## 2. Experiment design

**Fixed across all four conditions** (so only burn-in length varies):
- Arithmetic: profile 1 (fdlibm), numpy backend (`isc_step.step_vec(..., profile=1)`), matching the
  cipher's actual normative path.
- Seed-generation protocol: use the **existing HKDF seed-derivation machinery already in the codebase**
  (`kdf.py: Derivation.seeds()`), with a **fixed, recorded `(key, nonce)` pair per run** so the 256 initial
  `(x0, y0)` states are identical across all four burn-in conditions — isolating burn-in as the only
  independent variable. Record the exact `key.hex()`/`nonce.hex()` used so the run is exactly reproducible.
- Extraction method: run the comparison under **both** `mantissa8_v1` (existing) and, once implemented,
  `k14_scaled_modulo_v1` (per `dual_profile_generator_design.md`) — burn-in sensitivity could plausibly
  differ by extraction method, so this should not be assumed identical across both profiles without testing.
- Sample size per lane per condition: propose **N = 10^5 output bytes per lane** (i.e. 5×10^4 output steps,
  since each step emits 2 bytes/lane) as a starting point — large enough for Chi-square/ACF/entropy
  tests to have reasonable power without the ~6-minute-plus runtime the 10^6-sample Step 1.1 protocol
  required *per condition* (four conditions × this runtime would be prohibitive to run interactively).
  This sample size is a **proposal for the next phase to tune**, not a validated final value.
- All 256 lanes (4 streams × 64 lanes) should be run per condition, not a subsample, so that per-stream and
  cross-stream comparisons (§4) have the full population available.

**Four conditions**, varying only `burn_in` passed to `generator.build_streams(seeds, backend="numpy",
profile=1, burn_in=T)`:
- T = 1,024 (existing default)
- T = 2,048
- T = 5,000 (Step 1.1's value)
- T = 10,000

## 3. Metrics to compute per condition (per the task's Phase E requirements)

For each of the 4 burn-in values, computed separately for (a) `mantissa8_v1` extraction and (b)
`k14_scaled_modulo_v1` extraction, and separately for each of the 5 statistical populations defined in
`phase_2_source_code_architecture_audit.md §5`:

1. **Per-lane output distributions:** byte histogram (256 bins) for each of the 256 lanes individually.
2. **Per-stream byte distributions:** byte histogram for each of the 4 streams' pooled 64-lane output.
3. **Byte entropy:** Shannon entropy (bits) of each per-lane and per-stream histogram; compare to the
   ideal 8.0 bits.
4. **Chi-square uniformity:** standard `scipy.stats.chisquare` against a uniform null, both per-lane and
   per-stream-pooled, with Bonferroni correction across the resulting 256 (or 4) simultaneous tests —
   following exactly the multiple-testing discipline Step 1.1 already established
   (`final_step1_1_closure_report.md §5.3`).
5. **Byte ACF:** autocorrelation up to lag 100 (matching `configuration.json: max_autocorr_lag: 100`),
   computed on (a) each individual lane's own sub-sequence (population 2) and (b) the full interleaved
   stream (population 3) — explicitly as two separate computations, since interleaving changes what
   "lag 1" physically means (population 2's lag-1 is 128 bytes apart in the actual output stream;
   population 3's lag-1 is the very next emitted byte, from a different lane).
6. **Cross-lane correlations:** pairwise correlation (or mutual information, matching Step 1.1's
   Miller-Madow-corrected MI methodology) between every pair of lanes' byte sequences within a stream —
   256 choose 2 = 2,016 pairs for cross-stream-global, or 64 choose 2 = 2,016 pairs within one stream;
   propose testing within-stream pairs first (lower combinatorial cost) and only extending to full
   256-lane cross terms if a within-stream anomaly is found.
7. **Cross-stream correlations:** same MI/correlation methodology applied between e.g. `fwd` and `bwd`
   streams' pooled output, to test the "are the four domain-separated streams statistically distinguishable"
   question.
8. **Initial-condition sensitivity:** for a small number of lanes (propose 8, one per stream × 2), compute
   output under the fixed seed and under a seed perturbed by flipping the single lowest bit of the 16-byte
   HKDF seed (before `seed_to_state`), then measure byte-level Hamming/bit-divergence onset as a function
   of iteration count past burn-in, for each of the 4 burn-in lengths — this directly probes whether longer
   burn-in changes how quickly/whether initial-seed correlation is destroyed, addressing the Phase 1
   Lyapunov-based argument (`architecture_discrepancies.md §3`) empirically rather than only theoretically.
9. **Output reproducibility:** re-run the identical `(key, nonce, burn_in)` combination twice independently
   and assert byte-exact equality — a sanity check that the measurement protocol itself introduces no
   nondeterminism (should trivially pass given profile-1 determinism, but must be checked, not assumed).
10. **Performance overhead:** wall-clock time for `build_streams(...)` (burn-in only, no extraction) at each
    of the 4 `T` values, averaged over a fixed number of repetitions (propose reusing Step 1.1's own
    `timing_repetitions: 3` convention from `configuration.json:37`), to quantify the latency cost of larger
    `T` directly on this machine, rather than relying on the Phase 1 report's analytical estimate alone
    (`architecture_discrepancies.md §3`: "256 lanes × 1,024 steps ≈ 1.36s vs ≈ 6.6s at T=5,000" — an estimate,
    not a timed measurement on this environment).

## 4. Statistical caveats that must be respected (per the task's explicit instruction)

`[METHODOLOGICAL REQUIREMENT, carried over from Step 1.1's own established discipline]`:
- Samples from one lane's own trajectory (population 2) are **serially dependent, deterministic**
  observations, not i.i.d. draws — the same caveat Step 1.1 applied to its single orbit. Chi-square and
  entropy statistics computed on such a sequence characterize *that one sequence's empirical distribution*,
  not an independent-sample estimate of "the" distribution; p-values from tests that assume i.i.d. sampling
  (e.g. naive NIST sub-tests) must be interpreted with the same care Step 1.1 applied (`final_step1_1_closure_report.md
  §4-§6`: Miller-Madow bias correction, permutation-null and circular-shift surrogates, Bonferroni correction
  for multiple lags).
- **Comparisons across lanes must use permutation or surrogate-based null distributions**, exactly as Step
  1.1 did for mutual information (1,000 i.i.d. permutation trials, 500 circular-shift surrogates;
  `final_step1_1_closure_report.md §4.1`), rather than assuming textbook independent-sample formulas apply,
  because the 256 lanes are not drawn i.i.d. from a stationary distribution in any proven sense — they are
  256 deterministic trajectories from 256 distinct (HKDF-derived, non-random-in-the-statistical-sense)
  initial points.
- Multiple-sequence NIST evaluation (if performed per `multi_lane_statistical_validation_protocol.md`)
  must use the same eligibility and pass-rate-vs-lower-bound methodology Step 1.1 used
  (`final_step1_1_closure_report.md` Correction F), not a single-sequence NIST run presented as conclusive.

## 5. Explicitly not done here

This document proposes an experiment design only. No burn-in comparison code has been written, and no
burn-in-dependent numbers (entropy, Chi-square, ACF, or timing) are reported anywhere in this document or
elsewhere in this Phase 2 deliverable set, in compliance with the task's explicit instruction not to
fabricate or prematurely report experimental conclusions.
