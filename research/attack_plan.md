# Attack-driven evaluation plan for ISC-IMG v1 (stage 7), revision 2

Status: checkpoint 2, revision 2 (2026-10-26). **Pre-registered; nothing has run.** All items are
[PROPOSED]. Success criteria are fixed before any experiment. A change made after results are seen is
recorded in §7 with its reason, and the original criterion is kept.

Variants (identical envelope unless stated; see `design_comparison.md` §3):
* V-FULL (the proposal);
* V-STREAM (body = p XOR fwd bytes);
* V-LINEAR (S = identity);
* V-PERM (permutation only);
* V-FIXN (nonce forced to a constant);
* V-CHACHA (ChaCha20 streams);
* AES-256-GCM, ChaCha20-Poly1305 and AES-256-GCM-SIV.

## 1. Gates (run in this order; each must pass before the next)

### Gate C: correctness (implementation tests)

1. **Spec example.** The toy-S-box example of `algorithm_design.md` §12.1 reproduces π = [0, 2, 1],
   c = [56, 16, 240] and decrypts to [10, 20, 30] (already checked independently by
   `research/tools/check_spec_example.py`).
2. **Mapping lemmas.**
   * Seeds giving α ∈ {0, 1, 2^52 − 1, 2^52, 2^53 − 1} map exactly to −1, −1 + 2^-52, −2^-52, 0 and
     1 − 2^-52.
   * 10^5 random seeds: float result equals the exact rational computation (Python `fractions`).
   * The 2^11-to-1 property holds for the 11 dropped bits (exhaustive over the low 11 bits for
     sampled high bits).
3. **Component inverses, separately.**
   * Bounded: exact distribution check for small s by exhaustive enumeration of 2^16-word toy
     generators; rejection path exercised.
   * S-box bijectivity and S⁻¹∘S = id.
   * π bijectivity, and gather/scatter inverse.
   * Forward and backward diffusion inverses on random and adversarial inputs (all 0, all 255).
4. **Round trips with exact array equality** for:
   * shapes (1,1), (1,7), (7,1), (2,2), (15,16), (16,15), (64,64), (255,256), and (1,1,3), (4,6,3),
     (31,17,3), (256,256,3);
   * content: constant 0, 128, 255; gradients; checkerboard; a single bright pixel; repeated values;
     uniform random;
   * the scikit-image samples (§4).
5. **Error handling.** Wrong key type or length; non-uint8 arrays, wrong ndim, 4 channels, zero-size
   and oversize (n > 2^24) arrays; malformed ciphertexts (each validation rule of
   `algorithm_design.md` §11.2 triggered individually). The tag is checked before any generator code
   runs, verified by an instrumented call log.
6. **Batched versus scalar.** V1 (NumPy) and R1 (pure Python) produce identical lane states, streams
   and ciphertexts on E1.

### Gate R: reproducibility (KATs, `algorithm_design.md` §7.4)

KATs 1-2 (and the stream KAT) reproduce the **independent C oracle** bit for bit for R1 on E1, R1 on E2
(WSL Ubuntu 24.04, CPython 3.12.3, glibc 2.39) and V1 on E1. KAT 3 (R1-generated) is reproduced by V1 on E1
and R1 on E2. Status: PASSED at Checkpoint 3 (74,063 arguments) and for the 100,063-argument extended KAT 1
(revision 3). The fdlibm deviation from mpmath (200-bit) is recorded per branch. Only after Gate R are E1 and E2
declared supported environments.

## 2. Attacks, in priority order

### Priority 1: attacks on claims the design depends on

| id | attack | model | method | pre-registered criterion: **attack succeeds if …** | action on success |
|---|---|---|---|---|---|
| **A2** | forgery and tampering | CCA | flip every header bit and every body bit (small n), ≥ 10^4 random bit positions (large n); truncate or extend by 1..64 bytes; swap N, KCV or tag between ciphertexts; change H, W, C, profile, version; reshape with equal n (4×6 ↔ 6×4, gray ↔ RGB with W·3); decrypt with 10^3 wrong keys | any modified ciphertext or wrong key is accepted | implementation defect (G-INT is [PROVEN]); fix, re-run Gate C |
| **A12** | statistical re-validation of **G_v1** (new experiment, not a repeat) | statistics | official NIST STS 2.1.2, 15 tests, default parameters, binary input. 100 sequences of 10^6 bits from stream `fwd` of 100 independent (K, N); the same for stream `perm`; also one sequence per lane position class (bytes from a single lane), to detect lane-specific defects. Same analysis code as `results/nist_sts_official/`. | any test with flagged series beyond chance (chance tail p < 0.01), or uniformity failure in any single-series test | reported as a G_v1 weakness. **The extraction rule is not changed merely to pass.** A cause is identified first; any change is v2. Reported regardless of outcome. |
| **A1** | nonce reuse: deterministic CPA, equivalent key | nonce-misusing CPA | (a) equality leak (all variants). (b) V-STREAM: c1 ⊕ c2 = p1 ⊕ p2. (c) V-PERM: recover π with ⌈log₂₅₆ n⌉ chosen images [jolfaei2016]. (d) V-LINEAR: affine reduction and keystream recovery via chosen single-element differences, following [entropy2023crypt2dhyper]. (e) V-FULL: differential chosen-plaintext recovery of S, π and the keystreams; codebook for n ≤ 2. (f) V-CHACHA with the same attacks as (e). Budget: 2^20 chosen images at 64×64; 48 h. | an equivalent key that decrypts a different ciphertext under the same (K, N, H, W, C) with > 99% of elements correct | expected for (a)-(d) and for tiny n. For (e)/(f) at 64×64: reported prominently. No redesign (outside the model); AES-GCM-SIV is the documented remedy |
| **A9** | transfer across nonces | nonce-respecting CPA | apply any equivalent key from A1 to ciphertexts under N₂ ≠ N₁ | element agreement > 1/256 + 3σ | defect in stage 2 or 3 |
| **A11** | cross-platform and numerical-divergence detection | correctness | (i) profile 1: encrypt on E1 and decrypt on E2 and the reverse (100 random images, R1 on E2). (ii) Profile 2 on E1 versus E2 with host libm (expected failure; measured). (iii) KCV test: inject a 1-ulp change into one SIN result at step t in one lane, for t ∈ {burn-in, first output step, middle, last step}, and record detection. | (i) any failure. (iii) any wrong plaintext released without `NumericalDivergenceError` | (i) fix the implementation. (iii) KCV defect; quantify and document the undetectable window |
| **A6** | weak, cyclic and merging lane states | state space | (a) Cycles: 10^4 random lanes run to the maximum lane length (≈ 525,000 steps incl. burn-in), Brent detection with μ, λ recorded. (b) Merges: 2^20 random initial states after burn-in, and again after 2^19 output steps on a 2^16 subset; count identical states, giving the lower bound E_T ≳ m² if no collision. (c) Neighbour divergence: initial states differing by 1 ulp in x or y; steps until \|Δ\| > 0.1. (d) Lane independence: cross-correlation and mutual-information estimates between lanes of one stream and across streams. | any cycle within the maximum lane length; any merge; divergence after step T; dependence beyond a Bonferroni-corrected 99% bound | v2 rejection rule or parameter change, documented; v1 results kept |
| **A5** | key and nonce sensitivity, related keys | KPA-style | flip each of 256 K bits and 128 N bits; Hamming distance of the four streams (first 10^5 bytes) and of the ciphertexts versus 50%, with a binomial 99% interval | any per-bit result outside the interval after correction | defect in stage 2 or 3 |

### Priority 2: standard evaluations, interpreted carefully

| id | analysis | method | criterion and interpretation |
|---|---|---|---|
| **A3** | differential propagation (V-FULL, V-LINEAR, V-CHACHA; fixed nonce only) | +1 at the first, last and middle element and 100 random elements; 5 images × 5 keys; NPCR/UACI against the critical values of [wu2011npcr] (α = 0.05); per-position distribution; check of the 1/256 cancellation estimate (`algorithm_design.md` §9) | failures reported. Under fresh nonces NPCR/UACI are trivially high and **not reported as evidence** |
| **A8** | permutation-recovery transfer | A1(c) applied to V-FULL with a fixed nonce | recovers π |
| **A7** | ciphertext statistics (a category separate from stream tests) | histogram χ²; global and local entropy [wu2013localentropy]; horizontal, vertical and diagonal correlation with confidence intervals; NIST STS on ciphertext bodies (100 × 10^6 bits) | statistics only; differences from the AEADs beyond sampling error are investigated as possible defects |
| **A13** | parser and implementation | 10^5 random or mutated ciphertexts; boundary sizes; exception types; resource limits (n = 2^24 runtime and memory) | any crash other than the documented exceptions; any work on the generator before tag verification |

### Priority 3: research-level, possibly inconclusive

| id | analysis | method | reporting |
|---|---|---|---|
| **A4** | known-plaintext state recovery for one lane | (i) Reduced precision: ISC on a k-bit grid (k = 12..24), output of b middle bits per coordinate per step (b scaled with k); exhaustive and guess-and-determine recovery; work versus k measured. (ii) Full-precision exploratory attack: guess the high-order bits of (x, y) at step t and filter candidates with observed bytes at t, t+1, …, using the expansion of about 3.9 bits per step. | success at k means the recovered state predicts the next 10^4 bytes. The work-versus-k trend is extrapolated only as a labelled estimate. Failure means "not broken by this attempt", never "resistant" |
| **A15** | statistical predictability without state recovery (new in revision 2) | train predictors (linear over GF(2) via Berlekamp-Massey on bit streams; byte-level linear regression; small gradient-boosted classifier on the previous 32 bytes of the same lane) on 10^7 bytes; test next-byte accuracy on held-out data; compare with V-CHACHA | success if accuracy exceeds 1/256 + 3σ, or the linear complexity profile deviates from the ideal ≈ L/2 |
| **A10** | API misuse | confirm that the public API has no nonce parameter; document the absence of replay protection | documentation |
| **A14** | performance and ablation (B1-B6) | 10 repetitions; images 64² to 1024² (gray and RGB, n ≤ 2^24); all variants and baselines; machine, CPU flags and library versions recorded | reported against the `design_comparison.md` §4 predictions, whether confirmed or refuted |

## 3. Interpreting results

| outcome | allowed statement |
|---|---|
| A1(e)-A15 fail to break V-FULL | "not broken by attacks A1-A15 as specified, within the stated budgets" (never "secure") |
| A12 passes | "G_v1 shows no flagged series in official NIST STS at this sample size" (statistical only) |
| Gates C and R pass | "lossless and reproducible on E1/E2 with implementations R1/V1" |
| A2 passes | consistent with the proven integrity of encrypt-then-MAC; says nothing about confidentiality |
| any attack succeeds | reported with cost, data requirements and cause; preserved; redesign only per §6 |

## 4. Datasets and keys

* **Synthetic images.** Constant 0, 128, 255; horizontal and vertical gradients; checkerboards; a single
  bright pixel; uniform random. Sizes 1×1, 1×17, 17×1, 15×16, 64×64, 256×256, 512×512, 1024×1024
  (n ≤ 2^24); gray and RGB.
* **scikit-image samples.** `camera`, `astronaut`, `coffee`, `chelsea`, `moon`, `brick`, `grass`,
  `gravel`, `text`, `checkerboard`, `rocket`, `cat`. scikit-image version, shape, dtype and SHA-256 are
  recorded. Images that are not uint8 are converted by a documented, fixed rule or excluded by a
  pre-registered rule.
* **Keys and nonces.** Experiment keys come from `os.urandom` and are discarded after use. KATs use the
  public test key 0x00..0x1f (labelled as public).

## 5. Output layout

`results/encryption_experiments/<experiment>_<run_id>/`, one directory per run. Each contains a config,
an environment record (OS, CPU flags, Python/NumPy/cryptography versions, source SHA-256), input image
hashes, raw outputs, aggregates, plots, an error and exclusion log, and an execution log. Existing
results are never overwritten.

## 6. Stop and redesign rules

* A2, A9, A11(i) or A11(iii) succeeds → stop; fix; re-run Gates C and R; document the defect and fix.
* A6 or A12 fails → stop the main evaluation; analyse the cause; any redesign becomes v2 with a new
  specification entry; v1 results are preserved.
* A1(e) succeeds → no redesign (outside the model); report prominently.
* A4 or A15 succeeds at full precision → the ISC generator is broken; report it. The paper's conclusion
  changes accordingly.

## 7. Deviations log

(empty: nothing has run)
