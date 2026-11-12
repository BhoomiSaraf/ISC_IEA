# Extraction Backend Compatibility Specification — Scalar (Reference) vs. NumPy (Vectorized)

**Document ID:** `ISC-PHASE2-BACKENDCOMPAT-2026-02`
**Date:** 11 November 2026
**Source verified directly this session:** `isc_seq/extract.py` (124 lines, read in full),
`isc_cipher/generator.py` (141 lines, read in full), `isc_cipher/isc_step.py` (98 lines, read in full).

---

## 1. Reconfirming the exact `frac_byte` implementation

`[VERIFIED SOURCE]`, `isc_seq/extract.py:57-61`:
```python
FRAC_SCALE = 1e14  # |v| < 1 so |v| * 1e14 < 2**53: floor is exact

def frac_byte(v):
    return (np.floor(np.abs(np.asarray(v, dtype=np.float64)) * FRAC_SCALE) % 256).astype(np.uint8)
```
This matches, byte-for-byte in source text, the function quoted in the prior session's
`frac_byte_k14_compatibility_audit.md §1` — **re-confirmed by independent re-reading this session**, not
merely trusted from the earlier document.

**On the "previous Phase 2 testing reported equality across 13 edge cases and 2,000 trajectory values"
premise named in this task's Task D instructions:** this matches exactly what
`frac_byte_k14_compatibility_audit.md §3` reports (13 handpicked edge cases + 1,000 real trajectory points
× 2 coordinates = 2,000 values). That document's own §3 "Caveat" section already states explicitly: **"this
is 13 handpicked edge cases + 2,000 trajectory points, not an exhaustive proof over the float64 domain"**
— the prior session did not overclaim here; this task's instruction to "reconfirm" and "not assert
universal bit equivalence based solely on a finite sample" is **already satisfied by the prior document's
own stated caveat**, which this document carries forward rather than weakens.

---

## 2. Scalar reference-backend requirement: must work without NumPy

`[VERIFIED SOURCE]`: `isc_cipher/generator.py`'s module docstring (L10) states: *"Backends: 'reference'
(R1, pure Python, profile 1 only) and 'numpy' (V1, profiles 1 and 2)."* Confirmed structurally:
`RefStream` (`generator.py:29-66`) uses only `struct`, Python `list`, `bytearray` — **no `numpy` import
anywhere in `RefStream`'s code path** (`[VERIFIED SOURCE]`: `import struct` is the only import at the top
of `generator.py:13`; `NpStream.__init__` (`generator.py:72-73`) is the **only** place `numpy` is imported,
and it is imported **inside** the class's `__init__`, i.e. lazily, so that constructing only `RefStream`
objects never triggers a `numpy` import). `isc_step.step_ref` (`isc_step.py:27-55`) is likewise pure
Python/`math`-free (it uses only `*`, `+`, `-`, `/`, and calls into `fdlibm_ref`, itself presumably pure
Python — not re-verified line-by-line in this pass, flagged as `[UNVERIFIED — isc_cipher/fdlibm_ref.py was
not re-read in this session]`, consistent with the task's instruction not to assume).

**Critical constraint restated precisely:** `frac_byte` as written in `isc_seq/extract.py` **always calls
`np.asarray`, `np.floor`, `np.abs`** — it is **not usable, as-is, inside `RefStream`/`step_ref`'s pure-Python
code path without introducing a NumPy dependency**, exactly the risk this task's Task D explicitly warns
against ("Do not introduce a mandatory NumPy dependency into the scalar backend"). This is the single most
important compatibility fact to get right.

---

## 3. Proposed scalar (no-NumPy) implementation

`[PROPOSAL — not implemented]`:
```python
import math

def frac_byte_scalar(v):
    """Pure-Python equivalent of isc_seq.extract.frac_byte for one float64 value.

    Returns a plain Python int in [0, 255], with no numpy dependency.
    """
    scaled = math.floor(abs(float(v)) * 1e14)
    return scaled % 256
```
- Uses only `math.floor` and `abs`/`float` — **zero third-party dependency**, satisfying the hard
  constraint exactly.
- Returns a **plain Python `int`** (not a 0-d NumPy array), directly usable by `bytearray.append(...)` in
  `RefStream._output_step` (`generator.py:52-53`), matching the interface `m_byte(v)` already provides
  (`m_byte` returns `_pack_d(v)[6]`, a plain Python `int` in `[0,255]` since indexing a `bytes` object
  yields an `int` — confirmed by direct reading, `generator.py:25-26`).
- `math.floor(x)` on a Python `float` and `np.floor(x)` on a `float64` scalar are both required, under
  IEEE-754, to compute the mathematically exact floor of the input value with no intermediate rounding
  beyond what the single floating-point multiplication `abs(v) * 1e14` already introduced — **the two floor
  implementations cannot disagree** once their *input* (the already-computed float64 product) is identical,
  because floor of an IEEE-754 double has only one correct answer per the standard (it is not a
  transcendental approximation).

---

## 4. Proposed vectorized (NumPy) implementation — unchanged from `frac_byte`, plus shape adapter

`[PROPOSAL, consistent with `frac_byte_k14_compatibility_audit.md §5`, re-confirmed against the exact
`NpStream.take` code this session]`: `generator.py:82-103`'s `NpStream.take` currently does
(`generator.py:97-98`):
```python
mb = np.stack([xs, ys], axis=-1).view(np.uint64)          # (k, 64, 2): lane-minor, x before y
new = ((mb >> np.uint64(8)) & np.uint64(0xFF)).astype(np.uint8).tobytes()
```
where `xs, ys` have shape `(k, LANES)` = `(k, 64)` (allocated at `generator.py:88-89`). The proposed
k14-extraction branch, operating on the **same** `xs, ys` arrays, would be:
```python
from isc_seq.extract import frac_byte

bx = frac_byte(xs)        # shape (k, 64), uint8
by = frac_byte(ys)        # shape (k, 64), uint8
new = np.stack([bx, by], axis=-1).astype(np.uint8).tobytes()   # (k, 64, 2) -> same byte order as today
```
`np.stack([bx, by], axis=-1)` reproduces **exactly** the same `(k, 64, 2)`-shape, C-order-flattened,
lane-minor-x-before-y byte layout that the existing bit-trick branch already produces via
`np.stack([xs, ys], axis=-1)` — **confirmed by direct inspection that both branches stack along the same
axis in the same order**, so the round-robin interleaving derived in
`phase_2_source_code_architecture_audit.md §4` is preserved identically for both extraction methods; only
the per-element byte **value** changes, never the **position** of any byte in the output stream. This
directly satisfies this task's Task E requirement ("adding extraction selection does not accidentally change
interleaving, state advancement, or output lengths").

---

## 5. Common specification of finite-input behavior

`[DERIVED, extending `frac_byte_k14_compatibility_audit.md §1`'s "no special-casing" observation with the
specific non-finite cases this task's Task D explicitly requires]`:

| Input | `frac_byte`/`frac_byte_scalar` behavior | Reasoning |
|---|---|---|
| `NaN` | `np.abs(nan) = nan`; `nan * 1e14 = nan`; `np.floor(nan) = nan`; `nan % 256 = nan`; `.astype(np.uint8)` on a NaN float produces an **implementation-defined/platform-dependent integer value** (NumPy's float→uint8 cast of NaN is undefined behavior at the C level, not guaranteed portable) | **Must never occur in practice**: `isc_step.step_vec`/`step_ref`'s own `_guard`/vector-guard (`isc_step.py:21-24, 88-91`) raises `ValueError` if any SIN/COS argument has `|arg| >= 24`, which — per `phase_2_source_code_architecture_audit.md §4` — is the *only* existing non-finite/out-of-domain protection anywhere in the pipeline; **the ISC recurrence's own algebra guarantees `x,y ∈ [-1,1]` for any finite input** (`y_{n+1} = 2 sin²(...) - 1`, bounded by construction), so a NaN state could only arise from a prior NaN propagating through, which `_guard` would have already caught at the trigonometric-argument stage *before* reaching the extraction step — **this is a pre-existing property of the upstream recurrence, not something `frac_byte` itself needs to handle**, consistent with `cipher_integration_impact_analysis.md §12`'s caution against over-engineering defenses for scenarios the upstream code already structurally prevents. |
| `+Infinity` / `-Infinity` | `abs(inf) = inf`; `inf * 1e14 = inf`; `floor(inf) = inf`; `inf % 256` → `nan` (IEEE-754 float modulo of infinity is NaN); same uint8-cast concern as NaN | Same reasoning: cannot arise from a finite ISC state under the existing guard; **flagged as a theoretical edge case requiring no new code**, not a verified-safe one — this is `[DERIVED FROM THE RECURRENCE'S ALGEBRA, not exhaustively tested against every possible intermediate float64 rounding scenario]`. |
| Signed zero (`+0.0`, `-0.0`) | `abs(-0.0) = 0.0` (IEEE-754 guarantees `abs` normalizes sign); both produce byte `0` | **Already verified empirically**, `frac_byte_k14_compatibility_audit.md §3`: both `0.0` and `-0.0` produce `0`, confirmed `MATCH` against Step 1.1's reference. |
| Out-of-domain values (`|v| > 1.0`) | `frac_byte` has **no domain check or clamp** — it will compute `floor(|v| * 1e14) mod 256` for *any* finite `v`, including values the ISC map's algebra should never actually produce | **Cannot occur from the recurrence's own output** (bounded to `[-1,1]` by construction, per the table's first row), but **can occur if `frac_byte` is called on a value from any other source** (e.g. a test harness bug, or a future misuse) — this is a **silent-wrong-answer risk for misuse outside the cipher's own call sites**, not a risk within the cipher itself. Not a blocker, but worth a code comment if implemented. |

**Explicit non-claim per the task's instruction:** this table does **not** assert universal bit equivalence
based on the finite sample tested in §1 — it instead derives, from the **upstream recurrence's own proven
boundedness** (an algebraic fact, not a statistical one), why the untested non-finite cases are expected to
be unreachable in practice, while explicitly flagging that this is a structural argument, not an exhaustive
test.

---

## 6. Possible sources of scalar/NumPy divergence — explicit investigation (Task D requirement)

`[DERIVED, addressing each named risk individually]`:

- **Python vs. NumPy floating-point evaluation:** Both ultimately perform IEEE-754 binary64 arithmetic for
  basic operations (`*`, `abs`, floor, `%`) on this platform (confirmed indirectly: `isc_step.step_ref`
  and `isc_step.step_vec` are already proven bit-identical by the existing
  `test_isc_cipher_numeric.py` test, per Phase 1's `existing_implementation_audit.md §4.2`, for the
  recurrence's own arithmetic, which is more operation-dense than `frac_byte`'s four simple ops) — **no
  divergence expected**, consistent with IEEE-754's correctly-rounded-basic-operations guarantee.
- **Float64 conversion:** `frac_byte_scalar`'s `float(v)` and `frac_byte`'s `np.asarray(v, dtype=np.float64)`
  both produce the IEEE-754 binary64 representation of `v` — if `v` is already a Python `float` or a NumPy
  `float64` scalar (the only two types the cipher's own code ever passes to an extraction function,
  confirmed by `RefStream`'s `x, y` being plain Python floats, `generator.py:33,50`, and `NpStream`'s `xs,
  ys` being `np.float64` arrays, `generator.py:75-76,88-89`), no conversion-induced divergence is possible.
- **Integer conversion:** `frac_byte_scalar`'s `math.floor(...)` returns a Python `int` of arbitrary
  precision; `frac_byte`'s `np.floor(...).astype(np.uint8)` goes through a `float64` intermediate before
  the final `% 256` and `uint8` cast. For `|v| ≤ 1`, `|v|*1e14 ≤ 10^14 ≈ 2^46.5`, **far below both
  `2^53` (float64 exact-integer limit) and `2^63` (int64 range)** — so the floored value is always an
  *exactly representable* float64 integer, and both the Python-`int` path and the `float64`-then-cast path
  necessarily agree. This repeats, more precisely, the argument already made in
  `frac_byte_k14_compatibility_audit.md §3`'s caveat, now phrased explicitly in scalar-vs-vector terms.
- **Large intermediate magnitudes:** Not applicable — the maximum intermediate value (`~10^14`) is small
  relative to float64's exact-integer range (`2^53 ≈ 9×10^15`), as already established.
- **Floor vs. truncation:** Both `math.floor` and `np.floor` are floor (round toward `-∞`), not truncation
  (round toward 0) — confirmed by their standard library documentation and consistent naming; since
  `frac_byte`/`frac_byte_scalar` always operate on `abs(v) ≥ 0`, floor and truncation coincide for
  non-negative inputs anyway, so even a hypothetical floor/truncate mismatch would be moot here.
- **Platform-specific arithmetic:** `+`, `-`, `*`, `abs`, `floor`, `%` are IEEE-754 "basic operations,"
  required to be correctly rounded on any IEEE-754-conformant platform (x86-64 SSE2, ARM64 all conform) —
  **not** subject to the libm cross-platform divergence that motivated the fdlibm port (which exists
  specifically because `sin`/`cos` are *not* required to be correctly rounded or portable). This repeats
  `frac_byte_k14_compatibility_audit.md §4`'s conclusion, now explicitly listed as one of the task's named
  risk categories rather than a general aside.
- **Array layout / byte ordering:** Only relevant to the **vectorized** path's final `.tobytes()`/stacking
  step (§4 above), not to the extraction arithmetic itself — already addressed in §4's "same axis, same
  order" derivation.

**Conclusion of this section:** every named risk category either does not apply (platform arithmetic,
large magnitudes, floor-vs-truncation) or is resolved by an exact-representability argument (integer/float
conversion) grounded in the `k=14` scale factor being far below the float64 exact-integer threshold — **not**
by assuming equivalence from a finite test sample alone.

---

## 7. Tests required to establish operational compatibility (not implemented here — specification only)

`[PROPOSAL, for Phase 3A]`:
1. **Exact scalar/vector equivalence over the cipher's actual valid domain:** generate `N` (propose
   `10^6`, matching Step 1.1's own sample size for comparability) float64 values actually produced by
   `isc_cipher.isc_step.step_vec`/`step_ref` (not `isc_seq.isc_map`, to test the **production** recurrence
   specifically) under profile 1, and assert `frac_byte_scalar(v) == int(frac_byte(np.array([v])))` for
   every one, for both `x` and `y` coordinates — extends the prior session's 2,000-point check by 3 orders
   of magnitude and ties it to the actual cipher recurrence rather than the research one.
2. **Cross-backend shape-adapter equivalence:** for a fixed `(key, nonce)`, assert that a hypothetical
   `k14`-extraction `RefStream` and `NpStream` (once implemented per `dual_profile_generator_design.md §5`)
   produce byte-identical output for the same number of requested bytes — the exact analogue of the
   existing (Phase 1-reported) "bit-for-bit identity between scalar `step_ref` and vectorized `step_vec`"
   test, applied one layer downstream at the extraction-output level.
3. **Non-finite-input guard test (defensive, not expected to ever trigger in production):** explicitly feed
   `frac_byte`/`frac_byte_scalar` NaN/Inf and document the resulting behavior (even if "undefined/platform
   -dependent") in a test, so that if the upstream guard's guarantee is ever weakened by a future change,
   this test will catch the resulting undefined behavior rather than letting it surface silently in
   production.
4. **Regression test that the new branch does not alter `mantissa8_v1` output:** a direct byte-for-byte
   comparison of `build_streams(seeds, profile=1)` (no `extraction` argument) before and after the
   extraction-selection code is added — already recommended in `dual_profile_generator_design.md §6.3`;
   repeated here because it is the single most important regression guard for backend compatibility
   specifically (it proves the *existing* backend's behavior is unaffected by the *new* code's mere
   presence, not just that the new code is internally consistent).

---

## 8. Performance — explicitly deferred, not fabricated

`[CARRIED FORWARD, per `frac_byte_k14_compatibility_audit.md §6` and this task's own instruction not to
optimize prematurely]`: No benchmark was run in this session either. The relative cost ordering argued in
the prior document (bit-trick: reinterpret+shift+mask, zero float ops; `frac_byte`: abs+multiply+floor+mod+
cast, four float ops) is unchanged and still `[ANALYSIS, not measured]`.
