# Phase 5 — Verified Mathematical Specification Package

Each equation below is tagged by type (IMPLEMENTATION = governs actual code behavior; ANALYSIS = used to compute an experimental metric; THEORETICAL = reference/comparison value only) and by verification status.

## 1. ISC map recurrence (THEORETICAL / background — characterizes the map, not the cipher's per-message generator directly)
$$t_n = c - \frac{d}{1+x_n^2+y_n^2}, \quad X_n = 1+a(x_n\cos t_n - y_n\sin t_n), \quad Y_n = a(x_n\sin t_n + y_n\cos t_n)$$
$$x_{n+1} = 2\sin^2(\omega X_n) - 1, \quad y_{n+1} = 2\sin^2(\omega Y_n) - 1$$
Source: `ISC_PBL/isc_sequence_characterization.py`; re-expressed identically in `isc_cipher/isc_step.py` (params renamed A,C,D,W). **CODE-VERIFIED** (both repos checked directly).

## 2. Parameter definitions (IMPLEMENTATION)
$a=0.9,\ c=0.4,\ d=6.0,\ \omega=10.0$ (Repo A naming) ≡ $A=0.9,\ C=0.4,\ D=6.0,\ W=10.0$ (Repo B naming). **CODE-VERIFIED.**

## 3. Extraction profile 1 — `mantissa8_v1` (IMPLEMENTATION)
$m\_byte(v) = \text{struct.pack('>d', v)}[6]$ — byte 6 of the IEEE-754 big-endian encoding. Source: `isc_cipher/generator.py:39-40`. **CODE-VERIFIED.**

## 4. Extraction profile 2 — `k14_scaled_modulo_v1` (IMPLEMENTATION)
$B_n = \lfloor |x_n|\cdot 10^{14}\rfloor \bmod 256$. Source: `isc_cipher/generator.py:43-51`; identical formula in `ISC_PBL/isc_sequence_characterization.py` for Step 1.1's k=14 candidate. **CODE-VERIFIED (both repos).**

## 5. HKDF derivation structure (IMPLEMENTATION)
$PRK = \text{HMAC-SHA256}(salt=nonce, key=master\_key)$ (extract); $OKM = \text{HKDF-Expand}(PRK, info, L)$ (expand), RFC 5869. Source: `isc_cipher/kdf.py:32-44`. **CODE-VERIFIED**; expand step **TEST-VERIFIED** against RFC 5869 vectors and the `cryptography` library (Phase 4A).

## 6. Lane initialization (IMPLEMENTATION)
16-byte HKDF-derived seed → initial state $(x_0,y_0)\in[-1,1)^2$ on a $2^{106}$-point grid. Source: `isc_cipher/state_map.py`. **TEST-VERIFIED** (exact rational-arithmetic cross-check, Phase 4A).

## 7. Generator advancement (IMPLEMENTATION)
One ISC-map step per call; emits $B(x), B(y)$ per lane per step, lane-minor then lane-major ordering. Source: `isc_cipher/isc_step.py`, `generator.py`. **TEST-VERIFIED** (stream byte-order test, Phase 4A).

## 8. Burn-in (IMPLEMENTATION)
1,024 iterations discarded per lane by default (`BURN_IN=1024`), distinct from Step 1.1's 5,000-iteration transient (see cross-phase audit). Source: `isc_cipher/generator.py:29`. **CODE-VERIFIED.**

## 9. Random-index sampling — Lemire bounded (IMPLEMENTATION)
Standard Lemire rejection-sampling construction over extracted bytes. Source: `isc_cipher/sampling.py`. **DATA-VERIFIED** exact-enumeration unbiasedness check at tested moduli (Phase 4D).

## 10. Fisher–Yates construction (IMPLEMENTATION)
Standard algorithm, $i=n-1\ldots1,\ j=\text{Bounded}(i+1)$, swap. Source: `isc_cipher/sampling.py`. **TEST-VERIFIED** bijectivity + reference-implementation match (Phase 4A); re-confirmed Phase 4D.

## 11. S-box construction (IMPLEMENTATION)
Fisher–Yates over $[0,255]$ seeded by the `sbox` stream. Source: `isc_cipher/sampling.py:42-52`. **CODE-VERIFIED.**

## 12. Permutation operation (IMPLEMENTATION)
$q_k = p_{\pi(k)}$ (gather). Source: `isc_cipher/sampling.py:65-75`. **TEST-VERIFIED** inverse correctness (Phase 4A).

## 13. Forward diffusion (IMPLEMENTATION)
$u_k = S[(q_k+u_{k-1}+a_k)\bmod256],\ u_{-1}=iv_f$. Source: `isc_cipher/diffusion.py:13-20`. **CODE-VERIFIED.**

## 14. Backward diffusion (IMPLEMENTATION)
$c_k = S[(u_k+c_{k+1}+b_k)\bmod256],\ c_N=iv_b$. Source: `isc_cipher/diffusion.py:22-29`. **CODE-VERIFIED.**

## 15. Inverse backward diffusion (IMPLEMENTATION)
$u_k = (S^{-1}[c_k]-c_{k+1}-b_k)\bmod256$. Source: `isc_cipher/diffusion.py:32-43`. **TEST-VERIFIED** exact inverse on random/extreme inputs (Phase 4A).

## 16. Inverse forward diffusion (IMPLEMENTATION)
$q_k = (S^{-1}[u_k]-u_{k-1}-a_k)\bmod256$. Source: `isc_cipher/diffusion.py:46-57`. **TEST-VERIFIED** (same artifact as #15).

## 17. Inverse permutation (IMPLEMENTATION)
$p_{\pi(k)} = q_k$ (scatter). Source: `isc_cipher/sampling.py`. **TEST-VERIFIED.**

## 18. Authentication computation (IMPLEMENTATION)
$tag = \text{HMAC-SHA256}(k_{mac}, header\,\|\,body)$, verified via constant-time compare before any decryption work. Source: `isc_cipher/cipher.py:101,127-136`. **TEST-VERIFIED** (monkeypatch-forced-failure test, Phase 4A; re-confirmed Phase 4D).

## 19. Image byte serialization/reconstruction (IMPLEMENTATION)
`np.ascontiguousarray(image).tobytes()` / `.reshape(h,w,c)`. Source: `isc_cipher/cipher.py:148-175`. **CODE-VERIFIED.**

## 20. Shannon entropy (ANALYSIS)
$H(X) = -\sum_{i=0}^{255} p_i \log_2 p_i$. Used throughout Phase 4B/4C. **MATHEMATICALLY DERIVED, standard definition — DATA-VERIFIED application** (recomputed, `numerical_verification.md`).

## 21. Histogram chi-square (ANALYSIS)
Standard Pearson $\chi^2$ test against a uniform 256-bin null. **DATA-VERIFIED application**; bin-count assumption (expected frequency ≥5) explicitly checked in Phase 4C (expected freq. ≥170 for the tested image sizes).

## 22. Adjacent-pixel correlation (ANALYSIS)
$r_{xy} = \text{Cov}(X,Y)/\sqrt{D(X)D(Y)}$, computed for horizontal/vertical/diagonal neighbor pairs. **DATA-VERIFIED application.**

## 23. NPCR (ANALYSIS)
$NPCR = \frac{1}{N}\sum_i D_i \times 100\%,\ D_i=1$ iff $C_1(i)\neq C_2(i)$. Reference for i.i.d. uniform bytes: $E[NPCR]=99.609375\%$ ($=255/256$). **MATHEMATICALLY DERIVED reference + DATA-VERIFIED application.**

## 24. UACI (ANALYSIS)
$UACI=\frac{1}{N}\sum_i \frac{|C_1(i)-C_2(i)|}{255}\times100\%$. Reference for i.i.d. uniform bytes ≈33.4635%. **MATHEMATICALLY DERIVED reference + DATA-VERIFIED application.**

## 25. Mutual information (ANALYSIS, Step 1.1 only)
Plug-in estimator with analytical Miller–Madow finite-sample bias correction for a 256×256 contingency table; permutation and circular-shift nulls used for qualification. Source: `ISC_PBL/isc_sequence_characterization.py`; results in `sequence_statistics.csv` (raw MI = 0.0607 bits, bias = 0.0469 bits, adjusted MI = 0.0138 bits). **DATA-VERIFIED** (read directly from the raw CSV).

## 26. Autocorrelation (ANALYSIS, Step 1.1 only)
Byte-level ACF across lags 1–100, $N=10^6$, with Bonferroni-corrected confidence bounds. Source: `ISC_PBL/results/sequence_characterization/byte_acf_results.csv`. **DATA-VERIFIED** (file exists and was inspected; not every lag was individually re-plotted in this phase).

## 27. S-box differential/linear metrics (ANALYSIS, Phase 4D only)
Differential Distribution Table max probability, Linear Approximation Table max absolute bias, computed over the full 256×256 input/output-difference space for the generated S-box. Source: `experiments/phase4d/results/sbox_analysis.json` (max DDT prob. = 12/256 = 0.0469; max LAT bias = 68/256 = 0.266). **DATA-VERIFIED.**

No equation was introduced into this package beyond what is directly used in an inspected script or an executed analysis in this project's history.
