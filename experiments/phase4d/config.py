"""Phase 4D configuration: paths, seeds, non-secret labeling helpers.

Independent of experiments/phase4b/ and experiments/phase4c/ (not imported
from either, per isolation requirement) but follows the same conventions
for reproducibility.
"""

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

RESULTS_DIR = os.path.join(ROOT, "results")
PLOTS_DIR = os.path.join(ROOT, "plots")
LOGS_DIR = os.path.join(ROOT, "logs")

for _d in (RESULTS_DIR, PLOTS_DIR, LOGS_DIR):
    os.makedirs(_d, exist_ok=True)

MASTER_SEED = 20261112  # fixed, arbitrary, documented (date this phase started)

# Frozen literal fixture bytes, independently generated for Phase 4D (distinct
# from Phase 4B's and Phase 4C's BASE_KEY/BASE_NONCE) via os.urandom() once,
# then frozen as literals for reproducibility. These are TEST fixtures only,
# never real secrets; they are still never written to any result/log file in
# plaintext -- only through label()/key_label()/nonce_label() below.
KEY_A = bytes.fromhex(
    "1b6f4d9e2a7c5f81b3d6e9a0c4f7b2d5e8a1c4f7b0d3e6a9c2f5b8e1a4d7c0f3"
)[:32]
KEY_B = bytes.fromhex(   # related-key fixture: KEY_A with bit 0 of byte 0 flipped
    "1a6f4d9e2a7c5f81b3d6e9a0c4f7b2d5e8a1c4f7b0d3e6a9c2f5b8e1a4d7c0f3"
)[:32]
NONCE_A = bytes.fromhex("7e2c9a4f1d6b8e3c0a5f7d2b9e4c1a6f")[:16]
NONCE_B = bytes.fromhex("3f8b1d6e9a2c5f0b7e4a1d8c6f3b0e9a")[:16]

assert len(KEY_A) == len(KEY_B) == 32
assert len(NONCE_A) == len(NONCE_B) == 16
assert KEY_A != KEY_B and NONCE_A != NONCE_B


def key_label(key):
    """Non-secret identifier for a key: first 8 hex chars of SHA-256(key)."""
    return "K-" + hashlib.sha256(key).hexdigest()[:8]


def nonce_label(nonce):
    """Non-secret identifier for a nonce: first 8 hex chars of SHA-256(nonce)."""
    return "N-" + hashlib.sha256(nonce).hexdigest()[:8]


BACKEND = "numpy"
PROFILE_MANTISSA8 = 1   # isc_cipher.generator.EXTRACTION_MANTISSA8_V1, verified by reading source
PROFILE_K14 = 2         # isc_cipher.generator.EXTRACTION_K14_SCALED_MODULO_V1

ENV_INFO = {
    "python": sys.version,
    "platform": sys.platform,
}
try:
    import numpy as _np
    ENV_INFO["numpy"] = _np.__version__
except Exception:
    ENV_INFO["numpy"] = "unavailable"
