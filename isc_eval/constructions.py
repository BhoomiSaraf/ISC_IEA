"""Constructions compared in Gate A (research/gate_a_plan.md §1).

Experimental (ISC-IMG v1 and ablations; same HKDF derivation, header, KCV and HMAC envelope):
  V-FULL   = ISC-IMG v1 (permutation -> forward -> backward diffusion with S-box)
  V-LINEAR = V-FULL with S = identity
  V-STREAM = body = p XOR fwd bytes
  V-PERM   = body = permuted p
Controlled comparison:
  V-CHACHA = V-FULL with every ISC stream replaced by ChaCha20 (key = HKDF label "chacha/<stream>",
             16-byte zero nonce/counter), bytes consumed identically; KCV field = 8 zero bytes
Standard AEAD baselines (cryptography library): AES-256-GCM, ChaCha20-Poly1305, AES-256-GCM-SIV.

`materials` re-derives everything exactly as isc_cipher.cipher._materials does (stage order, consumption
order); for source="isc" it calls that function directly. Fixed-nonce oracles cache the materials, which is
legitimate because encryption under one (K, N, dims) is deterministic.
"""

import hashlib
import hmac

from isc_cipher import container, diffusion, sampling
from isc_cipher.cipher import _kcv, _materials
from isc_cipher.kdf import STREAMS, Derivation, context

VARIANTS = ("V-FULL", "V-LINEAR", "V-STREAM", "V-PERM", "V-CHACHA")
AEADS = ("AES-256-GCM", "ChaCha20-Poly1305", "AES-256-GCM-SIV")
IDENTITY = list(range(256))


class ChaChaStream:
    def __init__(self, key32):
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        self._enc = Cipher(algorithms.ChaCha20(key32, bytes(16)), mode=None).encryptor()
        self.steps = 0
        self.consumed = 0

    def take(self, m):
        self.consumed += m
        return self._enc.update(bytes(m))


def materials(key, nonce, h, w, c, source="isc", backend="numpy"):
    if source == "isc":
        return _materials(key, nonce, 1, h, w, c, backend)
    if source != "chacha":
        raise ValueError(source)
    n = h * w * c
    der = Derivation(key, nonce, context(1, container.DTYPE_UINT8, h, w, c))
    iv_f, iv_b = der.ivs()
    streams = {g: ChaChaStream(der.derive(f"chacha/{g}", 32)) for g in STREAMS}
    S, S_inv = sampling.build_sbox(streams["sbox"])
    pi = sampling.build_permutation(streams["perm"], n)
    a = streams["fwd"].take(n)
    b = streams["bwd"].take(n)
    return {"k_mac": der.mac_key(), "k_kcv": der.kcv_key(), "S": S, "S_inv": S_inv, "pi": pi, "a": a, "b": b,
            "iv_f": iv_f, "iv_b": iv_b, "streams": streams}


def body_encrypt(variant, m, p):
    if variant in ("V-FULL", "V-CHACHA", "V-LINEAR"):
        S = IDENTITY if variant == "V-LINEAR" else m["S"]
        q = sampling.apply_permutation(p, m["pi"])
        return diffusion.backward(diffusion.forward(q, m["a"], S, m["iv_f"]), m["b"], S, m["iv_b"])
    if variant == "V-STREAM":
        return bytes(x ^ y for x, y in zip(p, m["a"]))
    if variant == "V-PERM":
        return sampling.apply_permutation(p, m["pi"])
    raise ValueError(variant)


def body_decrypt(variant, m, c):
    if variant in ("V-FULL", "V-CHACHA", "V-LINEAR"):
        Si = IDENTITY if variant == "V-LINEAR" else m["S_inv"]
        q = diffusion.inverse_np(c, m["a"], m["b"], Si, m["iv_f"], m["iv_b"])
        return sampling.invert_permutation(q, m["pi"])
    if variant == "V-STREAM":
        return bytes(x ^ y for x, y in zip(c, m["a"]))
    if variant == "V-PERM":
        return sampling.invert_permutation(c, m["pi"])
    raise ValueError(variant)


def _source(variant):
    return "chacha" if variant == "V-CHACHA" else "isc"


def seal(variant, key, nonce, data, h, w, c, m=None):
    """Full ciphertext in the ISC-IMG format (header, body, KCV, HMAC tag) for any variant."""
    m = m or materials(key, nonce, h, w, c, _source(variant))
    body = body_encrypt(variant, m, data)
    kcv = bytes(8) if variant == "V-CHACHA" else _kcv(m["k_kcv"], m["streams"])
    hdr = container.Header(profile=1, c=c, h=h, w=w, nonce=nonce, kcv=kcv).pack()
    return hdr + body + hmac.new(m["k_mac"], hdr + body, hashlib.sha256).digest()


def unseal(variant, key, z):
    """Verify tag first; then decrypt. Raises isc_cipher.AuthenticationError on tag mismatch."""
    from isc_cipher import AuthenticationError
    hdr, body, tag = container.parse(z)
    der = Derivation(key, hdr.nonce, context(hdr.profile, container.DTYPE_UINT8, hdr.h, hdr.w, hdr.c))
    if not hmac.compare_digest(tag, hmac.new(der.mac_key(), bytes(z)[:container.HEADER_LEN + hdr.n], hashlib.sha256).digest()):
        raise AuthenticationError("authentication failed")
    m = materials(key, hdr.nonce, hdr.h, hdr.w, hdr.c, _source(variant))
    return body_decrypt(variant, m, body)


class FixedNonceOracle:
    """Encryption oracle under one fixed (K, N, dims): the nonce-misuse model (test only)."""

    def __init__(self, variant, key, nonce, h, w, c):
        self.variant, self.n = variant, h * w * c
        self.m = materials(key, nonce, h, w, c, _source(variant))
        self.queries = 0

    def encrypt(self, p):
        self.queries += 1
        return body_encrypt(self.variant, self.m, bytes(p))


# --------------------------------------------------------------------------- AEAD baselines
def aead(name, key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESGCMSIV, ChaCha20Poly1305
    return {"AES-256-GCM": AESGCM, "ChaCha20-Poly1305": ChaCha20Poly1305, "AES-256-GCM-SIV": AESGCMSIV}[name](key)


def aead_aad(h, w, c):
    """Associated data: the same public fields the ISC-IMG header authenticates (format id, dims)."""
    return b"AEAD-IMG/v1" + h.to_bytes(2, "big") + w.to_bytes(2, "big") + bytes([c])


def aead_seal(name, key, data, h, w, c, nonce12):
    return nonce12 + aead(name, key).encrypt(nonce12, bytes(data), aead_aad(h, w, c))


def aead_open(name, key, z, h, w, c):
    return aead(name, key).decrypt(z[:12], z[12:], aead_aad(h, w, c))


def aead_body(name, key, data, h, w, c, nonce12):
    """Ciphertext body without nonce and tag (for statistics); the tag is the last 16 bytes."""
    return aead_seal(name, key, data, h, w, c, nonce12)[12:-16]
