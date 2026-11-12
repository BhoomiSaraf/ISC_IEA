# Phase 3B Validation Readiness — Executable Experimental Specification

**Document ID:** `ISC-PHASE3B-READINESS-2026-02`
**Date:** 11 November 2026
**Status:** Specification only. **No Phase 3B experiment is run in this document.** This document
supersedes/extends `multi_lane_statistical_validation_protocol.md` and `burn_in_experiment_protocol.md`
from the prior session with the concrete file-level findings from `phase_2_closure_audit.md` §1-4.

---

## 1. What changed since the prior session's protocol documents

`[CORRECTIONS, grounded in this session's file-by-file reading of `isc_eval/exp_nist.py`, `isc_seq/stats.py`,
`isc_seq/nist.py`, `isc_seq/periodicity.py`]`:

1. **`isc_eval/exp_nist.py`'s `a12()` already tests populations 2 (fwd-stream lanes only) and 3 (fwd, perm
   streams) via the official NIST STS** — this was marked "not confirmed present" in the prior session;
   it is now confirmed present, with precisely bounded scope (§1 below).
2. **The burn-in axis requires zero new generator code** — `build_streams(..., burn_in=T)` already accepts
   any `T`; only a new driver script is needed. This was implicitly treated as blocked-on-implementation in
   the prior session; it is not.
3. **Two independent NIST SP 800-22 implementations exist in the codebase** (`isc_seq/nist.py`'s
   from-scratch reimplementation vs. the `nistrng` package Step 1.1 used vs. the official NIST STS C binary
   `exp_nist.py` drives) — any Phase 3B results must state **which** implementation produced them, since
   they are not guaranteed to agree to the last digit (cross-validation is recommended but not yet done).
4. **The official-STS path requires WSL/Linux** — `third_party/nist_sts/build_linux/assess` is a native
   Linux ELF binary, confirmed un-runnable on native Windows in this session.

---

## 2. Executable experimental specification, by population

For **each** of the two extraction profiles (`mantissa8_v1` now implementable via existing code;
`k14_scaled_modulo_v1` pending Phase 3A implementation), and using a **fixed, recorded `(key, nonce)`**
pair for reproducibility (per `burn_in_experiment_protocol.md §2`'s already-established discipline):

### 2.1 Individual lanes (population 2)

- **Generation mechanism (already exists, confirmed working):** `isc_eval.exp_nist.single_lane_sequences`
  (`exp_nist.py:39-43`) — currently hardwired to the `fwd` stream; **extend** (new code, small) to accept a
  `stream` parameter so `sbox`, `perm`, `bwd` lanes can be isolated too, using the identical reshape logic
  (`data = np.frombuffer(st.take(steps * BYTES_PER_STEP), np.uint8).reshape(steps, 64, 2)`).
- **Tests:** `isc_seq.stats.bit_stats` (byte-level Chi-square + Shannon entropy, reused unchanged, per
  `phase_2_closure_audit.md §2`) on each lane's own byte sequence; `isc_seq.stats.acf`/`acf_band` for a
  descriptive autocorrelation check (with the caveat, newly identified this session, that `isc_seq.stats.acf`
  uses a **biased estimator** different from Step 1.1's own corrected one — see §4); `isc_seq.nist.run_battery`
  + `evaluate` (reused unchanged) for the 10-test pure-Python NIST subset, bit-unpacked first.
- **Sample size:** `N = 10^5` bytes/lane (`burn_in_experiment_protocol.md §2`'s proposal, carried forward,
  still unvalidated/un-tuned).
- **NIST eligibility:** at `N=10^5` bytes = `8×10^5` bits, `Universal` (needs ≥387,840 bits) **is** eligible;
  `binary_matrix_rank` and `longest_run` have lower minimums (128, 6272, or 750000 bits depending on table
  row per `isc_seq/nist.py:64-69`) and are also eligible. **No sub-test is expected to be ineligible at this
  sample size** — a positive finding not previously established (`multi_lane_statistical_validation_protocol.md
  §2.5` flagged eligibility as an open concern without checking the actual thresholds against the proposed
  `N`; this session's direct reading of `nist.py`'s threshold table resolves it).

### 2.2 Interleaved streams (population 3)

- **Generation mechanism (partially exists):** `isc_eval.exp_nist.message_streams` + `.take()` already
  produces the actual `fwd`/`perm` stream bytes; **extend** to also capture `sbox`'s raw byte stream (not
  just its post-`build_sbox` permutation) and `bwd`'s raw byte stream — currently, `cipher.py` only ever
  consumes `sbox`/`perm` through `sampling.build_sbox`/`build_permutation`, never their raw bytes directly,
  so a **new, explicit raw-byte extraction call** (`streams["sbox"].take(n)`, bypassing `build_sbox`) is
  needed purely for statistical testing purposes — this does not exist in any file read in either session.
- **Tests:** identical battery to §2.1, applied to the full interleaved sequence instead of one lane's
  sub-sequence; **additionally**, a new cross-correlation check (within-128-byte-round vs. across-round-
  boundary) as proposed in `multi_lane_statistical_validation_protocol.md §2.2` — **no existing code
  implements this specific check**; it is new work, straightforward (a `numpy` reshape-and-correlate), not
  yet written.

### 2.3 Cross-stream comparisons (population 4)

- **Generation mechanism:** none exists (confirmed, `phase_2_closure_audit.md §1` table). New work: capture
  all 4 streams' raw byte output for the same message, then apply Miller-Madow-corrected MI with
  permutation/circular-shift nulls — **this requires importing the actual correction formulas from
  `isc_sequence_characterization.py`** (frozen, but importable, per
  `extraction_backend_compatibility_specification.md §1`'s reasoning that reading/importing a frozen file
  is not modifying it), since no equivalent MI-correction code was found in `isc_seq/stats.py` or
  `isc_seq/nist.py` (both confirmed, by direct reading, to **not** implement mutual information at all —
  `shannon_entropy` computes entropy, not MI; this is a **genuine capability gap**, not previously stated
  this precisely).

### 2.4 Across all 256 lanes globally (population 5)

- **Generation mechanism:** none exists. `isc_seq/periodicity.py`'s Brent's-algorithm tools are **not**
  wired to the 256-lane architecture (confirmed, `phase_2_closure_audit.md §4`) and address a different
  question (single-orbit eventual period, not cross-lane collision). The collision check proposed in
  `multi_lane_statistical_validation_protocol.md §2.4` (pairwise Hamming distance / prefix equality across
  `256 choose 2 = 32,640` pairs) remains **entirely unimplemented new work**.

### 2.5 NIST SP 800-22 — reconciled recommendation

`[CORRECTED RECOMMENDATION]`: use **`isc_seq.nist.py`'s pure-Python 10-test subset** (`run_battery` +
`evaluate`) as the **primary, portable** tool for populations 2-5 above (no WSL dependency, runs natively
on this Windows machine, already includes the exact multi-sequence protocol machinery Step 1.1 used
conceptually). **Reserve the official NIST STS (`exp_nist.py`/`a12`, via WSL)** for a **final, confirmatory,
publication-grade** run covering the additional 5 sub-tests (template matching, linear complexity, random
excursions variant) that `isc_seq/nist.py` does not implement — this is a **two-tier testing strategy**, not
previously articulated this explicitly, that uses each tool for what it is actually good at rather than
treating them as interchangeable.

---

## 3. Statistical rigor requirements (carried forward, re-confirmed as still binding)

Unchanged from `multi_lane_statistical_validation_protocol.md §4`: Miller-Madow bias correction for all MI
estimates; permutation-null and circular-shift surrogate nulls, not asymptotic formulas alone; Bonferroni
(or equivalent) correction for every multiple-simultaneous-test scenario (256 per-lane tests, 100 ACF lags,
6 cross-stream MI pairs); explicit distinction between "did not reject uniformity/independence at this
sample size" and "proved cryptographic unpredictability" (the task's and Step 1.1's own non-negotiable
discipline).

**New, session-2-specific addition:** when reporting any ACF result computed via `isc_seq.stats.acf`,
**explicitly disclose that this is the biased estimator**, distinct from Step 1.1's own corrected one, OR
substitute Step 1.1's corrected estimator (importable from the frozen `isc_sequence_characterization.py`)
for consistency — **this must be a conscious, disclosed choice**, not an accidental silent substitution of
methodology, since the two could in principle produce numerically different ACF values for the same data.

---

## 4. Feasibility of the proposed 100,000 bytes/lane — still unverified, pilot benchmark proposed

`[CARRIED FORWARD, per task's explicit instruction not to run the full experiment here]`: No timing
measurement was taken in this session for 256-lane output generation at `N=10^5` bytes/lane (that would
require implementing at least the `k14` extraction branch first, or running the `mantissa8_v1` path at this
scale, which was not done in this closure session since it is out of this task's scope — Task F explicitly
says "evaluate whether ... is computationally feasible... mark the estimate as unverified and propose a
pilot benchmark," not "run it"). **Proposed pilot benchmark (for the first Phase 3B implementation step,
not performed here):** time `build_streams(seeds, backend="numpy", profile=1).take(100_000)` for all 4
streams, on this machine, once, before committing to `N=10^5` as the final sample size for the full
multi-lane/multi-profile/multi-burn-in matrix (which would otherwise multiply this cost by `2 extraction
profiles × 4 burn-in values × (256 lanes + 4 streams + 6 cross-stream pairs + 1 global collision check)` —
a combinatorial cost that **must** be bounded by an actual timing number before committing to running the
full matrix, not estimated from the recurrence's known per-step cost alone).

---

## 5. Explicitly not done here

No statistical test in §2 was run. No p-value, Chi-square statistic, entropy value, ACF value, or MI
estimate for the actual multi-lane generator's output appears anywhere in this document, consistent with
the task's explicit instruction ("Do not run the full Phase 3B experiment in this closure task") and with
`burn_in_experiment_protocol.md §5`'s and `multi_lane_statistical_validation_protocol.md §5`'s identical
prior commitments, both still honored.
