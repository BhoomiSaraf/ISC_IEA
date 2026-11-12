# Gate A experiment plan (final draft for review): A1-A15

Date: 2026-10-26, **revision B** (after the checkpoint-3 review: A1 split into findings F1-F5; A15 finalised; A11(ii) labelled as a proxy; A11(iii) distribution defined). Baseline: Checkpoint 3 (`research/checkpoint3_report.md`).
* Pre-registration source: `research/attack_plan.md` (revision 2).
* This document finalises procedures and runtime budgets.
* Adjustments to revision 2 are listed in §3, each with its reason, **before any result exists**.
* **Nothing below has been run.**

## 1. Common conventions

**Constructions compared** (the identical envelope unless stated):

| label | kind | definition |
|---|---|---|
| V-FULL | **experimental (ISC-IMG v1)** | as specified, profile 1 |
| V-STREAM | experimental ablation | body = p XOR `fwd` bytes; same HKDF, nonce, KCV, HMAC |
| V-LINEAR | experimental ablation | V-FULL with S = identity |
| V-PERM | experimental ablation | body = q (permutation only) |
| V-FIXN | experimental misuse mode | any variant with the nonce forced to a constant (test-only entry point) |
| V-CHACHA | **controlled comparison** (agreed) | V-FULL with every ISC stream replaced by ChaCha20 (key = HKDF label `chacha/<stream>`, 16-byte zero nonce/counter), bytes consumed identically; KCV field zero |
| AES-256-GCM | **standard AEAD baseline** | `cryptography` 50.0.0; 12-byte random nonce; AAD = the 36-byte-equivalent header fields; body = raw pixel bytes |
| ChaCha20-Poly1305 | **standard AEAD baseline** | same conventions |
| AES-256-GCM-SIV | **standard misuse-resistant AEAD baseline** | same conventions; used for the nonce-reuse comparison |

**Keys and nonces.**
* Experiment keys are derived from a **public** experiment seed: HKDF(salt = "ISC-IMG Gate A", IKM = run
  label). They are labelled public test keys and recorded so that runs are reproducible. No real secret
  key exists in this project.
* Fresh nonces come from `os.urandom` and are recorded (they are public).
* Forced (reused) nonces are used only in nonce-misuse experiments, through the test-only entry point.

**Backends.** R1 and V1 are both known-answer-verified; the faster one is chosen per workload.
* R1 for single-lane or long single-orbit work (about 10 µs per lane-step);
* V1 for whole messages and many-lane batches (about 1.05 ms per step at 64 lanes, about 1.5 µs per
  lane-step at 4,096 or more lanes).

No code optimisation is planned in this phase.

**Cost model** for one V-FULL operation on n elements (V1):
* about 1.3 s + about 135 µs × n;
* calibrated from the Checkpoint-3 scikit-image run (the measured component costs underestimate it by
  about 2.7×);
* examples: 64×64 ≈ 1.9 s, 512×512×3 ≈ 108 s, 4096² ≈ 38 min.

**Outputs.**
* Each run writes to `results/encryption_experiments/<id>_<UTC>/`, containing `config.json`,
  `environment.json` (OS, CPU flags, Python/NumPy/cryptography versions, source SHA-256),
  `command.txt`, `log.txt`, `raw/`, `summary.json`/`.csv`, plots where relevant, and `manifest.json`.
* Failures and exclusions are logged; nothing is overwritten.

**Order of work.**
1. A **diagnostic run** of every harness on the smallest inputs (1-2 iterations, under 15 min in
   total), to validate the harnesses and recalibrate the estimates.
2. Then priority 1, priority 2 and priority 3.
3. Long jobs run in the background with a hard time limit. No unbounded loops.

## 2. Experiment table

Type:
* **PR** = pre-registered (procedure and criterion fixed in `attack_plan.md` rev. 2, adjustments in §3);
* **EX** = exploratory (the method is not fixed in advance; only the success criterion and budget are).
  Exploratory results are reported as exploratory.

| id | type | objective | threat model | procedure | inputs | attack succeeds / test fails if … | runtime est. | output |
|---|---|---|---|---|---|---|---|---|
| **A2** | PR | ciphertext integrity | CCA, tampering | every bit flip (4×6×3 ciphertext); 10^4 random flips (512×512×3); truncate or extend by 1..64 bytes; swap nonce, KCV or tag; re-label dimensions with equal n; profile change; 10^3 wrong keys; for V-FULL and V-CHACHA | public test key; 2 images | any modified ciphertext or wrong key accepted | 10 min | `A2_tamper_*` |
| **A12** | PR | statistical re-validation of the **new generator G_v1** | statistical | official NIST STS 2.1.2, 15 tests, binary input, default parameters (same tooling as `results/nist_sts_official`): (i) `fwd` stream, 100 messages × 10^6 bits; (ii) `perm` stream, same; (iii) single-lane sequences, 100 sequences of 10^6 bits (one lane each; 64 lanes from each of 2 messages, first 100 used) | 100 + 2 (K, N) pairs | flagged series beyond chance (chance tail p < 0.01), or a uniformity failure in any single-series test | generation 10 min + STS 3 batches in parallel about 30 min ≈ **45 min** | `A12_nist_gv1_*` |
| **A1** | PR (V-STREAM, V-PERM, V-LINEAR, AEADs) / **EX** (V-FULL, V-CHACHA) | nonce-reuse findings, judged separately | **nonce-misusing** CPA | see **§2.1** (findings F1-F5, each with its own criterion) | 64×64 gray; one fixed (K, N) | see §2.1 | (a-d) 20 min; V-FULL and V-CHACHA **cap 8 h in total** | `A1_misuse_*` |
| (A1 exploratory part) | EX | merged into the A1 row and §2.1 | | | | | | |
| **A9** | PR | **nonce-respecting** counterparts of F1 and F5 | nonce-respecting CPA | F1′: encrypt the same image under 10 fresh nonces; F5′: apply every equivalent key D̂ recovered in A1 for (K, N₁) to ciphertexts under (K, N₂ ≠ N₁) for 20 images | outputs of A1 | F1′: any two ciphertexts of the same image share their body. F5′: element agreement > 1/256 + 3σ (σ = √((1/256)(255/256)/n_total)) | 5 min | `A9_nonce_respecting_*` |
| **A11(i)** | PR | cross-platform correctness, profile 1 | correctness | 100 random 16×16 images: encrypt on E1 (V1) → decrypt on E2 (R1), and E2 → E1 | public test keys | any decryption failure or mismatch | 15 min | `A11_xplat_*` |
| **A11(ii)** | measurement only; **host-math-library proxy** | how much host `math` sin/cos differ between E1 (MSVC CRT) and E2 (glibc) | correctness (measurement) | compare `math.sin`/`math.cos` bit patterns on E1 and E2 for the 100,063 KAT arguments; first divergence step of the 10 KAT trajectories evaluated with `math` sin/cos. **This is a proxy for host-libm differences. It does NOT test NumPy profile 2 and does not establish cross-platform reproducibility of profile 2. NumPy is not installed on E2 (installation needs approval).** | KAT arguments | no pass criterion (reported as a measurement) | 10 min | `A11_hostlibm_proxy_*` |
| **A11(iii)** | PR | KCV behaviour under numerical divergence: rates of outcomes | correctness | 1,000 trials on a 4×6×3 image (V1, E1, public test key). Per trial: one sin call drawn uniformly from all sin calls of one decryption, one element uniformly from that call's array, direction ±1 ulp uniformly (public seed). Outcome classes: identical final states and correct plaintext / KCV rejection / **wrong plaintext released**. Rates are reported with Clopper-Pearson 95% intervals | public test key | **test fails if any wrong plaintext is released** | 45 min | `A11_kcv_*` |
| **A6** | PR | weak, cyclic and merging lane states | state space | (a) 10^4 random lanes for the maximum lane length (525,312 steps including burn-in), Brent cycle detection; (b) 2^20 random initial states after burn-in, count identical states, then a **2^12** subset for 2^19 further steps with checks at checkpoints; (c) 10^4 initial-state pairs differing by 1 ulp: steps until \|Δ\| > 0.1; (d) cross-lane and cross-stream correlation and mutual information (data from A12) | random grid states (public seed) | any cycle within the maximum lane length; any merge; divergence after step T; dependence beyond a Bonferroni-corrected 99% bound | (a) 3 h, (b) 1.4 h, (c, d) 10 min ≈ **4.6 h** | `A6_states_*` |
| **A5** | PR | key and nonce sensitivity | KPA-style | flip each of 256 key bits and 128 nonce bits; Hamming distance of the 4 streams (first 10^5 bytes) and of a 64×64 ciphertext body versus 50% | public test key | any per-bit result outside the binomial 99% interval after correction | 35 min | `A5_sensitivity_*` |
| **A3** | PR | differential propagation (fixed nonce) | nonce-misusing CPA | +1 change at the first, last and middle element and 100 random elements; 5 images (128×128 crops of camera, moon, text, coffee-RGB, random) × 5 keys; NPCR/UACI against the critical values of [wu2011npcr] (α = 0.05); per-position distribution; check of the 1/256 cancellation estimate; V-FULL, V-LINEAR, V-CHACHA | crops | reported per variant. NPCR/UACI under fresh nonces are not used as evidence | 20 min | `A3_differential_*` |
| **A8** | PR | permutation recovery transferred to V-FULL | nonce-misusing CPA | the A1(c) attack applied to V-FULL with a fixed nonce | 64×64 | recovers π | 5 min | `A8_perm_*` |
| **A7** | PR | ciphertext statistics (a category of its own) | statistical | V-FULL, V-CHACHA, AES-GCM and ChaCha20-Poly1305 (fresh nonces) on 12 scikit-image samples + 9 synthetic images (256×256 gray and RGB): histogram χ², global and local entropy [wu2013localentropy], H/V/D correlation with confidence intervals; NIST STS on 100 ciphertext bodies of 125,000 bytes (crops of the samples) for V-FULL, V-CHACHA and AES-GCM | images, crops | differences from AES-GCM beyond sampling error are investigated as possible defects. **Statistics only.** | encryption about 45 min + STS about 30 min ≈ **1.3 h** | `A7_stats_*` |
| **A13** | PR | parser robustness, resource limits | implementation | 10^5 random or mutated ciphertexts; boundary sizes; exception types; generator-call instrumentation; resource figures from Checkpoint 3 (n = 2^24: 73 min round trip) | random | any crash other than the documented exceptions; any generator work before tag verification | 10 min | `A13_parser_*` |
| **A4** | **EX** | known-plaintext state recovery of one lane | KPA | (i) reduced precision: ISC on a k-bit grid (k = 12, 14, 16, 18, 20, 24), outputting b scaled middle bits; exhaustive and guess-and-determine recovery; work versus k. (ii) exploratory full-precision guess-and-determine | R1 single lanes | the recovered state predicts the next 10^4 bytes. Failure = "not successful under the tested conditions" | **cap 6 h** | `A4_state_*` |
| **A15** | PR criterion, **EX** model choice | statistical predictability of single ISC lanes | KPA | see **§2.2** (data, split, models, accuracy, multiple-testing correction, linear-complexity thresholds, controls) | R1 lanes, ChaCha20 control, positive control | see §2.2 | 45 min | `A15_predict_*` |
| **A14** | PR | performance and ablation (B1-B6) | none | V-FULL, V-CHACHA and the 3 AEADs; images 64², 128², 256², 512², 1024², gray and RGB; 10 repetitions for n ≤ 2^18, 3 repetitions for larger n; encrypt and decrypt times, peak memory | synthetic | reported against the `design_comparison.md` §4 predictions | **1.8 h** | `A14_perf_*` |
| **A10** | PR | API misuse | — | the public API has no nonce parameter; no replay protection (documented) | — | documentation check | 5 min | `A10_api_*` |

**Totals.**
* Pre-registered: about **11 h** of computation.
* Exploratory caps: A1(e,f) 8 h and A4 6 h, so **at most 14 h** more.
* Independent jobs can run in parallel (the STS runs in WSL, 8 cores), so the expected wall time is
  about **1-1.5 days**, plus harness implementation and analysis.

### 2.1 A1 in detail: nonce-reuse findings F1-F5 (each judged separately)

**Setting.**
* Nonce-misuse only: all queries use one fixed (K, N, 64×64, profile 1) through the test-only entry point.
* The attacker sees the chosen plaintexts and the resulting ciphertexts; the ground truth (π, S, streams)
  is used **only for scoring**.
* Held-out data never queried by the attacker: 20 random images (F4) and a 64×64 crop of `camera` (F5).

| finding | definition | criterion: finding **present** if … | applies to (PR = pre-registered method; EX = exploratory) |
|---|---|---|---|
| **F1 equality leakage** | the same plaintext encrypted twice | bodies identical in all 10 trials | all 8 constructions (PR) |
| **F2 XOR leakage** | c₁ ⊕ c₂ versus p₁ ⊕ p₂ for 10 random pairs | equal on ≥ 99% of elements in every pair | V-STREAM, AES-GCM, ChaCha20-Poly1305, GCM-SIV (PR); V-FULL, V-CHACHA (measured) |
| **F3 permutation recovery** | attacker outputs π̂ | π̂[k] = π[k] for ≥ 99% of k | V-PERM (position-coded images, ⌈log₂₅₆ n⌉ = 2 queries), V-LINEAR (zero image, inversion of the key-independent linear map, then position coding; 3 queries) (PR); V-FULL, V-CHACHA (EX) |
| **F4 equivalent-key recovery** | attacker outputs a decryption procedure D̂ built only from oracle answers | D̂(E(P)) = P on ≥ 99% of elements for each of the 20 held-out random images | V-STREAM (keystream = c ⊕ p), V-PERM (π̂), V-LINEAR (constant + π̂), AES-GCM and ChaCha20-Poly1305 (keystream from one known pair) (PR); V-FULL, V-CHACHA (EX); not applicable to GCM-SIV under this method |
| **F5 decryption of another ciphertext** | D̂ applied to the encryption of the held-out natural image | ≥ 99% of elements correct | same as F4 |

* For each finding, the queries used, the attacker's runtime and the accuracy are reported per
  construction.
* Each finding is reported separately: F1 is not an equivalent-key break, and F3 alone does not decrypt
  anything.
* V-FULL and V-CHACHA F3-F5 are exploratory, with a combined cap of 8 h and 2^20 queries. If no finding
  results, they are reported as "not successful under the tested conditions" with the methods tried.
* Nonce-respecting counterparts are A9 (F1′, F5′), reported in a separate table.

### 2.2 A15 in detail (finalised before any data is generated; preserved once the experiment starts)

**Sources.** 2.2 × 10^6 bytes each, from:
* ISC lanes (R1, profile 1, after burn-in; bytes M(x), M(y) of that lane only): ℓ1 = `fwd` lane 0,
  ℓ2 = `perm` lane 31, ℓ3 = `bwd` lane 63 of one message (public experiment key and nonce, 64×64×3);
* **negative control:** the ChaCha20 `fwd` stream of V-CHACHA for the same message;
* **positive control:** the arccos-quantised byte of x on lane ℓ1 (`arccos8`, which failed NIST earlier),
  to show that the method can detect known structure.

**Split.** Chronological, no shuffling.
* Training targets: bytes 32 … 1,000,031.
* Test targets: the last 1,000,000 bytes.
* Features: the previous 32 bytes.

**Models.**
* **M1:** ridge regression (α = 1.0) on the 32 previous byte values plus an intercept; the prediction
  is the rounded value clipped to [0, 255]; metric = exact-byte accuracy.
* **M2:** logistic regression (L2, C = 1.0, lbfgs, max_iter 200) per output bit b = 0..7, on the 256
  previous bits.
* **M3:** HistGradientBoostingClassifier (max_iter 100, default parameters, random_state 0) per output
  bit, on the 32 previous byte values.

**Accuracy and test.** Accuracy = correct / 1,000,000 on the test set. One-sided z-test against
chance, p₀ = 1/256 for M1 and 1/2 for bits:
z = (acc − p₀) / √(p₀(1 − p₀)/10^6).

**Multiple testing.** 17 tests per source × 3 ISC lanes = 51 ISC tests, family-wise α = 0.01 with
Bonferroni, so per-test α = 1.96 × 10⁻⁴, i.e. z > 3.54.
* **Predictability finding** if any ISC test exceeds z > 3.54.
* Controls are evaluated with the same threshold but are not part of the family.

**Linear complexity.** Berlekamp-Massey over GF(2) on 20 non-overlapping segments of N = 10,000 bits
(bytes MSB-first, from the test portion) per source.
* Finding if any ISC segment has |L_N − N/2| > 10, or a profile maximum of |L_n − n/2| over
  n = 1..N greater than 14.
* The thresholds rest on the approximation that, for random bits, P(|L_n − n/2| ≥ k) is about
  c·2^(−2k); they are set so that the family-wise false-alarm rate over 60 ISC segments is below
  about 0.01. **The approximation is not verified here.** The negative control checks it empirically.

**Validity rules (fixed now).**
* If the ChaCha20 control triggers any criterion, the method is declared invalid and ISC results are
  not interpreted.
* If the positive control triggers nothing, the method is declared insensitive, and an ISC "no
  finding" is reported as uninformative.

**Reporting.** Accuracy, z and the linear-complexity statistics are reported for all 5 sources. A
negative result is reported as "no predictability detected by M1-M3 and BM under these conditions",
never as unpredictability.

## 3. Adjustments to `attack_plan.md` revision 2 (made before any result; each needs approval)

| item | revision 2 | proposed | reason |
|---|---|---|---|
| A6(b) long run | 2^16-lane subset × 2^19 steps | **2^12**-lane subset × 2^19 steps | 2^16 lanes × 2^19 steps at the measured cost ≈ 14.5 h; 2^12 ≈ 53 min. The lower bound on distinct states weakens accordingly (m² ≈ 2^24 instead of 2^32), and is reported as such |
| A12 single-lane sequences | "one sequence per lane position class" | 100 single-lane sequences from 64 lanes of each of 2 messages | concrete design; 62,500 steps per message gives 64 sequences |
| A11(ii) | profile 2 E1 vs E2 | **BLOCKED** (no NumPy on E2) + `math`-module proxy | installing NumPy in WSL needs an external download and your approval. Alternative: approve `pip install numpy` in WSL |
| A1(e,f) budget | 2^20 chosen images, 48 h | 2^20 chosen images, **8 h** combined | runtime management. Unsuccessful within 8 h is reported as "not successful under the tested conditions (8 h, 2^20 queries)" |
| A14 repetitions | 10 for all sizes | 10 for n ≤ 2^18, 3 for larger n | 1024²×3 needs about 7 min per operation; 10 repetitions ≈ 2.3 h for that size alone |
| A15 data | 10^7 bytes per source, unspecified models | 2.2 × 10^6 bytes per source, R1 single lanes, models and thresholds as in §2.2 | V1 has about 1 ms overhead per step; R1 is about 100× faster for single lanes |
| A7 NIST on ciphertext | V-FULL only | V-FULL, V-CHACHA and AES-GCM | fair comparison as requested |
| AEAD set | GCM, ChaCha20-Poly1305, GCM-SIV | unchanged (GCM-SIV used mainly in A1 and A14) | — |

## 4. Reporting rules (restated)

* Correctness, reproducibility, statistical properties, confidentiality and integrity are reported
  separately.
* Passing statistics is not evidence of security.
* An unsuccessful attack is reported as "not successful under the tested conditions" (with budget and
  data).
* Successful attacks are reported prominently, with cost, and the stop/redesign rules of
  `attack_plan.md` §6 apply.
* Any change to a criterion after results are seen is logged in `attack_plan.md` §7 with its reason;
  the original criterion stays.

## 5. Revision C (after the diagnostic run): calibrated costs and proposed changes, FOR APPROVAL

Diagnostic evidence: `research/gate_a_diagnostics.md`.
* The machine has 7.8 GB RAM (about 0.8 GB free during the diagnostic run) and 4 cores, so the full
  batch must run **sequentially**. The only exception is that one WSL STS job may overlap one
  Windows job.
* The estimates below scale the measured diagnostic times by workload, using the measured component
  costs (V1 about 1.05 ms per step at 64 lanes, about 1.5 µs per lane-step at ≥ 4,096 lanes; V-FULL
  operation ≈ 1.3 s + 135 µs × n).

| id | full workload | calibrated estimate |
|---|---|---|
| A10 | API check | < 1 min |
| A2 | V-FULL and V-CHACHA: 1,477 small-ciphertext cases, 10^4 flips (512×512×3), 1,000 wrong keys | ≈ 5 min |
| A13 | 2 × 10^5 random or mutated inputs | ≈ 8 min |
| A1 | pre-registered F1-F5 (10 / 10 / 20 trials) + exploratory part (proposed change 5) | ≈ 3 min + ≈ 30 min (cap 8 h unchanged) |
| A8 | V-FULL position coding | < 1 min |
| A9 | 10 fresh-nonce encryptions + 20 transfers per construction | ≈ 5 min |
| A5 | 384 flips, 10^5 bytes per stream | ≈ 40 min |
| A3 | 5 images × 5 keys × 3 variants × 104 queries | ≈ 10 min |
| A11(i) | 100 + 100 images E1 ↔ E2 | ≈ 17 min |
| A11(ii) proxy | fixed workload (100,063 arguments, 10 trajectories) | < 1 min |
| A11(iii) | 1,000 perturbation trials | ≈ 45 min |
| A6(a-d) | as planned | ≈ 4.3 h |
| A6(e) post-hoc (proposed change 1) | merge rates at 21 distances × 10^6 states; block compression for 10^4 blocks | ≈ 15 min |
| A4 (EX) | k = 10, 12, 14 (proposed change 3) | ≈ 35 min (cap 6 h) |
| A15 | as §2.2 with proposed change 2 | ≈ 50 min |
| A14 | all sizes, untraced timing + 1 traced repetition + 1 warm-up | ≈ 2.3 h |
| A7 | 21 images × 4 constructions + 3 × 100 ciphertexts + 3 STS batches | ≈ 1.3 h |
| A12 | 100 + 100 + 100 sequences + 3 STS batches | ≈ 45 min |
| **total** | | **≈ 12.5 h sequential** (plus at most about 14 h only if the exploratory caps are reached) |

**Proposed changes (each needs approval; made before any full-run result):**

1. **A6(e), new and labelled POST-HOC** (triggered by the diagnostic finding):
   * merge rate of initial-state pairs at distance d = 1, 2, 4, …, 2^20 ulp in x and in y
     (10^6 random grid states per d, one step, plus 64 steps to confirm);
   * the number of distinct one-step images of 10^4 blocks of 2^10 consecutive grid values;
   * an effective-entropy estimate per lane, reported as an estimate with its assumptions.

   No pass/fail criterion; it is a measurement. A6(a-d) and their criteria are unchanged.
2. **A15, M2 training size:** logistic regression on 10^6 × 256 bit features needs about 2 GB as
   float64, which does not fit the free memory.
   * Proposed: M2 is trained on the **first 250,000** training samples, and predictions are made in
     chunks over the full 10^6 test samples.
   * M1, M3, the test size, the thresholds and the controls are unchanged. Power is set by the test size
     and is unaffected.
3. **A4 (exploratory), k values:** k = 16 needs about 2^34 map evaluations (about 8 h > cap). Proposed
   k = 10, 12, 14.
4. **A14:** timing repetitions untraced, one traced repetition for peak memory, plus one discarded
   warm-up repetition. This fixes the 12× distortion found in the diagnostic.
5. **A1 exploratory part (V-FULL, V-CHACHA), made concrete:**
   * (EX-1) codebook for n = 2 (65,536 queries);
   * (EX-2) single-position probe: vary one plaintext element over all 256 values, with all other
     elements fixed, for 32 positions, and test whether any ciphertext position is a fixed function of
     the varied byte that is consistent across probes (which would leak S or π structure);
   * (EX-3) the pre-registered transfer attempt (already implemented).

   Methods from [hoang2026cryptmethod] are **not** attempted (full text not read).
   Unsuccessful = "not successful under the tested conditions".
6. **Execution order:**
   * the A6(e) analysis first;
   * then priority 1, priority 2, priority 3 sequentially;
   * one WSL STS job (A12, A7) overlapped with one Windows job;
   * a hard time limit per job of 1.5 × its estimate, after which it is stopped and reported as
     incomplete.

## 6. Revision D (2026-10-26): correction to revision C, proposed change 2 (A15)

The revision-C sentence "Power is set by the test size and is unaffected" is **incorrect and
withdrawn**: reducing M2's training data can reduce its sensitivity to weak dependences. The frozen
replacement method, its limitation and an added descriptive learning curve are in
`research/a15_revised_method.md`. The criteria and thresholds are unchanged. The revision-C text above
is left unedited, as a record.
