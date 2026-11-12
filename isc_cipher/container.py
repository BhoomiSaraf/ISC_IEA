"""Ciphertext format and validation (algorithm_design.md §10, §11.2 steps 2-6).

VERSION=1 (original, unchanged):
offset size field
0      4    magic "ISCI"
4      1    VERSION = 1
5      1    PROFILE (1 normative, 2 comparison)
6      1    DTYPE = 1 (uint8)
7      1    C in {1, 3}
8      2    H (BE16, 1..65535)
10     2    W (BE16, 1..65535)
12     16   nonce N
28     8    KCV
36     n    body
36+n   32   tag = HMAC-SHA-256(K_mac, bytes[0 : 36+n])

VERSION=2 (Phase 3A addition): identical to VERSION=1 for offsets 0-35; adds one EXTRACTION byte
at offset 36 (1 = mantissa8_v1, 2 = k14_scaled_modulo_v1), shifting body/tag by one byte:
offset size field
...    ...  (unchanged, offsets 0-35, VERSION byte = 2)
36     1    EXTRACTION (1 or 2)
37     n    body
37+n   32   tag = HMAC-SHA-256(K_mac, bytes[0 : 37+n])

A VERSION=1 ciphertext is never reinterpreted as VERSION=2 or vice versa: the VERSION byte at a
fixed offset (4) is read first and selects the entire subsequent parsing path. See
container_v2_binary_specification.md for the full design rationale.
"""

from dataclasses import dataclass

from .errors import Malformed

MAGIC = b"ISCI"
VERSION = 1                      # kept for backward compatibility; VERSIONS below is authoritative
VERSIONS = (1, 2)
DTYPE_UINT8 = 1
PROFILES = (1, 2)
EXTRACTIONS = (1, 2)
HEADER_LEN = 36                  # VERSION=1 header length; kept as-is (isc_eval/constructions.py uses
                                  # this name directly and only ever handles VERSION=1 ciphertexts)
HEADER_LEN_V1 = 36
HEADER_LEN_V2 = 37
TAG_LEN = 32
MAX_N = 1 << 24
MAX_DIM = 65535


def header_len(version):
    if version == 1:
        return HEADER_LEN_V1
    if version == 2:
        return HEADER_LEN_V2
    raise Malformed("unsupported version")


@dataclass(frozen=True)
class Header:
    profile: int
    c: int
    h: int
    w: int
    nonce: bytes
    kcv: bytes
    version: int = 1
    extraction: int = 1

    @property
    def n(self):
        return self.h * self.w * self.c

    def pack(self):
        if self.version not in VERSIONS:
            raise Malformed("unsupported version")
        base = (MAGIC + bytes([self.version, self.profile, DTYPE_UINT8, self.c])
                + self.h.to_bytes(2, "big") + self.w.to_bytes(2, "big") + self.nonce + self.kcv)
        if self.version == 1:
            if self.extraction != 1:
                raise Malformed("VERSION=1 only supports extraction=1 (mantissa8_v1)")
            return base
        # version == 2
        if self.extraction not in EXTRACTIONS:
            raise Malformed("unsupported extraction identifier")
        return base + bytes([self.extraction])


def check_dims(h, w, c):
    """True if the dimensions are within v1/v2 limits (identical for both versions)."""
    return (1 <= h <= MAX_DIM and 1 <= w <= MAX_DIM and c in (1, 3) and h * w * c <= MAX_N)


def parse(z):
    """Validation steps 2-6 of §11.2 (everything that needs no key). Returns (Header, body, tag).

    Reads MAGIC and VERSION first and selects the version-appropriate header length *before*
    computing or validating anything that depends on it (body/tag offsets, total length). A
    VERSION=1 ciphertext is always parsed on the VERSION=1 path (extraction implicitly 1); a
    VERSION=2 ciphertext is always parsed on the VERSION=2 path, which also validates the new
    EXTRACTION field. There is no code path that reads a VERSION=1 byte string under the
    VERSION=2 field layout, or vice versa.
    """
    if not isinstance(z, (bytes, bytearray)):
        raise Malformed("ciphertext must be bytes")
    z = bytes(z)
    if len(z) < 5:
        raise Malformed("ciphertext too short")
    if z[0:4] != MAGIC:
        raise Malformed("bad magic")
    version = z[4]
    if version not in VERSIONS:
        raise Malformed("unsupported version")
    hl = header_len(version)
    if len(z) < hl + 1 + TAG_LEN:
        raise Malformed("ciphertext too short")
    profile, dtype, c = z[5], z[6], z[7]
    h = int.from_bytes(z[8:10], "big")
    w = int.from_bytes(z[10:12], "big")
    if profile not in PROFILES or dtype != DTYPE_UINT8 or c not in (1, 3) or h == 0 or w == 0:
        raise Malformed("unsupported or invalid header field")
    extraction = 1
    if version == 2:
        extraction = z[36]
        if extraction not in EXTRACTIONS:
            raise Malformed("unsupported extraction identifier")
    n = h * w * c
    if n > MAX_N or len(z) != hl + n + TAG_LEN:
        raise Malformed("size limit exceeded or length mismatch")
    hdr = Header(profile=profile, c=c, h=h, w=w, nonce=z[12:28], kcv=z[28:36], version=version,
                 extraction=extraction)
    return hdr, z[hl:hl + n], z[hl + n:]
