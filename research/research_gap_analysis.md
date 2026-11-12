# Research gap analysis

Status: Phase B deliverable (checkpoint 1). Builds on `literature_review.md` and `literature_matrix.csv`.

## 1. What is not a gap

* **"No cipher uses the ISC map."** This is true within our searches, but a new map is not a contribution:
  dozens of maps exist and many map-based ciphers have been broken ([li2019yearreview],
  [preishuber2018]). Using ISC instead of another map does not, by itself, answer any open question.
* **"Combining a chaotic core with HKDF, a nonce and a MAC."** This was published in 2026 around a
  ChaCha20 core [medical2026chacha] and around a DNA-chaos core [jcta2025blockauth] (both
  abstract level). Earlier, hash-keyed chaotic designs existed [farajallah2016auth]. An ISC cipher in
  that envelope is an instance of a known pattern.
* **"Another permutation-diffusion pipeline with good NPCR/UACI and entropy."** These figures do not
  establish security [preishuber2018], [wu2011npcr].

## 2. Comparison with the closest work

Legend: ✓ present; ✗ absent; ? not determinable from what was read (abstract only).

| aspect | Zhong 2018 [chebsine2019] | Zhang et al. 2025 [lu2025sinecheb] | Hanis 2023 [sineikeda2023] | Sekertekin 2016 [ikedahenon2017] | Sharma 2022 [sharma2022hsm] | Zhu 2018 [zhu2018sha256] | Ouda 2026 [medical2026chacha] | Poetro 2026 [jcta2025blockauth] | **this project (direction)** |
|---|---|---|---|---|---|---|---|---|---|
| map | 2D Chebyshev-Sine | 2D-ISCM (Sine+Chebyshev) | Ikeda + additive sine | Ikeda, Hénon | 2D Hénon-Sine | chaotic system | none (ChaCha20) | DNA-chaos | frozen ISC (Ikeda → sin → T₂) |
| full image cipher | ✓ | ✓ | ✗ (key generator) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| standard KDF for chaotic state | ? | ? | ✗ | ? | ✗ (XOR/mod-1 mapping) | ✗ (SHA-256 of plaintext) | ✓ (HKDF; no chaos) | ✓ (HKDF) | ✓ (HKDF, domain separated) |
| per-message public nonce | ? | ✗ (plaintext-adaptive) | ✗ | ? | random border | plaintext hash | ✓ | ✓ (session) | ✓ |
| integrity / tamper detection | ? | ? | ✗ | ? | ✗ | ✗ | ✓ HMAC | ✓ block EtM | ✓ EtM (HMAC-SHA-256) |
| executed KPA/CPA/nonce-reuse attacks on own design | ? | ? | ✗ | ? | ✗ | ✗ (claims only) | ? | ? | ✓ planned (mandatory) |
| finite-precision cycle analysis of the map | ? | ? | cycle length reported | ? | ✗ | ? | n/a | ? | ✓ (existing: μ, λ, quantised scaling) |
| specified floating-point evaluation / cross-platform check | ? | ? | ✗ | ? | ✗ | ? | n/a (integer cipher) | ? | ✓ planned |
| official NIST STS on extracted bits, multi-sequence | ? | ? | ✓ (100 × 10^6, α = 0.001) | ? | ✗ | ? | ? | ? | ✓ (done, 15 tests, 5 extraction methods) |
| same-envelope standard-cipher baseline (only the keystream source changes) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | n/a | ? | ✓ planned |
| AEAD baseline (AES-GCM / ChaCha20-Poly1305) measured on the same images | ? | ? | ✗ | ? | ✗ | ? | ? | ? | ✓ planned |

Abstract-level '?' cells may be filled by the full texts; they must not be read as ✗.

## 3. Defensible gaps

**G1. Attack-driven evaluation of a map-based image cipher, run by its designers.** The cryptanalysis
literature shows that design papers report statistics and rarely execute KPA/CPA/differential
attacks on their own constructions [li2019yearreview], [alvarez2006 Rules 10-12]. Evaluating an ISC
cipher primarily through executed attacks addresses a real methodological weakness, but only
modestly. The executed attacks include:
* equivalent-keystream recovery under fixed and fresh nonces,
* permutation recovery,
* differential propagation,
* tampering and nonce reuse,
* finite-precision state collisions.

**G2. Isolating what the chaotic core contributes.** No reviewed chaotic image cipher compares against
the *same* construction with its chaotic keystream replaced by a standard stream cipher. Such an
ablation directly tests the claimed benefit of chaos (speed or security), which Preishuber et al.
dispute [preishuber2018]. With ISC this can be measured exactly, because the envelope, permutation,
diffusion and serialisation can stay identical.

**G3. Cross-platform correctness for maps with transcendental functions.** Santos et al. showed
decryption failure across devices for a polynomial map [reliability2019devices]. ISC uses sin and cos,
whose results IEEE 754 does not fix [coremath2022]. We measured that 3.2% of the platform's sin/cos
results on ISC arguments are not correctly rounded, and that a last-bit change in evaluating the
squares makes trajectories diverge by iteration 1331. (An earlier note attributed this divergence to
two sine libraries; that was corrected on 2026-10-26.) A specified, testable evaluation profile with
cross-library checks is a small but concrete, ISC-specific contribution. How to obtain correctly
rounded or otherwise library-independent sin/cos in the prototype is an open design question for
Phase C.

**G4. Connecting digital-extraction evidence to cipher design.** The project already has official NIST
STS results showing that ISC sign and arccos bits are strongly non-random while mantissa/fraction
bytes show no flags. Making the extraction rule a justified, tested design decision is an
adaptation of known practice, not new science, and should be presented that way.

**G5. Finite-precision safety bounds for ISC keystream length.** The measured cycle data (μ, λ;
quantised scaling ~1.1 bits of period per bit of precision; no float64 cycle in 2×10^6 steps) could
give an evidence-based limit on keystream length per derived state. This is currently a hypothesis
([grebogi1988] scaling); it needs a designed experiment before it can be claimed.

## 4. Risks to every gap

* **R1. Unprovable core.** The security of any ISC keystream rests on an unproven assumption that
  ISC-derived bytes are unpredictable to an adversary who knows the map. No reduction exists. The
  honest statement is "experimental construction; no security proof".
* **R2. The ablation may simply show that ChaCha20 is faster and at least as strong.** That is a
  legitimate result, and must be reported if observed.
* **R3. Abstract-level comparisons.** Several closest works were read only at abstract level; their
  matrix cells stay '?' unless full texts are obtained.
* **R4. Evaluation contribution versus design novelty.** Venues that expect "a novel cipher" may judge
  G1-G5 as insufficient novelty. The paper must not inflate them.
