"""Runs the full Phase 4E pipeline in order. Each script is independently runnable too."""
import subprocess
import sys

STEPS = [
    "derive_constraints.py",
    "count_constraints.py",
    "toy_model.py",
    "toy_solver.py",
    "toy_solver_robustness.py",
    "actual_attack_harness.py",
    "solver_benchmarks.py",
    "recovery_verifier.py",
    "analyse_results.py",
]

if __name__ == "__main__":
    for step in STEPS:
        print(f"=== {step} ===")
        subprocess.run([sys.executable, step], check=True)
