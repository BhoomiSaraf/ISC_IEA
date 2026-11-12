# Gate A diagnostic run: results, harness defects and calibration (2026-10-26)

* **Scope:** small diagnostic checks of the 17 Gate A harnesses only (`isc_eval/`).
* **Not run:** the full Gate A batch.
* **Machine:** Windows 11, Intel Core i5-10210U (4 cores / 8 threads), **7.8 GB RAM (about 0.8 GB free
  during the run)**, CPython 3.11.9, NumPy 2.0.2; WSL Ubuntu 24.04 for E2 and the STS.
* **Outputs:** `results/encryption_experiments/*_diagnostic_*` (21 directories, all kept; see §4).
* **Harness unit tests:** `tests/test_isc_eval_harness.py`, 16/16 PASS (twice: before and after the
  fixes).

Diagnostic results come from deliberately tiny inputs and are **not** experimental findings, with one
exception that is reported prominently (§1).

## 1. A pre-registered criterion fired: A6(c), 1-ulp neighbour divergence (needs your decision)

**Diagnostic observation (100 pairs per coordinate).** 34 of 100 (x+1 ulp) pairs and 27 of 100
(y+1 ulp) pairs did not separate within T = 1024 steps. The other pairs separated after 10-16 steps.
Under the pre-registered A6 rule, "divergence after step T" is a finding.

**Follow-up check** (20,000 random grid states per coordinate, one ISC step, profile 1):
* **33.7% (x) and 33.0% (y) of 1-ulp neighbour pairs became bit-identical after a single step**, and
  therefore identical forever after. None of these separated later.
* Of the pairs that did not merge, 99.5% separated within 60 steps.
* The merge rate depends on |coordinate|: about 70% for |v| < 0.25, about 35% for 0.25-0.5, and about
  14% for 0.5-1.

**Meaning.**
* The mapping from 16-byte seeds to initial states is exactly uniform (Lemma 2, unchanged). But
  **distinct initial states can yield identical lane sequences**: the first ISC step is many-to-one at
  binary64 resolution.
* The effective number of distinct lanes is therefore below 2^106, by an amount **not yet measured**.
* `algorithm_design.md` §5.4 item 2 listed merging as [OPEN]; this is the first evidence that it occurs,
  and at a substantial rate for neighbouring states.

**Hypothesis (not traced).** x enters the next state through X = 1 + a·(x·cos t − y·sin t). A 1-ulp
change in a small |x| falls below the rounding resolution of X (about 2^-52·|X|), so X, and with it
the next state, is unchanged.

**What is not implied.**
* Two lanes of real messages merge only if their HKDF-derived initial states are close enough to merge.
  For independent uniform seeds that probability is not yet measured, but it is expected to be tiny.
* The finding concerns the size of the effective state space, which affects the generic brute-force
  bound. It is not an attack.

**Options (your decision; no change has been made):**
* **(R) recommended:** run the full A6 unchanged on v1, plus a new, clearly labelled **post-hoc**
  sub-experiment **A6(e)** that quantifies the effect:
  * the merge rate for neighbours at distance 1, 2, 4, …, 2^20 ulp;
  * the number of distinct one-step images of blocks of 2^10 consecutive grid values (local
    compression factor), from which an effective-entropy estimate per lane follows.

  Under the pre-registered stop rule this is the "analyse the cause" step. Any redesign (v2) would come
  only after it.
* **(S)** stop Gate A now and design a v2 initial-state mapping before measuring anything else. Not
  recommended: without A6(e) there is no evidence that would guide the redesign.

## 2. Harness defects found by the diagnostic run (all fixed; harness tests re-run, 16/16 PASS)

| # | experiment | defect | effect in the diagnostic run | fix |
|---|---|---|---|---|
| 1 | A2 | a "swap KCV between ciphertexts" case for V-CHACHA produced a **byte-identical** ciphertext (V-CHACHA's KCV field is all zeros in every ciphertext), which was counted as an accepted forgery | reported "1 accepted" for V-CHACHA. **Not a forgery:** the unmodified ciphertext was accepted, as it should be | unchanged byte strings are now skipped and counted as `noop_unchanged_skipped`. Re-run: 0 of 2,953 genuine modifications accepted |
| 2 | A11(i), A11(ii) | in WSL, `python3 -I -m isc_eval.xplat_worker` cannot import the package, because `-I` drops the working directory from `sys.path` | both runs crashed (directories kept, without summary) | the worker is run as a script path. Re-run: both complete |
| 3 | A14 | timing was measured while `tracemalloc` was active | V-FULL 64×64 encryption measured **20.7 s instead of about 1.7 s** (about 12× distortion of Python-heavy code, which would unfairly penalise ISC) | timing repetitions are untraced; one extra traced repetition measures peak memory only. Re-run: V-FULL 1.66 s enc / 1.52 s dec |

## 3. Diagnostic results (tiny inputs; for harness validation only)

| id | diagnostic outcome | seconds |
|---|---|---|
| A10 | the public API has no nonce parameter | 6 |
| A2 | after fix: V-FULL 0/1,477 and V-CHACHA 0/1,476 accepted | 18 |
| A13 | 2,000 random or mutated inputs: 1,795 `Malformed`, 205 `AuthenticationError`, no other exception, no generator call | 5 |
| A1 | expected pre-registered breaks reproduced under nonce reuse: V-STREAM (1 query), V-PERM (2), V-LINEAR (3), AES-GCM (1), ChaCha20-Poly1305 (1) give F4/F5. GCM-SIV: only F1. V-FULL and V-CHACHA: F1 only; the transfer attempt gave F3-F5 negative; the exploratory n = 1 codebook recovers everything (256 queries) | 19 |
| A8 | V-FULL fixed nonce: π not recovered (0.0 correct; chance 2.4e-4) | 5 |
| A9 | nonce-respecting: no equal bodies; no transfer (agreement 0.0028-0.0046, threshold about 0.0056) | 108 |
| A5 | 4 flips: Hamming fractions 0.4948-0.5061, inside the intervals | 35 |
| A3 | 1 image × 1 key × 5 positions × 3 variants: 0 NPCR/UACI failures | 10 |
| A11(i) | 2 + 2 images E1 ↔ E2: 0 failures | 31 |
| A11(ii) **proxy** | host `math` sin/cos differ for **4,853 of 100,063** arguments between E1 (MSVC CRT) and E2 (glibc); trajectories using host `math` diverge after **1-24 steps**. A host-library proxy: it does not test NumPy profile 2 | 17 |
| A11(iii) | 5 trials: 2 identical states, 3 detected by KCV, 0 wrong releases | 26 |
| A6 | (a) no cycles (64 lanes, 3,000 steps); (b) 0 duplicates; **(c) finding, see §1**; (d) 0 dependence rejections | 48 |
| A4 (EX) | k = 8: state recovered from the outputs and predicts the rest (71,639 evaluations, 0.2 s) | 4 |
| A15 | method valid (ChaCha20 control z = 1.60, no LC flag) and sensitive (arccos8 control z = 11.6); ISC lanes max z 1.18-2.42 (threshold 3.54) | 50 |
| A14 | after fix: 64×64 gray, V-FULL 1.66 / 1.52 s, V-CHACHA 0.18 / 0.01 s, AEADs ≤ 15 ms (first AES-GCM call includes setup) | 57 |
| A7 | 2 small images and 2 STS sequences per construction: all runs complete, no STS problems | 71 |
| A12 | 2 sequences per batch: all 3 STS batches complete, 0 parse problems, 0 report mismatches | 223 |

## 4. Run directories

* Superseded by fixes (kept unchanged, not used): `A2_tamper_diagnostic_20261026T003641Z`,
  `A14_perf_diagnostic_20261026T004231Z`.
* Crashed (kept, no summary): `A11_xplat_diagnostic_20261026T003958Z`,
  `A11_hostlibm_proxy_diagnostic_20261026T004014Z`.
* All other diagnostic directories are complete, with a manifest.
