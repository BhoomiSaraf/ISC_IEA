# Phase 3A Implementation Plan — File-by-File Specification (Design Only, Not Implemented)

**Document ID:** `ISC-PHASE3A-PLAN-2026-02`
**Date:** 11 November 2026
**Status:** Planning document. No source file listed below has been modified in producing this plan.

---

## 1. File-by-file specification

### `isc_cipher/generator.py`

- **Existing responsibility:** burn-in, lane scheduling, byte extraction (`mantissa8_v1` only, today),
  stream construction (`RefStream`, `NpStream`, `build_streams`).
- **Proposed change:**
  1. Add `EXTRACTION_MANTISSA8_V1 = 1`, `EXTRACTION_K14_SCALED_MODULO_V1 = 2` module constants.
  2. Add `frac_byte_scalar(v)` (per `extraction_backend_compatibility_specification.md §3`) — pure Python,
     no new import at module scope (import `isc_seq.extract.frac_byte` lazily inside the vectorized branch
     only, to avoid making `isc_seq` a hard dependency of the reference backend).
  3. `RefStream.__init__` gains an `extraction` parameter (default `EXTRACTION_MANTISSA8_V1`); stores
     `self._extract = {EXTRACTION_MANTISSA8_V1: m_byte, EXTRACTION_K14_SCALED_MODULO_V1:
     frac_byte_scalar}[extraction]`. `_output_step` (`generator.py:46-54`) replaces hardcoded `m_byte(x)`/
     `m_byte(y)` with `self._extract(x)`/`self._extract(y)`.
  4. `NpStream.__init__` gains the same `extraction` parameter; `take()` (`generator.py:82-103`) branches
     at the line currently computing `mb = np.stack(...).view(np.uint64); new = (...)` (L97-98) between the
     existing bit-trick and the new `frac_byte`-based path (per
     `extraction_backend_compatibility_specification.md §4`).
  5. `build_streams(seeds, backend="numpy", profile=1, burn_in=BURN_IN, extraction=EXTRACTION_MANTISSA8_V1)`
     — add the new keyword, threaded into `RefStream`/`NpStream` construction (`generator.py:120,133-134`).
     **`burn_in` is already a keyword parameter today — no change needed there.**
- **Public API impact:** `build_streams`'s signature gains one optional keyword with a default that
  preserves current behavior exactly for every existing call site (`cipher.py:38`, `isc_eval/exp_nist.py:36`,
  any test). No existing call site requires edits.
- **Backward-compatibility requirement:** calling `build_streams(seeds, backend=X, profile=Y)` with no
  `extraction` argument must produce **byte-identical** output to the current, unmodified code, for every
  `(seeds, X, Y)` — this is the single most load-bearing regression guarantee in the whole plan.
- **Associated unit tests:** new `test_frac_byte_scalar_matches_frac_byte` (parametrized over a large
  sample, per `extraction_backend_compatibility_specification.md §7` item 1); new
  `test_build_streams_extraction_default_unchanged` (byte-for-byte regression, item 4); new
  `test_k14_extraction_refstream_npstream_equivalence` (item 2).
- **Associated integration tests:** full-cipher roundtrip under `extraction=EXTRACTION_K14_SCALED_MODULO_V1`
  (new), alongside the existing roundtrip tests which continue to run unmodified for `mantissa8_v1`.
- **Expected failure modes if implemented incorrectly:** (a) accidentally changing the *default* value of
  `extraction` anywhere would silently break every existing KAT vector — caught immediately by Gate R;
  (b) a shape mismatch in the `frac_byte`-based `NpStream.take` branch would raise a NumPy broadcasting
  error at runtime, not silently produce wrong output — a loud, not silent, failure mode.

### `isc_cipher/cipher.py`

- **Existing responsibility:** stage orchestration (`_materials`, `_encrypt`, `encrypt_bytes`,
  `decrypt_bytes`), reading `hdr.profile` from the parsed header and threading it through.
- **Proposed change:** `_materials(key, nonce, profile, h, w, c, backend)` (`cipher.py:33-44`) gains an
  `extraction` parameter, passed to `context(...)` (for `ctx` binding, per
  `hkdf_profile_binding_specification.md §3`) and to `_build_generators`/`build_streams` (`cipher.py:38,47-49`).
  `_encrypt` (`cipher.py:56-70`) gains an `extraction` parameter (default
  `EXTRACTION_MANTISSA8_V1`), used to build a V1 or V2 header depending on whether
  `extraction != EXTRACTION_MANTISSA8_V1` or a caller explicitly requests V2. `decrypt_bytes`
  (`cipher.py:78-94`) reads `hdr.extraction` from the parsed header (new field, defaulting to `1` for V1
  headers per `container_v2_binary_specification.md §4` item 3) and passes it through — **no caller-supplied
  extraction parameter on decryption**, exactly mirroring how `profile` already works today (self-describing
  from the ciphertext, not caller-chosen).
- **Public API impact:** `encrypt_bytes`/`encrypt` (`cipher.py:73-75,113-116`) — **recommend leaving the
  existing public signature unchanged by default** (still produces V1/`mantissa8_v1` ciphertexts unless a
  new, explicitly-named parameter or a separate function, e.g. `encrypt_bytes_v2(...)`, is added) — this is
  an **open design choice** (see `phase_2_final_decision_log.md`), not resolved here, because the task's own
  Section 2 open question ("should k14 ever be the default") is explicitly unresolved and should not be
  pre-empted by this plan.
- **Backward-compatibility requirement:** `encrypt_bytes(key, data, h, w, c)` called exactly as today must
  produce a ciphertext decryptable by the **current, unmodified** `decrypt_bytes` and vice versa — trivially
  true if the public signature is left unchanged, per the above.
- **Associated unit tests:** extend `tests/test_isc_cipher_auth.py`'s tamper-test battery to include
  "modified EXTRACTION byte rejected" (new, analogous to the existing `test_profile_field_change_rejected`);
  extend the `no_generator` fixture battery to cover the new field.
- **Associated integration tests:** full V2 roundtrip (encrypt→decrypt, `k14_scaled_modulo_v1`); mixed
  negative tests (V2 ciphertext with V1 parser expectations, and vice versa — both must fail cleanly per
  `container_v2_binary_specification.md §5`).
- **Expected failure modes:** omitting the `extraction`→`ctx` wiring would mean `EXTRACTION` is
  tag-protected but not key-schedule-bound (Defense 1 without Defense 2, per
  `hkdf_profile_binding_specification.md §5`) — not a correctness bug, but a weaker guarantee than
  recommended; must be caught by design review, not just tests (a test cannot easily distinguish "tag-only
  protection" from "tag+ctx protection" without specifically checking that `k_mac` differs across
  `extraction` values, which should itself be an explicit test).

### `isc_cipher/kdf.py`

- **Existing responsibility:** key check, HKDF extract/expand, `context()`, `Derivation`, seed derivation.
- **Proposed change:** `context(profile, dtype, h, w, c, extraction=None)` — additive parameter, per
  `hkdf_profile_binding_specification.md §2-3`. No other change; `Derivation`, `hkdf_extract`,
  `hkdf_expand`, `lane_label`, `STREAMS`, `LANES` are all **unaffected** (confirmed in
  `dual_profile_generator_design.md §2`, re-verified this session by direct reading of the full file).
- **Public API impact:** `context()`'s signature gains one optional keyword with a `None` default that
  reproduces the exact current 17-byte output — no existing call site requires edits.
- **Backward-compatibility requirement:** `context(profile, dtype, h, w, c)` (4 positional args as today)
  must return byte-identical output to the current code for every input.
- **Associated unit tests:** new `test_context_extraction_none_matches_v1` (exact byte equality);
  new `test_context_extraction_appends_one_byte` (length and content check for the V2 branch).
- **Associated integration tests:** none beyond what `cipher.py`'s tests already cover (this is a pure
  utility function; its correctness is fully exercised transitively through the cipher-level tests).
- **Expected failure modes:** an off-by-one in the appended byte's position would be caught immediately by
  the exact-byte-equality unit test, not silently.

### `isc_cipher/container.py`

- **Existing responsibility:** `Header` dataclass, `pack()`, `parse()`, format constants.
- **Proposed change:** per `container_v2_binary_specification.md §4` in full — `VERSIONS = (1, 2)` (or
  equivalent), `Header.extraction: int = 1` new field, `parse()` restructured to read `VERSION` before
  computing `HEADER_LEN` (a genuine control-flow change, not cosmetic — see that document's exact
  before/after description), `Header.pack()` branching on version to emit 36 or 37 header bytes.
- **Public API impact:** `Header`'s constructor gains a field with a default — existing call sites
  (`cipher.py:68`) that construct `Header(profile=..., c=..., h=..., w=..., nonce=..., kcv=...)` without
  `extraction=` continue to work, defaulting to `1`.
- **Backward-compatibility requirement:** `parse()` on any **existing, previously-valid V1 ciphertext byte
  string** must return the exact same `(Header, body, tag)` tuple as today — this is directly testable by
  re-running every existing roundtrip/auth test unmodified against the new `parse()`.
- **Associated unit tests:** every row of `container_v2_binary_specification.md §5`'s behavior table as a
  distinct test case (valid V1, valid V2, unknown version, unknown extraction, truncated header at both
  header lengths, tampered extraction byte, tampered version byte, length mismatch at both header lengths).
- **Associated integration tests:** full encrypt/decrypt roundtrip for both versions (covered under
  `cipher.py`'s integration tests above; listed here for cross-reference completeness).
- **Expected failure modes:** the version-before-length-check restructuring (per
  `container_v2_binary_specification.md §4` item 2) is the highest-risk single change in this entire plan —
  an off-by-one here could cause a V1 ciphertext shorter than 37 bytes (impossible in practice since
  `HEADER_LEN+1+TAG_LEN = 69` minimum, but hypothetically) to be misread. Must be covered by explicit
  boundary-length tests, not just "happy path" roundtrips.

### `isc_cipher/selftest.py`

- **Existing responsibility:** profile-1 self-test (sin/cos + short trajectory), **does not touch byte
  extraction at all** (re-confirmed this session, §5 of `phase_2_closure_audit.md`).
- **Proposed change:** **none required** for `mantissa8_v1` to remain covered (re-confirmed, not merely
  repeated from session 1). **A new, additive self-test path is needed** if `k14_scaled_modulo_v1` is to be
  made normative/self-tested — this would require new expected values in `_selftest_vectors.py` for a
  byte-extraction check, which does not exist today for *either* profile (the self-test, per its own
  module docstring, stops at the trajectory level, before extraction — this is true for `mantissa8_v1` too,
  so adding an extraction-level self-test would be a **new capability**, not a parity gap specific to k14).
- **Public API impact:** `run_selftest(profile, backend)`'s signature is unaffected by the extraction axis
  unless/until an extraction-level check is added; if added, it would need its own parameter or be folded
  into a combined `(profile, extraction, backend)` key for the `_DONE` memoization set (`selftest.py:13`).
- **Recommendation:** defer adding an extraction-level self-test to a later phase; it is not required for
  Phase 3A's "preserve legacy reproducibility + add k14 as a working, tested, but not yet self-test-covered
  option" goal, consistent with `dual_profile_generator_design.md §7`'s open question about whether k14
  should be fully normative yet.

### `isc_seq/extract.py`

- **Existing responsibility:** `frac_byte` and sibling research extraction functions; **not** a dependency
  of `isc_cipher` today (confirmed, no import found).
- **Proposed change:** **none to this file itself.** It becomes a **new runtime dependency of
  `isc_cipher.generator`** (specifically, of the `NpStream` extraction branch only, imported lazily — see
  `generator.py`'s plan above) — this is a **cross-package dependency direction that does not exist today**
  and should be noted explicitly: today, `isc_seq` depends on nothing in `isc_cipher`, and `isc_cipher`
  depends on nothing in `isc_seq`. Adding this import makes `isc_cipher` depend on `isc_seq` for one
  optional code path. **This has packaging/migration implications**: per `repository_migration_plan.md
  §7`, both packages already resolve via a shared repo-root-on-`sys.path` mechanism, so this is not
  expected to break anything *within* the existing repository structure, but it is a new coupling worth
  recording explicitly (not previously flagged this precisely in session 1's documents, which treated
  `frac_byte` reuse as a given without naming the new inter-package dependency it creates).

### CLI / public API entry points

- `encrypt(key, image, backend=...)` / `decrypt(key, ciphertext, backend=...)` (`cipher.py:113-124`): no
  change needed if the extraction-selection API is added only to `encrypt_bytes`/`_encrypt` and these
  thin wrappers continue to delegate, per the open design choice above.
- No standalone CLI script for the cipher itself was found in this or the prior session's inspection
  (`isc_cipher_kat/make_kat.py`, `gate_r.py` are the closest things to CLIs, both KAT-infrastructure, not
  encryption entry points).

### KAT infrastructure (`isc_cipher_kat/make_kat.py`, `gate_r.py`, and siblings)

- **Existing responsibility:** generate (`make_kat.py`) and verify (`gate_r.py`) known-answer vectors for
  `mantissa8_v1` under profile 1.
- **Proposed change:** **no change to existing vectors or existing check logic for `mantissa8_v1`** (per
  `cipher_integration_impact_analysis.md §7`, re-confirmed this session via a fresh Gate R run — see §2
  below). **New, separate KAT vectors** must be generated for `k14_scaled_modulo_v1` via `make_kat.py`'s
  existing generation logic, parameterized by the new `extraction` axis — this likely requires `make_kat.py`
  itself to gain an `extraction`/`--extraction` parameter (not inspected line-by-line beyond its header in
  this session; its full internals were flagged as an open item in session 1's
  `dual_profile_generator_design.md §3` and remain so here — **this file's full internals should be read
  before Phase 3A implementation begins**, as the first concrete implementation sub-task).
- **Associated unit/integration tests:** `gate_r.py --backend numpy --label <run>` must be extended to
  optionally check a second (`extraction=2`) vector set, without removing or altering its existing
  `mantissa8_v1` checks.

### Tests for both backends / both container versions

- New test file (suggested name, not mandatory): `tests/test_isc_cipher_extraction_profiles.py`, covering:
  cross-backend equivalence (§ generator.py above), container V1/V2 parsing (§ container.py above), ctx
  binding (§ kdf.py above), and full roundtrips for the new profile — collecting the scattered test
  requirements named throughout this plan into one coherent new test module, analogous to how the existing
  `test_isc_cipher_{auth,kdf_state,numeric,roundtrip,sampling_diffusion}.py` are already organized by
  concern.

### Additional affected files discovered during this session's inspection

- `isc_eval/exp_nist.py` (`message_streams`, `single_lane_sequences`, `a12`) — calls `build_streams(seeds,
  backend="numpy", profile=1)` with no `extraction` argument (`exp_nist.py:36`); will continue to work
  unmodified (defaults preserved) but **should** eventually gain an `extraction` parameter to let Gate A's
  A12 experiment be run against `k14_scaled_modulo_v1` too — flagged as a **Phase 3B**, not Phase 3A, task,
  consistent with `phase_3b_validation_readiness.md`.
- No other call sites to `build_streams`, `context`, or `Header` were found beyond `cipher.py` and
  `exp_nist.py` in the files actually read in this and the prior session; a repository-wide grep for all
  call sites of these three symbols is recommended as the **first concrete step of Phase 3A** (not
  performed exhaustively in this closure session — flagged as `[OPEN — recommend a `grep -rn
  "build_streams\|container\.Header\|kdf\.context"` across the whole `sine_chebyshev_ikeda_analysis` tree
  before writing any code]`).

---

## 2. Invariants that must be preserved (restated precisely, cross-referenced to verifying tests)

| Invariant | Verified today by | Must remain true after Phase 3A |
|---|---|---|
| ISC recurrence unchanged | `isc_step.py` untouched by this plan | Gate R `R-trig-KAT`, `R-trajectory-KAT` |
| State initialization unchanged | `state_map.py` untouched | Gate R `R-stream-KAT` |
| Four-stream architecture unchanged | `kdf.py: STREAMS` untouched | Gate R `R-stream-KAT`, Gate C `test_isc_cipher_kdf_state.py` |
| 64 lanes/stream unchanged | `kdf.py: LANES` untouched | same |
| Existing 1,024 burn-in default unchanged | `generator.py: BURN_IN` constant untouched; only the *default* value of the already-existing `burn_in` parameter matters | Gate R `R-stream-KAT` |
| Sampling algorithms unchanged | `sampling.py` untouched | Gate C `test_isc_cipher_sampling_diffusion.py` |
| Fisher–Yates unchanged | `sampling.py` untouched | same |
| Diffusion equations unchanged | `diffusion.py` untouched | Gate C `test_isc_cipher_sampling_diffusion.py` |
| HMAC authentication unchanged | `cipher.py`'s tag computation mechanism untouched (only its *inputs*, i.e. `hdr`, change when `EXTRACTION` is added — but the mechanism itself does not) | Gate C `test_isc_cipher_auth.py` |
| Legacy encryption/decryption output unchanged | Default-preserving signatures throughout | Gate R `R-cipher-KAT`, Gate C `test_isc_cipher_roundtrip.py` |
| Existing VERSION=1 container bytes unchanged | `container.py` V1 branch produces byte-identical output | Gate R `R-cipher-KAT` |
| Existing KAT vectors unchanged | No file in `isc_cipher_kat/vectors/` is edited; `make_kat.py` itself already "refuses to overwrite existing vectors" (confirmed this session, `phase_2_closure_audit.md §5`) | Gate R, re-run after every implementation step |

---

## 3. Recommended implementation order (summary; full ordered sequence given in the Final Response Part F)

1. Read `isc_cipher_kat/make_kat.py` and `make_kat_ext.py` fully (currently only their headers have been
   read across both sessions) — first concrete sub-task, before writing any production code.
2. Implement `kdf.py: context()` additive change + its two new unit tests. Run Gate C — must still pass
   unchanged (proves no regression from this step alone).
3. Implement `container.py` V2 layout + `Header.extraction` field + restructured `parse()` + its full
   behavior-table test suite. Run Gate C again.
4. Implement `generator.py` extraction-selection branch (both backends) + regression test (byte-identical
   default output) + cross-backend equivalence test. Run Gate C and Gate R again — **this is the step most
   likely to reveal an unanticipated issue**, given it touches the most performance/shape-sensitive code.
5. Implement `cipher.py` wiring (`_materials`, `_encrypt`, `decrypt_bytes` extraction threading) + new
   auth-tamper tests for the `EXTRACTION` field. Run full Gate C.
6. Generate new KAT vectors for `k14_scaled_modulo_v1` via the (now-understood, per step 1) `make_kat.py`.
   Run Gate R against both vector sets.
7. Run Gate A (`isc_eval` harness) to confirm no regression in the comparative/attack test suite (none of
   this plan's changes should affect it, since it defaults to `mantissa8_v1` throughout, but this must be
   **verified by running it**, not assumed).
8. Only after steps 1-7 are complete and all gates pass: begin Phase 3B statistical validation
   (`phase_3b_validation_readiness.md`) and the burn-in experiment (`burn_in_experiment_protocol.md`),
   both of which are now unblocked by `build_streams`'s pre-existing `burn_in` keyword and the new
   `extraction` keyword.
