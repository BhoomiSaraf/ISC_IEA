# Proposed specification changes (revision 3): FOR REVIEW, NOT APPLIED

Date: 2026-10-26.
* Applies to `research/algorithm_design.md` (revision 2) and `research/attack_plan.md` (revision 2).
* **None of these changes alters the algorithm, a parameter, a constant, the format or any
  implementation behaviour.**
* The implementation already behaves as the new text describes.
* After approval, the texts below replace the quoted texts verbatim, and §15 (change log) gets a
  revision-3 entry.

## Change 1: KCV rationale (`algorithm_design.md` §10.1)

**Reason.** In Checkpoint 3 testing, 3 of 7 single-ulp perturbations of one sin result were absorbed by
rounding: final states were bit-identical and the decryption was correct. The current sentence
("changes that lane's final state with very high probability") is not supported by the evidence.

**Current text**
> Because of the chaotic amplification (§6.2), a single different sin/cos result anywhere in a lane
> changes that lane's final state with very high probability, unless the divergence happens within the
> last few steps and stays below the representation. **The probability of that exception is not
> quantified [OPEN] (A11).**

**Proposed text: revision B (2026-10-26, replaces revision A below after review)**
> *Specified behaviour.* Decryption releases a plaintext only if the KCV recomputed from the decryptor's
> final lane states and step counts equals the KCV in the authenticated header. Otherwise it raises
> `NumericalDivergenceError` (a false match has probability 2^-64 if HMAC-SHA-256 is a PRF). The KCV
> covers final states and step counts only: a numerical divergence that leaves every final lane state and
> step count unchanged is not detected by the KCV.
>
> *Observed (Checkpoint 3, `research/checkpoint3_report.md` §4).* One sin result was changed by 1 ulp
> during decryption at 7 chosen points (4×6×3 image, V1, E1):
> * in 3 cases every final lane state was bit-identical to the reference, and the decrypted plaintext was
>   correct;
> * in 4 cases at least one final state differed, and decryption was rejected by the KCV;
> * no case released a wrong plaintext.
>
> **These 7 hand-chosen points do not establish a probability or rate for any outcome.**
>
> *Hypothesis (not tested).* The 3 identical cases are attributed to the 1-ulp change being lost in later
> rounding; the mechanism was not traced.
>
> *Open [OPEN] (A11(iii)).*
> * Whether a divergence can change the stream bytes that are consumed while leaving all final states and
>   step counts unchanged, which would release a wrong plaintext without detection.
> * The rates of the three outcomes (identical, detected, undetected-wrong) under a defined perturbation
>   distribution.

**Superseded proposal: revision A (not to be applied; it asserted chaotic propagation and an exhaustive list of causes)**
> A different sin/cos result has one of two consequences:
> (a) it is **absorbed** by subsequent rounding (for example in 2·sx² − 1), so every lane state stays
> bit-identical and decryption is correct, or
> (b) it changes at least one state; chaotic amplification (§6.2) then normally propagates the change to
> the final state, which the KCV detects.
> A wrong plaintext can therefore be released only if a state difference arises and is later erased
> before the final state. This was not observed: 7 tested perturbations gave 3 absorbed and 4
> detected, with 0 wrong releases (`research/checkpoint3_report.md` §4). The absorption rate and the
> frequency of the erase case are **not quantified [OPEN] (A11(iii))**.

## Change 2: profile 2 is NumPy-only (`algorithm_design.md` §7.5 and §11.2 step 9)

**Current text (§7.5, first line)**
> SIN and COS come from the host NumPy (MSVC C runtime on E1).

**Proposed text**
> SIN and COS come from the host NumPy (MSVC C runtime on E1). **Profile 2 is supported only by the
> vectorised NumPy implementation V1.** The pure-Python reference R1 raises `ProfileError` for
> profile 2, both when encrypting and when decrypting, because it cannot use host NumPy functions
> without NumPy. Profile 2 has no self-test, because no portable expected values exist.

**Current text (§11.2, step 9)**
> `9  ensure the profile self-test (KAT subset) has passed in this process, else raise ProfileError`

**Proposed text**
> `9  ensure the profile self-test (KAT subset) has passed in this process, else raise ProfileError;`
> `   profile 2: no self-test, and ProfileError unless the backend is V1 (NumPy)`

## Change 3: KAT 1 size, content, oracle source and per-branch accuracy (`algorithm_design.md` §7.4 item 1)

**Reasons.** Three deviations were found against the current text:
1. 74,063 arguments were used, not 10^5.
2. Arguments sampled from **real ISC orbits** were not included; uniform random arguments were used
   instead (newly found while preparing this proposal).
3. The mpmath deviation was checked on a sample, not "recorded per branch".

The expected outputs come from the independent C oracle, not from R1 as the current text says (see
Change 4).

**Plan (extension; the existing vector file stays unchanged):**
* Create `isc_cipher_kat/vectors/trig_kat_ext.txt.gz` with exactly 26,000 additional arguments drawn
  from real orbits:
  * re-run the C oracle (traj mode) on the 256 stream-KAT lane initial states (public test key,
    64×64×3) and take their burn-in states in lane order and step order (`stream_kat.json` stores only
    the final burn-in state);
  * for each state, compute the three arguments of the next step, t, ωX and ωY, with the §6.1
    arithmetic (cos and sin of t are needed for X and Y; R1 is used for those, which affects only
    *which* arguments are chosen, not the expected values);
  * keep the first 26,000 arguments (8,667 states).
* The expected sin/cos outputs for these arguments come from the C oracle (trig mode).
* That makes **100,063 arguments** in total, all with expected values from the C oracle.
* Record the mpmath (200-bit) deviation in ulps, **per fdlibm branch** (direct kernel, n = ±1, medium
  with 1, 2 or 3 reduction iterations).
* Gate R checks then run on the extended set: V1 and R1 on E1, R1 on E2.
* Estimated cost: oracle under 1 min; Gate R reruns about 15 min in total.

**Current text**
> 1. **SIN/COS points.** 10^5 arguments: every reachable branch boundary (each fdlibm `ix` threshold
>    ±1 ulp, every `npio2_hw` neighbourhood up to n = 15, ±π/4, ±3π/4) and arguments sampled from real
>    ISC orbits. The expected outputs come from R1 on E1. The KAT passes when V1 on E1 and R1 on E2 give
>    identical bits. Separately, the difference from mpmath at 200 bits is recorded (expected ≤ 1 ulp;
>    fdlibm is not correctly rounded, and this is not required).

**Proposed text**
> 1. **SIN/COS points.** At least 10^5 arguments in two files:
>    * `trig_kat.txt.gz` (74,063): every reachable branch boundary (each fdlibm `ix` threshold with
>      neighbouring high words and assorted low words), ±64 ulp around k·π/2 for k = 1..15, special
>      values, 50,000 uniform in [−24, 24] and 20,000 small magnitudes;
>    * `trig_kat_ext.txt.gz` (26,000): arguments t, ωX, ωY occurring on real ISC orbits.
>
>    The expected outputs come from the **independent C oracle** (unmodified fdlibm 5.3 sources, gcc,
>    `-O0 -ffp-contract=off -fno-builtin -D__LITTLE_ENDIAN`, E2). The KAT passes when R1 on E1, R1 on
>    E2 and V1 on E1 each reproduce the oracle bits exactly. The difference from mpmath (200-bit) is
>    recorded in ulps per fdlibm branch (expected ≤ 1 ulp; fdlibm is not correctly rounded, and this
>    is not required).

## Change 4: reproducibility is checked against the independent C oracle (`algorithm_design.md` §7.4 item 2 and `attack_plan.md` Gate R)

**Current text (§7.4 item 2)**
> 2. **ISC trajectory.** 10 initial states × 10^5 steps: the bits of every state are hashed. R1 on E1
>    and E2 and V1 on E1 must agree.

**Proposed text**
> 2. **ISC trajectory.** 10 initial states × 10^5 steps: the bits of every state are hashed and
>    checkpointed. The expected values come from the independent C oracle (same build as KAT 1),
>    which implements the §6.1 operation order with the fdlibm C functions. R1 on E1, R1 on E2 and V1
>    on E1 must each equal the oracle bit for bit (which also implies that they agree with each
>    other). Stream bytes and lane states after burn-in and after 8 output steps (public test key,
>    64×64×3) are checked against the oracle in the same way.
> 3. (unchanged) **Generator and cipher.** … *Add one sentence at the end:* These full-cipher vectors are
>    produced by R1 and are **not independent**. They are confirmed by V1 and by R1 on E2; the integer
>    stages are covered by component tests with independent expectations.

**Current text (`attack_plan.md`, Gate R)**
> KATs 1-3 pass identically for R1 on E1, R1 on E2 (WSL Ubuntu 24.04, CPython 3.12.3) and V1 on E1.

**Proposed text**
> KATs 1-2 (and the stream KAT) reproduce the **independent C oracle** bit for bit for R1 on E1, R1 on
> E2 (WSL Ubuntu 24.04, CPython 3.12.3, glibc 2.39) and V1 on E1. KAT 3 (R1-generated) is reproduced
> by V1 on E1 and R1 on E2. Status: PASSED at Checkpoint 3 for the 74,063-argument set; the extended
> set is to be rerun after Change 3.
