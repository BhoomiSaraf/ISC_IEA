# Phase 2 Closure Audit — The Four Previously Uninspected Files + Remaining Architecture Checks

**Document ID:** `ISC-PHASE2-CLOSURE-2026-02`
**Date:** 11 November 2026 (continuation session)
**Tagging convention (unchanged from the prior 8 documents):** `[VERIFIED SOURCE]` = read directly;
`[EXECUTED]` = command run, real output reported; `[PRIOR REPORT]` = stated in an earlier audit, not
re-derived here beyond what is marked `[EXECUTED]`; `[DERIVED]` = mathematical/logical consequence of
verified facts; `[RECOMMENDATION]` = design proposal; `[OPEN/UNVERIFIED]` = explicitly not established.

---

## 1. `isc_eval/exp_nist.py` (102 lines) — full line-by-line audit

`[VERIFIED SOURCE]`

**Purpose:** Implements Gate A experiment **A12**: runs the **official NIST STS 2.1.2** C test suite
(not a Python reimplementation) against the actual production generator `G_v1` (profile 1, HKDF seeds,
4 streams × 64 lanes, `T=1024`) — i.e., **this file is wired directly to `isc_cipher.generator.build_streams`,
not to the research-only `isc_seq.isc_map` single-orbit recurrence.** This directly contradicts the
tentative statement in the Phase 2 (session 1) document `multi_lane_statistical_validation_protocol.md §3`
("Not confirmed present... No file ... was found... wired directly to `isc_cipher.generator.build_streams`'s
actual output") — that statement is **corrected here**: such a file does exist, with the scope described below.

**Public entry points:**
- `message_streams(label)` (L32-36) — builds one message's 4 streams via `Derivation(key, nonce, context(1,
  1, 250, 500, 1)).seeds()` then `build_streams(seeds, backend="numpy", profile=1)`. Fixed `h=250, w=500, c=1`
  dims used purely to construct a valid HKDF context; unrelated to the sequence length actually drawn.
- `single_lane_sequences(label, lanes=64)` (L39-43) — takes the **`fwd` stream only**, draws
  `steps = SEQ_BYTES // 2` output steps via `.take()`, reshapes the raw buffer to `(steps, 64, 2)` (this
  reshape is only valid because `.take()`'s byte layout is exactly the round-robin interleaving derived in
  `phase_2_source_code_architecture_audit.md §4`: step-major, lane-minor, x-before-y — confirmed consistent
  here, independently, by this reshape actually working), then slices out `data[:, l, :]` per lane
  `l = 0..63` — i.e. this is the **exact mechanism to recover an individual lane's own sub-sequence (statistical
  population 2)** that `multi_lane_statistical_validation_protocol.md §2.1` proposed deriving from the
  round-robin formula; it already exists in working code, for the `fwd` stream only.
- `run_sts_batches(run, batches, log)` (L46-74) — for each named batch (a flat binary file of concatenated
  125,000-byte/1,000,000-bit sequences), invokes the **official NIST STS binary** `third_party/nist_sts/
  build_linux/assess` (not `nistrng`, not `isc_seq/nist.py`) via `isc_seq.sts_official.run_assess`, then
  cross-checks STS's own `finalAnalysisReport.txt` against an independent re-evaluation
  (`so.evaluate_workdir`) via `so.verify_against_report`. Runs up to 3 batches concurrently
  (`ThreadPoolExecutor(max_workers=3)`).
- `a12(mode)` (L77-102) — the actual experiment driver. `mode="full"` → `m=100` sequences per batch;
  anything else → `m=2` (a smoke-test mode). Generates **three batches**: (i) `fwd` stream of `m` messages
  (one 125,000-byte sequence per message — this is **population 3**, the interleaved stream, not a single
  lane), (ii) `perm` stream of `m` messages (same, population 3, different stream role), (iii)
  `single_lane_sequences` — `64` lane-sequences per call to `single_lane_sequences`, accumulated across
  however many distinct message labels are needed to reach `m` sequences (**population 2**, individual-lane,
  but from the `fwd` stream exclusively).

**Inputs/outputs/types:** All inputs are `label: str` (used to derive deterministic, public, non-secret
test keys/nonces via `isc_eval.common.public_key/public_nonce`, themselves HKDF-derived from a fixed public
salt — `common.py:13,16-19,22-24`, `[VERIFIED SOURCE]`). Outputs are raw binary files on disk (`run.path(...)`)
plus a JSON-serializable results dict (`{batch_name: {...}}`) returned by `run.finish(...)`.

**Statistical methods implemented directly in this file:** none — it is purely an **orchestration/generation
layer**; the actual NIST sub-tests run inside the external `assess` binary (official NIST STS 2.1.2 C
implementation), and the pass/fail "test_level" judgment is delegated to `experiments/analyze_official_sts.py`
(`an.test_level(...)`, L66 — **not inspected in this pass**, flagged as a further open item, consistent with
the task's instruction not to assume file contents from name alone).

**Dependencies and external tools — critical finding:**
`STS_BUILD = os.path.join(ROOT, "third_party", "nist_sts", "build_linux")` (L22), and `assess =
os.path.join(STS_BUILD, "assess")` (L49). `[EXECUTED]` I ran `file third_party/nist_sts/build_linux/assess`
on this machine: **`ELF 64-bit LSB pie executable, x86-64, ... for GNU/Linux 3.2.0, not stripped`.** This is
a **native Linux binary and cannot be executed directly on native Windows.** This resolves the open question
left in the prior session's `repository_migration_plan.md §4` ("relevance on the current Windows development
machine is unclear") — it is **not** dead weight; it is live tooling, but it **requires WSL or a Linux
environment to run**, consistent with `isc_cipher_kat/make_kat.py`'s own docstring reference to "built and
run in WSL Ubuntu." **`a12()` cannot be executed as-is on this native-Windows Python environment without
WSL.** `[EXECUTED, new finding this session]`

**Can it accept bytes from the production 256-lane generator?** Yes — it already does; that is its entire
purpose, unlike `isc_sequence_characterization.py` which only ever touched the single-orbit research
recurrence.

**Single orbit vs. multiple independent sequences:** Supports multiple independent sequences natively
(`m` messages/lanes per batch), using the project's own public-but-deterministic-seed convention
(`common.public_key/public_nonce`) for reproducibility — satisfies the "reproducible seeds and experiment
metadata" requirement via `Run`'s own manifest/environment recording (`common.environment()`, L37-40,
captures Python version, platform, and **SHA-256 of every `isc_cipher`/`isc_eval` source file** — a strong
reproducibility mechanism not previously documented in Phase 2 session 1).

**Appropriate for per-lane, per-stream, cross-stream testing?**
- **Per-lane (population 2):** Yes, but **`fwd` stream only** — `sbox`, `perm` (as individual lanes, as
  opposed to the whole interleaved `perm` stream which *is* covered), and `bwd` lanes are never isolated.
- **Per-stream (population 3):** Yes, but **`fwd` and `perm` only** — `sbox` and `bwd` streams' raw byte
  output are never tested by this file.
- **Cross-stream (population 4):** **No** — `a12()` never compares one stream's output against another's;
  each batch is tested independently by `assess`, which has no cross-batch comparison logic.
- **Across all 256 lanes globally / repeated-seed collision check (population 5):** **No** — not present
  here or, so far as inspected in this session, anywhere else in `isc_eval/` or `isc_seq/`.

**Statistical limitations / possible misinterpretations:** The file's own `a12()` return value says it
explicitly (L101-102): `"note": "statistical evaluation of G_v1 only; not evidence of security"` — the
project's own code already carries the correct epistemic caveat the task insists on. No overclaiming found
in this file.

**Missing capabilities for Phase 3B (this task's own required classification):**
1. No coverage of `sbox` or `bwd` streams (interleaved or per-lane).
2. No cross-stream MI/correlation testing (population 4 of `phase_2_source_code_architecture_audit.md §5`).
3. No full-256-lane collision/duplicate-orbit check (population 5).
4. Hardwired to `mantissa8_v1` only — `build_streams()` is called at L36 with no `extraction` parameter,
   so once a second extraction profile exists, this file will need a parameter threaded through
   `message_streams`/`single_lane_sequences`/`a12` to select it (a **small, additive change**, consistent
   with the dual-profile design's "additive branch" philosophy, not a rewrite).
5. Requires WSL/Linux to actually execute the official-STS part; this is an **environment dependency**, not
   a code gap, but it blocks running `a12()` as part of a native-Windows CI/regression pipeline without
   either a WSL step or falling back to the pure-Python `isc_seq/nist.py` subset.
6. No burn-in parameterization — `message_streams` calls `build_streams(seeds, backend="numpy", profile=1)`
   with the implicit default `burn_in=BURN_IN=1024` (confirmed by reading `generator.py:111`'s signature
   this session — `build_streams(seeds, backend="numpy", profile=1, burn_in=BURN_IN)` **already accepts a
   `burn_in` keyword argument today**, a positive finding: the burn-in experiment proposed in
   `burn_in_experiment_protocol.md` requires **zero new code** to vary `T` — it can call
   `build_streams(seeds, burn_in=5000)` today, as-is. This corrects an implicit assumption in the prior
   session's framing that implementing the burn-in experiment is a "Phase 3B" task; the *generator* already
   supports it, only the *driver script* (which does not yet exist) is missing.)

**Which functions can be reused unchanged?** `message_streams`, `single_lane_sequences`,
`run_sts_batches`, and the overall `a12()` structure can all be reused **unchanged** as the template for a
`sbox`/`bwd`-covering, both-extraction-profile-covering extension — none of their internals assume anything
`mantissa8_v1`-specific except the implicit default `extraction` (not yet a parameter at all, since it
doesn't exist yet) threaded through `build_streams`.

**Which require wrappers/new functionality?** A thin wrapper to (a) cover all 4 streams rather than 2, (b)
accept an `extraction` parameter once it exists, (c) add a cross-stream comparison stage, (d) add a
256-lane collision check, (e) provide a non-WSL-dependent fallback (using `isc_seq/nist.py`'s pure-Python
subset, §3 below) for environments without the Linux `assess` binary.

---

## 2. `isc_seq/stats.py` (89 lines) — full line-by-line audit

`[VERIFIED SOURCE]`

**Purpose:** Stated explicitly in its own module docstring (L1-4): "**descriptive checks**; NIST SP 800-22
testing lives in `nist.py`." This is a deliberate, self-documented separation of concerns — confirmed
correct by inspecting both files.

**Public functions:**
- `shannon_entropy(counts)` (L12-15) — generic Shannon entropy in bits from a histogram/count array; no
  assumption about the data's origin (bytes, bits, or any other categorical count).
- `acf(seq, max_lag=10)` (L18-23) — **biased** sample autocorrelation estimator (explicitly noted in its
  own docstring: "as in the legacy scripts"), operating on a generic real-valued 1-D array. **This differs
  from Step 1.1's own ACF methodology** (`final_step1_1_closure_report.md §5` used an unbiased/corrected
  estimator with explicit pointwise and Bonferroni bounds) — **a real, concrete incompatibility**: reusing
  `isc_seq.stats.acf` as-is for the multi-lane protocol would silently reintroduce the biased-estimator
  issue Step 1.1's own closure report specifically corrected (`final_step1_1_closure_report.md §5.1`,
  "Correction B"). `[DERIVED — new finding this session, not previously flagged]`
- `acf_band(n, z=1.96)` (L26-28) — the same `1.96/sqrt(n)` pointwise white-noise band Step 1.1 used; does
  **not** include a Bonferroni/family-wise correction factor (that was computed manually in Step 1.1's own
  report as `3.48/sqrt(N)` for 100 lags) — compatible as a *building block* but not a drop-in replacement for
  Step 1.1's full multiple-testing methodology.
- `raw_trajectory_stats(xs, ys, max_lag=10, bins=256)` (L31-52) — a single-call bundle of histogram, min/max,
  mean, sign fraction, lag-0 correlation, ACF (both coordinates), and 2-D joint entropy. **Operates on raw
  float `xs, ys` arrays, not on extracted bytes** — i.e., this function characterizes **continuous-state
  statistics** (relevant to the `architecture_discrepancies.md`-flagged continuous-state MI question), not
  the quantised byte statistics the k=14/mantissa8 comparison is actually about. Directly reusable for a
  continuous-state check of individual lanes' `(x,y)` trajectories, but not for byte-level uniformity.
- `entropy_vs_n(xs, ys, ns, bins=256)` (L55-65) — joint 2-D entropy computed at multiple sample sizes, to show
  finite-sample bias directly (empirically) rather than only analytically — complementary to, not a
  replacement for, the Miller-Madow analytical correction Step 1.1 used.
- `bit_stats(bits)` (L68-89) — the most directly reusable function for this task: takes a raw 0/1 bit array,
  computes **monobit frequency test** (`z`, two-sided `erfc` p-value — mathematically identical in form to
  `isc_seq/nist.py: frequency()`, see §3 below, a genuine duplication across the two files), bit-level lag-1
  correlation, and **byte-level Chi-square uniformity** (`scipy.stats.chi2.sf`) plus Shannon entropy of the
  resulting byte histogram. **This function is directly applicable, unmodified, to any extracted byte/bit
  stream regardless of its source (single orbit, one lane, one interleaved stream, or any population)** —
  it makes no assumption about the data's generating process beyond "a 0/1 array."

**Reusable unchanged:** `shannon_entropy`, `bit_stats`, `acf_band` (as a building block), `raw_trajectory_stats`
(for continuous-state checks only).
**Requires wrappers/extension:** `acf` — needs either a direct swap for Step 1.1's own unbiased estimator
(reused from `isc_sequence_characterization.py`, which is frozen and must not be edited, but **can be
imported from**, since importing a frozen file for reuse is not modifying it) or an explicit note that
`isc_seq.stats.acf`'s biased estimator is being knowingly used with a different interpretation than Step
1.1's corrected figures.
**Missing for Phase 3B:** No Chi-square *uniformity* test for a raw byte stream exists directly in this
file (`bit_stats` computes it only via the bit→byte-packing path, i.e., it needs a 0/1 bit array as input,
not a `uint8` byte array directly) — a trivial one-line wrapper (`np.unpackbits` the other way, or just call
`scipy.stats.chisquare` directly on a byte-histogram) would be needed for a byte-array-first interface
matching how `generator.py`'s `.take()` actually returns data (raw `uint8` bytes, not bits).

---

## 3. `isc_seq/nist.py` (325 lines) — full line-by-line audit

`[VERIFIED SOURCE]`

**Purpose:** A **from-scratch, pure-Python/NumPy/SciPy reimplementation** of a **subset** of NIST SP 800-22
Rev. 1a (explicitly enumerated in its own docstring, L3-12): Frequency (2.1), Block Frequency (2.2), Runs
(2.3), Longest Run (2.4), Binary Matrix Rank (2.5), DFT/Spectral (2.6), Maurer's Universal (2.9), Serial
(2.11), Approximate Entropy (2.12), Cumulative Sums fwd/bwd (2.13) — **10 of the 15 SP 800-22 sub-tests**.
Explicitly **not** implemented here (its own docstring, L10-12): non-overlapping/overlapping template
matching, Linear Complexity, Random Excursions (Variant) — the docstring explicitly says to "run the
official NIST STS on the saved bitstreams for those," which is exactly what `exp_nist.py`/`a12()` (§1 above)
does via the external `assess` binary. **These two files are a deliberately complementary pair**, not
redundant with each other: `nist.py` = fast, portable (no WSL needed), partial coverage; `exp_nist.py` +
official STS = complete coverage, Linux-only.

**Critical open question from the prior session, now resolved:** `multi_lane_statistical_validation_protocol.md
§2.5` proposed reusing Step 1.1's own protocol "exactly," citing `nistrng` version 1.2.3 as the package Step
1.1 used (per `final_step1_1_closure_report.md §3`'s environment table). **`isc_seq/nist.py` is a
*completely separate, independently-written* implementation from `nistrng`** — it is not a wrapper around
`nistrng` and does not import it (`[VERIFIED SOURCE]`: no `import nistrng` anywhere in this file). **This
means Step 1.1's NIST results and any future multi-lane NIST results computed via `isc_seq/nist.py` are
produced by two different pieces of test-implementation code**, even if both claim to implement the same
NIST SP 800-22 mathematical procedures. For an apples-to-apples comparison between Step 1.1's single-orbit
results and a future multi-lane result, this is a material methodological detail that must be disclosed
(and ideally cross-validated: running both `nistrng` and `isc_seq.nist` on the same sequence and confirming
matching p-values would be a cheap, high-value sanity check, **not performed in this pass** — flagged as a
recommended but unexecuted check).

**Multi-sequence protocol (L14-20, L292-325):** `proportion_range(m, alpha)` (L292-295) and `uniformity_p`
(L298-302) implement **exactly** the SP 800-22 §4.2 protocol Step 1.1 used (`p_hat ± 3·sqrt(p_hat(1-p_hat)/m)`
proportion bound; chi-square-over-10-bins p-value uniformity test, `gammaincc(9/2, chi2/2)`, with the same
`UNIFORMITY_MIN_SEQUENCES = 55` threshold Step 1.1's own report implicitly used (`final_step1_1_closure_report.md`
references an `M=100` run, which exceeds 55). `evaluate(pvalue_table, alpha)` (L305-325) is a **direct,
reusable, unchanged** multi-sequence evaluator: feed it `{test_name: [p for each of M sequences]}` and it
returns exactly the pass/fail-with-rationale structure needed for the multi-lane protocol's §2.5 requirement,
**already implemented, requiring no new code** for the evaluation/reporting layer — only the generation of
the `pvalue_table` input (running `run_battery` once per lane/stream/sequence) is new work.

**`run_battery(eps, ...)` (L271-289):** runs **all 10 implemented tests on one sequence**, returning
`{test_name: p_value}` — the single-sequence primitive the multi-sequence protocol needs called `M` times.

**Sample-size eligibility (relevant to this task's explicit warning not to silently skip or assume
eligibility):** Several tests have hard minimum-length requirements enforced by `raise ValueError` (e.g.
`longest_run` at L87: "needs n >= 128"; `binary_matrix_rank` at L142: "sequence too short"; `universal` at
L189: "needs n >= 387840 ... (or explicit L, Q)"). `run_battery` itself only conditionally includes
`Universal` (L283: `if n >= 387840`) but does **not** guard `longest_run` or `binary_matrix_rank` similarly
— calling `run_battery` on a sequence shorter than those tests' minimums will **raise an uncaught
`ValueError`**, not silently skip. **This is the opposite failure mode from "silently assumed to pass"
(which the task explicitly warns against) — it is a hard failure, which is arguably safer but means any
driver script built on top of `run_battery` for short per-lane sequences (e.g. the proposed `N=10^5` bytes
= 8×10^5 bits per lane) must itself catch/classify these `ValueError`s as "ineligible for this sequence
length," exactly as `nist_test_eligibility.csv` already does for Step 1.1's own single-orbit protocol.**
`[DERIVED — concrete implementation requirement for Phase 3B, newly identified this session]`

**Dependencies:** `numpy`, `scipy.special.{erfc,gammaincc}`, `scipy.stats.norm` — no NIST-STS binary, no WSL
requirement; pure Python/NumPy/SciPy, consistent with the project's existing environment
(`numpy==2.4.6`, `scipy==1.17.1`, confirmed `[EXECUTED]` this session via `python -c "import scipy;
print(scipy.__version__)"`).

**Accepts production generator bytes?** `_bits(eps)` (L33-36) accepts either a `str` of `'0'`/`'1'`
characters or any array-like of 0/1 values — **it does not accept raw `uint8` bytes directly**; a caller
must first `np.unpackbits(byte_array)` (as `isc_seq.stats.bit_stats` already does internally) before calling
any function in this file. **This is a 1-line adapter requirement, not a blocker.**

**Single orbit vs. multiple sequences:** The low-level test functions (`frequency`, `runs`, etc.) operate on
one sequence; the multi-sequence protocol (`evaluate`) operates on a list of p-values from multiple calls —
fully supports the multi-lane/multi-stream population structure this task requires, with no modification.

**Reusable unchanged:** `run_battery`, `evaluate`, `proportion_range`, `uniformity_p`, and every individual
test function — all are generic over the bit sequence's origin.
**Requires wrappers:** a byte→bit adapter at the call boundary (trivial, `np.unpackbits`); a per-sequence
eligibility guard wrapping `run_battery` to catch `ValueError` from under-length tests and record
"ineligible" rather than crash the whole batch.
**Missing for Phase 3B:** Linear Complexity, template matching, and Random Excursions (Variant) sub-tests —
by the file's own admission, these require the official STS (§1), which in turn requires WSL on this
machine.

---

## 4. `isc_seq/periodicity.py` (88 lines) — full line-by-line audit

`[VERIFIED SOURCE]`

**Purpose:** Explicitly **not** a statistical-uniformity tool. Per its own docstring (L1-9): computes the
**finite-precision eventual period** of the ISC map's orbit (pre-period `mu` and period `lambda`) using
**Brent's cycle-detection algorithm** (`brent(f, s0, max_steps)`, L38-67), because "any deterministic map on
a finite state space is eventually periodic." Also reproduces a **legacy, non-equivalent quantity**
(`floyd_meeting_index`, L70-83) that the historical `script/final_validation.py` computed using Floyd's
algorithm — explicitly documented as "a multiple of lambda, not lambda itself" (L8-9, L75) — i.e. this
function exists purely for **reconciling/explaining a historical artifact**, not as a new capability.

**`make_map(dtype, quant_bits, params, step)` (L17-35):** builds a closure `f(state) -> state` wrapping the
**research** `isc_step` from `isc_seq.isc_map` (imported at L14: `from .isc_map import FROZEN_PARAMS, isc_step`
— the research/single-orbit recurrence, **not** `isc_cipher.isc_step`), with optional `float32` precision and
optional fixed-point quantisation (`quant_bits`) applied **to the state itself** after every step — i.e. this
tool is designed to explore how **reduced-precision or quantised state representations** affect the orbit's
period, a different experimental axis entirely from byte-extraction-method comparison.

**Does it accept bytes from the production 256-lane generator?** **No** — it operates on `(x, y)` state
tuples from the research recurrence, has no byte-extraction step anywhere in the file, and is not wired to
`isc_cipher.generator` in any way (`[VERIFIED SOURCE]`: no import of `isc_cipher` anywhere in this file).

**Single orbit vs. multiple sequences:** Single orbit only, by construction (`brent(f, s0, ...)` takes one
initial state).

**Relevance to this task:** Indirect. It is relevant to the **"duplicate initial conditions"/"lane collision"**
question (`phase_2_source_code_architecture_audit.md §4`, `architecture_discrepancies.md §4`) only in the
sense that if the ISC map's finite-precision period were short relative to the cipher's output length, two
lanes landing on the same eventual cycle (even from different seeds) could in principle produce correlated
or repeating output — but **this file does not test that scenario directly** (it tests one orbit's own
period, not cross-lane collision), and **no periodicity analysis of the actual 256-lane, float64,
fdlibm-profile-1 generator has been performed anywhere found in this investigation.** This is a **gap**
worth flagging for Phase 3B's population-5 (cross-lane) analysis, though a low-priority one given that
`float64`'s state space (`2^106` distinct representable points per the state-mapping analysis in
`phase_2_source_code_architecture_audit.md §4`) makes short-period collisions astronomically unlikely absent
a design flaw — this is a `[DERIVED, qualitative]` argument, not a computed bound.

**Reusable unchanged:** `brent`, `floyd_meeting_index`, `make_map`, `as_state` — all generic over any
`(x,y)` step function, so in principle *could* be pointed at `isc_cipher.isc_step.step_ref` instead of
`isc_seq.isc_map.isc_step` with no modification (`make_map`'s `step` parameter already accepts an arbitrary
callable) — this would let periodicity analysis be run on the actual production recurrence rather than only
the research one, though this has **not been done or proposed as more than an observation** in this pass.
**Missing for Phase 3B:** No wiring to the 256-lane HKDF-seeded multi-lane architecture; no collision-
specific statistic (e.g., "do any two of the 256 lanes share a cycle within N steps") exists anywhere.

---

## 5. Remaining architecture checks (not covered by the four files above)

`[VERIFIED SOURCE]`, re-confirmed this session by direct reading (not merely re-cited from session 1):

- `generator.py:111`: `build_streams(seeds, backend="numpy", profile=1, burn_in=BURN_IN)` — **`burn_in` is
  already a first-class keyword parameter today.** This is a **correction/strengthening** of
  `burn_in_experiment_protocol.md`'s framing: the burn-in experiment requires **no generator code change**,
  only a new driver script that calls `build_streams(..., burn_in=T)` for `T` in `{1024, 2048, 5000, 10000}`
  and feeds the output to the statistical functions audited in §2-3 above.
- `isc_seq/extract.py:72-76` (`mantissa_byte`) and `isc_cipher/generator.py:25-26` (`m_byte`) are **two
  independent implementations of the same bit-extraction operation**, confirmed **mathematically identical
  by direct derivation in this session** (not merely re-asserted from session 1): bits 8-15 of a binary64
  word are always strictly within the 52-bit mantissa field (bits 0-51), for **any** finite value regardless
  of exponent/sign — because bit 15 < bit 52, masking the mantissa first (`mantissa_byte`'s approach) or not
  masking at all before slicing bits 8-15 (`m_byte`'s approach) cannot differ. This is a **positional fact
  about IEEE-754 bit layout**, not something that depends on the value being in `(-1, 1)` — a slightly
  stronger and more general claim than session 1's framing, which attributed the equivalence partly to the
  `(-1,1)` domain restriction.
- Neither `C:\Users\bhoom\Desktop\ISC_PBL` nor `C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis` has a
  `.git` directory. `[EXECUTED]` this session: `git status` in both locations returned `fatal: not a git
  repository (or any of the parent directories): .git` for both. **This resolves open question #5 from
  `phase_2_technical_decision_log.md §3`, previously flagged as unverified for the sibling repo — now
  confirmed for both.**
- `third_party/nist_sts/build_linux/` relevance (open question #4 from the same decision log): **resolved**
  — it is live tooling required by `isc_eval/exp_nist.py`'s `a12()`, but it is a native Linux ELF binary and
  cannot run on native Windows without WSL. Not dead weight; not Windows-executable either.
- `isc_cipher/selftest.py:39-43` (reference backend) / `L53-58` (numpy backend): re-confirmed by direct
  reading this session that `run_selftest` stops at comparing `(x, y)` trajectory values to `TRAJ["x"],
  TRAJ["y"]` and **never calls `m_byte` or any byte-extraction function** — confirms
  `dual_profile_generator_design.md §6.2`'s claim exactly as stated.
- `isc_cipher_kat/make_kat.py:14`: **"Refuses to overwrite existing vectors"** — confirmed by direct reading
  of the module docstring; this is a built-in safety property of the existing tooling relevant to Task
  G/H's "do not overwrite existing KAT vectors" constraint — the tool itself already enforces this, not just
  this task's self-imposed discipline.
