"""Shared encryption pass for Experiments B (histogram), C (entropy), D (correlation).

Encrypting every dataset image once and caching the (original, encrypted-BODY-only) byte
arrays avoids three redundant encryption passes across experiment_histogram.py,
experiment_entropy.py and experiment_correlation.py, which would otherwise each independently
re-run the (expensive) full encrypt pipeline over the same images.
"""

import os
import pickle

import numpy as np

import config
from common import encrypted_body
from generate_dataset import build_dataset
from isc_cipher.cipher import encrypt_bytes
from isc_cipher.generator import EXTRACTION_MANTISSA8_V1

CACHE_PATH = os.path.join(config.RESULTS_DIR, "stats_cache.pkl")


def build_stats_cache(sizes=None, extraction=EXTRACTION_MANTISSA8_V1, force=False):
    if os.path.exists(CACHE_PATH) and not force:
        with open(CACHE_PATH, "rb") as f:
            cache = pickle.load(f)
        if cache.get("extraction") == extraction and cache.get("sizes") == (sizes or config.PRIMARY_SIZES):
            return cache
    sizes = sizes or config.PRIMARY_SIZES
    images, _ = build_dataset(sizes=sizes)
    key = config.BASE_KEY
    entries = {}
    for (name, size, c), img in images.items():
        data = img.tobytes()
        ct = encrypt_bytes(key, data, size, size, c, backend="numpy", extraction=extraction)
        body, hdr = encrypted_body(ct)
        entries[(name, size, c)] = {
            "original": img,
            "body": body,  # bytes, length == size*size*c, header/nonce/tag excluded by construction
        }
    cache = {"extraction": extraction, "sizes": sizes, "entries": entries}
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    return cache


def body_as_image(body_bytes, h, w, c):
    arr = np.frombuffer(body_bytes, dtype=np.uint8)
    return arr.reshape((h, w) if c == 1 else (h, w, c))
