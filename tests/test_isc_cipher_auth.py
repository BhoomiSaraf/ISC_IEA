"""Gate C: authentication, tampering, malformed input, wrong keys, no release before authentication, KCV."""

import hashlib
import hmac
import os

import numpy as np
import pytest

from isc_cipher import (AuthenticationError, InvalidKey, Malformed, NumericalDivergenceError, ProfileError,
                        cipher, decrypt, decrypt_bytes, kdf)
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY, materials_TEST_ONLY
from isc_cipher.generator import kcv_state_bytes

KEY = bytes(range(32))
NONCE = bytes(range(16))
H, W, C = 4, 6, 3
DATA = bytes((i * 37 + 11) % 256 for i in range(H * W * C))


@pytest.fixture(scope="module")
def z():
    return encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE)


@pytest.fixture
def no_generator(monkeypatch):
    """Any attempt to build generators fails loudly: proves the tag is checked first."""
    def boom(*a, **k):
        raise AssertionError("generator work before authentication")
    monkeypatch.setattr(cipher, "_build_generators", boom)


def test_valid_ciphertext_decrypts(z):
    assert decrypt_bytes(KEY, z)[0] == DATA


def test_header_layout(z):
    assert z[0:4] == b"ISCI" and z[4] == 1 and z[5] == 1 and z[6] == 1 and z[7] == C
    assert int.from_bytes(z[8:10], "big") == H and int.from_bytes(z[10:12], "big") == W
    assert z[12:28] == NONCE and len(z) == 36 + H * W * C + 32
    k_mac = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C)).mac_key()
    assert z[-32:] == hmac.new(k_mac, z[:-32], hashlib.sha256).digest()      # tag over bytes [0, 36+n)


def test_every_bit_flip_rejected_before_generation(z, no_generator):
    for i in range(len(z)):
        for bit in range(8):
            t = bytearray(z)
            t[i] ^= 1 << bit
            with pytest.raises((AuthenticationError, Malformed)):
                decrypt_bytes(KEY, bytes(t))


def test_truncation_and_extension_rejected(z, no_generator):
    for k in range(1, 65):
        with pytest.raises(Malformed):
            decrypt_bytes(KEY, z[:-k])
        with pytest.raises(Malformed):
            decrypt_bytes(KEY, z + bytes(k))


@pytest.fixture(scope="module")
def other():
    # built before the no_generator guard is installed (the guard must only see decryption work)
    return encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, bytes(16))


def test_swapping_nonce_kcv_or_tag_between_ciphertexts_rejected(z, other, no_generator):
    for lo, hi in ((12, 28), (28, 36), (len(z) - 32, len(z))):
        t = z[:lo] + other[lo:hi] + z[hi:]
        with pytest.raises(AuthenticationError):
            decrypt_bytes(KEY, t)


def test_dimension_relabelling_rejected(z, no_generator):
    relabel = [(6, 4, 3), (1, 72, 1), (72, 1, 1), (8, 9, 1), (3, 8, 3)]       # same n = 72
    for h, w, c in relabel:
        t = bytearray(z)
        t[7] = c
        t[8:10] = h.to_bytes(2, "big")
        t[10:12] = w.to_bytes(2, "big")
        with pytest.raises(AuthenticationError):
            decrypt_bytes(KEY, bytes(t))


def test_profile_field_change_rejected(z, no_generator):
    t = bytearray(z)
    t[5] = 2
    with pytest.raises(AuthenticationError):
        decrypt_bytes(KEY, bytes(t))


def test_wrong_keys_rejected_before_generation(z, no_generator):
    for _ in range(200):
        with pytest.raises(AuthenticationError):
            decrypt_bytes(os.urandom(32), z)
    with pytest.raises(AuthenticationError):
        decrypt_bytes(bytes([KEY[0] ^ 1]) + KEY[1:], z)


@pytest.mark.parametrize("bad_key", [b"", bytes(31), bytes(33), "k" * 32, None])
def test_invalid_key_types(z, bad_key):
    with pytest.raises(InvalidKey):
        decrypt_bytes(bad_key, z)


def _hdr(magic=b"ISCI", version=1, profile=1, dtype=1, c=1, h=2, w=2, extra=0, n=None):
    n = h * w * c if n is None else n
    return magic + bytes([version, profile, dtype, c]) + h.to_bytes(2, "big") + w.to_bytes(2, "big") \
        + bytes(24) + bytes(n + extra) + bytes(32)


@pytest.mark.parametrize("blob", [
    b"", b"ISCI", bytes(68),                                   # too short / empty
    _hdr(magic=b"ISCX"), _hdr(version=2), _hdr(profile=0), _hdr(profile=3), _hdr(dtype=2),
    _hdr(c=2, h=2, w=2), _hdr(c=0), _hdr(h=0, n=4), _hdr(w=0, n=4),
    _hdr(extra=1), _hdr(extra=-1),                             # length mismatch
    _hdr(h=4097, w=4096, n=0),                                 # n > 2^24 (declared), short body
])
def test_malformed_ciphertexts(blob, no_generator):
    with pytest.raises(Malformed):
        decrypt_bytes(KEY, blob)


def test_non_bytes_ciphertext_rejected():
    for bad in ("text", None, 12, [1, 2, 3]):
        with pytest.raises(Malformed):
            decrypt_bytes(KEY, bad)


def test_kcv_definition_exact(z):
    m = materials_TEST_ONLY(KEY, NONCE, H, W, C)
    k_kcv = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C)).kcv_key()
    sb = kcv_state_bytes(m["streams"])
    assert len(sb) == 4 * (64 * 16 + 8) == 4128
    assert hmac.new(k_kcv, sb, hashlib.sha256).digest()[:8] == z[28:36]


@pytest.mark.parametrize("call,elem", [(499, 3), (500, 3), (501, 3), (502, 3), (500, 10), (2000, 100), (3070, 255)])
def test_kcv_fails_iff_final_states_differ_and_never_releases_wrong_plaintext(z, monkeypatch, call, elem):
    """A 1-ulp change of one SIN result during decryption (burn-in, all 256 lanes) either
    (a) is absorbed by rounding -> final states identical -> correct plaintext returned, or
    (b) changes the final states -> NumericalDivergenceError.  A wrong plaintext is never returned."""
    import math
    from isc_cipher import fdlibm_np
    from isc_cipher import cipher as cm
    real = fdlibm_np.sin
    calls = {"n": 0}

    def perturbed(x):
        out = real(x)
        calls["n"] += 1
        if calls["n"] == call:
            out = out.copy()
            out[elem] = math.nextafter(out[elem], 2.0)
        return out
    seen = {}
    real_kcv = cm._kcv

    def spy(k, streams):
        seen["states"] = kcv_state_bytes(streams)
        return real_kcv(k, streams)
    monkeypatch.setattr(cm, "_kcv", spy)
    monkeypatch.setattr(fdlibm_np, "sin", perturbed)
    reference_states = kcv_state_bytes(materials_TEST_ONLY(KEY, NONCE, H, W, C, backend="reference")["streams"])
    try:
        out = decrypt_bytes(KEY, z)[0]
        raised = False
    except NumericalDivergenceError:
        raised = True
    assert calls["n"] >= call                                  # the perturbation actually happened
    states_differ = seen["states"] != reference_states
    assert raised == states_differ
    if not raised:
        assert out == DATA


def test_kcv_detects_state_change_in_burn_in(z, monkeypatch):
    """Deterministic divergence: perturb one lane state right after burn-in."""
    from isc_cipher import cipher as cm
    real = cm.build_streams

    def build(seeds, backend, profile):
        st = real(seeds, backend=backend, profile=profile)
        s = st["perm"]
        s.x = s.x.copy()
        s.x[5] = np.nextafter(s.x[5], 2.0)
        return st
    monkeypatch.setattr(cm, "build_streams", build)
    with pytest.raises(NumericalDivergenceError):
        decrypt_bytes(KEY, z)


def test_kcv_detects_divergence_in_last_output_step(z, monkeypatch):
    """Perturb a lane state after the final output step only: KCV must still differ."""
    from isc_cipher import cipher as cm
    real = cm._kcv

    def tampered_kcv(k, streams):
        s = streams["bwd"]
        s.x = s.x.copy()
        s.x[0] = np.nextafter(s.x[0], 2.0)
        return real(k, streams)
    monkeypatch.setattr(cm, "_kcv", tampered_kcv)
    with pytest.raises(NumericalDivergenceError):
        decrypt_bytes(KEY, z)


def test_selftest_failure_blocks_decryption(z, monkeypatch):
    from isc_cipher import _selftest_vectors, selftest
    monkeypatch.setattr(selftest, "_DONE", set())
    bad = list(_selftest_vectors.TRIG)
    bad[0] = (bad[0][0], "0000000000000000", bad[0][2])
    monkeypatch.setattr(_selftest_vectors, "TRIG", bad)
    with pytest.raises(ProfileError):
        decrypt_bytes(KEY, z)


def test_profile2_roundtrip_numpy_only():
    z2 = encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, backend="numpy", profile=2)
    assert z2[5] == 2
    assert decrypt_bytes(KEY, z2, backend="numpy")[0] == DATA
    with pytest.raises(ProfileError):
        decrypt_bytes(KEY, z2, backend="reference")


def test_array_api_rejects_tampered(z, no_generator):
    t = bytearray(z)
    t[40] ^= 1
    with pytest.raises(AuthenticationError):
        decrypt(KEY, bytes(t))
