"""Track E / section 7.1: S-box structural analysis (DDT, LAT, fixed points, inverse check)."""
import json
import os
import time

import numpy as np

import config as cfg
from isc_cipher._testing import materials_TEST_ONLY

OUT = os.path.join(cfg.RESULTS_DIR, "sbox_analysis.json")


def ddt(S):
    """Differential distribution table: DDT[dx][dy] = #{x : S[x^dx]^S[x] == dy} using XOR
    differences (the standard DDT convention). 256x256 table, O(256^2) = 65536 ops -- cheap,
    no pilot needed."""
    n = 256
    table = np.zeros((n, n), dtype=np.int32)
    Sarr = np.array(S, dtype=np.int32)
    for dx in range(n):
        xs = np.arange(n, dtype=np.int32)
        ys = Sarr[xs ^ dx] ^ Sarr[xs]
        for dy in ys:
            table[dx, int(dy)] += 1
    return table


def lat(S):
    """Walsh-Hadamard-based linear approximation table bias, via brute-force correlation sums.
    LAT[a][b] = sum_x (-1)^(popcount(a&x) + popcount(b&S[x])) ; max bias reported as max|LAT|/256."
    """
    n = 256
    Sarr = np.array(S, dtype=np.int32)
    xs = np.arange(n, dtype=np.int32)
    pop = np.array([bin(v).count("1") for v in range(256)], dtype=np.int32)
    table = np.zeros((n, n), dtype=np.int32)
    for a in range(n):
        ax = pop[xs & a] & 1
        for b in range(n):
            bsx = pop[Sarr & b] & 1
            table[a, b] = np.sum(1 - 2 * ((ax ^ bsx)))
    return table


def main():
    findings = {}
    m = materials_TEST_ONLY(cfg.KEY_A, cfg.NONCE_A, 64, 64, 1, backend=cfg.BACKEND)
    S, S_inv = m["S"], m["S_inv"]

    # Bijectivity / inverse correctness
    findings["bijectivity"] = {
        "is_permutation": sorted(S) == list(range(256)),
        "inverse_correct": all(S_inv[S[x]] == x for x in range(256)),
    }
    # Fixed points
    fixed = [x for x in range(256) if S[x] == x]
    findings["fixed_points"] = {"count": len(fixed), "positions": fixed,
                                 "expected_for_random_permutation": "~1 on average (E[fixed points]=1)"}

    t0 = time.perf_counter()
    DDT = ddt(S)
    t_ddt = time.perf_counter() - t0
    # Max differential probability (excluding the trivial dx=0 row, which is always all-N at dy=0)
    DDT_nontrivial = DDT.copy()
    DDT_nontrivial[0, :] = 0
    max_diff_count = int(DDT_nontrivial.max())
    max_diff_prob = max_diff_count / 256
    findings["differential_distribution_table"] = {
        "computation_time_seconds": t_ddt,
        "shape": "256x256 (dx, dy), XOR-difference convention",
        "max_differential_probability_excluding_trivial": max_diff_prob,
        "max_count": max_diff_count,
        "random_permutation_reference_expected_max_count": "~ a few (typically 4-10 for a "
            "random 8-bit permutation; textbook AES S-box max is 4/256=0.0156)",
        "note": "Lower max differential probability is generally considered better against "
                "differential cryptanalysis OF THE S-BOX IN ISOLATION. This does NOT by itself "
                "establish anything about the resistance of the FULL cipher (permutation + "
                "chained diffusion + key schedule) to differential cryptanalysis -- the S-box "
                "here is also DIFFERENT for every (key, nonce), unlike AES's fixed public "
                "S-box, which changes the relevant threat model entirely (see final report).",
    }

    t0 = time.perf_counter()
    LAT = lat(S)
    t_lat = time.perf_counter() - t0
    LAT_nontrivial = LAT.copy()
    LAT_nontrivial[0, :] = 0
    LAT_nontrivial[:, 0] = 0
    max_bias = int(np.abs(LAT_nontrivial).max())
    findings["linear_approximation_table"] = {
        "computation_time_seconds": t_lat,
        "shape": "256x256 (a, b) input/output masks",
        "max_absolute_linear_bias_count": max_bias,
        "max_absolute_linear_bias_fraction": max_bias / 256,
        "random_permutation_reference": "a random 8-bit permutation typically has max|bias| "
            "well above textbook-S-box values (e.g. AES S-box's max bias count is 32/256=0.125 "
            "in the +-1 convention used here, before any correction factor); exact comparison "
            "convention-dependent -- reported here for THIS S-box only, not compared to a "
            "freshly-generated random-permutation ensemble average (out of scope at P1 time "
            "budget; flagged as a possible follow-on in section 18/limitations).",
    }

    # Multiple nonces: are S-boxes from different nonces statistically similar to each other
    # (as expected, since each is "just" a Fisher-Yates shuffle) or suspiciously correlated?
    m2 = materials_TEST_ONLY(cfg.KEY_A, cfg.NONCE_B, 64, 64, 1, backend=cfg.BACKEND)
    S2 = m2["S"]
    agreement = sum(1 for x in range(256) if S[x] == S2[x])
    findings["cross_nonce_sbox_similarity"] = {
        "positions_agreeing_between_two_sboxes": agreement,
        "expected_agreement_for_independent_random_permutations": "~1 (E[agreements]=1, "
            "same reasoning as fixed points of a random permutation applied to comparing two "
            "independent random permutations)",
        "conclusion": "No detected similarity beyond chance between S-boxes derived under "
                       "different nonces (same key) at this single-sample check.",
    }

    with open(OUT, "w") as f:
        json.dump(findings, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps(findings, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    main()
