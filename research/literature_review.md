# Literature review: chaos-based image encryption and the frozen ISC map

Status: Phase B deliverable (checkpoint 1). Written 2026-10-26, before any cipher design.

## 0. Method and evidence levels

**Search.** Web searches (general and extended), followed by registry verification of every
candidate reference against OpenAlex (by DOI or exact title) and Crossref (by DOI), using
`research/tools/verify_references.py` and `crossref_fetch.py`. Raw registry records are kept in
`research/sources/openalex/` and `research/sources/crossref/`; the formatted list is
`research/references.md` (91 entries). Two references not in the registries were verified by hand
from publisher or archive pages; the evidence is stated next to each.

**Reading depth.** Every entry below carries one of three evidence levels, and claims are limited to it:

* **full text**: an open version was read: Álvarez & Li [alvarez2006], Li, Zhang & Xie
  [li2019yearreview], Li et al. [li2018entropy], Li et al. [li2018autoblocking], Santos et al.
  [reliability2019devices], Hanis [sineikeda2023], and the supplied Sharma et al. paper [sharma2022hsm];
* **abstract**: the registry abstract was read (marked "(abstract)");
* **record**: only the bibliographic record was checked (marked "(record)"). Such references
  are cited only for what their title states.

Publisher pages for several papers returned HTTP 403 to automated access, and their PDFs were not
obtained. Those papers are cited at the "abstract" level only.

**Corrections to existing project material found during verification.** These are recorded here; the
slide deck was not edited.
* The deck cites "Lu, Y.; Xie, X. ... 2D improved Sine-Chebyshev ... (2025)". Crossref lists Yiming
  Zhang, Xiuli Chai, Lvchen Cao, Zhihua Gan, Yang Lu and Xiaodong Xie [lu2025sinecheb].
* The deck cites "Cao, C.; Li, K.; Chang, Q. et al. (2013)". Crossref and OpenAlex list a single
  author, Yang Cao [cao2013lhi].
* The deck's "Ikeda, H. et al., Physica D (1980)" could not be matched. The verified origins of the
  Ikeda map are Ikeda (1979, Optics Communications) [ikeda1979] and Ikeda, Daido & Akimoto (1980,
  Phys. Rev. Lett.) [ikeda1980prl].

**Project findings used below.** These come from this workspace, not from the literature:
`results/sequence_generation/default_20261025/` and
`results/nist_sts_official/sts212_default_20261025/`.

## 1. Chaos-based image encryption with discrete-time maps

The permutation-diffusion architecture goes back to Fridrich (1998) [fridrich1998] (abstract). There, a
discretised invertible 2D map acts as a pixel permutation, composed with a simple diffusion step.
The abstract itself notes that the discretised map is a permutation and "cannot be chaotic".
Chen, Mao & Chui (2004) [chen2004cat] (record) extended this to 3D cat maps. Shannon's
confusion-and-diffusion principle [shannon1949] is the conceptual root.

Since then, the dominant pattern in the abstracts reviewed is:
* a new or "improved" 1D/2D map (for example [zhou2014new1d], [hua2015slmm], [hua2016lasm],
  [hua2019cosine], [hua2020modular], [chebsine2019], [lu2025sinecheb]),
* followed by scrambling plus substitution or diffusion,
* evaluated with histograms, correlation, entropy, NPCR/UACI and key-sensitivity figures.

The supplied reference paper [sharma2022hsm] (full text) follows this pattern:
* a 2D Hénon-Sine map;
* a 256-bit key split into eight 32-bit words, XOR-combined into sixteen subkeys and mapped to
  initial conditions and parameters with mod 1;
* a one-pixel random border so repeated encryptions differ;
* two rounds of confusion and diffusion with the roles of two chaotic matrices swapped, plus an
  embedded diffusion step between the rounds.

Surveys [zia2022survey] (abstract), [ozkaynak2018] (record) and [satellite2024review] (abstract)
document the size of the field. The satellite-imagery review notes that chaos-based ciphers have
received far less cryptanalysis than standard ciphers.

## 2. Two- and higher-dimensional chaotic systems in cryptography

Two-dimensional maps are usually motivated by wider chaotic parameter ranges and two positive
Lyapunov exponents:
* sine-logistic modulation [hua2015slmm];
* logistic-adjusted sine [hua2016lasm];
* cosine-transform composition of two seed maps [hua2019cosine] (abstract);
* modular chaotification of any 2D map [hua2020modular] (abstract).

Hua et al. explicitly argue that cryptosystems built on maps without complex dynamics have shown
security defects [hua2019cosine].

**Maps closest to ISC.**
* **Chebyshev + Sine.** Zhong et al. (2018) [chebsine2019] (abstract) propose a 2D
  Chebyshev-Sine map with row-shift, column-mixing and CRT-based diffusion. Zhang et al. (2025)
  [lu2025sinecheb] (abstract) propose a 2D improved Sine-Chebyshev map (2D-ISCM) with a
  plaintext-adaptive cellular-automata permutation, an enhanced zigzag permutation and two-way
  diffusion. Neither has an Ikeda stage.
* **Ikeda + Sine.** Hanis (2023) [sineikeda2023] (full text) adds l·sin(πx_n) and l·sin(πy_n) to the
  Ikeda update. It uses harmonic means of trajectories as new seeds and changes parameters at
  every iteration, and it proposes a key generator, not an image cipher. ISC differs structurally:
  it composes Ikeda → sin(ω·) → Chebyshev T₂, so the new state is a bounded nonlinear function of
  the Ikeda output rather than the Ikeda output plus a perturbation.
* **Ikeda in image ciphers.** Sekertekin & Atan (2016) [ikedahenon2017] (abstract) shuffle rows and
  columns with the Ikeda map and change grey levels with the Hénon map. Cao (2013) [cao2013lhi] and
  Hikal & Eid (2020) [hikal2020] use hybrids of several maps (abstract level: the constituent maps
  are not stated in the abstracts). Abduljaleel et al. (2022) [abduljaleel2022tentikeda] use chaos
  for steganography, not image encryption. A dynamical study of the Ikeda map itself is [ikedashrimp2024].
* **Chebyshev in cryptography.** Kocarev & Tasev's Chebyshev public-key scheme [kocarev2003chebpk]
  was broken by Bergamo et al. [bergamo2005] (abstract: plaintext recovered from ciphertext). Huang
  (2012) [huang2012chebyshev] (record) uses a Chebyshev generator for image encryption.

**Result of the closest-work search.** No published map with the ISC recurrence (Ikeda → sin → T₂)
and no ISC-based image cipher was found in the searches performed. This is evidence of absence
within those searches, not proof of absence. A different map alone is not a contribution
(see `research_gap_analysis.md`).

## 3. Permutation and confusion

Permutation alone is insecure:
* Li et al. (2008) [li2008permutation] (record) give a general quantitative cryptanalysis of
  permutation-only multimedia ciphers under plaintext attacks.
* Jolfaei et al. (2016) [jolfaei2016] (abstract) prove that the permutation of any permutation-only
  image cipher is completely recovered by a chosen-plaintext attack, regardless of structure.
* Fridrich's permutation-diffusion scheme is itself attacked through its permutation
  [solak2010fridrich] (abstract: chosen-ciphertext attack revealing the permutation),
  [xie2017fridrich] (record).
* Sort-based index generation can leak: El Hanouti et al. [embedded2019crypt] break a scheme with
  one 3×400 chosen image by exploiting the stability of the sort used to build the permutation.
* A hierarchical permutation scheme was cracked [li2016hierarchical] (record).

Standard ways to turn random integers into a uniform permutation are the Fisher-Yates/Durstenfeld
shuffle [durstenfeld1964], with unbiased bounded-integer sampling [lemire2019] (both abstract).

## 4. Diffusion and plaintext/ciphertext feedback

Forward and backward diffusion with ciphertext feedback is very common, and repeatedly reducible:
* Zhang, Chen & Chen [entropy2022crypt2dhyper] (abstract) show that a cipher's two "complex"
  diffusions reduce to two simple diffusions and a modular addition, recovering an equivalent key by
  CPA and CCA in under two hours for 256×256 images.
* Jiang, Yu & Wang [entropy2023crypt2dhyper] (abstract) show that forward and backward diffusion
  with ciphertext feedback is equivalent to a global diffusion. Because the chaotic sequences are
  independent of the plaintext, equivalent permutation and diffusion keystreams follow from
  adjusting individual pixels of chosen plaintexts.
* Hoang & Nguyen (2026) [hoang2026cryptmethod] (abstract) reduce the encryption equations of
  permutation-diffusion ciphers built on XOR, modular arithmetic and addition to two generalised
  forms and propose a class-level attack framework.
* Li et al. [li2018entropy] (full text) recover the equivalent key of every operation of a
  one-round cipher by a differential attack.

Pixel-adaptive diffusion and fast scrambling for medical images [hua2018medical] (record) and
running-key-with-feedback designs [runningkey2014] (abstract) are examples of feedback used to
create plaintext sensitivity.

## 5. Digital sequence extraction from real-valued trajectories

Converting chaotic real values into bits is a design step of its own:
* Stojanovski & Kocarev [stojanovski2001rng] (abstract) analyse a piecewise-linear chaotic map as a
  Markov information source.
* Bit generators from the logistic map [patidar2009prbg], [wang2019prng] and the Chen system
  [hu2013chenprng] (abstract) rely on statistical testing.
* Özkaynak [ozkaynak2014csprng] (record) uses chaos only as an *additional input* to a
  cryptographically secure generator.
* Arroyo et al. [arroyo2008logistic] (abstract) argue that the logistic map is inadequate for
  cryptography.

The NIST suite explicitly states that statistical testing cannot replace cryptanalysis [sp80022].

**Project finding.** For ISC the extraction method matters greatly. Sign bits (P(x>0) ≈ 0.47) and an
arccos-based byte are strongly biased. Low-order mantissa/fraction bytes (`frac8`, `mantissa8`)
showed no flagged series in any of the 15 official NIST STS 2.1.2 tests on 100 × 10^6 bits. This
is a statistical result about the extracted bits only.

## 6. Finite precision, periodicity, quantisation, reproducibility

* Digital chaos degrades:
  * Li et al. [li2005degradation] quantify dynamical degradation of digital piecewise-linear maps.
  * Li et al. [li2003finiteprecision] (record) show security problems caused by finite-precision
    chaos.
  * Persohn & Povinelli [persohn2012] (record) analyse floating-point-induced periodicity in
    logistic-map PRNGs.
  * Grebogi, Ott & Yorke [grebogi1988] (abstract) show that round-off makes every simulated
    chaotic orbit eventually periodic, with expected period scaling as ε^(-d/2), where d is the
    correlation dimension.
  * Galias [galias2013] (abstract) presents interval methods for rigorous computation.
  * Álvarez & Li's Rules 1 and 2 require the digital implementation and its degradation to be
    specified [alvarez2006].
* Reproducibility across devices fails in practice. Santos et al. [reliability2019devices]
  (full text) generated keys with the cubic map on two IEEE-754-compliant devices; the keys
  differed and decryption failed. The root cause for maps using transcendental functions is that
  IEEE 754 does not require correctly rounded sin/cos. Correctly rounded libraries exist
  [coremath2022], [aanjaneya2022rlibm], and accuracy differs between libraries [gladman2024accuracy].

**Project findings (frozen ISC map).**
* Two evaluations of the same equations (legacy `x**2` with NumPy versus `x*x` with `math`)
  produce trajectories that first differ at iteration 1331.
* Evaluating x² as `x**2` (C `pow`) versus `x*x` changes the last bit.
* *Correction (2026-10-26):* this divergence was earlier attributed to NumPy `sin` versus
  `math.sin`. A controlled check on 80,000 sin/cos arguments from an ISC orbit found NumPy and
  `math` identical on this machine, so the divergence comes from the `pow`-based squares. The same
  check found that 2,593 of 80,000 results (3.2%) differ from correctly rounded values (mpmath,
  200-bit). The platform's sin/cos is therefore not correctly rounded, and another platform's
  library may round differently.
* float32 orbits fall into cycles (legacy orbit: pre-period μ = 278,509, period λ = 24,183).
* For k-bit quantised states the geometric-mean period grows from 115 (k = 8) to 58,017 (k = 16),
  about 1.1 bits of period per bit of precision over 10 orbits per k.
* No float64 cycle was found within 2×10^6 steps for 3 orbits.

The Grebogi scaling suggests an effective d ≈ 2.2 for these quantised orbits. That is an untested
hypothesis from noisy data, not an established property.

## 7. Key derivation and mapping keys to initial conditions

* Álvarez & Li require the key, key space and key-generation algorithm to be defined (Rules 4-8),
  partial key knowledge not to reveal plaintext (Rule 7), and a key space > 2^100 (Rule 13)
  [alvarez2006].
* Yap et al. [yap2016subkey] (record) study the *effective* subkey space of image ciphers that use
  external keys, showing that nominal and effective key space can differ.
* Standard key derivation is HKDF (extract-then-expand) [rfc5869], [krawczyk2010], or KDFs from
  pseudorandom functions [sp800108]; password-derived keys need a memory-hard function such as
  Argon2 [rfc9106]. HMAC [rfc2104] and SHA-2 [fips1804] are the underlying primitives.
* Plaintext-dependent key derivation is common, for example SHA-256 of the plain image
  [zhu2018sha256] (abstract) and MD5 [cao2013lhi] (abstract). It creates a key-management problem,
  because the decryptor must obtain plaintext-derived data. Plaintext-sensitivity mechanisms "can
  be easily cancelled by constructing some special plain-images" [li2019yearreview].
* HKDF with a fresh nonce and domain-separated subkeys has recently been used around image
  ciphers: Ouda (2026) [medical2026chacha] (abstract: HKDF from a master secret and a session nonce
  into encryption, permutation and authentication keys, with ChaCha20 keystreams, chained diffusion
  and HMAC), and Poetro et al. (2026) [jcta2025blockauth] (abstract: X25519 + HKDF into four
  domain-separated subkeys, a DNA-chaos core and block-wise encrypt-then-MAC).

## 8. Known- and chosen-plaintext attacks on image ciphers

* Early examples: Biham's break of the EUROCRYPT'91 chaotic cryptosystem [biham1991] (record), and
  the RCES/RSES break with one or two known or chosen images [li2005rces] (record).
* One known plain/cipher pair gives an equivalent mask key [li2018autoblocking] (full text).
* Equivalent keystreams have been recovered with chosen plaintexts in many other schemes
  [entropy2022crypt2dhyper], [entropy2023crypt2dhyper], [embedded2019crypt], [chen2018crypt1d],
  [zhu2018rttent], [feng2019integrated] (abstract/record).
* The common root cause in the abstracts read is that the keystreams depend only on the key, so
  any encryption under that key reveals reusable information.

## 9. Permutation-only and diffusion cryptanalysis

Covered in sections 3 and 4. The lessons for design are:
1. Permutation alone is never sufficient [jolfaei2016].
2. Multi-pass diffusion built from XOR and modular addition is often algebraically equivalent to a
   single keystream addition [entropy2022crypt2dhyper], [entropy2023crypt2dhyper],
   [hoang2026cryptmethod].
3. Any attack that recovers an equivalent keystream is only as damaging as that keystream's reuse.

## 10. Differential attacks, equivalent keys, weak keys, related keys

* Differential attacks recover equivalent keys of one-round schemes [li2018entropy] and of
  sort-based schemes [embedded2019crypt].
* Weak keys arise from non-chaotic parameter windows and short digital orbits; Hanis cites
  weak-key problems of chaotic maps as motivation [sineikeda2023], and Li et al. found short orbits
  in an attacked cipher [li2018entropy].
* Álvarez & Li (Rule 6) require that nearby keys give entirely different ciphertexts and that
  approaching a key on one parameter reveals nothing [alvarez2006].
* For ISC, finite-precision cycles mean that initial conditions very close together can lead to the
  same eventual cycle. Whether two distinct derived states produce identical keystream prefixes
  must be measured, not assumed.

## 11. Entropy, histogram, correlation, NPCR, UACI and their limits

* Wu, Noonan & Agaian [wu2011npcr] (record and web evidence) derive expected values and critical
  values of NPCR and UACI for ideally encrypted images, so "close to 99.6%/33.4%" can be tested
  rather than eyeballed.
* Wu et al. [wu2013localentropy] (record) propose local Shannon entropy with statistical tests.
* Murillo-Escobar et al. [integral2019] (abstract) propose a 20-point integral analysis checklist.
* Preishuber et al. [preishuber2018] (abstract) construct obviously insecure ciphers that pass these
  tests, and conclude that the tests are necessary but not sufficient.
* The 2018 review lists metric misuse as a central problem [li2019yearreview].
* For a nonce-based cipher, NPCR/UACI between encryptions under *different* nonces measure nothing
  about plaintext diffusion; they are only meaningful under a fixed nonce.

## 12. Statistical randomness testing and SP 800-22

SP 800-22 [sp80022] provides 15 tests and a multi-sequence protocol based on proportion and p-value
uniformity. It states that statistical testing is not a substitute for cryptanalysis.

**Project findings.**
* The official STS 2.1.2 build reproduced 78/80 Appendix B values exactly, and the remaining 2
  within 1e-6.
* Two published worked examples (DFT 2.6.8 and Maurer 2.9.4) are inconsistent with the official
  code or with their own formulas.
* The built-in G-SHA-1 generator is invalid on 64-bit Linux.

These matter for anyone reproducing NIST results.

## 13. Authenticated encryption, nonces, integrity

* Authenticated encryption and generic composition (encrypt-then-MAC is the generically secure
  order): Bellare & Namprempre [bellare2008ae] (record).
* Nonce-based symmetric encryption: Rogaway [rogaway2004nonce] (record).
* Standardised AEADs: AES-GCM [sp80038d] with AES [fips197]; ChaCha20-Poly1305 [rfc8439].
  Nonce-misuse-resistant AES-GCM-SIV [rfc8452].
* Nonce reuse is catastrophic in practice: GCM forgeries against real TLS servers
  [bock2016nonce] (manually verified).
* Chaotic image ciphers rarely provide integrity. Exceptions found are encrypt-then-MAC around a
  chaotic or DNA core [jcta2025blockauth], HMAC with ChaCha20 [medical2026chacha] and
  hash-keyed chaotic designs [farajallah2016auth] (abstract).

## 14. Comparative evaluation and reproducibility standards

* Many evaluations compare against numbers copied from other papers; Preishuber et al. challenge
  both the speed and the security motivation of chaos-based image encryption relative to AES
  [preishuber2018].
* Álvarez & Li Rule 3 asks for acceptable speed without loss of security [alvarez2006].
* Murillo-Escobar et al. propose consistent analysis points [integral2019].
* Some cryptanalysis papers publish their attack code [entropy2022crypt2dhyper]; most design
  papers reviewed here do not state code availability.
* Reproducibility therefore requires shared code, fixed inputs, hashes and, for chaotic ciphers,
  a specified floating-point evaluation (section 6).

## Summary of what the literature establishes

1. New maps are abundant. Their cryptographic value is unproven, and many map-based ciphers have
   been broken, mostly by CPA/KPA equivalent-key attacks that exploit key-only keystreams.
2. The usual metrics (entropy, correlation, NPCR/UACI, NIST on keystream) do not establish security.
3. Digital chaos needs explicit finite-precision and cross-platform specification. Without it,
   decryption can fail on a different machine.
4. Standard tools exist for key derivation, nonces and integrity (HKDF, nonce-based encryption,
   encrypt-then-MAC, AEADs). Combining them with a chaotic core has already been published, so the
   envelope is not a novelty.
5. No ISC-based cipher was found; the Ikeda → sin → T₂ map itself appears only in this project.
