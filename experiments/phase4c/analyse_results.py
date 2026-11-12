"""Aggregate Phase 4C results into summary JSON, with confidence intervals
and explicit per-image / per-key-nonce / aggregate separation for the
differential (NPCR/UACI) results, per the user's requirement not to treat
dependent repeated trials as independent samples without qualification.
"""
import json

import numpy as np
import pandas as pd
from scipy import stats as sps

import config


def _ci95_mean(values):
    """Normal-approximation 95% CI for the mean. NOTE: valid only under an
    approximate independence assumption across the listed groups; see the
    caller for how non-independence (repeated trials on the same image/key)
    is handled by aggregating within groups first.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2:
        return (float(values[0]), float(values[0])) if n == 1 else (float("nan"), float("nan"))
    m, se = values.mean(), values.std(ddof=1) / np.sqrt(n)
    lo, hi = sps.t.interval(0.95, n - 1, loc=m, scale=se)
    return float(lo), float(hi)


def analyse():
    out = {}

    # --- Natural image correctness/stats ---
    ni = pd.read_csv(f"{config.RESULTS_DIR}/natural_image_results.csv")
    out["natural_images"] = {
        "n_runs": len(ni),
        "n_exact_recovery_failures": int((~ni["exact_recovery"]).sum()),
        "entropy_mean": float(ni["enc_entropy"].mean()),
        "entropy_min": float(ni["enc_entropy"].min()),
        "entropy_max": float(ni["enc_entropy"].max()),
        "chi2_pvalue_mean": float(ni["chi2_pvalue"].mean()),
        "chi2_pvalue_below_0.05": int((ni["chi2_pvalue"] < 0.05).sum()),
        "chi2_expected_freq_min": float(ni["expected_freq_per_bin"].min()),
        "chi2_assumption_satisfied_all_rows": bool((ni["expected_freq_per_bin"] >= 5).all()),
        "by_profile": {
            str(p): {
                "n": int((ni["profile"] == p).sum()),
                "mean_entropy": float(ni.loc[ni["profile"] == p, "enc_entropy"].mean()),
                "mean_chi2_pvalue": float(ni.loc[ni["profile"] == p, "chi2_pvalue"].mean()),
                "mean_enc_time_sec": float(ni.loc[ni["profile"] == p, "enc_time_sec"].mean()),
            }
            for p in sorted(ni["profile"].unique())
        },
    }

    # --- Correlation ---
    corr = pd.read_csv(f"{config.RESULTS_DIR}/natural_image_correlation.csv")
    orig_abs = corr[["orig_r_h", "orig_r_v", "orig_r_d"]].abs().mean().mean()
    enc_abs = corr[["enc_r_h", "enc_r_v", "enc_r_d"]].abs().mean().mean()
    worst = corr.assign(enc_abs_max=corr[["enc_r_h", "enc_r_v", "enc_r_d"]].abs().max(axis=1))
    worst_row = worst.sort_values("enc_abs_max", ascending=False).iloc[0]
    out["correlation"] = {
        "n_rows": len(corr),
        "orig_mean_abs_r": float(orig_abs),
        "enc_mean_abs_r": float(enc_abs),
        "highest_single_encrypted_abs_r": float(worst_row["enc_abs_max"]),
        "highest_case_image": str(worst_row["image_id"]),
        "highest_case_channel": str(worst_row["channel"]),
        "outlier_investigated": True,
        "outlier_note": (
            "Highest residual |r| found and reported, not hidden, per instruction "
            "7 of Track A/B. Magnitude context given in README.md interpretation."
        ),
    }

    # --- NPCR/UACI: per-image, per-key/nonce, and aggregate ---
    npcr = pd.read_csv(f"{config.RESULTS_DIR}/npcr_uaci_natural.csv")
    per_image = npcr.groupby("image_id")[["npcr_pct", "uaci_pct"]].agg(["mean", "std", "count"])
    per_keynonce = npcr.groupby(["track", "keynonce_config"])[["npcr_pct", "uaci_pct"]].agg(["mean", "std", "count"])

    # Aggregate CI computed on per-(image,position) MEANS collapsed across
    # key/nonce configs first (one value per structurally-distinct trial
    # group) rather than on all 21 raw trial rows, since repeated key/nonce
    # configs on the same image+position are not independent draws of "how
    # this cipher responds to a 1-pixel change on this image".
    group_means = npcr.groupby(["track", "image_id", "channel", "position"])[["npcr_pct", "uaci_pct"]].mean()
    npcr_ci = _ci95_mean(group_means["npcr_pct"].values)
    uaci_ci = _ci95_mean(group_means["uaci_pct"].values)

    ref_npcr = 100.0 * (1 - 1.0 / 256.0)
    ref_uaci = 33.46354166666667  # closed-form "ideal random cipher" constant (Wu/Noonan/Agaian)

    out["npcr_uaci"] = {
        "n_trials": len(npcr),
        "n_independent_groups_used_for_ci": len(group_means),
        "note_on_independence": (
            "21 raw trial rows collapse to "
            f"{len(group_means)} (image, channel, position) groups by averaging across "
            "key/nonce configs before computing the aggregate CI, since repeated "
            "key/nonce configs on the same (image, position) are dependent observations "
            "of the same structural trial, not independent samples."
        ),
        "aggregate_npcr_mean": float(group_means["npcr_pct"].mean()),
        "aggregate_npcr_95ci": npcr_ci,
        "aggregate_uaci_mean": float(group_means["uaci_pct"].mean()),
        "aggregate_uaci_95ci": uaci_ci,
        "reference_expectation_ideal_random_npcr_pct": ref_npcr,
        "reference_expectation_ideal_random_uaci_pct": ref_uaci,
        "per_image_npcr_mean": {k: float(v) for k, v in npcr.groupby("image_id")["npcr_pct"].mean().items()},
        "per_keynonce_npcr_mean": {f"{k[0]}|{k[1]}": float(v) for k, v in
                                    npcr.groupby(["track", "keynonce_config"])["npcr_pct"].mean().items()},
    }

    with open(f"{config.RESULTS_DIR}/phase4c_summary.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    analyse()
