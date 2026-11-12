# Phase 2 — Source-Code Architecture Audit of ISC-IMG v1

**Document ID:** `ISC-PHASE2-ARCH-2026-01`
**Date:** 11 November 2026
**Method:** Direct line-by-line inspection of the actual source tree at
`C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis` (read-only; no files modified). All claims below
are tagged `[VERIFIED SOURCE]` (I read the exact lines quoted), `[EXECUTED]` (I personally ran the command
and report the real output), `[PRIOR REPORT]` (stated in the Phase 1 audit docs, not independently
re-derived here beyond what is marked `[EXECUTED]`), or `[DESIGN DOC]` (stated in `research/algorithm_design.md`,
the project's own specification, not the implementation).

---

## 1. Repository map (relevant subset)

```
sine_chebyshev_ikeda_analysis/
├── isc_cipher/
│   ├── kdf.py            Stage 1-2: key check, HKDF-SHA256, seeds()
│   ├── state_map.py      Stage 3: seed -> (x0, y0)
│   ├── isc_step.py       Stage 4: one ISC iteration (step_ref, step_vec)
│   ├── generator.py      Stage 4-5a: 256-lane burn-in + byte extraction (m_byte)
│   ├── sampling.py       Stage 5b: Lemire bounded(), Fisher-Yates S-box/permutation
│   ├── diffusion.py      Stage 6: forward/backward chained diffusion + inverses
│   ├── container.py      ISCI header pack/parse
│   ├── cipher.py          encrypt/decrypt orchestration, stage sequencing
│   ├── selftest.py        profile 1 self-test vs. _selftest_vectors.py
│   ├── fdlibm_ref.py / fdlibm_np.py   Netlib fdlibm 5.3 scalar/vector port
│   └── errors.py
├── isc_seq/
│   ├── isc_map.py          isc_step() / legacy_step() — single-orbit research recurrence
│   ├── extract.py          sign_bits, arccos8, frac8 (frac_byte), mantissa8, mantissa8_xor
│   ├── trajectory.py, nist.py, periodicity.py, stats.py, report.py, sts_official.py, experiment.py
├── isc_cipher_kat/
│   ├── gate_r.py            reproducibility checker vs. stored KAT vectors
│   ├── make_kat.py / make_kat_ext.py
│   └── vectors/             PROVENANCE.json, cipher_kat.json, stream_kat.json, traj_kat.json, trig_kat*.gz
├── isc_eval/                V-FULL/V-LINEAR/V-STREAM/V-PERM/V-CHACHA harness, AEAD baselines, attacks (A1-A15)
├── tests/                   test_isc_cipher_{auth,kdf_state,numeric,roundtrip,sampling_diffusion}.py,
│                            test_isc_eval_harness.py, test_isc_map.py, test_nist.py, test_periodicity.py,
│                            test_sts_official.py, test_trajectory_extract.py, test_experiment.py
└── research/                algorithm_design.md (669 lines), threat_model.md, checkpoint*_report.md, etc.
```
`[VERIFIED SOURCE]` — directory listing obtained via a recursive file search, 11 November 2026.

---

## 2. End-to-end call graph: key + nonce → ciphertext bytes

`[VERIFIED SOURCE]`, traced through `isc_cipher/cipher.py:_encrypt` (L56-70):

```
encrypt_bytes(key, data, h, w, c)                              cipher.py:73-75
  nonce = os.urandom(16)
  _encrypt(key, data, h, w, c, nonce, backend="numpy", profile=1)    cipher.py:56
    key = check_key(key)                                       kdf.py:26-29        (32 bytes, bytes/bytearray)
    ensure_selftest(1, "numpy")                                 selftest.py:63-66
    m = _materials(key, nonce, 1, h, w, c, "numpy")              cipher.py:33-44
      der = Derivation(key, nonce, context(1,1,h,w,c))           kdf.py:56-63  ctx = 17 bytes (kdf.py:47-49)
        _prk = HMAC-SHA256(salt=nonce, ikm=key)                  kdf.py:63, 32-33   (RFC 5869 extract)
      iv_f, iv_b = der.ivs()                                     kdf.py:74-76  (derive("iv", 2))
      seeds = der.seeds()                                        kdf.py:78-80
        -> {stream: [hkdf_expand(prk, ctx+0x00+"lane/<stream>/<0000..0063>", 16) for 64 lanes]} x4 streams
      streams = _build_generators(seeds, "numpy", 1)              cipher.py:47-49 -> generator.build_streams  generator.py:111-135
        states = {g: [seed_to_state(s) for s in seeds[g]] for g in STREAMS}        state_map.py:21-23
          seed_to_ints: alpha = BE64(s[0:8])>>11, beta = BE64(s[8:16])>>11          state_map.py:11-14
          int_to_coord: m * 2**-52 - 1.0                                            state_map.py:17-18
        x = [256 lane x0's, stream-major order sbox,perm,fwd,bwd]                   generator.py:129-130
        for _ in range(1024): x, y = step_vec(x, y, profile=1)                       generator.py:131-132 (BURN_IN=1024, line 19)
        -> 4 x NpStream(64 lanes each)                                               generator.py:133-134
      S, S_inv = sampling.build_sbox(streams["sbox"])             cipher.py:39 -> sampling.py:42-52
      pi = sampling.build_permutation(streams["perm"], n)         cipher.py:40 -> sampling.py:55-62
      a = streams["fwd"].take(n)                                  cipher.py:41  -> NpStream.take()  generator.py:82-103
      b = streams["bwd"].take(n)                                  cipher.py:42
      k_mac = der.mac_key(); k_kcv = der.kcv_key()                 cipher.py:43 -> kdf.py:68-72
    q = apply_permutation(data, pi)                                cipher.py:64 -> sampling.py:65-67  q_k = p[pi[k]]
    u = diffusion.forward(q, a, S, iv_f)                            cipher.py:65 -> diffusion.py:13-19
    body = diffusion.backward(u, b, S, iv_b)                        cipher.py:66 -> diffusion.py:22-29
    kcv = HMAC-SHA256(k_kcv, kcv_state_bytes(streams))[:8]           cipher.py:52-53,67 -> generator.py:138-140
    hdr = Header(profile, c, h, w, nonce, kcv).pack()                container.py:31-46
    tag = HMAC-SHA256(k_mac, hdr || body)                            cipher.py:69
  return hdr || body || tag
```

Decryption (`cipher.py:78-94`) runs the same `_materials` pipeline (so the generator, sampling, and
diffusion keys/bytes are regenerated identically), but **only after** `hmac.compare_digest(tag, expected)`
succeeds (`cipher.py:85-86`); `_build_generators` is never reached before that check (enforced in
`tests/test_isc_cipher_auth.py` via a `monkeypatch.setattr(cipher, "_build_generators", boom)` fixture
named `no_generator`, defined at `tests/test_isc_cipher_auth.py:27-31`, used by at least 9 test functions
including `test_every_bit_flip_rejected_before_generation` (L46) and `test_wrong_keys_rejected_before_generation`
(L94)). `[VERIFIED SOURCE]`

---

## 3. Byte extraction point — exactly where `M(v)` happens

`[VERIFIED SOURCE]` There is exactly **one production byte-extraction function**, defined twice (once per backend)
but mathematically identical:

- Reference/scalar backend: `generator.py:25-26`
  ```python
  def m_byte(v):
      return _pack_d(v)[6]          # big-endian byte 6 = bits 8..15 of the binary64 encoding
  ```
  called from `RefStream._output_step` at `generator.py:52-53` (`buf.append(m_byte(x)); buf.append(m_byte(y))`).

- NumPy/vectorised backend: `generator.py:96-98` inside `NpStream.take`:
  ```python
  mb = np.stack([xs, ys], axis=-1).view(np.uint64)
  new = ((mb >> np.uint64(8)) & np.uint64(0xFF)).astype(np.uint8).tobytes()
  ```
  i.e. `(bits(v) >> 8) & 0xFF`, bit-identical to `m_byte`.

Both implementations extract **bits 8-15 of the raw IEEE-754 binary64 encoding** (not masked to the
52-bit mantissa field first — the shift-by-8-and-mask-0xFF operation only ever touches bits 8-15 of the
64-bit word, which for any normalized double in `(-1, 1)` fall entirely inside the mantissa, so the
numeric result is the same as if the exponent/sign bits had been masked off first; this is a property of
the bit position, not of an explicit mask). This matches the project's own specification,
`research/algorithm_design.md:386`: `M(v) = (bits(v) >> 8) & 0xFF # bits 8..15 of the binary64 encoding`,
and `algorithm_design.md:390`: *"Values exactly ±1 or 0 have mantissa field 0, so M = 0. This is allowed
and not special-cased."* `[DESIGN DOC]`

**There is no call anywhere in `isc_cipher/` to `isc_seq.extract.frac_byte` or any k=14-style
scaled-floor-modulo function.** A repository-wide search for `frac_byte|frac8` (`[EXECUTED]`,
`grep -rn "frac_byte\|frac8" --include=*.py .`) found it referenced only in `isc_seq/extract.py` itself,
in `experiments/run_official_sts.py:178` (a CLI default argument string), and in
`tests/test_trajectory_extract.py:86-89` (a 3-case unit test of `frac_byte` alone, unrelated to the cipher).
No file under `isc_cipher/` imports `isc_seq`.

---

## 4. The 256-lane generator, precisely

`[VERIFIED SOURCE]`, from `generator.py` and `kdf.py`:

- **Streams and lanes:** `STREAMS = ("sbox", "perm", "fwd", "bwd")` (`kdf.py:16`), `LANES = 64` (`kdf.py:17`).
  Total lanes = 4 × 64 = 256.
- **Seed derivation:** `Derivation.seeds()` (`kdf.py:78-80`) returns, for each stream `g` and lane `l` in
  `0..63`, `hkdf_expand(prk, ctx || 0x00 || f"lane/{g}/{l:04d}", 16)` — a 16-byte seed per lane, 256 total,
  all derived from the single PRK via domain-separated HKDF-Expand labels (`lane_label`, `kdf.py:52-53`).
  Collision between any two labels is impossible because the label strings are syntactically distinct
  (different stream name and/or zero-padded lane index).
- **Seed → initial state:** `state_map.seed_to_state` (`state_map.py:21-23`) splits the 16-byte seed into
  two 8-byte halves, each interpreted as big-endian uint64, right-shifted by 11 bits (`seed_to_ints`,
  `state_map.py:11-14`, giving a 53-bit integer `m` in `[0, 2^53)`), then mapped to
  `float(m) * 2**-52 - 1.0` (`int_to_coord`, `state_map.py:17-18`). Since `2**-52` is an exact power of two
  and `m < 2^53`, this multiplication and subtraction are both exact IEEE-754 operations (no rounding),
  and the result lies in `[-1.0, 1.0 - 2**-52]` — i.e. **guaranteed inside the intended `[-1, 1]` domain**.
  **Duplicate initial conditions across lanes are possible in principle** (the map is `2^128 seed space -> 2^106 grid`,
  a 2^22-to-1 contraction per coordinate) but are astronomically unlikely for independently-HKDF-derived
  seeds; no code-level duplicate check exists, and none of the 256 lanes are checked for distinctness anywhere
  in `generator.py` or `kdf.py`. `[VERIFIED SOURCE: absence of such a check]`
- **Lane scheduling — numpy backend (`NpStream`, `generator.py:69-103`, the backend actually used by
  `cipher.py` default and by `encrypt`/`decrypt`):**
  - `build_streams` (`generator.py:111-135`, numpy branch `124-134`) concatenates all 256 lane initial
    states **stream-major**: `x = [... 64 sbox x0's, 64 perm x0's, 64 fwd x0's, 64 bwd x0's ...]`
    (`generator.py:129-130`), then burns in **all 256 lanes together** in one vectorised loop
    (`for _ in range(burn_in): x, y = step_vec(x, y, profile)`, `generator.py:131-132`) before slicing
    the 256-length arrays back into 4 arrays of 64 (`generator.py:133-134`).
  - **Within each stream**, bytes are produced by `NpStream.take(m)` (`generator.py:82-103`): it computes
    how many full "output steps" `k` are needed (`k = ceil(need / BYTES_PER_STEP)`, `BYTES_PER_STEP = 2*LANES = 128`,
    `generator.py:20,87`), runs `step_vec` `k` times advancing **all 64 lanes of that stream simultaneously**
    (`generator.py:91-94`), and for each of the `k` steps stacks `(x,y)` for all 64 lanes into shape
    `(k, 64, 2)`, reinterprets as uint64 and right-shifts by 8 (`generator.py:97-98`), then flattens to bytes
    via `.tobytes()`. NumPy's C-order flattening of a `(k, 64, 2)` array means the byte order is:
    **step 0: lane 0 x, lane 0 y, lane 1 x, lane 1 y, ..., lane 63 x, lane 63 y; then step 1: lane 0 x, ...**
    This is confirmed by the module docstring (`generator.py:6-8`): *"output step: every lane of the stream
    advances once, then emits M(x_l), M(y_l) for l = 0..63 ... Bytes are consumed strictly in order"*.
  - **Formal relationship** (derived from the above, not quoted verbatim from code):
    for global byte index `i` within one stream, with `BYTES_PER_STEP = 128`:
    ```
    step_index  = i // 128                     (lane-local iteration count = burn_in + step_index + 1)
    within_step = i % 128
    lane_index  = within_step // 2              (0..63)
    coord       = "x" if within_step % 2 == 0 else "y"
    ```
    i.e. **scheduling is round-robin across the 64 lanes of a stream, two bytes (x then y) per lane per
    round**, confirmed by direct derivation from `generator.py:88-99`, not merely assumed.
  - **Reference/scalar backend (`RefStream`, `generator.py:29-66`)** burns in and outputs **one lane at a
    time, fully sequentially** per `_output_step` (`generator.py:46-54`: a Python `for s in self.states`
    loop), but the *order of bytes appended to the buffer* is identical — lane 0 (x,y), lane 1 (x,y), ...,
    lane 63 (x,y) — so `RefStream` and `NpStream` must and do (per Gate R below) produce byte-identical
    streams for the same inputs and profile 1.
- **Four streams are never mixed.** `sbox`, `perm`, `fwd`, `bwd` each have their own independent 64-lane
  `NpStream`/`RefStream` object (`generator.py:133-134`, `122-123`); `cipher.py:39-42` calls
  `streams["sbox"]`, `streams["perm"]`, `streams["fwd"].take(n)`, `streams["bwd"].take(n)` strictly
  separately. There is no code path where bytes from one stream role feed into another's consumption.
- **Does one shared recurrence function govern every step?** Yes — `isc_step.step_vec` (numpy) /
  `isc_step.step_ref` (reference) is the single call site for advancing lane state in both burn-in
  (`generator.py:131-132` / `121`) and output (`generator.py:91-94` / `50`). `isc_step.py:58-98` (`step_vec`)
  and `isc_step.py:27-55` (`step_ref`) both dispatch to `fdlibm_np`/`fdlibm_ref` for profile 1 sin/cos
  (`isc_step.py:62-63`, `isc_step.py:10`), so **yes, fdlibm governs every trigonometric evaluation under
  profile 1**, in both burn-in and output phases, with no exception.
- **Non-finite / argument-guard behaviour:** `isc_step.py:21-24` (`_guard`) and `isc_step.py:88-91` (vector
  guard) raise `ValueError` if any `SIN/COS` argument has `|arg| >= 24` — **not** if the *state* `x,y`
  itself becomes non-finite. There is **no explicit NaN/Inf check on `x,y` anywhere in `generator.py` or
  `isc_step.py`**; a non-finite state would propagate until (if ever) it produced an out-of-bound trig
  argument, at which point `_guard` would raise. `[VERIFIED SOURCE: no clipping/normalization code found]`
  No state clipping or renormalization exists anywhere in the generator; the ISC recurrence is trusted to
  stay in `[-1,1]` by construction of its own equations (`y_{n+1} = 2 sin^2(...) - 1 ∈ [-1,1]` always, by
  the algebra of the map itself, independent of the extraction method).
- **Final-state use in KCV:** `generator.kcv_state_bytes` (`generator.py:138-140`) concatenates, for each
  stream in canonical order, `final_state_bytes()` (`generator.py:64-67` reference / `105-108` numpy):
  64 lanes × (BE64 x, BE64 y) followed by `steps.to_bytes(8, "big")` (the count of **output steps actually
  taken**, i.e. how many times `take()` advanced the lanes beyond burn-in). `cipher._kcv`
  (`cipher.py:52-53`) HMACs this with `k_kcv`. This binds the KCV to the *exact post-burn-in, post-output
  final lane state*, which only matches on decryption if every upstream computation (burn-in count, step
  function, profile) reproduced bit-for-bit — this is the mechanism that detects any numerical divergence
  between encryption and decryption environments (`errors.NumericalDivergenceError`, raised at
  `cipher.py:92-93` if KCV mismatches after successful tag verification).

---

## 5. Statistical populations implied by the 256-lane architecture

`[DERIVED/ANALYSIS]`, not previously stated elsewhere this precisely: the lane/stream architecture produces
**five distinct statistical populations that must not be conflated**:

1. **A single long orbit** (what Step 1.1 characterized): one `(x0,y0)`, `T=5000` burn-in, `N=10^6`
   sequential samples from one trajectory. No interleaving, no lane mixing.
2. **A single lane's own trajectory** inside the cipher: one of the 256 HKDF-seeded `(x0,y0)` points,
   `T=1024` burn-in, with samples spaced **128 bytes apart in the emitted stream** (one lane emits 2 bytes
   per 128-byte round). Equivalent in principle to population 1 but with a different burn-in and a
   different, HKDF-derived, initial condition.
3. **One interleaved stream** (e.g. the actual `fwd` keystream used for `a`): 64 lanes' outputs interleaved
   round-robin, 2 bytes/lane/round. Adjacent bytes in this stream come from *different, independent* lanes,
   not consecutive iterations of one orbit — so low adjacent-byte autocorrelation in this population could
   reflect lane independence rather than (or in addition to) the map's own mixing property. This is exactly
   the distinction the Phase 1 `architecture_discrepancies.md` §4 raised but did not test.
4. **Across the four stream roles** (`sbox` vs `perm` vs `fwd` vs `bwd`): each role's 64 lanes are seeded
   with distinct HKDF labels, so cross-stream comparison asks whether domain-separated-but-structurally-
   identical generators behave statistically alike — a different question from within-stream correlation.
5. **Across all 256 lanes globally** (ignoring stream grouping): the full population of HKDF-seeded ISC
   orbits under `T=1024` burn-in, relevant to questions like "do any two lanes ever produce correlated or
   near-duplicate output" (relevant to the "lane collision" caveat already flagged in Phase 1's
   `architecture_discrepancies.md` §4).

None of Step 1.1's NIST/Chi-square/MI results were computed on populations 2-5; they used population 1 only.
`research/algorithm_design.md:638-639` independently confirms this gap in the project's own records: the
design document's "Evidence register" table lists `G_prior` (population-1-style, profile 2, T=5000) as
tested, and explicitly lists `G_v1` (profile 1, HKDF seeds, 64 lanes interleaved, T=1024 — i.e. population 3
of the actual shipped generator) as **`[OPEN]: not tested`**. `[DESIGN DOC — self-reported gap]`

---

## 6. Independently executed verification of previously-reported test results

`[EXECUTED]` 11 November 2026, same machine/environment as this audit:

| Command | Result | Compare to Phase-1-reported result |
|---|---|---|
| `python -m pytest tests/test_isc_cipher_auth.py tests/test_isc_cipher_kdf_state.py tests/test_isc_cipher_numeric.py tests/test_isc_cipher_sampling_diffusion.py -q` | **130 passed in 48.60s** | Consistent: these 4 files + roundtrip = 161 collected tests total (see next row); 159 passed + 2 skipped overall means the 2 skips are inside this 132-test subset (132 collected here, 130 passed = 2 skipped), matching the previously reported "2 skipped" exactly. |
| `python -m pytest tests/test_isc_cipher_auth.py ... tests/test_isc_cipher_roundtrip.py --collect-only -q` | **161 tests collected** | Matches 159 passed + 2 skipped = 161 exactly. |
| `python -m pytest tests/test_isc_eval_harness.py -q` | **16 passed in 35.37s** | Matches previously reported "16 passed" exactly (duration differs: 35.37s here vs. 81.43s reported — machine-load dependent, not a discrepancy in outcome). |
| `python -m pytest tests/test_isc_cipher_roundtrip.py -q` | **29 passed, 2 skipped in 391.15s (0:06:31)** | Combined with the 130-passed subset above: 130+29=159 passed, 0+2=2 skipped, 132+29=161 collected — matches the previously reported "159 passed, 2 skipped" in **731.61s total** (Phase 1) vs. **48.60s + 391.15s = 439.75s** measured here, exactly in outcome, faster in wall-clock (machine-load dependent). |
| `python -I isc_cipher_kat/gate_r.py --backend numpy --label PHASE2-verify` | **overall: PASS** — `R-fdlibm-hashes: PASS (0.0s)`, `R-trig-KAT: PASS (0.3s)`, `R-trajectory-KAT: PASS (125.3s)`, `R-stream-KAT: PASS (1.6s)`, `R-cipher-KAT: PASS (29.3s)`. Report written to `results/cipher_validation/gate_r_PHASE2-verify_numpy_20261111T110629Z/`. | Matches previously reported "OVERALL: PASS" across all 5 stages exactly. |

Where a specific claim elsewhere in these 8 documents depends on a result not yet available at the time it
was written, it is marked `[PRIOR REPORT, not independently re-executed in this pass]`. See
`phase_2_technical_decision_log.md` §"Test execution log" for the final status of the roundtrip suite.

---

## 7. Answer to "does one shared recurrence function or multiple implementations exist?"

`[VERIFIED SOURCE]` Two *implementations* exist by necessity (scalar `step_ref` for the pure-Python
reference backend, vectorised `step_vec` for NumPy — `isc_step.py:27-55` and `58-98`), but they are proven
(not merely intended) to be bit-identical: `tests/test_isc_cipher_numeric.py` is reported (Phase 1,
`[PRIOR REPORT]`) to test "bit-for-bit identity between scalar `step_ref` and vectorized `step_vec`" over
500 random vectors × 300 steps. A **third** recurrence implementation exists in `isc_seq/isc_map.py:44-63`
(`isc_step`, confusingly same name as the cipher's module) — this is the **research-only** single-orbit
function used by Step 1.1's characterization and by `isc_eval`/`isc_seq` experiments; it is mathematically
the same recurrence but is a structurally separate piece of code from `isc_cipher/isc_step.py`, deliberately
so per its own docstring (`isc_cipher/isc_step.py:12-13`): *"Frozen parameters ... defined here (not imported
from isc_seq, which needs NumPy) so that the pure-Python reference path runs without NumPy; tests assert
equality with isc_seq.isc_map.FROZEN_PARAMS."* A fourth variant, `isc_seq.isc_map.legacy_step`
(`isc_seq/isc_map.py:66-77`), intentionally reproduces an older, non-bit-identical expression
(`x**2` via `pow()` instead of `x*x`) and is documented as diverging from `isc_step` after "a few dozen
iterations" (`isc_seq/isc_map.py:17-22`) — this is **not** used anywhere in `isc_cipher/`.
