"""TEST ONLY. Do not use for real encryption.

Fixed-nonce encryption is needed to produce and check known-answer vectors (Gate C/R) and, later,
for the pre-registered nonce-misuse experiments. The public API (isc_cipher.encrypt) never accepts a
nonce (threat_model.md §6).
"""

from .cipher import _encrypt, _materials
from .generator import EXTRACTION_MANTISSA8_V1


def encrypt_bytes_with_nonce_TEST_ONLY(key, data, h, w, c, nonce, backend="numpy", profile=1,
                                        extraction=EXTRACTION_MANTISSA8_V1, version=None):
    return _encrypt(key, data, h, w, c, nonce, backend, profile, extraction=extraction, version=version)


def materials_TEST_ONLY(key, nonce, h, w, c, backend="numpy", profile=1,
                         extraction=EXTRACTION_MANTISSA8_V1, version=None):
    """Derived per-message values (S, pi, a, b, ivs, streams) for KAT generation and checks."""
    if version is None:
        version = 1 if extraction == EXTRACTION_MANTISSA8_V1 else 2
    ctx_extraction = extraction if version == 2 else None
    return _materials(key, nonce, profile, h, w, c, backend, extraction=extraction, ctx_extraction=ctx_extraction)
