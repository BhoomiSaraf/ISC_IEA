"""Tests of the Gate A harness itself (isc_eval): the evaluation code must be correct before it is trusted."""

import os

import numpy as np
import pytest

from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY, materials_TEST_ONLY
from isc_eval import constructions as K
from isc_eval.common import public_key, public_nonce
from isc_eval.exp_misuse import attack_position_coding, linear_q_from_body
from isc_eval.exp_predict import berlekamp_massey_profile
from isc_eval.exp_sensitivity import ideal_npcr_uaci

KEY, NONCE = bytes(range(32)), bytes(range(16))


def test_public_keys_are_deterministic_and_distinct():
    assert public_key("x") == public_key("x") != public_key("y")
    assert len(public_key("x")) == 32 and len(public_nonce("x")) == 16 and len(public_nonce("x", 12)) == 12


def test_vfull_seal_equals_real_cipher():
    data = bytes(range(72))
    assert K.seal("V-FULL", KEY, NONCE, data, 4, 6, 3) == encrypt_bytes_with_nonce_TEST_ONLY(KEY, data, 4, 6, 3, NONCE)


@pytest.mark.parametrize("variant", K.VARIANTS)
def test_variants_roundtrip_and_reject_tamper(variant):
    data = bytes(np.random.default_rng(1).integers(0, 256, 75, dtype=np.uint8))
    z = K.seal(variant, KEY, NONCE, data, 5, 5, 3)
    assert K.unseal(variant, KEY, z) == data
    t = bytearray(z)
    t[40] ^= 1
    from isc_cipher import AuthenticationError
    with pytest.raises(AuthenticationError):
        K.unseal(variant, KEY, bytes(t))


def test_fixed_nonce_oracle_matches_seal_body():
    data = bytes(range(48))
    for v in K.VARIANTS:
        orc = K.FixedNonceOracle(v, KEY, NONCE, 4, 4, 3)
        assert orc.encrypt(data) == K.seal(v, KEY, NONCE, data, 4, 4, 3)[36:-32]


def test_chacha_stream_sequential_equals_single_take():
    a = K.ChaChaStream(bytes(32))
    b = K.ChaChaStream(bytes(32))
    assert a.take(5) + a.take(100) + a.take(0) == b.take(105)


@pytest.mark.parametrize("name", K.AEADS)
def test_aead_baselines_roundtrip(name):
    data = os.urandom(300)
    k = os.urandom(32)
    z = K.aead_seal(name, k, data, 10, 10, 3, os.urandom(12))
    assert K.aead_open(name, k, z, 10, 10, 3) == data
    assert len(K.aead_body(name, k, data, 10, 10, 3, os.urandom(12))) == 300


def test_linear_inversion_recovers_q_for_vlinear():
    m = materials_TEST_ONLY(KEY, NONCE, 8, 8, 1)
    orc = K.FixedNonceOracle("V-LINEAR", KEY, NONCE, 8, 8, 1)
    c0 = orc.encrypt(bytes(64))
    p = bytes(np.random.default_rng(2).integers(0, 256, 64, dtype=np.uint8))
    q_true = bytes(p[i] for i in m["pi"])
    assert linear_q_from_body(orc.encrypt(p), c0) == q_true


def test_position_coding_recovers_vperm_permutation():
    orc = K.FixedNonceOracle("V-PERM", KEY, NONCE, 20, 20, 1)
    pi_hat, digits = attack_position_coding(orc.encrypt, 400)
    assert digits == 2 and pi_hat == orc.m["pi"]


def test_berlekamp_massey_known_lfsr_and_random():
    # x^4 + x + 1 LFSR: s[i] = s[i-3] ^ s[i-4], linear complexity 4
    s = [1, 0, 0, 1]
    while len(s) < 200:
        s.append(s[-3] ^ s[-4])
    assert berlekamp_massey_profile(s)[-1] == 4
    rnd = np.random.default_rng(3).integers(0, 2, 2000)
    L = berlekamp_massey_profile(rnd)[-1]
    assert abs(L - 1000) <= 10


def test_ideal_npcr_uaci_values():
    v = ideal_npcr_uaci(256 * 256)
    assert abs(v["npcr_mean"] - 0.99609375) < 1e-12
    assert abs(v["uaci_mean"] - 0.334635) < 1e-6          # 33.4635% as reported by Wu et al.
