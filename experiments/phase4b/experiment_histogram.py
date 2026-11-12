"""Experiment B: histogram analysis, original vs. encrypted BODY bytes.

Per the Phase 4B instructions: the encrypted-body visualization reshaped into (H,W[,C]) is a
BYTE-LEVEL statistical view for histogram/entropy/correlation purposes only. It is explicitly
NOT a decrypted or valid image and is never claimed to be one -- it is simply the same bytes a
viewer of the raw ciphertext body would see if they (incorrectly) tried to interpret it as an
image of the original shape.
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config
from common import chi_square_256
from stats_core import build_stats_cache

REPRESENTATIVE = ["high_texture_random", "smooth_natural_like", "checkerboard", "all_zero", "correlated_rgb"]


def run():
    cache = build_stats_cache()
    rows = []
    for (name, size, c), entry in cache["entries"].items():
        orig = entry["original"]
        body = entry["body"]
        chi2_o, p_o = chi_square_256(orig.tobytes())
        chi2_e, p_e = chi_square_256(body)
        rows.append({
            "image_id": f"{name}_{size}x{size}_c{c}", "size": size, "channels": c,
            "orig_mean": float(orig.astype(np.float64).mean()), "orig_std": float(orig.astype(np.float64).std()),
            "enc_mean": float(np.frombuffer(body, dtype=np.uint8).astype(np.float64).mean()),
            "enc_std": float(np.frombuffer(body, dtype=np.uint8).astype(np.float64).std()),
            "orig_chi2": chi2_o, "orig_chi2_pvalue": p_o,
            "enc_chi2": chi2_e, "enc_chi2_pvalue": p_e,
        })
    out = os.path.join(config.RESULTS_DIR, "experiment_B_histogram.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # plots for representative images at size 256 (or the largest available primary size)
    size = max(config.PRIMARY_SIZES)
    for name in REPRESENTATIVE:
        for c in (1, 3):
            key = (name, size, c)
            if key not in cache["entries"]:
                continue
            entry = cache["entries"][key]
            orig = entry["original"]
            body = entry["body"]
            body_img = np.frombuffer(body, dtype=np.uint8).reshape((size, size) if c == 1 else (size, size, 3))

            fig, axes = plt.subplots(2, 2, figsize=(9, 8))
            axes[0, 0].imshow(orig, cmap="gray" if c == 1 else None, vmin=0, vmax=255)
            axes[0, 0].set_title(f"Original: {name} ({size}x{size}, c={c})")
            axes[0, 0].axis("off")
            axes[0, 1].imshow(body_img, cmap="gray" if c == 1 else None, vmin=0, vmax=255)
            axes[0, 1].set_title("Encrypted BODY bytes reshaped\n(NOT a valid/decrypted image)")
            axes[0, 1].axis("off")

            if c == 1:
                axes[1, 0].hist(orig.ravel(), bins=256, range=(0, 255), color="steelblue")
                axes[1, 1].hist(body_img.ravel(), bins=256, range=(0, 255), color="firebrick")
            else:
                colors = ["r", "g", "b"]
                for ci, col in enumerate(colors):
                    axes[1, 0].hist(orig[:, :, ci].ravel(), bins=256, range=(0, 255), color=col, alpha=0.5, label=col)
                    axes[1, 1].hist(body_img[:, :, ci].ravel(), bins=256, range=(0, 255), color=col, alpha=0.5, label=col)
                axes[1, 0].legend(); axes[1, 1].legend()
            axes[1, 0].set_title("Original histogram")
            axes[1, 1].set_title("Encrypted-body histogram")
            plt.tight_layout()
            fig.savefig(os.path.join(config.PLOTS_DIR, f"histogram_{name}_c{c}.png"), dpi=110)
            plt.close(fig)
    print(f"Histogram: {len(rows)} images analyzed; plots for {len(REPRESENTATIVE)} representative images saved.")
    return rows


if __name__ == "__main__":
    run()
