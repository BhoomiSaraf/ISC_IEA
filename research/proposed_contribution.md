# Proposed research contribution (draft for checkpoint 1)

Status: proposal only. No cipher has been designed or implemented. The final architecture is a Phase C
decision and will be presented at checkpoint 2.

## Recommended direction (A): an ISC image cipher evaluated by attacks and ablation

Working title: *An ISC-map image cipher under a nonce-based threat model: attack-driven evaluation,
keystream-source ablation and cross-platform reproducibility.*

### Contribution statements and their status

| # | statement | category | evidence planned |
|---|---|---|---|
| C1 | A fully specified ISC-based image cipher: HKDF-derived, domain-separated ISC initial states per (key, nonce); keystream from a NIST-screened extraction rule; keyed permutation; diffusion; encrypt-then-MAC | **adaptation**: envelope reused from [rfc5869], [bellare2008ae], [medical2026chacha], [jcta2025blockauth]; permutation-diffusion from [fridrich1998]; Fisher-Yates [durstenfeld1964] with [lemire2019] | specification + exact round-trip tests |
| C2 | Executed attacks on our own construction and on deliberately weakened variants: equivalent-keystream CPA/KPA under fixed versus fresh nonces, permutation recovery, nonce reuse, ciphertext tampering, differential propagation, finite-precision state collision search | **new experimental evidence** (methods reused from [jolfaei2016], [entropy2022crypt2dhyper], [entropy2023crypt2dhyper], [li2018autoblocking]) | attack scripts, raw outputs, success/failure tables |
| C3 | Keystream-source ablation: the identical envelope with ISC replaced by ChaCha20, plus AES-GCM and ChaCha20-Poly1305 as AEAD baselines, on the same images | **new experimental evidence** | runtime, statistics and attack outcomes side by side |
| C4 | Specified floating-point evaluation of ISC and a cross-library reproducibility test (decrypt under a different sin/cos implementation) | **adaptation** of [reliability2019devices], [coremath2022] to ISC; ISC-specific measurements | divergence iteration, decryption success matrix |
| C5 | Extraction rule justified by existing official NIST STS results (sign/arccos rejected; mantissa/fraction bytes retained) | **reuse of project evidence**; statistical only | existing `results/nist_sts_official/` |
| H1 | Finite-precision keystream-length bound from cycle scaling | **unresolved hypothesis** | designed cycle experiment; reported as a hypothesis unless it is supported |

### Explicit non-claims

* No claim that the cipher is secure, IND-CPA or IND-CCA. Integrity comes from HMAC, not from ISC.
* No claim that ISC is better than other maps for cryptography.
* No claim of novelty for the envelope, the permutation-diffusion structure or the use of a nonce.
* NIST, entropy, correlation and NPCR/UACI results are reported as statistics, not security evidence.

### Why this direction

It follows the literature's main lessons:
* keystreams that depend only on the key are the recurrent root cause of breaks, which per-message
  nonces address;
* statistics are insufficient, so attacks are executed;
* digital chaos must be specified, so a floating-point profile is defined.

It keeps the frozen map unchanged, reuses the verified ISC sequence code, and is honest about where
the security comes from.

## Alternative B: a conventional deterministic permutation-diffusion cipher

A Madhu-style scheme without a nonce, with plaintext-dependent or key-only keystreams, evaluated by
histograms, correlation and NPCR/UACI. This would be comparable with most published papers, but the
literature predicts CPA/KPA equivalent-key breaks ([entropy2023crypt2dhyper],
[hoang2026cryptmethod], [li2019yearreview]). **Recommendation:** do not propose it. Implement it
only as a *weakened variant* inside C2 to show that such breaks happen, and that the conventional
metrics do not detect them.

## Alternative C: ISC-derived S-boxes or other component-level contribution

The 2018 review notes that S-boxes are rarely used in image encryption [li2019yearreview]. A
key-dependent, ISC-generated S-box could replace additive diffusion. Chaos-based S-box generation
is itself a large literature that this survey did not cover. Novelty would be doubtful without a
dedicated survey, and S-box quality metrics again fall short of proving security.
**Recommendation:** not now; possible future work.

## Decisions needed at checkpoint 1

1. Accept direction A (evaluation-centred, narrow novelty), or prefer B or C.
2. Whether the paper's framing as "experimental construction + attack-driven evaluation" is
   acceptable for the intended venue.
3. Whether ω stays fixed at 10.0 (recommended: yes; the secret is only in the derived initial
   states), or a key-derived ω in [8, 12] should be examined as a separate, labelled experiment.
4. Test images: synthetic images plus scikit-image's bundled sample images (documented provenance,
   no download needed) are proposed. Standard sets such as USC-SIPI require a download and
   licence check.
