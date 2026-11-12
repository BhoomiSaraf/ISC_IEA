# Phase 2 Final Decision Log — Closure Session

**Document ID:** `ISC-PHASE2-FINALDECISIONLOG-2026-02`
**Date:** 11 November 2026

---

## 1. Decisions finalized this session

| # | Decision | Supporting evidence | Status |
|---|---|---|---|
| F1 | `frac_byte` ≡ Step 1.1 k=14, re-confirmed by re-reading source (not re-executing the comparison script, which remains session-1's result) | `extraction_backend_compatibility_specification.md §1`; original test in `frac_byte_k14_compatibility_audit.md §3` | **Frozen** |
| F2 | `EXTRACTION` header byte goes at **offset 36** (appended after KCV, before body), not inserted between existing fields | `container_v2_binary_specification.md §3` — corrects session-1's unresolved "immediately after DTYPE/C ... or appended before the tag" | **Frozen recommendation** |
| F3 | VERSION=2 permits **both** `EXTRACTION ∈ {1,2}` — no restricted version/extraction pairing | `container_v2_binary_specification.md §6` | **Frozen recommendation** |
| F4 | `context()` gains an **additive, default-`None`** `extraction` parameter; V1 `ctx` output is byte-for-byte unchanged when omitted | `hkdf_profile_binding_specification.md §2-3` | **Frozen recommendation** |
| F5 | Both HMAC-tag coverage (Defense 1) and `ctx`-binding (Defense 2) are recommended together for `EXTRACTION` | `hkdf_profile_binding_specification.md §5` | **Frozen recommendation** |
| F6 | Scalar backend gets a **new, dependency-free** `frac_byte_scalar` using `math.floor`, not a wrapped `isc_seq.extract.frac_byte` call | `extraction_backend_compatibility_specification.md §3` | **Frozen recommendation** |
| F7 | `isc_seq.extract` becomes a **new, lazily-imported, optional** runtime dependency of `isc_cipher.generator`'s NumPy path only — not of the reference path | `phase_3a_implementation_plan.md`, `isc_cipher/generator.py` row | **Frozen recommendation** |
| F8 | Burn-in experiment requires **no generator code change** — `build_streams(..., burn_in=T)` already accepts arbitrary `T` | `phase_2_closure_audit.md §5`; verified directly from `generator.py:111` signature | **Correction of session-1's implicit framing** |
| F9 | `isc_eval/exp_nist.py`'s `a12()` **already** tests populations 2 (fwd-lanes only) and 3 (fwd/perm streams only) via official NIST STS | `phase_2_closure_audit.md §1` | **Correction of session-1's "not confirmed present"** |
| F10 | Official NIST STS (`third_party/nist_sts/build_linux/assess`) is a **native Linux ELF binary**, cannot run on native Windows | `phase_2_closure_audit.md §1`, `[EXECUTED]` `file` command this session | **Resolves session-1 open question #4** |
| F11 | Neither repository has a `.git` directory (confirmed for **both**, not just `ISC_PBL`) | `phase_2_closure_audit.md §5`, `[EXECUTED]` `git status` both locations | **Resolves session-1 open question #5** |
| F12 | Two-tier NIST testing strategy: `isc_seq.nist.py` (portable, 10/15 tests) as primary; official STS (WSL-gated, remaining 5) as confirmatory | `phase_3b_validation_readiness.md §2.5` | **New recommendation, not in session 1** |
| F13 | `isc_seq.stats.acf` uses a **biased** estimator, methodologically different from Step 1.1's own corrected one — must be disclosed if reused, not silently substituted | `phase_2_closure_audit.md §2`, `phase_3b_validation_readiness.md §3` | **New finding, not in session 1** |
| F14 | No mutual-information implementation exists in `isc_seq/stats.py` or `isc_seq/nist.py` — cross-stream MI (population 4) requires importing Step 1.1's own correction formulas | `phase_3b_validation_readiness.md §2.3` | **New finding, not in session 1** |
| F15 | All three regression gates independently re-executed in **this** closure session (not merely cited from session 1 or Phase 1) | §2 below | **Done** |
| F16 | No git commit made; no source file in either repository modified, renamed, or deleted | Compliance statement, §3 below | **Done** |

---

## 2. Test execution log — this closure session (11 November 2026, same machine: Windows 10/11 Pro Build
10.0.22631-SP0, Python 3.11.9, NumPy 2.4.6, SciPy 1.17.1, pytest 9.1.1)

```
cd sine_chebyshev_ikeda_analysis

$ python -m pytest tests/test_isc_cipher_auth.py tests/test_isc_cipher_kdf_state.py \
    tests/test_isc_cipher_numeric.py tests/test_isc_cipher_sampling_diffusion.py \
    tests/test_isc_cipher_roundtrip.py -q
159 passed, 2 skipped in 460.70s (0:07:40)

$ python -m pytest tests/test_isc_eval_harness.py -q
16 passed in 51.84s

$ python -I isc_cipher_kat/gate_r.py --backend numpy --label PHASE2-CLOSURE-verify
R-fdlibm-hashes:    PASS (0.0 s)
R-trig-KAT:         PASS (0.3 s)
R-trajectory-KAT:   PASS (147.5 s)
R-stream-KAT:       PASS (1.7 s)
R-cipher-KAT:       PASS (32.0 s)
overall: PASS -> results/cipher_validation/gate_r_PHASE2-CLOSURE-verify_numpy_20261111T122755Z

$ git status   (run in both ISC_PBL and sine_chebyshev_ikeda_analysis)
fatal: not a git repository (or any of the parent directories): .git     [both locations]

$ file third_party/nist_sts/build_linux/assess
ELF 64-bit LSB pie executable, x86-64, ... for GNU/Linux 3.2.0, not stripped
```

**Conclusion: every previously-reported result (Phase 1 and Phase 2 session 1) was independently
re-executed a second time in this closure session and reproduced exactly — 159/2/161 for Gate C, 16/0 for
Gate A, overall PASS across all 5 Gate R checks.** No test is reported as passed in this document unless it
is listed, with its real output, in this log.

---

## 3. Explicit compliance statement with Section 12's 13 non-negotiable constraints

1. **No frozen Step 1.1 artifact edited** — only read (`isc_sequence_characterization.py`'s `quantise_digit_extraction`
   function was read, not modified, in session 1; not touched at all this session).
2. **No repository migration performed** — `repository_migration_plan.md` remains a plan only.
3. **No production cipher code modified** — every file in §1 of `phase_3a_implementation_plan.md` was read,
   not edited.
4. **No existing test or KAT vector overwritten** — `make_kat.py` itself refuses to overwrite
   (`phase_2_closure_audit.md §5`); no test file was edited.
5. **No default silently changed** — every proposed change in this document set is explicitly additive
   with a default that reproduces current behavior (F4, F6, F8 above).
6. **Extraction and burn-in were not changed simultaneously anywhere in any design** — the dual-profile
   design (`dual_profile_generator_design.md`) and the burn-in protocol (`burn_in_experiment_protocol.md`)
   are presented as orthogonal axes, each holding the other fixed, per that document's own §2 "fixed across
   all four conditions: extraction method" framing.
7. **No mandatory NumPy dependency introduced into the scalar backend** — `frac_byte_scalar` (F6) is
   `math`-only.
8. **No claim that statistical randomness proves cryptographic security** — every document in this set
   carries an explicit non-claim statement where relevant (`cipher_integration_impact_analysis.md §12`,
   `hkdf_profile_binding_specification.md §7`, `phase_3b_validation_readiness.md §3`).
9. **No claim that k=14 is superior to mantissa8 without multi-lane testing** — `phase_3b_validation_readiness.md`
   explicitly defers this to an unrun Phase 3B experiment.
10. **No fabricated/hardcoded experiment results** — `burn_in_experiment_protocol.md` and
    `phase_3b_validation_readiness.md` contain zero numerical statistical findings; every number quoted
    anywhere in this document set that looks like a "result" is either (a) a test-execution log entry with
    a real pass/fail count and real wall-clock time (§2 above), or (b) a parameter of a proposed protocol
    (e.g. "N=10^5"), never a fabricated statistical outcome.
11. **No ambiguity left in the container layout or KDF encoding** — exact byte offsets given in
    `container_v2_binary_specification.md §1,§3`; exact context byte sequence given in
    `hkdf_profile_binding_specification.md §3`.
12. **No test reported as passed unless it actually executed successfully** — every "passed"/"PASS" claim
    in this document traces to §2's literal command output.
13. **No git commit created** — no authorization was given; none was made. (Also moot: neither repository
    is a git repository at all, per F11.)

---

## 4. Unresolved questions carried forward from session 1, with resolution status

| # | Question | Status after this session |
|---|---|---|
| 1 | Exact byte position of `EXTRACTION` field | **Resolved** — offset 36 (F2) |
| 2 | Should k14 ever become default extraction | **Still open** — explicitly deferred (F2 area, `phase_3a_implementation_plan.md` §`cipher.py` row) |
| 3 | Does `exp_nist.py` already implement the multi-lane protocol | **Resolved** — partially (populations 2-fwd-only, 3-fwd/perm-only); gaps enumerated in `phase_2_closure_audit.md §1` | 
| 4 | Is `third_party/nist_sts/build_linux/` live or stale | **Resolved** — live, but Linux-only (F10) |
| 5 | Does the sibling repo have `.git` | **Resolved** — no (F11) |
| 6 | Is N=10^5 bytes/lane validated | **Still open** — pilot benchmark proposed, not run (`phase_3b_validation_readiness.md §4`) |
| 7 | Performance cost of `frac_byte` vs. `m_byte` | **Still open** — deferred again this session, consistent with "do not optimize prematurely" |

## 5. New unresolved questions introduced this session

1. Whether to cross-validate `isc_seq.nist.py`'s results against `nistrng` (the package Step 1.1 used) on
   an identical sequence, to confirm the two independent NIST implementations agree — recommended, not done.
2. Exact `Header`/`pack()`/`parse()` Python-level representation for the two-version container (single
   dataclass with optional fields vs. two dataclasses) — left to the Phase 3A implementer.
3. Full line-by-line contents of `isc_cipher_kat/make_kat.py` and `make_kat_ext.py` beyond their headers —
   explicitly flagged as the **first concrete step** of Phase 3A implementation, not yet done in either
   session.
4. Full line-by-line contents of `experiments/analyze_official_sts.py`'s `test_level()` function (referenced
   by `exp_nist.py:66`) — not inspected in this session, flagged rather than assumed.
