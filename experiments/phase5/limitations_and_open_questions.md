# Phase 5 — Limitations and Open Questions

## CRITICAL (would invalidate a central claim or break reproducibility if unaddressed)

1. **No formal security proof or external peer-reviewed cryptanalysis exists** for the custom permutation + modular-additive-diffusion construction. Every phase of this project (4A, 4D, 4E) independently arrived at the same conclusion. A manuscript must not claim or imply overall cryptographic security.
2. **The real-scale (256-byte alphabet, realistic message length) nonce-reuse known-plaintext question is genuinely unresolved** (Phase 4E). Only a toy-scale model and a degenerate single-byte real-cipher case were actually tested; no SMT/SAT solver was available to attempt the real scale.
3. **Diffusion dependency is not 100% complete** — an exact, reproducible counterexample exists (Phase 4D). Any manuscript claim of "full diffusion" or "complete avalanche" must be qualified.

## IMPORTANT (should be strengthened or explicitly disclosed, but can be handled by narrowing claims)

4. The portable/`nistrng`-based NIST SP 800-22 implementation used in Step 1.1 is explicitly not equivalent to the official NIST STS reference implementation, and documented software defects in `nistrng` (BinaryMatrixRank mutation, OverlappingTemplate negative-probability issue) were noted by the project's own Step 1.1 closure report. Coverage was also incomplete relative to the full 15-test NIST battery.
5. The Phase 3B pooled chi-square anomaly affecting some mantissa8 streams was flagged in Repo A's own validation-readiness document and was **never re-investigated or resolved by any subsequent phase**, including this one (time-budgeted out).
6. The single-largest-Lyapunov-exponent figure (λ₁≈2.73 nats/iteration) used to justify burn-in sufficiency could not be independently isolated from a raw artifact in this phase — only the *sum* of the two exponents (≈4.38 at ω=10, confirming chaos) was found in raw form.
7. Performance/timing measurements across Phase 4B and 4C carry substantial, partially unexplained run-to-run variance on the test hardware (Phase 4C's own finding) — all absolute timing figures should be treated as order-of-magnitude, not precise, in any manuscript.
8. The S-box's standalone differential/linear uniformity (DDT 0.0469, LAT 0.266) is measurably weaker than a designed block-cipher S-box (AES: 0.0156 / 0.125). Whether per-message freshness compensates against a motivated attacker is untested.
9. Natural-image coverage (Phase 4C) used only `skimage.data`'s bundled sample photographs (12 base images) — real, openly licensed natural images, but a narrow and non-diverse source; broader natural-image validation (e.g. USC-SIPI, Kodak) was not obtained due to network/time constraints, and this was explicitly disclosed by Phase 4C rather than hidden.
10. No formal differential or linear cryptanalytic characteristic was constructed through the *full* permutation+diffusion chain — only the standalone S-box was analyzed at that level of rigor.

## OPTIONAL (would improve the paper without being essential to a defensible, narrower contribution)

11. Larger natural-image datasets and more extraction-profile-comparison trials at the natural-image level (Phase 4C's k14 subset was only 4 images).
12. A working SMT/SAT solving capability to extend Phase 4E's toy-scale identifiability result toward the real cipher's scale.
13. A dedicated Lyapunov-exponent re-computation isolating λ₁ from λ₂, to settle the 2.73-nats figure definitively.
14. Cross-platform reproducibility testing beyond the Windows/WSL-Ubuntu Gate R comparison already referenced in Repo A.
15. Resolution of the two 404-flagged bibliography entries (`satellite2024review`, `arroyo2008logistic`).

## Explicitly preserved negative/anomalous findings (not suppressed)

- The degenerate n=1 real-cipher nonce-reuse attack that **succeeded** (Phase 4E) — this is unfavorable to an uncritical reading of the cipher's strength and is preserved verbatim rather than downplayed.
- The diffusion dependency matrix's 0.42% non-dependent positions (Phase 4D).
- The S-box's below-AES-level DDT/LAT metrics (Phase 4D).
- Phase 4C's measurement-variance anomaly, chased down but not fully explained (attributed to environment, not confirmed).
- The Phase 3B pooled chi-square anomaly, carried forward as unresolved rather than silently dropped.
