# Phase 3A Implementation Report — Dual-Profile ISC-IMG Cipher

**Document ID:** `ISC-PHASE3A-IMPL-2026-02`
**Date:** 11 November 2026
**Repository implemented in:** `C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis`
**Repository left untouched:** `C:\Users\bhoom\Desktop\ISC_PBL` (Step 1.1, frozen)

Tagging convention (unchanged from the Phase 2 documents): `[VERIFIED SOURCE]` = read directly;
`[EXECUTED]` = command run, real output reported; `[DERIVED]` = logical/mathematical consequence;
`[DECISION]` = design choice made during implementation, with rationale.

---

## 1. Architecture implemented

Two independent axes were added to the existing, unchanged ISC-IMG v1 architecture (4 streams x 64
lanes, HKDF-SHA-256, Lemire sampling, Fisher-Yates, forward/backward diffusion, HMAC-SHA-256,
fdlibm 5.3):

1. **Byte extraction** (`isc_cipher/generator.py`): `EXTRACTION_MANTISSA8_V1 = 1` (the original,
   unchanged `m_byte` = bits 8-15 of the Float64 encoding) and `EXTRACTION_K14_SCALED_MODULO_V1 = 2`
   (the Step 1.1-characterized `B(v) = floor(|v| * 1e14) mod 256`, reusing `isc_seq.extract.frac_byte`
   for the NumPy backend and a new, dependency-free `frac_byte_scalar` for the reference backend).
2. **Container version** (`isc_cipher/container.py`): VERSION=1 (36-byte header, unchanged,
   implicitly `extraction=1`) and VERSION=2 (37-byte header, explicit `EXTRACTION` byte at offset
   36, authenticated like every other header field).

### 1.1 Flow from the public API to the generator and back (Section B's answer)

**Encryption**, `encrypt_bytes(key, data, h, w, c, backend, extraction=1)`:
1. `_encrypt` validates `extraction` and auto-selects `version` (1 if `extraction==1`, else 2)
   unless a caller (test/KAT code only) explicitly overrides `version`.
2. `_materials` computes `ctx_extraction = extraction if version==2 else None` and calls
   `kdf.context(profile, dtype, h, w, c, extraction=ctx_extraction)` — this is the **only** point
   where the extraction choice enters the HKDF key schedule (`hkdf_profile_binding_specification.md`
   Defense 2).
3. `_build_generators` calls `generator.build_streams(seeds, backend, profile, extraction=...)` —
   the **only** point where the extraction choice enters byte generation. Internally,
   `RefStream`/`NpStream` look up the extraction function once at construction and apply it at
   every output step; the ISC recurrence (`isc_step.step_ref`/`step_vec`), burn-in, and lane
   scheduling are completely unaware of which extraction function is in use.
4. The sampling (S-box, permutation), diffusion (forward/backward), and KCV stages consume
   whatever bytes the chosen extraction function produced, unmodified from their original logic.
5. `container.Header(..., version=version, extraction=extraction).pack()` builds the header;
   `extraction` is only serialized into the header bytes when `version==2`.
6. The HMAC tag covers `header || body` as before — now including the `EXTRACTION` byte for V2
   headers, since it is simply part of `header`.

**Decryption**, `decrypt_bytes(key, z, backend)`:
1. `container.parse(z)` reads `VERSION` first, selects the header length, and (for V2) validates
   `EXTRACTION ∈ {1, 2}` — **before** any key material is derived.
2. `ctx_extraction`/`hl` are computed from the **parsed header**, never from a caller argument.
3. The HMAC tag is verified over `z[:hl + n]` using the version/extraction-appropriate `ctx`.
   **Tag verification happens before `_build_generators` is ever called** — proven by the existing
   `no_generator` test fixture pattern, now also exercised for VERSION=2/tampered-`EXTRACTION`
   scenarios by the new test module.
4. Only after the tag passes does `_materials`/`build_streams` run with `hdr.extraction`, exactly
   mirroring how `hdr.profile` already worked.

---

## 2. Files modified / added

See `phase_3a_file_change_log.md` for the complete, file-by-file breakdown with line-level
reasoning. Summary:

- **Modified:** `isc_cipher/kdf.py`, `isc_cipher/container.py`, `isc_cipher/generator.py`,
  `isc_cipher/cipher.py`, `isc_cipher/_testing.py`.
- **Added:** `isc_cipher_kat/make_kat_k14.py`, `isc_cipher_kat/gate_r_k14.py`,
  `isc_cipher_kat/vectors/stream_kat_k14.json`, `isc_cipher_kat/vectors/cipher_kat_k14.json`,
  `tests/test_isc_cipher_extraction_profiles.py`.
- **Explicitly not modified:** `isc_cipher/selftest.py`, `isc_cipher/isc_step.py`,
  `isc_cipher/state_map.py`, `isc_cipher/sampling.py`, `isc_cipher/diffusion.py`,
  `isc_cipher/fdlibm_ref.py`, `isc_cipher/fdlibm_np.py`, `isc_seq/extract.py`,
  `isc_cipher_kat/make_kat.py`, `isc_cipher_kat/gate_r.py`, every existing test file, every
  existing KAT vector file, and everything in `ISC_PBL`.

---

## 3. Public API changes

- `encrypt_bytes(key, data, h, w, c, backend=DEFAULT_BACKEND, extraction=EXTRACTION_MANTISSA8_V1)`
  and `encrypt(key, image, backend=DEFAULT_BACKEND, extraction=EXTRACTION_MANTISSA8_V1)` — new
  trailing keyword-only-by-position argument. **No existing call shape changes meaning.**
- `decrypt_bytes`/`decrypt` — **no signature change**; extraction is read from the ciphertext.
- `isc_cipher.generator.{EXTRACTION_MANTISSA8_V1, EXTRACTION_K14_SCALED_MODULO_V1, EXTRACTIONS,
  frac_byte_scalar}` — new public names, importable from `isc_cipher.cipher` and
  `isc_cipher.generator`.

`[DECISION]` k14 is **not** the default and is not made normative by this implementation: Phase 3B's
multi-lane statistical validation (`phase_3b_validation_readiness.md`) has not run. This
implementation makes k14 *available and fully tested at the engineering level*; it makes no
statistical or cryptographic security claim about it.

---

## 4. Container V1/V2 behaviour

See `container_v2_binary_specification.md §5` for the full behaviour table; every row was
implemented and tested (`phase_3a_validation_results.md §3`). Key facts:
- VERSION=1 ciphertexts are parsed and produced identically to before Phase 3A, byte-for-byte.
- VERSION=2 adds exactly one byte (`EXTRACTION`, offset 36), authenticated identically to every
  other header field.
- `container.HEADER_LEN` (= 36) is kept as a module constant, unchanged, because
  `isc_eval/constructions.py` references it directly for its own (VERSION=1-only) baseline
  construction — a real external dependency discovered by grep, not assumed.

---

## 5. KDF context behaviour

See `hkdf_profile_binding_specification.md §2-6`, implemented exactly as specified:
`context(..., extraction=None)` is additive; `None` reproduces the 17-byte V1 context
byte-for-byte; `1`/`2` produce an 18-byte V2 context. A VERSION=1 ciphertext and a
VERSION=2/`extraction=1` ciphertext for the same `(key, nonce, dims)` derive **completely
different** key material (verified directly, `test_v1_ctx_binding_differs_from_v2_extraction_1_ctx_binding`),
confirming Defense 2 (ctx-binding) is real and not merely nominal.

---

## 6. Scalar/NumPy extraction backend compatibility

`frac_byte_scalar` (pure `math.floor`/`abs`/`float`, no NumPy) was verified against
`isc_seq.extract.frac_byte` (NumPy) on:
- 1,000,000 `(x, y)` points **actually produced by the production `isc_cipher.isc_step.step_vec`
  recurrence** (not the research recurrence), stride-sampled at every 10,007th point plus a dense
  2,000-point prefix check — all matched exactly.
- The full boundary-value set from the Phase 2 audit (`0.0`, `-0.0`, `±1.0`, `±(1-2^-52)`, `±0.5`,
  `±2^-52`) — all matched exactly.
- Confirmed `frac_byte_scalar` returns a plain Python `int` in `[0, 255]`.
- Confirmed (by bytecode inspection, `dis.Bytecode(frac_byte_scalar).codeobj.co_names`) that
  `frac_byte_scalar`'s own code object references neither `np` nor `numpy`, and that
  `isc_cipher.generator`'s module namespace contains no `numpy` binding at import time — the
  reference backend remains usable without NumPy, satisfying the hard constraint explicitly.
- `RefStream` and `NpStream` constructed with `extraction=2` for the same seeds/burn-in produce
  byte-identical `take()` output (`test_k14_refstream_and_npstream_produce_byte_identical_output`).
- The full cipher, scalar vs. vector backend, for the same `(key, nonce, dims)` and
  `extraction=K14`, produces **byte-identical ciphertexts**, verified both ad hoc and via
  `gate_r_k14.py --backend both`'s `R-k14-backend-cross-equal` check.

This extends, by three orders of magnitude and onto the production (not research) recurrence, the
prior session's 2,000-point check — consistent with `extraction_backend_compatibility_specification.md
§7`'s proposal. It remains an **operational equivalence demonstration over a large, representative
sample**, not an exhaustive proof over the entire float64 domain — the same caveat the design
documents carried throughout.

---

## 7. KAT results

| Vector set | Generation method | Verification | Result |
|---|---|---|---|
| `trig_kat.txt.gz`, `traj_kat.json` (existing) | unchanged | `gate_r.py` (unmodified) | PASS — extraction-independent, fully reused |
| `stream_kat.json`, `cipher_kat.json` (existing, mantissa8_v1/V1) | unchanged | `gate_r.py` (unmodified) | PASS, both before and after every code change |
| `stream_kat_k14.json` (new) | independent: C oracle (fdlibm 5.3, via WSL) for the trajectory; Python `frac_byte` for bytes | `gate_r_k14.py --backend reference\|numpy` | PASS, both backends |
| `cipher_kat_k14.json` (new) | self-generated, R1 reference backend, VERSION=2/extraction=2 | `gate_r_k14.py --backend reference\|numpy`, plus direct reference-vs-numpy byte equality | PASS, both backends, byte-identical cross-check |

No existing vector file's bytes changed (SHA-256-verified before and after all code changes; see
`phase_3a_validation_results.md §1,§5`).

---

## 8. Test coverage

- All 5 existing Gate C modules (`test_isc_cipher_{auth,kdf_state,numeric,sampling_diffusion,
  roundtrip}.py`): **unmodified**, 159 passed / 2 skipped, both before and after every
  implementation change.
- Existing Gate A (`test_isc_eval_harness.py`): **unmodified**, 16 passed, both before and after.
- New `tests/test_isc_cipher_extraction_profiles.py` (51 tests): covers KDF context binding (7),
  container V1/V2 (14), generator/backend compatibility (9), cipher integration (11), totaling the
  battery specified in Sections 5-8 of the implementation task.

See `phase_3a_validation_results.md` for exact commands and real pass/fail counts — no number in
this report is asserted without a corresponding executed-command entry there.

---

## 9. Remaining limitations (explicitly not addressed by Phase 3A, by design)

1. **No statistical validation of k14 in the actual multi-lane generator** — Phase 3B
   (`phase_3b_validation_readiness.md`) is a separate, not-yet-run phase. This implementation makes
   no claim that `k14_scaled_modulo_v1` is statistically better, worse, or equivalent to
   `mantissa8_v1` inside the 256-lane architecture.
2. **No self-test coverage of either extraction method** — `isc_cipher/selftest.py` was
   deliberately left unmodified (it already stopped before the extraction step for `mantissa8_v1`
   too, so this is not a new parity gap).
3. **No performance benchmark of `frac_byte` vs. `m_byte`** — deliberately deferred again, per the
   original task's "do not optimize prematurely" instruction; the relative cost ordering
   (`m_byte`: bit operations only; `frac_byte`/`frac_byte_scalar`: four floating-point operations)
   remains an analytical observation, not a measurement.
4. **`isc_eval/exp_nist.py`'s `a12()` is still hardwired to `mantissa8_v1`** (`build_streams(seeds,
   backend="numpy", profile=1)`, no `extraction` argument) — it continues to work unmodified
   (verified, `isc_eval.exp_nist.message_streams` smoke-tested this session) but was not extended
   to accept the new `extraction` parameter, since that is Phase 3B scope per
   `phase_2_closure_audit.md §1` item 4.
5. **`make_kat_k14.py`/`gate_r_k14.py` require WSL** (for stream KAT generation only, via the same
   oracle `make_kat.py` already depends on) — this is an existing environment dependency of the
   project's KAT infrastructure, not a new one introduced by this change.

No claim is made anywhere in this report that passing Gate C/A/R, or any statistical test, proves
cryptographic security for either extraction profile.
