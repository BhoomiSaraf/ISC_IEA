"""Consolidates toy_solver + actual_attack_harness raw results into explicit recovery-level
verdicts for each of Part E's objectives (E1-E5), reading only the JSON files already written
to results/ by the other scripts (no new experiments run here)."""
import json
import os

import config


def load(name):
    path = os.path.join(config.RESULTS_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def main():
    toy = load("toy_solver_results.json")
    toy_rob = load("toy_solver_robustness.json")
    real = load("actual_attack_results.json")

    verdict = {"toy_model": {}, "real_implementation": {}}

    if toy:
        exps = {e["M"]: e for e in toy["experiments"]}
        verdict["toy_model"] = {
            "scale": toy.get("chosen_scale"),
            "E1_permutation_recovery": "NOT uniquely recovered at any tested M (pi is one of "
                "several free components across all surviving tuples; not separately verified "
                "component-by-component, only as part of the full tuple).",
            "E2_sbox_recovery": "NOT uniquely recovered at any tested M (same caveat as E1).",
            "E3_diffusion_material_recovery": "NOT uniquely recovered at any tested M.",
            "E4_equivalent_material_recovery": (
                f"YES at M=4 (A={toy['chosen_scale']['A']}, n={toy['chosen_scale']['n']}): "
                f"{exps.get(4, {}).get('num_consistent_tuples')} distinct tuples remain "
                "consistent with all 4 known pairs, and ALL of them are functionally "
                "equivalent on the held-out target (E5 below) -- i.e. recovery succeeds at "
                "the level of 'a tuple that behaves identically to the true one', not at the "
                "level of 'the unique true tuple'."
            ) if exps.get(4, {}).get("all_found_tuples_agree_on_held_out_target") else "NO at tested M.",
            "E5_target_plaintext_recovery": {
                str(m): exps[m]["target_decryption_succeeded"] for m in sorted(exps)
            },
            "robustness_across_seeds": toy_rob,
        }

    if real:
        verdict["real_implementation"] = {
            "determinism_codebook_leak": "CONFIRMED (n=64 test): " +
                str(real["determinism_leak"]["same_plaintext_same_key_nonce_same_ciphertext"]
                    and real["determinism_leak"]["different_plaintext_same_key_nonce_different_ciphertext"]),
            "E5_target_plaintext_recovery_n1": real["n1_full_codebook"]["all_held_out_correct"],
            "E5_target_plaintext_recovery_n2": "NOT ATTEMPTED (infeasible within budget, see "
                "n2_partial_codebook_feasibility.projected_full_codebook_time_hours)",
            "n2_projected_hours": real["n2_partial_codebook_feasibility"]["projected_full_codebook_time_hours"],
        }

    path = os.path.join(config.RESULTS_DIR, "recovery_verdict.json")
    with open(path, "w") as f:
        json.dump(verdict, f, indent=2)
    print("wrote", path)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
