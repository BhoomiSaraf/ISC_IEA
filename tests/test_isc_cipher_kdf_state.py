"""Gate C, stages 1-3: key handling, HKDF derivations, seed -> initial-state mapping."""

import os
import random
from fractions import Fraction

import pytest

from isc_cipher import InvalidKey, generate_key, kdf
from isc_cipher.state_map import int_to_coord, seed_to_ints, seed_to_state


# ---------------------------------------------------------------- stage 1: key
def test_generate_key_is_32_random_bytes():
    k1, k2 = generate_key(), generate_key()
    assert isinstance(k1, bytes) and len(k1) == 32 and k1 != k2


@pytest.mark.parametrize("bad", [b"", b"\x00" * 31, b"\x00" * 33, "0" * 32, None, 123, list(range(32)), memoryview(b"\x00" * 32)])
def test_check_key_rejects_wrong_type_or_length(bad):
    with pytest.raises(InvalidKey):
        kdf.check_key(bad)


def test_check_key_accepts_bytes_and_bytearray():
    assert kdf.check_key(bytes(32)) == bytes(32)
    assert kdf.check_key(bytearray(32)) == bytes(32)


# ---------------------------------------------------------------- stage 2: HKDF
def test_hkdf_rfc5869_test_case_1():
    prk = kdf.hkdf_extract(bytes(range(13)), b"\x0b" * 22)
    assert prk.hex() == "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5"
    okm = kdf.hkdf_expand(prk, bytes(range(0xF0, 0xFA)), 42)
    assert okm.hex() == ("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
                         "34007208d5b887185865")


def test_hkdf_rfc5869_test_case_3_empty_salt_and_info():
    prk = kdf.hkdf_extract(b"", b"\x0b" * 22)
    assert prk.hex() == "19ef24a32c717b167f33a91d6f648bdf96596776afdb6377ac434c1c293ccb04"
    okm = kdf.hkdf_expand(prk, b"", 42)
    assert okm.hex() == ("8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d"
                         "9d201395faa4b61a96c8")


def test_hkdf_matches_cryptography_library():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    rng = random.Random(5)
    for _ in range(50):
        salt, ikm, info = os.urandom(16), os.urandom(32), os.urandom(rng.randrange(0, 60))
        length = rng.choice([2, 16, 32, 33, 64, 100])
        ours = kdf.hkdf_expand(kdf.hkdf_extract(salt, ikm), info, length)
        theirs = HKDF(hashes.SHA256(), length, salt, info).derive(ikm)
        assert ours == theirs


def test_hkdf_output_length_limits():
    prk = kdf.hkdf_extract(b"s", b"k")
    with pytest.raises(ValueError):
        kdf.hkdf_expand(prk, b"", 0)
    with pytest.raises(ValueError):
        kdf.hkdf_expand(prk, b"", 255 * 32 + 1)
    assert len(kdf.hkdf_expand(prk, b"", 255 * 32)) == 255 * 32


def test_context_bytes_exact():
    ctx = kdf.context(1, 1, 0x0102, 0x0304, 3)
    assert ctx == b"ISC-IMG/v1" + bytes([1, 1, 0x01, 0x02, 0x03, 0x04, 3])
    assert len(ctx) == 17


def test_derivation_labels_lengths_and_definition():
    key, nonce = bytes(range(32)), bytes(range(16))
    ctx = kdf.context(1, 1, 4, 6, 3)
    der = kdf.Derivation(key, nonce, ctx)
    prk = kdf.hkdf_extract(nonce, key)
    assert der.mac_key() == kdf.hkdf_expand(prk, ctx + b"\x00mac", 32)
    assert der.kcv_key() == kdf.hkdf_expand(prk, ctx + b"\x00kcv", 32)
    iv = kdf.hkdf_expand(prk, ctx + b"\x00iv", 2)
    assert der.ivs() == (iv[0], iv[1])
    seeds = der.seeds()
    assert list(seeds) == ["sbox", "perm", "fwd", "bwd"]
    assert all(len(seeds[g]) == 64 and all(len(s) == 16 for s in seeds[g]) for g in seeds)
    assert seeds["fwd"][5] == kdf.hkdf_expand(prk, ctx + b"\x00lane/fwd/0005", 16)
    assert kdf.lane_label("perm", 63) == "lane/perm/0063"
    all_seeds = [s for g in seeds for s in seeds[g]]
    assert len(set(all_seeds)) == 256                            # 259 derivations, all distinct here
    assert len({der.mac_key(), der.kcv_key()}) == 2


def test_derivation_depends_on_every_input():
    key, nonce = bytes(range(32)), bytes(range(16))
    base = kdf.Derivation(key, nonce, kdf.context(1, 1, 4, 6, 3)).mac_key()
    assert kdf.Derivation(bytes([1]) + key[1:], nonce, kdf.context(1, 1, 4, 6, 3)).mac_key() != base
    assert kdf.Derivation(key, bytes([1]) + nonce[1:], kdf.context(1, 1, 4, 6, 3)).mac_key() != base
    for ctx in (kdf.context(2, 1, 4, 6, 3), kdf.context(1, 1, 6, 4, 3), kdf.context(1, 1, 4, 18, 1)):
        assert kdf.Derivation(key, nonce, ctx).mac_key() != base


def test_derivation_rejects_wrong_nonce_length():
    with pytest.raises(ValueError):
        kdf.Derivation(bytes(32), bytes(15), kdf.context(1, 1, 1, 1, 1))


# ---------------------------------------------------------------- stage 3: mapping (Lemmas 1-3)
def seed_with(alpha, beta, low_a=0, low_b=0):
    return ((alpha << 11) | low_a).to_bytes(8, "big") + ((beta << 11) | low_b).to_bytes(8, "big")


@pytest.mark.parametrize("alpha,expected", [
    (0, -1.0), (1, -1.0 + 2.0 ** -52), (2 ** 52 - 1, -(2.0 ** -52)), (2 ** 52, 0.0), (2 ** 53 - 1, 1.0 - 2.0 ** -52)])
def test_mapping_boundaries(alpha, expected):
    x, y = seed_to_state(seed_with(alpha, alpha))
    assert x == expected and y == expected


def test_mapping_exact_against_rational_arithmetic():
    rng = random.Random(11)
    for _ in range(100000):
        m = rng.randrange(2 ** 53)
        v = int_to_coord(m)
        assert Fraction(v) == Fraction(m, 2 ** 52) - 1          # Lemma 1: exact
        assert -1 <= v < 1


def test_mapping_ignores_exactly_the_11_low_bits():
    rng = random.Random(12)
    for _ in range(200):
        a, b = rng.randrange(2 ** 53), rng.randrange(2 ** 53)
        target = seed_to_state(seed_with(a, b))
        for low in range(2 ** 11):                              # all 2^11 low patterns of the x half
            assert seed_to_state(seed_with(a, b, low_a=low))[0] == target[0]
        assert seed_to_state(seed_with(a, b, low_b=2 ** 11 - 1)) == target
        assert seed_to_state(seed_with(a ^ 1, b))[0] != target[0]   # the 53 kept bits are injective


def test_seed_to_ints_rejects_wrong_length():
    with pytest.raises(ValueError):
        seed_to_ints(bytes(15))


def test_frozen_parameters_match_isc_seq():
    from isc_cipher import isc_step
    from isc_seq.isc_map import FROZEN_PARAMS
    assert (isc_step.A, isc_step.C, isc_step.D, isc_step.W) == (
        FROZEN_PARAMS.a, FROZEN_PARAMS.c, FROZEN_PARAMS.d, FROZEN_PARAMS.omega) == (0.9, 0.4, 6.0, 10.0)
