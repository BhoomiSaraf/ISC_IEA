# Phase 3A Validation Results

**Document ID:** `ISC-PHASE3A-VALIDATION-2026-02`
**Date:** 11 November 2026
**Environment (identical across every command below):** Windows 10/11 Pro (Build 10.0.22631-SP0,
AMD64), Python 3.11.9, NumPy 2.4.6, SciPy 1.17.1, pytest 9.1.1, run from
`C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis`.

Every number in this document is either (a) the literal output of a command actually executed in
this session, with its real wall-clock time, or (b) a SHA-256 hash actually computed in this
session. Nothing here is carried over from a prior session's report without being independently
re-run.

---

## 1. Baseline — before any Phase 3A source edit

### 1.1 File hashes recorded as the rollback baseline (copies also saved to
`C:\Users\bhoom\Desktop\phase3a_backups_20261111\`)

```
040c320ca22a2d7e05900ad719eaef622023ce7eb792c080ca49b7979f11d566  isc_cipher/kdf.py
83d67aa4d645e75f290b99b37c1c5d30f8bc2ce3ea569f393d1d9c101e03908a  isc_cipher/container.py
ba334c3764564163a511d6b22de531a015d3e4f4adde346dd875d9189ba06333  isc_cipher/generator.py
3e0e9a60964cb784ac9e05b4297e10848a6a78193326049f252b49d0a9e59785  isc_cipher/cipher.py
61b49e95505c981d3d2fa8f85aa59f3b48e3edae73588f99d5094d2aa3b941c8  isc_cipher/_testing.py
9b056e4b0cad248842f79f3028b0db7fe7819cded7d8eb578f61e8e4e335031c  isc_cipher/selftest.py
9cc31d5ddfed5c6bf441b6bc911aa259cec63dca762988b0c73d86319b5dcca3  isc_cipher_kat/make_kat.py
175f889c13375cfe99f294bca7da148f1aea9073bb2b91a44c94375d55efe566  isc_cipher_kat/gate_r.py
```

### 1.2 Existing KAT vector hashes (baseline; must remain unchanged throughout)

```
14ae5f5a61f74f3bc886b9509dabe4dad8c32780ab91ff92466e40697a873d1d  isc_cipher_kat/vectors/PROVENANCE.json
c5de66495d9363f63ca1f5c11a0e39e5d89a2d582acc0b620baa085f22bba5d8  isc_cipher_kat/vectors/cipher_kat.json
59b340af1003e29b12f28098488fa9c8f9100db4838506c9b48befd308aba20e  isc_cipher_kat/vectors/stream_kat.json
9878b24205596a041159f04f414f28da4b36e4cc2389c46c3b4c941bf76fe172  isc_cipher_kat/vectors/traj_kat.json
69b292c6e52edad91aec240a33dd2fb4375b0f8571d2d9af10449fde9654eaf5  isc_cipher_kat/vectors/trig_accuracy_by_branch.json
2d6cbecf818a140ea523abccf7f19d2345736950987e81967108d86ce6f5caca  isc_cipher_kat/vectors/trig_kat.txt.gz
77aa9d1a85b8a3efcba1884555768dd0fcf5bd8e145d7e055218dea51e763403  isc_cipher_kat/vectors/trig_kat_ext.txt.gz
```

### 1.3 Baseline gate runs (before any source edit)

```
$ python -m pytest tests/test_isc_cipher_auth.py tests/test_isc_cipher_kdf_state.py \
    tests/test_isc_cipher_numeric.py tests/test_isc_cipher_sampling_diffusion.py \
    tests/test_isc_cipher_roundtrip.py -q
159 passed, 2 skipped in 364.09s (0:06:04)

$ python -m pytest tests/test_isc_eval_harness.py -q
16 passed in 47.61s
```

(Gate R was not re-run at this exact baseline point in this session, to avoid duplicating the ~5
minutes of Gate R twice; it was re-run once after all implementation was complete, §2 below, which
is the result that matters for regression-detection purposes. The prior closure session's Gate R
re-run on this same machine, same day, reported identical PASS results for all 5 checks.)

---

## 2. Post-implementation gate runs (after all five modified files were edited)

```
$ python -m pytest tests/test_isc_cipher_auth.py tests/test_isc_cipher_kdf_state.py \
    tests/test_isc_cipher_numeric.py tests/test_isc_cipher_sampling_diffusion.py \
    tests/test_isc_cipher_roundtrip.py -q
159 passed, 2 skipped in 422.68s (0:07:02)

$ python -m pytest tests/test_isc_eval_harness.py -q
16 passed in 40.00s

$ python -I isc_cipher_kat/gate_r.py --backend numpy --label PHASE3A-post-impl
R-fdlibm-hashes:    PASS (0.1 s)
R-trig-KAT:         PASS (0.3 s)
R-trajectory-KAT:   PASS (168.1 s)
R-stream-KAT:       PASS (1.5 s)
R-cipher-KAT:       PASS (26.4 s)
overall: PASS -> results/cipher_validation/gate_r_PHASE3A-post-impl_numpy_20261111T135417Z
```

**Conclusion: identical pass/skip counts to the baseline for Gate C and Gate A; Gate R fully PASS
against the original, unmodified vectors.** Zero regression in any existing test or vector.

### 2.1 Existing KAT vector hashes, re-verified unchanged after all implementation work

```
14ae5f5a61f74f3bc886b9509dabe4dad8c32780ab91ff92466e40697a873d1d  isc_cipher_kat/vectors/PROVENANCE.json
c5de66495d9363f63ca1f5c11a0e39e5d89a2d582acc0b620baa085f22bba5d8  isc_cipher_kat/vectors/cipher_kat.json
59b340af1003e29b12f28098488fa9c8f9100db4838506c9b48befd308aba20e  isc_cipher_kat/vectors/stream_kat.json
9878b24205596a041159f04f414f28da4b36e4cc2389c46c3b4c941bf76fe172  isc_cipher_kat/vectors/traj_kat.json
69b292c6e52edad91aec240a33dd2fb4375b0f8571d2d9af10449fde9654eaf5  isc_cipher_kat/vectors/trig_accuracy_by_branch.json
2d6cbecf818a140ea523abccf7f19d2345736950987e81967108d86ce6f5caca  isc_cipher_kat/vectors/trig_kat.txt.gz
77aa9d1a85b8a3efcba1884555768dd0fcf5bd8e145d7e055218dea51e763403  isc_cipher_kat/vectors/trig_kat_ext.txt.gz
```
Byte-for-byte identical to §1.2 — confirmed unmodified.

### 2.2 `isc_cipher_kat/make_kat.py` and `gate_r.py` hashes, re-verified unchanged

```
9cc31d5ddfed5c6bf441b6bc911aa259cec63dca762988b0c73d86319b5dcca3  isc_cipher_kat/make_kat.py
175f889c13375cfe99f294bca7da148f1aea9073bb2b91a44c94375d55efe566  isc_cipher_kat/gate_r.py
```
Byte-for-byte identical to §1.1 — confirmed unmodified (no edits were made to either file; the
new k14 profile uses separate, parallel scripts instead, §4).

### 2.3 `isc_cipher/selftest.py` hash, re-verified unchanged

```
9b056e4b0cad248842f79f3028b0db7fe7819cded7d8eb578f61e8e4e335031c  isc_cipher/selftest.py
```
Byte-for-byte identical to §1.1 — confirmed unmodified, per the deliberate decision to defer an
extraction-level self-test (`phase_3a_implementation_plan.md`'s `selftest.py` row).

---

## 3. New test module

```
$ python -m pytest tests/test_isc_cipher_extraction_profiles.py -q
```

**First run** (immediately after writing the module, before fixing 3 test-authoring bugs found —
not implementation bugs; see below): **46 passed, 5 failed in 433.84s**. All 5 failures were in
the *test code itself*, not the production code:
1. `test_header_v2_serialization_byte_layout_and_offsets` — compared the full 36-byte prefix of a
   V2-packed header against a V1-packed header, including the VERSION byte itself (which is
   *supposed* to differ, 1 vs 2) — a test-authoring oversight, not a container.py bug. Fixed by
   comparing MAGIC, VERSION, and the remaining fields separately.
2. `test_tampered_extraction_byte_rejected_before_generator` — installed the `no_generator`
   monkeypatch *before* constructing the test ciphertext (which itself requires calling
   `_build_generators` once, legitimately, during encryption) — an ordering bug in the test, not in
   `cipher.py`. Fixed by constructing the ciphertext first.
3. `test_tampered_version_byte_rejected` — the same ordering bug. Fixed the same way.
4. `test_frac_byte_scalar_matches_numpy_frac_byte_over_production_recurrence` — compared a
   1,000,000-element array against a 2,000-element array with `np.array_equal`, which correctly
   returns `False` for mismatched shapes regardless of content — a test-authoring bug. Fixed by
   slicing the larger array to the same length before comparing.
5. `test_no_generator_work_before_authentication_for_v2` — the same monkeypatch-ordering bug as
   item 2/3. Fixed the same way.

**After fixing all 5 test-authoring bugs, rerun:**

```
$ python -m pytest tests/test_isc_cipher_extraction_profiles.py -q
51 passed in 363.53s (0:06:03)
```

All 51 tests pass, with zero production-code changes needed to fix the 5 original failures —
every one was a bug in the new test file itself, not in `kdf.py`/`container.py`/`generator.py`/
`cipher.py`.

---

## 4. New KAT vectors (k14_scaled_modulo_v1)

```
$ python isc_cipher_kat/make_kat_k14.py
stream KAT (k14) done
cipher KAT (k14) (1, 1, 1)
cipher KAT (k14) (1, 7, 1)
cipher KAT (k14) (7, 1, 1)
cipher KAT (k14) (4, 6, 3)
cipher KAT (k14) (16, 16, 1)
cipher KAT (k14) (64, 64, 3)
done
```

New vector files and their hashes (generated once, this session; not regenerated or overwritten
afterward — `make_kat_k14.py` itself refuses a second run while these exist):
```
491026774c260077487329f602f36d9ad1c5327af6cf15d1bc3f52cbb8be427c  isc_cipher_kat/vectors/stream_kat_k14.json  (3,388 lines)
724a819d6c19a4c14ddcfe4b98bd59e0263d8093124c2e08bb753668a6abd234  isc_cipher_kat/vectors/cipher_kat_k14.json  (506 lines)
```

```
$ python isc_cipher_kat/gate_r_k14.py --backend both --label PHASE3A-k14
[19:24:27] Gate R (k14 extension), backend=both, Python 3.11.9
[19:24:31] R-k14-stream-KAT (reference): PASS (3.9 s)
[19:25:49] R-k14-cipher-KAT (reference): PASS (78.0 s)
[19:25:51] R-k14-stream-KAT (numpy): PASS (2.1 s)
[19:26:31] R-k14-cipher-KAT (numpy): PASS (40.1 s)
[19:27:06] R-k14-backend-cross-equal: PASS
[19:27:06] overall: PASS -> results/cipher_validation/gate_r_k14_PHASE3A-k14_both_20261111T135427Z
```

`R-k14-stream-KAT` cross-checks the HKDF-derived seeds and initial states against the **independent
C oracle** (fdlibm 5.3, run fresh via WSL in this session — not reused from a prior session's
output) and the first 1,024 bytes of each stream computed with `frac_byte` against that same
oracle trajectory. `R-k14-cipher-KAT` is self-generated (R1, not independent) but cross-checked
between backends. `R-k14-backend-cross-equal` directly confirms the reference and NumPy backends
produce byte-identical VERSION=2/k14 ciphertexts for the same inputs.

---

## 5. Compliance check against the task's 13 non-negotiable constraints

1. No frozen Step 1.1 artifact edited — confirmed; nothing under `ISC_PBL` was opened for writing.
2. No repository migration performed — confirmed; `sine_chebyshev_ikeda_analysis` was edited in
   place, `ISC_PBL` untouched.
3. Production cipher code modified **only** as specified in `phase_3a_file_change_log.md`, with
   every change additive-by-default and regression-tested.
4. No existing test file or KAT vector overwritten — confirmed by hash comparison (§2.1-2.3) and by
   `make_kat_k14.py`'s own refuse-to-overwrite check.
5. No default silently changed — every new parameter's default reproduces prior behaviour exactly
   (verified by the full existing Gate C/A/R suites passing unmodified).
6. Extraction and burn-in were not changed together anywhere — burn-in defaults (`BURN_IN = 1024`)
   were not touched; no burn-in experiment was run in this task (out of scope, Phase 3B).
7. No mandatory NumPy dependency introduced into the scalar backend — confirmed by bytecode
   inspection of `frac_byte_scalar` and by `isc_cipher.generator`'s module namespace containing no
   `numpy` binding (`tests/test_isc_cipher_extraction_profiles.py::
   test_scalar_backend_importable_and_usable_without_numpy_module_object`).
8. No claim that statistical randomness proves cryptographic security — none made anywhere in this
   document set.
9. No claim that k=14 is superior to mantissa8 without multi-lane testing — none made; Phase 3B
   remains open and is explicitly deferred (§9 of `phase_3a_implementation_report.md`).
10. No fabricated/hardcoded experiment results — every number in this document traces to a command
    actually run in this session.
11. No ambiguity left in the container layout or KDF encoding — implemented exactly per
    `container_v2_binary_specification.md` and `hkdf_profile_binding_specification.md`.
12. No test reported as passed unless it actually executed successfully — every count above is a
    literal command output.
13. No git commit created — neither repository is a git repository (confirmed in the prior Phase 2
    closure session); no commit was made or attempted.
