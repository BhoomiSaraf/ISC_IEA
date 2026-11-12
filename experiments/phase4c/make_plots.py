"""Minimal required visualizations (section 17.G): one original/encrypted
histogram comparison, one correlation scatter pair, one performance scaling
plot. Not an exhaustive plot set for every image -- time-budgeted to a
representative subset, documented as such rather than claimed exhaustive.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from isc_cipher import encrypt_bytes
import common

KEY = config.BASE_KEY


def histogram_plot(image_id="astronaut_gray"):
    arr = np.load(f"{config.DATASET_DIR}/{image_id}.npy")
    h, w = arr.shape[0], arr.shape[1]
    data = arr.tobytes()
    ct = encrypt_bytes(KEY, data, h, w, 1)
    body = np.frombuffer(common.body_bytes(ct), dtype=np.uint8)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    axes[0].imshow(arr, cmap="gray")
    axes[0].set_title(f"Original: {image_id}")
    axes[0].axis("off")
    axes[1].imshow(body.reshape(h, w), cmap="gray")
    axes[1].set_title("Ciphertext BODY reshaped\n(NOT a valid/decrypted image)")
    axes[1].axis("off")
    axes[2].hist(arr.ravel(), bins=256, range=(0, 255), alpha=0.6, label="original", color="tab:blue")
    axes[2].hist(body, bins=256, range=(0, 255), alpha=0.6, label="encrypted body", color="tab:orange")
    axes[2].set_title("Byte-value histogram")
    axes[2].legend()
    fig.tight_layout()
    fig.savefig(f"{config.PLOTS_DIR}/histogram_{image_id}.png", dpi=110)
    plt.close(fig)


def correlation_scatter(image_id="chelsea_rgb"):
    arr = np.load(f"{config.DATASET_DIR}/{image_id}.npy")
    h, w = arr.shape[0], arr.shape[1]
    c = arr.shape[2] if arr.ndim == 3 else 1
    data = arr.tobytes()
    ct = encrypt_bytes(KEY, data, h, w, c)
    body = np.frombuffer(common.body_bytes(ct), dtype=np.uint8).reshape(h, w, c) if c > 1 else \
        np.frombuffer(common.body_bytes(ct), dtype=np.uint8).reshape(h, w)

    orig_ch = arr[..., 0] if c > 1 else arr
    enc_ch = body[..., 0] if c > 1 else body

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    axes[0].scatter(orig_ch[:, :-1].ravel()[::37], orig_ch[:, 1:].ravel()[::37], s=2, alpha=0.3)
    axes[0].set_title(f"Original adjacent pixels (horiz)\n{image_id}, channel 0")
    axes[0].set_xlabel("pixel(x,y)")
    axes[0].set_ylabel("pixel(x+1,y)")
    axes[1].scatter(enc_ch[:, :-1].ravel()[::37], enc_ch[:, 1:].ravel()[::37], s=2, alpha=0.3, color="tab:orange")
    axes[1].set_title("Encrypted BODY adjacent bytes (horiz)")
    axes[1].set_xlabel("byte(x,y)")
    axes[1].set_ylabel("byte(x+1,y)")
    fig.tight_layout()
    fig.savefig(f"{config.PLOTS_DIR}/correlation_{image_id}.png", dpi=110)
    plt.close(fig)


def performance_plot():
    df = pd.read_csv(f"{config.RESULTS_DIR}/benchmark_scaling.csv")
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.plot(df["size"], df["enc_mean_sec"], "o-", label="encrypt")
    ax.plot(df["size"], df["dec_mean_sec"], "s-", label="decrypt")
    ax.set_xlabel("image side length (px, square grayscale)")
    ax.set_ylabel("wall-clock seconds")
    ax.set_title("Phase 4C isolated scaling re-check (gray only)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(f"{config.PLOTS_DIR}/performance_scaling.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    histogram_plot("astronaut_gray")
    histogram_plot("rocket_gray")  # the one image with chi2_pvalue < 0.05
    correlation_scatter("chelsea_rgb")
    correlation_scatter("hubble_deep_field_gray")
    performance_plot()
    print("Plots written to", config.PLOTS_DIR)
