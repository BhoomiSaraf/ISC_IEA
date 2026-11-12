import struct

import numpy as np
import pytest

from isc_seq import extract as ex
from isc_seq.trajectory import (generate_trajectory, initial_conditions, load_trajectory,
                                save_trajectory, sha256_of_arrays)


def test_transient_semantics():
    xs, ys = generate_trajectory(0.1, 0.1, 300, transient=0)
    xt, yt = generate_trajectory(0.1, 0.1, 200, transient=100)
    assert np.array_equal(xt, xs[100:]) and np.array_equal(yt, ys[100:])


def test_first_output_is_first_iterate_not_initial_condition():
    xs, _ = generate_trajectory(0.1, 0.1, 1, transient=0)
    assert xs[0] != 0.1


def test_deterministic_and_batched_matches_single():
    x0, y0 = initial_conditions(seed=7, count=4)
    x0b, y0b = initial_conditions(seed=7, count=4)
    assert np.array_equal(x0, x0b) and np.array_equal(y0, y0b)
    bx, by = generate_trajectory(x0, y0, 500, transient=50)
    assert bx.shape == (500, 4)
    for k in range(4):
        sx, sy = generate_trajectory(x0[k], y0[k], 500, transient=50)
        assert np.array_equal(sx, bx[:, k]) and np.array_equal(sy, by[:, k])


def test_initial_conditions_count_dependence_is_as_documented():
    a, b = initial_conditions(1, 3), initial_conditions(1, 10)
    assert np.array_equal(a[0], b[0][:3])
    assert not np.array_equal(a[1], b[1][:3])


def test_float32_trajectory_dtype():
    xs, ys = generate_trajectory(0.1, 0.1, 10, transient=5, dtype=np.float32)
    assert xs.dtype == np.float32 and ys.dtype == np.float32


def test_invalid_arguments():
    with pytest.raises(ValueError):
        generate_trajectory(0.1, 0.1, -1)
    with pytest.raises(ValueError):
        generate_trajectory([0.1, 0.2], [0.1], 5)


def test_save_load_roundtrip_and_no_overwrite(tmp_path):
    xs, ys = generate_trajectory(0.1, 0.1, 100, transient=10)
    p = tmp_path / "t.npz"
    digest = save_trajectory(str(p), xs, ys, {"x0": 0.1})
    lx, ly, meta = load_trajectory(str(p))
    assert np.array_equal(lx, xs) and np.array_equal(ly, ys)
    assert meta["sha256"] == digest == sha256_of_arrays(xs, ys)
    with pytest.raises(FileExistsError):
        save_trajectory(str(p), xs, ys, {})


@pytest.mark.parametrize("name", list(ex.METHODS))
def test_extractor_lengths_and_values(name):
    xs, ys = generate_trajectory(0.3, -0.2, 257, transient=10)
    bits = ex.extract(name, xs, ys)
    assert bits.dtype == np.uint8
    assert bits.size == 257 * ex.METHODS[name].bits_per_iter
    assert set(np.unique(bits)) <= {0, 1}
    assert ex.extract(name, xs, ys, n_bits=100).size == 100
    with pytest.raises(ValueError):
        ex.extract(name, xs, ys, n_bits=bits.size + 1)


def test_sign_bits_order():
    bits = ex.sign_bits(np.array([0.5, -0.5]), np.array([-0.1, 0.2]))
    assert bits.tolist() == [1, 0, 0, 1]


def test_arccos_byte_endpoints_and_monotone():
    assert ex.arccos_byte(-1.0) == 0
    assert ex.arccos_byte(1.0) == 255
    v = np.linspace(-1, 1, 1001)
    assert np.all(np.diff(ex.arccos_byte(v).astype(int)) >= 0)


def test_frac_byte():
    assert ex.frac_byte(0.0) == 0
    assert ex.frac_byte(-1.23e-12) == 123  # floor(123.0) mod 256
    assert ex.frac_byte(2.56e-12) == 0


def test_mantissa_byte_against_struct():
    for v in (0.1, -0.7342, 0.999999, 1e-5):
        raw = struct.unpack("<Q", struct.pack("<d", v))[0]
        expect = ((raw & ((1 << 52) - 1)) >> ex.MANTISSA_SHIFT) & 0xFF
        assert int(ex.mantissa_byte(v)) == expect


def test_byte_bits_are_msb_first_x_then_y():
    xs = np.array([0.1])
    ys = np.array([-0.7342])
    bits = ex.mantissa8_bits(xs, ys)
    bx, by = int(ex.mantissa_byte(0.1)), int(ex.mantissa_byte(-0.7342))
    assert bits.tolist() == [int(b) for b in f"{bx:08b}{by:08b}"]
    xor = ex.mantissa8_xor_bits(xs, ys)
    assert xor.tolist() == [int(b) for b in f"{bx ^ by:08b}"]
