"""Shared helpers for Phase 4B experiments. Read-only against isc_cipher/isc_seq/isc_eval.

All functions that need "the encrypted body only" use isc_cipher.container.parse(), which
returns (header, body, tag) without any manual byte-offset arithmetic, so header/nonce/KCV/tag
bytes can never leak into image statistics by construction.
"""

import hashlib
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from isc_cipher import container
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY
from isc_cipher.cipher import decrypt_bytes, encrypt_bytes
from isc_cipher.generator import EXTRACTION_K14_SCALED_MODULO_V1, EXTRACTION_MANTISSA8_V1

PROFILE_NAMES = {EXTRACTION_MANTISSA8_V1: "mantissa8_v1", EXTRACTION_K14_SCALED_MODULO_V1: "k14_scaled_modulo_v1"}


def encrypted_body(ciphertext):
    """Return only the encrypted BODY bytes of a ciphertext (never header/nonce/tag)."""
    hdr, body, tag = container.parse(ciphertext)
    return body, hdr


def fixed_nonce_encrypt(key, data, h, w, c, nonce, extraction=EXTRACTION_MANTISSA8_V1, backend="numpy"):
    """TEST-ONLY fixed-nonce encryption, for controlled differential comparisons only."""
    return encrypt_bytes_with_nonce_TEST_ONLY(key, data, h, w, c, nonce, backend=backend, extraction=extraction)


def shannon_entropy(byte_array):
    arr = np.frombuffer(bytes(byte_array), dtype=np.uint8)
    if arr.size == 0:
        return 0.0
    counts = np.bincount(arr, minlength=256).astype(np.float64)
    p = counts[counts > 0] / arr.size
    return float(-(p * np.log2(p)).sum())


def checksum(byte_array):
    return hashlib.sha256(bytes(byte_array)).hexdigest()


def chi_square_256(byte_array):
    """Chi-square goodness-of-fit against a uniform distribution over 256 byte values."""
    from scipy import stats
    arr = np.frombuffer(bytes(byte_array), dtype=np.uint8)
    observed = np.bincount(arr, minlength=256).astype(np.float64)
    expected = np.full(256, arr.size / 256.0)
    chi2, p = stats.chisquare(observed, expected)
    return float(chi2), float(p)


def adjacent_pixel_correlation(channel_2d):
    """Pearson correlation between adjacent pixels: horizontal, vertical, diagonal.

    channel_2d: 2D array (H, W) of a single channel (uint8 or similar).
    Returns dict with keys h, v, d and the (x, y) sample arrays used (for scatter plots).
    """
    a = channel_2d.astype(np.float64)
    h, w = a.shape
    out = {}
    pairs = {
        "horizontal": (a[:, :-1].ravel(), a[:, 1:].ravel()),
        "vertical": (a[:-1, :].ravel(), a[1:, :].ravel()),
        "diagonal": (a[:-1, :-1].ravel(), a[1:, 1:].ravel()),
    }
    for name, (x, y) in pairs.items():
        if x.size < 2 or np.std(x) == 0 or np.std(y) == 0:
            out[name] = {"r": float("nan"), "x": x, "y": y}
        else:
            r = float(np.corrcoef(x, y)[0, 1])
            out[name] = {"r": r, "x": x, "y": y}
    return out


def npcr_uaci(body1, body2):
    """NPCR and UACI between two equal-length BODY byte strings."""
    a = np.frombuffer(bytes(body1), dtype=np.uint8).astype(np.int64)
    b = np.frombuffer(bytes(body2), dtype=np.uint8).astype(np.int64)
    assert a.shape == b.shape, "bodies must be the same length for NPCR/UACI"
    n = a.size
    diff_mask = a != b
    n_diff = int(diff_mask.sum())
    npcr = 100.0 * n_diff / n
    uaci = 100.0 * np.mean(np.abs(a - b) / 255.0)
    return {
        "n_bytes": n,
        "n_diff_bytes": n_diff,
        "npcr_pct": float(npcr),
        "uaci_pct": float(uaci),
    }


def hamming_distance_bits(body1, body2):
    a = np.frombuffer(bytes(body1), dtype=np.uint8)
    b = np.frombuffer(bytes(body2), dtype=np.uint8)
    x = np.bitwise_xor(a, b)
    return int(np.unpackbits(x).sum())


def flip_key_bit(key, bit_index):
    """Return a copy of `key` (bytes, len 32) with exactly one bit flipped."""
    byte_i, bit_i = divmod(bit_index, 8)
    arr = bytearray(key)
    arr[byte_i] ^= (1 << bit_i)
    return bytes(arr)


def time_call(fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    t1 = time.perf_counter()
    return result, (t1 - t0)


def npcr_uaci_reference_expectation(n_bytes_unused=None):
    """Theoretical expectation for a byte stream behaving as i.i.d. uniform random bytes.

    These are the standard closed-form "random cipher" reference values (Wu, Noonan & Agaian
    2011) used ONLY as a descriptive reference point for what an ideal random byte stream would
    produce -- NOT a claim that meeting them proves security (per the Phase 4B instructions).
    NPCR_expected = (1 - 1/256) * 100
    UACI_expected = (1/(3*256)) * sum_{i=1}^{255} i*(i+1) / 256  -- the standard 33.46% figure.
    """
    npcr_expected = (1 - 1.0 / 256.0) * 100.0
    # Closed form from Wu et al.: UACI* = (1/255) * sum_{i=1}^{255} i(i+1)/256 / ... the commonly
    # cited constant is 33.4635%. We reproduce it by direct summation rather than hardcoding.
    total = 0.0
    for i in range(1, 256):
        total += i * (i + 1)
    uaci_expected = total / (255.0 * 256.0 * 256.0) * 100.0
    return {"npcr_expected_pct": npcr_expected, "uaci_expected_pct": uaci_expected}
