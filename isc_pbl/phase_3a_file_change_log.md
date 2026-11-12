# Phase 3A File Change Log

**Document ID:** `ISC-PHASE3A-CHANGELOG-2026-02`
**Date:** 11 November 2026
**Scope:** every file touched while implementing the `k14_scaled_modulo_v1` extraction profile and
the VERSION=2 ISCI container in `C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis`. Nothing in
`C:\Users\bhoom\Desktop\ISC_PBL` (Step 1.1, frozen) was modified.

Backups of every file below, as they stood immediately before this session's first edit, are at
`C:\Users\bhoom\Desktop\phase3a_backups_20261111\` (same relative paths). Baseline SHA-256 hashes
were recorded before any edit; see `phase_3a_validation_results.md §1`.

---

## Modified files

### `isc_cipher/kdf.py`

- **Original responsibility:** key validation, RFC 5869 HKDF-SHA-256, `context()` domain-separation
  string, `Derivation` (mac/kcv/iv/lane-seed derivation).
- **Exact change:** `context(profile, dtype, h, w, c)` → `context(profile, dtype, h, w, c,
  extraction=None)`. `extraction=None` (the default) returns the identical 17-byte string as
  before. `extraction=1` or `2` appends one byte, producing an 18-byte VERSION=2 context.
  Invalid `extraction` values (anything other than `None`, `1`, `2`) raise `ValueError`.
- **Reason:** `hkdf_profile_binding_specification.md §2-3` (Decision F4) — bind the VERSION=2
  extraction choice into every derived key/seed so profile confusion is cryptographically
  impossible, not just tag-rejected.
- **Backward-compatibility impact:** none. No existing call site passes `extraction`; `hkdf_extract`,
  `hkdf_expand`, `Derivation`, `STREAMS`, `LANES`, `CONTEXT_PREFIX` are untouched.
- **Tests validating this change:** `tests/test_isc_cipher_extraction_profiles.py::
  test_context_extraction_none_matches_v1`, `test_context_extraction_appends_one_byte`,
  `test_context_invalid_extraction_rejected`, `test_context_v1_derivation_unchanged_for_every_existing_call_shape`,
  `test_derived_mac_keys_differ_between_v2_extraction_1_and_2`,
  `test_derived_lane_seeds_differ_between_v2_extraction_1_and_2`,
  `test_v1_ctx_binding_differs_from_v2_extraction_1_ctx_binding`. Also exercised transitively by
  every existing `tests/test_isc_cipher_kdf_state.py` test (unmodified, still passing).

### `isc_cipher/container.py`

- **Original responsibility:** `Header` dataclass, `pack()`/`parse()`, VERSION=1 format constants.
- **Exact change:**
  - Added `VERSIONS = (1, 2)`, `EXTRACTIONS = (1, 2)`, `HEADER_LEN_V1 = 36`, `HEADER_LEN_V2 = 37`,
    and a `header_len(version)` helper. `HEADER_LEN = 36` is **kept, unchanged**, because
    `isc_eval/constructions.py:101` references it directly and only ever handles VERSION=1.
  - `Header` gained two fields with defaults that reproduce current behaviour: `version: int = 1`,
    `extraction: int = 1`.
  - `Header.pack()` now branches on `self.version`: V1 packs exactly as before (36 bytes); V2 packs
    37 bytes (adds the `EXTRACTION` byte at offset 36). Rejects `version=1` paired with
    `extraction != 1`, and `version=2` paired with an extraction outside `{1, 2}`.
  - `parse()` was **restructured** (not just extended) per
    `container_v2_binary_specification.md §4` item 2: it now reads `MAGIC`+`VERSION` first (needs
    only 5 bytes), rejects unsupported versions immediately, selects `header_len` from the version,
    *then* applies the length/field checks — rather than checking length against a single
    module-level constant before the version is known, as the original code did.
- **Reason:** `container_v2_binary_specification.md §3-5` (Decisions F2, F3) — append the new field
  after KCV (offset 36) rather than inserting it between existing fields, and support both
  extraction identifiers under VERSION=2.
- **Backward-compatibility impact:** every VERSION=1 byte string is parsed identically to before
  (same offsets, same field meanings, same exceptions for the same malformed inputs); the only
  behavioural difference for V1 input is that `parse()` now reaches its conclusions via a different
  (but equivalent) code path.
- **Flagged conflict discovered and resolved:** none for this file; see the `cipher.py` entry below
  for the one real compatibility conflict found during implementation.
- **Tests validating this change:** `test_header_v1_serialization_byte_for_byte`,
  `test_header_v2_serialization_byte_layout_and_offsets`, `test_header_v1_rejects_non_default_extraction`,
  `test_header_v2_rejects_unknown_extraction`, `test_parse_valid_v1`, `test_parse_valid_v2`,
  `test_parse_unknown_version_rejected`, `test_parse_unknown_extraction_rejected_under_v2`,
  `test_parse_truncated_v1_header_rejected`, `test_parse_truncated_v2_header_rejected`,
  `test_parse_body_length_mismatch_v1_rejected`, `test_parse_body_length_mismatch_v2_rejected`.
  Also every existing `tests/test_isc_cipher_auth.py::test_malformed_ciphertexts` case (unmodified)
  and `test_header_layout` still pass against the restructured `parse()`.

### `isc_cipher/generator.py`

- **Original responsibility:** lane burn-in, output-step scheduling, `m_byte` extraction,
  `RefStream`/`NpStream`/`build_streams`.
- **Exact change:**
  - Added `EXTRACTION_MANTISSA8_V1 = 1`, `EXTRACTION_K14_SCALED_MODULO_V1 = 2`,
    `EXTRACTIONS = (1, 2)`.
  - Added `frac_byte_scalar(v)`: pure-Python (`math.floor`, `abs`, `float`), no NumPy import,
    returns a plain `int` in `[0, 255]`. `import math` added at module scope; **no new import of
    `numpy` or `isc_seq` at module scope** — the reference backend remains NumPy-free.
  - `RefStream.__init__` gained `extraction=EXTRACTION_MANTISSA8_V1`; stores
    `self._extract` (looked up from a small dict `{1: m_byte, 2: frac_byte_scalar}`).
    `_output_step` calls `self._extract(x)`/`self._extract(y)` instead of the hardcoded `m_byte`.
  - `NpStream.__init__` gained the same `extraction` parameter. `take()` branches: the original
    bit-trick path is completely unchanged for `extraction=1`; for `extraction=2` it lazily imports
    `isc_seq.extract.frac_byte` and applies it to the same `xs, ys` arrays, then stacks the result
    with the identical `axis=-1` order as the original path, producing the same `(k, 64, 2)` byte
    layout (only the values differ, never the positions).
  - `build_streams(seeds, backend="numpy", profile=1, burn_in=BURN_IN,
    extraction=EXTRACTION_MANTISSA8_V1)` — one new keyword, threaded into `RefStream`/`NpStream`
    construction.
- **Reason:** `dual_profile_generator_design.md`, `extraction_backend_compatibility_specification.md
  §3-4` (Decisions F6, F7) — additive extraction selection at the one isolated byte-extraction
  boundary, dependency-free scalar path.
- **Backward-compatibility impact:** `build_streams(seeds, backend=X, profile=Y)` called with no
  `extraction` argument is byte-for-byte identical to the pre-Phase-3A function (verified directly,
  see `test_build_streams_default_extraction_byte_identical_to_pre_phase3a_baseline`), and Gate R's
  `R-stream-KAT`/`R-cipher-KAT` against the **original, untouched** vectors confirm this at the full
  cipher level.
- **Tests validating this change:** the full new-test-module generator section (scalar/vector
  equivalence, boundary values, NumPy-freedom of the scalar path, `RefStream`/`NpStream`
  byte-identity, default-path regression, stream length/ordering, state-advancement independence
  from extraction, invalid-identifier rejection) — see `phase_3a_validation_results.md §3`.

### `isc_cipher/cipher.py`

- **Original responsibility:** stage orchestration (`_materials`, `_build_generators`, `_encrypt`,
  `encrypt_bytes`/`decrypt_bytes`/`encrypt`/`decrypt`).
- **Exact change:**
  - `_materials(key, nonce, profile, h, w, c, backend, extraction=EXTRACTION_MANTISSA8_V1,
    ctx_extraction=None)` — `extraction` selects the generator's byte-extraction function;
    `ctx_extraction` (separate, explicit) controls whether/which value is folded into
    `kdf.context(...)`. Keeping these as two separate parameters (rather than one) is what allows a
    VERSION=2/extraction=1 ciphertext to bind extraction into its key schedule while a VERSION=1
    ciphertext's key schedule is completely untouched by the new axis.
  - `_build_generators(seeds, backend, profile, extraction=EXTRACTION_MANTISSA8_V1)` — **conditional
    forwarding**: calls `build_streams(seeds, backend=backend, profile=profile)` (the *exact*
    original 3-keyword call) when `extraction` is the default, and only passes the 4th keyword when
    it is not. See "Flagged conflict" below for why this matters.
  - `_encrypt(key, data, h, w, c, nonce, backend, profile, extraction=EXTRACTION_MANTISSA8_V1,
    version=None)` — `version=None` auto-selects VERSION=1 when `extraction` is the default and
    VERSION=2 otherwise; it can be set explicitly (e.g. `version=2` with `extraction=1`) to produce
    every valid combination for testing. VERSION=1 paired with a non-default extraction raises
    `ValueError` before any generator work.
  - `encrypt_bytes(key, data, h, w, c, backend=DEFAULT_BACKEND, extraction=EXTRACTION_MANTISSA8_V1)`
    and `encrypt(key, image, backend=DEFAULT_BACKEND, extraction=EXTRACTION_MANTISSA8_V1)` — the
    **public API** now exposes extraction selection directly (not only through a private/test-only
    helper), satisfying the task's explicit requirement, while every existing positional/keyword
    call shape is unaffected.
  - `decrypt_bytes` — reads `hdr.extraction`/`hdr.version` from the parsed header (never
    caller-supplied); computes `ctx_extraction = hdr.extraction if hdr.version == 2 else None` and
    `hl = container.header_len(hdr.version)` instead of the fixed `container.HEADER_LEN`.
- **Reason:** `phase_3a_implementation_plan.md` (`cipher.py` row), `hkdf_profile_binding_specification.md
  §5-6`.
- **Backward-compatibility impact:** `encrypt_bytes(key, data, h, w, c)` / `encrypt(key, image)`
  called exactly as before produce byte-identical VERSION=1 ciphertexts (verified,
  `test_v1_ciphertext_output_unchanged_byte_for_byte_vs_pre_phase3a_reference`, and the entire
  existing Gate C/Gate R suites against **unmodified** KAT vectors and tests).
- **Flagged conflict discovered and resolved (real, non-hypothetical):**
  `tests/test_isc_cipher_auth.py::test_kcv_detects_state_change_in_burn_in` (existing,
  **unmodified**, line 182-190) replaces the module-level name `build_streams` inside `cipher.py`
  with a 3-parameter fake `def build(seeds, backend, profile)`. Had `_build_generators` always
  forwarded a 4th `extraction=` keyword to `build_streams`, this fake would raise
  `TypeError: unexpected keyword argument 'extraction'` and the existing test would fail — a real
  backward-compatibility break that only the actual source code (not the design documents) revealed.
  Resolved with the smallest possible change: `_build_generators` only passes `extraction=` when it
  is not the default value, so the exact original 3-keyword call shape is preserved for every
  existing caller and every existing monkeypatch. Verified: the full, unmodified Gate C suite
  (including this specific test) passes after the change (`phase_3a_validation_results.md §2`).
- **Tests validating this change:** the full new-test-module cipher-integration section
  (`test_v1_roundtrip_unaffected`, `test_v2_extraction_1_roundtrip`, `test_v2_extraction_2_roundtrip`,
  `test_public_encrypt_bytes_exposes_extraction_selection`,
  `test_public_encrypt_bytes_default_still_v1_mantissa8`,
  `test_v1_and_v2_extraction1_ciphertexts_differ_despite_same_extraction_method`,
  `test_no_generator_work_before_authentication_for_v2`,
  `test_kcv_present_and_distinguishes_profiles_under_both_versions`,
  `test_v1_ciphertext_output_unchanged_byte_for_byte_vs_pre_phase3a_reference`,
  `test_tampered_extraction_byte_rejected_before_generator`, `test_tampered_version_byte_rejected`)
  plus the complete, unmodified `tests/test_isc_cipher_auth.py` battery.

### `isc_cipher/_testing.py`

- **Original responsibility:** `encrypt_bytes_with_nonce_TEST_ONLY`, `materials_TEST_ONLY` — the
  fixed-nonce entry points used only by tests and KAT generation/verification.
- **Exact change:** both functions gained `extraction=EXTRACTION_MANTISSA8_V1` and `version=None`
  keyword parameters, threaded straight into `_encrypt`/`_materials`. `materials_TEST_ONLY`
  replicates `_encrypt`'s `version=None` auto-selection logic so its `ctx_extraction` matches what
  `_encrypt` would actually use for the same inputs.
- **Reason:** required so the new KAT generator (`make_kat_k14.py`) and Gate R extension
  (`gate_r_k14.py`) can request the new profile; required by the new test module.
- **Backward-compatibility impact:** none — defaults reproduce the exact prior signatures'
  behaviour; every existing call site in `tests/*.py`, `isc_cipher_kat/*.py`, `isc_eval/*.py`,
  `experiments/demo_show_keystream.py` passes none of the two new keywords and is unaffected.

## Unmodified files (verified by SHA-256, unchanged from the recorded pre-implementation baseline)

- `isc_cipher/selftest.py` — **no change**, per the explicit recommendation in
  `phase_3a_implementation_plan.md` (`selftest.py` row): the existing self-test does not test byte
  extraction for *either* profile today (it stops at the trajectory level), so adding
  `k14_scaled_modulo_v1` support does not create a parity gap. An extraction-level self-test for
  either profile remains a deferred, future capability, not a Phase 3A requirement.
- `isc_cipher/isc_step.py`, `isc_cipher/state_map.py`, `isc_cipher/sampling.py`,
  `isc_cipher/diffusion.py`, `isc_cipher/fdlibm_ref.py`, `isc_cipher/fdlibm_np.py` — untouched;
  the ISC recurrence, state mapping, sampling, and diffusion are unaffected by the extraction axis
  by design.
- `isc_seq/extract.py` — untouched. It becomes a new, lazily-imported, optional runtime dependency
  of `isc_cipher.generator`'s NumPy path only (not of the reference path) — a new cross-package
  dependency direction that did not exist before (previously `isc_seq` depended on nothing in
  `isc_cipher` and vice versa).
- `isc_cipher_kat/make_kat.py`, `isc_cipher_kat/gate_r.py` — untouched (hash-verified, see
  `phase_3a_validation_results.md §1`). The open design question from `phase_2_closure_audit.md §7`
  ("extend `gate_r.py` or write a parallel script") was resolved in favour of **parallel scripts**
  (`make_kat_k14.py`, `gate_r_k14.py`): this gives the new profile its own KAT generation/
  verification path with zero risk of altering the existing, already-passing mantissa8_v1 checks.
- Every file under `C:\Users\bhoom\Desktop\ISC_PBL` — untouched (Step 1.1 is frozen).

## New files

- `isc_cipher_kat/make_kat_k14.py` — generates `vectors/stream_kat_k14.json` (independent: the ISC
  trajectory comes from the same C oracle `make_kat.py` already uses, run fresh via WSL in this
  session; only the byte-extraction step, applied in Python afterward, is new) and
  `vectors/cipher_kat_k14.json` (self-generated by the R1 reference backend, analogous to the
  existing `cipher_kat.json`, explicitly labelled "NOT independent"). Refuses to overwrite existing
  files, including its own outputs on a second run. Does **not** regenerate `trig_kat.txt.gz` or
  `traj_kat.json`: those vectors test the ISC recurrence/trigonometric evaluation, which the
  extraction axis does not affect, so they are fully reused as-is.
- `isc_cipher_kat/gate_r_k14.py` — verifies `stream_kat_k14.json` and `cipher_kat_k14.json` against
  both backends, plus a direct reference-vs-numpy ciphertext byte-equality cross-check
  (`--backend both`). Does not touch or re-invoke any of `gate_r.py`'s own checks.
- `isc_cipher_kat/vectors/stream_kat_k14.json`, `isc_cipher_kat/vectors/cipher_kat_k14.json` — the
  new KAT vectors themselves (generated and verified this session; see
  `phase_3a_validation_results.md §4`).
- `tests/test_isc_cipher_extraction_profiles.py` — new test module (51 tests) covering KDF context
  binding, container VERSION=1/2 parsing, generator scalar/vector compatibility, and cipher
  integration, per `phase_3a_implementation_plan.md`'s suggestion to collect these scattered
  requirements into one coherent module.
