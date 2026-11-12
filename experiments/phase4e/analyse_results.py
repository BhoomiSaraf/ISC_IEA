"""Aggregates all results/*.json into a single results/phase4e_summary.json and prints the
headline numbers used in the final report. Runs no new experiments."""
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
    summary = {
        "constraint_formulation": load("constraint_formulation.json"),
        "constraint_counts": load("constraint_counts.json"),
        "toy_solver_results": load("toy_solver_results.json"),
        "toy_solver_robustness": load("toy_solver_robustness.json"),
        "actual_attack_results": load("actual_attack_results.json"),
        "solver_benchmarks": load("solver_benchmarks.json"),
        "recovery_verdict": load("recovery_verdict.json"),
    }
    path = os.path.join(config.RESULTS_DIR, "phase4e_summary.json")
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print("wrote", path)


if __name__ == "__main__":
    main()
