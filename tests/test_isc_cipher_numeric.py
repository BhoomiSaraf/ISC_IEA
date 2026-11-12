"""Gate C, stages 4-5a: fdlibm profile, ISC step, lanes, burn-in, byte extraction, consumption."""

import gzip
import json
import math
import os
import struct

import numpy as np
import pytest

from conftest import ROOT
from isc_cipher import fdlibm_np, fdlibm_ref, kdf
from isc_cipher.generator import BURN_IN, NpStream, RefStream, build_streams, m_byte
from isc_cipher.isc_step import step_ref, step_vec

VEC = os.path.join(ROOT, "isc_cipher_kat", "vectors")


def h2d(h):
    return struct.unpack(">d", bytes.fromhex(h))[0]


def d2h(v):
    return struct.pack(">d", float(v)).hex()


@pytest.fixture(scope="module")
def trig_rows():
    return [l.split() for l in gzip.open(os.path.join(VEC, "trig_kat.txt.gz"), "rt") if not l.startswith("#")]


def test_trig_r1_matches_c_oracle(trig_rows):
    bad = [r for r in trig_rows[::7] if (d2h(fdlibm_ref.sin(h2d(r[0]))), d2h(fdlibm_ref.cos(h2d(r[0])))) != (r[1], r[2])]
    assert not bad


def test_trig_v1_matches_c_oracle(trig_rows):
    x = np.array([h2d(r[0]) for r in trig_rows])
    s = [d2h(v) for v in fdlibm_np.sin(x)]
    c = [d2h(v) for v in fdlibm_np.cos(x)]
    assert s == [r[1] for r in trig_rows] and c == [r[2] for r in trig_rows]


def test_trig_within_one_ulp_of_correctly_rounded(trig_rows):
    """fdlibm is not correctly rounded (not required), but must be within 1 ulp on profile arguments."""
    mpmath = pytest.importorskip("mpmath")
    mpmath.mp.prec = 200
    worst = 0.0
    for r in trig_rows[::50]:
        x = h2d(r[0])
        for got, f in ((h2d(r[1]), mpmath.sin), (h2d(r[2]), mpmath.cos)):
            exact = f(mpmath.mpf(x))
            ulp = math.ulp(float(exact)) if float(exact) != 0 else 5e-324
            worst = max(worst, float(abs(mpmath.mpf(got) - exact)) / ulp)
    assert worst <= 1.0


def test_large_argument_branch_is_rejected():
    with pytest.raises(ValueError):
        fdlibm_ref.sin(1e7)
    with pytest.raises(ValueError):
        fdlibm_np.sin(np.array([1e7]))


def test_step_argument_guard():
    with pytest.raises(ValueError):
        step_ref(5.0, 5.0)                     # outside [-1,1]^2: omega*X exceeds 24
    with pytest.raises(ValueError):
        step_vec(np.array([5.0]), np.array([5.0]), 1)


def test_step_ref_equals_step_vec_bitwise():
    rng = np.random.default_rng(3)
    x, y = rng.uniform(-1, 1, 500), rng.uniform(-1, 1, 500)
    vx, vy = x.copy(), y.copy()
    rx, ry = list(x), list(y)
    for _ in range(300):
        vx, vy = step_vec(vx, vy, 1)
        for k in range(len(rx)):
            rx[k], ry[k] = step_ref(rx[k], ry[k])
    assert [d2h(v) for v in vx] == [d2h(v) for v in rx]
    assert [d2h(v) for v in vy] == [d2h(v) for v in ry]


def test_profile2_step_is_the_existing_canonical_isc_step():
    from isc_seq.isc_map import isc_step
    rng = np.random.default_rng(4)
    x, y = rng.uniform(-1, 1, 300), rng.uniform(-1, 1, 300)
    a = step_vec(x, y, 2)
    b = isc_step(x, y)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_states_stay_in_unit_square_on_kat_trajectories():
    kat = json.load(open(os.path.join(VEC, "traj_kat.json")))["trajectories"]
    for t in kat:
        for xh, yh in t["checkpoints"].values():
            assert -1.0 <= h2d(xh) <= 1.0 and -1.0 <= h2d(yh) <= 1.0


def test_step_ref_first_checkpoints_match_oracle():
    kat = json.load(open(os.path.join(VEC, "traj_kat.json")))["trajectories"]
    for t in kat:
        x, y = h2d(t["x0"]), h2d(t["y0"])
        for i in range(1, 101):
            x, y = step_ref(x, y)
            if str(i) in t["checkpoints"]:
                assert [d2h(x), d2h(y)] == t["checkpoints"][str(i)]


def test_m_byte_definition():
    for v in (0.1, -0.7342, 0.999999, 1e-5, -1.0, 1.0, 0.0):
        bits = struct.unpack(">Q", struct.pack(">d", v))[0]
        assert m_byte(v) == (bits >> 8) & 0xFF
    assert m_byte(1.0) == 0 and m_byte(-1.0) == 0 and m_byte(0.0) == 0


def _states(n):
    rng = np.random.default_rng(5)
    return list(zip(rng.uniform(-1, 1, n), rng.uniform(-1, 1, n)))


def test_stream_byte_order_lane_minor_x_before_y():
    st = _states(64)
    s = RefStream(st, step_ref)
    out = s.take(128)
    exp = bytearray()
    for x, y in st:
        nx, ny = step_ref(x, y)
        exp += bytes([m_byte(nx), m_byte(ny)])
    assert out == bytes(exp) and s.steps == 1


def test_stream_consumption_and_steps():
    st = _states(64)
    for cls in ("ref", "np"):
        s = RefStream(st, step_ref) if cls == "ref" else NpStream([a for a, _ in st], [b for _, b in st], 1)
        full = (RefStream(st, step_ref) if cls == "ref" else NpStream([a for a, _ in st], [b for _, b in st], 1)).take(1000)
        parts = s.take(1) + s.take(127) + s.take(0) + s.take(500) + s.take(372)
        assert parts == full
        assert s.consumed == 1000 and s.steps == math.ceil(1000 / 128)


def test_reference_and_numpy_streams_identical():
    seeds = kdf.Derivation(bytes(range(32)), bytes(range(16)), kdf.context(1, 1, 5, 5, 1)).seeds()
    ref = build_streams(seeds, backend="reference", burn_in=64)
    vec = build_streams(seeds, backend="numpy", burn_in=64)
    for g in kdf.STREAMS:
        assert ref[g].take(700) == vec[g].take(700)
        assert ref[g].final_state_bytes() == vec[g].final_state_bytes()


def test_burn_in_length_and_stream_kat_after_burn_in():
    assert BURN_IN == 1024
    kat = json.load(open(os.path.join(VEC, "stream_kat.json")))
    seeds = {g: [bytes.fromhex(s) for s in kat["streams"][g]["seeds_hex"]] for g in kdf.STREAMS}
    vec = build_streams(seeds, backend="numpy")
    for g in kdf.STREAMS:
        assert [[d2h(a), d2h(b)] for a, b in zip(vec[g].x, vec[g].y)] == kat["streams"][g]["after_burn_in"]
        assert vec[g].take(1024).hex() == kat["streams"][g]["first_1024_bytes_hex"]


def test_reference_backend_rejects_profile2():
    from isc_cipher import ProfileError
    seeds = kdf.Derivation(bytes(32), bytes(16), kdf.context(2, 1, 1, 1, 1)).seeds()
    with pytest.raises(ProfileError):
        build_streams(seeds, backend="reference", profile=2)
