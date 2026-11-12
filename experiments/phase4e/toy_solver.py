"""Part C: exact brute-force identifiability solver for the toy model.

No SMT/SAT solver is available in this environment (z3-solver is not installed, and this
phase's environment denies ad-hoc package installation -- documented here as a genuine
tooling limitation per Part F's "solver encoding limitations" category, not worked around).
This script therefore uses EXHAUSTIVE brute-force search with early-abort pruning, which is
exact (no approximation, no heuristic incompleteness) but only tractable at small (A, n).

Search space size (naive, before pruning):
    n! (pi) * A! (S) * A^n (a) * A^n (b) * A (iv_f) * A (iv_b)

Early-abort strategy: for each candidate secret tuple, simulate the FULL forward pass (cheap),
then the backward pass ONE POSITION AT A TIME, comparing the computed ciphertext byte against
the known target immediately and aborting the candidate the instant any byte disagrees, across
however many known messages are supplied, in order. This does not change the exactness of the
search; it only prunes doomed candidates as early as possible.
"""
import itertools
import json
import os
import time

import config
import toy_model as tm


def candidate_consistent_with(secret_like, pairs):
    """pairs: list of (p, c) toy-alphabet lists. Returns True iff encrypt(secret_like, p) == c
    for every pair, with early abort inside each message's backward pass."""
    A = secret_like["A"]
    pi = secret_like["pi"]
    S = secret_like["S"]
    a = secret_like["a"]
    b = secret_like["b"]
    iv_f = secret_like["iv_f"]
    iv_b = secret_like["iv_b"]
    for p, c_target in pairs:
        q = tm.apply_permutation(p, pi)
        u = tm.forward(q, a, S, iv_f, A)
        nxt = iv_b
        n = len(u)
        for k in range(n - 1, -1, -1):
            nxt = S[(u[k] + nxt + b[k]) % A]
            if nxt != c_target[k]:
                return False
        # full message matched (loop completed without early return)
    return True


def brute_force(A, n, pairs, time_budget_s=None, verbose=False):
    """Exhaustive search over (pi, S, a, b, iv_f, iv_b). Returns list of all consistent tuples
    found (each as a plain dict), plus timing/exhaustion metadata. If time_budget_s is hit
    before the search space is exhausted, returns what was found so far with exhausted=False.
    """
    t0 = time.time()
    found = []
    n_tested = 0
    exhausted = True
    positions = list(range(n))
    elems = list(range(A))

    for pi in itertools.permutations(positions):
        for S in itertools.permutations(elems):
            for iv_f in elems:
                for iv_b in elems:
                    for a in itertools.product(elems, repeat=n):
                        for b in itertools.product(elems, repeat=n):
                            n_tested += 1
                            cand = {"A": A, "n": n, "pi": list(pi), "S": list(S),
                                     "a": list(a), "b": list(b), "iv_f": iv_f, "iv_b": iv_b}
                            if candidate_consistent_with(cand, pairs):
                                found.append(cand)
                            if time_budget_s is not None and (time.time() - t0) > time_budget_s:
                                exhausted = False
                                break
                        if not exhausted:
                            break
                    if not exhausted:
                        break
                if not exhausted:
                    break
            if not exhausted:
                break
        if not exhausted:
            break

    elapsed = time.time() - t0
    if verbose:
        print(f"A={A} n={n} M={len(pairs)}  tested={n_tested}  found={len(found)}  "
              f"elapsed={elapsed:.2f}s  exhausted={exhausted}")
    return {"found": found, "n_tested": n_tested, "elapsed_s": elapsed, "exhausted": exhausted}


def pilot_and_scale(seed=1):
    """Pilot the smallest instance, report runtime, then scale up only as far as the pilot
    arithmetic justifies within a short (<=120s per instance) budget. This is the required
    'pilot before expensive experiments' step for Part C."""
    report = {"pilots": [], "experiments": []}

    # --- Pilot: smallest possible non-degenerate instance ---
    A, n = 3, 2
    secret = tm.make_secret(A, n, seed=seed)
    p1 = [0, 1]
    pairs = [(p1, tm.encrypt(secret, p1))]
    t0 = time.time()
    res = brute_force(A, n, pairs, time_budget_s=60, verbose=True)
    pilot_time = time.time() - t0
    naive_space = 2 * 6 * (A ** n) * (A ** n) * A * A  # n!=2, A!=6
    report["pilots"].append({"A": A, "n": n, "M": 1, "naive_space": naive_space,
                               "measured_s": pilot_time, "n_tested": res["n_tested"],
                               "n_found": len(res["found"])})
    print(f"PILOT A={A} n={n} M=1: naive_space={naive_space} measured={pilot_time:.3f}s "
          f"tested={res['n_tested']} found={len(res['found'])}")

    # Extrapolate: naive_space scales as A! * A^(2n) (pi fixed small, dominated by A!*A^2n).
    # Decision rule: only attempt an instance whose naive_space is within ~50x the pilot's,
    # keeping projected runtime under ~90s. Document the arithmetic explicitly.
    per_candidate_cost = pilot_time / max(res["n_tested"], 1)
    decisions = []
    for A2, n2 in [(3, 3), (4, 2), (4, 3), (5, 2)]:
        space2 = (
            __import__("math").factorial(n2) * __import__("math").factorial(A2)
            * (A2 ** n2) * (A2 ** n2) * A2 * A2
        )
        projected_s = space2 * per_candidate_cost
        decisions.append({"A": A2, "n": n2, "naive_space": space2, "projected_s": projected_s})
    report["scale_decision_arithmetic"] = {
        "per_candidate_cost_s": per_candidate_cost,
        "candidates": decisions,
    }
    print("Scale-up projections (per-candidate cost = "
          f"{per_candidate_cost*1e6:.3f} microseconds):")
    for d in decisions:
        print(f"  A={d['A']} n={d['n']}: naive_space={d['naive_space']:,} "
              f"projected={d['projected_s']:.1f}s")

    # Pick the largest instance projected under 90s as the "real" identifiability experiment.
    budget_s = 90
    chosen = max([d for d in decisions if d["projected_s"] <= budget_s],
                 key=lambda d: d["naive_space"], default=decisions[0])
    report["chosen_scale"] = chosen
    print(f"Chosen scale for main experiment: A={chosen['A']} n={chosen['n']} "
          f"(projected {chosen['projected_s']:.1f}s, budget {budget_s}s)")

    A, n = chosen["A"], chosen["n"]
    for M in (1, 2, 4):
        secret = tm.make_secret(A, n, seed=seed)
        # Use M distinct known plaintexts plus one held-out target.
        import random
        rng = random.Random(seed * 1000 + M)
        all_msgs = list(itertools.product(range(A), repeat=n))
        rng.shuffle(all_msgs)
        known_p = [list(x) for x in all_msgs[:M]]
        target_p = list(all_msgs[M])  # held out, NOT given to the solver
        pairs = [(p, tm.encrypt(secret, p)) for p in known_p]
        target_c = tm.encrypt(secret, target_p)

        res = brute_force(A, n, pairs, time_budget_s=budget_s, verbose=True)
        # Check generalisation: for every found candidate tuple, does it predict target_c from
        # target_p? (Equivalent-material success per Part E4/E5.)
        agreements = []
        for cand in res["found"]:
            predicted_c = tm.encrypt(cand, target_p)
            agreements.append(predicted_c == target_c)
        all_agree = len(res["found"]) > 0 and all(agreements)
        any_agree = any(agreements)
        exp = {
            "A": A, "n": n, "M": M, "seed": seed,
            "n_tested": res["n_tested"], "n_found": len(res["found"]),
            "exhausted": res["exhausted"], "elapsed_s": res["elapsed_s"],
            "unique_true_tuple_found": len(res["found"]) == 1,
            "num_consistent_tuples": len(res["found"]),
            "all_found_tuples_agree_on_held_out_target": all_agree,
            "at_least_one_found_tuple_agrees_on_held_out_target": any_agree,
            "target_decryption_succeeded": all_agree,  # the real success criterion
        }
        report["experiments"].append(exp)
        print(f"  M={M}: found={len(res['found'])} exhausted={res['exhausted']} "
              f"target_decryption_succeeded={exp['target_decryption_succeeded']}")

    return report


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    report = pilot_and_scale(seed=1)
    path = os.path.join(config.RESULTS_DIR, "toy_solver_results.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print("wrote", path)


if __name__ == "__main__":
    main()
