"""Experiment D: adjacent-pixel correlation, original vs. encrypted-body-as-image."""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config
from common import adjacent_pixel_correlation
from stats_core import build_stats_cache

REPRESENTATIVE = ["high_texture_random", "smooth_natural_like", "correlated_rgb", "gradient_horizontal"]


def channel_slices(img, c):
    if c == 1:
        return {"gray": img}
    return {ch: img[:, :, i] for i, ch in enumerate("RGB")}


def run():
    cache = build_stats_cache()
    rows = []
    scatter_cache = {}
    for (name, size, c), entry in cache["entries"].items():
        orig = entry["original"]
        body = entry["body"]
        body_img = np.frombuffer(body, dtype=np.uint8).reshape((size, size) if c == 1 else (size, size, 3))
        for ch_name, ch_arr in channel_slices(orig, c).items():
            corr_o = adjacent_pixel_correlation(ch_arr)
            corr_e = adjacent_pixel_correlation(channel_slices(body_img, c)[ch_name])
            row = {"image_id": f"{name}_{size}x{size}_c{c}", "size": size, "channels": c, "channel": ch_name}
            for direction in ("horizontal", "vertical", "diagonal"):
                r_o = corr_o[direction]["r"]
                r_e = corr_e[direction]["r"]
                row[f"orig_r_{direction}"] = r_o
                row[f"enc_r_{direction}"] = r_e
                row[f"abs_reduction_{direction}"] = (abs(r_o) - abs(r_e)) if (r_o == r_o and r_e == r_e) else float("nan")
            rows.append(row)
            if name in REPRESENTATIVE and ((name, size, c, ch_name) not in scatter_cache):
                scatter_cache[(name, size, c, ch_name)] = (corr_o["horizontal"], corr_e["horizontal"])

    out = os.path.join(config.RESULTS_DIR, "experiment_D_correlation.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # scatter plots for a handful of representative (image, channel) pairs at the largest size
    size = max(config.PRIMARY_SIZES)
    n_plotted = 0
    for (name, sz, c, ch_name), (ho, he) in scatter_cache.items():
        if sz != size:
            continue
        fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
        axes[0].scatter(ho["x"], ho["y"], s=1, alpha=0.15, color="steelblue")
        axes[0].set_title(f"Original ({name}, {ch_name})\nr={ho['r']:.4f}")
        axes[0].set_xlabel("pixel(x)"); axes[0].set_ylabel("pixel(x+1), horizontal")
        axes[1].scatter(he["x"], he["y"], s=1, alpha=0.15, color="firebrick")
        axes[1].set_title(f"Encrypted body ({name}, {ch_name})\nr={he['r']:.4f}")
        axes[1].set_xlabel("byte(x)"); axes[1].set_ylabel("byte(x+1), horizontal")
        plt.tight_layout()
        fig.savefig(os.path.join(config.PLOTS_DIR, f"correlation_{name}_{ch_name}.png"), dpi=110)
        plt.close(fig)
        n_plotted += 1
    print(f"Correlation: {len(rows)} (image, channel) rows; {n_plotted} scatter plots saved.")
    return rows


if __name__ == "__main__":
    run()
