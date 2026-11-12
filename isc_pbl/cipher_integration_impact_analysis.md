# Cipher Integration Impact Analysis — Effect of Changing Byte Extraction

**Document ID:** `ISC-PHASE2-IMPACT-2026-01`
**Date:** 11 November 2026

---

## 1. Does the S-box remain a permutation of 0-255?

`[VERIFIED SOURCE + DERIVED]`: `sampling.build_sbox` (`sampling.py:42-52`) constructs `S` via Fisher-Yates
swaps starting from `list(range(256))`, using `bounded(src, i+1)` to pick swap indices — the algorithm is a
permutation by construction **regardless of the statistical quality of the bytes `src` draws from**, because
Fisher-Yates with *any* sequence of indices `j_i ∈ [0, i]` produces a permutation (it is a sequence of
transpositions on an initially-identity list; this is true even if `j_i` were drawn from a biased or
non-uniform source — only the *distribution over which permutation results* would change, not the fact
that the result is always some permutation). **Changing the extraction method changes which bytes feed
`WordSource`/`bounded()` (`sampling.py:11-39`), hence which permutation is produced for a given key/nonce,
but cannot break the permutation invariant itself.** This is a structural (code-logic) guarantee, not a
statistical one.

## 2. Does Fisher-Yates sampling remain unbiased?

`[VERIFIED SOURCE + ANALYSIS]`: `bounded()`'s unbiasedness (Lemire's method, `sampling.py:28-39`) is a
property of the algorithm applied to its **input words** (`src.next_word()`, 32-bit big-endian integers
drawn from the stream), **conditional on those input words being uniformly distributed over
`[0, 2^32)`**. Lemire's method does not introduce bias *given* uniform input; it does not *guarantee*
output uniformity if the input word distribution is itself biased. **This means: whether Fisher-Yates
sampling is "unbiased" in the complete, end-to-end sense depends on the statistical quality of whichever
extraction method feeds it** — exactly the gap `multi_lane_statistical_validation_protocol.md` is designed
to close for both `mantissa8_v1` (currently *unvalidated* at the multi-lane level per
`phase_2_source_code_architecture_audit.md §5`'s citation of `algorithm_design.md:638-639`'s own
"[OPEN]: not tested" admission) and the proposed `k14_scaled_modulo_v1` (validated only at the
single-orbit level by Step 1.1, not yet at the multi-lane level either). **The existing unit test cited in
Phase 1** (`test_isc_cipher_sampling_diffusion.py: test_bounded_is_exactly_uniform`, described in Phase 1's
`existing_implementation_audit.md §3.5` as testing "every value v ∈ [0, s) has an identical count of
accepted 32-bit words") proves the *algorithm* is unbiased **given synthetic/exhaustive 32-bit word
inputs**, not that the *actual keystream-derived* words are themselves uniform — these are different claims.
`[DISTINCTION NOT PREVIOUSLY MADE THIS EXPLICITLY IN PHASE 1 — new in this Phase 2 analysis]`

## 3. Does the permutation remain valid?

Yes, by the same Fisher-Yates structural argument as §1 — `build_permutation` (`sampling.py:55-62`) is
algorithmically identical in structure to `build_sbox`, so the same reasoning applies: always a valid
permutation of `[0, n)`, regardless of extraction method; statistical quality of *which* permutation is
produced depends on the extraction method per §2's caveat.

## 4. Does diffusion remain invertible?

`[VERIFIED SOURCE]`: `diffusion.forward`/`backward` (`diffusion.py:13-29`) and their inverses
(`diffusion.py:32-57`) are invertible by **algebraic construction** — `u_k = S[(q_k + prev + a_k) mod 256]`
is invertible given `S_inv`, `prev` (the previous output or `iv_f`), and `a_k`, **for any values of `a_k`,
`b_k`** (these are just keystream bytes added mod 256; the modular-addition-then-S-box structure is
invertible for *any* byte value of `a`/`b`/`S`, as long as `S` is a valid permutation, which §1 established
is unconditionally true). **Changing the extraction method changes the *values* of `a`, `b`, `S`, `pi` but
cannot affect invertibility**, which is a property of the diffusion equations' algebra, not of the
keystream's statistical properties. This is confirmed structurally; the existing
`test_isc_cipher_sampling_diffusion.py` roundtrip tests on `inverse_ref`/`inverse_np`
(Phase 1's `existing_implementation_audit.md §3.5`, `§3.6`) already establish this for the current
extraction method, and the same algebraic argument guarantees it independent of which extraction method
produced the inputs.

## 5. Must decryption use exactly the same profile as encryption?

`[VERIFIED SOURCE]`: Yes, unconditionally, already true today for `PROFILE` (arithmetic engine) and must
hold identically for the proposed `EXTRACTION` axis. `decrypt_bytes` (`cipher.py:78-94`) reads
`hdr.profile` from the **ciphertext's own header** (`cipher.py:83`, `container.parse`) and uses it to
regenerate the same key material via `_materials` (`cipher.py:88`) — it does not take profile as a
caller-supplied parameter at all for decryption (only `backend` is caller-supplied). This means: **once
`EXTRACTION` is added to the header (per `dual_profile_generator_design.md §4`), decryption will
automatically use whatever extraction value is stored in the ciphertext**, by the same mechanism that
already makes `PROFILE` self-describing. If the extraction byte is tampered with, the entire downstream
key/keystream regeneration diverges, which is caught either by the KCV check (`cipher.py:92-93`,
`NumericalDivergenceError`) or — if `EXTRACTION` is folded into `ctx` as recommended — earlier, by the
HMAC tag check itself (`cipher.py:85-86`), since a wrong `ctx` means a wrong `k_mac`.

## 6. Does KCV calculation change?

`[VERIFIED SOURCE]`: `kcv_state_bytes` (`generator.py:138-140`) is computed from the **final lane states**
(`x, y` float64 pairs) and `steps` count, via `final_state_bytes()` (`generator.py:64-67`, `105-108`) —
**not** from the extracted bytes at all. Changing the extraction method (which happens strictly *after*
state advancement, converting an already-computed `x`/`y` to a byte) **does not change the KCV
computation's inputs**, because the KCV only ever sees the raw float64 lane states, never the extracted
bytes. **The KCV mechanism is extraction-method-agnostic by construction** — a useful property, since it
means the numerical-divergence-detection mechanism continues to work identically regardless of which
extraction profile is active.

## 7. Do existing KAT vectors remain valid for the legacy profile? Are new KAT vectors needed for k=14?

`[DERIVED, consistent with `dual_profile_generator_design.md §6`]`: Yes to both. Existing KAT vectors
(`isc_cipher_kat/vectors/{traj,stream,cipher}_kat.json`) were generated entirely under `mantissa8_v1`
(the only extraction that has ever existed in this codebase); since that code path is left untouched under
the proposed additive design, **existing KAT vectors remain valid indefinitely, with zero regeneration
needed**, confirmed independently in this pass by `[EXECUTED]` re-running `gate_r.py --backend numpy` to
completion: **overall PASS**, including `R-stream-KAT: PASS` and `R-cipher-KAT: PASS` against these exact
stored vectors (see `phase_2_source_code_architecture_audit.md §6`). **New KAT vectors are required** for
`k14_scaled_modulo_v1` once implemented, generated via the existing `isc_cipher_kat/make_kat.py` tooling
(file present, not inspected line-by-line in this pass — flagged as an open item for the implementer) under
the new extraction path, before `gate_r.py` can meaningfully check that profile's reproducibility.

## 8. Must the ISCI container format change?

Yes — see `dual_profile_generator_design.md §4` for the full design (recommended: a new `EXTRACTION` byte,
`HEADER_LEN` 36→37, gated behind a `VERSION` bump so legacy 36-byte ciphertexts remain byte-for-byte valid
and unambiguous).

## 9. Is profile metadata authenticated?

`[VERIFIED SOURCE]`: Yes, already true today for the existing header fields including `PROFILE` — the
entire header (`hdr`) is included in the HMAC tag input (`cipher.py:69`: `tag = hmac.new(m["k_mac"], hdr +
body, ...)`, and `cipher.py:84`: `expected = hmac.new(der.mac_key(), z[:container.HEADER_LEN + hdr.n], ...)`).
Phase 1's `existing_implementation_audit.md` independently reports `test_profile_field_change_rejected` and
`test_dimension_relabelling_rejected` as passing tests confirming this for `PROFILE`/`H`/`W`/`C` specifically.
Any new `EXTRACTION` field added to the same header is automatically covered by the same mechanism, with no
new code needed for *tamper-detection* of that field (though, per `dual_profile_generator_design.md §4`,
folding it into `ctx` as well is recommended for a stronger guarantee — wrong extraction value immediately
produces wrong keys, not just a tag mismatch after the fact).

## 10. Does cross-platform bit-exact reproducibility remain guaranteed?

`[DERIVED, consistent with `frac_byte_k14_compatibility_audit.md §4`]`: Yes, **conditional on the
extraction function itself using only IEEE-754-mandated-correctly-rounded basic operations** (not
transcendental functions) — true for `frac_byte` (`np.abs`, multiply, `np.floor`, `%`, cast; verified by
reading `isc_seq/extract.py:60-61`, no sin/cos call). The only cross-platform risk in the entire pipeline
is the sin/cos evaluation inside `isc_step.step_vec`/`step_ref`, which is already solved by the fdlibm port
for profile 1 (`architecture_discrepancies.md §5`) and is **upstream of, and unaffected by, the byte
extraction step**. Adding `k14_scaled_modulo_v1` introduces no new cross-platform risk beyond what already
exists for `mantissa8_v1`.

## 11. Are the existing four streams statistically distinguishable or correlated?

`[OPEN — NOT TESTED in this pass or, per `multi_lane_statistical_validation_protocol.md §3`, confirmed
tested anywhere in the existing `isc_eval`/`isc_seq` code without further inspection of `exp_nist.py`]`.
This is explicitly one of the gaps `multi_lane_statistical_validation_protocol.md §2.3` is designed to
close. No claim of distinguishability or correlation (or their absence) is made here.

## 12. Caution against overclaiming (explicit, per the task's instruction)

`[METHODOLOGICAL]`: None of the above establishes that `isc_cipher` is *cryptographically secure* — only
that specific structural invariants (permutation validity, invertibility, tamper-detection coverage,
cross-platform determinism) hold **by construction**, independent of the keystream's statistical quality.
Unbiased integer sampling (§2) and a valid permutation (§1, §3) are necessary but **not sufficient**
conditions for security; an attacker who can predict or bias the underlying keystream (the open question
this entire Phase 2 effort and `multi_lane_statistical_validation_protocol.md` are about) could still break
confidentiality even though every structural invariant above holds. This distinction must be preserved in
any future reporting of these results.
