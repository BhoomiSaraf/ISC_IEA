# Checkpoint 3: ISC-IMG v1 implementation, Gate C (correctness) and Gate R (reproducibility)

Date: 2026-10-26. Specification: `research/algorithm_design.md` revision 2.

Scope:
* **Included:** implementation and correctness/reproducibility validation only.
* **Not started:** attack tests, the new generator's NIST evaluation, benchmarking, and any other Gate A
  experiment.

**Passing Gates C and R shows that the implementation is correct and reproducible on the tested
environments. It does not establish confidentiality or cryptographic security.**

## 0. Environments

| id | where | software | used for |
|---|---|---|---|
| E1 | Windows 11 (10.0.22631), x86_64, the working directory of this project | CPython 3.11.9, NumPy 2.0.2 (MSVC build; SIMD baseline SSE/SSE2), cryptography 50.0.0, scikit-image 0.26.0, mpmath 1.3.0 | all development, Gate C, Gate R (R1 and V1) |
| E2 | WSL2 Ubuntu 24.04 on the same machine (kernel 6.18.54.1, glibc 2.39) | CPython 3.12.3, **no NumPy**, cryptography 41.0.7, gcc 13.3.0 | C oracle build and execution; Gate R (R1 only) |

The CPU supports AVX2 and FMA. The implementations do not use fused operations: one Python or NumPy
operation is one IEEE binary64 operation. Only E1 and E2 were tested. E2 is a different OS, C library,
Python version and Python build on the **same hardware**, so different CPUs are untested.

## 1. New and modified files

**Modified:** none of the existing files.
* `isc_seq/`, `script/`, `experiments/`, `plots/`, the existing tests, `tests/conftest.py` and all earlier
  results are unchanged.
* The earlier result manifests re-verified: `results/sequence_generation/default_20261025` (21 files) and
  `results/nist_sts_official/sts212_default_20261025` (2,363 files), with 0 mismatches.

**New:**

| group | files |
|---|---|
| cipher package | `isc_cipher/__init__.py`, `errors.py`, `kdf.py`, `state_map.py`, `fdlibm_ref.py`, `fdlibm_np.py`, `isc_step.py`, `generator.py`, `sampling.py`, `diffusion.py`, `container.py`, `cipher.py`, `selftest.py`, `_testing.py` (test-only fixed-nonce entry points), `_selftest_vectors.py` (generated from the C oracle) |
| KAT and oracle | `isc_cipher_kat/README.md`, `make_kat.py`, `gate_r.py`, `oracle/oracle.c`, `oracle/build_oracle.sh`, `oracle/build/` (objects, `oracle` binary, `BUILD_INFO.txt`), `vectors/` (`trig_kat.txt.gz`, `traj_kat.json`, `stream_kat.json`, `cipher_kat.json`, `PROVENANCE.json`) |
| official third-party source (archive only, unmodified) | `third_party/fdlibm/netlib_5.3/`: `s_sin.c`, `s_cos.c`, `e_rem_pio2.c`, `k_sin.c`, `k_cos.c`, `k_rem_pio2.c`, `fdlibm.h`, `readme` (retrieved at checkpoint 2), plus `s_fabs.c`, `s_floor.c`, `s_scalbn.c`, `s_copysign.c` (retrieved now: link dependencies of the oracle), `SHA256SUMS.txt`, `RETRIEVED_UTC.txt` |
| tests (Gate C) | `tests/test_isc_cipher_kdf_state.py`, `test_isc_cipher_numeric.py`, `test_isc_cipher_sampling_diffusion.py`, `test_isc_cipher_roundtrip.py`, `test_isc_cipher_auth.py` |
| evidence | `results/cipher_validation/gate_c_E1-windows_20261025T214654Z/`, `gate_r_E1-windows_numpy_20261025T212431Z/`, `gate_r_E1-windows_reference_20261025T212808Z/`, `gate_r_E2-wsl-ubuntu_reference_20261025T212820Z/` |
| report | `research/checkpoint3_report.md` (this file) |

## 2. Implementation summary, in dependency order

| stage | module | what it does (spec section) | implementation notes |
|---|---|---|---|
| 1 key | `kdf.generate_key`, `check_key` | 32 bytes from `os.urandom`; anything other than bytes/bytearray of length 32 → `InvalidKey` (§4.1) | memoryview, str and lists are rejected |
| 2 KDF | `kdf` | HKDF-SHA-256 (stdlib hmac/hashlib): PRK = HMAC(N, K); ctx of 17 bytes; labels `mac`, `kcv`, `iv`, `lane/<stream>/<NNNN>` (§4.2-4.3) | 259 derivations per message |
| 3 initial state | `state_map` | α = BE64 >> 11; x0 = float(α)·2^-52 − 1 (§5.1) | exact, as tested |
| 4 numerical profile | `fdlibm_ref` (R1), `fdlibm_np` (V1) | fdlibm 5.3 sin/cos, reachable branches only; large-argument branch raises (§7.2) | constants built from the exact hex words in the sources; V1 evaluates every reachable branch for every element and selects by the C conditions |
| 4 ISC step | `isc_step` | normative operation order (§6.1); \|arg\| < 24 guard; profile 2 = host NumPy (V1 only) | frozen constants defined locally (so R1 needs no NumPy), with a test asserting equality with `isc_seq.FROZEN_PARAMS` |
| 4-5a generator | `generator` | 4 streams × 64 lanes; joint burn-in of all 256 lanes (T = 1024); output step = all 64 lanes, bytes M(x), M(y) lane-minor; on-demand consumption with steps counted (§2, §6.2, §8.1) | V1 burns in all 256 lanes as one array. This is element-wise, so it is equivalent to per-stream burn-in (tested against R1) |
| 5b integers | `sampling.bounded`, `WordSource` | Lemire with 32-bit words; prefetches exactly 4·(planned draws) bytes and fetches one more word per rejection (§8.2) | |
| 5b S-box / π | `sampling.build_sbox`, `build_permutation` | Fisher-Yates i = 255..1 and i = n−1..1; gather convention (§8.3-8.4) | |
| 6 diffusion | `diffusion` | forward and backward recurrences (§9); inverse implemented twice: scalar (`inverse_ref`, used by R1) and vectorised (`inverse_np`, used by V1) | |
| 6 format | `container` | header (§10); `parse` performs the key-free validation steps 2-6 of §11.2 | `MAX_N = 2^24` |
| 6/6′ cipher | `cipher` | encrypt and decrypt in the §11 order. Decrypt: key check → parse/validate → HMAC verify (constant-time) → self-test → stages 2-5 → inverses → KCV verify (constant-time) → release | no plaintext before step 15 |
| self-test | `selftest` | once per process and profile: sin/cos and a 16-step trajectory against oracle values | profile 2 has no self-test (non-normative) |

**One design-level choice made during implementation (within the spec, flagged for review).**
`decrypt_bytes` accepts PROFILE = 2 only with the NumPy backend. R1 raises `ProfileError` for profile 2,
because the spec defines profile 2 as "host NumPy sin/cos", which R1 cannot provide without NumPy.

## 3. Exact commands used

```bash
# oracle (E2, inside WSL)
sh isc_cipher_kat/oracle/build_oracle.sh
# vectors (E1; calls the oracle through WSL)
python -I isc_cipher_kat/make_kat.py
# Gate R
python -I isc_cipher_kat/gate_r.py --backend numpy --label E1-windows                     # E1, V1
python -I isc_cipher_kat/gate_r.py --backend reference --label E1-windows                 # E1, R1
wsl -d Ubuntu-24.04 --cd <project> -- python3 -I isc_cipher_kat/gate_r.py --backend reference --label E2-wsl-ubuntu   # E2, R1
# Gate C (E1)
python -m pytest tests -rA -p no:cacheprovider --junitxml=<dir>/junit_full.xml
ISC_SLOW=1 python -m pytest tests/test_isc_cipher_roundtrip.py -k "scikit or maximum" -rA -p no:cacheprovider --durations=0 --junitxml=<dir>/junit_slow.xml
```

## 4. Results

### Gate R (reproducibility): all PASS

| check | E1 V1 (NumPy) | E1 R1 (pure Python) | E2 R1 (pure Python, Linux) |
|---|---|---|---|
| R-fdlibm-hashes: archived sources match SHA256SUMS | PASS | PASS | PASS |
| R-trig-KAT: 74,063 sin/cos results equal to the C oracle (bit-exact) | PASS | PASS | PASS |
| R-trajectory-KAT: 10 trajectories × 100,000 steps, SHA-256 over **every intermediate state** plus checkpoints, equal to the C oracle | PASS | PASS | PASS |
| R-stream-KAT: seeds, initial states, states after burn-in, first 1024 bytes and states after 8 steps for all 4 streams × 64 lanes, equal to the C oracle | PASS | PASS | PASS |
| R-cipher-KAT: 6 shapes. S-box, IVs, π, stream prefixes, step counts, KCV, body and ciphertext equal to the recorded vectors; decryption round trip; KCV recomputed from the state bytes as specified | PASS | PASS (reproduces the vectors it generated) | PASS |

Evidence: `results/cipher_validation/gate_r_*/report.json`. These include environment details: Python
build, platform, NumPy build compilers and SIMD (E1), CPU flags (E2) and `float_info`.

### Gate C (correctness): all PASS in the final runs

| file | tests | status | independent expected values used |
|---|---|---|---|
| `test_isc_cipher_kdf_state.py` | 27 | PASS | RFC 5869 test cases 1 and 3; the `cryptography` HKDF on 50 random cases; exact rational arithmetic (`fractions`) on 10^5 mappings; exhaustive check of the 2^11 ignored bits |
| `test_isc_cipher_numeric.py` | 15 | PASS | C-oracle vectors; mpmath (200-bit), which shows fdlibm within 1 ulp on the sampled vectors; equality of profile 2 with the existing `isc_seq` canonical step |
| `test_isc_cipher_sampling_diffusion.py` | 46 | PASS | exact analytic acceptance counts proving Lemire uniformity for 12 bounds; a separately written Fisher-Yates; crafted word streams (identity S-box, forced rejection); the spec's §12.1 worked example; independently coded recurrences |
| `test_isc_cipher_roundtrip.py` | 29 + 2 slow | PASS | array equality on 9 shapes × 9 contents (zeros, 255, constant, gradients, checkerboard, repeated values, single bright pixel, random), R1 and V1, **R1 vs V1 ciphertext equality and cross-decryption**, 255×256 and 256×256×3; size limits; invalid images |
| slow: `test_scikit_image_samples_roundtrip` | 1 | PASS (1215 s) | all 12 samples (`camera`, `astronaut`, `coffee`, `chelsea`, `moon`, `brick`, `grass`, `gravel`, `text`, `checkerboard`, `rocket`, `cat`); all are uint8, none excluded or converted |
| slow: `test_maximum_size_roundtrip` | 1 | PASS (4366 s) | 4096 × 4096 random uint8 (n = 2^24, the maximum) |
| `test_isc_cipher_auth.py` | 42 | PASS | the HMAC recomputed independently. Covers: every single-bit flip of a full ciphertext; truncation and extension by 1..64 bytes; nonce, KCV and tag swaps; dimension re-labelling with equal n; profile change; 201 wrong keys; 15 malformed-header cases; invalid key types; **an instrumented guard proving no generator work happens before authentication**; the exact KCV definition (4128 state bytes); the KCV under numerical perturbation; self-test failure blocking decryption; profile 2 round trip |
| existing tests (sequence generation, NIST tooling) | 64 | PASS | unchanged |

Totals: **223 passed, 0 failed** in the full run (16 min), plus **2 passed** in the slow run (93 min). The
11 warnings are all `DeprecationWarning: invalid escape sequence` from the unmodified legacy scripts in
`script/`, which an existing test parses.

### Failures during development (preserved, not suppressed)

The first Gate C run gave **77 passed, 2 failed, 2 skipped**. Both failures were defects in the tests, not
in the cipher.

1. **`test_swapping_nonce_kcv_or_tag_between_ciphertexts_rejected`**
   * Minimal case: the test enabled the "no generator before authentication" guard and then
     *encrypted* a second ciphertext.
   * Expected: `AuthenticationError` from decryption. Actual: `AssertionError("generator work before
     authentication")` raised by the test's own encryption.
   * Cause: test ordering. Fix: build that ciphertext in a fixture created before the guard. The
     cipher was unchanged.
2. **`test_kcv_detects_numerical_divergence_and_withholds_plaintext`**
   * Minimal case: during decryption (E1, V1), the 500th call of the vectorised `sin` was perturbed by
     1 ulp at lane 3.
   * Expected (by the test): `NumericalDivergenceError`. Actual: decryption returned the **correct**
     plaintext.
   * Cause: the 1-ulp change was absorbed by later rounding (for example in 2·sx² − 1), so every lane
     state stayed bit-identical. Measured over 7 perturbation points, 3 were absorbed (states
     identical, correct plaintext) and 4 changed the states and were rejected by the KCV. **No case
     released a wrong plaintext.**
   * Fix: the test now checks exactly the specified property: the KCV fails **if and only if** the final
     states differ, and no wrong plaintext is ever returned. A deterministic state-perturbation test was
     added. The cipher was unchanged.

## 5. Known-answer vectors (public test key 00 01 … 1f, public test nonce 00 01 … 0f; never for real use)

| shape | KCV | IVs (f, b) | output steps (sbox, perm, fwd, bwd) | notes |
|---|---|---|---|---|
| 1×1 | `6557bc2ca35da65a` | 77, 185 | 8, 0, 1, 1 | full ciphertext: `49534349 01010101 0001 0001 000102030405060708090a0b0c0d0e0f 6557bc2ca35da65a c0 278e93a3…e4afe9` |
| 1×7 | `20b98fd8cbd88270` | 211, 135 | 8, 1, 1, 1 | π = [0, 5, 4, 3, 1, 6, 2] |
| 7×1 | `a65e475df1b10a46` | 126, 176 | 8, 1, 1, 1 | π = [6, 2, 1, 0, 3, 4, 5] |
| 4×6×3 | `371432947bc77599` | 153, 42 | 8, 3, 1, 1 | |
| 16×16 | `e6cbe2184d2607a5` | 223, 172 | 8, 8, 2, 2 | |
| 64×64×3 | `f7dc5a1beb0d050e` | 36, 192 | 8, 384, 96, 96 | |

Further vectors:
* Oracle trajectory from (0.1, 0.1): state after 100,000 steps = (`bfd8555e27ad7832`, `3fef29b46334932c`);
  SHA-256 over all states `346ceecc48e6081a…`.
* Complete data in `isc_cipher_kat/vectors/`.
* Oracle binary SHA-256 `b4bccc1c…4540165f` (gcc 13.3.0, `-O0 -ffp-contract=off -fno-builtin -D__LITTLE_ENDIAN`).

**Independence of the vectors:**
* Independent: sin/cos, trajectories and stream bytes (C oracle on the official fdlibm sources).
* Not independent: the full-cipher vectors, which were produced by R1 and are confirmed by V1
  (different code paths for generation and decryption) and by R1 on Linux. A shared misunderstanding
  of the specification in the integer stages (S-box, π, diffusion) would not be caught by them. It is
  covered instead by the component tests with independent expectations (§4).

## 6. Discrepancies between specification and implementation or evidence

1. **§10.1 rationale sentence is inaccurate (evidence, not code).**
   * The spec says that a single different sin/cos result changes a lane's final state "with very high
     probability". Measured: in 3 of 7 one-ulp perturbations it did not, because rounding absorbed it.
   * The KCV's specified behaviour (it detects any final-state difference) is correct and tested.
     Absorbed perturbations are harmless, because decryption is then correct.
   * **Proposed correction for review:** replace the sentence with "a sin/cos difference either is
     absorbed by rounding (states identical, decryption correct) or changes the state, in which case the
     KCV detects it; the absorption rate is not quantified." The spec file has **not** been edited.
2. **Profile 2 with the reference backend:** raises `ProfileError` (§2 above). The spec is silent on this;
   proposed clarification: "profile 2 is supported by V1 only".
3. **Spec §7.4 KAT 1 asks for "10^5 arguments"; 74,063 were used.** The set covers every listed branch
   class, plus 50,000 uniform and 20,000 small-magnitude arguments. This deviates from the stated count;
   it can be extended on request.
4. **Spec §7.4 KAT 2 lists "R1 on E1 and E2 and V1 on E1 must agree" with each other.** Implemented more
   strongly: all three are compared with the independent C oracle.

No other differences were found. No algorithm, parameter or constant deviates from the specification.

## 7. Outstanding limitations

**Correctness**
* Integer-stage expectations for full-cipher vectors are not independent (see §5); component tests cover
  this partially.
* Inputs larger than n = 2^24, other dtypes and 4-channel images are rejected by design and untested
  beyond rejection.

**Numerical**
* Reproducibility is shown only for E1 (Windows, CPython 3.11.9, NumPy 2.0.2) and E2 (WSL Ubuntu, CPython
  3.12.3) on **one physical CPU**. Different CPUs, macOS, ARM, other NumPy builds (for example with
  AVX-512 SVML paths for basic operations), PyPy and compiled ports are untested. **No universal
  cross-platform claim is made.**
* fdlibm is not correctly rounded. Within 1 ulp was observed on the sampled arguments, but this is not
  proven for all arguments.
* Lemma 3's floating-point step (|sx| ≤ 1 for fdlibm sin) was not violated in any test (all states in
  [−1, 1]), but it is not proven for all inputs.
* The KCV's undetectable window (divergence that does not change final states) is harmless by
  construction, but its frequency is not quantified.

**Performance (not an evaluation, observed while testing)**
* V1 needs about 1.7 ms per vectorised ISC step on E1, so even a 1×1 image takes about 2 s per operation
  (burn-in), and 4096×4096 takes about 36 min per operation.
* This will make the planned Gate A experiments slow. Speed-ups that do not change results (for
  example evaluating only the needed fdlibm branch per element) would need review, because they change
  code that is now KAT-verified.

**Security (unchanged from the specification; none of this is addressed by Gates C and R)**
* Confidentiality is unproven and depends on the ISC conjecture.
* Integrity rests on HMAC-SHA-256.
* Nonce reuse makes encryption deterministic.
* The effective security level of the ISC streams is unknown.

## 8. Gate status

* **Gate C: PASSED** on E1. 225 tests pass, including the slow ones; 0 failures in the final runs; 2
  development-time test defects were found and fixed, as documented in §4.
* **Gate R: PASSED** for the tested scope: V1 and R1 on E1, and R1 on E2, all bit-identical to the
  independent C oracle and to the recorded vectors.
* **Not started:** attacks A1-A15, the A12 NIST re-test of the new generator, benchmarking, ciphertext
  statistics. These wait for approval.
