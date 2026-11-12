"""Shared helpers for Phase 4C experiments. Isolated from phase4b/common.py
(not imported), but follows the same body-bytes-only extraction convention.
"""
import numpy as np

from isc_cipher.container import parse as container_parse


def body_bytes(ciphertext: bytes) -> bytes:
    """Return only the ciphertext BODY (never header/nonce/KCV/HMAC tag)."""
    hdr, body, _tag = container_parse(ciphertext)
    return body


def shannon_entropy(byte_array: np.ndarray) -> float:
    counts = np.bincount(np.asarray(byte_array, dtype=np.uint8).reshape(-1), minlength=256)
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-(p * np.log2(p)).sum())


def adjacent_correlation(arr: np.ndarray):
    """Pearson r for horizontal/vertical/diagonal adjacent-pixel pairs on a
    single 2D uint8 channel array."""
    arr = arr.astype(np.float64)
    h, horiz = arr[:, :-1].ravel(), arr[:, 1:].ravel()
    v_top, v_bot = arr[:-1, :].ravel(), arr[1:, :].ravel()
    d_tl, d_br = arr[:-1, :-1].ravel(), arr[1:, 1:].ravel()

    def _r(x, y):
        if x.std() == 0 or y.std() == 0:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    return _r(h, horiz), _r(v_top, v_bot), _r(d_tl, d_br)
