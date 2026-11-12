# Design comparison: ISC-IMG v1 against the closest published methods and the standard baselines

Status: checkpoint 2, revision 2 (2026-10-26); status labels as defined in `algorithm_design.md`. Every element below is [PROPOSED] (not implemented). "Abstract-level" sources are marked: those comparisons rest on abstracts only
(see `literature_review.md` §0).

## 1. Element-by-element provenance

| element of ISC-IMG v1 | status | source / closest prior use | what is specific here |
|---|---|---|---|
| encrypt-then-MAC with HMAC-SHA-256 over header and body | **established** | [bellare2008ae], [rfc2104]; around image ciphers: [medical2026chacha], [jcta2025blockauth] (abstract-level) | nothing |
| HKDF with random nonce as salt; domain-separated labels; header fields bound into `info` | **established** | [rfc5869], [krawczyk2010]; nonce plus HKDF for image keys in [medical2026chacha] (abstract-level) | label set and context layout only |
| 128-bit random nonce, probabilistic uniqueness | **established** | [rogaway2004nonce]; nonce-reuse consequences [bock2016nonce] | nothing |
| key → chaotic initial state through a KDF instead of key splitting or plaintext hashing | **adaptation** | key splitting and XOR mixing in [sharma2022hsm] (not used); plaintext-hash initialisation in [zhu2018sha256], [cao2013lhi] (not used); HKDF-seeded chaos in [jcta2025blockauth] (abstract-level) | exact mapping of 16 bytes to the 2^106-point binary64 grid in [−1,1)², with an exactness proof and an effective-key-space statement |
| frozen ISC map as the generator | **project-specific** | ISC defined in this project; related maps [chebsine2019], [lu2025sinecheb], [sineikeda2023] | the map is frozen; its use is the subject of study, not a claimed improvement |
| extraction of mantissa bits 8..15 | **adaptation** | bit extraction from chaotic values is common ([patidar2009prbg], [wang2019prng], abstract-level) | the rule was *chosen* using the project's official NIST STS results on an earlier generator (G_prior: profile 2, single orbit, T = 5000), which rejected sign and arccos extraction. **These results do not transfer to the v1 generator** (profile 1, HKDF seeds, 64 lanes, T = 1024), which is untested ([OPEN], A12; `algorithm_design.md` §14). |
| 4 streams × 64 lanes (256 independently seeded orbits), interleaved within each stream | **adaptation** | parallel chaotic streams are common; no specific source claimed | lanes give vectorisation and limit the exposure from one recovered state. Cross-lane independence is [OPEN] (A6(d), A12). |
| fdlibm-based portable sin/cos profile and a numerical KCV | **adaptation** | cross-device failure [reliability2019devices]; correctly rounded libraries [coremath2022], [aanjaneya2022rlibm]; fdlibm (Sun, 1993) | applying a fixed elementary-function algorithm to make a transcendental chaotic cipher reproducible, plus an authenticated check value that separates numerical divergence from forgery. No prior use was found in the literature reviewed; this is not claimed as a general novelty. |
| Fisher-Yates permutation with unbiased bounded integers | **established** | [durstenfeld1964], [lemire2019] | avoids sort-based index generation, which leaked in [embedded2019crypt] |
| key-dependent 8-bit S-box by Fisher-Yates | **established** | S-boxes recommended but rarely used in image ciphers [li2019yearreview] | nothing |
| forward plus backward chained diffusion | **established** | forward/backward ciphertext-feedback diffusion is widespread and has been attacked [entropy2022crypt2dhyper], [entropy2023crypt2dhyper], [hoang2026cryptmethod] | an S-box inside the chain makes it non-linear over Z_256. Whether this resists the cited reductions under nonce reuse is **untested** (A1, A3). |
| single round | **design choice** | | not justified by any security argument. It is a parsimony choice for the nonce-respecting model, where repeated rounds do not change the unproven status. Under nonce reuse the round count may matter; A1 measures this (§4). |

**Conclusion on novelty.** The construction is an assembly of established techniques. The parts specific
to it are the ISC key-to-state mapping, the ISC byte generator (profile, transient, extraction,
lanes) and the KCV. Any contribution must therefore come mainly from the evaluation (attacks,
ablation, reproducibility), as approved at checkpoint 1.

## 2. Comparison with the closest published methods

| aspect | Sharma et al. 2022 [sharma2022hsm] | Zhang et al. 2025 [lu2025sinecheb] (abstract) | Zhong et al. 2018 [chebsine2019] (abstract) | Ouda 2026 [medical2026chacha] (abstract) | Poetro et al. 2026 [jcta2025blockauth] (abstract) | **ISC-IMG v1** |
|---|---|---|---|---|---|---|
| keystream source | 2D Hénon-Sine map | 2D-ISCM | 2D Chebyshev-Sine map | ChaCha20 | DNA-chaos core | frozen ISC map, 4 streams × 64 lanes |
| key → state | 256-bit key split, XOR-mixed, mod 1 | ? | ? | HKDF (no chaos) | HKDF + plaintext hash + block coordinates | HKDF(N, K) → exact 53-bit grid states |
| per-message randomness | random 1-pixel border | plaintext-adaptive rules | ? | session nonce | session (X25519) | 128-bit public nonce |
| deterministic under fixed key | no (border) | yes, given the plaintext | ? | no | no | no (yes only if the nonce is reused) |
| permutation | two rounds, role-swapped matrices | CA permutation + enhanced zigzag | row shift / column mixing | keyed permutation | keyed permutation | Fisher-Yates over all elements |
| substitution / diffusion | round diffusions + embedded diffusion | two-way diffusion | CRT-based diffusion | chained diffusion | DNA operations + diffusion | forward + backward chained diffusion with keyed S-box |
| integrity | none | ? | ? | HMAC | block-wise EtM, truncated HMAC | EtM HMAC-SHA-256 (full tag) |
| numerical reproducibility handled | no | ? | ? | n/a (integer) | ? | fixed fdlibm profile + KCV |
| security evidence | statistics, key sensitivity, NPCR/UACI | experiments (per abstract) | claims differential/CPA resistance | ? | reduction argument for the MAC layer (per abstract) | planned executed attacks + ablation + AEAD baselines; no security proof |

**Differences from the Madhu paper, which was used as workflow reference only.** No key splitting
into 32-bit parts, no XOR subkey pairing, no mod-1 mapping, no random border, no two-round
role-swap structure and no embedded diffusion; the map is ISC, not 2D-HSM. What remains in common
is the general confusion-diffusion workflow and the reporting of standard metrics, which are generic
to the field [fridrich1998].

## 3. Baselines and how comparisons are kept fair

| baseline | definition | what it isolates |
|---|---|---|
| **V-CHACHA** | ISC-IMG v1 with each generator g replaced by ChaCha20 (key = HKDF label `chacha/<g>`, 32 B; 16-byte all-zero nonce/counter field; output bytes consumed exactly like the ISC bytes). Same HKDF, S-box, permutation, diffusion, format and MAC; KCV field zero. | the effect of the keystream source alone (ISC versus a standard stream cipher) |
| **V-STREAM-ISC** | body = p XOR next_bytes(fwd, n): no permutation, no S-box, no diffusion; same envelope | whether permutation and diffusion add anything under the nonce model |
| **AES-256-GCM** | `cryptography` AESGCM; 12-byte random nonce; AAD = header fields; body = raw pixel bytes | established AEAD reference |
| **ChaCha20-Poly1305** | `cryptography` ChaCha20Poly1305; same conventions | established AEAD reference |
| **AES-256-GCM-SIV** | `cryptography` AESGCMSIV; same conventions | established nonce-misuse-resistant AEAD, the fair reference for misuse experiments |

* All baselines run on the same images, in the same process, with the same timing harness.
* Their input is the identical flattened byte array plus the same header fields as associated data.
* Ciphertext statistics are computed on the body only.

## 4. Does the custom construction offer a measurable benefit? (hypotheses)

The honest prior expectation, from the literature and the construction itself, is **no security or
speed benefit**. The investigation is framed so that a negative answer is a clean result.

| id | hypothesis that would show a benefit | measurement | expected outcome (prediction, to be tested) |
|---|---|---|---|
| B1 | ISC-IMG is faster than an AEAD | runtime per image and per MB, all variants | **No**: Python/NumPy ISC needs about 3n lane-steps of transcendental arithmetic, while AES-GCM and ChaCha20 are optimised C/assembly |
| B2 | ISC-IMG ciphertext statistics are better | entropy, correlations, χ², NPCR/UACI under fixed nonce, NIST STS on ciphertext | **Indistinguishable** from AEAD ciphertext under fresh nonces. A difference would indicate a defect, not a benefit |
| B3 | ISC-IMG resists an attack the AEADs do not | all A-attacks under fresh nonces | **No**: under fresh nonces neither family is broken by the planned attacks; AEAD security rests on far stronger evidence |
| B4 | ISC-IMG degrades more gracefully under nonce reuse than GCM/ChaCha20-Poly1305 | A1 on V-FULL vs V-CHACHA vs GCM vs GCM-SIV: leakage of p1 ⊕ p2, plaintext equality, chosen-plaintext equivalent-key recovery cost; integrity after reuse | **Possibly** better than GCM: GCM leaks p1 ⊕ p2 directly and allows forgeries after reuse [bock2016nonce], while V-FULL becomes a deterministic cipher with intact HMAC integrity. Any such difference comes from the envelope (permutation, diffusion, HMAC), so **V-CHACHA should show the same benefit**: it is not attributable to ISC. **Not better than GCM-SIV**, which is designed for this. If V-FULL is cheaply broken under reuse, B4 is refuted. |
| B5 | ISC-IMG offers properties tied to chaos (key sensitivity, "complex dynamics") that matter for security | key/nonce sensitivity experiments | these hold equally for HKDF + any PRF-based generator; **no specific benefit** expected |
| B6 | ISC-IMG is more portable or reproducible | cross-platform KAT (Windows vs WSL Linux), profile 1 vs profile 2 | **No benefit over AEADs**, which are integer-exact. Profile 1 is meant to remove an ISC-specific disadvantage, not to create an advantage |

## 5. Is the ISC map cryptographically justified as a keystream source?

**Assessment: not justified on current evidence. It is acceptable only as the object of an experimental study.**

| argument | for | against |
|---|---|---|
| dynamics | two positive Lyapunov exponents (about 2.73 and 1.64 nats/step at ω = 10), 0-1 test K ≈ 0.998 | chaotic behaviour is a property of the real-valued map. The cipher uses a finite-precision version, which is eventually periodic [grebogi1988], [li2005degradation]. Sensitivity to initial conditions is not unpredictability to an adversary who knows the map. |
| statistics | earlier generator G_prior, `mantissa8` bytes: 0 flagged series in official NIST STS (100 × 10^6 bits). Not yet measured for the v1 generator. | statistical tests can reject but never certify a generator [sp80022], [preishuber2018]; insecure generators pass them |
| state size | 2^106 initial grid states per lane (`algorithm_design.md` Lemma 2) | this is a representation size and an **upper bound** on per-lane min-entropy, not a security level. Merging of states, state recovery from 16 observed bits per step, and statistical prediction are all untested (§5.4 there; A4, A6, A15). Standard stream ciphers have a 256-bit key and decades of analysis. A key-space guideline such as 2^100 [alvarez2006] is a necessary condition only and is not used as evidence. |
| design maturity | none | standard stream ciphers have decades of public cryptanalysis; ISC has none. Chebyshev-based public-key systems were broken [bergamo2005]; chaos-based ciphers are frequently broken [li2019yearreview]. |
| engineering | none specific | needs a specified elementary-function profile to decrypt across platforms [reliability2019devices]; about 3n lane-steps of transcendental arithmetic per image |

The construction is therefore presented as **"an experimental cipher using ISC as its keystream
source, evaluated by attacks"**. It is **not** presented as a secure replacement for ChaCha20 or
AES. Every confidentiality statement in the paper must carry this qualification.

If all hypotheses B1-B6 come out as predicted, the paper's conclusion will be that **the ISC construction
offers no measurable benefit over standard authenticated encryption in this evaluation**, and its
value is limited to being a carefully engineered and attacked research artefact. That conclusion
will be reported as such.
