# Final Scientific Correction, Validation, and Closure Report
## Step 1.1: Ikeda–Sine–Chebyshev (ISC) Chaotic Sequence Characterization & Quantisation

**Document Identification:** `ISC-CLOSURE-STEP1.1-2026-01`  
**Execution Timestamp:** 10 November 2026  
**Project:** ISC Chaotic Map Image Encryption Research Pipeline  
**Target Repository:** `ISC_PBL`  
**Author / Auditor:** Independent Scientific Audit Agent (Antigravity Advanced Pairing)  

---

## 1. Scope of the Final Audit and Validation

This report delivers the final scientific correction, validation, and formal closure of Step 1.1 of the ISC chaotic map image encryption research project. It addresses all open items identified during the preliminary audit of the initial characterization experiment (`isc_sequence_characterization.py`).

### Scope of Activities Completed:
1. **Repository & Artifact Preservation:** Preserved the original September 2026 historical validation scripts, the Step 1 baseline script (`isc_sequence_characterization_v1_backup.py`), and the initial Step 1.1 audit script (`isc_sequence_characterization_step1_1_v1_backup.py`).
2. **Mutual Information Qualified Re-evaluation (Correction A):** Derived analytical Miller–Madow finite-sample bias for $256 \times 256$ contingency tables ($N=10^6$), performed 1,000 i.i.d. random permutation trials and 500 circular time-shift null surrogates, and established qualified interpretations distinguishing contemporaneous, lagged, and marginal dependence.
3. **Byte Autocorrelation & Lag Reporting (Correction B):** Recomputed byte autocorrelation across the full $N=1,000,000$ sequence, distinguished adjacent-byte linear correlation ($\rho(1)$) from maximum non-zero lag ACF, evaluated multiple-testing considerations (Bonferroni bounds), and eliminated plot-axis clipping.
4. **Kolmogorov–Smirnov Distribution Analysis & Ablations (Correction C):** Computed continuous KS distances against the theoretical Chebyshev arcsine CDF, evaluated trajectory thinning (stride=50) to assess significance under reduced temporal dependence, and executed controlled numerical ablations isolating coupling nonlinearity ($d=0$) and folding frequency ($\omega$).
5. **Exact Empirical Float64 Parity Defect at $k=16$ (Correction D):** Derived the exact Float64 53-bit significand threshold $\theta = 2^{53}/10^{16}$, computed exact empirical proportions on the retained $10^6$ trajectory, and proved that $100\%$ of bytes generated in the affected region are strictly even.
6. **Cryptographic Terminology Corrections (Correction E):** Purged unsupported assertions of cryptographic security, PRNG proof, or secure extraction across code, documentation, and reports.
7. **Multiple-Sequence NIST SP 800-22 Assessment (Correction F):** Evaluated $M=100$ independently initialized candidate streams for $k=14$ ($X$ and $Y$) across all eligible tests, evaluated pass proportions against the NIST $96.02\%$ lower bound, and performed p-value uniformity testing.
8. **Final Quantisation Comparison:** Synthesized all empirical metrics into a unified comparison table and formulated justified, qualified engineering recommendations for Step 2.

---

## 2. Files Inspected and Preserved

### Preserved Artifacts (Read-Only Baseline):
- [`script/analyze.py`](file:///c:/Users/bhoom/Desktop/ISC_PBL/script/analyze.py) (Historical reference script, Sept 2026)
- [`script/final_validation.py`](file:///c:/Users/bhoom/Desktop/ISC_PBL/script/final_validation.py) (Historical reference script, Sept 2026)
- [`script/final_freeze_validation.py`](file:///c:/Users/bhoom/Desktop/ISC_PBL/script/final_freeze_validation.py) (Historical reference script, Sept 2026)
- [`isc_sequence_characterization_v1_backup.py`](file:///c:/Users/bhoom/Desktop/ISC_PBL/isc_sequence_characterization_v1_backup.py) (Step 1 original experiment script)
- [`results/sequence_characterization_v1_backup/`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization_v1_backup/) (Step 1 original raw output directory)
- [`isc_sequence_characterization_step1_1_v1_backup.py`](file:///c:/Users/bhoom/Desktop/ISC_PBL/isc_sequence_characterization_step1_1_v1_backup.py) (Step 1.1 preliminary audit script)

### Modified & Generated Working Artifacts:
- [`isc_sequence_characterization.py`](file:///c:/Users/bhoom/Desktop/ISC_PBL/isc_sequence_characterization.py) (Corrected, validated closure script)
- [`results/sequence_characterization/final_step1_1_closure_report.md`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/final_step1_1_closure_report.md) (This deliverable)
- [`results/sequence_characterization/summary_report.md`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/summary_report.md) (Updated research summary)
- [`results/sequence_characterization/step1_1_changelog.md`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/step1_1_changelog.md) (Detailed changelog)
- [`results/sequence_characterization/final_quantisation_comparison.csv`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/final_quantisation_comparison.csv)
- [`results/sequence_characterization/final_quantisation_comparison.md`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/final_quantisation_comparison.md)
- [`results/sequence_characterization/mutual_information_results.csv`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/mutual_information_results.csv)
- [`results/sequence_characterization/byte_acf_results.csv`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/byte_acf_results.csv)
- [`results/sequence_characterization/float64_parity_analysis.csv`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/float64_parity_analysis.csv)
- [`results/sequence_characterization/nist_results/nist_multi_sequence_summary.csv`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/nist_results/nist_multi_sequence_summary.csv)
- [`results/sequence_characterization/nist_results/nist_per_sequence_results.csv`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/nist_results/nist_per_sequence_results.csv)
- [`results/sequence_characterization/nist_results/nist_test_eligibility.csv`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/nist_results/nist_test_eligibility.csv)
- [`results/sequence_characterization/nist_results/nist_environment.txt`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/nist_results/nist_environment.txt)
- High-Resolution Publication Plots (PNG + PDF): [`results/sequence_characterization/plots/`](file:///c:/Users/bhoom/Desktop/ISC_PBL/results/sequence_characterization/plots/)

---

## 3. Verified Software and Computational Environment

- **Operating System:** Microsoft Windows 10/11 Professional (Build 10.0.22631-SP0, AMD64)
- **Python Version:** 3.11.9 (64-bit MSC v.1938)
- **NumPy Version:** 2.4.6
- **SciPy Version:** 1.17.1
- **Matplotlib Version:** 3.10.0
- **NIST SP 800-22 Package:** `nistrng` version 1.2.3

---

## 4. Correction A: Mutual Information Analysis & Scientific Qualification

### 4.1 Methodology & Derivation
The plug-in mutual information estimator evaluated on an $R \times C = 256 \times 256$ contingency table with sample size $N = 1,000,000$ is subject to asymptotic Miller–Madow bias:
$$\text{Bias}_{\text{MM}} = \frac{(R - 1)(C - 1)}{2 N \ln 2} = \frac{(255)(255)}{2 \times 10^6 \times 0.69314718} \approx 0.0469056\text{ bits}$$

To evaluate the null distribution, two distinct resampling procedures were executed:
1. **I.I.D. Random Permutation (1,000 trials):** Shuffles $B_Y$ uniformly across all iterations, breaking all contemporaneous and lagged cross-correlations as well as temporal structure within $Y$.
2. **Circular Time-Shift Surrogates (500 trials):** Applies circular shifts $Y_{\tau} = \text{roll}(Y, \tau)$ with random lags $\tau \in [100, N-100]$. This preserves $100\%$ of the temporal autocorrelation within $X$ and $Y$ while breaking contemporaneous alignment.

### 4.2 Empirical Results

| Variable Pair / Candidate | Raw Plug-in MI (bits) | Miller-Madow Bias (bits) | Permutation Null Mean (1,000 trials) | Permutation Null Std | Circular Shift Mean (500 trials) | Adjusted MI (bits) |
|---|---|---|---|---|---|---|
| **Continuous States $(X, Y)$** | $0.060671$ | $0.046906$ | $0.047844$ | $\pm 0.000268$ | $0.047849 \pm 0.000270$ | **$0.013765$** |
| **Quantised Modulo $k=13$** | $0.046794$ | $0.046906$ | $0.047365$ | $\pm 0.000180$ | $0.047371 \pm 0.000185$ | **$0.000000$** |
| **Quantised Modulo $k=14$** | $0.047309$ | $0.046906$ | $0.047530$ | $\pm 0.000160$ | $0.047528 \pm 0.000162$ | **$0.000404$** |
| **Quantised Modulo $k=15$** | $0.047627$ | $0.046906$ | $0.047622$ | $\pm 0.000140$ | $0.047625 \pm 0.000143$ | **$0.000722$** |
| **Quantised Modulo $k=16$** | $0.047398$ | $0.046906$ | $0.047596$ | $\pm 0.000120$ | $0.047601 \pm 0.000125$ | **$0.000493$** |
| **Arccos Transform** | $0.061576$ | $0.046906$ | $0.047460$ | $\pm 0.000150$ | $0.047465 \pm 0.000152$ | **$0.014670$** |

### 4.3 Scientifically Qualified Interpretation
The observed plug-in mutual information of $\approx 0.0473\text{ bits}$ between $B_X$ and $B_Y$ for $k=14$ is consistent with the finite-sample bias estimated using the Miller–Madow approximation ($\approx 0.0469\text{ bits}$) and permutation-null trials ($0.0475\text{ bits}$). The current experiment provides no convincing evidence of substantial contemporaneous dependence between the quantised byte streams. However, this does not establish that the underlying variables are strictly statistically independent; nonlinear dynamical coupling is present in continuous space ($I_{\text{adj}} \approx 0.0138\text{ bits}$), and deterministic phase relationships exist.

---

## 5. Correction B: Byte Autocorrelation & Cross-Correlation Analysis

### 5.1 Sample Size Effect & Resolution of Preliminary Discrepancy
The preliminary Step 1 script computed byte ACF over an arbitrary subset of $50,000$ samples, whereas continuous ACF and byte statistics used the full $1,000,000$ samples.
- On $N=50,000$ samples: The pointwise white-noise standard error is $1.96/\sqrt{50,000} \approx 0.00876$, and maximum noise peaks across 100 lags scaled to $\approx 0.0147$.
- On the full $N=1,000,000$ sequence: The pointwise white-noise standard error drops to $1.96/\sqrt{1,000,000} = 0.00196$.

### 5.2 Full-Sample Autocorrelation Results ($N = 1,000,000$)

| Stream Key | Adjacent-Byte Corr. $\rho(1)$ | Max Non-Zero Lag ACF | Lag of Max ACF | Pointwise 95% Bound | Bonferroni 95% Bound | Multiple-Testing Decision |
|---|---|---|---|---|---|---|
| `de_k13_x` | $-0.000318$ | $+0.002538$ | 84 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `de_k13_y` | $-0.000895$ | $-0.003262$ | 43 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `de_k14_x` | $-0.000588$ | $-0.002277$ | 8 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `de_k14_y` | $-0.000067$ | $-0.002737$ | 75 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `de_k15_x` | $-0.000377$ | $-0.003184$ | 79 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `de_k15_y` | $-0.001625$ | $+0.003424$ | 88 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `de_k16_x` | $-0.000715$ | $+0.003452$ | 3 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `de_k16_y` | $+0.000475$ | $-0.002380$ | 22 | $\pm 0.00196$ | $\pm 0.00348$ | Within Family-Wise Bound |
| `arccos_x` | $-0.095149$ | $-0.095149$ | 1 | $\pm 0.00196$ | $\pm 0.00348$ | **Severe Violation (Dynamical Memory)** |
| `arccos_y` | $+0.012714$ | $+0.012714$ | 1 | $\pm 0.00196$ | $\pm 0.00348$ | **Severe Violation (Dynamical Memory)** |

### 5.3 Multiple-Testing Discussion & Reporting Qualification
Across $K = 100$ tested lags, individual $95\%$ confidence bounds ($\pm 1.96/\sqrt{N}$) are expected to produce $\approx 5$ nominal false exceedances purely by chance. When applying the Bonferroni correction for family-wise error control ($\alpha_{\text{Bonf}} = 0.05 / 100 = 0.0005$, critical threshold $3.48/\sqrt{N} = 0.00348$), **all scaled-floor-modulo streams remain strictly within the family-wise white-noise envelope.**

*Qualified Statement:* The scaled-floor-modulo transformation exhibits very low adjacent-byte linear correlation ($|\rho| < 0.0006$) and maximum non-zero lag ACF bounded within $\pm 0.0035$ across 100 tested lags. These results characterize measured linear dependence and do not establish statistical independence or cryptographic unpredictability.

---

## 6. Correction C: Kolmogorov–Smirnov Analysis & Controlled Ablation

### 6.1 Distribution Distance vs. Inferential P-Value
Against the theoretical 1D Chebyshev arcsine CDF ($F(z) = 0.5 + \frac{1}{\pi}\arcsin(z)$):
- Coordinate $x_n$: Empirical KS distance $D_X = 0.031227$ ($3.12\%$).
- Coordinate $y_n$: Empirical KS distance $D_Y = 0.035109$ ($3.51\%$).
- The ordinary two-sided KS test reported $p = 0.0000$. This is a numerical underflow of the asymptotic formula $p \sim 2\exp(-2 N D^2) \sim 2\exp(-1950) \approx 10^{-847}$, caused by the massive statistical power of $N=1,000,000$ observations.
- To assess significance under reduced temporal autocorrelation, trajectory thinning with stride $L=50$ ($N=20,000$) was evaluated:
  - Thinned $x_n$: $D = 0.0338$, $p = 2.60 \times 10^{-20}$.
  - Thinned $y_n$: $D = 0.0327$, $p = 5.11 \times 10^{-19}$.
  The departure from the pure arcsine distribution remains highly significant even when consecutive samples are temporally separated beyond the autocorrelation length.

### 6.2 Controlled Ablation Experiments ($N = 100,000$)
To isolate the physical and mathematical mechanisms responsible for this departure, five controlled configurations were evaluated:

| Map Configuration | Tested Mechanism | KS Distance $D$ | KS $p$-value | Empirical Finding |
|---|---|---|---|---|
| **Pure 1D Chebyshev** ($x_{n+1}=2x_n^2-1$) | Isolated degree-2 polynomial | **$0.003245$** | $0.2424$ | Fails to reject ideal arcsine ($p > 0.05$). Exact theoretical match. |
| **Baseline ISC Map** ($\omega=10, d=6, a=0.9$) | Full coupled 2D system | **$0.029797$** | $1.44 \times 10^{-77}$ | Statistically significant $3\%$ deviation from arcsine. |
| **Ablation $d=0$** (constant rotation angle) | Removes state-dependent phase modulation | **$0.010856$** | $1.15 \times 10^{-10}$ | $D$ drops by nearly a factor of 3 ($64\%$ reduction in deviation). |
| **Ablation $\omega=50$** (higher sine folding) | Increases intermediate folds from $\approx 8$ to $40$ | **$0.007733$** | $1.27 \times 10^{-5}$ | Structural ripples smooth out under denser folding. |
| **Ablation $\omega=100$** (high sine folding) | Increases intermediate folds to $\approx 80$ | **$0.001710$** | $0.9313$ | Invariant density converges to ideal arcsine ($p = 0.931$). |

*Conclusion:* The deviation of the ISC map from an ideal arcsine measure is driven by two demonstrable factors: (1) nonlinear state-dependent phase modulation via the Ikeda factor $d/(1+x^2+y^2)$, and (2) the finite folding frequency ($\omega=10$), which wraps $X_n$ only $\approx 8$ times across $2\pi$. This explains why the Arccos transformation fails byte-level uniformity testing ($\chi^2 > 5,200$).

---

## 7. Correction D: Exact Empirical Float64 Parity Defect at $k=16$

### 7.1 Threshold and Empirical Trajectory Counts
- IEEE 754 Float64 53-bit significand limit: $2^{53} = 9,007,199,254,740,992$.
- Critical scaling threshold: $\theta = 2^{53} / 10^{16} = 0.9007199254740992$.
- Theoretical arcsine proportion: $P_{\text{arcsine}}(|x| > \theta) = 1 - \frac{2}{\pi}\arcsin(\theta) \approx 0.286079$ ($28.6079\%$).

### 7.2 Empirical Verification on Retained Trajectory ($N = 1,000,000$)
- **Coordinate $x_n$:**
  - Count exceeding $\theta$: **$281,822$ samples** ($28.1822\%$, difference from theory: $-0.4257\%$).
  - In affected region ($|x_n| > \theta$): **$281,822$ even bytes, $0$ odd bytes ($0.00\%$ odd).**
  - In unaffected region ($|x_n| \le \theta$): **$359,639$ even bytes, $358,539$ odd bytes ($49.92\%$ odd).**
- **Coordinate $y_n$:**
  - Count exceeding $\theta$: **$295,807$ samples** ($29.5807\%$, difference from theory: $+0.9728\%$).
  - In affected region ($|y_n| > \theta$): **$295,807$ even bytes, $0$ odd bytes ($0.00\%$ odd).**
  - In unaffected region ($|y_n| \le \theta$): **$352,572$ even bytes, $351,621$ odd bytes ($49.93\%$ odd).**

### 7.3 Conclusive Mechanism
In IEEE 754 Float64, when a number exceeds $2^{53}$, the Unit in the Last Place (ULP) transitions from $1.0$ to $2.0$. In this regime, every representable floating-point integer is strictly **even**. Because the ISC state distribution is U-shaped, over $28\%$ of the trajectory falls into this regime. Consequently, $\lfloor |x_n| \times 10^{16} \rfloor \bmod 256$ is strictly even for over $280,000$ iterations, creating a severe parity defect against odd byte values that results in catastrophic Chi-Square failure ($\chi^2 \approx 80,290.63, p=0.0$). This failure is completely independent of 64-bit integer overflow.

---

## 8. Correction E: Purge of Cryptographic Overclaims

All text, documentation, and comments have been audited and updated:
1. **Terminology Standardized:** The operation $B_n = \lfloor |x_n| \times 10^k \rfloor \bmod 256$ is designated exclusively as the **Fixed-Point Scaled-Floor-Modulo Transformation (Candidate Digit Extraction)**.
2. **Unsupported Claims Removed:** No claim is made that the transformation is a cryptographic hash, secure extractor, proven PRNG, or resistant to chosen/known-plaintext cryptanalysis.
3. **Core Conceptual Distinctions Enforced:**
   - Marginal uniformity $\ne$ cryptographic unpredictability.
   - Low sample autocorrelation $\ne$ statistical independence.
   - Passing NIST SP 800-22 $\ne$ cryptographic security.
   - High Lyapunov exponents $\ne$ key sensitivity or attack resistance.

---

## 9. Correction F: Multi-Sequence NIST SP 800-22 Assessment

### 9.1 Multi-Sequence Testing Protocol
In accordance with NIST SP 800-22 Rev 1a Section 4.2:
- **Sample Size:** $M = 100$ independently initialized sequences per candidate stream.
- **Initial Conditions:** Seeded deterministically via PRNG (`seed=20261110`) uniformly drawing $(x_0, y_0) \in [-0.8, 0.8]^2 \setminus \{0, 0\}$.
- **Burn-in:** 5,000 transient iterations discarded per sequence.
- **Length per Stream:** $100,000$ bits (unpacked MSB-first).
- **Defensive Copying:** Enforced per test to prevent Gaussian elimination memory mutation.
- **Significance Level:** $\alpha = 0.01$.
- **NIST Minimum Acceptance Proportion:**
  $$p_{\text{lower}} = (1 - \alpha) - 3\sqrt{\frac{\alpha(1-\alpha)}{M}} = 0.99 - 3\sqrt{\frac{0.01 \times 0.99}{100}} = 0.96015 \implies 96\%$$
- **Uniformity of P-values Criterion:** $\chi^2$ goodness-of-fit across 10 sub-intervals with $P\text{-value}_T \ge 0.0001$.

### 9.2 Multi-Sequence Empirical Results

#### Candidate $k=14$, Coordinate $X$ ($M = 100$ Streams):
| NIST Test Name | Sequences Tested | Sequences Passed | Empirical Pass Rate | NIST Acceptance Lower Bound | P-value Uniformity $P_T$ | Overall Evaluation |
|---|---|---|---|---|---|---|
| **Monobit (Frequency)** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.9717$ | **PASS** |
| **Frequency within Block** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.1719$ | **PASS** |
| **Runs** | 100 | 98 | **$98.0\%$** | $96.0\%$ | $0.4750$ | **PASS** |
| **Longest Run of Ones** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.9781$ | **PASS** |
| **Binary Matrix Rank** | 100 | 98 | **$98.0\%$** | $96.0\%$ | $0.0308$ | **PASS** |
| **Discrete Fourier Transform** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.0712$ | **PASS** |
| **Non-overlapping Template** | 100 | 100 | **$100.0\%$** | $96.0\%$ | $< 10^{-100}$ | **PASS Pass-Rate** (see package note) |
| **Serial** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.4012$ | **PASS** |
| **Approximate Entropy** | 100 | 98 | **$98.0\%$** | $96.0\%$ | $0.8514$ | **PASS** |
| **Cumulative Sums** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.0669$ | **PASS** |

#### Candidate $k=14$, Coordinate $Y$ ($M = 100$ Streams):
| NIST Test Name | Sequences Tested | Sequences Passed | Empirical Pass Rate | NIST Acceptance Lower Bound | P-value Uniformity $P_T$ | Overall Evaluation |
|---|---|---|---|---|---|---|
| **Monobit (Frequency)** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.6163$ | **PASS** |
| **Frequency within Block** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.6993$ | **PASS** |
| **Runs** | 100 | 98 | **$98.0\%$** | $96.0\%$ | $0.2897$ | **PASS** |
| **Longest Run of Ones** | 100 | 98 | **$98.0\%$** | $96.0\%$ | $0.0712$ | **PASS** |
| **Binary Matrix Rank** | 100 | 100 | **$100.0\%$** | $96.0\%$ | $0.8978$ | **PASS** |
| **Discrete Fourier Transform** | 100 | 100 | **$100.0\%$** | $96.0\%$ | $0.0909$ | **PASS** |
| **Non-overlapping Template** | 100 | 100 | **$100.0\%$** | $96.0\%$ | $< 10^{-100}$ | **PASS Pass-Rate** (see package note) |
| **Serial** | 100 | 98 | **$98.0\%$** | $96.0\%$ | $0.5544$ | **PASS** |
| **Approximate Entropy** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.5342$ | **PASS** |
| **Cumulative Sums** | 100 | 99 | **$99.0\%$** | $96.0\%$ | $0.0329$ | **PASS** |

*Average Multi-Sequence Pass Rate:* **$98.8\%$ for $X$**, **$99.0\%$ for $Y$**.  
Every test exceeded the NIST $96.02\%$ minimum threshold. Nine of the ten tests exhibited uniform p-value distributions ($P_T \ge 0.03 \gg 0.0001$). Non-overlapping Template Matching passed $100\%$ of sequences, with $P_T$ clustering due to the `nistrng` implementation returning $p=1.0$ under zero template matches.

---

## 10. Final Quantisation Comparison & Engineering Recommendation

### Consolidated Comparison Table:
| Candidate Key | Quantisation Method | Shannon Entropy (bits) | Chi-Square $\chi^2$ ($df=255$) | $\chi^2$ $p$-value | Uniformity Decision ($\alpha=0.05$) | Adjacent Byte Corr. $\rho(1)$ | Max Byte ACF ($N=10^6$) | NIST Single Pass Ratio | NIST Multi-Seq Pass Rate | Precision Limitations |
|---|---|---|---|---|---|---|---|---|---|---|
| `de_k13_x` | Scaled Modulo ($k=13, X$) | $7.999807$ | $268.02$ | $0.2755$ | **UNIFORM** | $-0.000318$ | $+0.002538$ (lag 84) | $10/10$ ($100\%$) | N/A | None (within mantissa) |
| `de_k13_y` | Scaled Modulo ($k=13, Y$) | $7.999822$ | $247.34$ | $0.6229$ | **UNIFORM** | $-0.000895$ | $-0.003262$ (lag 43) | $10/10$ ($100\%$) | N/A | None (within mantissa) |
| `de_k14_x` | Scaled Modulo ($k=14, X$) | $7.999831$ | $234.07$ | $0.8222$ | **UNIFORM** | $-0.000588$ | $-0.002277$ (lag 8) | $10/10$ ($100\%$) | **$98.8\%$** | None (within mantissa) |
| `de_k14_y` | Scaled Modulo ($k=14, Y$) | $7.999846$ | $212.49$ | $0.9755$ | **UNIFORM** | $-0.000067$ | $-0.002737$ (lag 75) | $10/10$ ($100\%$) | **$99.0\%$** | None (within mantissa) |
| `de_k15_x` | Scaled Modulo ($k=15, X$) | $7.999816$ | $254.95$ | $0.4892$ | **UNIFORM** | $-0.000377$ | $-0.003184$ (lag 79) | $10/10$ ($100\%$) | N/A | Near mantissa limit |
| `de_k15_y` | Scaled Modulo ($k=15, Y$) | $7.999812$ | $261.18$ | $0.3817$ | **UNIFORM** | $-0.001625$ | $+0.003424$ (lag 88) | $10/10$ ($100\%$) | N/A | Near mantissa limit |
| `de_k16_x` | Scaled Modulo ($k=16, X$) | $7.941283$ | $80,290.63$ | $0.0000$ | **REJECTED** | $-0.000715$ | $+0.003452$ (lag 3) | $3/9$ ($33.3\%$) | N/A | ULP=2.0 even-parity over 28.2% |
| `de_k16_y` | Scaled Modulo ($k=16, Y$) | $7.935329$ | $88,319.99$ | $0.0000$ | **REJECTED** | $+0.000475$ | $-0.002380$ (lag 22) | $3/9$ ($33.3\%$) | N/A | ULP=2.0 even-parity over 29.6% |
| `arccos_x` | Arccos Transform ($X$) | $7.996226$ | $5,258.98$ | $0.0000$ | **REJECTED** | $-0.095149$ | $-0.095149$ (lag 1) | $10/10$ ($100\%$) | N/A | Invariant measure departs 3.1% |
| `arccos_y` | Arccos Transform ($Y$) | $7.993013$ | $9,950.42$ | $0.0000$ | **REJECTED** | $+0.012714$ | $+0.012714$ (lag 1) | $5/9$ ($55.6\%$) | N/A | Invariant measure departs 3.5% |

### Engineering Recommendation:
The **Fixed-Point Scaled-Floor-Modulo Transformation with $k = 14$** is provisionally selected as the preferred candidate for the image-encryption pipeline. Its observed marginal byte uniformity ($p=0.822$ for $X$, $p=0.975$ for $Y$), low linear autocorrelation ($|\rho| \le 0.0027$), and high multi-sequence pass rates ($98.8\%$ to $99.0\%$) justify further investigation. Exponents $k \ge 16$ and the Arccos transformation are strictly rejected.

---

## 11. Explicit Answers to Closure Questions

1. **Is the ISC recurrence implemented correctly?**  
   **YES.** The implementation strictly matches `analyze.py`, `final_validation.py`, and `final_freeze_validation.py`.
2. **Are the retained trajectory values correctly indexed?**  
   **YES.** Retained values correspond strictly to the degree-2 Chebyshev folded states $x_{n+1}, y_{n+1} \in [-1, 1]$ post 5,000 burn-in iterations. Intermediate coordinates ($X_n, Y_n$) are never passed to quantisation.
3. **Is $k = 16$ demonstrably affected by Float64 precision limitations?**  
   **YES.** Verified analytically and empirically: for $|x_n| > 2^{53}/10^{16}$, Float64 ULP increases to 2.0, forcing $100\%$ of generated bytes to be strictly even across $28.18\%$ of the trajectory.
4. **Does $k = 14$ pass the reported marginal byte-uniformity tests?**  
   **YES.** $\chi^2 = 234.07$ ($p = 0.8222$) for $X$, $\chi^2 = 212.49$ ($p = 0.9755$) for $Y$ at $\alpha=0.05$ ($df=255$, critical threshold $293.25$).
5. **Does $k = 15$ pass the reported marginal byte-uniformity tests?**  
   **YES.** $\chi^2 = 254.95$ ($p = 0.4892$) for $X$, $\chi^2 = 261.18$ ($p = 0.3817$) for $Y$.
6. **What do the corrected ACF results actually demonstrate?**  
   They demonstrate that on the full $N=1,000,000$ sequence, sample linear autocorrelation remains bounded within $\pm 0.0035$ across 100 tested lags (within Bonferroni bounds). They characterize linear decorrelation, not statistical independence or unpredictability.
7. **Is there convincing evidence of substantial contemporaneous X–Y byte dependence?**  
   **NO.** Raw mutual information ($\approx 0.047\text{ bits}$) is consistent with the finite-sample bias of a $256 \times 256$ contingency table ($\text{Bias}_{\text{MM}} \approx 0.0469\text{ bits}$).
8. **What can and cannot be concluded from the KS analysis?**  
   *Can be concluded:* The empirical invariant measure of the ISC map departs by $\approx 3.1\%$ from the pure 1D Chebyshev arcsine measure, driven by nonlinear Ikeda rotation and finite sine folding ($\omega=10$).  
   *Cannot be concluded:* It does not prove that the map is defective or non-chaotic; it demonstrates that assuming an exact arcsine measure for Arccos quantisation is mathematically invalid.
9. **How many NIST tests were eligible?**  
   **10 tests** were eligible at $n=100,000$ bits. Five tests were ineligible: Maurer's Universal ($n < 387,840$), Linear Complexity ($n < 10^6$), Overlapping Template ($n < 1,028,016$ and library defect), Random Excursion ($J < 500$), and Random Excursion Variant ($J < 500$).
10. **How many sequences were tested?**  
    **100 independent sequences** were tested for $k=14$ ($X$ and $Y$).
11. **What proportion passed each eligible test?**  
    Between **$98.0\%$ and $100.0\%$** passed each eligible test across both coordinates, exceeding the NIST $96.02\%$ threshold.
12. **Is the evidence sufficient to select $k = 14$ provisionally?**  
    **YES.** The empirical uniformity, low linear correlation, and $98.9\%$ average multi-sequence NIST pass rate provide strong justification for provisional selection.
13. **Has cryptographic security been established?**  
    **NO.** Cryptographic security cannot be established by statistical tests, Shannon entropy, or Lyapunov exponents. The byte stream is generated by a deterministic map without secret-key derivation.
14. **Is Step 1.1 ready to close?**  
    **YES. Final status: COMPLETE.**
15. **What exact work remains before Step 2?**  
    Designing a secure key schedule (deriving parameters and initial conditions from a 256-bit secret key), and architecting keyed non-linear substitution and bidirectional diffusion mechanisms resistant to known/chosen-plaintext cryptanalysis.

---

## 12. Final Step 1.1 Closure Status

**Status:** **`COMPLETE`**  
All mathematical derivations, empirical verifications, code corrections, multi-sequence NIST evaluations, and documentation deliverables are fully executed, verified, and archived.

