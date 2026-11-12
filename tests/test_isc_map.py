import ast
import math
import os

import numpy as np
import pytest

from isc_seq.isc_map import FROZEN_PARAMS, ISCParams, isc_step, legacy_step
from conftest import ROOT

LEGACY_SCRIPTS = ["analyze.py", "final_validation.py", "final_freeze_validation.py"]


def spec_step(x, y, a=0.9, c=0.4, d=6.0, w=10.0):
    """Frozen equations, written independently with the math module."""
    t = c - d / (1 + x * x + y * y)
    X = 1 + a * (x * math.cos(t) - y * math.sin(t))
    Y = a * (x * math.sin(t) + y * math.cos(t))
    return 2 * math.sin(w * X) ** 2 - 1, 2 * math.sin(w * Y) ** 2 - 1


def load_legacy(script):
    """Extract sine_chebyshev_ikeda_step from a legacy script without running the script."""
    path = os.path.join(ROOT, "script", script)
    if not os.path.exists(path):
        pytest.skip(f"{script} not present")
    tree = ast.parse(open(path, encoding="utf-8").read())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "sine_chebyshev_ikeda_step")
    ns = {"np": np}
    exec(compile(ast.Module([node], []), script, "exec"), ns)
    return ns["sine_chebyshev_ikeda_step"]


def test_frozen_parameters():
    assert FROZEN_PARAMS == ISCParams(a=0.9, c=0.4, d=6.0, omega=10.0)
    with pytest.raises(Exception):
        FROZEN_PARAMS.a = 1.0


def test_single_step_matches_spec():
    rng = np.random.default_rng(0)
    pts = rng.uniform(-1, 1, (2000, 2))
    for x, y in pts:
        cx, cy = isc_step(float(x), float(y))
        sx, sy = spec_step(float(x), float(y))
        assert abs(cx - sx) < 1e-12 and abs(cy - sy) < 1e-12


def test_output_bounded():
    rng = np.random.default_rng(1)
    x, y = rng.uniform(-5, 5, 10000), rng.uniform(-5, 5, 10000)
    nx, ny = isc_step(x, y)
    assert np.all(np.abs(nx) <= 1) and np.all(np.abs(ny) <= 1)


def test_scalar_and_batched_bit_identical():
    rng = np.random.default_rng(2)
    x0, y0 = rng.uniform(-1, 1, 16), rng.uniform(-1, 1, 16)
    X, Y = x0.copy(), y0.copy()
    traj = np.empty((3000, 16))
    for i in range(3000):
        X, Y = isc_step(X, Y)
        traj[i] = X
    for k in (0, 7, 15):
        x, y = float(x0[k]), float(y0[k])
        for i in range(3000):
            x, y = isc_step(x, y)
            assert x == traj[i, k], (k, i)


def test_float32_stays_float32():
    x, y = isc_step(np.float32(0.1), np.float32(0.1))
    assert type(x) is np.float32 and type(y) is np.float32


@pytest.mark.parametrize("script", LEGACY_SCRIPTS)
def test_legacy_step_reproduces_scripts_bitwise(script):
    ref = load_legacy(script)
    x = y = lx = ly = 0.1
    for _ in range(5000):
        x, y = ref(x, y, **FROZEN_PARAMS.as_dict())
        lx, ly = legacy_step(lx, ly)
        assert (x, y) == (lx, ly)


def test_canonical_and_legacy_agree_per_step():
    rng = np.random.default_rng(3)
    for x, y in rng.uniform(-1, 1, (2000, 2)):
        c = isc_step(np.float64(x), np.float64(y))
        lg = legacy_step(np.float64(x), np.float64(y))
        assert abs(c[0] - lg[0]) < 1e-13 and abs(c[1] - lg[1]) < 1e-13


def test_golden_values_regression():
    # First iterates of the canonical map from (0.1, 0.1), recorded when the module was written.
    # A change here means the canonical floating-point evaluation changed.
    x, y = 0.1, 0.1
    got = []
    for _ in range(5):
        x, y = isc_step(x, y)
        got.append((x, y))
    assert got == GOLDEN


GOLDEN = [
    (-0.44362527888166814, 0.8274127172254948),
    (-0.34339813068622893, -0.2232771722366148),
    (-0.29321422074872927, -0.999999257298653),
    (-0.8889843320484979, -0.14036596403778345),
    (0.8928863965213405, -0.9747645876494493),
]
