"""Run the full Phase 4C pipeline in the recommended order (section 11 of
the spec). Each step is also independently runnable as its own script.

NOTE: performance profiling/benchmarking steps are run LAST and are not
run concurrently with anything else in this process (this script itself is
single-process/sequential), consistent with the "do not run tracks
concurrently" requirement.
"""
import verify_phase4b
import prepare_dataset
import experiment_natural_images
import experiment_npcr_uaci
import profile_components
import benchmark_scaling
import analyse_results


def main():
    print("=== 1. Verify Phase 4B artifacts ===")
    verify_phase4b.verify()

    print("\n=== 2. Prepare natural-image dataset ===")
    prepare_dataset.prepare()

    print("\n=== 3. Natural-image correctness/entropy/histogram/correlation ===")
    experiment_natural_images.run()

    print("\n=== 4. NPCR/UACI confirmatory experiment ===")
    experiment_npcr_uaci.run()

    print("\n=== 5. Component-level profiling (isolated) ===")
    profile_components.run()

    print("\n=== 6. Clean scaling benchmark (isolated) ===")
    benchmark_scaling.run()

    print("\n=== 7. Consolidated analysis ===")
    analyse_results.analyse()


if __name__ == "__main__":
    main()
