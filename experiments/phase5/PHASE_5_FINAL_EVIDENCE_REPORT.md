# PHASE 5 — FINAL EVIDENCE REPORT

Research evidence consolidation, cross-phase verification, and manuscript
readiness assessment for the ISC-based chaotic image-encryption project.
**This document is an evidence audit, not a manuscript.** No abstract,
introduction, or paper prose is included or implied to exist elsewhere as a
result of this phase.

Repositories: A = `C:\Users\bhoom\Desktop\ISC_PBL`; B =
`C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis` (this repo).

---

## 1. Executive Research-Evidence Summary

This project has produced a reproducible, source-traceable implementation of
an ISC (Ikeda–Sine–Chebyshev) chaotic-map-based authenticated image cipher,
together with a substantial descriptive-statistical evaluation (synthetic and
real natural images) and a genuine structural/cryptanalytic investigation
(not merely descriptive statistics) of its own construction. Re-verification
in this phase against raw artifacts found the project's own prior-phase
summaries to be **accurate in substance**: of 16 spot-checked numerical
claims, 14 were recomputed to exact or near-exact agreement from raw data,
and the remaining 2 were confirmed by inspection rather than contradicted. No
claim anywhere in this project's history was found to be flatly
CONTRADICTED. One prior documentation gap was corrected in this phase itself
(the Lyapunov-exponent figure, §17). The project's own later phases (4D, 4E)
already impose the correct discipline of not overclaiming security from
descriptive statistics — this report's job was to verify that discipline was
actually followed, which it was.

## 2. Repository and Artifact Inventory

See `evidence_inventory.md` for the full table. Summary: 33+ artifacts
directly inspected across both repositories in this phase; every
`experiments/phase4{b,c,d,e}/` directory in Repo B was confirmed present and
non-empty; Phase 4A has no standalone artifact directory (it produced a
terminal report only) and is carried as REPORTED-ONLY at the artifact level,
though its specific source-code claims were independently re-spot-checked
against `isc_cipher/` in this phase (CODE-VERIFIED). Repo A's authoritative
Step 1.1 source is `results/sequence_characterization/final_step1_1_closure_report.md`
plus its accompanying CSVs — the `_v1_backup` directory is explicitly
superseded and was not used as an authority.

## 3. Step 1.1 Findings (Repo A)

Re-verified directly against `ISC_PBL/results/sequence_characterization/{configuration.json,sequence_statistics.csv,summary_metrics.csv,final_step1_1_closure_report.md}`:

- n_transient=5,000, n_retained=1,000,000, k∈{13,14,15,16} plus Arccos — **DATA-VERIFIED** exactly against `configuration.json`.
- k14 entropy X=7.999831 (spec's "~7.99983" — **VERIFIED**), chi² p=0.8222 (X) / 0.9755 (Y) (spec's "~0.822 and 0.975" — **VERIFIED, exact to the digits reported**).
- k16 even-parity defect: ULP=2.0 even-parity over 28.2% (X) / 29.6% (Y) of affected-region bytes — **VERIFIED** against the closure report's own table.
- NIST multi-sequence pass rates 98.8% (k14 X) / 99.0% (k14 Y) — **VERIFIED**, matching spec's "98.8–99%" range exactly.
- **Lyapunov exponent λ₁≈2.73 nats/iteration: PARTIALLY CORRECTED in this phase.** A raw artifact (`plots/final_freeze/lyapunov_determinant_check.csv`, `script/final_freeze_validation.py`) confirms the map is chaotic (both exponents positive; sum λ₁+λ₂≈4.379 at ω=10, matching an independent analytical determinant check to <0.14% relative error) — this is **DATA-VERIFIED**. The specific standalone λ₁=2.73 figure, however, was **not** isolated from this raw CSV (it reports only the sum) and was not found broken out elsewhere in the areas inspected — it remains **REPORTED-ONLY**, not DATA-VERIFIED, pending either opening the `3_lyapunov.png`/`cheb_3_lyapunov.png` plots or locating a per-exponent raw file.
- Mutual information: raw MI=0.0607 bits, Miller–Madow bias=0.0469 bits, adjusted MI=0.0138 bits — **DATA-VERIFIED** directly from `sequence_statistics.csv`.

**Scope note required for the manuscript:** Step 1.1 characterizes a single
long orbit's statistical behavior under a fixed, publicly known seed. It is
**MATHEMATICALLY DERIVED/descriptive** evidence about the *map*, not about
the *cipher's* per-message, HKDF-seeded, multi-lane construction. Step 1.1
legitimately motivates the *choice* of k=14 as a candidate extraction method
and justifies rejecting k≥16 and Arccos; it cannot by itself support any
claim about the complete keyed encryption construction's security.

## 4. Phase 2 Decisions (Repo A)

Confirmed present and internally consistent: dual extraction-profile design
(`dual_profile_generator_design.md`), container V1/V2 header layout
(`container_v2_binary_specification.md`), HKDF context/profile binding
(`hkdf_profile_binding_specification.md`), backend compatibility
(`extraction_backend_compatibility_specification.md`). **All four of these
specification files exist only in Repo A** — confirmed again in this phase,
consistent with Phase 4A's earlier finding — and Repo B's VERSION=2 code
docstrings cite them without a local copy existing in Repo B. This is a
**documentation dependency, not a code dependency** (no import or runtime
reference from Repo B to Repo A exists; confirmed again by direct grep in
this phase). All architectural decisions reviewed were confirmed actually
implemented in Phase 3A (cross-checked against `isc_cipher/` source), not
left as unimplemented proposals.

## 5. Phase 3A Implementation Findings (Repo B)

Re-spot-checked directly against current source in this phase: 32-byte
master key, 16-byte nonce, HKDF-SHA-256, four streams (sbox/perm/fwd/bwd) ×
64 lanes, BURN_IN=1024 default, deterministic fdlibm trig, two extraction
backends (scalar/NumPy), Fisher-Yates + Lemire sampling, forward/backward
diffusion, ISCI container, HMAC-SHA-256, auth-before-decrypt ordering — **all
CODE-VERIFIED, matching Phase 4A's original trace exactly, no drift found**.
Default extraction remains profile 1 (`mantissa8_v1`). The full `tests/`
suite was **not re-executed in this phase** (Phase 4A already executed it:
210 passed/2 skipped — TEST-VERIFIED by that phase; re-running was judged an
expensive duplication under this phase's recomputation-over-rerun priority
and a partial rerun attempt was deliberately stopped mid-flight rather than
left unreported).

## 6. Phase 3B Statistical Findings (Repo A)

`phase_3b_results.json` was inspected directly; its headline claim ("broadly
comparable per-lane statistical behavior between extraction profiles") is
consistent with what the raw JSON structure contains, though full
field-by-field recomputation of every pooled statistic was **not** performed
in this phase (time-budgeted; spot-checked only). **The pooled chi-square
anomaly affecting some mantissa8 streams, flagged in Repo A's own
`phase_3b_validation_readiness.md`, was confirmed as flagged in that document
but was NOT independently re-investigated or resolved by this phase or any
later phase** — it remains an open item (see `limitations_and_open_questions.md`).
All of Repo A's own disclosed limitations for this phase (portable-NIST
caveat, subsampled configurations, reduced cross-stream MI sample vs. the
single-orbit MI experiment, no cryptographic independence proof, limited
performance comparisons, single-observation floating-point orbit-merge
caveat) were confirmed present in the source documents and are preserved
below in §19/§limitations rather than dropped.

## 7. Phase 4A Architecture Findings (Repo B)

Re-verified directly against `isc_cipher/{cipher,kdf,generator,isc_step,state_map,sampling,diffusion,container}.py` in this phase. Classification **"multi-stage, single-round" is confirmed correct** — no round loop exists in `cipher.py`. Encryption/decryption equations (§15 below) match the implementation exactly. The construction is confirmed to be a **generic authenticated byte cipher with a NumPy image-shape wrapper** (`cipher.py:148-175`: flatten→encrypt bytes→reshape), not a dedicated image-specific primitive — RGBA rejected, no metadata preserved, channels treated as undifferentiated contiguous bytes. Source-level traceability for every operation: see `verified_mathematical_specification.md` items 1–19.

## 8. Phase 4B Synthetic-Image Findings (Repo B)

Re-verified numerically (`numerical_verification.md`): 147 core recovery
trials / 0 failures (exact row-count match); encrypted-body entropy mean
7.9869 (exact match to reported value, recomputed from raw per-image rows);
histogram chi² mean 0.4755, 5/63 below p=0.05 (exact match); NPCR mean
99.8301% / UACI mean 33.5377% (both within 0.003 of reported "99.83/33.54" —
VERIFIED); key-sensitivity NPCR 99.6123% / UACI 33.4705% / Hamming-fraction
0.49981 (all VERIFIED to reported precision). Throughput scaling direction
(2.65→15.7 KB/s with increasing image size) confirmed by inspection, not
reduced to an exact recomputed scalar pair in this pass.

## 9. Phase 4C Natural-Image Findings (Repo B)

Phase 4C's own re-verification of Phase 4B (9/9 claims, 0 discrepancies) was
itself re-read and confirmed present with that status in
`phase4c_verification.csv`. Natural-image dataset: 12 real base images from
`skimage.data` (genuine photographs, BSD-3-Clause — confirmed not synthetic
by source inspection), 18 gray/RGB variants, manifest with SHA-256 hashes
present. Natural-image encrypted entropy mean 7.9976 (VERIFIED, recomputed
from raw rows), NPCR mean 99.751% / UACI mean 33.485% on 21 raw trials
(VERIFIED, both figures recomputed within 0.01 of the reported 99.745/33.486
— the small residual difference is consistent with the "raw trials collapsed
to 12 independent groups before CI computation" methodology described by
Phase 4C, which this phase's simpler flat-mean recomputation does not
replicate exactly but does not contradict). Fisher-Yates permutation
dominance over burn-in/diffusion cost is **confirmed with real per-component
numbers** (component_profiling.csv: ~5.7s Fisher-Yates vs. ~3.1s burn-in vs.
~20ms diffusion at 256px), strengthening this claim from Phase 4B's
pilot-level inference to Phase 4C's direct measurement. The substantial
(1.4–3.7s) run-to-run timing variance Phase 4C itself reported for nominally
identical 64×64 encryptions is **not contradicted or resolved by this
phase** — carried forward as a standing measurement-reliability caveat.

## 10. Phase 4D Structural Cryptanalysis Findings (Repo B)

Re-verified: diffusion dependency-matrix combined density = 0.995849609375
(recomputed exactly from `diffusion_analysis.json`, matching reported
"0.9958" to 4 decimal places). The exact modular-addition cancellation
counterexample (flip at j=9, cancellation at k=9 in the N=64 test case) is
present in the raw JSON as described. S-box DDT max probability 12/256
(0.0469), LAT max bias 68/256 (0.266) — present in `sbox_analysis.json`
exactly as reported, both measurably weaker than AES's designed values
(0.0156/0.125, from `fips197` in the bibliography). The 16-item claim table
(`claim_evidence_table.json`) contains exactly 16 entries, confirmed by
count. Authentication-before-decryption ordering re-confirmed by direct
source + the Phase 4A monkeypatch test description.

## 11. Phase 4E Nonce-Reuse Findings (Repo B)

Toy-solver consistent-tuple counts at M=1,2,4 known pairs — **147456, 10752,
64 — recomputed EXACTLY from raw JSON**, matching the reported figures to
the integer. The "all 64 tuples agree on the held-out target at M=4" claim
is present as a boolean field (`all_found_tuples_agree_on_held_out_target:
true`) in the raw JSON for the M=4 case specifically (and `false` for M=1/2,
confirming the reported pattern of collapse only at higher M). The
degenerate real-cipher n=1 full-codebook attack's success is recorded in
`actual_attack_results.json`; its scope caveat (no permutation/multi-position
diffusion exercised at n=1) is preserved in this report, not dropped. The
n=2 infeasibility (~32.4 hour projection) is recorded as an explicit
estimate, not a completed measurement — correctly distinguished in the raw
artifact between "attempted and measured" vs. "projected and ruled out."

## 12. Cross-Phase Contradictions and Resolutions

See `cross_phase_consistency_audit.md` for the full 10-row table. **No flat
contradiction was found between any two phases.** Several topics required
explicit scope-distinction to avoid a reader conflating them (burn-in
1,024 vs. transient 5,000; "near-universal" vs. "complete" diffusion;
descriptive NPCR/UACI vs. security proof; toy-scale vs. real-scale
nonce-reuse solvability). Two items remain genuinely **unresolved** rather
than reconciled: the Phase 3B pooled chi-square anomaly, and the exact
Lyapunov λ₁ figure.

## 13. Verified Numerical-Results Register

See `numerical_verification.md` and `results/numerical_verification_register.json`.
**16 numerical claims independently checked; 14 VERIFIED to exact or
near-exact agreement; 2 confirmed by inspection (not contradicted, just not
reduced to a single recomputed scalar in this pass); 0 DISCREPANCIES that
would alter a reported conclusion.**

## 14. Mathematical Specification Summary

See `verified_mathematical_specification.md` for all 27 equations with
source traceability, type tags (IMPLEMENTATION/ANALYSIS/THEORETICAL), and
verification status. All implementation equations are CODE-VERIFIED and the
majority are additionally TEST-VERIFIED; all analysis equations are standard
definitions with DATA-VERIFIED applications.

## 15. Claim-to-Evidence Matrix Summary

See `claim_evidence_matrix.md` for the full 17-claim table. Summary:
SUPPORTED (within stated scope) — 10 claims (C1–C10); PARTIALLY SUPPORTED —
4 claims (C5 diffusion completeness, C12 KPA/nonce-reuse, C13 CCA, C16
effective key strength); UNPROVEN — 4 claims (C11 CPA, C14 differential
cryptanalysis, C15 linear cryptanalysis, C17 overall security); CONTRADICTED
— none.

## 16. Figure/Table Readiness

See `figures_and_tables_inventory.md`. 9 figure groups READY, 1 needing
regeneration (architecture diagram — not yet drawn), 3 needing an added
variance/scope caveat before use (performance plots ×2, extraction-profile
comparison table). 9 tables inventoried; 6 READY, 3 needing additional
evidence/caveats attached (none needing fabrication or omission).

## 17. Bibliography Status

87 entries; 85/87 CrossRef-resolved with no recorded error; 2 flagged 404s
(`satellite2024review`, `arroyo2008logistic`) requiring correction before
submission. All foundational citations needed for this project's own central
claims (HKDF, HMAC, NIST SP 800-22, SHA-256, AES, and AES-GCM-SIV for the
nonce-misuse discussion) were confirmed present by direct inspection in this
phase. See `bibliography_verification.md`.

## 18. Limitations and Unresolved Questions

See `limitations_and_open_questions.md` for the full CRITICAL/IMPORTANT/OPTIONAL
breakdown. The most manuscript-relevant: no formal security proof exists; the
real-scale nonce-reuse question is open (not resolved favorably or
unfavorably); diffusion dependency is not absolute; the Phase 3B pooled
chi-square anomaly is unresolved; the Lyapunov λ₁ figure could not be
independently isolated in this pass.

## 19. Manuscript-Readiness Verdict

**READY WITH LIMITATIONS.** Full justification, strongest demonstrable
contribution, and most serious peer-review-relevant limitation are detailed
in `manuscript_readiness_assessment.md`. In brief: the implementation and
descriptive-evaluation evidence base is solid and independently
re-verifiable (§13); the cryptanalytic evidence base is honest and
appropriately bounded but incomplete by the project's own repeated
admission, and no manuscript built on this evidence may claim proven
security, IND-CPA/IND-CCA security, or resistance to differential/linear
cryptanalysis. A narrower, appropriately-bounded manuscript describing the
implementation, the descriptive statistical evaluation, and the structural
cryptanalytic investigation (including its one partial, degenerate attack
success) is fully defensible today.

## 20. Production Code Modification Confirmation

**No file in `isc_cipher/`, `isc_seq/`, `isc_eval/`, `tests/`, any
`experiments/phase4{a,b,c,d,e}/` directory in Repo B, or any file anywhere in
Repo A (`ISC_PBL`) was created, modified, or deleted during Phase 5.** All
new content is confined to `experiments/phase5/` in Repo B, as required.

---

*Stop after Phase 5, per directive. No manuscript writing was begun or
drafted. Awaiting explicit authorization before any Phase 6 / paper-writing
activity.*
