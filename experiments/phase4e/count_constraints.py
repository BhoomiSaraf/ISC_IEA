"""Part B: variable/constraint accounting and identifiability classification.

A raw equation count is NOT the same as independent-constraint count for a nonlinear modular
system with an unknown lookup table in the loop. This script reports both the naive count
(as Phase 4D did) and an honest assessment of why naive counting does not establish
identifiability here, then gives the empirically-testable question that toy_solver.py
actually answers.
"""
import json
import math
import os

import config


def naive_counts(A, n, M):
    """A = alphabet size (256 for the real cipher), n = message length, M = known pairs."""
    unknowns_raw = A + n + n + n + 2          # S table + pi + a + b + iv_f + iv_b (raw slot count)
    # Effective bits, respecting bijectivity (a permutation of k elements carries log2(k!) bits,
    # not k*log2(k) bits -- this is the "raw count overstates freedom" correction).
    bits_S = math.log2(math.factorial(A))
    bits_pi = math.log2(math.factorial(n)) if n >= 1 else 0.0
    bits_a = n * math.log2(A)
    bits_b = n * math.log2(A)
    bits_iv = 2 * math.log2(A)
    effective_bits = bits_S + bits_pi + bits_a + bits_b + bits_iv

    equations_raw = M * 2 * n                  # 2n byte-equality constraints per message (naive)
    bits_per_equation = math.log2(A)           # each byte-equality constrains log2(A) bits, AT MOST,
    # and typically far less than that in practice here because many equations share the same
    # unknown S-table entry or the same latent chain value, so they are NOT independent.
    equation_bits_upper_bound = equations_raw * bits_per_equation

    return {
        "A": A, "n": n, "M": M,
        "unknowns_raw_slot_count": unknowns_raw,
        "effective_unknown_bits_respecting_bijectivity": effective_bits,
        "equations_raw_count": equations_raw,
        "equation_bits_upper_bound_IF_independent": equation_bits_upper_bound,
        "naive_verdict_bits_only": (
            "overdetermined (upper bound)" if equation_bits_upper_bound >= effective_bits
            else "underdetermined (upper bound)"
        ),
        "why_naive_bound_is_not_proof": (
            "Each equation's 'bit budget' (log2(A)) is an UPPER bound on how many bits of "
            "unknown-material information it can reveal, not a guarantee. Equations that touch "
            "a chain position for the first time introduce a brand-new, previously-unconstrained "
            "latent chain value (u^(i)_k) at the SAME time as they touch a point of S -- so many "
            "early-position equations are consistent with many (S-point, u-value) pairs "
            "simultaneously and reveal close to ZERO net bits until later equations cross-link "
            "the same S domain point from a different chain path. Whether that cross-linking "
            "happens frequently enough to pin down S is an empirical question about the search "
            "space, not something the raw bit count can settle."
        ),
        "identifiability_classes_considered": [
            "1. underdetermined: multiple materially different (S,pi,a,b,iv) tuples fit all M pairs "
            "   and disagree on an unseen target.",
            "2. overdetermined_inconsistent: not applicable here by construction (we only ever test "
            "   pairs actually produced by a real/toy encryption, so a consistent tuple always exists).",
            "3. overdetermined_unique: exactly one tuple (up to irrelevant relabeling) fits all M pairs "
            "   and it is the true tuple (or a functional equivalent that agrees with it everywhere).",
            "4. overdetermined_multiple_equivalent: more than one tuple fits all M known pairs, but "
            "   all surviving candidates agree on the unseen target (functional equivalence for "
            "   decryption purposes even though the raw material differs).",
            "5. computationally_hard_despite_overdetermined: a unique/near-unique solution may exist "
            "   in principle, but no tractable search method was available to find it within budget.",
        ],
        "empirical_question_for_toy_solver": (
            "For small (A, n), does an exhaustive/backtracking search over ALL consistent "
            "(S,pi,a,b,iv_f,iv_b) tuples collapse to a single tuple (or a set that all agree on a "
            "held-out target) as M increases from 1 to a modest number? This is tested directly, "
            "not assumed from the bit count above."
        ),
    }


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    # Real-cipher scale, for reference only -- NOT claimed solvable by this count alone.
    for M in (1, 2, 4, 8, 16):
        rows.append(naive_counts(256, 4096, M))   # 64x64 gray image-sized n, illustrative
    # Toy scales actually used by toy_solver.py
    for A, n, M in [(4, 3, 1), (4, 3, 2), (4, 3, 4), (8, 4, 2), (8, 4, 4), (8, 4, 8)]:
        rows.append(naive_counts(A, n, M))

    path = os.path.join(config.RESULTS_DIR, "constraint_counts.json")
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)
    print("wrote", path)
    for r in rows:
        print(f"A={r['A']:>4} n={r['n']:>5} M={r['M']:>3}  "
              f"eff_unknown_bits={r['effective_unknown_bits_respecting_bijectivity']:.1f}  "
              f"eq_bits_upper={r['equation_bits_upper_bound_IF_independent']:.1f}  "
              f"naive={r['naive_verdict_bits_only']}")


if __name__ == "__main__":
    main()
