# ISC_PBL — Project Status Summary

**Generated:** 11 November 2026
**Scope:** Everything currently present in `C:\Users\bhoom\Desktop\ISC_PBL` plus the related external codebase it audits (`sine_chebyshev_ikeda_analysis`).

---

## 1. What this project is

This is a research pipeline for the **Ikeda–Sine–Chebyshev (ISC) chaotic map**, a 2D chaotic system combining Ikeda-map-style rotation, sine folding, and Chebyshev polynomial coupling. The end goal is to turn this chaotic map into a **chaos-based image encryption cipher** and evaluate it rigorously enough to be publication-grade (NIST SP 800-22, Chi-square uniformity, cryptanalytic attack testing, AEAD comparisons against AES-256-GCM / ChaCha20-Poly1305).

There are two source materials backing the math:
- `Ikeda_Sine_Chebyshev_Map_Analysis.pdf` — the theoretical analysis of the map.
- `Madhu_MTAP_SecondPaper (2).pdf` — a related second paper (context for prior work in this space).
- `ISC_PBL_Evaluation_Proposed_Map_Final_Comparison_Updated.pptx` — a slide deck comparing the proposed map/evaluation against alternatives.

The work is organized in **Steps**, tracked like a lab notebook with frozen baselines, backups, and audit documents at each stage.

---

## 2. Step 1 / Step 1.1 — Sequence Characterization (COMPLETE, frozen)

**Goal:** characterize the raw statistical quality of the ISC map's chaotic output stream (before any cipher is built around it) — uniformity, autocorrelation, entropy, mutual information between the two coordinates, and how to best quantize a continuous float into a byte.

**Key files:**
- `isc_sequence_characterization.py` (current, 88K — the corrected/closure version)
- `isc_sequence_characterization_v1_backup.py` and `isc_sequence_characterization_step1_1_v1_backup.py` (preserved historical versions — do not edit)
- `isc_sequence_characterization_audit.md` — audit of the preliminary run
- `results/sequence_characterization/final_step1_1_closure_report.md` — the final, corrected report
- `results/sequence_characterization/` and `results/sequence_characterization_v1_backup/` — all raw CSVs, NIST results, autocorrelation, byte frequency, mutual information, quantisation comparison, plots (PNG+PDF)
- `script/analyze.py`, `script/final_validation.py`, `script/final_freeze_validation.py` — earlier (Sept 2026) historical validation scripts, kept as read-only reference
- `plots/` — earlier generation of trajectory/bifurcation/Lyapunov/Kolmogorov-entropy plots

**What was actually found (the science):**
- Several byte-quantisation methods were compared: scaled-floor-modulo at `k=13,14,15,16` (`B_n = floor(|x_n| × 10^k) mod 256`) vs. an arccos transform vs. raw float64 mantissa bits.
- **`k=14` was selected as the normative baseline.** It passed Chi-square uniformity (p=0.822 for X, p=0.975 for Y), stayed within Bonferroni-corrected autocorrelation bounds (|ρ|≤0.0028), and achieved ~98.8–99.0% NIST SP 800-22 pass rates across 100 independent sequences.
- Mutual information between the X and Y quantized streams, after correcting for Miller–Madow finite-sample bias and permutation/circular-shift null surrogates, showed **no evidence of exploitable contemporaneous dependence** at k=14 (adjusted MI ≈ 0.0004 bits). Continuous-state MI was higher (~0.0138 bits), a weaker nonlinear coupling, correctly reported as present but small.
- The arccos transform **failed** — it showed severe autocorrelation (ρ(1) ≈ -0.095) and failed byte-uniformity testing (χ² > 5,200), traced to the ISC map's finite sine-folding frequency and Ikeda-style nonlinear phase modulation.
- A Float64-specific numerical defect was found and proven: at `k=16`, due to the 53-bit significand limit, 100% of bytes generated in a certain region are forced even (a parity defect) — meaning `k=16` is numerically unsafe, reinforcing the choice of `k=14`.
- The report explicitly **purged over-claiming language** — nothing here is asserted as "cryptographically secure" or "a proven PRNG"; findings are stated as statistical characterizations only.

**Status: closed and frozen.** This is the validated scientific baseline that any cipher implementation should be judged against.

---

## 3. Step 1.2 Phase 1 — Existing Implementation Reconciliation (COMPLETE, 11 Nov 2026)

This is the most recent and most significant work in the folder (all four audit docs dated today). It discovered and reconciled an **already-built cipher implementation** that lives in a sibling folder, not inside `ISC_PBL`.

**Documents produced (all in `ISC_PBL` root):**
| File | Purpose |
|---|---|
| `existing_implementation_audit.md` | Full audit of the discovered `isc_cipher` implementation: 15-point claim verification table, crypto design audit (key schedule, nonce handling, domain separation, diffusion, auth order), and test execution results. |
| `architecture_discrepancies.md` | Documents 5 concrete mismatches between the Step 1.1 baseline and the actual cipher code. |
| `step_1_2_phase_1_recommendation.md` | Executive Q&A + roadmap: does a cipher exist (yes), is it the right one (yes), what to reuse (~90%), what to fix, what's missing, and the Phase 2 plan. |
| `test_coverage_audit.md` | Independent re-execution of all test suites with a 15-point mandated-requirement checklist. |
| `implementation_feature_matrix.csv` | Row-per-feature traceability matrix (file/line, actual behavior, doc discrepancies, test status) for the cipher implementation. |

### 3.1 What was discovered

A **complete, working, AEAD-style image cipher** called **ISC-IMG v1** already exists at:
`C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis\isc_cipher` (plus `isc_seq`, `isc_eval`, `isc_cipher_kat`, `tests/`), built 25–26 October 2026 — **before** this audit, but apparently not previously connected to the `ISC_PBL` workspace or Step 1.1's findings.

Its design:
- 32-byte key, 16-byte random nonce, HKDF-SHA256 (RFC 5869) key schedule with strict domain separation.
- 4 independent keystream roles (`sbox`, `perm`, `fwd`, `bwd`) × 64 parallel ISC-map lanes = 256 lanes, each burned in for 1,024 steps.
- Byte extraction via **Float64 mantissa bits 8–15**, *not* the Step 1.1 `k=14` scaled-floor-modulo method.
- Lemire unbiased rejection sampling + Fisher–Yates shuffle for S-box/permutation generation.
- Bidirectional non-linear chained diffusion (forward + backward passes with a keyed S-box), decryption vectorized in NumPy.
- A 36-byte `ISCI` ciphertext container with a key-check value (KCV) to detect numerical divergence.
- Encrypt-then-MAC (HMAC-SHA256), with a verified invariant: **no chaotic/plaintext computation happens before the MAC tag is checked** (enforced by a test fixture that fails if generator code runs pre-auth).
- A bit-exact **Netlib fdlibm 5.3** sine/cosine port (Profile 1) specifically to guarantee identical ciphertexts across Windows/Linux/macOS — because the map's Lyapunov exponent (~2.73 nats/iter) means even a 1-ULP libm difference causes total divergence within ~25 iterations.
- An evaluation harness (`isc_eval`) comparing 5 cipher variants (V-FULL, V-LINEAR, V-STREAM, V-PERM, V-CHACHA) against AES-256-GCM, ChaCha20-Poly1305, and AES-256-GCM-SIV, including actual cryptanalytic attacks (position-coding, linear reduction, nonce-misuse differential analysis, key-sensitivity avalanche).

### 3.2 Test results independently re-verified today

| Gate | What | Result |
|---|---|---|
| Gate C (correctness) | `pytest tests/test_isc_cipher_*.py` | **159 passed, 2 skipped**, 0 failed (~12.2 min) |
| Gate A (eval harness) | `pytest tests/test_isc_eval_harness.py` | **16 passed**, 0 failed (~1.4 min) |
| Gate R (reproducibility/KAT) | `gate_r.py` vs. independent C oracle | **PASS** — fdlibm hashes, 74,063 trig values, 10×100,000-step trajectories, 256 lane streams, full ciphertexts all bit-exact |

### 3.3 Critical open discrepancy

**Quantisation mismatch:** the cipher uses mantissa-bit extraction; Step 1.1's statistical validation (NIST/Chi-square/MI/autocorrelation) was only ever done on the `k=14` scaled-floor-modulo method. **The two are not mathematically equivalent**, so Step 1.1's "this is statistically sound" conclusion does **not** currently transfer to the actual cipher as built. Four other discrepancies were also logged (burn-in 1,024 vs 5,000 steps; 256-lane interleaved architecture vs. single long orbit; fdlibm vs. host libm; and deliberate plaintext/keystream decoupling vs. plaintext-hash-seeded designs seen in prior literature).

### 3.4 Recommendation reached

**Continue and reconcile the existing architecture rather than rebuild.** ~90% of the existing cipher code is sound and reusable (key schedule, container format, state mapping, fdlibm engine, sampling/shuffling, diffusion, auth layer, eval harness). The concrete next steps (Phase 2) are:
1. Decide how to reconcile quantisation — either switch the cipher to `k=14`, or run a full independent NIST/Chi-square characterization specifically on the mantissa-bit stream.
2. Physically migrate `isc_cipher`, `isc_eval`, `isc_cipher_kat`, `tests/` into `ISC_PBL` (currently they live in a separate, disconnected folder).
3. Run the full Gate A comparative benchmark suite (throughput, memory, statistical uniformity) against AES-256-GCM and ChaCha20-Poly1305 on real images (Lena, Baboon, Peppers, Cameraman, USC-SIPI).
4. Speed up Fisher–Yates permutation generation for large images (currently scalar Python loops).
5. Formalize fixed-nonce NPCR/UACI measurement to test the diffusion stage's avalanche property in isolation from nonce randomness.

---

## 4. What I can infer about overall project state

- **This is not a toy/class exercise anymore** — it has grown into a fairly mature, two-track research pipeline: (a) a pure-math/statistics characterization of the chaotic map itself, and (b) a full cryptographic engineering implementation with AEAD-grade testing discipline (bit-flip tamper tests, KAT vectors against an independent C oracle, cross-platform determinism engineering). The level of rigor (Miller–Madow bias correction, Bonferroni correction, mpmath 200-bit verification, fdlibm porting) suggests this is being prepared for academic publication, not just a course deliverable.
- **The two tracks were built somewhat independently and only connected today.** The cipher implementation (`sine_chebyshev_ikeda_analysis`) was built in late October without apparent awareness of, or integration with, the Step 1.1 statistical baseline finalized in `ISC_PBL`. Today's audit (11 Nov) is the first point where someone (or an audit agent) formally reconciled the two, and it surfaced a real scientific gap: the shipped cipher's byte-extraction method has never been statistically validated the way the research track's chosen method was.
- **The project is methodical about provenance** — every step keeps "v1_backup" copies of scripts and results before modifying them, and documents are consistently named/dated/identified (`ISC-AUDIT-...`, `ISC-CLOSURE-...` document IDs), suggesting this is tracked like a formal lab/thesis process, possibly with an AI auditing agent ("Antigravity Advanced Pairing") used as an independent verification step rather than the implementer.
- **No actual migration/code changes have happened yet** for Step 1.2 — Phase 1 was purely investigative/audit (read-only). The actual code reconciliation (Phase 2) has not started. The `__pycache__` folder and lack of any `isc_cipher`-named files inside `ISC_PBL` itself confirm the cipher code still physically lives outside this workspace.
- **No version control** — this folder is not a git repository, so all history tracking is being done manually via dated `_backup` file copies and markdown reports rather than commits/branches. This is a risk if files get overwritten (mitigated somewhat by the backup-file discipline already in place).
- **Immediate next decision point** for whoever owns this project: choose between reconciling the cipher's byte-extraction to match the validated `k=14` method, or running a parallel validation specifically for the mantissa-bit method — this blocks Phase 2 and any publication claim of "statistically validated keystream."

---

## 5. File inventory (for reference)

```
ISC_PBL/
├── ISC_PBL_Evaluation_Proposed_Map_Final_Comparison_Updated.pptx   (slide deck)
├── Ikeda_Sine_Chebyshev_Map_Analysis.pdf                           (theory paper)
├── Madhu_MTAP_SecondPaper (2).pdf                                  (related paper)
├── architecture_discrepancies.md            ← Step 1.2 Phase 1 audit doc
├── existing_implementation_audit.md         ← Step 1.2 Phase 1 audit doc
├── implementation_feature_matrix.csv        ← Step 1.2 Phase 1 audit doc
├── step_1_2_phase_1_recommendation.md       ← Step 1.2 Phase 1 audit doc
├── test_coverage_audit.md                   ← Step 1.2 Phase 1 audit doc
├── isc_sequence_characterization.py         ← Step 1.1 current/closure script
├── isc_sequence_characterization_v1_backup.py        (preserved)
├── isc_sequence_characterization_step1_1_v1_backup.py (preserved)
├── isc_sequence_characterization_audit.md
├── script/              (Sept 2026 historical validation scripts)
├── plots/               (early trajectory/bifurcation/Lyapunov plots)
└── results/
    ├── sequence_characterization/            (Step 1.1 final outputs: NIST, MI, ACF, plots, closure report)
    └── sequence_characterization_v1_backup/  (preserved Step 1 outputs)
```

External (referenced, not inside this folder):
```
C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis\
├── isc_cipher/      (the actual ISC-IMG v1 cipher: kdf, state_map, generator, sampling, diffusion, container, cipher, fdlibm)
├── isc_seq/          (sequence extraction utilities, incl. unused frac_byte k=14)
├── isc_eval/         (attack harness, AEAD baselines, benchmarks)
├── isc_cipher_kat/   (known-answer-test vectors + gate_r.py reproducibility checker)
└── tests/            (159+16 passing unit/integration tests)
```
