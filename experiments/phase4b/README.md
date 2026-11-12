# Phase 4B — Image-Level Encryption Experimental Evaluation

Experimental evaluation of the EXISTING `isc_cipher` implementation (audited, unmodified, in
Phase 4A) applied to images. Nothing under `isc_cipher/`, `isc_seq/`, `isc_eval/`, `tests/`, or
any earlier-phase artifact was modified. All new code lives in this directory.

## Verified interfaces (re-checked against current source, not assumed from Phase 4A)

- Public API: `isc_cipher.encrypt_bytes(key, data, h, w, c, backend, extraction)` /
  `decrypt_bytes(key, z, backend)`, and the NumPy-array wrappers `encrypt`/`decrypt`
  (`isc_cipher/cipher.py:105-176`). Neither accepts a nonce.
- Fixed-nonce TEST-ONLY mechanism: `isc_cipher._testing.encrypt_bytes_with_nonce_TEST_ONLY`
  (`isc_cipher/_testing.py:12-14`), used here ONLY for the controlled plaintext-differential
  (Experiment E) and key-sensitivity (Experiment F) comparisons, exactly as Phase 4A described.
  It calls the same `_encrypt()` the public API uses, so it does not alter production defaults
  (`encrypt_bytes` still draws `os.urandom(16)` whenever this test-only path is not used).
- `isc_cipher.container.parse(z) -> (Header, body, tag)` isolates the encrypted BODY from
  header/nonce/KCV/tag by construction (`isc_cipher/container.py:92-131`); `common.encrypted_body()`
  wraps this and is the ONLY way this phase's code extracts ciphertext bytes for statistics,
  satisfying the "never include header/nonce/tag in image statistics" validity rule.
- Supported channels: 1 (grayscale) or 3 (RGB) only; RGBA (`c=4`) is rejected by
  `_image_to_bytes` (`isc_cipher/cipher.py:155-158`). Supported dtype: `uint8` only.
- Extraction profile selection: `extraction=EXTRACTION_MANTISSA8_V1` (default, =1) or
  `EXTRACTION_K14_SCALED_MODULO_V1` (=2), imported from `isc_cipher.generator`.
- Dimensions/channels ARE authenticated: they are part of the packed header, which is covered
  by the HMAC tag (`hdr + body` is MAC'd, `isc_cipher/cipher.py:101,134`).
- Nonce IS stored in the container (offset 12-28) and is recovered from the header on decrypt.

## Pilot-based runtime decisions (mandatory, requested explicitly)

Before sizing Experiment E (NPCR/UACI) and Experiment F (key sensitivity), a small pilot of
single `encrypt` calls was run at several sizes/backends (see `logs/pilot_timing.json` for the
raw numbers and the exact arithmetic). Headline results:

| shape | backend | seconds |
|---|---|---|
| 32x32x1 (n=1024) | numpy | 1.35 |
| 64x64x1 (n=4096) | numpy | 1.41 |
| 128x128x1 (n=16384) | numpy | 2.03 |
| 256x256x1 (n=65536) | numpy | 4.07 |
| 256x256x1, k14 profile | numpy | 4.14 |
| 256x256x3 (n=196608) | numpy | 10.07 |
| 512x512x1 (n=262144) | numpy | 12.76 |
| 32x32x1 / 64x64x1 / 128x128x1 / 256x256x1 | reference | 2.27 / 2.39 / 2.72 / 4.11 |

**Interpretation**: there is a large fixed per-call cost (~1.3s, dominated by the 256-lane x
1024-iteration burn-in) plus a marginal cost of ~42 microseconds/byte dominated by the inherently
sequential Fisher-Yates permutation-construction loop (this is why the numpy and reference
backends converge at large n: that loop is not meaningfully vectorizable).

**Decision for Experiment E (NPCR/UACI)**: a full 3-size x 3-image-type x 3-position x 2-profile
matrix would need on the order of 100+ encryptions and approach 5+ minutes; instead the full
sweep (3 image types x 3 positions) runs only at the two cheap sizes (64, 128), the 256x256 size
is reduced to positions-only with one image type, and a small RGB channel-separate set and a
small k14-profile cross-check are added. Estimated ~89s; see `results/experiment_E_summary.json`
for the actual measured `elapsed_sec`.

**Decision for Experiment F (key sensitivity)**: the key is 256 bits; an exhaustive per-bit sweep
(256 positions) at even the smallest size would cost roughly 256 x 2 x 1.4s =~ 717s by itself, and
multiplying that across sizes was judged not worth the marginal evidence for a README/phase-report
deliverable. Instead, 16 bit positions (every 16th bit, i.e. one per two key bytes) are swept at
both 64x64 and 128x128, plus a reduced 8-position sweep at 256x256. Estimated ~175s; see
`results/experiment_F_summary.json` for the actual measured `elapsed_sec`.

Both decisions trade an exhaustive sweep for a *stratified, still-meaningful* sample, per the
user's explicit instruction ("meaningful repeated trials, not hundreds of redundant runs").

## Directory layout

```
config.py                   fixed seeds/key/nonce, dataset & trial-matrix sizing
common.py                   shared stats/crypto helpers (entropy, chi2, correlation, NPCR/UACI, ...)
generate_dataset.py         synthetic image generators + manifest (Experiment / Section 4)
stats_core.py                shared single-pass encryption cache for B/C/D/G
experiment_recovery.py       Experiment A (exact recovery) + shape/dtype edge cases
experiment_histogram.py      Experiment B
experiment_entropy.py        Experiment C
experiment_correlation.py    Experiment D
experiment_npcr_uaci.py       Experiment E
experiment_key_sensitivity.py Experiment F
experiment_profiles.py        Experiment G
experiment_performance.py     Experiment H
experiment_edge_cases.py      Experiment I (small dims + structure-leakage check)
experiment_tamper.py          Experiment J (small regression; Phase 4A already covers this in depth)
run_all.py                    runs everything in one command
analyse_results.py            collects results/*.csv + *.json into results/master_summary.json
results/                      CSV/JSON outputs
plots/                        PNG visualizations
logs/                         pilot_timing.json and this README's supporting numbers
```

## Reproducing

```
cd experiments/phase4b
python run_all.py          # full pipeline
python analyse_results.py  # collect everything into results/master_summary.json
```

Every `experiment_*.py` is also independently runnable (`python experiment_npcr_uaci.py`, etc).
All randomness is seeded from `config.MASTER_SEED` / the fixed `config.BASE_KEY` /
`config.BASE_NONCE`; re-running produces identical dataset images and identical trial plaintexts
(the only inherent non-determinism is encryption nonce generation when the PUBLIC API is used,
e.g. in Experiment A/B/C/D/H, which is why Experiments E and F use the TEST-ONLY fixed-nonce path
instead).

## Known limitations of this harness (read before interpreting results)

- No external natural test images (Lena/Baboon/etc.) were fetched; see
  `generate_dataset.py`'s module docstring for why, and note that the existing (frozen) Phase 4A
  test suite already exercises `scikit-image`'s bundled sample photographs for round-trip
  correctness, so this gap is not a complete absence of natural-image coverage project-wide.
- `experiment_performance.py`'s per-phase timing breakdown calls `isc_cipher`'s already-exposed
  internal functions (`_build_generators`, `_kcv`, `Derivation`, etc.) directly from this
  directory to time sub-stages, because the Phase 4B instructions explicitly forbid adding
  instrumentation to the production cipher code. This reproduces `_encrypt()`'s stage order by
  hand; if a future change to `isc_cipher/cipher.py` reorders those stages, this file's
  decomposition would silently go stale (flagged, not fixed, since fixing it means watching
  `cipher.py` rather than editing it).
- `stats_core.build_stats_cache()` keys its on-disk cache only on `(extraction, sizes)`, so
  running `experiment_profiles.py` (which builds a k14 cache) after the B/C/D experiments causes
  the next B/C/D run to silently rebuild its own (mantissa8) cache rather than reuse a stale one
  -- correct, but means re-running `run_all.py` repeatedly does more encryption work than strictly
  necessary. Not a correctness bug; noted as an inefficiency.
