# ISCI Container Binary Specification — VERSION=1 (existing, unchanged) and VERSION=2 (proposed)

**Document ID:** `ISC-PHASE2-CONTAINERV2-2026-02`
**Date:** 11 November 2026
**Source verified directly:** `isc_cipher/container.py` (73 lines, read in full this session),
`isc_cipher/cipher.py` (125 lines, read in full this session).

---

## 1. VERSION=1 layout — exact, re-verified against source (not merely cited from Phase 1/session 1)

`[VERIFIED SOURCE]` — the module's own docstring (`container.py:1-15`) matches the code exactly;
independently re-derived field-by-field from `Header.pack()` (`container.py:44-46`) and `parse()`
(`container.py:54-72`):

| Field | Offset | Width | Encoding | Valid values | Authenticated? | Source |
|---|---|---|---|---|---|---|
| `MAGIC` | 0 | 4 | literal bytes | `b"ISCI"` | Yes (part of `hdr`, see §3) | `container.py:21,45,61` |
| `VERSION` | 4 | 1 | `uint8` | `1` only (constant `VERSION = 1`, `container.py:22`) | Yes | `container.py:45,63,66` |
| `PROFILE` | 5 | 1 | `uint8` | `{1, 2}` (`PROFILES = (1, 2)`, `container.py:24,66`) | Yes | `container.py:45,63,66` |
| `DTYPE` | 6 | 1 | `uint8` | `1` only (`DTYPE_UINT8 = 1`, `container.py:23,66`) | Yes | `container.py:45,63,66` |
| `C` | 7 | 1 | `uint8` | `{1, 3}` (`container.py:66`) | Yes | `container.py:45,63,66` |
| `H` | 8 | 2 | `uint16` big-endian | `1..65535` (`MAX_DIM`, `container.py:28,66`) | Yes | `container.py:45,64,66` |
| `W` | 10 | 2 | `uint16` big-endian | `1..65535` | Yes | `container.py:45,65,66` |
| `NONCE` | 12 | 16 | raw bytes | any 16 bytes (caller-supplied, `os.urandom(16)` in practice) | Yes | `container.py:46,71` |
| `KCV` | 28 | 8 | raw bytes (truncated HMAC-SHA256) | any 8 bytes | Yes | `container.py:46,71` |
| **`HEADER_LEN`** | **36** | — | — | constant (`container.py:25`) | — | — |
| `BODY` | 36 | `n = H·W·C` | raw ciphertext bytes | `n ≤ MAX_N = 2^24` (`container.py:27,69`) | Yes | `cipher.py:69,84` |
| `TAG` | `36+n` | 32 | HMAC-SHA-256 digest | — | — (it IS the authentication) | `container.py:26`, `cipher.py:69,84-86` |

**Authentication coverage, verified precisely from `cipher.py`, not assumed:** `cipher.py:69`:
`tag = hmac.new(m["k_mac"], hdr + body, hashlib.sha256).digest()` — the tag covers **the entire 36-byte
header concatenated with the entire body**, i.e. every field above offset 0-35 plus the body, confirmed on
the decrypt side too: `cipher.py:84`: `expected = hmac.new(der.mac_key(), z[:container.HEADER_LEN +
hdr.n], hashlib.sha256).digest()` — slices `z[0 : 36+n]`, i.e. exactly header+body, matching the encrypt
side's input exactly. **Every byte of the 36-byte header is authenticated; none of it is "metadata only."**

**Backward-compatibility implication of VERSION=1 itself:** `parse()` (`container.py:54-72`) hard-rejects
(`raise Malformed`) any ciphertext where `version != VERSION` (i.e. `!= 1`) at line 66, **before** computing
`n` or validating body length. This means: **a VERSION=2 ciphertext submitted to today's unmodified
`parse()` is already correctly rejected as malformed** (not silently misinterpreted) — a VERSION bump is a
safe, already-supported rejection path for anything that isn't exactly `VERSION=1`.

---

## 2. Verifying the 36-byte premise (per this task's explicit instruction not to assume it)

`[VERIFIED SOURCE, independently recomputed]`: `4 (MAGIC) + 1 (VERSION) + 1 (PROFILE) + 1 (DTYPE) + 1 (C) +
2 (H) + 2 (W) + 16 (NONCE) + 8 (KCV) = 36`. This matches `HEADER_LEN = 36` (`container.py:25`) exactly —
**the premise is correct, confirmed by direct field-width summation against the live constant, not merely
trusted from the Phase 2 session 1 documents' citation of the same number.**

---

## 3. Where should the new `EXTRACTION` byte go? — corrected recommendation

`[CORRECTION to `dual_profile_generator_design.md §4`]`: the prior session's document said the new field
should be added "immediately after the existing `DTYPE`/`C` fields or appended before the tag," without
picking one. Having now re-derived the exact byte offsets in §1, there is a materially better choice than
inserting the field *between* existing fields:

**Recommendation: append `EXTRACTION` as a 37th byte, at offset 36, immediately after `KCV` and before the
body — not inserted between any existing fields.**

Rationale:
- Inserting between existing fields (e.g. after `C` at offset 7) would shift `H`, `W`, `NONCE`, `KCV` all
  by one byte, requiring every line of `Header.pack()` and `parse()` that reads a fixed offset to be
  re-derived and re-tested (`container.py:45-46, 63-64, 71`), and would make a future human reader need to
  remember that "offset 8 means `H` under V1 but `EXTRACTION` under V2" — a persistent source of error.
- **Appending at the end of the header (offset 36) means offsets 0-35 are byte-for-byte identical in meaning
  between VERSION=1 and VERSION=2.** Only three things change: (a) the `VERSION` byte's value (1 vs 2), (b)
  `HEADER_LEN` becomes conditional on the parsed `VERSION` (37 for V2, 36 for V1), (c) one new field is
  read/written at the fixed offset 36 when, and only when, `VERSION=2`.
- This is the same pattern already used for extensible binary formats (TLV-free, fixed-field, with a
  version-gated trailing extension) and requires the **minimum possible diff** to `container.py`.

### Proposed VERSION=2 layout

| Field | Offset | Width | Encoding | Valid values | Authenticated? |
|---|---|---|---|---|---|
| `MAGIC` | 0 | 4 | literal | `b"ISCI"` | Yes |
| `VERSION` | 4 | 1 | `uint8` | `2` | Yes |
| `PROFILE` | 5 | 1 | `uint8` | `{1, 2}` (unchanged meaning — arithmetic engine) | Yes |
| `DTYPE` | 6 | 1 | `uint8` | `1` | Yes |
| `C` | 7 | 1 | `uint8` | `{1, 3}` | Yes |
| `H` | 8 | 2 | `uint16` BE | `1..65535` | Yes |
| `W` | 10 | 2 | `uint16` BE | `1..65535` | Yes |
| `NONCE` | 12 | 16 | raw | any | Yes |
| `KCV` | 28 | 8 | raw | any | Yes |
| **`EXTRACTION`** (new) | **36** | **1** | `uint8` | `{1 = mantissa8_v1, 2 = k14_scaled_modulo_v1}` | Yes (part of `hdr`, same mechanism) |
| **`HEADER_LEN_V2`** | **37** | — | — constant, version-conditional | — |
| `BODY` | 37 | `n` | raw | `n ≤ MAX_N` | Yes |
| `TAG` | `37+n` | 32 | HMAC-SHA-256 | — | — |

---

## 4. Exact code impact on `container.py` (file-level, not yet implemented — design only)

`[PROPOSAL]`:
1. `VERSION` (L22) becomes a tuple of supported versions, e.g. `VERSIONS = (1, 2)`, or `parse()` branches
   explicitly on the byte at offset 4 — **not** a single constant compared with `!=`, since two versions
   must now both be accepted.
2. `HEADER_LEN` (L25) can no longer be a single module-level constant used unconditionally by `parse()`
   before the version is known. **Concrete control-flow change required:** `parse()` (`container.py:54-72`)
   currently does `if len(z) < HEADER_LEN + 1 + TAG_LEN` (L59) **before** reading `version` at L63 — this
   ordering must change to: (a) check `len(z) >= 5` (enough to read `MAGIC`+`VERSION`), (b) read
   `version = z[4]`, (c) branch: `header_len = 36 if version == 1 else 37 if version == 2 else raise
   Malformed("unsupported version")`, (d) **then** apply the existing length/field checks using the
   version-appropriate `header_len`. This is a **real, non-trivial control-flow restructuring** of `parse()`,
   not a cosmetic change — flagged precisely here so the implementer does not underestimate it.
3. `Header` dataclass (`container.py:31-38`) gains an `extraction: int = 1` field with a **default of `1`**
   (`mantissa8_v1`) so that every existing call site that constructs a `Header` for a VERSION=1 ciphertext
   (`cipher.py:68`) needs **no change** — the default preserves current behavior exactly.
4. `Header.pack()` (`container.py:44-46`) must branch on whether `self` represents a V1 or V2 header (e.g.
   via a `version` field added to `Header` itself, or by the caller choosing which pack path to invoke) —
   **open design choice, not resolved here**, flagged in `phase_2_final_decision_log.md`.
5. `PROFILES = (1, 2)` (L24) is **unchanged in meaning** — this axis is orthogonal to the new `EXTRACTION`
   axis, per the recommendation already made in `dual_profile_generator_design.md §4` Option 1, re-confirmed
   here as still correct after re-deriving the exact byte layout.

---

## 5. Exact behavior specification for every required case (Task B requirement)

`[PROPOSAL — exact rules, not yet implemented]`:

| Case | Required behavior | Mechanism |
|---|---|---|
| Valid legacy (V1) ciphertext | Decrypts exactly as today; `extraction` implicitly `mantissa8_v1` | `parse()` branch sets `header_len=36`, `Header.extraction` defaults to `1`; generator path unchanged |
| Valid VERSION=2 ciphertext | Decrypts using the `EXTRACTION` value stored at offset 36 | `parse()` branch reads offset 36 when `version==2`; passed through to `build_streams` |
| Unknown version (e.g. 3, 0, 255) | `raise Malformed("unsupported version")` | New explicit check before any header-length-dependent logic |
| Unknown extraction identifier (e.g. 0, 3..255) under V2 | `raise Malformed("unsupported extraction identifier")` | New explicit check, analogous to the existing `profile not in PROFILES` check (`container.py:66`) |
| Truncated header (fewer than `header_len+1+TAG_LEN` bytes, for whichever version was read) | `raise Malformed("ciphertext too short")` | Same mechanism as today (`container.py:59`), applied with the version-appropriate `header_len` |
| Modified `EXTRACTION` byte in transit | Tag verification fails (`AuthenticationError`), **before** any decryption/generator work, exactly like a modified `PROFILE` byte today | Already guaranteed: offset 36 falls inside `hdr`, which is fully covered by the HMAC tag (§1) — no new code needed for this guarantee, only for *parsing* the new field correctly |
| Modified `VERSION` byte (e.g. V1→V2 or V2→V1) | Tag verification fails, because `ctx`/key derivation and/or header-length interpretation diverges — **must** fail, never silently reinterpret | See `hkdf_profile_binding_specification.md §3` for why this holds even if `VERSION` itself is not folded into `ctx` |
| Authentication failure (any field tampered) | `raise AuthenticationError("authentication failed")`, exactly as today (`cipher.py:85-86`), unconditionally before any generator/KCV work | Unchanged mechanism — the `no_generator` test fixture (`tests/test_isc_cipher_auth.py:27-31`) already proves this ordering holds for V1; an equivalent test must be added for V2 (see `phase_3a_implementation_plan.md`) |
| Header/body length mismatch | `raise Malformed("size limit exceeded or length mismatch")`, exactly as today (`container.py:69-70`), recomputed with the version-appropriate `header_len` | Same check, parameterized |
| **A VERSION=1 ciphertext must never be silently reinterpreted as VERSION=2, or vice versa** | Guaranteed structurally: the `version` byte at a fixed offset (4) is read first and used to select the *entire* subsequent parsing path; there is no code path where a V1 ciphertext's bytes are parsed using the V2 field layout or vice versa | This is the central non-negotiable constraint (task §12, item 5: "do not silently change defaults") — satisfied by construction of the branch-on-version design, not by convention |

---

## 6. Policy decision: should VERSION=2 permit both extraction identifiers, or require a restricted pairing?

`[RECOMMENDATION, with explicit justification, per the task's instruction to "recommend one explicit policy"]`:

**Recommendation: VERSION=2 permits both `EXTRACTION ∈ {1, 2}`.** Do **not** restrict VERSION=2 to only the
new extraction method.

Justification:
1. **Symmetry and testability.** If VERSION=2 could only mean `k14_scaled_modulo_v1`, there would be no way
   to produce a V2 ciphertext using `mantissa8_v1` for direct byte-for-byte comparison/regression testing
   against the V1 path using the *same* container code path — forcing a confusing situation where testing
   "does the V2 parser correctly handle `mantissa8_v1`" requires constructing a V1 ciphertext instead.
2. **Future extensibility.** If a *third* extraction method is ever added, a restricted V1↔V2 pairing policy
   would force a VERSION=3 bump for every new extraction method, re-coupling two independent axes exactly
   as `dual_profile_generator_design.md §4` already argued against for the `PROFILE` field. An explicit,
   unrestricted `EXTRACTION` byte under a single V2 format scales to N extraction methods without further
   container-format changes.
3. **No security or correctness reason to restrict.** Per `cipher_integration_impact_analysis.md §1-4`
   (re-confirmed structurally sound in this session by direct reading of `sampling.py`/`diffusion.py`
   logic), every structural invariant (permutation validity, invertibility, tamper detection) holds
   **regardless** of which extraction method is paired with which version — there is no code-correctness
   argument for restricting the pairing.
4. **Cost of the unrestricted policy:** `EXTRACTION` values must still be explicitly validated
   (`{1, 2}` only, rejecting anything else, per §5's "unknown extraction identifier" row) — this is already
   required either way, so there is no implementation cost difference between "allow both" and "restrict
   to one."

---

## 7. Open items not resolved in this document

`[OPEN/FOR APPROVAL]`:
- Exact Python-level representation of `Header` version-dependent fields (a single dataclass with optional
  fields vs. two dataclasses vs. a version-tagged union) — left to the implementer in Phase 3A.
- Whether `make_kat.py`/`gate_r.py` need a `--version` flag to generate/check V2 vectors, or whether a
  parallel `make_kat_v2.py` is cleaner — not decided here; see `phase_3a_implementation_plan.md`.
