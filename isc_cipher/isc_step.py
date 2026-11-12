"""Stage 4: one step of the frozen ISC map with the normative operation order (algorithm_design.md §6.1).

Frozen equations and parameters (a = 0.9, c = 0.4, d = 6.0, omega = 10.0) are those of
isc_seq.isc_map; only the source of SIN/COS differs by numerical profile:
  profile 1 (F64-FDLIBM, normative): fdlibm 5.3 via fdlibm_ref (R1) or fdlibm_np (V1)
  profile 2 (F64-HOSTLIBM, comparison only): host NumPy sin/cos, V1 only
Every SIN/COS argument must satisfy |arg| < 24 (§6.1); otherwise ValueError.
"""

from . import fdlibm_ref

# Frozen ISC parameters. Defined here (not imported from isc_seq, which needs NumPy) so that the
# pure-Python reference path runs without NumPy; tests assert equality with isc_seq.isc_map.FROZEN_PARAMS.
A = 0.9
C = 0.4
D = 6.0
W = 10.0
ARG_BOUND = 24.0


def _guard(v):
    if not -ARG_BOUND < v < ARG_BOUND:
        raise ValueError("SIN/COS argument outside the profile-1 bound |arg| < 24")
    return v


def step_ref(x, y, sin=fdlibm_ref.sin, cos=fdlibm_ref.cos):
    """Scalar step (R1). Each line is one binary64 operation."""
    t1 = x * x
    t2 = y * y
    r = t1 + t2
    t3 = 1.0 + r
    t4 = D / t3
    t = C - t4
    _guard(t)
    ct = cos(t)
    st = sin(t)
    t5 = x * ct
    t6 = y * st
    t7 = t5 - t6
    t8 = A * t7
    X = 1.0 + t8
    t9 = x * st
    t10 = y * ct
    t11 = t9 + t10
    Y = A * t11
    t12 = W * X
    sx = sin(_guard(t12))
    t13 = W * Y
    sy = sin(_guard(t13))
    t14 = sx * sx
    t15 = 2.0 * t14
    t16 = sy * sy
    t17 = 2.0 * t16
    return t15 - 1.0, t17 - 1.0


def step_vec(x, y, profile=1):
    """Vectorised step (V1) on float64 arrays; same operations element-wise."""
    import numpy as np
    if profile == 1:
        from . import fdlibm_np
        sin, cos = fdlibm_np.sin, fdlibm_np.cos
    elif profile == 2:
        sin, cos = np.sin, np.cos
    else:
        raise ValueError("unknown profile")
    f = np.float64
    t1 = x * x
    t2 = y * y
    r = t1 + t2
    t3 = f(1.0) + r
    t4 = f(D) / t3
    t = f(C) - t4
    ct = cos(t)
    st = sin(t)
    t5 = x * ct
    t6 = y * st
    t7 = t5 - t6
    t8 = f(A) * t7
    X = f(1.0) + t8
    t9 = x * st
    t10 = y * ct
    t11 = t9 + t10
    Y = f(A) * t11
    t12 = f(W) * X
    t13 = f(W) * Y
    if profile == 1:
        for v in (t, t12, t13):
            if not np.all(np.abs(v) < ARG_BOUND):
                raise ValueError("SIN/COS argument outside the profile-1 bound |arg| < 24")
    sx = sin(t12)
    sy = sin(t13)
    t14 = sx * sx
    t15 = f(2.0) * t14
    t16 = sy * sy
    t17 = f(2.0) * t16
    return t15 - f(1.0), t17 - f(1.0)
