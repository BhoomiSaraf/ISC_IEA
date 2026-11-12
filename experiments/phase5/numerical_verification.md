# Phase 5 — Numerical Verification Register

Full machine-readable register: `results/numerical_verification_register.json`
(produced by `verification/recompute_numerics.py`, which reads only the raw
CSV/JSON files under `experiments/phase4b|4c|4d|4e/results/` and writes only
to `experiments/phase5/results/`).

## Method

For each claim, the script independently recomputes the aggregate (mean,
count, density, etc.) directly from the raw per-trial rows/fields and
compares it to the value reported in the corresponding phase's narrative
summary. A match within floating-point tolerance is marked VERIFIED.

## Results: 16 claims checked, 14 VERIFIED, 2 INSPECTED-NOT-RECOMPUTED-TO-SCALAR

| Claim ID | Metric | Reported | Recomputed | Status |
|---|---|---|---|---|
| 4B-A1 | n_trials (core recovery CSV) | 147 | 147 | VERIFIED |
| 4B-A2 | n_failures (core) | 0 | 0 | VERIFIED |
| 4B-A3 | n_edgecase_rows | 5 | 5 | VERIFIED |
| 4B-E1 | NPCR mean % | 99.83 | 99.8301 | VERIFIED |
| 4B-E2 | UACI mean % | 33.54 | 33.5377 | VERIFIED |
| 4B-F1 | key-sensitivity NPCR mean % | 99.61 | 99.6123 | VERIFIED |
| 4B-F2 | key-sensitivity UACI mean % | 33.47 | 33.4705 | VERIFIED |
| 4B-F3 | key-sensitivity Hamming fraction mean | 0.4998 | 0.49981 | VERIFIED |
| 4B-H1 | throughput range 2.65→15.7 KB/s | qualitative | inspected in `experiment_H_performance.csv`, direction confirmed | **INSPECTED, not reduced to single recomputed scalar** |
| 4C-V1 | Phase 4B claims independently verified by Phase 4C | 9/9 | 9/9 | VERIFIED (string match) |
| 4C-NU1 | natural-image NPCR mean % | 99.745 | 99.751 | VERIFIED |
| 4C-NU2 | natural-image UACI mean % | 33.486 | 33.485 | VERIFIED |
| 4C-NU3 | n raw NPCR/UACI trials | 21 | 21 | VERIFIED |
| 4D-C1 | n security claims in claim-evidence table | 16 | 16 | VERIFIED |
| 4D-D1 | combined diffusion dependency-matrix density | 0.9958 | 0.99585 | VERIFIED |
| 4E-T1 | toy-solver consistent-tuple counts at M=1,2,4 | [147456, 10752, 64] | [147456, 10752, 64] | VERIFIED (exact) |

## Notes and caveats

1. **4B-H1 (throughput)**: `experiment_H_performance.csv` contains per-size,
   per-repetition timing rows; the narrative's "2.65 → 15.7 KB/s" figure is a
   derived min/max across image sizes using a specific throughput-column
   convention. This phase confirmed the qualitative scaling direction
   (throughput increases with image size, consistent with amortized burn-in
   cost) by inspection but did not re-derive the exact two endpoint numbers
   from a single formula in this pass — classified **DATA-VERIFIED
   (qualitative)**, not a byte-for-byte scalar match.
2. **4C-V1**: Phase 4C's own `phase4b_verification.csv` already contains a
   self-reported "VERIFIED" status column for its 9 checked claims against
   Phase 4B; this phase re-read that file and confirms all 9 rows carry that
   status, but did not re-derive Phase 4B's numbers a third time independently
   (that would duplicate Phase 4C's own verification pass without new
   evidence) — classified **DATA-VERIFIED (second-hand confirmation of a
   first-hand recomputation)**.
3. All other 14 claims above were recomputed from raw per-row data with no
   intermediate reliance on any phase's own summary arithmetic, and matched
   to within numerical tolerance (≤0.01 absolute on percentage-scale metrics,
   exact integer match on counts).
4. **No discrepancy that would alter a reported conclusion was found.** The
   two "not reduced to scalar" items are inspection-level confirmations, not
   contradictions.
5. Values **not independently recomputed in this phase** (time-budgeted; see
   `limitations_and_open_questions.md`): Step 1.1's Lyapunov exponent figure
   (2.73 nats/iteration — REPORTED-ONLY, no raw computation artifact located
   in Repo A); Phase 3B's full pooled chi-square/MI/NIST aggregate recomputation
   (spot-checked against `phase_3b_results.json` rather than fully
   re-derived field by field); Phase 4A's full implementation-audit claims
   (re-spot-checked against current source rather than re-executing the
   entire Phase 4A process); the full `tests/` suite (Phase 4A already
   executed it to 210 passed/2 skipped; re-running was judged an expensive,
   non-value-adding duplication under this phase's time budget and a partial
   rerun was deliberately stopped rather than left to finish uninspected).
