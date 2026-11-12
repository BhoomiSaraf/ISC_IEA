"""ISC-IMG v1 encryption and decryption (algorithm_design.md §11), in the specified stage order:

  1 key validation  2 HKDF (salt = nonce)  3 seeds -> initial states  4 burn-in
  5 S-box, permutation, diffusion bytes  6 permute + diffuse, KCV, HMAC tag
Decryption: parse/validate -> verify tag -> profile self-test -> stages 2-5 -> inverse diffusion
-> inverse permutation -> verify KCV -> release plaintext.

Byte-level functions (encrypt_bytes / decrypt_bytes) need no NumPy with backend="reference".
"""

import hashlib
import hmac
import os

from . import container, diffusion, sampling
from .errors import AuthenticationError, InvalidImage, NumericalDivergenceError
from .generator import EXTRACTION_K14_SCALED_MODULO_V1, EXTRACTION_MANTISSA8_V1, EXTRACTIONS, build_streams, kcv_state_bytes
from .kdf import NONCE_LEN, Derivation, check_key, context
from .selftest import ensure_selftest

DEFAULT_BACKEND = "numpy"


def _validate_dims(h, w, c, n_data):
    if not (isinstance(h, int) and isinstance(w, int) and isinstance(c, int)):
        raise InvalidImage("dimensions must be integers")
    if not container.check_dims(h, w, c):
        raise InvalidImage("unsupported dimensions (1 <= H, W <= 65535, C in {1, 3}, H*W*C <= 2^24)")
    if n_data != h * w * c:
        raise InvalidImage("data length does not match dimensions")


def _materials(key, nonce, profile, h, w, c, backend, extraction=EXTRACTION_MANTISSA8_V1, ctx_extraction=None):
    """Stages 2-5. Returns dict with K_mac, K_kcv, S, S_inv, pi, a, b, iv_f, iv_b, streams.

    extraction selects the generator's byte-extraction function (threaded to build_streams).
    ctx_extraction controls whether/which EXTRACTION byte is folded into the HKDF context
    (hkdf_profile_binding_specification.md §2-4): None reproduces the original 17-byte V1
    context byte-for-byte; callers pass it explicitly (equal to `extraction`) only for
    VERSION=2 ciphertexts, so that VERSION=1 key/seed derivation is completely unaffected by
    this function gaining the extraction axis.
    """
    n = h * w * c
    der = Derivation(key, nonce, context(profile, container.DTYPE_UINT8, h, w, c, extraction=ctx_extraction))
    iv_f, iv_b = der.ivs()
    streams = _build_generators(der.seeds(), backend, profile, extraction)
    S, S_inv = sampling.build_sbox(streams["sbox"])
    pi = sampling.build_permutation(streams["perm"], n)
    a = streams["fwd"].take(n)
    b = streams["bwd"].take(n)
    return {"k_mac": der.mac_key(), "k_kcv": der.kcv_key(), "S": S, "S_inv": S_inv, "pi": pi,
            "a": a, "b": b, "iv_f": iv_f, "iv_b": iv_b, "streams": streams}


def _build_generators(seeds, backend, profile, extraction=EXTRACTION_MANTISSA8_V1):
    # separate function so tests can verify it is never reached before authentication.
    # Calls build_streams with exactly the original 3 keyword arguments whenever extraction is
    # the default: tests/test_isc_cipher_auth.py:test_kcv_detects_state_change_in_burn_in replaces
    # the module-level `build_streams` name with a 3-argument fake (seeds, backend, profile) and
    # must keep working unmodified; only the new, non-default extraction path passes the 4th
    # keyword, which no existing test exercises via that monkeypatch.
    if extraction == EXTRACTION_MANTISSA8_V1:
        return build_streams(seeds, backend=backend, profile=profile)
    return build_streams(seeds, backend=backend, profile=profile, extraction=extraction)


def _kcv(k_kcv, streams):
    return hmac.new(k_kcv, kcv_state_bytes(streams), hashlib.sha256).digest()[:8]


def _encrypt(key, data, h, w, c, nonce, backend, profile, extraction=EXTRACTION_MANTISSA8_V1, version=None):
    """extraction=EXTRACTION_MANTISSA8_V1 (default) and version=None together reproduce the
    original VERSION=1 / mantissa8_v1 ciphertext byte-for-byte. version=None auto-selects
    VERSION=1 when extraction is the default, VERSION=2 otherwise; it may be set explicitly
    (e.g. version=2 with extraction=1) for testing the VERSION=2 path end to end with the legacy
    extraction method. VERSION=1 never pairs with a non-default extraction (container.py rejects
    this combination; checked here too so the error is raised before any generator work).
    """
    key = check_key(key)
    data = bytes(data)
    _validate_dims(h, w, c, len(data))
    if len(nonce) != NONCE_LEN:
        raise ValueError("nonce must be 16 bytes")
    if extraction not in EXTRACTIONS:
        raise ValueError("unknown extraction identifier")
    if version is None:
        version = 1 if extraction == EXTRACTION_MANTISSA8_V1 else 2
    if version not in container.VERSIONS:
        raise ValueError("unsupported version")
    if version == 1 and extraction != EXTRACTION_MANTISSA8_V1:
        raise ValueError("VERSION=1 only supports extraction=1 (mantissa8_v1)")
    ensure_selftest(profile, backend)
    ctx_extraction = extraction if version == 2 else None
    m = _materials(key, nonce, profile, h, w, c, backend, extraction=extraction, ctx_extraction=ctx_extraction)
    q = sampling.apply_permutation(data, m["pi"])
    u = diffusion.forward(q, m["a"], m["S"], m["iv_f"])
    body = diffusion.backward(u, m["b"], m["S"], m["iv_b"])
    kcv = _kcv(m["k_kcv"], m["streams"])
    hdr = container.Header(profile=profile, c=c, h=h, w=w, nonce=bytes(nonce), kcv=kcv,
                            version=version, extraction=extraction).pack()
    tag = hmac.new(m["k_mac"], hdr + body, hashlib.sha256).digest()
    return hdr + body + tag


def encrypt_bytes(key, data, h, w, c, backend=DEFAULT_BACKEND, extraction=EXTRACTION_MANTISSA8_V1):
    """Encrypt n = h*w*c bytes (row-major, channel-last). Nonce from os.urandom; profile 1.

    extraction (default EXTRACTION_MANTISSA8_V1, i.e. today's only method) selects the
    byte-extraction function; omitting it produces a VERSION=1 ciphertext identical to before
    this parameter existed. Passing EXTRACTION_K14_SCALED_MODULO_V1 explicitly opts into the
    k=14 scaled-floor-modulo method (Step 1.1) and produces a VERSION=2 ciphertext. k14 is not
    the default: Phase 3B's multi-lane statistical validation has not yet run
    (phase_3b_validation_readiness.md), so no claim of statistical superiority is made or implied
    by its availability here.
    """
    return _encrypt(key, data, h, w, c, os.urandom(NONCE_LEN), backend, 1, extraction=extraction)


def decrypt_bytes(key, z, backend=DEFAULT_BACKEND):
    """Returns (data bytes, h, w, c). Raises before releasing anything unless tag and KCV verify.

    extraction is never a caller-supplied argument here: it is read from the parsed ciphertext
    header (hdr.extraction, which container.parse() defaults to 1 for VERSION=1 ciphertexts),
    exactly mirroring how `profile` already works -- self-describing from the ciphertext, not
    caller-chosen.
    """
    key = check_key(key)                                               # step 1
    hdr, body, tag = container.parse(z)                                # steps 2-6
    z = bytes(z)
    ctx_extraction = hdr.extraction if hdr.version == 2 else None
    der = Derivation(key, hdr.nonce, context(hdr.profile, container.DTYPE_UINT8, hdr.h, hdr.w, hdr.c,
                                              extraction=ctx_extraction))
    hl = container.header_len(hdr.version)
    expected = hmac.new(der.mac_key(), z[:hl + hdr.n], hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):                        # step 8
        raise AuthenticationError("authentication failed")
    ensure_selftest(hdr.profile, backend)                              # step 9
    m = _materials(key, hdr.nonce, hdr.profile, hdr.h, hdr.w, hdr.c, backend,
                   extraction=hdr.extraction, ctx_extraction=ctx_extraction)   # step 10
    inverse = diffusion.inverse_np if backend == "numpy" else diffusion.inverse_ref
    q = inverse(body, m["a"], m["b"], m["S_inv"], m["iv_f"], m["iv_b"])          # steps 11-12
    p = sampling.invert_permutation(q, m["pi"])                                   # step 13
    if not hmac.compare_digest(hdr.kcv, _kcv(m["k_kcv"], m["streams"])):         # step 14
        raise NumericalDivergenceError("regenerated lane states do not match the KCV")
    return p, hdr.h, hdr.w, hdr.c                                                 # step 15


def _image_to_bytes(image):
    import numpy as np
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise InvalidImage("image must be a numpy uint8 array")
    if image.ndim == 2:
        h, w = image.shape
        c = 1
    elif image.ndim == 3 and image.shape[2] == 3:
        h, w, c = image.shape
    else:
        raise InvalidImage("shape must be (H, W) or (H, W, 3)")
    if not container.check_dims(h, w, c):
        raise InvalidImage("unsupported dimensions")
    return np.ascontiguousarray(image).tobytes(), h, w, c


def encrypt(key, image, backend=DEFAULT_BACKEND, extraction=EXTRACTION_MANTISSA8_V1):
    """Encrypt a uint8 array of shape (H, W) or (H, W, 3). Returns the ciphertext bytes."""
    data, h, w, c = _image_to_bytes(image)
    return encrypt_bytes(key, data, h, w, c, backend, extraction=extraction)


def decrypt(key, ciphertext, backend=DEFAULT_BACKEND):
    """Decrypt to a uint8 array of shape (H, W) or (H, W, 3)."""
    import numpy as np
    data, h, w, c = decrypt_bytes(key, ciphertext, backend)
    arr = np.frombuffer(data, dtype=np.uint8)
    return arr.reshape((h, w) if c == 1 else (h, w, 3)).copy()
