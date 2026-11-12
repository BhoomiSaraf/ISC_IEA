"""Phase 4C Track A, steps 3.2/3.3: standardize natural images to grayscale
and RGB uint8, resize where needed, and build the dataset manifest.

Resize target: config.NATURAL_RESIZE (256 px longest side), chosen so the
Phase 4B performance envelope (~5.6s/encrypt at 256x256 gray, worse for RGB
and for 512x512) keeps the full natural-image correctness+stats battery
inside a practical runtime -- see README.md for the arithmetic. Aspect
ratio is preserved; resampling uses skimage.transform.resize (anti-aliased)
and the result is re-quantized to uint8 (documented, not lossless, but no
lossy *compression* such as JPEG is applied).
"""
import hashlib
import os

import numpy as np
import pandas as pd
from skimage.transform import resize as sk_resize

import config
import acquire_images


def _entropy(arr: np.ndarray) -> float:
    counts = np.bincount(arr.reshape(-1), minlength=256)
    p = counts[counts > 0] / counts.sum()
    return float(-(p * np.log2(p)).sum())


def _resize_to(img: np.ndarray, target: int) -> tuple[np.ndarray, tuple[int, int]]:
    h, w = img.shape[:2]
    if max(h, w) <= target:
        return img, (h, w)
    scale = target / max(h, w)
    new_h, new_w = max(1, round(h * scale)), max(1, round(w * scale))
    out = sk_resize(img, (new_h, new_w) + img.shape[2:], anti_aliasing=True, preserve_range=True)
    return out.astype(np.uint8), (new_h, new_w)


def prepare():
    manifest_rows, failures = acquire_images.acquire()
    rows = []
    for r in manifest_rows:
        img = np.load(r["npy_path"])
        orig_h, orig_w = img.shape[0], img.shape[1]
        orig_c = img.shape[2] if img.ndim == 3 else 1

        resized, (new_h, new_w) = _resize_to(img, config.NATURAL_RESIZE)
        resized = np.ascontiguousarray(resized.astype(np.uint8))

        # Build both a grayscale and (if source is RGB) an RGB uint8 variant
        variants = {}
        if resized.ndim == 2:
            variants["gray"] = resized
        else:
            variants["rgb"] = resized
            gray = np.round(
                resized[..., 0] * 0.2989 + resized[..., 1] * 0.5870 + resized[..., 2] * 0.1140
            ).astype(np.uint8)
            variants["gray"] = np.ascontiguousarray(gray)

        for variant_name, arr in variants.items():
            c = arr.shape[2] if arr.ndim == 3 else 1
            out_path = os.path.join(config.DATASET_DIR, f"{r['image_id']}_{variant_name}.npy")
            np.save(out_path, arr)
            checksum = hashlib.sha256(arr.tobytes()).hexdigest()
            rows.append({
                "image_id": f"{r['image_id']}_{variant_name}",
                "base_image": r["image_id"],
                "description": r["description"],
                "category": r["category"],
                "source": r["source"],
                "license": "scikit-image BSD-3-Clause sample data",
                "orig_width": orig_w,
                "orig_height": orig_h,
                "orig_channels": orig_c,
                "resized_width": new_w,
                "resized_height": new_h,
                "channels": c,
                "dtype": str(arr.dtype),
                "resample_method": "skimage.transform.resize, anti_aliasing=True, preserve_range=True"
                                   if (new_h, new_w) != (orig_h, orig_w) else "none (already <= target)",
                "aspect_ratio_preserved": True,
                "n_pixels": int(new_h * new_w),
                "n_bytes": int(arr.size),
                "entropy_bits_per_byte": _entropy(arr),
                "mean": float(arr.mean()),
                "std": float(arr.std()),
                "sha256": checksum,
                "npy_path": out_path,
            })

    df = pd.DataFrame(rows)
    out_csv = os.path.join(config.RESULTS_DIR, "natural_image_manifest.csv")
    df.to_csv(out_csv, index=False)
    print(f"Prepared {len(df)} dataset variants (gray/rgb) from {len(manifest_rows)} base images.")
    print(df[["image_id", "resized_width", "resized_height", "channels", "entropy_bits_per_byte"]].to_string(index=False))
    return df


if __name__ == "__main__":
    prepare()
