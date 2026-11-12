# Dual-Profile Generator Design — `mantissa8_v1` vs `k14_scaled_modulo_v1`

**Document ID:** `ISC-PHASE2-DUALPROFILE-2026-01`
**Date:** 11 November 2026
**Status:** Design proposal only. Nothing in this document has been implemented.

---

## 1. Goal

Allow the existing 256-lane ISC-IMG v1 generator to produce keystream bytes using either:
- **`mantissa8_v1`** — the existing, shipped extraction (`generator.py:25-26`, `97-98`): bits 8-15 of the
  raw binary64 word. Must remain byte-for-byte reproducible against existing KAT vectors
  (`isc_cipher_kat/vectors/*.json`) and the existing self-test constants (`isc_cipher/_selftest_vectors.py`).
- **`k14_scaled_modulo_v1`** (new) — `B_n = floor(|x_n| × 10^14) mod 256`, implemented via
  `isc_seq.extract.frac_byte` (verified bit-exact equivalent to the Step 1.1 baseline; see
  `frac_byte_k14_compatibility_audit.md`), with its own new KAT vectors and self-test constants.

## 2. Components that do NOT need to change

`[RECOMMENDATION, grounded in §4-5 of `phase_2_source_code_architecture_audit.md`]`:

| Component | File | Why unaffected |
|---|---|---|
| Key validation | `kdf.py: check_key` | Operates before any generator code runs; extraction-agnostic. |
| HKDF key schedule | `kdf.py: Derivation, hkdf_extract/expand` | Produces seeds/keys from `(key, nonce, ctx)`; does not know or care how seeds are later turned into bytes. |
| Context/domain separation | `kdf.py: context()` | 17-byte ctx already includes `PROFILE` (see §4 below for why this field is the natural place to add the new identifier). |
| State mapping | `state_map.py` | Seed → `(x0,y0)` is upstream of the recurrence and extraction; untouched. |
| ISC recurrence | `isc_step.py: step_ref/step_vec` | Produces `(x,y)` state; extraction happens strictly after this, on the already-computed values. Changing the extraction function cannot change the recurrence's own output. |
| Burn-in count/loop | `generator.py:111-135 (build_streams)` | Burn-in advances state via `step_vec`/`step_ref`; it does not call the byte-extraction function at all (burn-in output is discarded, never extracted). |
| Lane scheduling / interleaving | `generator.py: NpStream.take, RefStream._output_step` | The round-robin two-bytes-per-lane order is a property of *how the loop iterates*, not of *what function converts a float to a byte* — only the one line that calls `m_byte`/the bit-trick needs a second branch. |
| Lemire sampling | `sampling.py` | Consumes already-extracted bytes as raw 32-bit words; agnostic to how those bytes were produced. |
| Fisher-Yates S-box/permutation | `sampling.py: build_sbox, build_permutation` | Same reasoning — operates on bytes already extracted. |
| Diffusion (forward/backward + inverses) | `diffusion.py` | Operates on `(q, a, b, S, iv_f, iv_b)`, all already-extracted-byte-derived; agnostic to extraction method. |
| Ciphertext body length/format | `container.py: HEADER_LEN, TAG_LEN, Header.pack/parse` | Unaffected — body length is `h*w*c`, independent of how keystream bytes were generated. |
| Authentication (HMAC order) | `cipher.py: _encrypt/decrypt_bytes` | Tag computed over header+body; extraction method is internal to how `a`/`b`/`S`/`pi` were derived, invisible to the MAC. |

## 3. Components that DO need to change

| Component | File | Change required |
|---|---|---|
| Byte extraction | `generator.py:25-26` (`m_byte`) and `96-98` (`NpStream.take` inline bit-trick) | Add a second function (`frac_byte`-derived) and branch on an extraction-mode parameter at exactly these two call sites. |
| `build_streams` signature | `generator.py:111` | Add an `extraction` (or reuse/extend `profile`, see §4) parameter, threaded into `RefStream`/`NpStream` construction so each stream's `take()`/`_output_step()` knows which extractor to call. |
| `RefStream` / `NpStream` classes | `generator.py:29-66`, `69-108` | Store the chosen extractor function (or an enum/flag) at construction; use it in `_output_step`/`take` instead of hardcoding `m_byte` / the bit-trick. |
| Container profile field semantics | `container.py: PROFILES = (1, 2)`, `Header.profile` | See §4 — must decide how to represent the new extraction choice without silently reinterpreting the existing `PROFILE` field (which currently means *numerical/arithmetic* profile: fdlibm vs. host libm, per `research/algorithm_design.md:468`, not *extraction* method). |
| Self-test vectors | `isc_cipher/_selftest_vectors.py`, `isc_cipher/selftest.py` | A new self-test path is needed for any new (profile, extraction) combination that is to be normative/self-tested, analogous to the existing profile-1 self-test. |
| KAT vectors | `isc_cipher_kat/vectors/stream_kat.json`, `cipher_kat.json` | New KAT vectors must be generated (via `isc_cipher_kat/make_kat.py`) for any new combination that should be reproducibility-checked by `gate_r.py`. Existing vectors are untouched and remain valid for `mantissa8_v1` (nothing about them changes). |
| `isc_seq.extract.frac_byte` call site | n/a — new adapter code in `generator.py` | Per `frac_byte_k14_compatibility_audit.md` §5: a thin shape adapter is needed, not a change to `frac_byte` itself. |

## 4. Profile/extraction identifier scheme

`[RECOMMENDATION]`: Investigation of `container.py:21-28` shows:
```python
VERSION = 1
PROFILES = (1, 2)
```
and `research/algorithm_design.md:468` documents: `PROFILE | 1 (normative) or 2 (comparison only)` — i.e.
**the existing `PROFILE` field is already overloaded to mean "numerical arithmetic profile" (fdlibm vs.
host libm)**, not "extraction method." Extraction method is currently *implicit* and fixed
(`mantissa8_v1` is the only one that exists), so there is no existing field for it at all.

**Two design options, with a recommendation:**

- **Option 1 (recommended): add extraction as an orthogonal axis, not a reinterpretation of `PROFILE`.**
  Keep `PROFILE ∈ {1, 2}` meaning exactly what it means today (arithmetic engine). Add a new header field,
  e.g. `EXTRACTION` (1 byte, values `1 = mantissa8_v1` (default/legacy), `2 = k14_scaled_modulo_v1`), to the
  36-byte `ISCI` header, immediately after the existing `DTYPE`/`C` fields or appended before the tag.
  - **Container format impact:** `HEADER_LEN` increases from 36 to 37 bytes; `container.py: Header` dataclass,
    `pack()`, `parse()` (`container.py:31-72`) all need the new field threaded through. `VERSION` should be
    bumped (e.g. to 2) so that old 36-byte headers are unambiguously rejected or unambiguously interpreted as
    `EXTRACTION=1` — **do not silently reinterpret existing `VERSION=1` ciphertexts**; the task explicitly
    forbids changing existing profile identifiers' meaning. A clean rule: `VERSION=1` ⇒ 36-byte header,
    `EXTRACTION` is implicitly `mantissa8_v1` (no behavior change, no code path change for legacy
    ciphertexts); `VERSION=2` ⇒ 37-byte header with an explicit `EXTRACTION` byte. This keeps every
    existing KAT vector (produced under `VERSION=1`) valid forever, unconditionally.
  - **Advantage:** `PROFILE` keeps its existing, already-documented meaning; no retroactive reinterpretation.
    Clean 2-axis matrix: `{PROFILE 1,2} × {EXTRACTION mantissa8_v1, k14_scaled_modulo_v1}` = 4 combinations,
    though only `PROFILE=1 × EXTRACTION∈{1,2}` is likely to be made normative/self-tested initially (profile 2
    is explicitly non-normative per `algorithm_design.md:549`, so pairing it with a new extraction is lower
    priority).
- **Option 2 (not recommended): overload `PROFILE` itself**, e.g. `PROFILE=3` meaning "fdlibm +
  k14_scaled_modulo." Rejected because it conflates two independent design axes (arithmetic engine vs. byte
  extraction) into one enum, makes the 4-combination matrix impossible to express cleanly if a third
  extraction method is ever proposed, and risks exactly the "silently reinterpreting existing profile
  identifiers" the task explicitly says not to do, if any future reviewer assumes `PROFILE` only ever meant
  arithmetic engine.

**Authentication of the new metadata:** per `kdf.py: context()` (`kdf.py:47-49`), `PROFILE` is already
folded into the 17-byte HKDF context string, which is itself bound into every derived key via
`Derivation.__init__`/`derive()` (`kdf.py:59-66`) — changing `ctx` changes every downstream key. The same
mechanism must cover the new `EXTRACTION` field: it should be added to `context()`'s input (e.g.
`ctx = CONTEXT_PREFIX || u8(PROFILE) || u8(EXTRACTION) || u8(DTYPE) || BE16(H) || BE16(W) || u8(C)`),
so that **the extraction choice is cryptographically bound into the key schedule itself**, not just
carried as unauthenticated metadata. In addition, the whole header (including the new field, wherever it
lives) is already covered by the existing HMAC tag computed over `hdr || body` (`cipher.py:69`,
`cipher.py:84`) — so even without being folded into `ctx`, tampering with the `EXTRACTION` byte in transit
would already be caught by tag verification before decryption proceeds. **Recommendation: do both** —
fold it into `ctx` (so a wrong `EXTRACTION` value derives entirely different, non-matching keys/keystream,
failing the KCV/tag checks loudly) **and** rely on the existing tag to protect the header bytes in transit
(already true for free, same mechanism that protects `PROFILE`/`H`/`W`/`C` today per
`architecture_discrepancies.md`'s own report of `test_dimension_relabelling_rejected` /
`test_profile_field_change_rejected`).

**Decryptor's profile/extraction selection:** `decrypt_bytes` (`cipher.py:78-94`) already reads
`hdr.profile` from the parsed header (`cipher.py:83`) and passes it through to `_materials` → `build_streams`
(`cipher.py:88` → `generator.py:111`, parameter `profile`). The same mechanism extends naturally: parse
`hdr.extraction` from the (new, versioned) header and pass it through the same call chain to select which
extraction function `build_streams` wires into the `RefStream`/`NpStream` objects it constructs. No new
control-flow concept is needed — this is exactly the existing profile-selection pattern, duplicated for a
second axis.

## 5. Proposed function-level interface

`[PROPOSAL — not implemented]`:

```python
# generator.py — proposed additions, illustrative only, NOT implemented

EXTRACTION_MANTISSA8_V1 = 1      # existing, default, legacy
EXTRACTION_K14_SCALED_MODULO_V1 = 2   # new

def m_byte(v):                   # existing, unchanged
    return _pack_d(v)[6]

def frac_byte_scalar(v):         # new thin wrapper for the reference backend
    # adapts isc_seq.extract.frac_byte (array-returning) to a single int, as RefStream needs
    from isc_seq.extract import frac_byte
    return int(frac_byte(v))

_EXTRACTORS_REF = {EXTRACTION_MANTISSA8_V1: m_byte, EXTRACTION_K14_SCALED_MODULO_V1: frac_byte_scalar}

# RefStream.__init__ gains an `extraction` parameter, stores self._extract = _EXTRACTORS_REF[extraction]
# RefStream._output_step uses self._extract(x) / self._extract(y) instead of hardcoded m_byte

# NpStream.take's inline bit-trick (generator.py:97-98) becomes a branch:
#   if extraction == EXTRACTION_MANTISSA8_V1: (existing bit-trick)
#   elif extraction == EXTRACTION_K14_SCALED_MODULO_V1: use isc_seq.extract.frac_byte on xs, ys separately,
#        then interleave into the same (k, LANES, 2) -> bytes layout the existing code already produces

# build_streams(seeds, backend="numpy", profile=1, burn_in=BURN_IN, extraction=EXTRACTION_MANTISSA8_V1):
#   unchanged except passing `extraction` through to RefStream/NpStream construction
```

This keeps the **existing default value** (`EXTRACTION_MANTISSA8_V1`) as the implicit behavior for any
caller that does not pass the new parameter, which is how byte-for-byte legacy reproducibility is
preserved: no existing call site in `cipher.py`, `tests/`, or `isc_cipher_kat/` needs to change unless it
explicitly opts into the new extraction.

## 6. Backward compatibility guarantee

`[RECOMMENDATION]`, concrete and testable:
1. Every existing KAT vector in `isc_cipher_kat/vectors/` was generated under the implicit
   `mantissa8_v1` behavior; none of them need to change, and `gate_r.py`'s existing checks
   (`check_trig`, `check_traj`, `check_streams`, `check_cipher`) continue to exercise exactly the same code
   path they do today, unmodified, as long as the default extraction value is `mantissa8_v1` and no
   existing call site is edited to pass a different value.
2. The existing self-test (`isc_cipher/selftest.py: run_selftest`) checks profile-1 sin/cos and a
   short trajectory — it does **not** currently check the extraction function at all (it stops at
   verifying `(x, y)` trajectory values, before any byte extraction happens — confirmed by reading
   `selftest.py:39-43` and `53-58`, which compare `_h(x), _h(y)` to `TRAJ["x"], TRAJ["y"]`, never calling
   `m_byte`). **This means the self-test does not need to change at all for `mantissa8_v1` to remain
   covered**, and a new self-test path for `k14_scaled_modulo_v1` can be added purely additively.
3. **Recommended regression test to add (not implemented here):** a new test asserting that
   `build_streams(seeds, backend="numpy", profile=1)` (no `extraction` argument) produces byte-identical
   output to the current, unmodified `generator.py` behavior, run once before any implementation change
   and again after, as a direct byte-for-byte regression guard — in addition to relying on the existing
   KAT vectors.

## 7. Open design questions (explicitly unresolved — not decided here)

`[OPEN / FOR APPROVAL]`:
- Whether `k14_scaled_modulo_v1` should ever be made the *default* for new encryptions once validated, or
  remain an explicit opt-in indefinitely (recommendation: keep `mantissa8_v1` as default until the new
  profile has its own full Gate C/Gate A/Gate R coverage and a dedicated multi-lane statistical validation
  per `multi_lane_statistical_validation_protocol.md`).
- Whether `EXTRACTION` should be a header byte (Option 1 above) or could instead be derived implicitly from
  `VERSION` alone (i.e. `VERSION=2` always implies `k14_scaled_modulo_v1`, no separate byte) — rejected as
  the primary recommendation because it would prevent ever adding a *third* extraction method without a
  `VERSION=3`, whereas an explicit field scales to N methods under one version bump.
- Exact byte position of the new `EXTRACTION` field within the header — left to the implementer, with the
  only hard constraint being that it must be covered by the HMAC tag (trivially true, since the tag already
  covers the entire header) and should be included in `ctx` for key-derivation binding (§4).
