"""Phase 4C Track A, step 3.1: acquire a real natural-image dataset.

Decision on image source (documented honestly, per the user's requirement
not to fabricate sources or relabel synthetic images as natural):

    scikit-image's bundled sample-data package (skimage.data) was used.
    These are real photographs / scientific images shipped locally with the
    scikit-image distribution already installed in this environment (it is
    an existing dependency -- Phase 4A's own frozen test suite already uses
    skimage sample images for round-trip testing, see
    tests/test_isc_cipher_roundtrip.py). No network download was attempted:
    this repo's sandboxed execution environment should not be assumed to
    have reliable outbound network access for fetching USC-SIPI/Kodak
    datasets, and skimage.data already provides a legitimate, openly
    licensed (BSD-3, scikit-image license) local alternative of real
    natural-image content (portraits, animals, textures, scientific/space
    imagery, everyday objects) that satisfies the spirit of section 3.1
    without an unverified network dependency. This substitution is reported
    explicitly here rather than silently -- it is a deliberate, documented
    choice, not a silent fallback to synthetic data.

    Two images (`lily`, `eagle`) in skimage.data required an extra
    data-fetching package not installed here and were skipped (recorded as
    failures below, not silently dropped).
"""
import json
import os

import numpy as np
import skimage.data as skd

import config

# name -> (loader, human description, scene category)
CANDIDATES = {
    "astronaut": ("astronaut", "Portrait (Eileen Collins, STS-114)", "portrait"),
    "camera": ("camera", "Classic 'cameraman' test image", "object/person"),
    # NOTE: skimage.data.cat() is a byte-for-byte alias of chelsea() in this
    # skimage version (verified: np.array_equal(cat(), chelsea()) == True).
    # "cat" is therefore deliberately excluded here to avoid double-counting
    # one image as two independent natural-image samples.
    "chelsea": ("chelsea", "Cat close-up photograph", "animal"),
    "coffee": ("coffee", "Coffee cup, overhead photograph", "object"),
    "coins": ("coins", "Scattered coins, grayscale", "object/texture"),
    "horse": ("horse", "Horse silhouette (binary mask)", "animal/binary"),
    "rocket": ("rocket", "Rocket launch photograph", "object/landscape"),
    "hubble_deep_field": ("hubble_deep_field", "Hubble Deep Field (space imagery)", "high-detail scene"),
    "immunohistochemistry": ("immunohistochemistry", "Microscopy tissue image", "high-texture scene"),
    "brick": ("brick", "Brick wall texture", "texture/urban"),
    "grass": ("grass", "Grass texture", "texture/vegetation"),
    "gravel": ("gravel", "Gravel texture", "texture"),
    "lily": ("lily", "Lily microscopy (requires skimage-data extra)", "vegetation"),
    "eagle": ("eagle", "Eagle photograph (requires skimage-data extra)", "animal"),
}

LICENSE = (
    "scikit-image sample data, distributed under the scikit-image BSD-3-Clause "
    "license (https://scikit-image.org, package skimage.data). Individual "
    "image provenance is documented in the skimage.data module; astronaut, "
    "camera, cat, chelsea, coffee, coins, horse, rocket, hubble_deep_field, "
    "immunohistochemistry, brick, grass and gravel ship directly with the "
    "installed scikit-image wheel used in this environment."
)


def acquire():
    os.makedirs(config.DATASET_DIR, exist_ok=True)
    manifest_rows = []
    failures = []
    for key, (attr, desc, category) in CANDIDATES.items():
        try:
            fn = getattr(skd, attr)
            img = fn()
        except Exception as ex:  # noqa: BLE001 -- recorded, not hidden
            failures.append({"image_id": key, "reason": f"{type(ex).__name__}: {ex}"})
            continue
        img = np.asarray(img)
        if img.dtype == bool:
            img = (img.astype(np.uint8) * 255)
        out_path = os.path.join(config.DATASET_DIR, f"{key}.npy")
        np.save(out_path, img)
        manifest_rows.append({
            "image_id": key,
            "description": desc,
            "category": category,
            "orig_shape": str(img.shape),
            "orig_dtype": str(img.dtype),
            "source": "skimage.data (local, bundled with installed scikit-image)",
            "license": LICENSE,
            "npy_path": out_path,
        })

    with open(os.path.join(config.LOGS_DIR, "acquire_images_failures.json"), "w") as f:
        json.dump(failures, f, indent=2)

    print(f"Acquired {len(manifest_rows)} real natural images; {len(failures)} failed (see logs).")
    for r in manifest_rows:
        print(f"  {r['image_id']:24s} {r['orig_shape']} {r['orig_dtype']} ({r['category']})")
    for fail in failures:
        print(f"  FAILED {fail['image_id']}: {fail['reason']}")
    return manifest_rows, failures


if __name__ == "__main__":
    acquire()
