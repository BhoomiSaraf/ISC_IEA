"""Robustness check for the toy_solver main result: repeat the A=4,n=3 experiment across
multiple random seeds and M values to confirm the M=4 functional-recovery result (and the
M=1/M=2 failure) is not a one-off lucky/unlucky instance (spec Part C: "run multiple toy
instances"). Reuses toy_solver.brute_force directly; does not re-derive the algorithm."""
import itertools
import json
import os
import random
import time

import config
import toy_model as tm
from toy_solver import brute_force


def run(A, n, M, seed, budget_s=90):
    secret = tm.make_secret(A, n, seed=seed)
    rng = random.Random(seed * 9973 + M)
    all_msgs = [list(x) for x in itertools.product(range(A), repeat=n)]
    rng.shuffle(all_msgs)
    known_p = all_msgs[:M]
    target_p = all_msgs[M]
    pairs = [(p, tm.encrypt(secret, p)) for p in known_p]
    target_c = tm.encrypt(secret, target_p)
    res = brute_force(A, n, pairs, time_budget_s=budget_s, verbose=False)
    agreements = [tm.encrypt(cand, target_p) == target_c for cand in res["found"]]
    return {
        "A": A, "n": n, "M": M, "seed": seed,
        "n_found": len(res["found"]), "exhausted": res["exhausted"],
        "elapsed_s": res["elapsed_s"],
        "all_agree_on_held_out_target": len(res["found"]) > 0 and all(agreements),
    }


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    rows = []
    for seed in (2, 3, 4):
        for M in (1, 4):
            t0 = time.time()
            r = run(4, 3, M, seed)
            r["wall_s"] = time.time() - t0
            rows.append(r)
            print(r)
    path = os.path.join(config.RESULTS_DIR, "toy_solver_robustness.json")
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)
    print("wrote", path)


if __name__ == "__main__":
    main()
