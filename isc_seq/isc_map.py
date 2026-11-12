"""Frozen Ikeda-Sine-Chebyshev (ISC) map.

    t_n     = c - d / (1 + x_n^2 + y_n^2)
    X_n     = 1 + a (x_n cos t_n - y_n sin t_n)
    Y_n     = a (x_n sin t_n + y_n cos t_n)
    x_{n+1} = 2 sin^2(w X_n) - 1
    y_{n+1} = 2 sin^2(w Y_n) - 1

Default parameters: a=0.9, c=0.4, d=6.0, w=10.0.  These must not change.

Floating-point evaluation
-------------------------
`isc_step` is the canonical evaluation.  Squares are written as explicit
products (x*x, s*s), which IEEE-754 rounds exactly, so the result is identical
for Python floats, NumPy scalars and NumPy arrays (verified by the tests).

`legacy_step` reproduces the expression used in script/*.py bit for bit
(`x**2`, `np.sin(.)**2`).  On NumPy scalars `**2` goes through the C library
`pow()`, which occasionally differs by one ulp from x*x, so the two evaluations
agree to ~1e-16 per step but their chaotic trajectories separate after a few
dozen iterations.  Use `legacy_step` only to reproduce previously reported
results; use `isc_step` for everything new.
"""

from dataclasses import dataclass, asdict

import numpy as np


@dataclass(frozen=True)
class ISCParams:
    a: float = 0.9
    c: float = 0.4
    d: float = 6.0
    omega: float = 10.0

    def as_dict(self):
        return asdict(self)


FROZEN_PARAMS = ISCParams()


def isc_step(x, y, params=FROZEN_PARAMS):
    """One canonical ISC iteration.  Works on scalars or arrays of any float dtype.

    Parameters are cast to the dtype of `x`, so float32 inputs are iterated in
    float32 arithmetic throughout (NumPy >= 2 promotion rules).
    """
    ftype = np.asarray(x).dtype.type
    if not np.issubdtype(ftype, np.floating):
        ftype = np.float64
    a, c, d, w = (ftype(v) for v in (params.a, params.c, params.d, params.omega))
    one, two = ftype(1.0), ftype(2.0)

    t = c - d / (one + (x * x + y * y))
    ct = np.cos(t)
    st = np.sin(t)
    X = one + a * (x * ct - y * st)
    Y = a * (x * st + y * ct)
    sx = np.sin(w * X)
    sy = np.sin(w * Y)
    return two * (sx * sx) - one, two * (sy * sy) - one


def legacy_step(x, y, params=FROZEN_PARAMS):
    """Same expressions as `sine_chebyshev_ikeda_step` in script/final_validation.py.

    Parameters are passed as Python floats, exactly as the legacy scripts did.
    """
    a, c, d, omega = float(params.a), float(params.c), float(params.d), float(params.omega)
    tn = c - d / (1.0 + x**2 + y**2)
    Xn = 1.0 + a * (x * np.cos(tn) - y * np.sin(tn))
    Yn = a * (x * np.sin(tn) + y * np.cos(tn))
    xn = 2.0 * (np.sin(omega * Xn)**2) - 1.0
    yn = 2.0 * (np.sin(omega * Yn)**2) - 1.0
    return xn, yn
