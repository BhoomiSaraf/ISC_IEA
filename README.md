# ISC-IEA — Iterative Sine–Chebyshev–Ikeda Image Encryption Algorithm

A comprehensive research codebase and implementation of the Enhanced Iterative Sine–Chebyshev–Ikeda (ISC-IEA) chaotic cryptosystem for high-security digital image encryption. The construction integrates hyperchaotic map dynamics, cryptographic key derivation, dynamic algebraic substitution, group-heterogeneous ARX-S mixing, and spatial transposition into a misuse-resistant authenticated image encryption pipeline.

---

## Architecture & Cryptographic Primitives

The enhanced ISC-IEA construction is engineered to provide robust security against statistical, differential, chosen-plaintext, and nonce-reuse attacks:

- **RFC 8452 Synthetic IV (SIV) Nonce Derivation**: Context-separated HKDF-SHA-256 expansion ensuring nonce-misuse resistance and deterministic payload authentication.
- **2D-ISC Hyperchaotic Map**: 2D discrete chaotic system ($a=0.9, c=0.4, d=6.0, \omega=10.0$) with strictly positive dual Lyapunov exponents ($\lambda_1 \approx +2.75, \lambda_2 \approx +1.64$) verified by independent analytic and finite-difference Jacobians.
- **Uniform Byte Harvesting (`mantissa_mid_xor`)**: Discretization technique eliminating statistical bias and achieving uniform byte distributions ($\chi^2 \approx 187.5$).
- **Dynamic Galois Field $\text{GF}(2^8)$ Inversion S-boxes**: Key-dependent affine-inversion S-box generation achieving optimal differential probability ($\text{DP}_{\max} = 4/256$) and high non-linearity.
- **2-Round Group-Heterogeneous ARX-S Mixing**: Addition-Rotation-XOR diffusion core coupled with 2D inter-round matrix spatial transposition for full avalanche effect across adjacent and distant pixels.
- **Adaptive Fisher–Yates Permutations**: Wide-word pseudorandom position shuffling destroying spatial pixel correlation.
- **Authenticated Container Format**: Reversible container format ensuring exact bit-for-bit invertibility ($\mathcal{D}(\mathcal{E}(P)) = P$) and payload integrity.

---

## Repository Layout

| Path | Contents |
|---|---|
| `experiments/paper_workflow_study/` | Enhanced ISC-IEA cipher pipeline (`cipher_pipeline.py`), standard USC-SIPI evaluations (`run_standard_evaluations.py`), benchmark suites, dataset, and publication figures |
| `experiments/diffusion_study/` | Candidate diffusion architecture benchmarks (multi-stream, Candidate A/B/C vs original baseline) |
| `experiments/step4_candidates/` | Downstream component studies (S-box selection, multi-round diffusion, byte extraction validation) |
| `experiments/step5_controlled/` | Controlled baseline comparisons and nonce-reuse evaluations |
| `experiments/phase5_followup/` | Independent audits, Lyapunov recomputation, chi-square anomaly localization, SMT nonce-reuse solver |
| `isc_cipher/` | Core cipher implementation: HKDF-SHA-256, 4 ISC streams × 64 lanes, ISCI container |
| `isc_cipher_kat/` | Known-answer-test (KAT) generation and test vectors |
| `isc_seq/` | ISC map implementation, byte extraction profiles, statistical and NIST tooling |
| `isc_eval/` | Evaluation harness (statistical tests, misuse resistance, AEAD baselines, throughput) |
| `tests/` | Comprehensive pytest suite for map, cipher, auth, and evaluations |
| `results/`, `plots/` | Sequence generation outputs, NIST STS reports, and architectural diagrams |
| `third_party/fdlibm/` | Deterministic sin/cos reference implementation |

---

## Empirical Evaluation on Standard USC-SIPI Benchmark

Evaluated across the standard USC-SIPI image dataset (grayscale: Lena 512, Boat 512, 5.1.09–5.1.14, 5.2.08; color: Baboon 512 RGB, Peppers 512 RGB, Lena 512 RGB):

- **Differential Resistance (NPCR & UACI)**:
  - $\text{NPCR} \ge 99.5980\%$ (exceeds critical $\alpha = 0.01$ and $\alpha = 0.05$ thresholds)
  - $\text{UACI} \approx 33.4594\%$ (within standard theoretical nominal interval $[33.28\%, 33.64\%]$)
- **Shannon Information Entropy**:
  - Exceeds $7.9993$ across all test images (approaching theoretical optimum $8.0000$ for 8-bit images)
- **Correlation Coefficients**:
  - Horizontal, vertical, and diagonal correlation $|r| < 0.005$ in encrypted ciphertexts (reduced from $>0.95$ in plain images)
- **Histogram & Statistical Uniformity**:
  - Chi-square goodness-of-fit test passes uniform distribution hypothesis ($p > 0.01$)
- **Strict Key Sensitivity**:
  - Single-bit key flip produces bit change rate $\text{NBCR} \approx 49.9976\%$ with negligible standard error

---

## Running Tests and Evaluations

### 1. Pytest Test Suite
```bash
python -m pytest tests/
```
Set `ISC_SLOW=1` to run long-duration statistical and high-sample tests:
```bash
ISC_SLOW=1 python -m pytest tests/
```

### 2. Enhanced Cipher Pipeline Self-Test
Verify round-trip invertibility, SIV nonce derivation, and diffusion integrity:
```bash
python experiments/paper_workflow_study/test_enhanced_pipeline.py
```

### 3. USC-SIPI Standard Evaluations
Run the full benchmark evaluation on grayscale and RGB standard dataset images:
```bash
python experiments/paper_workflow_study/run_standard_evaluations.py
```

### 4. Diffusion and Downstream Benchmarks
Run candidate diffusion comparisons and S-box metrics:
```bash
python experiments/diffusion_study/benchmarks/benchmark_diffusion.py
python experiments/step4_candidates/improved_sbox.py
```

---

## Author & Attribution

- **Bhoomi Saraf** ([@BhoomiSaraf](https://github.com/BhoomiSaraf))
