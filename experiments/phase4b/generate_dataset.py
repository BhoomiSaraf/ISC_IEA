"""Phase 4B synthetic test-image dataset generation.

Natural test images (Lena/Baboon/Peppers/Cameraman/Barbara) were NOT included: fetching
legally-clear, redistributable copies within the time budget was not attempted (per Section 4.1
"do not spend excessive time searching for datasets" / "if external images cannot be obtained,
generate a deterministic synthetic dataset"). scikit-image's bundled sample images (camera,
astronaut, etc.) ARE already used by the existing, frozen Phase-4A test suite
(tests/test_isc_cipher_roundtrip.py), so a form of "real image" round-trip coverage already
exists upstream of this phase; Phase 4B does not duplicate it and instead focuses entirely on the
syntheticedge-case dataset requested in Section 4.1 items 1-10, which specifically exercises
structure (uniformity, gradients, periodicity, correlation) that natural images do not reliably
isolate.

All generation is seeded from config.MASTER_SEED and otherwise deterministic.
"""

import csv
import json
import os

import numpy as np

import config
from common import checksum, shannon_entropy

RNG = np.random.default_rng(config.MASTER_SEED)


def _rng_for(label):
    # deterministic, label-dependent child RNG so each image type/size combo is reproducible
    # independent of call order
    seed = (config.MASTER_SEED ^ (abs(hash(label)) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return np.random.default_rng(seed)


def gen_uniform(h, w, c, value=127):
    shape = (h, w) if c == 1 else (h, w, c)
    return np.full(shape, value, dtype=np.uint8)


def gen_all_zero(h, w, c):
    return gen_uniform(h, w, c, 0)


def gen_all_255(h, w, c):
    return gen_uniform(h, w, c, 255)


def gen_gradient_h(h, w, c):
    row = np.linspace(0, 255, w, dtype=np.float64)
    img = np.tile(row, (h, 1)).astype(np.uint8)
    if c == 3:
        img = np.stack([img] * 3, axis=-1)
    return img


def gen_gradient_v(h, w, c):
    col = np.linspace(0, 255, h, dtype=np.float64).reshape(h, 1)
    img = np.tile(col, (1, w)).astype(np.uint8)
    if c == 3:
        img = np.stack([img] * 3, axis=-1)
    return img


def gen_checkerboard(h, w, c, block=8):
    yy, xx = np.indices((h, w))
    pattern = (((yy // block) + (xx // block)) % 2) * 255
    img = pattern.astype(np.uint8)
    if c == 3:
        img = np.stack([img] * 3, axis=-1)
    return img


def gen_binary_bw(h, w, c, label="binary_bw"):
    rng = _rng_for(label + f"_{h}x{w}x{c}")
    img = (rng.integers(0, 2, size=(h, w)) * 255).astype(np.uint8)
    if c == 3:
        img = np.stack([img] * 3, axis=-1)
    return img


def gen_low_entropy(h, w, c, label="low_entropy"):
    # mostly one value with a small amount of rare variation -> low Shannon entropy
    rng = _rng_for(label + f"_{h}x{w}x{c}")
    shape = (h, w) if c == 1 else (h, w, c)
    img = np.full(shape, 40, dtype=np.uint8)
    mask = rng.random(shape) < 0.02
    noise = rng.integers(0, 256, size=shape, dtype=np.uint8)
    img = np.where(mask, noise, img).astype(np.uint8)
    return img


def gen_high_texture_random(h, w, c, label="high_texture_random"):
    rng = _rng_for(label + f"_{h}x{w}x{c}")
    shape = (h, w) if c == 1 else (h, w, c)
    return rng.integers(0, 256, size=shape, dtype=np.uint8)


def gen_smooth_natural_like(h, w, c, label="smooth_natural_like"):
    # low-frequency 2D sum-of-sinusoids, scaled to uint8 -- a deterministic stand-in for a
    # "smooth natural-like" image without depending on any external file
    rng = _rng_for(label + f"_{h}x{w}x{c}")
    yy, xx = np.meshgrid(np.linspace(0, 2 * np.pi, w), np.linspace(0, 2 * np.pi, h))
    freqs = rng.uniform(0.5, 3.0, size=4)
    phases = rng.uniform(0, 2 * np.pi, size=4)
    field = (np.sin(freqs[0] * xx + phases[0]) + np.sin(freqs[1] * yy + phases[1])
             + 0.5 * np.sin(freqs[2] * (xx + yy) + phases[2]) + 0.5 * np.cos(freqs[3] * (xx - yy) + phases[3]))
    field = (field - field.min()) / (field.max() - field.min())
    img = (field * 255).astype(np.uint8)
    if c == 3:
        img = np.stack([img] * 3, axis=-1)
    return img


def gen_correlated_rgb(h, w, c, label="correlated_rgb"):
    if c != 3:
        return gen_smooth_natural_like(h, w, 1, label=label)
    base = gen_smooth_natural_like(h, w, 1, label=label).astype(np.float64)
    rng = _rng_for(label + f"_{h}x{w}x{c}")
    r = np.clip(base + rng.normal(0, 3, base.shape), 0, 255)
    g = np.clip(base + rng.normal(0, 3, base.shape), 0, 255)
    b = np.clip(base + rng.normal(0, 3, base.shape), 0, 255)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


GENERATORS = {
    "uniform_gray127": lambda h, w, c: gen_uniform(h, w, c, 127),
    "all_zero": gen_all_zero,
    "all_255": gen_all_255,
    "gradient_horizontal": gen_gradient_h,
    "gradient_vertical": gen_gradient_v,
    "checkerboard": gen_checkerboard,
    "binary_bw": gen_binary_bw,
    "low_entropy": gen_low_entropy,
    "high_texture_random": gen_high_texture_random,
    "smooth_natural_like": gen_smooth_natural_like,
    "correlated_rgb": gen_correlated_rgb,
}


def build_dataset(sizes=None, channel_modes=(1, 3), manifest_path=None):
    sizes = sizes or config.PRIMARY_SIZES
    manifest_path = manifest_path or os.path.join(config.RESULTS_DIR, "dataset_manifest.csv")
    rows = []
    images = {}  # key: (name, size, c) -> ndarray
    for name, gen in GENERATORS.items():
        for size in sizes:
            for c in channel_modes:
                if name == "correlated_rgb" and c != 3:
                    continue  # this generator is RGB-specific; skip the grayscale slot
                img = gen(size, size, c)
                key = (name, size, c)
                images[key] = img
                n_bytes = img.size
                flat = img.tobytes()
                rows.append({
                    "image_id": f"{name}_{size}x{size}_c{c}",
                    "source": "synthetic",
                    "height": size,
                    "width": size,
                    "channels": c,
                    "dtype": str(img.dtype),
                    "n_pixels": size * size,
                    "n_bytes": n_bytes,
                    "entropy_bits": shannon_entropy(flat),
                    "mean": float(img.astype(np.float64).mean()),
                    "std": float(img.astype(np.float64).std()),
                    "sha256": checksum(flat),
                })
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return images, rows


if __name__ == "__main__":
    images, rows = build_dataset(sizes=config.PRIMARY_SIZES + config.EXTENDED_SIZES)
    print(f"Generated {len(images)} images; manifest written to results/dataset_manifest.csv")
    with open(os.path.join(config.RESULTS_DIR, "dataset_summary.json"), "w") as f:
        json.dump({"n_images": len(images), "generators": list(GENERATORS.keys()),
                   "sizes": config.PRIMARY_SIZES + config.EXTENDED_SIZES}, f, indent=2)
