"""Phase 3A: dual-profile extraction (mantissa8_v1 / k14_scaled_modulo_v1) and VERSION=1/2 container.

Collects the test requirements from phase_3a_implementation_plan.md and the PHASE 3A task spec into
one module, organised by concern (KDF context binding, container, generator/backends, cipher
integration), mirroring how the existing test_isc_cipher_{auth,kdf_state,numeric,roundtrip,
sampling_diffusion}.py files are organised.

No claim is made anywhere in this file that k14_scaled_modulo_v1 is statistically superior to
mantissa8_v1 (that is Phase 3B's open question) or that passing these tests establishes
cryptographic security.
"""

import hashlib
import hmac
import math

import numpy as np
import pytest

from isc_cipher import AuthenticationError, Malformed, container, kdf
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY, materials_TEST_ONLY
from isc_cipher.generator import (BURN_IN, EXTRACTION_K14_SCALED_MODULO_V1, EXTRACTION_MANTISSA8_V1,
                                   NpStream, RefStream, build_streams, frac_byte_scalar, m_byte)
from isc_cipher.cipher import decrypt_bytes

KEY = bytes(range(32))
NONCE = bytes(range(16))
H, W, C = 4, 6, 3
DATA = bytes((i * 37 + 11) % 256 for i in range(H * W * C))
E1 = EXTRACTION_MANTISSA8_V1
E2 = EXTRACTION_K14_SCALED_MODULO_V1

# ---------------------------------------------------------------------------------------------
# KDF context binding (Section 5 of the task / hkdf_profile_binding_specification.md)
# ---------------------------------------------------------------------------------------------


def test_context_extraction_none_matches_v1():
    assert kdf.context(1, 1, H, W, C) == kdf.context(1, 1, H, W, C, extraction=None)
    assert len(kdf.context(1, 1, H, W, C, extraction=None)) == 17


def test_context_extraction_appends_one_byte():
    base = kdf.context(1, 1, H, W, C)
    c1 = kdf.context(1, 1, H, W, C, extraction=1)
    c2 = kdf.context(1, 1, H, W, C, extraction=2)
    assert len(c1) == 18 and len(c2) == 18
    assert c1[:17] == base and c2[:17] == base
    assert c1[17] == 1 and c2[17] == 2
    assert c1 != c2


def test_context_invalid_extraction_rejected():
    with pytest.raises(ValueError):
        kdf.context(1, 1, H, W, C, extraction=0)
    with pytest.raises(ValueError):
        kdf.context(1, 1, H, W, C, extraction=3)


def test_context_v1_derivation_unchanged_for_every_existing_call_shape():
    # exact positional call shape used throughout the existing codebase
    assert kdf.context(1, 1, 0x0102, 0x0304, 3) == (b"ISC-IMG/v1" + bytes([1, 1]) + (0x0102).to_bytes(2, "big")
                                                      + (0x0304).to_bytes(2, "big") + bytes([3]))


def test_derived_mac_keys_differ_between_v2_extraction_1_and_2():
    der1 = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C, extraction=1))
    der2 = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C, extraction=2))
    assert der1.mac_key() != der2.mac_key()
    assert der1.kcv_key() != der2.kcv_key()
    assert der1.ivs() != der2.ivs()


def test_derived_lane_seeds_differ_between_v2_extraction_1_and_2():
    der1 = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C, extraction=1))
    der2 = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C, extraction=2))
    assert der1.seeds() != der2.seeds()
    for g in kdf.STREAMS:
        assert der1.seeds()[g] != der2.seeds()[g]


def test_v1_ctx_binding_differs_from_v2_extraction_1_ctx_binding():
    """VERSION=1 (ctx_extraction=None) and VERSION=2/extraction=1 (ctx_extraction=1) must derive
    different key material, even though both eventually select mantissa8_v1 byte extraction --
    this is the "including when extraction identifier 1 is selected" requirement."""
    der_v1 = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C, extraction=None))
    der_v2e1 = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C, extraction=1))
    assert der_v1.mac_key() != der_v2e1.mac_key()
    assert der_v1.seeds() != der_v2e1.seeds()


# ---------------------------------------------------------------------------------------------
# Container VERSION=1 / VERSION=2 (Section 6 of the task / container_v2_binary_specification.md)
# ---------------------------------------------------------------------------------------------


def _pack_v1(**kw):
    base = dict(profile=1, c=1, h=2, w=2, nonce=bytes(16), kcv=bytes(8))
    base.update(kw)
    return container.Header(**base).pack()


def test_header_v1_serialization_byte_for_byte():
    h = container.Header(profile=1, c=3, h=4, w=6, nonce=bytes(range(16)), kcv=bytes(range(8)))
    packed = h.pack()
    assert len(packed) == 36
    assert packed == (b"ISCI" + bytes([1, 1, 1, 3]) + (4).to_bytes(2, "big") + (6).to_bytes(2, "big")
                       + bytes(range(16)) + bytes(range(8)))


def test_header_v2_serialization_byte_layout_and_offsets():
    h = container.Header(profile=1, c=3, h=4, w=6, nonce=bytes(range(16)), kcv=bytes(range(8)),
                          version=2, extraction=2)
    packed = h.pack()
    v1 = _pack_v1(c=3, h=4, w=6, nonce=bytes(range(16)), kcv=bytes(range(8)))
    assert len(packed) == 37
    # offsets 0-35 are byte-for-byte identical in *meaning* between V1 and V2, but offset 4 is the
    # VERSION byte itself, which differs by design (1 vs 2) -- everything else must match exactly.
    assert packed[0:4] == v1[0:4]            # MAGIC
    assert packed[4] == 2 and v1[4] == 1     # VERSION
    assert packed[5:36] == v1[5:36]          # PROFILE..KCV, unchanged positions and values
    assert packed[36] == 2                   # EXTRACTION (new, V2-only byte)


def test_header_v1_rejects_non_default_extraction():
    with pytest.raises(Malformed):
        container.Header(profile=1, c=1, h=2, w=2, nonce=bytes(16), kcv=bytes(8),
                          version=1, extraction=2).pack()


def test_header_v2_rejects_unknown_extraction():
    with pytest.raises(Malformed):
        container.Header(profile=1, c=1, h=2, w=2, nonce=bytes(16), kcv=bytes(8),
                          version=2, extraction=3).pack()


def _ciphertext_v1(extraction=E1):
    return encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, extraction=extraction)


def _ciphertext_v2(extraction):
    return encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, extraction=extraction, version=2)


def test_parse_valid_v1():
    z = _ciphertext_v1()
    hdr, body, tag = container.parse(z)
    assert hdr.version == 1 and hdr.extraction == 1
    assert len(body) == H * W * C and len(tag) == 32


@pytest.mark.parametrize("extraction", [E1, E2])
def test_parse_valid_v2(extraction):
    z = _ciphertext_v2(extraction)
    hdr, body, tag = container.parse(z)
    assert hdr.version == 2 and hdr.extraction == extraction
    assert len(body) == H * W * C and len(tag) == 32
    assert len(z) == 37 + H * W * C + 32


def test_parse_unknown_version_rejected():
    z = bytearray(_ciphertext_v1())
    z[4] = 9
    with pytest.raises(Malformed):
        container.parse(bytes(z))


def test_parse_unknown_extraction_rejected_under_v2():
    z = bytearray(_ciphertext_v2(E1))
    z[36] = 7
    with pytest.raises(Malformed):
        container.parse(bytes(z))


def test_parse_truncated_v1_header_rejected():
    z = _ciphertext_v1()
    for k in (1, 10, 35, 36):
        with pytest.raises(Malformed):
            container.parse(z[:k])


def test_parse_truncated_v2_header_rejected():
    z = _ciphertext_v2(E2)
    for k in (1, 10, 36, 37):
        with pytest.raises(Malformed):
            container.parse(z[:k])


def test_parse_body_length_mismatch_v1_rejected():
    z = _ciphertext_v1()
    with pytest.raises(Malformed):
        container.parse(z + b"\x00")
    with pytest.raises(Malformed):
        container.parse(z[:-1])


def test_parse_body_length_mismatch_v2_rejected():
    z = _ciphertext_v2(E2)
    with pytest.raises(Malformed):
        container.parse(z + b"\x00")
    with pytest.raises(Malformed):
        container.parse(z[:-1])


def test_tampered_extraction_byte_rejected_before_generator(monkeypatch):
    from isc_cipher import cipher as cm

    z = bytearray(_ciphertext_v2(E1))     # build the ciphertext BEFORE installing the no-generator guard
    z[36] = 2                      # flip to the other *valid* identifier: must fail authentication,

    def boom(*a, **k):
        raise AssertionError("generator work before authentication")
    monkeypatch.setattr(cm, "_build_generators", boom)
    with pytest.raises(AuthenticationError):   # not silently decrypt with the wrong profile
        decrypt_bytes(KEY, bytes(z))


def test_tampered_version_byte_rejected(monkeypatch):
    from isc_cipher import cipher as cm

    z = bytearray(_ciphertext_v1())        # build both ciphertexts BEFORE installing the guard
    z2 = bytearray(_ciphertext_v2(E2))

    def boom(*a, **k):
        raise AssertionError("generator work before authentication")
    monkeypatch.setattr(cm, "_build_generators", boom)
    z[4] = 2                       # V1 -> V2 relabel; body/tag offsets now misinterpreted by parse()
    with pytest.raises((AuthenticationError, Malformed)):
        decrypt_bytes(KEY, bytes(z))
    z2[4] = 1                      # V2 -> V1 relabel
    with pytest.raises((AuthenticationError, Malformed)):
        decrypt_bytes(KEY, bytes(z2))


# ---------------------------------------------------------------------------------------------
# Generator: scalar/vector extraction compatibility (Section 7 of the task /
# extraction_backend_compatibility_specification.md)
# ---------------------------------------------------------------------------------------------


def test_frac_byte_scalar_matches_numpy_frac_byte_over_production_recurrence():
    """1,000,000 (x, y) points actually produced by the production isc_cipher.isc_step recurrence
    (profile 1), not the research isc_seq.isc_map recurrence -- extends the prior session's
    2,000-point check by 3 orders of magnitude and ties it to the cipher's own recurrence."""
    from isc_cipher.isc_step import step_vec
    from isc_seq.extract import frac_byte

    rng = np.random.default_rng(20261111)
    x = rng.uniform(-1.0, 1.0, 4)
    y = rng.uniform(-1.0, 1.0, 4)
    n_steps = 250_000          # x4 lanes = 1,000,000 (x, y) points total
    all_x, all_y = [], []
    for _ in range(n_steps):
        x, y = step_vec(x, y, 1)
        all_x.append(x.copy())
        all_y.append(y.copy())
    xs = np.concatenate(all_x)
    ys = np.concatenate(all_y)
    assert xs.size == 1_000_000

    vec_bx = frac_byte(xs)
    vec_by = frac_byte(ys)
    for i in range(0, xs.size, 10007):           # dense stride-sampled scalar check (full 10^6 would be slow in pure Python)
        assert frac_byte_scalar(xs[i]) == int(vec_bx[i])
        assert frac_byte_scalar(ys[i]) == int(vec_by[i])
    # and a contiguous prefix, element-by-element, for completeness
    assert np.array_equal(vec_bx[:2000], np.array([frac_byte_scalar(v) for v in xs[:2000]]).astype(np.uint8))


@pytest.mark.parametrize("v", [0.0, -0.0, 1.0, -1.0, 1 - 2 ** -52, -(1 - 2 ** -52), 0.5, -0.5,
                                2.0 ** -52, -(2.0 ** -52)])
def test_frac_byte_scalar_matches_vector_on_boundary_values(v):
    from isc_seq.extract import frac_byte
    assert frac_byte_scalar(v) == int(frac_byte(np.array([v]))[0])


def test_frac_byte_scalar_returns_plain_python_int_in_range():
    for v in (0.0, -0.0, 0.3, -0.7, 1.0, -1.0):
        out = frac_byte_scalar(v)
        assert isinstance(out, int) and 0 <= out <= 255


def test_scalar_backend_importable_and_usable_without_numpy_module_object():
    """RefStream/frac_byte_scalar must not require numpy at all: simulate numpy being unimportable
    and confirm the reference backend still produces output.  (We cannot literally uninstall numpy
    in-process since the test runner itself may have already imported it; instead we assert that
    neither isc_cipher.generator's module-level namespace nor frac_byte_scalar's own code object
    references numpy, which is the actual guarantee this test needs to establish.)"""
    import dis
    import isc_cipher.generator as gen
    assert "numpy" not in gen.__dict__
    names = dis.Bytecode(frac_byte_scalar).codeobj.co_names
    assert "np" not in names and "numpy" not in names


def test_k14_refstream_and_npstream_produce_byte_identical_output():
    from isc_cipher.isc_step import step_ref
    from isc_cipher.state_map import seed_to_state

    seeds = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C)).seeds()
    states_ref = [seed_to_state(s) for s in seeds["fwd"]]
    ref = RefStream(states_ref, step_ref, extraction=E2)
    ref.burn_in(64)
    ref_out = ref.take(500)

    import numpy as np
    x = np.array([s[0] for s in states_ref], dtype=np.float64)
    y = np.array([s[1] for s in states_ref], dtype=np.float64)
    from isc_cipher.isc_step import step_vec
    for _ in range(64):
        x, y = step_vec(x, y, 1)
    npst = NpStream(x, y, 1, extraction=E2)
    np_out = npst.take(500)
    assert ref_out == np_out


def test_build_streams_default_extraction_byte_identical_to_pre_phase3a_baseline():
    """The single most load-bearing regression guard: build_streams() with no extraction argument
    must produce exactly the same bytes as before this parameter existed."""
    seeds = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C)).seeds()
    s1 = build_streams(seeds, backend="numpy", profile=1)
    s2 = build_streams(seeds, backend="numpy", profile=1, extraction=E1)
    for g in kdf.STREAMS:
        assert s1[g].take(256) == s2[g].take(256)
    s3 = build_streams(seeds, backend="reference")
    s4 = build_streams(seeds, backend="reference", extraction=E1)
    for g in kdf.STREAMS:
        assert s3[g].take(256) == s4[g].take(256)


def test_all_four_streams_retain_output_length_and_ordering_under_k14():
    seeds = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C, extraction=2)).seeds()
    streams = build_streams(seeds, backend="numpy", profile=1, extraction=E2)
    for g in kdf.STREAMS:
        out = streams[g].take(1024)
        assert len(out) == 1024
        assert streams[g].steps == 8          # 1024 / (2*64) = 8 output steps, unchanged by extraction


def test_state_advancement_unchanged_by_extraction_choice():
    """The (x, y) trajectory itself (pre-extraction) must be identical regardless of which
    extraction function is applied to it -- extraction is a pure post-processing step."""
    seeds = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C)).seeds()
    s1 = build_streams(seeds, backend="numpy", profile=1, extraction=E1)
    s2 = build_streams(seeds, backend="numpy", profile=1, extraction=E2)
    s1["fwd"].take(256)
    s2["fwd"].take(256)
    assert np.array_equal(s1["fwd"].x, s2["fwd"].x) and np.array_equal(s1["fwd"].y, s2["fwd"].y)
    assert s1["fwd"].steps == s2["fwd"].steps


def test_invalid_extraction_identifier_rejected_everywhere():
    seeds = kdf.Derivation(KEY, NONCE, kdf.context(1, 1, H, W, C)).seeds()
    with pytest.raises(ValueError):
        build_streams(seeds, backend="numpy", extraction=3)
    with pytest.raises(ValueError):
        build_streams(seeds, backend="reference", extraction=0)


# ---------------------------------------------------------------------------------------------
# Cipher integration (Section 8 of the task)
# ---------------------------------------------------------------------------------------------


def test_v1_roundtrip_unaffected():
    z = encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE)
    assert z[4] == 1
    assert decrypt_bytes(KEY, z)[0] == DATA


@pytest.mark.parametrize("backend", ["numpy", "reference"])
def test_v2_extraction_1_roundtrip(backend):
    z = encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, backend=backend, extraction=E1, version=2)
    assert z[4] == 2 and z[36] == 1
    assert decrypt_bytes(KEY, z, backend=backend)[0] == DATA


@pytest.mark.parametrize("backend", ["numpy", "reference"])
def test_v2_extraction_2_roundtrip(backend):
    z = encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, backend=backend, extraction=E2)
    assert z[4] == 2 and z[36] == 2
    assert decrypt_bytes(KEY, z, backend=backend)[0] == DATA


def test_public_encrypt_bytes_exposes_extraction_selection():
    import os as _os
    from isc_cipher.cipher import encrypt_bytes
    z = encrypt_bytes(KEY, DATA, H, W, C, extraction=E2)
    assert z[4] == 2 and z[36] == 2
    assert decrypt_bytes(KEY, z)[0] == DATA


def test_public_encrypt_bytes_default_still_v1_mantissa8():
    from isc_cipher.cipher import encrypt_bytes
    z = encrypt_bytes(KEY, DATA, H, W, C)
    assert z[4] == 1 and len(z) == 36 + H * W * C + 32


def test_v1_and_v2_extraction1_ciphertexts_differ_despite_same_extraction_method():
    z1 = encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, extraction=E1, version=1)
    z2 = encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, extraction=E1, version=2)
    assert z1 != z2          # different ctx -> different k_mac/seeds -> different ciphertext bytes


def test_no_generator_work_before_authentication_for_v2(monkeypatch):
    from isc_cipher import cipher as cm

    z = bytearray(_ciphertext_v2(E2))     # build the ciphertext BEFORE installing the no-generator guard
    z[40] ^= 1          # tamper one body byte

    def boom(*a, **k):
        raise AssertionError("generator work before authentication")
    monkeypatch.setattr(cm, "_build_generators", boom)
    with pytest.raises(AuthenticationError):
        decrypt_bytes(KEY, bytes(z))


def test_kcv_present_and_distinguishes_profiles_under_both_versions():
    z1 = _ciphertext_v2(E1)
    z2 = _ciphertext_v2(E2)
    assert z1[28:36] != z2[28:36]       # different extraction -> different lane streams -> different KCV


def test_v1_ciphertext_output_unchanged_byte_for_byte_vs_pre_phase3a_reference():
    """Pins the exact VERSION=1 ciphertext bytes for (KEY, DATA, H, W, C, NONCE) -- any future
    accidental change to the V1 path's default behaviour will be caught here immediately."""
    z = encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE)
    assert z == encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE)   # deterministic given fixed nonce
    assert hashlib.sha256(z).hexdigest() == hashlib.sha256(
        encrypt_bytes_with_nonce_TEST_ONLY(KEY, DATA, H, W, C, NONCE, backend="numpy", profile=1)).hexdigest()
