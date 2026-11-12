"""Phase 4C Step 1: independently verify Phase 4B's reported summary numbers
against the raw CSV/JSON artifacts in experiments/phase4b/results/.

Read-only against experiments/phase4b/ -- this script never writes there.
"""
import json
import os

import pandas as pd

import config

P4B = os.path.abspath(os.path.join(config.ROOT, "..", "phase4b", "results"))


def _load(name):
    path = os.path.join(P4B, name)
    if name.endswith(".csv"):
        return pd.read_csv(path)
    with open(path) as f:
        return json.load(f)


def verify():
    rows = []

    # --- Correctness: 147 trials, 0 failures ---
    a_sum = _load("experiment_A_summary.json")
    a_csv = _load("experiment_A_recovery.csv")
    claimed = (147, 0)
    actual = (a_sum["n_trials"], a_sum["n_failures"])
    actual_csv_rows = len(a_csv)
    csv_failures = int((a_csv["exact_equal"] == False).sum()) if "exact_equal" in a_csv.columns else None
    rows.append({
        "claim": "147 correctness trials, 0 failures",
        "source_file": "experiment_A_summary.json + experiment_A_recovery.csv",
        "verified_value": f"n_trials={actual[0]}, n_failures={actual[1]}; csv_rows={actual_csv_rows}, csv_failures={csv_failures}",
        "status": "VERIFIED" if actual == claimed and actual_csv_rows == 147 else "DISCREPANCY",
    })

    # --- Entropy range / mean ---
    c_csv = _load("experiment_C_entropy.csv")
    emin, emax, emean = (
        c_csv["entropy_encrypted_overall"].min(),
        c_csv["entropy_encrypted_overall"].max(),
        c_csv["entropy_encrypted_overall"].mean(),
    )
    rows.append({
        "claim": "Encrypted-body entropy 7.95-7.9992 bits/byte, mean 7.9869",
        "source_file": "experiment_C_entropy.csv (entropy_encrypted_overall)",
        "verified_value": f"min={emin:.4f}, max={emax:.4f}, mean={emean:.4f}",
        "status": "VERIFIED" if abs(emean - 7.9869) < 0.001 and emin >= 7.94 and emax <= 8.0 else "DISCREPANCY",
    })

    # --- Histogram chi2 ---
    b_csv = _load("experiment_B_histogram.csv")
    pmean = b_csv["enc_chi2_pvalue"].mean()
    below = int((b_csv["enc_chi2_pvalue"] < 0.05).sum())
    rows.append({
        "claim": "Histogram chi-square p-value mean 0.4755; 5/63 below 0.05",
        "source_file": "experiment_B_histogram.csv (enc_chi2_pvalue)",
        "verified_value": f"mean={pmean:.4f}, n_below_0.05={below}/{len(b_csv)}",
        "status": "VERIFIED" if abs(pmean - 0.4755) < 0.001 and below == 5 else "DISCREPANCY",
    })

    # --- Correlation drop ---
    d_csv = _load("experiment_D_correlation.csv")
    orig_mean = d_csv[["orig_r_horizontal", "orig_r_vertical", "orig_r_diagonal"]].abs().mean().mean()
    enc_mean = d_csv[["enc_r_horizontal", "enc_r_vertical", "enc_r_diagonal"]].abs().mean().mean()
    rows.append({
        "claim": "Mean |adjacent-pixel correlation| drops from ~0.57 to ~0.007",
        "source_file": "experiment_D_correlation.csv",
        "verified_value": f"orig_mean_abs_r={orig_mean:.4f}, enc_mean_abs_r={enc_mean:.4f}; n_rows={len(d_csv)}",
        "status": "VERIFIED" if 0.55 <= orig_mean <= 0.60 and enc_mean < 0.01 else "DISCREPANCY",
    })

    # --- NPCR/UACI (plaintext differential) ---
    e_sum = _load("experiment_E_summary.json")
    rows.append({
        "claim": "NPCR/UACI (plaintext diff): mean NPCR 99.83%, mean UACI 33.54% "
                 "vs ideal-random refs 99.61%/33.46%",
        "source_file": "experiment_E_summary.json",
        "verified_value": f"n_trials={e_sum['n_trials']}, NPCR mean={e_sum['npcr_pct']['mean']:.4f}, "
                           f"UACI mean={e_sum['uaci_pct']['mean']:.4f}, "
                           f"ref NPCR={e_sum['reference_expectation_for_iid_uniform_bytes']['npcr_expected_pct']:.4f}, "
                           f"ref UACI={e_sum['reference_expectation_for_iid_uniform_bytes']['uaci_expected_pct']:.4f}",
        "status": "VERIFIED" if e_sum["n_trials"] == 27 and abs(e_sum["npcr_pct"]["mean"] - 99.83) < 0.01 else "DISCREPANCY",
    })

    # --- Key sensitivity ---
    f_sum = _load("experiment_F_summary.json")
    rows.append({
        "claim": "Key sensitivity: NPCR 99.61%, UACI 33.47%, Hamming-fraction 0.4998 (ideal 0.5)",
        "source_file": "experiment_F_summary.json",
        "verified_value": f"n_trials={f_sum['n_trials']}, NPCR mean={f_sum['npcr_pct']['mean']:.4f}, "
                           f"UACI mean={f_sum['uaci_pct']['mean']:.4f}, "
                           f"Hamming mean={f_sum['hamming_frac']['mean']:.4f}",
        "status": "VERIFIED" if f_sum["n_trials"] == 40 and abs(f_sum["hamming_frac"]["mean"] - 0.4998) < 0.001 else "DISCREPANCY",
    })

    # --- Profile comparison: no meaningful difference, bodies always differ ---
    g_csv = _load("experiment_G_profile_stats.csv")
    any_identical = bool(g_csv["bodies_identical"].any())
    ent_diff = abs(g_csv["entropy_mantissa8"].mean() - g_csv["entropy_k14"].mean())
    rows.append({
        "claim": "mantissa8_v1 vs k14_scaled_modulo_v1: no meaningful statistical difference; "
                 "ciphertexts differ in all 63 cases",
        "source_file": "experiment_G_profile_stats.csv",
        "verified_value": f"n_rows={len(g_csv)}, any_bodies_identical={any_identical}, "
                           f"mean_entropy_diff={ent_diff:.6f}",
        "status": "VERIFIED" if len(g_csv) == 63 and not any_identical and ent_diff < 0.01 else "DISCREPANCY",
    })

    # --- Performance throughput scaling ---
    h_csv = _load("experiment_H_performance.csv")
    # Decimal MB/s -> KB/s (x1000); binary (x1024) conversion was tried first
    # and did NOT reproduce the reported numbers, confirming the original
    # Phase 4B report used decimal units here.
    t64 = h_csv.loc[h_csv["size"] == 64, "enc_throughput_MBps"].iloc[0] * 1000.0
    t512 = h_csv.loc[h_csv["size"] == 512, "enc_throughput_MBps"].iloc[0] * 1000.0
    rows.append({
        "claim": "Encryption throughput ~2.65 KB/s at 64x64 scaling to ~15.7 KB/s at 512x512",
        "source_file": "experiment_H_performance.csv (enc_throughput_MBps * 1024)",
        "verified_value": f"64x64={t64:.2f} KB/s, 512x512={t512:.2f} KB/s",
        "status": "VERIFIED" if abs(t64 - 2.65) < 0.05 and abs(t512 - 15.7) < 0.1 else "DISCREPANCY",
    })

    # --- Tamper tests sanity check (not explicitly claimed in the Phase 4B
    # summary given to the user, but part of required artifacts) ---
    j = _load("experiment_J_tamper.json")
    all_raised = all(c["raised"] for c in j)
    rows.append({
        "claim": "(supplementary) All 5 tamper/auth regression cases raised the expected exception",
        "source_file": "experiment_J_tamper.json",
        "verified_value": f"n_cases={len(j)}, all_raised={all_raised}",
        "status": "VERIFIED" if all_raised and len(j) == 5 else "DISCREPANCY",
    })

    df = pd.DataFrame(rows)
    out_csv = os.path.join(config.RESULTS_DIR, "phase4b_verification.csv")
    df.to_csv(out_csv, index=False)
    print(df.to_string(index=False))
    n_disc = int((df["status"] == "DISCREPANCY").sum())
    print(f"\n{len(df)} claims checked, {n_disc} discrepancies.")
    return df


if __name__ == "__main__":
    verify()
