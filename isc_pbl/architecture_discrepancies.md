# Architectural Discrepancies and Design Conflicts with Step 1.1
## Step 1.2 — Phase 1: Existing Implementation Reconciliation

**Document Identification:** `ISC-DISCREPANCIES-STEP1.2-PHASE1-2026-01`  
**Date:** 11 November 2026  
**Auditor:** Independent Scientific Audit Agent (Antigravity Advanced Pairing)  
**Project:** ISC Chaotic Map Image Encryption Research Pipeline

---

## 1. Overview of Identified Discrepancies

A rigorous comparison between the validated **Step 1.1 Sequence Characterization Baseline** and the existing **ISC-IMG v1 Cipher Implementation** (`sine_chebyshev_ikeda_analysis`) reveals five fundamental architectural divergences:

```
+----------------------------------------------------------------------------------------------------+
|                                    ARCHITECTURAL COMPARISON                                        |
+------------------------------+----------------------------------+----------------------------------+
| Feature Dimension            | Step 1.1 Characterization        | Existing Cipher Implementation   |
+------------------------------+----------------------------------+----------------------------------+
| 1. Quantisation / Extraction | Scaled-Floor-Modulo (k=14)       | Float64 Mantissa Bits 8..15      |
|                              | B_n = floor(|x|*10^14) mod 256   | m_byte = (bits(x) >> 8) & 0xFF   |
| 2. Transient Burn-in         | T = 5,000 steps                  | T = 1,024 steps                  |
| 3. Orbit Architecture        | 1 long orbit (N = 1,000,000)     | 256 parallel lanes (4 x 64)      |
| 4. Arithmetic Engine         | Host platform NumPy Float64      | Netlib fdlibm 5.3 (Profile 1)    |
| 5. Plaintext Binding         | N/A (Keystream study only)       | Key + Nonce only (Decoupled)     |
+------------------------------+----------------------------------+----------------------------------+
```

---

## 2. Discrepancy 1: Quantisation vs. Binary Mantissa Bit Extraction

### 2.1 Mathematical Comparison

#### Method A: Scaled-Floor-Modulo Quantisation ($k = 14$)
$$B_n = \lfloor |x_n| \times 10^{14} \rfloor \bmod 256$$
- **Mechanism:** Scales the chaotic coordinate $x_n \in [-1, 1]$ by the decimal factor $10^{14}$, takes the floor integer, and extracts the least-significant 8 bits modulo 256.
- **Precision Margin:** Since $|x_n| \le 1.0$, the scaled quantity $|x_n| \times 10^{14} \le 10^{14} \approx 2^{46.51}$. This consumes $46.5$ bits of the 53-bit IEEE 754 significand, leaving a safety buffer of $6.5$ bits ($2^{6.5} \approx 90$ ULPs) before roundoff distortion occurs.
- **Step 1.1 Empirical Evidence:** Exhaustively verified in Step 1.1 across $N = 10^6$ samples and $M = 100$ independent sequences:
  - Chi-Square uniformity: $\chi^2 = 234.07, p = 0.822$ ($X$); $\chi^2 = 212.49, p = 0.975$ ($Y$).
  - Full-sequence byte autocorrelation: $|\rho| \le 0.0028$ (strictly within Bonferroni white-noise bounds).
  - Multi-sequence NIST pass rate: **$98.8\%$ ($X$) and $99.0\%$ ($Y$)**.

#### Method B: Float64 Mantissa Bit Extraction (`mantissa8`)
$$\text{bits} = \text{view\_uint64}(x_n)$$
$$\text{mantissa} = \text{bits} \ \& \ ((1 \ll 52) - 1)$$
$$m\_byte(x_n) = (\text{mantissa} \gg 8) \ \& \ 0\text{xFF}$$
- **Mechanism:** Interprets the Float64 number directly as a 64-bit unsigned integer. Discards the sign bit (bit 63) and 11-bit exponent (bits 52..62). Masks the 52-bit mantissa, discards the lowest 8 bits (bits 0..7), and extracts bits 8 through 15 (8 bits).
- **Physical Meaning:** In IEEE 754 Float64, normalized numbers are represented as $(-1)^s \times 2^{e - 1023} \times (1 + \sum_{i=1}^{52} b_{52-i} 2^{-i})$. Extracting bits 8..15 extracts binary fractional digits corresponding to place values $2^{-37}$ through $2^{-44}$ relative to the normalized significand.

### 2.2 Why Step 1.1 Results Cannot Be Transferred to Method B
1. **Mathematical Inequivalence:** Base-10 scaling modulo 256 and base-2 bit-slicing are completely different projection operators. There is no homomorphic mapping between $\lfloor x \times 10^{14} \rfloor \bmod 256$ and $(\text{bits}(x) \gg 8) \bmod 256$.
2. **Distributional Differences:** In binary mantissa extraction, the value of the extracted byte is conditioned on the floating-point exponent $e$. As $x_n$ fluctuates between $10^{-3}$ and $1.0$, the exponent shifts, causing bits 8..15 to correspond to varying absolute decimal precisions. In contrast, $10^{14}$ maintains a constant absolute scaling across the entire domain.
3. **Scientific Invalidation:** **It is scientifically invalid to cite the Step 1.1 $k = 14$ characterization report as justification for the security or uniformity of the existing `isc_cipher` implementation.** If `isc_cipher` retains `mantissa8`, it requires an independent multi-sequence NIST SP 800-22 and Chi-Square evaluation.

---

## 3. Discrepancy 2: Transient Burn-in Iteration Count

- **Step 1.1 Protocol:** 5,000 transient iterations discarded before retaining samples.
- **Existing Cipher (`generator.py:BURN_IN`):** Exactly 1,024 transient iterations discarded per lane.
- **Technical Analysis:**
  - The largest Lyapunov exponent of the frozen ISC map is $\lambda_1 \approx 2.73\text{ nats/iteration}$.
  - Under this divergence rate, an initial perturbation of $10^{-16}$ expands by a factor of $e^{\lambda_1 \times T}$. For $T = 1,024$:
    $$e^{2.73 \times 1024} = e^{2795} \approx 10^{1214} \gg 10^{16}$$
    The state is thoroughly decorrelated from the initial seed $(x_0, y_0)$ within $\approx 20$ iterations.
  - However, in Step 1.1, $T = 5,000$ was mandated to ensure complete convergence to the invariant measure and purge any initial transient density fluctuations.
  - Reducing $T$ from 5,000 to 1,024 was an intentional engineering trade-off in `isc_cipher` to reduce startup latency ($256 \text{ lanes} \times 1,024 \text{ steps} \approx 1.36\text{s}$ vs $\approx 6.6\text{s}$ at $T = 5,000$).
  - **Verdict:** $T = 1,024$ is cryptographically sufficient to destroy seed correlations, but the statistical properties of post-1024-step streams must be empirically confirmed.

---

## 4. Discrepancy 3: Orbit Topology and Parallel Lane Interleaving

- **Step 1.1 Architecture:**
  - Single continuous trajectory of $N = 1,000,000$ iterations.
  - Keystream is strictly sequential from one initial state $(x_0, y_0) = (0.1, 0.1)$.
- **Existing Cipher Architecture:**
  - 256 independent lanes distributed across 4 functional streams (`sbox`, `perm`, `fwd`, `bwd`), with 64 lanes each.
  - Keystream within each stream is generated by **interleaving** 64 lanes:
    $$\text{Round } j: [M(x_0^{(j)}), M(y_0^{(j)}), M(x_1^{(j)}), M(y_1^{(j)}), \dots, M(x_{63}^{(j)}), M(y_{63}^{(j)})]$$
  - Each round emits $64 \times 2 = 128$ bytes.
- **Implications:**
  - In `isc_cipher`, consecutive bytes in the diffusion stream do NOT come from consecutive iterations of the same map! Byte 0 comes from Lane 0 ($x$), Byte 1 from Lane 0 ($y$), Byte 2 from Lane 1 ($x$), and so on. Consecutive steps of the same lane are separated by 128 bytes.
  - This interleaving breaks temporal dynamical memory ($\rho(1) \approx 0$ between adjacent bytes is guaranteed by lane independence rather than map mixing alone).
  - However, it introduces the assumption that the 64 parallel lanes remain mutually independent. If any two lanes collide or enter identical orbits (state merging), keystream repetition could occur. (Evaluated in Gate A Attack A6).

---

## 5. Discrepancy 4: Arithmetic Portability (Host LIBM vs FDLIBM 5.3)

- **Step 1.1:** Evaluated using Python/NumPy default trigonometric functions, which delegate to the underlying host C runtime math library (MSVCRT / UCRT on Windows, glibc on Linux).
- **Existing Cipher:** Implements a strict dual-profile system:
  - **Profile 1 (Normative, F64-FDLIBM):** Embeds Sun Microsystems Netlib fdlibm 5.3 in pure Python (`fdlibm_ref.py`) and vectorized NumPy (`fdlibm_np.py`). Evaluates sine/cosine using exact bit-for-bit polynomial coefficients and range reduction.
  - **Profile 2 (Comparison, F64-HOSTLIBM):** Uses host platform NumPy.
- **Implications:**
  - Host libm implementations are NOT bit-exact across platforms. A Float64 `sin(x)` on Windows MSVC can differ from Linux glibc by 1 ULP.
  - In a chaotic map with $\lambda_1 \approx 2.73$, a 1-ULP difference at step 0 causes complete divergence in $\approx 25$ iterations ($e^{2.73 \times 25} \approx 2^{98}$).
  - Without Profile 1, a ciphertext encrypted on Windows CANNOT be decrypted on Linux or macOS.
  - Profile 1 solves this cross-platform divergence issue, as verified in Gate R (bit-exact match between Windows and Linux WSL).

---

## 6. Discrepancy 5: Plaintext Dependency and Key Agility

- **Step 1.1 Surveyed Context:** 9 of 15 surveyed chaotic image ciphers hash the plaintext image ($\text{SHA-256}(P)$) and inject the hash into the map parameters or initial states to achieve high NPCR/UACI.
- **Existing Cipher:** The keystream is **completely decoupled from the plaintext image**:
  $$\text{Keystream} = F(K, N, \text{dims})$$
  The plain image $P$ is never hashed to derive keystream material.
- **Why `isc_cipher` Made This Decision:**
  1. *Receiver Side-Information Problem:* If the keystream depends on $\text{SHA-256}(P)$, how does the receiver decrypt? The receiver does not have $P$ yet. Sending $\text{SHA-256}(P)$ in the clear allows attackers to verify plaintext guesses.
  2. *Chosen-Ciphertext Attack (CCA) Vulnerability:* Plaintext-dependent chaotic ciphers frequently fail under CCA because modifying the ciphertext disrupts the decrypted plaintext and desynchronizes decryption.
  3. *Standard Cryptographic Practice:* Real-world authenticated ciphers (AES-GCM, ChaCha20-Poly1305) always derive keystreams from $(K, \text{Nonce})$. Plaintext sensitivity is achieved through **diffusion passes**, not key scheduling.
- **Consequence:** Under a fixed nonce, the cipher is deterministic. CPA resistance is achieved strictly through the probabilistic uniqueness of the 16-byte nonce $N \leftarrow \text{os.urandom}(16)$ and authenticated Encrypt-then-MAC packaging.

---

## 7. Reconciliation Recommendations for Step 1.2

To align the implementation with the research goals of Step 1.2:
1. **Option A (Reconcile Cipher to Step 1.1):** Replace `mantissa_byte(v)` in `isc_cipher/generator.py` with `frac_byte(v)` ($k = 14$ scaled-floor-modulo).
   - *Advantage:* Directly inherits the rigorous Step 1.1 empirical validation (Chi-Square, multi-sequence NIST, Miller-Madow mutual information).
   - *Requirement:* Must update KAT vectors and self-test constants in `isc_cipher_kat`.
2. **Option B (Retain Mantissa Extraction in Cipher):** Keep `mantissa_byte(v)` as Profile 1, but execute an equivalent Step 1.1 characterization suite specifically for the `mantissa8` extractor to provide publication-grade statistical evidence.
3. **Maintain Nonce-Based Architecture:** Retain the decoupled Key + Nonce architecture with Encrypt-then-MAC. Do NOT inject plain image hashes into the chaotic key schedule.

