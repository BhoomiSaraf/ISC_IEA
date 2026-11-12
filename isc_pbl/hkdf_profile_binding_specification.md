# HKDF Profile/Extraction Binding Specification

**Document ID:** `ISC-PHASE2-HKDFBIND-2026-02`
**Date:** 11 November 2026
**Source verified directly this session:** `isc_cipher/kdf.py` (80 lines, read in full), `isc_cipher/cipher.py`
(125 lines, read in full).

---

## 1. Exact current (VERSION=1) HKDF behavior

`[VERIFIED SOURCE]`, re-derived field-by-field from the actual code, not cited from Phase 1/session 1:

- **Input keying material (IKM):** the 32-byte master `key` (`kdf.py:63`, second argument to `hkdf_extract`).
- **Salt:** the 16-byte `nonce` (`kdf.py:63`, first argument — confirmed: `Derivation.__init__`,
  `kdf.py:59-63`: `self._prk = hkdf_extract(nonce, key)`, and `hkdf_extract(salt, ikm)` at `kdf.py:32-33` is
  `hmac.new(salt, ikm, hashlib.sha256).digest()` — **salt and IKM positions are exactly as RFC 5869 defines
  "extract": `PRK = HMAC-Hash(salt, IKM)`**, confirmed to match by direct reading, not assumed from the name
  "HKDF.")
- **Extract:** `hkdf_extract(nonce, key)` → one 32-byte `PRK` (`kdf.py:32-33`).
- **Expand:** `hkdf_expand(prk, info, length)` (`kdf.py:36-44`) — standard RFC 5869 expand, counter starting
  at 1, `length` capped at `255*32` bytes (`kdf.py:37`).
- **Domain-separation / context construction:** `context(profile, dtype, h, w, c)` (`kdf.py:47-49`):
  ```
  ctx = CONTEXT_PREFIX || u8(profile) || u8(dtype) || BE16(H) || BE16(W) || u8(C)
  ```
  where `CONTEXT_PREFIX = b"ISC-IMG/v1"` (10 bytes, `kdf.py:18`) — **total ctx length = 10+1+1+2+2+1 = 17
  bytes**, confirmed by direct summation, matching the figure cited in Phase 1's audit exactly.
- **Per-derivation labels, inside `Derivation.derive(label, length)` (`kdf.py:65-66`):**
  `info = ctx + b"\x00" + label.encode("ascii")`, then `hkdf_expand(self._prk, info, length)`. The `ctx` is
  **fixed once per `Derivation` instance** (set in `__init__`, `kdf.py:62`); only `label` varies per call.
- **Derived outputs and exact lengths, each via a distinct `label` string:**
  - `mac_key()` → `derive("mac", 32)` (`kdf.py:68-69`) — 32 bytes.
  - `kcv_key()` → `derive("kcv", 32)` (`kdf.py:71-72`) — 32 bytes.
  - `ivs()` → `derive("iv", 2)` (`kdf.py:74-76`) — 2 bytes, split into `iv_f = iv[0]`, `iv_b = iv[1]`.
  - `seeds()` → for each of 4 streams × 64 lanes, `derive(f"lane/{stream}/{lane:04d}", 16)`
    (`kdf.py:78-80`, `lane_label`, `kdf.py:52-53`) — 256 independent 16-byte seeds.
- **What header/version information is currently used in `ctx`?** Only `profile`, `dtype`, `h`, `w`, `c` —
  **`VERSION` itself is never included in `ctx`** (`[VERIFIED SOURCE]`: `context()`'s signature,
  `kdf.py:47`, takes exactly `(profile, dtype, h, w, c)`, no `version` parameter at all). This is a material
  fact for §3 below.

---

## 2. Preserving VERSION=1 derivation byte-for-byte

`[NON-NEGOTIABLE, per task §12 item 4 "do not silently change defaults"]`: Any change to `context()`'s
signature must leave its **output** identical for every existing call site that does not explicitly request
the new behavior. Concretely:

```python
# existing signature, unchanged:
def context(profile, dtype, h, w, c):
    return CONTEXT_PREFIX + bytes([profile, dtype]) + h.to_bytes(2, "big") + w.to_bytes(2, "big") + bytes([c])
```//kdf.py:47-49, quoted verbatim

**Proposed, additive change:**
```python
def context(profile, dtype, h, w, c, extraction=None):
    base = CONTEXT_PREFIX + bytes([profile, dtype]) + h.to_bytes(2, "big") + w.to_bytes(2, "big") + bytes([c])
    if extraction is None:
        return base                      # byte-for-byte identical to today, for every V1 call site
    return base + bytes([extraction])    # 18 bytes, V2 only
```

This satisfies "preserve V1 byte-for-byte" **by construction**: no existing call site
(`cipher.py:36,83`) passes an `extraction` argument, so `context(profile, dtype, h, w, c)` called exactly as
today produces exactly the same 17-byte `ctx` it always has, for every key/seed ever derived under V1 —
including every value baked into the existing KAT vectors (`isc_cipher_kat/vectors/*.json`) and the
self-test constants (`_selftest_vectors.py`), which depend on `ctx` only through the fixed test
key/nonce/dims used to generate them, none of which involve `extraction` at all under V1.

---

## 3. Proposed VERSION=2 context encoding — exact byte-level specification

`[PROPOSAL — exact encoding, per task's instruction to leave no ambiguity]`:

```
ctx_v2 = "ISC-IMG/v1" || u8(PROFILE) || u8(DTYPE) || BE16(H) || BE16(W) || u8(C) || u8(EXTRACTION)
```
- **Literal prefix:** unchanged, `b"ISC-IMG/v1"` (10 bytes) — **not** bumped to e.g. `b"ISC-IMG/v2"`.
  Rationale: the prefix string names the *algorithm family* ("ISC-IMG"), not the container version; reusing
  it avoids implying the underlying cryptographic construction changed, when only a byte-extraction
  post-processing step and a container field were added. (This is a naming judgment call, flagged as
  `[RECOMMENDATION, not forced by any technical constraint]` — an alternative of bumping the prefix is
  possible and would also work, at the cost of being a larger textual diff with no compatibility benefit
  since the prefix is never compared against a legacy value anywhere in the code.)
- **Field order:** identical to V1 for the first 17 bytes, **then** one appended byte, `u8(EXTRACTION) ∈
  {1, 2}`. Total length: **18 bytes** for V2, vs. 17 for V1.
- **Field widths:** unchanged for all pre-existing fields; `EXTRACTION` is 1 byte (sufficient for 256
  possible extraction methods, matching the width convention already used for `PROFILE`, `DTYPE`, `C`).
- **Version separation:** `VERSION` itself is **still not included in `ctx`**, consistent with V1's own
  behavior (§1) — the task does not require every header field to be folded into `ctx`; only the
  **newly added, security-relevant** `EXTRACTION` field needs this treatment, by the same logic that
  `PROFILE` (arithmetic engine, directly affects which bytes are produced) is already in `ctx` while, e.g.,
  `NONCE` is not in `ctx` (it is the *salt*, used in `hkdf_extract`, a different role entirely) and `KCV` is
  not in `ctx` (it is an *output* of the derived material, not an input to it — circular if it were).

---

## 4. Why this avoids unintended cross-profile key reuse

`[DERIVED]`: Because `ctx` is concatenated into **every** `derive()` call's `info` (`kdf.py:65-66`:
`info = self.ctx + b"\x00" + label.encode(...)`), changing `ctx`'s content by even one byte changes the
HMAC input for **every** derived key and seed simultaneously — `mac_key`, `kcv_key`, both `iv`s, and all 256
lane seeds. **Two ciphertexts with the same `(key, nonce, profile, dtype, h, w, c)` but different
`EXTRACTION` values will therefore derive completely unrelated `PRK`-expansion outputs for every single
field** — not just "different keystream bytes because the extraction function differs downstream," but
**different lane seeds, different `(x0,y0)` initial states, different `mac_key`, different `kcv_key`,
different IVs** — the two profiles' entire key schedules are cryptographically unlinked, not merely
post-processed differently. This is a materially stronger guarantee than relying on the HMAC tag alone,
consistent with `dual_profile_generator_design.md §4`'s recommendation (re-confirmed here with the exact
mechanism spelled out, not just asserted).

---

## 5. Why tampering with `EXTRACTION` in an authenticated ciphertext cannot produce an "accepted but
differently interpreted" plaintext

`[DERIVED, two independent, stacking defenses]`:

1. **Defense 1 — the HMAC tag itself.** The entire header (including the new offset-36 `EXTRACTION` byte,
   per `container_v2_binary_specification.md §1,§5`) is covered by `tag = hmac.new(k_mac, hdr + body, ...)`
   (`cipher.py:69`). If an attacker flips the `EXTRACTION` byte in transit, `hdr` changes, so the tag the
   attacker would need to forge changes too — without knowing `k_mac`, `hmac.compare_digest` fails
   (`cipher.py:85-86`) and decryption is refused **before any generator/key-schedule code runs at all**
   (enforced today for `PROFILE`/`H`/`W`/`C` tampering by the existing `no_generator` test fixture,
   `tests/test_isc_cipher_auth.py:27-31`; an equivalent test must be added for `EXTRACTION` — see
   `phase_3a_implementation_plan.md`).
2. **Defense 2 — `ctx` binding (§3-4 above), which is strictly stronger and independent of tag integrity.**
   Even in a hypothetical scenario where tag verification were somehow bypassed or where one were
   analyzing a chosen-ciphertext attack surface abstractly, binding `EXTRACTION` into `ctx` means the
   *decryption key material itself* for a tampered `EXTRACTION` value is **unrelated** to the correct one —
   so even "successfully" decrypting with the wrong `EXTRACTION` value could not produce the *original*
   plaintext; it would produce unrelated garbage, not a "differently interpreted but still meaningful"
   plaintext. This is the property the task's Task C explicitly asks to be explained, not merely asserted.

**Both defenses are recommended together** ("belt and braces," per `dual_profile_generator_design.md §4`,
re-confirmed here): Defense 1 alone is already sufficient for the system's actual threat model (an
authenticated-encryption scheme where the tag is always checked first, per the verified `cipher.py:85-86`
ordering), but Defense 2 costs nothing extra to implement (one appended byte to an existing `ctx`
computation) and removes any reliance on "the tag check always runs first" being the *only* thing
protecting against profile confusion.

---

## 6. Interaction with existing HMAC authentication — explicit statement

`[VERIFIED SOURCE + DERIVED]`: No conflict or redundancy issue exists. `k_mac` (used for the outer HMAC tag)
is itself derived via `derive("mac", 32)`, which already uses `ctx` (§1) — so if `EXTRACTION` is folded into
`ctx`, **`k_mac` itself becomes `EXTRACTION`-dependent too**, meaning a V2 ciphertext's tag is computed with
a different `k_mac` than a V1 ciphertext of the same `(key, nonce, dims)` would use. This is **intended and
correct**: it is exactly analogous to how `k_mac` is already `PROFILE`-dependent today (since `PROFILE` is
already in `ctx`), and the existing `test_profile_field_change_rejected` test (cited in Phase 1's
`existing_implementation_audit.md`) already proves this pattern works correctly for `PROFILE` — the same
reasoning extends to `EXTRACTION` without any new cryptographic mechanism, only a new input byte to an
existing, already-tested mechanism.

---

## 7. Explicit non-claim (per task's instruction)

`[METHODOLOGICAL, required by the task]`: **Profile binding via `ctx`, by itself, does not prove the
scheme resists chosen-plaintext or known-plaintext attacks.** It proves that (a) the `EXTRACTION` value is
cryptographically bound into the key schedule such that tampering with it or confusing profiles cannot
cause one profile's ciphertext to be misinterpreted as another's, and (b) this is independently
tag-protected. It says **nothing** about whether `k14_scaled_modulo_v1` or `mantissa8_v1`'s keystream is
itself unpredictable to an attacker — that is the separate, open statistical question
`multi_lane_statistical_validation_protocol.md` and `phase_3b_validation_readiness.md` address, and no
claim about cryptographic security is made or implied by this document.

---

## 8. Unresolved items

`[OPEN]`:
- Whether `ctx_v2`'s prefix should differ from V1's `"ISC-IMG/v1"` string (§3) — recommendation given, not
  mandatory.
- Whether `Derivation.__init__`/`context()`'s call sites in `cipher.py:36,83` should be updated to pass
  `extraction=hdr.extraction` unconditionally (computing V1's `ctx` the long way, always truthy-checking)
  or via a cleaner branch — a Phase 3A implementation detail, not a design ambiguity (the *value* produced
  is unambiguous either way, per §2's additive-default construction).
