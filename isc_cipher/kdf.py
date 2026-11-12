"""Stage 1-2: key validation/generation and HKDF-SHA-256 derivations (algorithm_design.md §4).

HKDF follows RFC 5869 with SHA-256, implemented with the standard library (hmac, hashlib) so
that the reference path needs no third-party package. Tests check it against the RFC 5869
test vectors and against the independent `cryptography` implementation.
"""

import hashlib
import hmac
import os

from .errors import InvalidKey

KEY_LEN = 32
NONCE_LEN = 16
STREAMS = ("sbox", "perm", "fwd", "bwd")
LANES = 64
CONTEXT_PREFIX = b"ISC-IMG/v1"          # 10 bytes


def generate_key():
    """A fresh 32-byte key from the operating system CSPRNG."""
    return os.urandom(KEY_LEN)


def check_key(key):
    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_LEN:
        raise InvalidKey("key must be exactly 32 bytes (bytes or bytearray)")
    return bytes(key)


def hkdf_extract(salt, ikm):
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk, info, length):
    if not 0 < length <= 255 * 32:
        raise ValueError("invalid HKDF output length")
    out, block, counter = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def context(profile, dtype, h, w, c, extraction=None):
    """ctx = "ISC-IMG/v1" || u8(PROFILE) || u8(DTYPE) || BE16(H) || BE16(W) || u8(C)  (17 bytes).

    extraction=None (default) reproduces the original 17-byte V1 context byte-for-byte: every
    existing call site and every existing KAT vector depends on this exact behaviour. Passing
    extraction=1 or 2 appends one byte (u8(EXTRACTION)), binding the VERSION=2 extraction-method
    choice into every key/seed derived from this context (see
    hkdf_profile_binding_specification.md). This does not change HKDF-SHA-256 itself.
    """
    base = CONTEXT_PREFIX + bytes([profile, dtype]) + h.to_bytes(2, "big") + w.to_bytes(2, "big") + bytes([c])
    if extraction is None:
        return base
    if extraction not in (1, 2):
        raise ValueError("extraction must be 1 or 2")
    return base + bytes([extraction])


def lane_label(stream, lane):
    return f"lane/{stream}/{lane:04d}"


class Derivation:
    """All per-message derived values for (K, N, ctx)."""

    def __init__(self, key, nonce, ctx):
        if len(nonce) != NONCE_LEN:
            raise ValueError("nonce must be 16 bytes")
        self.ctx = ctx
        self._prk = hkdf_extract(nonce, key)

    def derive(self, label, length):
        return hkdf_expand(self._prk, self.ctx + b"\x00" + label.encode("ascii"), length)

    def mac_key(self):
        return self.derive("mac", 32)

    def kcv_key(self):
        return self.derive("kcv", 32)

    def ivs(self):
        iv = self.derive("iv", 2)
        return iv[0], iv[1]

    def seeds(self):
        """{stream: [16-byte seed for lane 0..63]} in canonical stream order."""
        return {g: [self.derive(lane_label(g, l), 16) for l in range(LANES)] for g in STREAMS}
