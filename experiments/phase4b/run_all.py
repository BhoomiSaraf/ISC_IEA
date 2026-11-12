"""Run the full Phase 4B pipeline in order. Each experiment_*.py is also independently runnable.

Order matters only for the shared stats_cache.pkl (histogram/entropy/correlation vs. profiles);
experiment_profiles.py is run last among the stats-cache consumers so it does not force the
mantissa8_v1 cache to be silently rebuilt for the others. See stats_core.py / README.md.
"""

import json
import os
import time

import config
import generate_dataset
import experiment_recovery
import experiment_entropy
import experiment_histogram
import experiment_correlation
import experiment_npcr_uaci
import experiment_key_sensitivity
import experiment_tamper
import experiment_edge_cases
import experiment_performance
import experiment_profiles

def main():
    log = []
    t_start = time.time()

    def step(name, fn):
        print(f"\n=== {name} ===")
        t0 = time.time()
        try:
            fn()
            status = "ok"
        except Exception as e:  # noqa: BLE001 -- recorded, never silently swallowed
            status = f"FAILED: {type(e).__name__}: {e}"
            print(f"  !! {status}")
        dt = time.time() - t0
        log.append({"step": name, "status": status, "elapsed_sec": dt})
        print(f"  ({dt:.1f}s)")

    step("generate_dataset", lambda: generate_dataset.build_dataset(sizes=config.PRIMARY_SIZES + config.EXTENDED_SIZES))
    step("experiment_A_recovery", experiment_recovery.run)
    step("experiment_C_entropy", experiment_entropy.run)
    step("experiment_B_histogram", experiment_histogram.run)
    step("experiment_D_correlation", experiment_correlation.run)
    step("experiment_E_npcr_uaci", experiment_npcr_uaci.run)
    step("experiment_F_key_sensitivity", experiment_key_sensitivity.run)
    step("experiment_J_tamper", experiment_tamper.run)
    step("experiment_I_edge_cases", experiment_edge_cases.run)
    step("experiment_H_performance", experiment_performance.run)
    step("experiment_G_profiles", experiment_profiles.run)

    total = time.time() - t_start
    with open(os.path.join(config.RESULTS_DIR, "run_all_log.json"), "w") as f:
        json.dump({"log": log, "total_elapsed_sec": total}, f, indent=2)
    print(f"\nTotal Phase 4B run time: {total:.1f}s")


if __name__ == "__main__":
    main()
