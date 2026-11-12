# Step 1.1 Implementation & Audit Changelog
## ISC Sequence Characterization and Quantisation Analysis Suite

**Project:** ISC Chaotic Map Image Encryption Research Pipeline  
**Target Repository:** `ISC_PBL`  
**Date:** 10 November 2026  

---

### [2026-11-10 18:35] Preservation & Backup Initialization
- **Action:** Created complete read-only backup of initial Step 1 code and outputs prior to audit modifications.
- **Files Preserved:**
  - `isc_sequence_characterization.py` -> `isc_sequence_characterization_v1_backup.py`
  - `results/sequence_characterization/` -> `results/sequence_characterization_v1_backup/`
  - Unmodified September 2026 scripts: `script/analyze.py`, `script/final_validation.py`, `script/final_freeze_validation.py`.

---

### [2026-11-10 18:42] Implementation of Initial Audit Fixes (Step 1.1 Preliminary)
- **Defensive Memory Copying for NIST Battery:**
  - *Location:* `run_nist_battery` in `isc_sequence_characterization.py`.
  - *Change:* Passed `bit_array.copy()` defensively to every test object.
  - *Reason:* Resolved critical bug in `nistrng.BinaryMatrixRankTest` which mutates the shared array in-place via Gaussian elimination, corrupting the first 99,328 bits and causing false $p=0.0$ failures in DFT, Serial, ApEn, and CumSums.
- **Random Excursion Eligibility Pre-Check:**
  - *Change:* Computed zero-crossings $J = \sum \mathbb{I}(S_k = 0)$. If $J < 500$, classified Random Excursion and Variant as `INELIGIBLE` per NIST SP 800-22 Section 2.14.
  - *Reason:* `nistrng` hardcoded `is_eligible() -> True`, causing spurious failures on $n=100,000$ bits where $J \approx 137$.
- **Plot Axis Clipping Correction:**
  - *Change:* Modified y-limits for continuous ACF and CCF plots from `[-0.05, 0.05]` to `[-0.18, 0.18]`.
  - *Reason:* Prevented clipping of $\rho_X(1) = -0.103447$ and $\rho_{XY}(-1) = +0.135246$.
- **Mathtext Parsing Fix:**
  - *Change:* Replaced `\ge` and `\le` with `\geq` and `\leq` in matplotlib plot title strings.
  - *Reason:* Resolved `ValueError` parse exception in matplotlib mathtext parser.

---

### [2026-11-10 19:49] Preservation of Preliminary Audit Version
- **Action:** Created versioned backup of the preliminary Step 1.1 script prior to final validation and closure enhancements.
- **File Preserved:** `isc_sequence_characterization.py` -> `isc_sequence_characterization_step1_1_v1_backup.py`.

---

### [2026-11-10 20:01] Final Closure & Scientific Validation Implementation
- **Fast Vectorized Pattern Counting for NIST Library:**
  - *Location:* `apply_nistrng_optimizations()` in `isc_sequence_characterization.py`.
  - *Change:* Monkeypatched `SerialTest._psi_sq_mv1` and `ApproximateEntropyTest._phi_m` to use `np.lib.stride_tricks.sliding_window_view` and `np.bincount` instead of pure-Python nested loops.
  - *Reason:* Achieved a 7,000x execution speedup while preserving the exact NIST SP 800-22 mathematical algorithms, enabling full multi-sequence testing across 100 streams in ~3 minutes.
- **Mutual Information 1,000 Permutation & Circular Shift Trials (Correction A):**
  - *Location:* `analyze_joint_distribution_2d` in `isc_sequence_characterization.py`.
  - *Change:* Expanded permutation trials from 5 to 1,000. Implemented 500 circular time-shift null surrogates to preserve marginal temporal autocorrelation. Exported detailed results to `mutual_information_results.csv`.
  - *Reason:* Formally established that raw plug-in MI ($\approx 0.047\text{ bits}$) is consistent with the finite-sample Miller–Madow bias ($\approx 0.0469\text{ bits}$).
- **Full-Sample Byte Autocorrelation ($N=1,000,000$) (Correction B):**
  - *Location:* `compute_autocorrelation` and Step 7 in `isc_sequence_characterization.py`.
  - *Change:* Evaluated byte ACF over the full $N=1,000,000$ sequence rather than the initial $N=50,000$ shortcut. Documented both sample sizes in `byte_acf_results.csv` and added Bonferroni family-wise bounds ($3.48/\sqrt{N}$).
  - *Reason:* Clarified that maximum non-zero lag ACF was $0.0147$ on $50,000$ samples due to sample noise, and is $\le 0.0028$ on the full $1,000,000$ sequence.
- **Empirical Float64 Parity Defect at $k=16$ (Correction D):**
  - *Location:* `analyze_float64_parity_defect()` in `isc_sequence_characterization.py`.
  - *Change:* Added exact threshold calculation ($\theta = 2^{53}/10^{16} = 0.9007199254740992$), evaluated empirical trajectory counts exceeding $\theta$ ($28.18\%$ for $X$, $29.58\%$ for $Y$), and verified that $100\%$ of bytes generated in this domain are strictly even.
  - *Reason:* Proven exact mathematical mechanism causing $\chi^2 \approx 80,290$ failure, independent of 64-bit integer overflow.
- **Controlled Coupling & Folding Ablation Experiments (Correction C):**
  - *Location:* `run_coupling_ablation_experiment()` in `isc_sequence_characterization.py`.
  - *Change:* Evaluated pure 1D Chebyshev ($D = 0.0032$), baseline ISC ($D = 0.0298$), $d=0$ constant rotation ($D = 0.0108$), and higher folding $\omega=50$ ($D = 0.0077$) and $\omega=100$ ($D = 0.0017$).
  - *Reason:* Provided empirical evidence isolating the coupling and folding mechanisms responsible for the departure from the ideal arcsine measure.
- **Multi-Sequence NIST SP 800-22 Assessment across 100 Streams (Correction F):**
  - *Location:* `run_nist_multi_sequence_assessment()` in `isc_sequence_characterization.py`.
  - *Change:* Evaluated $M=100$ independently initialized streams ($100,000$ bits each) for candidate $k=14$ ($X$ and $Y$). Evaluated pass rates against the NIST $96.02\%$ threshold and computed p-value uniformity $\chi^2$ and $P_T$.
  - *Reason:* Met NIST SP 800-22 Section 4.2 multi-sequence evaluation standards.
- **Cryptographic Terminology Corrections (Correction E):**
  - *Change:* Renamed method to "Fixed-Point Scaled-Floor-Modulo Transformation (Candidate Digit Extraction)" and purged unsupported assertions of cryptographic security.

---

### [2026-11-10 20:18] Deliverable Generation & Closure Verification
- **Output Artifacts Produced & Validated:**
  - `results/sequence_characterization/final_step1_1_closure_report.md`
  - `results/sequence_characterization/summary_report.md`
  - `results/sequence_characterization/final_quantisation_comparison.csv`
  - `results/sequence_characterization/final_quantisation_comparison.md`
  - `results/sequence_characterization/mutual_information_results.csv`
  - `results/sequence_characterization/byte_acf_results.csv`
  - `results/sequence_characterization/float64_parity_analysis.csv`
  - `results/sequence_characterization/nist_results/nist_multi_sequence_summary.csv`
  - `results/sequence_characterization/nist_results/nist_per_sequence_results.csv`
  - `results/sequence_characterization/nist_results/nist_test_eligibility.csv`
  - `results/sequence_characterization/nist_results/nist_environment.txt`
  - `results/sequence_characterization/plots/` (12 PNG and 12 vector PDF publication figures).

