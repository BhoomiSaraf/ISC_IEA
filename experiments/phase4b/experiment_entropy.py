"""Experiment C: Shannon entropy, original vs. encrypted-body, per-image and per-channel."""

import csv
import os

import numpy as np

import config
from common import shannon_entropy
from stats_core import build_stats_cache


def run():
    cache = build_stats_cache()
    rows = []
    for (name, size, c), entry in cache["entries"].items():
        orig = entry["original"]
        body = entry["body"]
        row = {
            "image_id": f"{name}_{size}x{size}_c{c}", "size": size, "channels": c,
            "entropy_original_overall": shannon_entropy(orig.tobytes()),
            "entropy_encrypted_overall": shannon_entropy(body),
        }
        if c == 3:
            for ci, cname in enumerate("RGB"):
                row[f"entropy_original_{cname}"] = shannon_entropy(np.ascontiguousarray(orig[:, :, ci]).tobytes())
                body_img = np.frombuffer(body, dtype=np.uint8).reshape(size, size, 3)
                row[f"entropy_encrypted_{cname}"] = shannon_entropy(np.ascontiguousarray(body_img[:, :, ci]).tobytes())
        rows.append(row)
    fieldnames = sorted({k for r in rows for k in r.keys()}, key=lambda k: (k != "image_id", k))
    out = os.path.join(config.RESULTS_DIR, "experiment_C_entropy.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    overall_enc = [r["entropy_encrypted_overall"] for r in rows]
    print(f"Entropy: {len(rows)} images. Encrypted overall entropy: min={min(overall_enc):.4f} "
          f"max={max(overall_enc):.4f} mean={np.mean(overall_enc):.4f} bits/byte (max possible = 8.0)")
    return rows


if __name__ == "__main__":
    run()
