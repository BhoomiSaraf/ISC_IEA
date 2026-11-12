# Phase 2 Technical Decision Log

**Document ID:** `ISC-PHASE2-DECISIONLOG-2026-01`
**Date:** 11 November 2026
**Purpose:** Record every design decision, alternative considered, rationale, unresolved question, and
recommendation made during this Phase 2 investigation, plus the final test execution log.

---

## 1. Decisions and rationale

| # | Decision | Alternative(s) considered | Rationale | Status |
|---|---|---|---|---|
| D1 | Re-verify all Phase 1 claims against actual source code and actual test execution rather than citing Phase 1 reports as authoritative | Trust Phase 1 reports as-is | Task Section 13/§2 explicitly forbids treating prior audits as a substitute for source inspection | Done — see `phase_2_source_code_architecture_audit.md` |
| D2 | Treat `frac_byte` (`isc_seq/extract.py:60-61`) as the candidate k=14 implementation, verified by direct execution rather than by name/docstring alone | Assume equivalence from the function's name/docstring | Task explicitly warns "Do not assume this merely because of its name" | Done — bit-exact match confirmed on 13 edge cases + 2,000 real trajectory samples, see `frac_byte_k14_compatibility_audit.md §3` |
| D3 | Recommend injecting the new extraction as an **additive, isolated branch** at the two existing `m_byte`/bit-trick call sites (`generator.py:52-53`, `97-98`), rather than restructuring `generator.py` | Rewrite `generator.py` to be extraction-agnostic via a plugin architecture from the start | Task explicitly asks to "minimize changes" and identify only components that "genuinely need modification"; the existing two call sites are already the sole extraction boundary, confirmed by repo-wide search finding no other extraction call site | Recommended, not implemented |
| D4 | Recommend a **new, orthogonal `EXTRACTION` header field** rather than overloading the existing `PROFILE` field | Reinterpret `PROFILE` values 3/4 as "fdlibm + k14" combinations | `PROFILE` is already documented (`algorithm_design.md:468`) and used (`container.py:24`) to mean "arithmetic engine" specifically; conflating two independent axes into one enum would make a future third extraction method or third arithmetic profile impossible to express cleanly, and risks exactly the "silently reinterpreting existing profile identifiers" the task forbids | Recommended, not implemented |
| D5 | Recommend gating the new header field behind a `VERSION` bump (1→2) rather than changing the meaning of `VERSION=1` ciphertexts | Keep `VERSION=1` and add the field unconditionally (breaking existing 36-byte-header parsing) | Preserves every existing KAT vector and every ciphertext ever produced under `VERSION=1` as permanently valid and unambiguous, satisfying "must not break legacy reproducibility" | Recommended, not implemented |
| D6 | Recommend folding the new `EXTRACTION` value into the HKDF `ctx` string, in addition to relying on the existing HMAC tag coverage of the whole header | Rely on HMAC tag coverage alone (already sufficient for tamper detection) | Folding into `ctx` makes a wrong extraction value fail *earlier and more informatively* (key derivation itself diverges) rather than only at tag-verification time; belt-and-braces, consistent with how `PROFILE` is already handled (`kdf.py:47-49`) | Recommended, not implemented |
| D7 | Decline to benchmark `frac_byte` vs. `m_byte` performance in this pass | Run a timing benchmark now | Task explicitly says "do not optimize prematurely"; a meaningful benchmark requires the shape-adapted version operating on real `(k, LANES)` arrays, which does not exist yet (nothing has been implemented) | Deferred — flagged as an open item for Phase 3 |
| D8 | Decline to execute any burn-in comparison (1024/2048/5000/10000) numerically in this pass | Run a quick exploratory burn-in comparison to "see what happens" | Task explicitly: "This phase should produce an experiment design, not fabricated conclusions" and "Do not invent results" | Protocol designed only — `burn_in_experiment_protocol.md` |
| D9 | Flag `isc_eval/exp_nist.py`, `isc_seq/stats.py`, `isc_seq/nist.py`, `isc_seq/periodicity.py` as **not line-by-line inspected** rather than assume their capabilities from filenames | Infer their behavior from filenames/docstrings only | Task Section 13: "If a repository or file is inaccessible, explicitly state that rather than assuming its contents" (extended here to "not yet inspected," which is the honest status) | Explicitly flagged in `multi_lane_statistical_validation_protocol.md §3` |
| D10 | Independently re-execute Gate C (full, both the 4-file subset and the roundtrip suite separately), Gate A, and Gate R rather than citing Phase 1's numbers alone | Cite Phase 1's reported results without re-running | Task §2: "Verify them against the actual repository and do not assume they remain valid without checking" | Done — all three gates independently re-run to completion in this session; see §2 below |
| D11 | Recommend placing the migrated cipher repository in a new `ISC_PBL/cipher/` subdirectory rather than merging files into `ISC_PBL`'s existing flat layout | Merge files directly into `ISC_PBL` root | Avoids the discovered `script/` directory naming collision (`repository_migration_plan.md §8`) and preserves every `ROOT = dirname(dirname(...))` path assumption found in 7 different files without editing any of them | Recommended, not implemented |
| D12 | Recommend initializing git before any physical migration or implementation change | Proceed without version control, continuing the manual `_v1_backup` convention only | Task §10 explicitly asks to "recommend introducing Git version control before substantial implementation changes"; neither repository currently has one | Recommended, not implemented |

## 2. Test execution log (all commands independently run in this Phase 2 session, 11 November 2026, same machine as Phase 1: Windows 10/11 Pro Build 10.0.22631-SP0, Python 3.11.9, NumPy 2.4.6)

```
cd sine_chebyshev_ikeda_analysis

$ python -m pytest tests/test_isc_cipher_auth.py tests/test_isc_cipher_kdf_state.py \
    tests/test_isc_cipher_numeric.py tests/test_isc_cipher_sampling_diffusion.py -q
130 passed in 48.60s

$ python -m pytest tests/test_isc_cipher_roundtrip.py -q
29 passed, 2 skipped in 391.15s (0:06:31)

  => combined Gate C total: 159 passed, 2 skipped, 161 collected
     (independently confirmed via --collect-only -q on all 5 files together: "161 tests collected")

$ python -m pytest tests/test_isc_eval_harness.py -q
16 passed in 35.37s

$ python -I isc_cipher_kat/gate_r.py --backend numpy --label PHASE2-verify
[...] R-fdlibm-hashes: PASS (0.0 s)
[...] R-trig-KAT: PASS (0.3 s)
[...] R-trajectory-KAT: PASS (125.3 s)
[...] R-stream-KAT: PASS (1.6 s)
[...] R-cipher-KAT: PASS (29.3 s)
[...] overall: PASS -> results/cipher_validation/gate_r_PHASE2-verify_numpy_20261111T110629Z
```

**Conclusion: every previously-reported Gate C / Gate A / Gate R result was independently re-executed in
this Phase 2 session and reproduced exactly (159/2/161 for Gate C, 16/0 for Gate A, overall PASS across
all 5 Gate R checks for Gate R).** No previously reported test result was found to be stale, incorrect, or
unreproducible.

Additionally executed, not part of the formal gates, for the `frac_byte`/k=14 equivalence check
(`frac_byte_k14_compatibility_audit.md §3`): a standalone in-memory comparison script (not saved to disk
in either repository) importing `isc_seq.extract.frac_byte` and `ISC_PBL\isc_sequence_characterization.py:
quantise_digit_extraction(..., k=14)` side by side, run once, output recorded verbatim in that document.

## 3. Unresolved questions carried forward (not decided in this pass — require approval or further investigation)

1. Exact byte position and bit-width of the new `EXTRACTION` header field (`dual_profile_generator_design.md §7`).
2. Whether `k14_scaled_modulo_v1` should ever become the default extraction for new encryptions, or remain
   permanently opt-in (`dual_profile_generator_design.md §7`).
3. Whether `isc_eval/exp_nist.py` already implements some or all of `multi_lane_statistical_validation_protocol.md`'s
   §2 requirements — **not inspected in this pass**, first task for the next phase.
4. Whether `third_party/nist_sts/build_linux/` is live tooling or stale cross-platform build output
   (`repository_migration_plan.md §4`) — not resolved.
5. Whether the sibling repository `sine_chebyshev_ikeda_analysis` itself has a `.git` directory —
   observed absent in directory listings but not exhaustively confirmed with `git status` inside it in
   this pass (`repository_migration_plan.md §11`).
6. The proposed sample size (`N=10^5` bytes/lane) for the burn-in and multi-lane statistical protocols is a
   starting-point proposal, not a validated final value — needs tuning against actual runtime cost once
   implemented (`burn_in_experiment_protocol.md §2`).
7. Exact performance cost of `frac_byte`-based extraction vs. the existing bit-trick, deferred per D7.

## 4. Explicit statement of compliance with Section 13 restrictions

No source file in either `ISC_PBL` or `sine_chebyshev_ikeda_analysis` was modified, renamed, deleted, or
moved during this investigation. The only files created are the 8 documents listed in the Phase 2 task's
Section 11, all newly created in `ISC_PBL`'s root, none overwriting an existing file. All test executions
listed in §2 were read-only invocations of pre-existing test/diagnostic scripts (`pytest`, `gate_r.py`)
that do not alter source code; `gate_r.py` writes a new, timestamped report directory under
`sine_chebyshev_ikeda_analysis/results/cipher_validation/`, which is the tool's normal, intended behavior
(documented in its own module docstring, `gate_r.py:1-8`) and does not modify any existing file.
