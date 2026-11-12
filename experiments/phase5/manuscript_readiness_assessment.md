# Phase 5 — Manuscript Readiness Assessment

## Verdict: **READY WITH LIMITATIONS**

A manuscript can be written from this project's evidence base, but only with the
claim restrictions established in `claim_evidence_matrix.md` and the disclosures
in `limitations_and_open_questions.md` treated as mandatory, not optional.

## Justification

**What is solid:** The implementation has been traced end-to-end against source
(Phase 4A, re-spot-checked here), the encryption/decryption equations are
verified exact inverses (test-executed, not merely derived), and a large,
reproducible body of descriptive statistical evidence exists across synthetic
images (Phase 4B), real natural images (Phase 4C), and structural/cryptanalytic
probing (Phase 4D/4E). Numerical re-verification in this phase found 14/16
spot-checked claims to match raw data exactly, with the remaining 2 confirmed
by inspection rather than full contradiction. This is a genuinely defensible,
reproducible evidence base for a *descriptive implementation-and-evaluation*
paper.

**What prevents an unqualified READY:** No phase of this project — including
this one — established a formal security argument, and Phase 4E's own central
question (real-scale nonce-reuse recoverability) remains open specifically
because the necessary tooling (an SMT/SAT solver) was unavailable, not because
the question was answered favorably. A paper that asserted security conclusions
beyond what `claim_evidence_matrix.md` licenses would not be defensible under
peer review.

**What would make it NOT READY:** none of the unresolved issues found
individually invalidate the project's actual, narrower, defensible
contribution (below) — they only constrain how that contribution may be
worded. No contradiction was found between phases that could not be explained
by scope differences (see `cross_phase_consistency_audit.md`).

## Strongest demonstrable contribution

An implementation-grounded, source-code-verified, and experimentally
reproducible **characterization and evaluation of a novel chaotic-map-based
authenticated image-encryption construction**, including: (a) exact
source-to-equation traceability for every pipeline stage; (b) a reproducible
descriptive statistical evaluation (entropy, histogram uniformity,
correlation, NPCR/UACI, key sensitivity) across both synthetic and real
natural images; (c) a structural cryptanalytic audit that goes beyond
descriptive statistics to construct an exact dependency matrix and S-box
differential/linear characteristics; and (d) a genuine (not merely
theoretical) attempt to build a nonce-reuse recovery attack, including one
degenerate case that actually succeeded. The combination of (c) and (d) — a
project that tried to break its own construction and reported an honest,
partial result rather than only favorable statistics — is the strongest and
most distinctive part of the contribution.

## Most serious limitation for peer review

A reviewer would most likely focus on **the absence of any full-scale
chosen/known-plaintext or differential/linear cryptanalytic result for the
real construction** (only a standalone S-box was analyzed at that depth;
Phase 4E's attack succeeded only in a degenerate n=1 case and was otherwise
blocked by tooling and runtime, not by demonstrated cipher strength). This is
exactly the kind of gap that must be stated as a limitation, not minimized —
and this project's own phases already do so explicitly, which should be
preserved rather than edited out during manuscript writing.

## Experiments genuinely necessary before stronger claims (not before writing a bounded paper)

1. Full-scale (or larger-toy-scale) nonce-reuse solvability with working
   SMT/SAT tooling.
2. A full-chain (not standalone-S-box) differential/linear characteristic
   search.
3. Re-investigation of the Phase 3B pooled chi-square anomaly.

None of these are required to write a *defensible, appropriately bounded*
paper about what this project actually demonstrates — they are required only
to make stronger security claims than the current evidence supports.
