"""Consolidates the pilot/scale-up arithmetic already recorded by toy_solver.py and
actual_attack_harness.py into a single benchmarks summary, and explicitly records the
solver-availability limitation (no SMT/SAT solver installed) for Part F's failure-type
classification. Runs no new experiments."""
import json
import os

import config


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    try:
        import z3  # noqa: F401
        z3_available = True
    except ImportError:
        z3_available = False

    summary = {
        "smt_solver_availability": {
            "z3_available": z3_available,
            "note": (
                "z3-solver is NOT installed in this environment, and this phase's sandbox "
                "denies ad-hoc `pip install` (classified as an oversight-risk action by the "
                "harness). This is a genuine TOOLING limitation, recorded explicitly per "
                "Part F category 3 (solver encoding/availability limitations) -- it is the "
                "reason brute-force search (exact but combinatorially limited) was used "
                "instead of SMT/SAT/CP solving for Part C/D, and the reason real-scale "
                "(alphabet=256) structural material recovery (S, pi, a, b) was not attempted "
                "via solver search at all (see actual_attack_harness.py's codebook-based "
                "approach instead, which sidesteps needing to solve for internal structure)."
            ),
        },
        "toy_solver_scale_limit": (
            "Exhaustive brute force (with early-abort pruning) was tractable up to A=4, n=3 "
            "(naive search space 9,437,184) within ~55s per instance. Extrapolated cost grows "
            "as n! * A! * A^(2n) * A^2 -- e.g. A=5,n=3 or A=4,n=4 would already run into tens "
            "of minutes to hours by the measured per-candidate cost (~3.1 microseconds), and "
            "the REAL cipher's A=256 is astronomically beyond brute-force reach (256! alone "
            "has ~1684 bits of entropy) regardless of n."
        ),
        "real_cipher_codebook_limit": (
            "Measured directly in actual_attack_harness.py: ~2s fixed cost per encryption "
            "call (independent of message size, matching Phase 4B/4C's burn-in-dominated "
            "finding). A full n=1 codebook (256 queries) costs ~512s and was completed. A full "
            "n=2 codebook (65536 queries) would cost on the order of 36 hours by direct "
            "extrapolation -- not attempted, reported as infeasible within this phase's "
            "budget rather than left unexplained."
        ),
    }
    path = os.path.join(config.RESULTS_DIR, "solver_benchmarks.json")
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print("wrote", path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
