# Response to the checkpoint-2 review (revision 2 of the design)

Date: 2026-10-26. Documents revised: `algorithm_design.md` (rewritten), `threat_model.md` (rewritten),
`design_comparison.md` (edited), `attack_plan.md` (rewritten).

Unchanged: the frozen ISC equations, ω = 10.0, all code under `isc_seq/`, `experiments/` and
`script/`, and all results. **No cipher code was written.**

New artefacts:
* `third_party/fdlibm/netlib_5.3/`: official fdlibm 5.3 sources from netlib, with SHA-256 sums and
  retrieval time;
* `research/tools/check_spec_example.py`: a standalone check of the hand-worked example.

| # | review point | what was done | resolved? | evidence | still open |
|---|---|---|---|---|---|
| 1 | state space is not a security proof | `algorithm_design.md` §5.3 proves Lemma 1 (exact binary64 evaluation), Lemma 2 (uniform 2^22-to-1 surjection from 2^128 seeds onto the 2^106 grid), the corollaries on unavoidable collisions (2^-106 per lane pair; < 2^-90 within a message; bound for q messages) and Lemma 3 (validity, with one KAT-dependent step). §5.4 separates representation size (an **upper bound** of 106 bits on per-lane min-entropy) from security, lists merging, state recovery and prediction as unanalysed, and withdraws the 2^100 guideline as supporting evidence (also corrected in `design_comparison.md` §5). | **yes**, as specification | proofs in the document | E_T (distinct post-burn-in states): A6(b), which can only give lower bounds of about m². State recovery: A4. Prediction: A15 (new). **No security level is claimed.** |
| 2 | 256 seeds vs 64 lanes | §2 defines stream, lane, seed, output step, stream byte sequence, consumption and steps_g. **4 streams × 64 lanes = 256 lanes, each with its own seed; nothing is shared.** Byte budgets per stream as functions of n; behaviour for n = 1 (perm runs 0 output steps but is still burned in); maximum n reduced to 2^24 so that every lane stays within about 525,000 steps. Independence is stated as an HKDF assumption for seeds and an [OPEN] property for orbits. | **yes** | definitions; budget table | cross-lane and cross-stream independence: A6(d), A12 |
| 3 | extraction evidence | §8.1 and the evidence register in §14: G_prior (profile 2, single orbit, PCG64 initial states, T = 5000) is [TESTED]; **G_v1 is [OPEN] and untested**, and earlier results "do not transfer". A12 is described as a new experiment reported regardless of outcome. `design_comparison.md` is qualified in the same way. | **yes** | earlier results paths cited | A12 not run |
| 4 | numerical reproducibility | §6.1 gives the normative single-operation order; §7.1 the arithmetic model (binary64, round-to-nearest-even, no FMA, contraction, re-association, extended precision or FTZ/DAZ); §7.2 the fdlibm 5.3 definition with archived, hashed sources and only the branches reachable for \|arg\| < 24 (others raise); §7.3 two implementations (R1 pure CPython, V1 NumPy) and two environments (E1 Windows, E2 WSL Ubuntu; both checked to exist, and E2 has no NumPy, hence R1); §7.4 KAT contents and pass criteria; §10.1 the exact KCV definition with **detects / does-not-detect** lists. Reproducibility is claimed **only for environments where the KATs pass**. | **yes**, as specification | fdlibm sources and hashes; measured 3.2% non-correctly-rounded host sin/cos (scratch, to be archived in A11) | KATs not run (Gate R, A11); the window in which the KCV cannot detect divergence is not quantified (A11(iii)) |
| 5 | cipher correctness | §8 (Lemire, S-box, permutation as a gather convention, diffusion bytes), §9 (both recurrences and inverses, edge case n = 1, propagation note), §3 (byte order, flattening, no padding), §11 (encryption and decryption pseudocode), §12 (reversibility theorem with proof). §12.1 gives a **hand-checkable example** with a toy affine S-box, including a Lemire rejection case. The example was verified independently. | **yes**, as specification | `research/tools/check_spec_example.py` output: `pi [0, 2, 1] … c [56, 16, 240] … p [10, 20, 30] OK True` | automated tests are part of Gate C (not implemented) |
| 6 | authentication and nonces | §10: byte-exact header table, authenticated range [0, 36 + n), 32-byte tag. §4.3: all 259 HKDF labels and lengths. §11.2: numbered validation order with error classes; the tag is checked at step 8 before any generator work; the plaintext is released only at step 15, after the KCV check. `threat_model.md` §6: nonce generation, birthday bound and the **exact consequences of reuse** (fixed deterministic permutation; equality leak; no XOR leak in V-FULL; CPA and codebook attacks apply; integrity is preserved, unlike GCM). | **yes** | definitions; birthday bound | the cost of attacks under reuse (A1) |
| 7 | security claims and evaluation | confidentiality is marked **[OPEN]/unproven** everywhere. `threat_model.md` §5 separates integrity, which is [PROVEN] given HMAC as a PRF and independent of ISC, from confidentiality, which is a conjecture depending on ISC, and states that HMAC cannot repair weak encryption. §7 there contrasts the AEAD baselines' guarantees with the experimental construction. The attack plan pre-registers success criteria for every attack and lists the allowed statements (§3 there). `design_comparison.md` B4 now notes that any nonce-reuse benefit would come from the envelope and should also appear in V-CHACHA, so it would not be attributable to ISC. | **yes** | documents | everything experimental |
| 8 | research integrity | status labels [IMPL]/[TESTED]/[PROVEN]/[ASSUMED]/[PROPOSED]/[OPEN] are defined and applied in the specification (status register §0, summary §13, evidence register §14). Every attack-plan item is [PROPOSED]. Frozen map, ω, existing code and results are untouched. No implementation was done. | **yes** | `algorithm_design.md` §0, §13, §14 | none |

## Corrections made during revision

* **Maximum image size reduced from 2^28 to 2^24 elements.** This keeps lane lengths within the
  range covered by the existing cycle search; that evidence is still thin (3 orbits), and A6 extends it.
* **2^100 guideline withdrawn as support** (revision 1 described the per-lane state as "just above" it).
* **The NIST evidence is no longer attributed to the v1 generator.**
* **New experiment A15** (statistical predictability).
* **A12 extended** to single-lane sequences.

## Remaining decisions for the reviewer

1. Accept maximum n = 2^24 (for example 4096×4096 RGB) for v1.
2. Accept the two-implementation strategy (R1 pure Python, V1 NumPy) instead of installing NumPy in WSL.
   Installing it would need an external download and approval; it would only add a third check.
3. Approve moving to implementation with **Gates C and R first**. Checkpoint 3 would follow Gates C and R,
   before any attack or statistical experiment.
