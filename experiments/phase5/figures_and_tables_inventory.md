# Phase 5 — Figure and Table Inventory

## Figures

| # | Figure | Path | Source data | Status |
|---|---|---|---|---|
| F1 | ISC map trajectory/phase portrait | `ISC_PBL/plots/1_trajectory_graph.png` | Step 1.1 script | READY (verify axis labels/units before final use — not re-opened pixel-by-pixel in this pass) |
| F2 | Bifurcation diagram | `ISC_PBL/plots/2_bifurcation.png`, `2_csi_bifurcation.png` | Step 1.1 script | READY |
| F3 | Lyapunov exponent vs. ω | `ISC_PBL/plots/3_lyapunov.png`, `3_csi_lyapunov.png` | `script/final_freeze_validation.py` | **NEEDS ADDITIONAL EVIDENCE** — confirm whether this plot shows λ₁ alone or the sum, to resolve the 2.73-nats figure (see cross-phase audit) |
| F4 | KS/entropy vs. parameter | `ISC_PBL/plots/4_kolmogorov.png`, `4_csi_ks_entropy.png`, `5_bifurcation_entropy.png` | Step 1.1 script | READY |
| F5 | Final-validation autocorrelation plots | `ISC_PBL/plots/final_validation/1_autocorrelation_x.png` (+ siblings) | Step 1.1 final closure run | READY |
| F6 | Synthetic histogram comparisons (original vs. encrypted-body) | `experiments/phase4b/plots/histogram_*.png` (9 images) | `experiment_B_histogram.csv` | READY — already explicitly labeled "not a valid/decrypted image" per Phase 4B's own convention |
| F7 | Synthetic correlation scatter plots | `experiments/phase4b/plots/correlation_*.png` (15 images) | `experiment_D_correlation.csv` | READY |
| F8 | Synthetic performance scaling | `experiments/phase4b/plots/performance_scaling.png` | `experiment_H_performance.csv` | **NEEDS ADDITIONAL EVIDENCE** — Phase 4C found substantial run-to-run timing variance on this hardware; this plot should carry an explicit variance caveat before publication, or be regenerated with error bars |
| F9 | Natural-image histogram comparisons | `experiments/phase4c/plots/histogram_astronaut_gray.png`, `histogram_rocket_gray.png` | `natural_image_results.csv` | READY, but only 2 of 18 natural-image variants illustrated — representative, not exhaustive; acceptable for a figure, should be captioned as such |
| F10 | Natural-image correlation scatter plots | `experiments/phase4c/plots/correlation_chelsea_rgb.png`, `correlation_hubble_deep_field_gray.png` | `natural_image_correlation.csv` | READY, same representative-subset caveat as F9 |
| F11 | Natural-image performance scaling | `experiments/phase4c/plots/performance_scaling.png` | `benchmark_scaling.csv` | Same variance caveat as F8 |
| F12 | Diffusion dependency matrix (forward-only vs. combined) | `experiments/phase4d/plots/dependency_matrix.png` | `diffusion_analysis.json` | READY — this is the figure that visually substantiates the "99.58%, not 100%" finding; high manuscript value |
| F13 | Cipher architecture / encrypt-decrypt pipeline diagram | **Not yet generated** | Phase 4A's verified call graph and equations | **NEEDS REGENERATION** — no diagram file exists yet; the underlying facts (`PHASE_5_FINAL_EVIDENCE_REPORT.md` §architecture) are verified and ready to diagram |

## Tables

| # | Table | Candidate source | Status |
|---|---|---|---|
| T1 | ISC map parameters & Step 1.1 extraction-candidate comparison | `ISC_PBL/results/sequence_characterization/final_step1_1_closure_report.md` (the k13–k16/Arccos comparison table) | READY — already exists in near-final form in the source document |
| T2 | Cipher configuration summary (key/nonce sizes, streams, lanes, burn-in, profiles) | Verified facts in `verified_mathematical_specification.md` | **NEEDS REGENERATION** as a standalone table — facts are ready, table itself not yet assembled |
| T3 | Extraction-profile comparison (Step 1.1 sequence-level vs. Phase 3B multi-lane vs. Phase 4B/4C image-level) | `ISC_PBL/phase_3b_results.json`; `experiments/phase4b/results/experiment_G_*`; `experiments/phase4c/results/*` | **NEEDS ADDITIONAL EVIDENCE** — the Phase 3B pooled chi-square anomaly (flagged, unresolved per cross-phase audit) must be included as a row/footnote, not omitted |
| T4 | NIST test outcomes (Step 1.1 multi-sequence) | `ISC_PBL/results/sequence_characterization/final_step1_1_closure_report.md` §9 table | READY |
| T5 | Synthetic-image evaluation summary (recovery, entropy, histogram, correlation, NPCR/UACI, key sensitivity) | `numerical_verification.md` register + `experiments/phase4b/results/*` | READY |
| T6 | Natural-image evaluation summary | `numerical_verification.md` register + `experiments/phase4c/results/*` | READY |
| T7 | Performance/throughput scaling table | `experiments/phase4b/results/experiment_H_performance.csv`, `experiments/phase4c/results/benchmark_scaling.csv` | **NEEDS ADDITIONAL EVIDENCE** — must carry the measurement-variance caveat from Phase 4C explicitly in a footnote |
| T8 | Cryptanalysis findings summary (S-box DDT/LAT, dependency density, nonce-reuse attack results) | `experiments/phase4d/results/*`, `experiments/phase4e/results/*` | READY — assembled directly from `claim_evidence_matrix.md` |
| T9 | Security claims and limitations (the claim-evidence matrix itself) | `claim_evidence_matrix.md` | READY — already in final form for direct manuscript adaptation |

## Omitted candidates

- No candidate figure or table was found fabricated, decorative-only, or misleading in a way that would warrant OMIT. One borderline case (F8/F11 performance plots) is flagged NEEDS ADDITIONAL EVIDENCE rather than OMIT, since the underlying measurement is real — it just needs its variance caveat attached before being presented without qualification.
