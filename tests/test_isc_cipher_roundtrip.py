"""Gate C: exact round trips Decrypt(Encrypt(P)) == P (shape, dtype, every element), both backends,
cross-implementation equality, size limits. Slow cases run only with ISC_SLOW=1."""

import inspect
import os

import numpy as np
import pytest

import isc_cipher
from isc_cipher import InvalidImage, decrypt, encrypt, generate_key
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY
from isc_cipher.cipher import decrypt_bytes

SLOW = os.environ.get("ISC_SLOW") == "1"
KEY = bytes(range(32))


def roundtrip(img, backend="numpy"):
    z = encrypt(KEY, img, backend=backend)
    out = decrypt(KEY, z, backend=backend)
    assert out.dtype == np.uint8 and out.shape == img.shape and np.array_equal(out, img)
    assert len(z) == 68 + img.size
    return z


def patterns(h, w, c):
    shape = (h, w) if c == 1 else (h, w, 3)
    rng = np.random.default_rng(h * 1000 + w * 10 + c)
    yy, xx = np.indices((h, w))
    base = {
        "zeros": np.zeros(shape, np.uint8),
        "all255": np.full(shape, 255, np.uint8),
        "const128": np.full(shape, 128, np.uint8),
        "hgrad": ((xx * 255) // max(w - 1, 1)).astype(np.uint8),
        "vgrad": ((yy * 255) // max(h - 1, 1)).astype(np.uint8),
        "checker": (((xx + yy) % 2) * 255).astype(np.uint8),
        "repeated": np.tile(np.array([7, 7, 7, 200], np.uint8), (h * w * c) // 4 + 1)[: h * w * c].reshape(shape),
        "random": rng.integers(0, 256, shape, dtype=np.uint8),
    }
    single = np.zeros(shape, np.uint8)
    single[h // 2, w // 2] = 255
    base["single_bright"] = single
    if c == 3:
        for k in ("hgrad", "vgrad", "checker"):
            base[k] = np.repeat(base[k][:, :, None], 3, axis=2)
    return base


SHAPES = [(1, 1, 1), (1, 1, 3), (1, 7, 1), (7, 1, 1), (2, 2, 1), (15, 16, 1), (16, 15, 3), (31, 17, 3), (64, 64, 1)]


@pytest.mark.parametrize("h,w,c", SHAPES)
def test_roundtrip_numpy_all_patterns(h, w, c):
    for name, img in patterns(h, w, c).items():
        roundtrip(img, "numpy")


@pytest.mark.parametrize("h,w,c", [(1, 1, 1), (1, 7, 1), (4, 6, 3)])
def test_roundtrip_reference_backend(h, w, c):
    img = patterns(h, w, c)["random"]
    roundtrip(img, "reference")


@pytest.mark.parametrize("h,w,c", [(1, 1, 1), (3, 5, 3), (16, 16, 1)])
def test_backends_produce_identical_ciphertexts_and_cross_decrypt(h, w, c):
    data = bytes((i * 91 + 3) % 256 for i in range(h * w * c))
    nonce = bytes(range(100, 116))
    z_ref = encrypt_bytes_with_nonce_TEST_ONLY(KEY, data, h, w, c, nonce, backend="reference")
    z_np = encrypt_bytes_with_nonce_TEST_ONLY(KEY, data, h, w, c, nonce, backend="numpy")
    assert z_ref == z_np
    assert decrypt_bytes(KEY, z_np, backend="reference")[0] == data
    assert decrypt_bytes(KEY, z_ref, backend="numpy")[0] == data


def test_larger_images_roundtrip():
    rng = np.random.default_rng(1)
    for shape in [(255, 256), (256, 256, 3)]:
        roundtrip(rng.integers(0, 256, shape, dtype=np.uint8))


@pytest.mark.skipif(not SLOW, reason="set ISC_SLOW=1 (scikit-image samples, full size)")
def test_scikit_image_samples_roundtrip():
    from skimage import data
    names = ["camera", "astronaut", "coffee", "chelsea", "moon", "brick", "grass", "gravel", "text",
             "checkerboard", "rocket", "cat"]
    for name in names:
        img = getattr(data, name)()
        assert img.dtype == np.uint8, name           # all 12 are uint8; non-uint8 would be excluded, not converted
        if img.ndim == 3 and img.shape[2] == 4:
            pytest.fail(f"{name} has 4 channels")
        roundtrip(np.ascontiguousarray(img))


def test_repeated_encryption_uses_fresh_nonces():
    img = np.zeros((4, 4), np.uint8)
    z1, z2 = encrypt(KEY, img), encrypt(KEY, img)
    assert z1[12:28] != z2[12:28] and z1 != z2
    assert np.array_equal(decrypt(KEY, z1), decrypt(KEY, z2))


def test_fixed_nonce_is_deterministic():
    data = bytes(range(48))
    n = bytes(16)
    assert (encrypt_bytes_with_nonce_TEST_ONLY(KEY, data, 4, 4, 3, n)
            == encrypt_bytes_with_nonce_TEST_ONLY(KEY, data, 4, 4, 3, n))


def test_public_api_takes_no_nonce():
    for f in (isc_cipher.encrypt, isc_cipher.encrypt_bytes):
        assert not any("nonce" in p for p in inspect.signature(f).parameters)


@pytest.mark.parametrize("bad", [
    np.zeros((4, 4), np.uint16), np.zeros((4, 4), np.float64), np.zeros((4, 4, 4), np.uint8),
    np.zeros((4, 4, 1), np.uint8), np.zeros((4,), np.uint8), np.zeros((0, 4), np.uint8),
    np.zeros((2, 2, 3, 1), np.uint8), [[1, 2], [3, 4]]])
def test_invalid_images_rejected(bad):
    with pytest.raises(InvalidImage):
        encrypt(KEY, bad)


def test_size_limits():
    from isc_cipher import encrypt_bytes
    with pytest.raises(InvalidImage):                    # n = 2^24 + 4096 > 2^24
        encrypt_bytes(KEY, bytes(4097 * 4096), 4097, 4096, 1)
    with pytest.raises(InvalidImage):                    # W > 65535
        encrypt_bytes(KEY, bytes(65536), 1, 65536, 1)
    with pytest.raises(InvalidImage):                    # length mismatch
        encrypt_bytes(KEY, bytes(10), 3, 3, 1)
    with pytest.raises(InvalidImage):                    # C = 2
        encrypt_bytes(KEY, bytes(8), 2, 2, 2)
    from isc_cipher import container
    assert container.check_dims(4096, 4096, 1) and container.MAX_N == 2 ** 24
    assert container.check_dims(1, 65535, 3) and not container.check_dims(1, 65535 * 2, 3)


@pytest.mark.skipif(not SLOW, reason="set ISC_SLOW=1 (maximum size 4096 x 4096, several minutes)")
def test_maximum_size_roundtrip():
    rng = np.random.default_rng(7)
    img = rng.integers(0, 256, (4096, 4096), dtype=np.uint8)
    roundtrip(img)


def test_generate_key_works_with_cipher():
    k = generate_key()
    img = np.arange(30, dtype=np.uint8).reshape(5, 6)
    assert np.array_equal(decrypt(k, encrypt(k, img)), img)
