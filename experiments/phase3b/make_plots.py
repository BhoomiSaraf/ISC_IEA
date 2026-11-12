"""Generate Phase 3B plots from the raw CSVs. Run after stage_a_primary.py and stage_b_burnin.py."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plots")
os.makedirs(OUT, exist_ok=True)


def savefig(name):
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, name), dpi=150)
    plt.close()


def plot_entropy_distributions(lane_df):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, extraction in zip(axes, (1, 2)):
        sub = lane_df[lane_df.extraction == extraction]
        for g in sub.stream.unique():
            s = sub[sub.stream == g]
            ax.hist(s.shannon_entropy_bits, bins=30, alpha=0.5, label=g)
        ax.set_title(f"extraction={extraction}")
        ax.set_xlabel("per-lane Shannon entropy (bits)")
        ax.axvline(8.0, color="k", linestyle="--", linewidth=1, label="ideal=8.0")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("lane count (all seeds pooled)")
    fig.suptitle("Per-lane byte entropy distribution by stream and extraction profile")
    savefig("01_entropy_distributions.png")


def plot_chi2_distributions(lane_df):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, extraction in zip(axes, (1, 2)):
        sub = lane_df[lane_df.extraction == extraction]
        for g in sub.stream.unique():
            s = sub[sub.stream == g]
            ax.hist(s.chi2_p, bins=20, range=(0, 1), alpha=0.5, label=g)
        ax.set_title(f"extraction={extraction}")
        ax.set_xlabel("per-lane chi-square p-value")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("lane count")
    fig.suptitle("Per-lane chi-square uniformity p-value distribution")
    savefig("02_chi2_pvalue_distributions.png")


def plot_per_lane_acf(lane_df):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for extraction, marker in zip((1, 2), ("o", "x")):
        sub = lane_df[lane_df.extraction == extraction]
        ax.scatter(sub.lane, sub.max_abs_acf_lag1_100, s=6, alpha=0.4,
                   label=f"extraction={extraction}", marker=marker)
    bonf = lane_df.bonferroni_bound_256tests.iloc[0]
    ax.axhline(bonf, color="r", linestyle="--", label=f"Bonferroni bound={bonf:.4f}")
    ax.set_xlabel("lane index (0-63)")
    ax.set_ylabel("max |ACF|, lags 1-100")
    ax.legend(fontsize=8)
    ax.set_title("Per-lane maximum autocorrelation vs. Bonferroni bound")
    savefig("03_per_lane_acf_vs_bonferroni.png")


def plot_cross_stream_mi(cross_df):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    cross_df["pair"] = cross_df.stream_1 + "-" + cross_df.stream_2
    for extraction, offset in zip((1, 2), (-0.15, 0.15)):
        sub = cross_df[cross_df.extraction == extraction]
        grp = sub.groupby("pair").agg(adj=("adjusted_mi_bits", "mean"),
                                       std=("perm_null_std_bits", "mean")).reset_index()
        x = range(len(grp))
        ax.errorbar([xi + offset for xi in x], grp.adj, yerr=grp["std"], fmt="o",
                    label=f"extraction={extraction}", capsize=3)
    ax.set_xticks(range(len(grp)))
    ax.set_xticklabels(grp.pair, rotation=30, ha="right")
    ax.set_ylabel("adjusted mutual information (bits)")
    ax.axhline(0, color="k", linewidth=0.5)
    ax.legend()
    ax.set_title("Cross-stream adjusted MI (Miller-Madow corrected), mean across seeds,\n"
                 "error bars = permutation-null std")
    savefig("04_cross_stream_mi.png")


def plot_nist_pass_proportions(nist_df, name, title):
    fig, ax = plt.subplots(figsize=(10, 5))
    for extraction, offset in zip((1, 2), (-0.15, 0.15)):
        sub = nist_df[(nist_df.extraction == extraction) & (nist_df.seed == "seedA")]
        grp = sub.groupby("test").agg(prop=("proportion", "mean"),
                                       lo=("proportion_min", "mean")).reset_index()
        x = range(len(grp))
        ax.scatter([xi + offset for xi in x], grp.prop, label=f"extraction={extraction}")
        if extraction == 1:
            ax.scatter(x, grp.lo, marker="_", color="r", label="NIST lower bound")
    ax.set_xticks(range(len(grp)))
    ax.set_xticklabels(grp.test, rotation=45, ha="right")
    ax.set_ylabel("pass proportion")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    ax.set_title(title)
    savefig(name)


def plot_burnin_comparison(burnin_df):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for extraction, marker in zip((1, 2), ("o-", "x--")):
        sub = burnin_df[burnin_df.extraction == extraction].groupby("burn_in").agg(
            H=("lane_entropy_mean", "mean"), chi2=("lane_chi2_mean", "mean"),
            t=("generation_time_seconds", "mean")).reset_index()
        axes[0].plot(sub.burn_in, sub.H, marker, label=f"extraction={extraction}")
        axes[1].plot(sub.burn_in, sub.t, marker, label=f"extraction={extraction}")
    axes[0].axhline(8.0, color="k", linestyle=":", linewidth=1)
    axes[0].set_xlabel("burn-in (steps)")
    axes[0].set_ylabel("mean per-lane entropy (bits)")
    axes[0].legend(fontsize=8)
    axes[1].set_xlabel("burn-in (steps)")
    axes[1].set_ylabel("generation time (s), 20,000 bytes/lane")
    axes[1].legend(fontsize=8)
    fig.suptitle("Burn-in sweep: mean per-lane entropy and generation cost")
    savefig("05_burnin_entropy_and_runtime.png")


def plot_collision_min_hamming(coll_df):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for extraction in (1, 2):
        sub = coll_df[coll_df.extraction == extraction]
        ax.scatter(sub.stream, sub.min_hamming_distance, label=f"extraction={extraction}", s=60)
    ax.set_ylabel("minimum pairwise Hamming distance\n(first 256 bytes, 2016 pairs/stream)")
    ax.set_title("256-lane collision check: minimum observed Hamming distance per stream")
    ax.legend()
    savefig("06_lane_collision_min_hamming.png")


if __name__ == "__main__":
    lane_df = pd.read_csv("raw/stage_a_lane_metrics.csv")
    stream_df = pd.read_csv("raw/stage_a_stream_metrics.csv")
    cross_df = pd.read_csv("raw/stage_a_cross_stream_metrics.csv")
    nist_lane_df = pd.read_csv("raw/stage_a_nist_lane.csv")
    nist_stream_df = pd.read_csv("raw/stage_a_nist_stream.csv")
    coll_df = pd.read_csv("raw/stage_a_collision.csv")
    burnin_df = pd.read_csv("raw/stage_b_burnin_comparison.csv")

    plot_entropy_distributions(lane_df)
    plot_chi2_distributions(lane_df)
    plot_per_lane_acf(lane_df)
    plot_cross_stream_mi(cross_df)
    plot_nist_pass_proportions(nist_lane_df, "07_nist_lane_pass_proportions.png",
                                "NIST pass proportions, per-lane (M=64, seedA)")
    plot_nist_pass_proportions(nist_stream_df, "08_nist_stream_pass_proportions.png",
                                "NIST pass proportions, per-stream chunks (M=64, seedA)")
    plot_burnin_comparison(burnin_df)
    plot_collision_min_hamming(coll_df)
    print("wrote plots to", OUT)
