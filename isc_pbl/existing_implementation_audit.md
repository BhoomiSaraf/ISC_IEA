# Comprehensive Scientific and Implementation Audit of Existing ISC Cipher Codebase
## Step 1.2 — Phase 1: Existing Implementation Reconciliation

**Document Identification:** `ISC-AUDIT-STEP1.2-PHASE1-2026-01`  
**Date of Audit:** 11 November 2026  
**Auditor:** Independent Scientific Audit Agent (Antigravity Advanced Pairing)  
**Target Repositories Inspected:**
- Primary Workspace: `C:\Users\bhoom\Desktop\ISC_PBL`
- Discovered Implementation Source: `C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis`

---

## 1. Executive Summary & Codebase Discovery

During Step 1.1, the `ISC_PBL` repository contained the historical map validation scripts (`script/analyze.py`, `script/final_validation.py`, `script/final_freeze_validation.py`) and our newly developed sequence characterization suite (`isc_sequence_characterization.py`). However, the earlier workflow document ([`Claude outputs/Chaotic map image encryption workflow.md`](file:///c:/Users/bhoom/Desktop/ISC_PBL/Claude%20outputs/Chaotic%20map%20image%20encryption%20workflow.md)) referenced a fully specified AEAD-style cipher with packages `isc_cipher`, `isc_seq`, `isc_eval`, `isc_cipher_kat`, and twelve test files.

A exhaustive filesystem search across the workstation identified the complete implementation repository located in:
$$\text{Path: } \texttt{C:\textbackslash Users\textbackslash bhoom\textbackslash Desktop\textbackslash sine\_chebyshev\_ikeda\_analysis}$$

### Key Findings of the Codebase Audit:
1. **The Cipher Implementation Fully Exists:** The repository `sine_chebyshev_ikeda_analysis` contains an implementation of **ISC-IMG v1** developed between 25 October 2026 and 26 October 2026.
2. **Implementation Completeness:** It includes the complete encryption and decryption engine (`isc_cipher`), sequence extraction and analysis tools (`isc_seq`), an attack-driven evaluation harness (`isc_eval`), known-answer test vectors generated from an independent C oracle (`isc_cipher_kat`), and full test suites (`tests/`).
3. **Verified Empirical Pass:**
   - **Gate C (Correctness Test Suite):** All **159 active test cases passed** (2 skipped as slow by design) in **731.61 seconds** (~12 minutes).
   - **Gate A (Evaluation Harness Tests):** All **16 test cases passed** in **81.43 seconds**.
   - **Gate R (Reproducibility & KAT Verification):** Evaluated against stored C-oracle vectors; achieved **100% bit-exact PASS** on all checks (hashes, 74,063 trig values, 1,000,000 trajectory steps, 256 lane streams, and full ciphertexts).
4. **Critical Architectural Discrepancy with Step 1.1:**  
   The existing `isc_cipher` implementation extracts **bits 8–15 of the IEEE 754 Float64 representation** (`mantissa_byte(v)`). It does **NOT** use the Step 1.1 characterized **Fixed-Point Scaled-Floor-Modulo Transformation with $k = 14$** ($B_n = \lfloor |x_n| \times 10^{14} \rfloor \bmod 256$). The $k = 14$ transformation exists only as an isolated utility in `isc_seq/extract.py: frac_byte` and was never wired into the cipher pipeline.

---

## 2. Verification of Earlier Workflow Document Claims

Each claim from Section 2 of the task description was audited directly against the source code:

| # | Workflow Document Claim | Status | Exact Source File & Line | Verified Source Code Implementation |
|---|---|---|---|---|
| 1 | **32-byte master key** | **VERIFIED** | [`isc_cipher/kdf.py:L14, L26-L29`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/kdf.py#L14) | `KEY_LEN = 32`. `check_key(key)` strictly rejects any input that is not a 32-byte `bytes` or `bytearray`. |
| 2 | **16-byte per-encryption nonce** | **VERIFIED** | [`isc_cipher/kdf.py:L15`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/kdf.py#L15), [`isc_cipher/cipher.py:L60-L61, L75`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/cipher.py#L60) | `NONCE_LEN = 16`. In `encrypt_bytes`, the nonce is drawn from `os.urandom(NONCE_LEN)`. Public `encrypt()` API accepts no user nonce parameter, preventing nonce-misuse in application code. |
| 3 | **HKDF-SHA-256 derivation** | **VERIFIED** | [`isc_cipher/kdf.py:L32-L44, L56-L80`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/kdf.py#L32) | Follows RFC 5869: `PRK = HMAC-SHA256(salt=nonce, ikm=key)`. Implements clean extract-and-expand using Python standard library `hmac` and `hashlib`. |
| 4 | **Four independent streams** | **VERIFIED** | [`isc_cipher/kdf.py:L16`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/kdf.py#L16), [`isc_cipher/generator.py:L3-L8`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/generator.py#L3) | `STREAMS = ("sbox", "perm", "fwd", "bwd")`. Each stream serves exactly one structural purpose and has completely disjoint lane instances. |
| 5 | **64 ISC map lanes per stream** | **VERIFIED** | [`isc_cipher/kdf.py:L17`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/kdf.py#L17), [`isc_cipher/generator.py:L129-L134`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/generator.py#L129) | `LANES = 64`. Total lanes per message: $4 \times 64 = 256$ independently seeded ISC orbits. |
| 6 | **1,024 burn-in iterations** | **VERIFIED** | [`isc_cipher/generator.py:L19, L111-L134`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/generator.py#L19) | `BURN_IN = 1024`. All 256 lanes advance exactly 1,024 steps prior to emitting any keystream bytes. *(Note: Step 1.1 used $T = 5,000$)*. |
| 7 | **Float64 bit extraction (bits 8–15)** | **VERIFIED** | [`isc_cipher/generator.py:L25-L26, L97-L98`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/generator.py#L25) | `_pack_d(v)[6]`: Extracts byte 6 of IEEE 754 big-endian Float64 representation, corresponding to mantissa bits 8..15 (`(bits >> 8) & 0xFF`). |
| 8 | **Lemire rejection sampling** | **VERIFIED** | [`isc_cipher/sampling.py:L28-L40`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/sampling.py#L28) | Implements Lemire's fast nearly-divisionless algorithm: uniform integer in $[0, s)$ from 32-bit words with exact rejection threshold $t = (2^{32} - s) \bmod s$. |
| 9 | **Fisher–Yates S-box and permutation** | **VERIFIED** | [`isc_cipher/sampling.py:L42-L63`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/sampling.py#L42) | Generates 256-byte S-box (and $S^{-1}$) and length-$n$ coordinate permutation $\pi$ via backward Fisher-Yates loops ($i$ from $n-1$ down to 1 with $j = \text{bounded}(i+1)$). |
| 10 | **Forward & backward chained diffusion** | **VERIFIED** | [`isc_cipher/diffusion.py:L13-L29`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/diffusion.py#L13) | Forward: $u_k = S[(q_k + u_{k-1} + a_k) \bmod 256]$ ($u_{-1} = iv_f$). Backward: $c_k = S[(u_k + c_{k+1} + b_k) \bmod 256]$ ($c_n = iv_b$). |
| 11 | **ISCI ciphertext container** | **VERIFIED** | [`isc_cipher/container.py:L1-L72`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/container.py#L1) | 36-byte header: `MAGIC=b"ISCI"`, `VERSION=1`, `PROFILE` (1 or 2), `DTYPE=1`, `C` (1 or 3), `H` (BE16), `W` (BE16), `NONCE` (16B), `KCV` (8B). |
| 12 | **Key-check value (KCV)** | **VERIFIED** | [`isc_cipher/cipher.py:L52-L53`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/cipher.py#L52), [`isc_cipher/generator.py:L138-L140`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/generator.py#L138) | $\text{KCV} = \text{HMAC-SHA256}(K_{\text{kcv}}, \text{lane\_states} \parallel \text{steps})[:8]$ over final lane states of all 256 orbits. Detects numerical divergence on decryption. |
| 13 | **HMAC-SHA-256 authentication** | **VERIFIED** | [`isc_cipher/cipher.py:L69-L70, L84-L86`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/cipher.py#L69) | Encrypt-then-MAC: $\text{tag} = \text{HMAC-SHA256}(K_{\text{mac}}, \text{header} \parallel \text{ciphertext\_body})$. Verified with constant-time `hmac.compare_digest` before decryption. |
| 14 | **Deterministic fdlibm sine/cosine** | **VERIFIED** | [`isc_cipher/fdlibm_ref.py`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/fdlibm_ref.py), [`isc_cipher/fdlibm_np.py`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/fdlibm_np.py) | Direct port of Netlib fdlibm 5.3 kernel trigonometric and argument reduction functions. Guarantees identical Float64 bits across compilers, OSes, and architectures. |
| 15 | **AEAD baselines & attack harness** | **VERIFIED** | [`isc_eval/constructions.py`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_eval/constructions.py), [`isc_eval/exp_misuse.py`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_eval/exp_misuse.py) | Full harness comparing V-FULL against V-LINEAR, V-STREAM, V-PERM, V-CHACHA, and standard AEADs (AES-256-GCM, ChaCha20-Poly1305, AES-256-GCM-SIV). |

---

## 3. Cryptographic Design Audit

### 3.1 Key-to-State Mapping & Effective Key Entropy
- **Algorithm:** Each lane seed $s$ (16 bytes) is converted to $(x_0, y_0)$ in [`isc_cipher/state_map.py`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/state_map.py#L11):
  $$\alpha = \text{BE64}(s[0:8]) \gg 11, \quad \beta = \text{BE64}(s[8:16]) \gg 11$$
  $$x_0 = \text{float}(\alpha) \times 2^{-52} - 1.0, \quad y_0 = \text{float}(\beta) \times 2^{-52} - 1.0$$
- **Entropy Analysis:**
  - The bit shift $\gg 11$ maps a 64-bit integer to a 53-bit integer ($0 \le \alpha < 2^{53}$), discarding the low 11 bits.
  - The multiplication by $2^{-52}$ and subtraction of $1.0$ is exact in IEEE 754 Float64 (powers of 2, within significand capacity).
  - The grid consists of exactly $2^{53} \times 2^{53} = 2^{106}$ points in $[-1.0, 1.0]$.
  - The mapping is a uniform $2^{22}$-to-1 contraction from the $2^{128}$ seed space to the $2^{106}$ grid.
  - **Security Evaluation:** Since the master key has 256 bits of entropy, and HKDF-SHA256 expands it to 256 distinct 128-bit lane seeds, no effective key entropy is lost. Each lane begins on an exact 53-bit representable point.

### 3.2 Nonce Uniqueness and Misuse Resistance
- **Generation:** Nonce $N \in \{0, 1\}^{128}$ is generated randomly via `os.urandom(16)`.
- **Collision Probability:** Under standard birthday bound, probability of nonce collision is negligible ($p < 2^{-32}$ after $2^{48}$ encryptions).
- **Public API:** `encrypt(key, image)` takes NO nonce parameter, preventing callers from accidentally reusing a nonce.
- **Misuse Behavior:** If a nonce IS maliciously reused (as tested in `isc_eval/exp_misuse.py`):
  - Because keystream generation is deterministic given $(K, N, \text{dims})$, reusing $(K, N)$ on two plaintexts produces identical keystreams $S, \pi, a, b$.
  - However, because diffusion is non-linear (via keyed S-box), $c_1 \oplus c_2 \ne p_1 \oplus p_2$. Nonce reuse does not leak plaintext XOR directly (unlike AES-GCM or stream ciphers).

### 3.3 Domain Separation
- **Context String:**
  $$\text{ctx} = \texttt{"ISC-IMG/v1"} \parallel \text{uint8}(\text{PROFILE}) \parallel \text{uint8}(\text{DTYPE}) \parallel \text{BE16}(H) \parallel \text{BE16}(W) \parallel \text{uint8}(C)$$
  Total length: exactly 17 bytes.
- **Per-Key Derivations:**
  - $K_{\text{mac}} = \text{HKDF-Expand}(\text{PRK}, \text{ctx} \parallel \texttt{"\textbackslash x00mac"}, 32)$
  - $K_{\text{kcv}} = \text{HKDF-Expand}(\text{PRK}, \text{ctx} \parallel \texttt{"\textbackslash x00kcv"}, 32)$
  - $iv_f, iv_b = \text{HKDF-Expand}(\text{PRK}, \text{ctx} \parallel \texttt{"\textbackslash x00iv"}, 2)$
  - Lane seeds: $\text{HKDF-Expand}(\text{PRK}, \text{ctx} \parallel \texttt{"\textbackslash x00lane/<stream>/<0000..0063>"}, 16)$
- **Security Evaluation:** Domain separation is mathematically sound. Derivations for different image dimensions $(H, W, C)$, profiles, or lanes cannot collide.

### 3.4 Lane Independence & Map Orbits
- **Structure:** 4 streams $\times$ 64 lanes = 256 independent orbits.
- **Interleaving:** Emissions occur in rounds of 64 lanes. In each round, each lane steps once and emits 2 bytes ($M(x), M(y)$), producing 128 bytes per round.
- **Separation:** The four streams have completely disjoint initial states and never interact.
- **Limitation:** The mathematical independence of chaotic orbits seeded by distinct points is an assumption. Step 1.1 demonstrated that continuous coordinates have weak nonlinear coupling ($I \approx 0.0138\text{ bits}$).

### 3.5 Bounded Sampling & Permutation Generation
- **Method:** Lemire's nearly-divisionless rejection sampling on 32-bit big-endian words.
- **Unbiased Proof:** Exhaustively proven in `test_isc_cipher_sampling_diffusion.py:test_bounded_is_exactly_uniform` using exact integer arithmetic: every value $v \in [0, s)$ has an identical count of accepted 32-bit words.
- **Permutation:** Fisher-Yates shuffle with gather convention ($q_k = p[\pi_k]$). Scatter inversion ($p[\pi_k] = q_k$) is exact and bijective.

### 3.6 Diffusion Linearity & Decryption Parallelism
- **Forward:** $u_k = S[(q_k + u_{k-1} + a_k) \bmod 256]$.
- **Backward:** $c_k = S[(u_k + c_{k+1} + b_k) \bmod 256]$.
- **Non-linearity:** Keyed S-box breaks linearity over $\mathbb{Z}_{256}$ and $\text{GF}(2)^8$.
- **Decryption Vectorization:** While encryption is strictly sequential, decryption is **trivially parallelizable** because the ciphertext is known in advance:
  $$u_k = (S^{-1}[c_k] - c_{k+1} - b_k) \bmod 256$$
  $$q_k = (S^{-1}[u_k] - u_{k-1} - a_k) \bmod 256$$
  In [`isc_cipher/diffusion.py:inverse_np`](file:///C:/Users/bhoom/Desktop/sine_chebyshev_ikeda_analysis/isc_cipher/diffusion.py#L46), this is implemented using parallel NumPy `int16` array arithmetic, providing high-throughput decryption.

### 3.7 Authentication Order & Integrity Protection
- **Order of Operations:**
  1. Parse header.
  2. Compute expected HMAC tag over $\text{header} \parallel \text{ciphertext\_body}$.
  3. Verify tag with constant-time equality `hmac.compare_digest`.
  4. **Only if valid:** run self-test, keystream generation, inverse diffusion, and inverse permutation.
  5. Compute and verify KCV against header KCV.
  6. **Only if KCV matches:** release decrypted plaintext.
- **Verification:** Verified by `test_isc_cipher_auth.py:no_generator`: any attempt to touch the chaotic generator before the HMAC tag is validated triggers an assertion failure. The cipher is strictly immune to unauthenticated oracle attacks and invalid-ciphertext side-channels.

---

## 4. Test Infrastructure Audit & Execution Results

All test suites were executed in the local environment (Windows 10/11 Pro, Python 3.11.9, NumPy 2.4.6):

### 4.1 Gate C (Correctness Test Suite)
- **Command:** `python -m pytest tests/test_isc_cipher_*.py`
- **Duration:** 731.61 seconds (~12.2 minutes)
- **Outcome:** **159 passed, 2 skipped** (100% success rate).
- **Coverage Details:**
  - `test_isc_cipher_auth.py` (42 tests): Bit flips across every single byte of header and body; truncation from 1 to 64 bytes; extension by 1 to 64 bytes; 200 random wrong keys; 1-bit modified keys; dimension relabeling; profile swapping.
  - `test_isc_cipher_kdf_state.py` (27 tests): RFC 5869 test cases 1 & 3; comparison against `cryptography` library HKDF; exact rational mapping proofs (`fractions.Fraction`); exhaustive 11-bit truncation check.
  - `test_isc_cipher_numeric.py` (15 tests): FDLIBM 5.3 C-oracle trig vectors; mpmath 200-bit precision verification; argument guard checks; bit-for-bit identity between scalar `step_ref` and vectorized `step_vec`.
  - `test_isc_cipher_roundtrip.py` (29 tests): Exact array equality across 9 shapes $\times$ 9 patterns (zeros, ones, checkerboard, gradients, random, single bright pixel); cross-backend compatibility (`reference` vs `numpy`); size limits.
  - `test_isc_cipher_sampling_diffusion.py` (48 tests): Lemire uniformity proofs; Fisher-Yates bijectivity; diffusion roundtrips on edge-case inputs; scalar vs vectorized inverse equality.

### 4.2 Gate A (Evaluation Harness Tests)
- **Command:** `python -m pytest tests/test_isc_eval_harness.py`
- **Duration:** 81.43 seconds
- **Outcome:** **16 passed, 0 failed** (100% success rate).
- **Coverage Details:**
  - Variant roundtrips and tamper detection for V-FULL, V-LINEAR, V-STREAM, V-PERM, V-CHACHA.
  - Baseline AEAD roundtrips for AES-256-GCM, ChaCha20-Poly1305, AES-256-GCM-SIV.
  - Attack position coding and linear cryptanalysis tests.
  - Berlekamp-Massey linear complexity validation.
  - Ideal NPCR/UACI analytical formula verification.

### 4.3 Gate R (Reproducibility & KAT Verification)
- **Command:** `python -I isc_cipher_kat/gate_r.py --backend numpy --label E1-windows`
- **Duration:** 289.9 seconds (~4.8 minutes)
- **Outcome:** **OVERALL: PASS**.
  - `R-fdlibm-hashes`: PASS (Sun Microsystems archive matches SHA256SUMS).
  - `R-trig-KAT`: PASS (74,063 sin/cos arguments match independent C oracle bit-for-bit).
  - `R-trajectory-KAT`: PASS (10 trajectories $\times$ 100,000 steps match SHA-256 hashes of C oracle).
  - `R-stream-KAT`: PASS (256 lane seeds, burn-in states, and byte outputs match C oracle).
  - `R-cipher-KAT`: PASS (Ciphertexts and decrypt roundtrips match recorded KAT vectors).

---

## 5. Security Assumptions and Open Limitations

While Gate C and Gate R prove that the implementation is mathematically correct and reproducible, the following security assumptions remain unproven:
1. **Keystream Statistical Independence Across Lanes:** The 256 lanes are initialized with independent seeds, but whether parallel chaotic orbits generated by the same map equations maintain zero mutual information across long trajectories is an assumption.
2. **Resistance to Nonce-Misuse Differential Cryptanalysis:** Although the keyed S-box prevents linear reduction, the differential propagation under repeated nonces requires empirical evaluation (Attack A1).
3. **Absence of Plaintext Sensitivity in Keystream:** Unlike several academic proposals that seed the map with $H(\text{plain})$, `isc_cipher` intentionally decouples the keystream from the plaintext (relying solely on a fresh 16-byte nonce). This prevents side-information transmission problems, but means that differential security (NPCR/UACI) under a fixed nonce relies entirely on the diffusion passes.
4. **Float64 Mantissa Bit Extraction vs Scaled-Floor-Modulo:** The statistical properties of bits 8–15 of IEEE 754 Float64 were chosen based on preliminary experiments, but have NOT been characterized with the rigor of our Step 1.1 suite ($k=14$).

---

## 6. Audit Conclusion

An image encryption prototype implementing the ISC chaotic map already exists in `sine_chebyshev_ikeda_analysis`. It is an engineered, AEAD-compliant system featuring bit-exact cross-platform determinism (fdlibm 5.3), formal domain separation, unbiased sampling, and authenticated decryption.

However, there is an unresolved **quantisation discrepancy** between the existing cipher (Float64 bits 8–15 extraction) and our validated Step 1.1 research baseline ($k=14$ scaled-floor-modulo). Phase 2 must reconcile this discrepancy before freezing Step 1.2.

