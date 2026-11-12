# Phase 3B pooled chi-square anomaly investigation (Stage 5)

Status: **PARTIALLY RESOLVED** — the anomaly reproduces exactly from raw seeds (not a bug/aggregation error), and a concrete, localized source is identified; full independence-adjusted inference is not attempted here.

Script: `verification/chisq_investigation.py`. Command: `python experiments/phase5_followup/verification/chisq_investigation.py`. Output: `results/phase3b_chisquare_investigation.json`. Original frozen artifacts (`experiments/phase3b/raw/stage_a_stream_metrics.csv`, `isc_pbl/phase_3b_experiment_report.md`) were **read, not modified**.

## G1/G2 — Original observation, reproduced exactly
All 6 pooled-stream chi² values (extraction 1 = `mantissa8_v1`, extraction 2 = `k14_scaled_modulo_v1`; seeds A/B/C; streams `sbox`,`bwd`; 8,000,000 bytes, same `SEED_CONFIGS`/burn_in=1024/125,000 bytes-per-lane as `experiments/phase3b/common.py`) were **independently regenerated from the raw key/nonce seeds** and matched the frozen CSV to <1e-6:

| extraction/seed | stream | chi² (regen) | chi² (stored) | p |
|---|---|---|---|---|
| 1/A | sbox | 338.56 | 338.56 | 3.5e-4 |
| 1/A | bwd | 313.09 | 313.09 | 7.6e-3 |
| 1/B | sbox | 362.05 | 362.05 | 1.2e-5 |
| 1/B | bwd | 345.29 | 345.29 | 1.4e-4 |
| 1/C | sbox | 341.96 | 341.96 | 2.2e-4 |
| 1/C | bwd | 315.94 | 315.94 | 5.6e-3 |
| 2/A | sbox | 261.77 | 261.77 | 0.37 |
| 2/A | bwd | 308.19 | 308.19 | 1.3e-2 |
| 2/B | sbox | 267.64 | 267.64 | 0.28 |
| 2/B | bwd | 250.47 | 250.47 | 0.57 |
| 2/C | sbox | 258.61 | 258.61 | 0.43 |
| 2/C | bwd | 280.13 | 280.13 | 0.13 |

Degrees of freedom = 255 (256 bins). No duplicated bytes, no mis-pooling found: `generate()` returns exactly `bytes_per_lane*64` bytes per stream, the chi² implementation (`common.chisquare_uniform`) is the standard `Σ(O-E)²/E` with `scipy.stats.chi2.sf(., 255)`. **This rules out an implementation or aggregation bug** — the low p-values are a genuine, deterministic, reproducible property of the `mantissa8_v1` extraction's byte output, not noise or a one-off artifact.

## G3 — Diagnosis: the effect is localized in the low nibble
A 100-trial i.i.d.-uniform null gives chi²(255) ≈ 257.9 ± 26.6 (matches the theoretical χ²₂₅₅ mean/SD of 255/√510≈22.6, confirming the test calibration is sound). All 6 `mantissa8_v1` (extraction=1) values (313–362) sit only 1–4σ above that null for the **full byte**, but splitting the byte by nibble is decisive:

| | high nibble χ²(df=15) | low nibble χ²(df=15) | expected (df=15) |
|---|---|---|---|
| extraction 1 (mantissa8), 6 runs | 7–21 (normal) | **63–91** | 15 (σ≈5.5) |
| extraction 2 (k14), 6 runs | 9–22 (normal) | 8–18 (normal) | 15 |

A low-nibble χ² of ~75–90 against an expected 15±5.5 is roughly 11–14 standard deviations — a strong, highly significant, and **specific** effect confined to the 4 least-significant bits of `mantissa8_v1`'s output byte. The high nibble is statistically unremarkable in both extractions. This matches `mantissa8_v1`'s definition (bits taken directly from the float64 mantissa, per `isc_cipher/generator.py`): the low-order mantissa bits of a value produced by composing `sin`/`cos` with modest-amplitude chaotic coordinates are more weakly mixed than the top bits, so a small, reproducible non-uniformity in the bottom 4 bits is consistent with the extraction method, not a bug in it. `k14_scaled_modulo_v1` rescales/quantizes differently and does not show this.

Supporting diagnostics (all stored in the JSON):
- **Independence:** block-count variance ratio ≈ 0.996–1.006 (no clustering); lag-1 high-nibble-pair χ²(255) within [219,293], consistent with the i.i.d. null's spread — no serial dependence detected.
- **Reproducibility of the effect itself:** both halves of each 8M-byte stream independently show elevated χ² for extraction 1 (split-half values both >270 in all 6 cases) vs. normal split halves for extraction 2 — the effect is not a one-half fluke.
- **Effect size:** Cohen's w for the full byte is only 0.0027–0.0037 (tiny; `max_abs_rel_bin_dev` stays small) — this is a **statistically real but practically small** deviation, detectable only because n=8,000,000 gives the chi² test enormous power.
- **Seed/config:** identical pattern across all 3 independent seeds and both streams tested (`sbox`,`bwd`) — not a single-seed coincidence.
- **No bit-pattern anomaly for extraction 2:** confirms the effect is extraction-specific, not an artifact of the pooling/interleaving code shared by both extractions.

## G4 — Interpretation and manuscript wording
- The pooled chi² anomaly for `mantissa8_v1` **reproduces deterministically from the documented seeds** and is **not** an implementation, aggregation, or double-counting bug.
- It traces to a small, real non-uniformity in the 4 least-significant bits of that extraction's byte output; the top 4 bits and `k14_scaled_modulo_v1` as a whole show no such effect.
- Per-lane statistics (Section 3.2 of the original report) are indistinguishable between the two profiles — the effect only becomes visible once 64 lanes' low nibbles are pooled into 8,000,000 samples, i.e. it is a **large-sample-only** finding, not something that would affect a single encryption's keystream distinguishably from random at achievable sample sizes.
- **Defensible wording:** "Under extended pooled-sample testing (8×10⁶ bytes), the `mantissa8_v1` extraction profile shows a small, statistically significant (p≈10⁻³–10⁻⁵), and reproducible non-uniformity confined to its 4 least-significant output bits; the `k14_scaled_modulo_v1` profile and the top 4 bits of `mantissa8_v1` show no such effect. The deviation's effect size is small (Cohen's w≈0.003) and was not observed in any per-lane (125,000-byte) statistic; it should not be interpreted as evidence against single-message keystream quality, but `k14_scaled_modulo_v1` is the better-supported extraction profile where large pooled samples matter." Do not claim "no statistical anomaly" for `mantissa8_v1`, and do not claim the anomaly proves a security weakness — neither is supported by the evidence here.

## Remaining uncertainty
- The claim that low-order mantissa bits are "more weakly mixed" is a plausible mechanism, not independently derived from the map's analytic properties here; a rigorous bit-level entropy argument (e.g., tracking how the chaotic map's Lyapunov exponent translates to mixing time per mantissa bit) was not attempted.
- Only `sbox` and `bwd` streams were re-examined in depth (the two flagged in the original report); `fwd`/`perm` were not re-diagnosed at the nibble level here.
- Formal correction for the implicit multiple comparisons across streams/seeds/extractions was not applied; the Bonferroni-style bounds the original report already uses for lane-level ACF are a separate test, not reused here for this chi² statistic.
