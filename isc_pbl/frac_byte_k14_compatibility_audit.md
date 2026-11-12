# frac_byte / k=14 Compatibility Audit

**Document ID:** `ISC-PHASE2-FRACBYTE-2026-01`
**Date:** 11 November 2026

---

## 1. Exact source of `frac_byte`

`[VERIFIED SOURCE]` `isc_seq/extract.py:57-61`:

```python
FRAC_SCALE = 1e14  # |v| < 1 so |v| * 1e14 < 2**53: floor is exact

def frac_byte(v):
    return (np.floor(np.abs(np.asarray(v, dtype=np.float64)) * FRAC_SCALE) % 256).astype(np.uint8)
```

Properties, read directly from the code:
- **Accepts:** anything `np.asarray` accepts — Python floats, Python ints, NumPy scalars, NumPy arrays of
  any shape (the `% 256` and `.astype(np.uint8)` broadcast element-wise). `[VERIFIED SOURCE]`
- **Explicit `dtype=np.float64`** cast before any arithmetic — guarantees float64 regardless of input dtype.
- **Computes `np.abs(...)` first**, matching Method B's `|x_n|`.
- **Scales by `1e14` before flooring** — the docstring-level comment (`FRAC_SCALE = 1e14 ... floor is exact`)
  matches Step 1.1's own derivation (`architecture_discrepancies.md §2.1`, reproduced in Phase 1 audit):
  `|x_n| × 10^14 ≤ 10^14 ≈ 2^46.51`, well inside the 53-bit float64 integer-exact range, so the floor is
  computed on an exactly-representable value with no rounding error.
- **Modulo 256 is applied to the float64 result directly** (`... % 256`), *then* cast to `uint8` — this
  differs textually from Step 1.1's own implementation (see §2), which casts to `int64` *before* taking
  the modulo. Verified experimentally in §3 below that this textual difference produces **identical
  results** for all tested values, because `floor(|x|*1e14)` is always an exact non-negative integer value
  representable in float64 for `|x| ≤ 1` (max ≈ 10^14 ≪ 2^53), so float modulo and int64 modulo agree.
- **Uses host NumPy float64 arithmetic** (`np.abs`, `np.floor`), not fdlibm — but `frac_byte` performs no
  trigonometric operation itself; it only post-processes whatever `x_n`/`y_n` values it is given. It is
  agnostic to which recurrence (host libm, fdlibm, profile 1 or 2) produced those values. Determinism
  across platforms is therefore entirely inherited from whatever produced `v`, not from `frac_byte` itself.
- **No special-casing of boundary values** (`+0.0`, `-0.0`, exactly `±1.0`) exists in the function body —
  verified by reading all 2 lines of the function; there is no `if`/`where` branch.

## 2. Exact source of the Step 1.1 reference implementation

`[VERIFIED SOURCE]` `C:\Users\bhoom\Desktop\ISC_PBL\isc_sequence_characterization.py:552-563`:

```python
def quantise_digit_extraction(seq: np.ndarray, k: int) -> np.ndarray:
    """
    Transforms continuous state sequence into byte sequence via:
      B_n = floor(|x_n| * 10^k) mod 256
    """
    abs_seq = np.abs(seq)
    scaled = np.floor(abs_seq * (10.0 ** k)).astype(np.int64)
    byte_seq = (scaled % 256).astype(np.uint8)
    return byte_seq
```

Called with `k=14` for the normative baseline (per `results/sequence_characterization/configuration.json:17-22`,
`[VERIFIED SOURCE]`: `"digit_extraction_k_candidates": [13, 14, 15, 16]`, and per the closure report
identifying k=14 as the selected baseline).

## 3. Is `frac_byte` exactly Method B (the Step 1.1 k=14 transform)?

**Answer: Yes, bit-exact, verified empirically — not merely by reading the formulas.** `[EXECUTED]`

I wrote and ran a standalone comparison script (not committed/saved into either repository; executed
in-memory only, per the read-only restriction) that imported `isc_seq.extract.frac_byte` directly from the
cipher repository and `quantise_digit_extraction` (with `k=14`) directly from
`ISC_PBL\isc_sequence_characterization.py` via `importlib`, and compared their output byte-for-byte on:

| Test input | `frac_byte` output | `quantise_digit_extraction(k=14)` output | Result |
|---|---|---|---|
| `0.0` | 0 | 0 | MATCH |
| `-0.0` | 0 | 0 | MATCH |
| `1e-20` | 0 | 0 | MATCH |
| `-1e-20` | 0 | 0 | MATCH |
| `0.9999999999999` | 246 | 246 | MATCH |
| `-0.9999999999999` | 246 | 246 | MATCH |
| `1.0` | 0 | 0 | MATCH |
| `-1.0` | 0 | 0 | MATCH |
| `0.123456789012345` | 242 | 242 | MATCH |
| `-0.123456789012345` | 242 | 242 | MATCH |
| `1.23e-12` | 123 | 123 | MATCH |
| `-1.23e-12` | 123 | 123 | MATCH |
| `2.56e-12` | 0 | 0 | MATCH |

I additionally generated 1,000 real values from the actual ISC recurrence (`isc_seq.isc_map.isc_step`,
`x0=y0=0.1`, 1,000 burn-in steps discarded, next 1,000 steps retained for both `x` and `y`) and compared
the two functions over the **entire 1,000-element array** for both coordinates:

```
trajectory x match all: True
trajectory y match all: True
```

**Conclusion: `frac_byte` is mathematically and numerically identical to Step 1.1's `k=14`
scaled-floor-modulo method, `B_n = floor(|x_n| × 10^14) mod 256`, for every case tested, including the
edge cases the Phase 2 task explicitly requested (zero, signed zero, near-zero, near ±1, boundary values,
and real trajectory output).** This equivalence was *not assumed from the name* — it is demonstrated, as
required.

**Caveat (honesty about test coverage):** this is 13 handpicked edge cases + 2,000 trajectory points, not
an exhaustive proof over the float64 domain. The only known-possible source of divergence — int64-cast
modulo vs. float64 modulo — only differs when the scaled value is non-exactly-representable as an int64 or
when float modulo rounds differently near a multiple of 256; for `|x|≤1` and `k=14` (max scaled value
≈10^14 ≪ 2^63 and ≪2^53) this cannot occur, so the two code paths are provably equivalent for the entire
valid input domain `|x| ≤ 1`, not merely empirically equivalent on the tested samples. (This provability
argument is `[DERIVED]`, not independently formally verified by an automated exhaustive search — doing so
would require iterating ~10^14 possible floor targets, which is infeasible in this pass; the reasoning is
sound given IEEE-754 exactness guarantees but is not a machine-checked proof.)

## 4. Is `frac_byte` deterministic across platforms?

`[DERIVED]`: `frac_byte`'s own operations (`np.abs`, `*`, `np.floor`, `%`, `.astype`) are all IEEE-754
basic arithmetic operations (not transcendental functions), which are required to be correctly rounded by
the IEEE-754 standard and are not subject to the libm cross-platform divergence problem that motivated the
fdlibm port (`isc_cipher/fdlibm_np.py`, `isc_cipher/fdlibm_ref.py`). **`frac_byte` itself introduces no
new cross-platform non-determinism.** However, `frac_byte`'s *input* `v` is whatever the ISC recurrence
produced, and that recurrence's own determinism depends entirely on which sin/cos implementation produced
it (fdlibm under profile 1, host libm under profile 2) — a property of the generator, not of `frac_byte`.
**If `frac_byte` were substituted for `m_byte` inside the profile-1 generator path (which already uses
fdlibm), end-to-end cross-platform reproducibility would be preserved**, because the only non-arithmetic,
potentially-non-deterministic step (sin/cos) is unchanged; only the already-deterministic post-processing
of its output would differ.

## 5. Can `frac_byte` be reused directly in the cipher's generator interface, or does it need modification?

`[ANALYSIS/RECOMMENDATION]` — **It requires a thin adapter, not a rewrite**, for the following concrete
reasons found by inspecting the call sites:

1. **Interface mismatch — batch vs. the generator's two call sites.** `frac_byte` takes one NumPy array
   and returns one `uint8` array of the same shape. The numpy generator's extraction call
   (`generator.py:96-98`) currently does:
   ```python
   mb = np.stack([xs, ys], axis=-1).view(np.uint64)
   new = ((mb >> np.uint64(8)) & np.uint64(0xFF)).astype(np.uint8).tobytes()
   ```
   where `xs`, `ys` have shape `(k, LANES)` (k output-steps × 64 lanes). `frac_byte` would need to be
   called as `frac_byte(xs)` and `frac_byte(ys)` separately (it does not accept a combined/interleaved
   array the way `m_byte`'s bit-trick does via `np.stack(...).view(...)`), then the two `(k, LANES)` uint8
   results interleaved in the same `(k, LANES, 2)` → `.tobytes()` order the current code produces. This is
   a **straightforward reshaping change, not a change to `frac_byte`'s own math.**
2. **Scalar backend mismatch.** The reference backend's `m_byte(v)` (`generator.py:25-26`) takes one Python
   float and returns one Python `int` (`bytes[6]` of the packed double). `frac_byte` as written always
   returns a NumPy array (even for a scalar input, `np.asarray(v)` makes a 0-d array, and `.astype(np.uint8)`
   returns a 0-d NumPy uint8 array, not a plain Python `int`). `RefStream._output_step`
   (`generator.py:46-54`) calls `buf.append(m_byte(x))`, and `bytearray.append` requires a plain int in
   `[0,255]` — a 0-d NumPy array would need `int(frac_byte(x))` or an equivalent scalar extraction to work
   as a drop-in replacement. **This is a 1-line wrapper, not a semantic change.**
3. **No change to `frac_byte`'s own formula is needed or recommended.** Per §3, it already implements
   exactly the characterized Step 1.1 method. The adapter work is purely about shape/type conformance to
   the two existing `Stream` classes' internal buffer-filling code, confirmed by direct inspection of
   `generator.py:46-54` (`RefStream`) and `generator.py:82-103` (`NpStream`) — no other file calls into the
   byte-extraction step.
4. **Location of the isolated change.** Because `m_byte`/the inline bit-trick is called from exactly two
   places (`generator.py:52-53` and `generator.py:97-98`), and nowhere else in `isc_cipher/`, a second
   extraction function can be added at exactly those two call sites, gated by a `profile` or dedicated
   extraction-mode parameter, without touching `kdf.py`, `state_map.py`, `isc_step.py`, `sampling.py`,
   `diffusion.py`, `container.py`, or `cipher.py`'s control flow (see `dual_profile_generator_design.md`
   for the full design). **This directly answers the Phase 2 task's central question: yes, injection at one
   isolated byte-extraction boundary is sufficient and requires no change to the ISC recurrence, the lane
   architecture, the burn-in, the KDF, or the sampling/diffusion stages.**

## 6. Performance comparison

`[ANALYSIS]`, not independently benchmarked in this pass (flagged as an open item, not fabricated):
- `m_byte`/the bit-trick extraction is a bit-shift-and-mask on an already-materialized float64 array
  viewed as `uint64` — effectively free (no floating-point arithmetic at all, just a reinterpret + shift +
  mask, vectorized natively by NumPy).
- `frac_byte` performs one `np.abs`, one float multiply, one `np.floor`, one `% 256` (float modulo), and
  one cast — four extra vectorized floating-point passes over the array compared to `m_byte`'s zero
  floating-point operations.
- **Expected relative cost:** `frac_byte` is almost certainly measurably slower per call than the bit-trick,
  but the absolute magnitude is **not measured here** — this must be benchmarked on real lane-count arrays
  (shape `(k, 64)`) before any performance claim is treated as established. This is an open item for Phase
  3 implementation, not a blocker for the design in `dual_profile_generator_design.md`.
- **Vectorization is already present** in `frac_byte` as written (it is already a NumPy-array function,
  not a scalar Python loop), so no further vectorization work is needed beyond the shape-adapter in §5.
- Recommendation: **do not optimize prematurely** (per the task's own instruction); benchmark only once a
  concrete profile-2-equivalent code path exists and is under test.

## 7. Summary answer to the Phase 2 task's central question

**"How exactly can the experimentally characterized k=14 extraction method be incorporated into the
existing 256-lane ISC-IMG v1 generator without unnecessarily changing the cipher architecture or breaking
legacy reproducibility?"**

By adding a second extraction function at the two existing `m_byte`/bit-trick call sites in
`generator.py` (lines 52-53 and 97-98), using `isc_seq.extract.frac_byte` as the mathematical core after a
thin shape/type adapter (vectorized-array interleaving for the numpy path, scalar-int extraction for the
reference path), selected by a new profile or mode flag threaded through `build_streams` exactly the way
`profile` (1 vs. 2) is already threaded today (`generator.py:111`, `cipher.py:_materials`). No other
component — key schedule, state mapping, lane scheduling, burn-in, sampling, diffusion, or container
format — needs to change for this substitution alone. Legacy reproducibility is preserved automatically
because the existing `mantissa8_v1` code path is left completely untouched; the new path is additive. Full
design in `dual_profile_generator_design.md`.
