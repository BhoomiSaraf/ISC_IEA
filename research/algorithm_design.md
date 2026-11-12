# ISC-IMG v1: algorithm specification and design rationale (revision 3, partial)

Status: revision 3 (2026-10-26). Changes 2-4 are applied; Change 1 (§10.1) is pending review. The
algorithm is unchanged since revision 2.
* **Implemented at Checkpoint 3** in `isc_cipher/` (Gates C and R passed; `checkpoint3_report.md`).
* The [PROPOSED] and [OPEN] labels below reflect the specification-time status; implementation and test
  evidence is recorded in `checkpoint3_report.md` and `results/cipher_validation/`.
* Earlier revisions are listed in §15.
Companion documents: `threat_model.md`, `design_comparison.md`, `attack_plan.md` and
`checkpoint2_review_response.md`.

## Status labels

Every decision or claim carries one of these labels:

| label | meaning |
|---|---|
| **[IMPL]** | implemented in this workspace (the file is named) |
| **[TESTED]** | measured by an experiment whose output is saved (the path is named) |
| **[PROVEN]** | follows from a proof given in this document, or from a standard result that is cited |
| **[ASSUMED]** | standard cryptographic assumption, not proven here |
| **[PROPOSED]** | design decision, not implemented and not tested |
| **[OPEN]** | unresolved; the experiment or decision that resolves it is named |

## 0. Dependency chain and status register

Stages run strictly in this order. Each consumes only outputs of earlier stages. Decryption repeats
stages 2-5 identically, but only after the tag has been verified (§11).

| # | stage | output | status |
|---|---|---|---|
| 1 | secret-key format and threat model | K: 32 random bytes; adversary model | [PROPOSED] (§4.1, `threat_model.md`) |
| 2 | key derivation: HKDF-SHA-256 with salt = nonce, info = context ‖ label | PRK; K_mac, K_kcv, iv_f, iv_b, 256 lane seeds | [PROPOSED]; HKDF security [ASSUMED] |
| 3 | key-dependent ISC initialisation | 256 initial states (x0, y0) on a 2^106-point grid | [PROPOSED]; mapping properties [PROVEN] (§5.3) |
| 4 | sequence generation: frozen ISC recurrence, profile 1, burn-in T = 1024 | lane states over time | map evaluation order [IMPL] in `isc_seq/isc_map.py: isc_step` with host sin/cos; profile 1 sin/cos [PROPOSED]; lanes [PROPOSED] |
| 5 | conversion: bytes M(v), bounded integers, S-box, permutation, diffusion bytes | S, S⁻¹, π, a, b | byte rule [IMPL] `isc_seq/extract.py: mantissa_byte` (single orbit); the rest [PROPOSED] |
| 6 | encryption (permutation → forward diffusion → backward diffusion), KCV, HMAC tag | ciphertext | [PROPOSED]; invertibility [PROVEN] (§12) |
| 6′ | decryption: parse → validate → verify tag → stages 2-5 → inverse diffusion → inverse permutation → verify KCV → release | plaintext or error | [PROPOSED] |
| 7 | implementation gates and attack-driven evaluation | test and attack results | [PROPOSED] (`attack_plan.md`); nothing has run |

**Why this order.** The frozen recurrence and its parameters are public. Secret material must determine
the initial states (stage 3) before any sequence is generated (stage 4), or every user would get the same
sequence. A per-message public nonce must enter the derivation (stage 2), or every image under one key
would reuse the same streams, which is the root cause of the equivalent-key breaks in the literature
([entropy2023crypt2dhyper], [li2018autoblocking]). Key-dependent initialisation is necessary but **not
sufficient** for confidentiality. That remains [OPEN] (§13).

## 1. Overview

```
K (32 B) ─┐
N (16 B, public, random) ─┼─ HKDF-SHA-256 ─► K_mac (32 B), K_kcv (32 B), iv (2 B),
header context ─┘                            seeds s[g][l] (16 B) for 4 streams × 64 lanes
seed ─► (x0, y0) on the 2^106 grid ─► ISC recurrence (profile 1) ─► burn-in T = 1024 ─► output steps
lane outputs ─► bytes M(x), M(y) ─► interleaved per stream: B_sbox, B_perm, B_fwd, B_bwd
B_sbox ─► S-box S;  B_perm ─► permutation π;  B_fwd ─► a;  B_bwd ─► b
P ─► flatten ─► q = permute(p, π) ─► u = forward(q; S, a, iv_f) ─► c = backward(u; S, b, iv_b)
final lane states ─► KCV = HMAC(K_kcv, ·)[0:8];   tag = HMAC(K_mac, header ‖ c)
```

## 2. Terminology (normative)

| term | definition |
|---|---|
| **stream** | one of four named byte sources `sbox`, `perm`, `fwd`, `bwd`, in this canonical order. Each stream serves exactly one purpose. |
| **lane** | one ISC orbit belonging to one stream. Each stream has L = 64 lanes, indexed l = 0..63. There are 4 × 64 = **256 lanes per message** in total. |
| **seed** | the 16-byte HKDF output for one lane, label `lane/<stream>/<l as 4 decimal digits>`. There are 256 seeds per message, one per lane; no seed is shared. |
| **initial state** | (x0, y0) computed from the seed (§5.2) |
| **burn-in** | T = 1024 applications of the ISC step to each lane before any output; burn-in states are never output |
| **output step** | one application of the ISC step to all 64 lanes of a stream, followed by emission of 2 bytes per lane (128 bytes per output step) |
| **stream byte sequence** | the concatenation, over output steps j = 1, 2, …, of [M(x_0^(j)), M(y_0^(j)), M(x_1^(j)), M(y_1^(j)), …, M(x_63^(j)), M(y_63^(j))] |
| **consumption** | stream bytes are consumed strictly in order, each exactly once. A stream runs ⌈B_g / 128⌉ output steps, where B_g is the number of bytes it consumes. Unconsumed bytes of the last output step are discarded and never used elsewhere. |
| **steps_g** | number of output steps run by stream g (excluding burn-in) |

**Byte budgets per message (n = number of image elements).**

| stream | bytes consumed B_g | output steps |
|---|---|---|
| sbox | 4·(255 + r_s), where r_s ≥ 0 is the number of Lemire rejections | ⌈B/128⌉ ≥ 8 |
| perm | 4·(n − 1 + r_p) (0 when n = 1) | ⌈B/128⌉ (0 when n = 1) |
| fwd | n | ⌈n/128⌉ |
| bwd | n | ⌈n/128⌉ |

* All four streams are always initialised and burned in, whatever n is.
* The expected number of rejections is far below one per draw (Lemire: rejection probability
  < s/2^32 per draw).
* Maximum n is 2^24 in v1 (reduced from 2^28 in revision 1). Hence B_perm ≤ 4·2^24 + small, so at
  most about 2^19 + 1 output steps and at most about **525,000 steps per lane including burn-in**.
  This keeps every lane length inside the range where the cycle search found no cycle (2×10^6 steps,
  3 orbits; [TESTED] `results/sequence_generation/default_20261025/periodicity.csv`). That evidence is
  thin (3 orbits) and is extended in A6.
* No byte is ever used twice, and the four streams have disjoint lanes.

**Independence assumption [ASSUMED → OPEN].** The 256 seeds are outputs of a PRF and are treated
as independent uniform 16-byte strings ([ASSUMED], HKDF). The resulting *orbits* are deterministic
functions of independent initial states. Whether their output bytes are statistically independent
across lanes and streams is a property of ISC, not of HKDF. It is [OPEN] and tested in A6(d) and A12.

## 3. Numbers, bytes and arrays (normative)

* Bytes are integers 0..255. `‖` is concatenation. BE16, BE32 and BE64 are big-endian encodings or
  decodings. u8(v) is one byte.
* `bits(v)` is the IEEE 754 binary64 encoding of v as an unsigned 64-bit integer.
* Integer arithmetic is exact. Sums in the diffusion are at most 765 and are reduced mod 256 as
  written. The product w·s in §8.1 is less than 2^64 and is computed exactly.
* Image array: dtype uint8, shape (H, W) with C = 1, or (H, W, 3) with C = 3.
  * Flattening is row-major: index k = (i·W + j)·C + ch, for 0 ≤ k < n = H·W·C.
  * Reshaping uses the same convention.
  * There is no padding. Every stage works on byte sequences of any length n ≥ 1, so no dimension
    needs rounding.
* Constants (binary64 nearest values): a = 0.9, c = 0.4, d = 6.0, ω = 10.0, 1.0, 2.0. These are the
  frozen ISC parameters. ω is never key-dependent.

## 4. Keys, nonce and context (stages 1-2)

### 4.1 Secret key and nonce

| item | specification | status |
|---|---|---|
| K | exactly 32 bytes (`bytes`/`bytearray`), generated by `GenerateKey() = os.urandom(32)`. Any other type or length → `InvalidKey`, raised before any computation. No text, hex or password input (a password would need Argon2 [rfc9106]; out of scope). | [PROPOSED] |
| key quality | uniform 256-bit K is assumed. Low-entropy keys cannot be reliably detected and are not filtered. | [ASSUMED] |
| key handling | K is never logged, serialised or hashed into outputs | [PROPOSED] |
| N | 16 bytes from `os.urandom(16)`, generated inside `Encrypt`. Public: stored in clear and authenticated. Not a key and not secret; its only requirement is uniqueness per key. The public API has no nonce parameter. | [PROPOSED]; CSPRNG uniformity [ASSUMED] |
| salt | N is the HKDF salt. There is no other salt. | [PROPOSED] |

### 4.2 Context string

```
ctx = 0x49 0x53 0x43 0x2D 0x49 0x4D 0x47 0x2F 0x76 0x31        # ASCII "ISC-IMG/v1" (10 bytes)
      ‖ u8(PROFILE) ‖ u8(DTYPE) ‖ BE16(H) ‖ BE16(W) ‖ u8(C)     # 7 bytes; total 17 bytes
```

### 4.3 HKDF derivations (RFC 5869 [rfc5869], hash SHA-256)

```
PRK = HMAC-SHA-256(key = N, message = K)                                  # HKDF-Extract(salt=N, IKM=K)
Derive(label, len) = HKDF-Expand(PRK, info = ctx ‖ 0x00 ‖ ASCII(label), L = len)
```

| label (ASCII) | length (bytes) | output |
|---|---|---|
| `mac` | 32 | K_mac |
| `kcv` | 32 | K_kcv |
| `iv` | 2 | iv_f = byte 0, iv_b = byte 1 |
| `lane/sbox/0000` … `lane/sbox/0063` | 16 each | seeds of stream sbox |
| `lane/perm/0000` … `lane/perm/0063` | 16 each | seeds of stream perm |
| `lane/fwd/0000` … `lane/fwd/0063` | 16 each | seeds of stream fwd |
| `lane/bwd/0000` … `lane/bwd/0063` | 16 each | seeds of stream bwd |

* That is 259 derivations, all lengths ≤ 32 ≤ 255·32 as RFC 5869 requires.
* Labels are pairwise distinct and none is a prefix-extension ambiguity: the info string ends at the
  label, and the label's length differs or its bytes differ.
* By the HKDF PRF assumption, all derived values are independent and uniform [ASSUMED].
* Binding H, W, C and PROFILE into `ctx` means that a ciphertext reinterpreted with other metadata uses
  unrelated streams. The tag also covers these fields.

## 5. Key-dependent ISC initialisation (stage 3)

### 5.1 Mapping

For a 16-byte seed s:

```
α  = BE64(s[0:8])  >> 11           # integer in [0, 2^53)
β  = BE64(s[8:16]) >> 11
x0 = float(α) · 2^-52 − 1.0          # binary64; see Lemma 1
y0 = float(β) · 2^-52 − 1.0
```

### 5.2 Grid

G = {−1 + m·2^-52 : m ∈ ℤ, 0 ≤ m < 2^53} ⊂ [−1, 1), with |G| = 2^53. The state grid is G × G, with
|G × G| = 2^106.

### 5.3 Proven properties [PROVEN]

**Lemma 1 (exact evaluation).** For every α ∈ [0, 2^53), the binary64 evaluation of float(α)·2^-52 − 1.0
equals the real number α·2^-52 − 1, and this number lies in G.

*Proof.*
* α < 2^53 is an integer, so it is exactly representable and float(α) = α.
* Multiplying by 2^-52 only changes the exponent (no underflow, since the result is 0 or at least
  2^-52), so it is exact.
* The real value v = α·2^-52 − 1 = (α − 2^52)·2^-52. The integer α − 2^52 lies in [−2^52, 2^52), so
  its magnitude is at most 2^52 < 2^53. Hence v is an integer multiple of 2^-52 with an integer
  coefficient of magnitude below 2^53, and so it is representable in binary64 (53-bit significand,
  exponent within range).
* IEEE subtraction returns the exactly rounded result of the real difference. That difference is
  representable, so the result is exact. Finally v ∈ [−1, 1 − 2^-52], which is G. ∎

**Lemma 2 (uniform 2^22-to-1 surjection).** The map s ↦ (x0, y0) from {0,1}^128 onto G × G is surjective,
and every grid point has exactly 2^22 preimages.

*Proof.* s ↦ α keeps the top 53 of the first 64 bits. Each α ∈ [0, 2^53) arises from exactly 2^11
values of s[0:8], and similarly for β from s[8:16]. The two halves are independent, so each pair
(α, β) arises from 2^11·2^11 = 2^22 seeds. Lemma 1 makes α ↦ x0 and β ↦ y0 injective onto G. ∎

**Corollary 1 (distribution).** If a seed is uniform on {0,1}^128 (HKDF assumption), the initial state is
uniform on G × G.

**Corollary 2 (unavoidable collisions).** The seed space (2^128) is larger than the state space (2^106), so
distinct seeds necessarily collide, 2^22 at a time.
* For two independent uniform seeds, P[same initial state] = 2^-106.
* Among the 256 lanes of one message, P[any two lanes share an initial state] ≤ C(256,2)·2^-106 < 2^-90.
* Among q messages under any keys, there are at most 256q lanes, so the probability is at most
  (256q)²/2^107, which is below 2^-32 for q ≤ 2^33.

These collisions concern **initial states**. Coincidence of later states (merging) is a separate question
(§5.4).

**Lemma 3 (validity).** Every (x0, y0) ∈ G × G is a valid input of the ISC map, and every subsequent
state lies in [−1, 1]².

*Proof.* 1 + x² + y² ≥ 1, so the division is defined, and sin and cos are defined everywhere.
x' = 2·sin² − 1 ∈ [−1, 1] in exact arithmetic. In floating point, sx·sx ∈ [0, 1] because |sx| ≤ 1 for
fdlibm sin on these arguments (to be confirmed by KAT; [OPEN] until then). So 2·(sx·sx) ∈ [0, 2] and
subtracting 1 lies in [−1, 1]. ∎

No initial state is rejected in v1, because no weak region is known. If A6 finds one, v2 adds a
documented rejection rule.

### 5.4 State-space size versus security (what is not proven)

The 2^106 figure is a representation size and an upper bound. It is **not** a security level.
1. **Upper bound only.** A lane's output sequence is a deterministic function of its initial state,
   so it has at most 2^106 possible values: min-entropy at most 106 bits per lane [PROVEN]. Nothing
   bounds it from below.
2. **Merging.** The ISC map is many-to-one even in exact arithmetic (the sin² stage folds), and
   floating-point rounding can map distinct states to the same state. The number E_T of distinct
   states after burn-in can therefore be smaller than 2^106 by an unknown factor [OPEN]. Experiments
   can show only weak lower bounds: no collision among m sampled lanes suggests E_T ≳ m², for example
   about 2^40 for m = 2^20 (A6(b)).
3. **State recovery.** An adversary does not need the initial state. Any state at any time t suffices to
   predict all later bytes. Each output step reveals 16 bits of the 2 × 64-bit state. The cost of
   recovering a state from observed bytes (guess-and-determine, lattice or other algebraic methods) is
   unknown and may be far below 2^106 [OPEN] (A4).
4. **Predictability without full recovery.** Statistical prediction of the next bytes from previous ones
   (for example linear or learned predictors) has not been tested [OPEN] (A15).
5. **Guidelines are not evidence.** The 2^100 key-space guideline of [alvarez2006] is a necessary
   condition on key space, not evidence that a generator is secure. It is not cited as support for
   ISC-IMG.

Consequently, no security level is claimed for the ISC streams. The only claim is that K (256 bits) is
not the weakest link by size; the weakest link is the unknown cost of predicting ISC streams.

## 6. Sequence generation (stage 4)

### 6.1 One ISC step (normative operation order)

Each line is one binary64 operation with round-to-nearest-even. Parentheses define the operations;
no operation may be fused or re-associated.

```
step(x, y):
    t1 = x * x;   t2 = y * y;   r = t1 + t2
    t3 = 1.0 + r; t4 = d / t3;  t = c - t4
    ct = COS(t);  st = SIN(t)
    t5 = x * ct;  t6 = y * st;  t7 = t5 - t6;  t8 = a * t7;  X = 1.0 + t8
    t9 = x * st;  t10 = y * ct; t11 = t9 + t10; Y = a * t11
    t12 = ω * X;  sx = SIN(t12);  t13 = ω * Y;  sy = SIN(t13)
    t14 = sx * sx; t15 = 2.0 * t14; x' = t15 - 1.0
    t16 = sy * sy; t17 = 2.0 * t16; y' = t17 - 1.0
    return (x', y')
```

This is the same evaluation as `isc_seq.isc_map.isc_step` [IMPL]; only SIN and COS differ by profile.
The equations and parameters are the frozen ones.

**Argument bounds [PROVEN] (in exact arithmetic, for states in [−1, 1]²).**
* r ∈ [0, 2], so t ∈ [c − d, c − d/3] = [−5.6, −1.6].
* |x·cos t − y·sin t| ≤ √(x² + y²) ≤ √2, so X ∈ [1 − 0.9√2, 1 + 0.9√2] and ωX ∈ [−2.73, 22.73].
* |Y| ≤ 0.9√2, so |ωY| ≤ 12.73.
* Floating-point rounding can move these by a few ulps at most. The implementation checks
  |argument| < 24 for every SIN/COS call and raises an error otherwise.

### 6.2 Burn-in

T = 1024 steps per lane, all discarded.

Rationale: the largest Lyapunov exponent is about 2.73 nats per step at ω = 10 ([TESTED]
`plots/final_freeze/omega_robustness_scan.csv`). A 1-ulp difference reaches order 1 in about 14
steps, so 1024 steps remove the structure of the 2^-52 grid. This is a heuristic argument, not a proof;
A6(c) measures divergence of neighbouring initial states.

## 7. Numerical profiles

### 7.1 Arithmetic model required by profile 1 (normative)

1. IEEE 754-2008 binary64 for every floating-point value.
2. Round-to-nearest, ties-to-even, for every operation.
3. Each operation in §6.1 and §7.2 is separately rounded. No fused multiply-add, no contraction, no
   re-association, no extended or double-rounding intermediate precision (x87 80-bit is not
   allowed), and no flush-to-zero or denormals-are-zero.
4. Integer operations on the 32-bit high word are exact two's-complement 32-bit operations.

### 7.2 Profile 1 `F64-FDLIBM`: SIN and COS

SIN and COS are fdlibm 5.3 `sin` and `cos` (Sun Microsystems 1993, permissive licence; notice preserved).
The official files are archived in `third_party/fdlibm/netlib_5.3/` with SHA-256 sums in `SHA256SUMS.txt`
([IMPL] archive only; retrieved 2026-10-26 from netlib.org/fdlibm). The normative semantics are those C
routines evaluated under the arithmetic model of §7.1, in C operator precedence. Because |argument| < 24,
only the following paths are reachable (`hx` is the signed high 32 bits of x, `ix = hx & 0x7fffffff`):

| condition | sin(x) | cos(x) |
|---|---|---|
| ix ≤ 0x3fe921fb (|x| ≲ π/4) | `__kernel_sin(x, 0, 0)` | `__kernel_cos(x, 0)` |
| otherwise | `n = rem_pio2(x, y)`; by n mod 4: k_sin(y0,y1,1), k_cos(y0,y1), −k_sin(y0,y1,1), −k_cos(y0,y1) | by n mod 4: k_cos, −k_sin, −k_cos, k_sin |

**`rem_pio2`, reachable branches** (constants with exact hex in `e_rem_pio2.c`: invpio2, pio2_1, pio2_1t,
pio2_2, pio2_2t, pio2_3, pio2_3t, half and the table `npio2_hw`):
* ix < 0x4002d97c (|x| < 3π/4): n = ±1 special case, including the `ix == 0x3ff921fb` sub-branch.
* ix ≤ 0x413921fb: medium case. `n = (int)(|x|·invpio2 + half)`, computed as two separate operations
  and then C truncation. Then the 1st reduction; the 2nd and 3rd reductions are selected by the
  exponent tests `i > 16` and `i > 49`. Finally y1 = (r − y0) − w, and the signs are flipped if hx < 0.
* The large-argument branch (`k_rem_pio2.c`) is unreachable and must raise if reached.

**Kernels:**
* `k_sin`: the |x| < 2^-27 early return, S1..S6.
* `k_cos`: the |x| < 2^-27 early return, C1..C6, the |x| < 0.3 branch and the qx construction
  (qx = 0.28125, or the high word minus 0x00200000 with low word 0).

Expressions are evaluated exactly as parsed in the C source, for example
`x - ((z*(half*y - v*r) - y) - v*S1)`.

### 7.3 Profile 1 implementations and supported environments

| implementation | environment | status |
|---|---|---|
| R1: reference, pure CPython `float` (`struct` for high and low words, no NumPy) | E1: Windows 11 x86_64, CPython 3.11.9; E2: WSL2 Ubuntu 24.04 x86_64, CPython 3.12.3 (no NumPy) | [PROPOSED] |
| V1: vectorised NumPy (`view(uint64)` for words; one ufunc per operation) | E1 with NumPy 2.0.2 (MSVC build) | [PROPOSED] |

* CPython evaluates each float operation as one C double operation using SSE2 on x86_64, without
  contraction across bytecodes.
* NumPy evaluates each ufunc call as an elementwise IEEE operation, so separate calls are never fused.
* These are properties of the implementations as documented and observed, not guarantees for every
  build. The **claim is limited to the environments in which the KATs pass**.
* The development CPU supports FMA (`/proc/cpuinfo` in WSL), so a C or compiled port must disable
  contraction (`-ffp-contract=off` for GCC/Clang, `/fp:precise` for MSVC). The Python implementations
  do not compile code.

### 7.4 Known-answer tests (KATs) [PROPOSED]

1. **SIN/COS points.** 100,063 arguments in two files:
   * `trig_kat.txt.gz` (74,063): every reachable branch boundary (each fdlibm `ix` threshold with
     neighbouring high words and assorted low words), ±64 ulp around k·π/2 for k = 1..15, special values,
     50,000 uniform in [−24, 24] and 20,000 small magnitudes;
   * `trig_kat_ext.txt.gz` (26,000): arguments t, ωX, ωY occurring on real ISC orbits (burn-in of the
     stream-KAT lanes).

   The expected outputs come from the **independent C oracle** (unmodified fdlibm 5.3 sources, gcc,
   `-O0 -ffp-contract=off -fno-builtin -D__LITTLE_ENDIAN`, E2). The KAT passes when R1 on E1, R1 on E2 and
   V1 on E1 each reproduce the oracle bits exactly. The difference from mpmath (200-bit) is recorded in ulps
   per fdlibm branch (`vectors/trig_accuracy_by_branch.json`; expected ≤ 1 ulp; fdlibm is not correctly
   rounded, and this is not required).
2. **ISC trajectory.** 10 initial states × 10^5 steps: the bits of every state are hashed and
   checkpointed. The expected values come from the independent C oracle (same build as KAT 1), which
   implements the §6.1 operation order with the fdlibm C functions. R1 on E1, R1 on E2 and V1 on E1 must
   each equal the oracle bit for bit, which also implies that they agree with each other. Stream bytes and
   lane states after burn-in and after 8 output steps (public test key, 64×64×3) are checked against the
   oracle in the same way.
3. **Generator and cipher.** Fixed public test key K_test = 0x00..0x1f and N_test = 0x00..0x0f. For
   images of shapes (1,1), (1,7), (7,1), (4,6,3), (16,16) and (64,64,3), store the S-box, the first
   1024 bytes of each stream, π (for small n), the KCV, the body hash and the full ciphertext. These
   full-cipher vectors are produced by R1 and are **not independent**. They are confirmed by V1 and by R1
   on E2; the integer stages are covered by component tests with independent expectations.

Profile 1 is declared reproducible **only** on environments where all KATs pass ([OPEN] until A11 runs).

### 7.5 Profile 2 `F64-HOSTLIBM` (non-normative)

SIN and COS come from the host NumPy (MSVC C runtime on E1). **Profile 2 is supported only by the
vectorised NumPy implementation V1.** The pure-Python reference R1 raises `ProfileError` for profile 2,
both when encrypting and when decrypting, because it cannot use host NumPy functions without NumPy.
Profile 2 has no self-test, because no portable expected values exist.
* It reproduces the earlier experiments [IMPL].
* It is not portable [TESTED, 2026-10-26, scratch measurement]: 2,593 of 80,000 sin/cos results on ISC
  arguments differ from correctly rounded values. NumPy and `math` agreed on all 80,000 calls on E1.
  The scratch script is not archived; it will be re-run and saved as part of A11.
* Profile 2 is used only for comparison and failure measurement.

## 8. Conversion to usable values (stage 5)

### 8.1 Byte extraction

```
M(v) = (bits(v) >> 8) & 0xFF        # bits 8..15 of the binary64 encoding (inside the 52-bit mantissa field)
```

* Applied to x' and y' of every lane at every output step, in the order given in §2.
* Values exactly ±1 or 0 have mantissa field 0, so M = 0. This is allowed and not special-cased.
* **Evidence status (see §14):** the rule was chosen because of earlier tests on a *different*
  generator. It is not yet tested on the v1 generator.

### 8.2 Unbiased bounded integer (Lemire [lemire2019])

```
Bounded(g, s):                  # requires 1 ≤ s ≤ 2^32; returns uniform integer in [0, s) if bytes are uniform
    w = BE32(take(g, 4));  m = w · s;  l = m mod 2^32
    if l < s:
        t = (2^32 − s) mod s
        while l < t:
            w = BE32(take(g, 4));  m = w · s;  l = m mod 2^32
    return m >> 32              # floor(m / 2^32)
```

Here take(g, 4) consumes the next 4 bytes of stream g. Uniformity, given uniform bytes, is the
result of [lemire2019] [PROVEN there].

### 8.3 S-box (stream `sbox`)

```
σ = [0, 1, …, 255]
for i = 255, 254, …, 1:
    j = Bounded(sbox, i + 1);  swap(σ[i], σ[j])
S = σ;  S⁻¹ = array with S⁻¹[S[v]] = v for all v
```

### 8.4 Permutation (stream `perm`)

```
π = [0, 1, …, n − 1]
for i = n − 1, n − 2, …, 1:
    j = Bounded(perm, i + 1);  swap(π[i], π[j])
```

* Convention: **gather**. q_k = p_{π[k]}. Inverse: p_{π[k]} = q_k.
* For n = 1 the loop is empty and π = [0].
* Elements, not pixels, are permuted, so colour channels move independently.

### 8.5 Diffusion bytes

* a = take(fwd, n), with a_k its k-th byte.
* b = take(bwd, n), with b_k its k-th byte. b is indexed by position, not by processing order.

## 9. Encryption transform (stage 6)

```
Forward,  k = 0, 1, …, n−1:      u_k = S[(q_k + u_{k−1} + a_k) mod 256]      with u_{−1} = iv_f
Backward, k = n−1, n−2, …, 0:    c_k = S[(u_k + c_{k+1} + b_k) mod 256]      with c_n    = iv_b
```

The body is c_0 … c_{n−1}. Edge case n = 1: c_0 = S[(S[(q_0 + iv_f + a_0) mod 256] + iv_b + b_0) mod 256].

**Inverse.** Every u_k and q_k can be computed independently, because all of c, and then all of u, are known:

```
u_k = (S⁻¹[c_k] − c_{k+1} − b_k) mod 256        for all k     (c_n = iv_b)
q_k = (S⁻¹[u_k] − u_{k−1} − a_k) mod 256        for all k     (u_{−1} = iv_f)
p_{π[k]} = q_k                                   for all k
```

**Propagation note [PROVEN in part].**
* A change of q at position j changes every u_k for k ≥ j: for fixed other inputs, the argument
  of S is injective in u_{k−1}.
* In the backward pass, c_k for k < j changes whenever c_{k+1} changed and u_k did not.
* For k ≥ j, u_k and c_{k+1} both change, and their changes can cancel modulo 256. When the changes
  behave like random bytes this happens with probability about 1/256 per position. A cancellation
  at k leaves c_k unchanged, but propagation continues through earlier positions.
* So a one-element change alters each ciphertext byte except with probability about 1/256, the same
  as for unrelated random bytes. This is a heuristic statement, measured in A3.

## 10. Ciphertext format (normative, big-endian)

| offset | length | field | valid values |
|---|---|---|---|
| 0 | 4 | magic | 0x49 0x53 0x43 0x49 (`ISCI`) |
| 4 | 1 | VERSION | 1 |
| 5 | 1 | PROFILE | 1 (normative) or 2 (comparison only) |
| 6 | 1 | DTYPE | 1 = uint8 |
| 7 | 1 | C | 1 or 3 |
| 8 | 2 | H | 1..65535 |
| 10 | 2 | W | 1..65535 |
| 12 | 16 | N | any |
| 28 | 8 | KCV | any |
| 36 | n | body | n = H·W·C ≤ 2^24 |
| 36 + n | 32 | tag | HMAC-SHA-256(K_mac, bytes[0 : 36 + n]) |

* Total length 68 + n.
* **Authenticated range: bytes [0, 36 + n)**, that is every header field (including N and KCV) and the
  whole body. The tag is untruncated (32 bytes).
* Nothing is authenticated implicitly. Dimensions and profile are additionally bound through `ctx`.

### 10.1 KCV (keystream check value)

```
state_bytes = ‖_{g in (sbox, perm, fwd, bwd)} ( ‖_{l=0..63} BE64(bits(x_{g,l})) ‖ BE64(bits(y_{g,l})) ‖ BE64(steps_g) )
KCV = HMAC-SHA-256(K_kcv, state_bytes)[0:8]
```

* (x_{g,l}, y_{g,l}) is the state of lane l of stream g after its last output step, or after burn-in
  if steps_g = 0.
* state_bytes is 4·(64·16 + 8) = 4128 bytes.

**What the KCV detects.** Any difference, between encryptor and decryptor, in any final lane state or in
any steps_g, with probability 1 − 2^-64, assuming HMAC is a PRF. Because of the chaotic amplification
(§6.2), a single different sin/cos result anywhere in a lane changes that lane's final state with very
high probability, unless the divergence happens within the last few steps and stays below the
representation. **The probability of that exception is not quantified [OPEN] (A11).**

**What the KCV does not detect:**
1. Errors in the integer stages (S-box, permutation, diffusion, reshaping). Those are deterministic
   integer code and are covered by the KATs.
2. Divergence affecting only bytes that were never consumed. That is harmless.
3. Identical non-conformance on both sides, for example the same buggy platform. In that case
   decryption is still correct.
4. Which side is non-conforming.

The KCV is checked only after the tag verifies, so it is never an oracle for unauthenticated input.

## 11. Algorithms

### 11.1 Encrypt

```
Encrypt(K, P) -> bytes:
 1  if type(K) not in (bytes, bytearray) or len(K) != 32: raise InvalidKey
 2  if P.dtype != uint8 or P.ndim not in (2, 3) or (P.ndim == 3 and P.shape[2] != 3): raise InvalidImage
 3  H, W = P.shape[0], P.shape[1];  C = 1 if P.ndim == 2 else 3;  n = H·W·C
 4  if not (1 ≤ H ≤ 65535 and 1 ≤ W ≤ 65535 and n ≤ 2^24): raise InvalidImage
 5  N = os.urandom(16);  PROFILE = 1
 6  ctx = "ISC-IMG/v1" ‖ u8(1) ‖ u8(1) ‖ BE16(H) ‖ BE16(W) ‖ u8(C)
 7  PRK = HMAC-SHA-256(N, K);  K_mac, K_kcv, (iv_f, iv_b), seeds = Derive(...)            # §4.3
 8  for g in (sbox, perm, fwd, bwd): for l in 0..63: (x,y)[g,l] = init(seed[g,l])        # §5.1
 9  for each lane: apply step T = 1024 times                                                # §6
10  S, S⁻¹ = sbox_build();  π = perm_build(n);  a = take(fwd, n);  b = take(bwd, n)        # §8, this order
11  p = flatten(P);  q[k] = p[π[k]]
12  u = forward(q, a, S, iv_f);  c = backward(u, b, S, iv_b)                               # §9
13  KCV = kcv(final states, steps)                                                          # §10.1
14  hdr = "ISCI" ‖ u8(1) ‖ u8(1) ‖ u8(1) ‖ u8(C) ‖ BE16(H) ‖ BE16(W) ‖ N ‖ KCV
15  tag = HMAC-SHA-256(K_mac, hdr ‖ c)
16  return hdr ‖ c ‖ tag
```

### 11.2 Decrypt (validation order is normative)

```
Decrypt(K, Z) -> array:
 1  if type(K) not in (bytes, bytearray) or len(K) != 32:          raise InvalidKey
 2  if type(Z) not in (bytes, bytearray) or len(Z) < 69:           raise Malformed       # 68 + n, n ≥ 1
 3  parse magic, VERSION, PROFILE, DTYPE, C, H, W from Z[0:12]
 4  if magic != "ISCI" or VERSION != 1 or PROFILE not in {1,2} or DTYPE != 1
       or C not in {1,3} or H == 0 or W == 0:                      raise Malformed
 5  n = H·W·C;  if n > 2^24 or len(Z) != 68 + n:                    raise Malformed
 6  N = Z[12:28];  KCV_hdr = Z[28:36];  c = Z[36:36+n];  tag = Z[36+n:68+n]
 7  PRK = HMAC-SHA-256(N, K);  K_mac = Derive("mac", 32)
 8  if not hmac.compare_digest(tag, HMAC-SHA-256(K_mac, Z[0:36+n])):  raise AuthenticationError
    --- nothing below runs unless the tag is valid ---
 9  ensure the profile self-test (KAT subset) has passed in this process, else raise ProfileError;
    profile 2: no self-test, and ProfileError unless the backend is V1 (NumPy)
10  derive K_kcv, iv, seeds; initialise; burn in; build S, S⁻¹, π, a, b in the same order as Encrypt 10
11  u[k] = (S⁻¹[c[k]] − c[k+1] − b[k]) mod 256   (c[n] = iv_b)
12  q[k] = (S⁻¹[u[k]] − u[k−1] − a[k]) mod 256   (u[−1] = iv_f)
13  p[π[k]] = q[k]
14  if not hmac.compare_digest(KCV_hdr, kcv(final states, steps)):   raise NumericalDivergenceError   # p is discarded
15  return reshape(p, (H, W) if C == 1 else (H, W, 3)) as uint8
```

* **No plaintext is released before step 15.**
* Steps 9-14 run only for authenticated input.
* A wrong key fails at step 8 (`AuthenticationError`), which by design cannot be distinguished from
  tampering.
* Error messages carry no secret-dependent detail.

## 12. Reversibility [PROVEN]

**Theorem.** For every valid (K, P), if Encrypt and Decrypt compute the same S, π, a, b, iv_f and iv_b
(condition R), then Decrypt(K, Encrypt(K, P)) = P (equal shape, dtype and every element).

*Proof.*
* **Condition R holds when both sides conform to profile 1.** All inputs to stages 2-5 (K, N, ctx) are
  identical, because ctx comes from authenticated header fields. Stages 2-5 are deterministic, and both
  sides consume the streams in the same order and amounts: the S-box needs the same 255 draws, π the
  same n − 1 draws, so both follow the same rejection path, and a and b need n bytes each. Condition R
  is checked at run time by the KCV for the floating-point part.
* (i) S and π are compositions of transpositions applied to identities, so they are bijections.
* (ii) From c_k = S[(u_k + c_{k+1} + b_k) mod 256], applying S⁻¹ gives
  u_k ≡ S⁻¹[c_k] − c_{k+1} − b_k (mod 256). Since u_k ∈ [0, 255], u_k equals the residue computed in
  step 11.
* (iii) Likewise, q_k equals the residue computed in step 12.
* (iv) The q_k = p_{π[k]} for all k determine p uniquely, because π is a bijection.
* (v) Reshaping with the same (H, W, C) convention restores the array, and dtype uint8 holds by
  construction. ∎

### 12.1 Hand-checkable example (illustration only)

This example uses a **toy affine S-box** S(v) = (5v + 3) mod 256, with inverse
S⁻¹(w) = 205·(w − 3) mod 256 (5·205 = 1025 ≡ 1), and hand-picked stream bytes. It demonstrates the
recurrences and conventions, not v1's actual S-box.

* Image p = [10, 20, 30] (n = 3, for example a 1×3 grayscale image). iv_f = 7, iv_b = 9,
  a = [1, 2, 3], b = [4, 5, 6].
* **Permutation.** Perm stream words (BE32): 0x80000000, 0xC0000000.
  * i = 2: s = 3. m = 3·2^31 = 0x1_8000_0000, l = 0x8000_0000 ≥ 3, so j = 1. Swap → π = [0, 2, 1].
  * i = 1: s = 2. m = 2·0xC000_0000 = 0x1_8000_0000, so j = 1. No change. π = [0, 2, 1].
  * q = [p0, p2, p1] = [10, 30, 20].
* **Lemire rejection example (not used above).** For s = 3, t = (2^32 − 3) mod 3 = 1. The word w = 0 gives
  l = 0 < 3 and l < t, so it is rejected and the next word is drawn.
* **Forward pass.**
  * u0 = S[(10 + 7 + 1) = 18] = 93
  * u1 = S[(30 + 93 + 2) = 125] = 628 mod 256 = 116
  * u2 = S[(20 + 116 + 3) = 139] = 698 mod 256 = 186
* **Backward pass.**
  * c2 = S[(186 + 9 + 6) = 201] = 1008 mod 256 = 240
  * c1 = S[(116 + 240 + 5) mod 256 = 105] = 528 mod 256 = 16
  * c0 = S[(93 + 16 + 4) = 113] = 568 mod 256 = 56
  * **c = [56, 16, 240].**
* **Decryption, recovering u.**
  * u0 = S⁻¹[56] − 16 − 4 = 113 − 20 = 93
  * u1 = S⁻¹[16] − 240 − 5 = 105 − 245 ≡ 116
  * u2 = S⁻¹[240] − 9 − 6 = 201 − 15 = 186
* **Decryption, recovering q.**
  * q0 = S⁻¹[93] − 7 − 1 = 18 − 8 = 10
  * q1 = S⁻¹[116] − 93 − 2 = 125 − 95 = 30
  * q2 = S⁻¹[186] − 116 − 3 = 139 − 119 = 20
* **Inverse permutation.** p[π[k]] = q[k] gives p0 = 10, p2 = 30, p1 = 20, so **p = [10, 20, 30] ✓**.

The example was also checked by an independent scratch script (see `checkpoint2_review_response.md`).
In Gate C it becomes an automated test, with the toy S-box injected through a test-only hook.

## 13. Security status summary

| property | status |
|---|---|
| exact invertibility (given condition R) | [PROVEN] §12 |
| key-to-state mapping exact, uniform, 2^22-to-1 | [PROVEN] §5.3 (uniformity assumes HKDF is a PRF [ASSUMED]) |
| integrity (INT-CTXT) of the format | [PROVEN] by generic encrypt-then-MAC with HMAC-SHA-256 as a PRF, independent K_mac and the full authenticated range ([bellare2008ae], [ASSUMED] HMAC PRF). Not dependent on ISC. |
| confidentiality (IND-CPA, nonce-respecting) | **[OPEN] and unproven.** It depends on ISC streams being unpredictable, which has no reduction. HMAC does not help confidentiality. |
| IND-CCA | follows from IND-CPA + INT-CTXT for encrypt-then-MAC, so it is **[OPEN]** to the same extent |
| effective security level of ISC streams | **[OPEN]**: ≤ 106 bits per lane (upper bound only); merging, state recovery and prediction untested (§5.4) |
| behaviour under nonce reuse | deterministic encryption; integrity is preserved; confidentiality degrades; see `threat_model.md` §6. **No claim.** |
| reproducibility of profile 1 | **[OPEN]** until the KATs pass on E1 and E2 (A11) |
| statistical quality of v1 streams | **[OPEN]**, pending A12 |

## 14. Evidence register for the extraction rule

| generator | configuration | evidence | status |
|---|---|---|---|
| G_prior (earlier experiments) | profile 2, a single orbit per sequence, initial states from NumPy PCG64 (seed 20261025), T = 5000, bytes M(x), M(y) per step, 100 sequences × 10^6 bits | Python battery: 12/12 tests passed protocol; official NIST STS 2.1.2: 0 flagged series among 188 (`results/sequence_generation/default_20261025/`, `results/nist_sts_official/sts212_default_20261025/`) | [TESTED] (statistical only) |
| **G_v1 (this design)** | profile 1, HKDF seeds, 64 lanes interleaved, T = 1024, four streams | none | **[OPEN]: not tested.** A12 re-runs the official suite on it, and the result will be reported whether it passes or fails |

G_prior's results do **not** transfer to G_v1. They motivated the choice of rule; they do not validate it.

## 15. Change log

* **Revision 3 (2026-10-26), after the checkpoint-3 review** (`proposed_spec_changes_rev3.md`). No change
  to the algorithm, parameters, constants, format or implementation behaviour.
  * Change 2: profile 2 is supported by V1 only (§7.5, §11.2 step 9).
  * Change 3: KAT 1 extended to 100,063 arguments, including 26,000 real-orbit arguments; per-branch
    mpmath deviation recorded (§7.4). Evidence: `results/cipher_validation/gate_r_ext_*` (all PASS).
  * Change 4: KATs 1-2 and the stream KAT are checked against the independent C oracle; KAT 3 is not
    independent (§7.4).
  * Change 1 (§10.1 KCV rationale) is pending review; the old text still stands.
* **Revision 2 (2026-10-26), after the checkpoint-2 review:**
  * status labels;
  * terminology for stream, lane and seed (256 seeds = 4 streams × 64 lanes);
  * byte budgets;
  * maximum n reduced from 2^28 to 2^24;
  * Lemmas 1-3 with proofs;
  * a state-space section separating representation size from security; the 2^100 guideline is no
    longer used as support;
  * normative operation order;
  * arithmetic model, fdlibm reachable-path specification, archived sources, implementations R1/V1
    and environments E1/E2;
  * KAT definition;
  * KCV detects / does-not-detect lists;
  * full validation order with error classes;
  * hand-checkable example;
  * evidence register.
* **Revision 1 (2026-10-26):** initial draft (superseded).
