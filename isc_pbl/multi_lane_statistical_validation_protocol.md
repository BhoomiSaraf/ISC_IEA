# Multi-Lane Statistical Validation Protocol

**Document ID:** `ISC-PHASE2-MULTILANE-STATS-2026-01`
**Date:** 11 November 2026
**Status:** Protocol design only. No statistical results are reported here.

---

## 1. Why Step 1.1's results do not transfer automatically

`[CARRIED FORWARD FROM PHASE 1, re-grounded in source code here]`: Step 1.1's NIST/Chi-square/MI/ACF
results (`final_step1_1_closure_report.md`) were computed on **one single orbit** of `N=10^6` samples under
`T=5000` burn-in, host-libm arithmetic. The actual shipped generator (`generator.py:111-135`) produces
bytes from **256 HKDF-seeded lanes, T=1024, fdlibm profile-1 arithmetic, round-robin-interleaved within
each of 4 streams** (architecture confirmed in `phase_2_source_code_architecture_audit.md §4`). These are
different statistical objects. This protocol defines how to test the *actual* generator's output, for both
the existing `mantissa8_v1` extraction and the proposed `k14_scaled_modulo_v1` extraction (once
implemented per `dual_profile_generator_design.md`).

## 2. Scope: what must be tested, distinctly, per the task's Phase F

For **each** of the two extraction profiles (`mantissa8_v1`, `k14_scaled_modulo_v1`):

### 2.1 Individual lanes (population 2)
- Generate, for a fixed `(key, nonce)`, each of the 256 lanes' own output sub-sequence in isolation
  (i.e., read every 128th byte pair starting at that lane's offset within its stream — recoverable exactly
  from the round-robin formula derived in `phase_2_source_code_architecture_audit.md §4`:
  `lane_index = (i % 128) // 2`).
- Per-lane: byte frequency, Shannon entropy, Chi-square uniformity (with Bonferroni correction across the
  256 simultaneous per-lane tests), ACF up to lag 100.
- Sample size: propose the same `N=10^5` starting point as `burn_in_experiment_protocol.md §2`; a larger
  N (e.g. matching Step 1.1's 10^6) should be considered for a final/publication-grade run but is
  deferred pending a timing measurement (burn-in + output generation cost scales with N × 256 lanes).

### 2.2 Interleaved streams (population 3) — the actual bytes `a`, `b` consumed by diffusion, and the
actual bytes consumed by `build_sbox`/`build_permutation`
- Test each of the 4 streams' *actual emitted byte sequence* (what `cipher.py:41-42`
  (`streams["fwd"].take(n)`, `streams["bwd"].take(n)`) and `sampling.build_sbox`/`build_permutation`
  (`cipher.py:39-40`) actually consume) as one sequence each.
- Byte frequency, Shannon entropy, Chi-square uniformity, ACF up to lag 100, and — critically, because this
  population is new relative to Step 1.1 — **cross-correlation between consecutive bytes within a 128-byte
  round versus across round boundaries**, to test whether the round-robin interleaving itself introduces
  structure not present in a single lane's own trajectory.

### 2.3 Cross-stream comparisons (population 4)
- Pairwise comparison (MI with Miller-Madow bias correction + permutation/circular-shift nulls, exactly
  per Step 1.1's own methodology in `final_step1_1_closure_report.md §4`) between each pair of the 4
  streams' pooled output: `(sbox, perm)`, `(sbox, fwd)`, `(sbox, bwd)`, `(perm, fwd)`, `(perm, bwd)`,
  `(fwd, bwd)` — 6 pairs.
- Tests whether domain-separated-but-structurally-identical generator instances are statistically
  distinguishable from one another (relevant to whether an attacker observing one stream learns anything
  about another).

### 2.4 Across all 256 lanes globally (population 5)
- Repeated-seed / near-duplicate check: compute pairwise Hamming distance (or short-prefix equality) of
  each lane's first `M` output bytes (propose `M=256`) across all `256 choose 2 = 32,640` lane pairs, to
  empirically test the "could two lanes collide or produce correlated orbits" concern raised in
  `architecture_discrepancies.md §4` ("Limitation: ... if any two lanes collide or enter identical orbits
  (state merging), keystream repetition could occur"). This is a **direct empirical test of a previously
  only-theoretical concern**, not previously executed by either the Phase 1 audit or this Phase 2 audit.
- Cross-lane MI, as in `burn_in_experiment_protocol.md §3.6`, extended here to the full 256-lane population
  if the within-stream (64-lane) version in §2.2/§2.3 above shows no anomaly — propose running the full
  256-lane version only as a confirmatory follow-up, given its combinatorial cost.

### 2.5 NIST SP 800-22 where eligible
- Apply **exactly** Step 1.1's own multi-sequence protocol (`final_step1_1_closure_report.md` Correction F):
  `M` independently-labeled sequences (here, naturally, the 256 lanes or the 4 streams, rather than 100
  independently-seeded single orbits), each of length `nist_num_bits` (matching `configuration.json:32`,
  `100000` bits per sequence, i.e. 12,500 bytes), tested against the eligible NIST sub-tests only (per
  `configuration.json`'s own eligibility handling and `nist_results/nist_test_eligibility.csv`'s precedent),
  with pass-proportion-vs-lower-bound and p-value-uniformity reporting exactly as Step 1.1 did.
- **Note on sample-size eligibility:** NIST SP 800-22 sub-tests have minimum-length requirements per test
  (e.g. the Linear Complexity test needs very long sequences); if individual-lane sequences at the proposed
  `N=10^5` byte sample size are too short for certain sub-tests, those sub-tests must be marked ineligible
  for population 2.2 exactly as Step 1.1 already does for its own eligibility table, not silently skipped
  or silently assumed to pass.
- Multiple-sequence pass proportions and p-value uniformity must be evaluated against the same
  NIST-documented lower bound Step 1.1 used (`final_step1_1_closure_report.md` reports a 96.02% lower bound
  context for its own M=100 runs); the exact bound depends on the chosen `M` and must be recomputed if `M`
  (256 lanes, or 4 streams) differs from Step 1.1's `M=100`.

## 3. What the existing evaluation harness already covers vs. what is newly needed

`[VERIFIED SOURCE, from inspecting `isc_eval/`]`:

| Capability | Already in `isc_eval/`? | Evidence | Gap vs. this protocol |
|---|---|---|---|
| Comparative cipher-variant roundtrips/tamper tests (V-FULL/V-LINEAR/V-STREAM/V-PERM/V-CHACHA) | **Yes** | `isc_eval/constructions.py:4-9,25` (`VARIANTS` tuple), exercised by `tests/test_isc_eval_harness.py` (16 tests, independently re-run: **16 passed in 35.37s**, `[EXECUTED]`). | Not a statistical uniformity/ACF/MI test of the keystream itself — it is a cryptanalytic/structural test (position-coding, linear reduction, AEAD baseline comparison). Different purpose from this protocol. |
| NIST SP 800-22 on cipher streams | Partially — `isc_eval/exp_nist.py` exists (file present, not inspected line-by-line in this pass) | File listing confirms existence. | **Not verified in this pass whether `exp_nist.py` runs the multi-lane/multi-stream protocol of §2.1-2.5 above, or a different/simpler single-sequence test.** This is an explicit open item: `exp_nist.py` must be read in the next phase before deciding whether it can be reused or must be extended. `[UNVERIFIED — flagged, not assumed]` |
| Sensitivity/avalanche testing | Yes — `isc_eval/exp_sensitivity.py` (Attack A5, per Phase 1's `test_coverage_audit.md` item 9) | File present; Phase 1 describes it as testing key/nonce bit-flip avalanche in keystream/ciphertext bits — a different population (bit-flip propagation) from this protocol's distributional/independence focus. | Does not address Chi-square/entropy/ACF/MI on the *unperturbed* keystream — complementary, not overlapping. |
| Byte frequency / entropy / Chi-square / ACF / cross-correlation / MI on raw lane or stream output, specifically for the actual 256-lane generator | **Not confirmed present** | No file in `isc_eval/` or `isc_seq/` was found, in this pass, that is wired directly to `isc_cipher.generator.build_streams`'s actual output (as opposed to `isc_seq.isc_map`'s single-orbit research recurrence). `isc_seq/stats.py`, `isc_seq/nist.py` likely implement the underlying statistical primitives (Chi-square, entropy, etc.) used by Step 1.1, but Step 1.1's own script (`isc_sequence_characterization.py`) is a standalone script in `ISC_PBL`, not wired to `isc_cipher`. | **This is the main newly-needed implementation**: wiring `isc_seq/stats.py`'s (or `isc_sequence_characterization.py`'s) existing statistical primitives to `isc_cipher.generator.build_streams`'s actual per-lane/per-stream output, for both extraction profiles, per §2 above. |

**Honesty note:** `isc_eval/exp_nist.py`, `isc_seq/stats.py`, `isc_seq/nist.py`, and `isc_seq/periodicity.py`
were identified by file listing but **not read line-by-line in this investigation pass** due to scope/time
constraints within this Phase 2 effort — their exact capabilities relative to §2 above should be the first
task of whoever implements this protocol, rather than assumed from their filenames. `[EXPLICITLY FLAGGED AS
UNVERIFIED, per the task's instruction to state inaccessible/unchecked items rather than assume.]`

## 4. Statistical rigor requirements carried over from Step 1.1 (non-negotiable per the task)

- Miller-Madow bias correction for all MI estimates on finite samples (`final_step1_1_closure_report.md §4.1`
  formula, directly reusable: `Bias_MM = (R-1)(C-1) / (2 N ln 2)` for an R×C contingency table).
- Permutation-null (i.i.d. shuffle) and circular-time-shift surrogate nulls for every MI/correlation claim,
  not textbook asymptotic formulas alone.
- Bonferroni (or equivalent family-wise) correction whenever multiple simultaneous tests are run (256
  per-lane Chi-square tests, 100 ACF lags, 6 cross-stream MI pairs, etc.).
- Explicit distinction, in any eventual results document, between "did not reject uniformity/independence
  at this sample size" and "proved cryptographic unpredictability" — the latter is never established by
  any test in this protocol, matching the task's explicit instruction and Step 1.1's own established
  discipline (`final_step1_1_closure_report.md §4.3`: "does not establish that the underlying variables are
  strictly statistically independent").

## 5. Explicitly not done here

No test in §2 has been run. No statistical values are reported anywhere in this document. This is a
protocol specification for the next implementation phase.
