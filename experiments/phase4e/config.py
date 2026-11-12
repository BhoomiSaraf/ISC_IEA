"""Phase 4E shared configuration. No secret material is ever written to disk by any script
in this directory; keys/nonces used against the real isc_cipher are generated here and only
ever passed in-memory to the production API via isc_cipher._testing (TEST ONLY path).
"""
import hashlib

RESULTS_DIR = "results"
LOGS_DIR = "logs"
PLOTS_DIR = "plots"

# Fixed, deterministic, non-secret-in-a-real-sense key/nonce used only for this research
# experiment (never used for anything the project treats as confidential).
REAL_KEY = bytes(range(32))          # 0x00..0x1f
REAL_NONCE = bytes(range(16))        # 0x00..0x0f


def key_label(key: bytes) -> str:
    return "key:" + hashlib.sha256(key).hexdigest()[:12]


def nonce_label(nonce: bytes) -> str:
    return "nonce:" + hashlib.sha256(nonce).hexdigest()[:12]
