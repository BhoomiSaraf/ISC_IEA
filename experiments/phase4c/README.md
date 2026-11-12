# Phase 4C — Confirmatory Image Validation and Performance Profiling

Isolated from `experiments/phase4b/` (read-only reference) and from
`isc_cipher/`, `isc_seq/`, `isc_eval/`, `tests/` (not modified at all).

## Natural-image source decision

`skimage.data` (scikit-image's bundled sample-data package, already an
existing dependency) was used instead of attempting a network download of
USC-SIPI/Kodak datasets. This environment's outbound network access for
fetching an external dataset was not assumed reliable, and `skimage.data`
already ships real photographs/scientific images locally (BSD-3-Clause
license). This substitution is documented explicitly, not a silent
fallback to synthetic data — see `acquire_images.py`'s module docstring.

12 base images acquired (13 candidates; `lily`/`eagle` failed — require the
optional `pooch` dependency, not installed; failures recorded in
`logs/acquire_images_failures.json`, not hidden). `cat` was excluded after
discovering it is a byte-for-byte alias of `chelsea` in this skimage
version (`np.array_equal(skd.cat(), skd.chelsea()) == True`) — kept as one
image, not double-counted as two independent samples.

18 gray/RGB variants produced after resizing to a 256px-longest-side cap
(`prepare_dataset.py`), preserving aspect ratio, via
`skimage.transform.resize` (anti-aliased, re-quantized to uint8 — not a
lossy *compression*, but not a lossless resize either; documented, not
hidden).

## Pilot-based runtime decisions (mandatory, run before any full-scale track)

`pilot_timing.py` measured, on one portrait image (astronaut, 256-class
gray and RGB):

| | mean sec/call |
|---|---|
| encrypt, gray 256-class | 4.84 |
| decrypt, gray 256-class | 10.74 |
| encrypt, RGB 256-class | 26.11 |
| decrypt, RGB 256-class | 26.28 |

**Track A (natural-image battery):** `mantissa8_v1` on the full 18-variant
dataset estimated at ~371s; confirmed actual total ≈ 216s (faster than
pilot estimate — the single pilot image, astronaut, happened to be among
the slower RGB cases). `k14_scaled_modulo_v1` restricted to a 4-case
subset (astronaut + hubble_deep_field, gray+RGB) rather than the full
dataset, since Phase 4B already found the two profiles statistically
indistinguishable across 63 synthetic images — a small confirmatory subset
on natural images is proportionate, a full second sweep is not.

**Track B (NPCR/UACI):** the original naive plan (5 images × 4 positions ×
3 key/nonce configs, gray, + 3×3 RGB-channel trials = 69 trials) was
estimated at **~1828s (~30 min)** once per-trial-pair cost was actually
measured (22.4s/trial gray, 53.5s/trial RGB — see
`logs/pilot_timing.json`). This was judged disproportionate for a
*confirmatory* check and scaled back to:

- gray: 3 images × 3 positions × 2 key/nonce configs = 18 trials (~404s)
- RGB: 3 channels × 1 key/nonce config, 1 image = 3 trials (~160s)
- **21 trials total, ~564s (~9.4 min) estimated**

This arithmetic, and the actual measured runtime, are both recorded in
`logs/pilot_timing.json` and in the NPCR/UACI section of the final report.

**Track C (profiling/benchmarking):** run strictly after Tracks A and B
finish (not concurrently), per the user's requirement that concurrent
tracks distort timing (observed directly in Phase 4B). Limited to
64/128/256px gray only — 512px and RGB sizes were excluded from this
*confirmatory* re-benchmark given the per-call costs observed above; Phase
4B's `experiment_H` already covers the larger-size/RGB performance surface
and is treated as the primary source for that part of the picture, with
Phase 4C contributing the *component-level* breakdown Phase 4B did not
attempt.

## Files

- `config.py` — paths, seeds, fixed key/nonce, trial-budget constants (with inline arithmetic/decision comments).
- `acquire_images.py` — real natural-image acquisition (skimage.data).
- `prepare_dataset.py` — resize/standardize/manifest.
- `verify_phase4b.py` — independent re-derivation of all 9 Phase 4B summary claims from raw CSV/JSON.
- `pilot_timing.py` — mandatory pilot measurements and resulting trial-budget decisions.
- `experiment_natural_images.py` — Track A: correctness, entropy, histogram chi², adjacent-pixel correlation (folds sections 3.4/5/6/7 of the spec into one script per image/profile, since all four statistics are cheap once a ciphertext is produced — avoids re-encrypting the same image four times for four separate scripts).
- `experiment_npcr_uaci.py` — Track B: plaintext-differential NPCR/UACI using the TEST-ONLY fixed-nonce path.
- `profile_components.py` — Track C: 13 of the 15 listed component timings (burn-in and initial-state construction could not be isolated from each other without modifying `isc_cipher/generator.py`'s `build_streams`; reported as one combined stage, explicitly marked, not estimated apart).
- `benchmark_scaling.py` — Track C: isolated, clean end-to-end scaling re-check (64/128/256 gray).
- `analyse_results.py` — aggregation, 95% CIs, per-image/per-key-nonce/aggregate separation for NPCR/UACI.
- `run_all.py` — runs the full pipeline in the recommended order.

## Reproducing

```
cd experiments/phase4c
python run_all.py
```

or run any script individually; all use `config.MASTER_SEED` / `config.BASE_KEY` / `config.BASE_NONCE`.

Environment: same machine/Python/NumPy/SciPy as Phase 4B (see Phase 4B's
README for the recorded versions); this phase did not re-collect that
information since it is unchanged.
