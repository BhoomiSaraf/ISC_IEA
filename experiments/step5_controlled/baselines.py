"""Step 5: Ablation baselines — V-CHACHA and V-STREAM-ISC.

V-CHACHA: identical envelope (HKDF, S-box, permutation, diffusion, HMAC) but replaces
the ISC generator with ChaCha20. Isolates the keystream source contribution.

V-STREAM-ISC: body = plaintext XOR ISC fwd stream bytes; no permutation, no S-box,
no diffusion. Isolates whether the confusion-diffusion envelope adds anything.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from isc_cipher import diffusion, sampling
from isc_cipher.kdf import Derivation, context, NONCE_LEN, STREAMS, LANES, check_key

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms


class ChaChaStream:
    """Drop-in replacement for ISC NpStream/RefStream that produces bytes from ChaCha20."""

    def __init__(self, key_32, nonce_16):
        # ChaCha20 uses a 16-byte nonce in the cryptography library
        self._key = key_32
        self._nonce = nonce_16
        self._offset = 0
        self.consumed = 0

    def take(self, n):
        cipher = Cipher(algorithms.ChaCha20(self._key, self._nonce), mode=None)
        enc = cipher.encryptor()
        # Seek to offset by encrypting zeros
        if self._offset > 0:
            enc.update(b"\x00" * self._offset)
        out = enc.update(b"\x00" * n)
        self._offset += n
        self.consumed += n
        return out


def _chacha_streams(derivation):
    """Build ChaCha20-based streams with the same HKDF labels as ISC."""
    streams = {}
    for g in STREAMS:
        chacha_key = derivation.derive(f"chacha/{g}", 32)
        chacha_nonce = derivation.derive(f"chacha/{g}/nonce", 16)
        streams[g] = ChaChaStream(chacha_key, chacha_nonce)
    return streams


def v_chacha_encrypt(key, data, h, w, c, nonce):
    """V-CHACHA: same envelope as ISC-IMG, ChaCha20 keystream."""
    import hashlib, hmac
    from isc_cipher import container
    key = check_key(key)
    n = h * w * c
    assert len(data) == n
    ctx = context(1, container.DTYPE_UINT8, h, w, c)
    der = Derivation(key, nonce, ctx)
    iv_f, iv_b = der.ivs()

    streams = _chacha_streams(der)
    S, S_inv = sampling.build_sbox(streams["sbox"])
    pi = sampling.build_permutation(streams["perm"], n)
    a = streams["fwd"].take(n)
    b = streams["bwd"].take(n)

    q = sampling.apply_permutation(data, pi)
    u = diffusion.forward(q, a, S, iv_f)
    body = diffusion.backward(u, b, S, iv_b)
    return body


def v_chacha_materials(key, nonce, h, w, c):
    """Return S, S_inv, pi, a, b, iv_f, iv_b for V-CHACHA (for metric measurement)."""
    from isc_cipher import container
    key = check_key(key)
    n = h * w * c
    ctx = context(1, container.DTYPE_UINT8, h, w, c)
    der = Derivation(key, nonce, ctx)
    iv_f, iv_b = der.ivs()
    streams = _chacha_streams(der)
    S, S_inv = sampling.build_sbox(streams["sbox"])
    pi = sampling.build_permutation(streams["perm"], n)
    a = streams["fwd"].take(n)
    b = streams["bwd"].take(n)
    return {"S": S, "S_inv": S_inv, "pi": pi, "a": a, "b": b,
            "iv_f": iv_f, "iv_b": iv_b}


def v_stream_isc_encrypt(key, data, h, w, c, nonce, extraction=1):
    """V-STREAM-ISC: body = plaintext XOR ISC fwd stream. No permutation/S-box/diffusion."""
    from isc_cipher import container
    from isc_cipher.generator import build_streams
    key = check_key(key)
    n = h * w * c
    assert len(data) == n
    ctx = context(1, container.DTYPE_UINT8, h, w, c)
    der = Derivation(key, nonce, ctx)
    streams = build_streams(der.seeds(), backend="numpy", profile=1, extraction=extraction)
    ks = streams["fwd"].take(n)
    body = bytes(d ^ k for d, k in zip(data, ks))
    return body
