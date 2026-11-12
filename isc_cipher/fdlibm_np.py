"""Profile 1 vectorised implementation (V1): fdlibm 5.3 sin/cos on float64 NumPy arrays.

Same algorithm and constants as fdlibm_ref (R1). Every arithmetic step is a separate NumPy ufunc
call on float64 arrays, i.e. one correctly rounded IEEE binary64 operation per element (no fused
multiply-add). All reachable branches are evaluated for all elements and the branch result is
selected element-wise with the same conditions as the C code, so the value returned for each
element is exactly the value of its own branch.

Copyright notice of the original code (preserved as required by its licence):
  Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
  Developed at SunSoft, a Sun Microsystems, Inc. business.
  Permission to use, copy, modify, and distribute this software is freely granted,
  provided that this notice is preserved.
"""

import numpy as np

from . import fdlibm_ref as R

F = np.float64
_NPIO2_HW = np.array(R.NPIO2_HW, dtype=np.int64)


def hi(x):
    """Signed high words (int64 holding C int values)."""
    h = (np.ascontiguousarray(x, dtype=np.float64).view(np.uint64) >> np.uint64(32)).astype(np.int64)
    return np.where(h >= 0x80000000, h - 0x100000000, h)


def from_hi(hw):
    """Doubles with high word hw (non-negative int64 < 2^31) and low word 0."""
    return (hw.astype(np.uint64) << np.uint64(32)).view(np.float64)


def _trunc_int(v):
    return np.trunc(v).astype(np.int64)


def kernel_sin(x, y, iy):
    ix = hi(x) & 0x7FFFFFFF
    tiny = (ix < 0x3E400000) & (_trunc_int(x) == 0)
    z = x * x
    v = z * x
    r = F(R.S2) + z * (F(R.S3) + z * (F(R.S4) + z * (F(R.S5) + z * F(R.S6))))
    if iy == 0:
        res = x + v * (F(R.S1) + z * r)
    else:
        res = x - ((z * (F(R.half) * y - v * r) - y) - v * F(R.S1))
    return np.where(tiny, x, res)


def kernel_cos(x, y):
    ix = hi(x) & 0x7FFFFFFF
    tiny = (ix < 0x3E400000) & (_trunc_int(x) == 0)
    z = x * x
    r = z * (F(R.C1) + z * (F(R.C2) + z * (F(R.C3) + z * (F(R.C4) + z * (F(R.C5) + z * F(R.C6))))))
    small = F(R.one) - (F(0.5) * z - (z * r - x * y))
    qx = np.where(ix > 0x3FE90000, F(0.28125), from_hi(np.maximum(ix - 0x00200000, 0)))
    hz = F(0.5) * z - qx
    a = F(R.one) - qx
    big = a - (hz - (z * r - x * y))
    res = np.where(ix < 0x3FD33333, small, big)
    return np.where(tiny, F(R.one), res)


def rem_pio2(x):
    """Vectorised e_rem_pio2.c (reachable branches). Returns (n int64, y0, y1)."""
    hx = hi(x)
    ix = hx & 0x7FFFFFFF
    if np.any(ix > 0x413921FB):
        raise ValueError("fdlibm large-argument branch is outside profile 1")
    b0 = ix <= 0x3FE921FB
    b1 = (~b0) & (ix < 0x4002D97C)
    near = ix == 0x3FF921FB
    pos = hx > 0
    # branch 1, positive x
    zp = x - F(R.pio2_1)
    y0p = zp - F(R.pio2_1t)
    y1p = (zp - y0p) - F(R.pio2_1t)
    zp2 = zp - F(R.pio2_2)
    y0p2 = zp2 - F(R.pio2_2t)
    y1p2 = (zp2 - y0p2) - F(R.pio2_2t)
    # branch 1, negative x
    zn = x + F(R.pio2_1)
    y0n = zn + F(R.pio2_1t)
    y1n = (zn - y0n) + F(R.pio2_1t)
    zn2 = zn + F(R.pio2_2)
    y0n2 = zn2 + F(R.pio2_2t)
    y1n2 = (zn2 - y0n2) + F(R.pio2_2t)
    b1y0 = np.where(pos, np.where(near, y0p2, y0p), np.where(near, y0n2, y0n))
    b1y1 = np.where(pos, np.where(near, y1p2, y1p), np.where(near, y1n2, y1n))
    b1n = np.where(pos, 1, -1).astype(np.int64)
    # branch 2, medium
    t = np.abs(x)
    n = _trunc_int(t * F(R.invpio2) + F(R.half))
    fn = n.astype(np.float64)
    r1 = t - fn * F(R.pio2_1)
    w1 = fn * F(R.pio2_1t)
    y0_1 = r1 - w1
    idx = np.clip(n - 1, 0, 31)
    quick = (n < 32) & (ix != _NPIO2_HW[idx])
    j = ix >> 20
    i1 = j - ((hi(y0_1) >> 20) & 0x7FF)
    t2 = r1
    w2a = fn * F(R.pio2_2)
    r2 = t2 - w2a
    w2 = fn * F(R.pio2_2t) - ((t2 - r2) - w2a)
    y0_2 = r2 - w2
    i2 = j - ((hi(y0_2) >> 20) & 0x7FF)
    t3 = r2
    w3a = fn * F(R.pio2_3)
    r3 = t3 - w3a
    w3 = fn * F(R.pio2_3t) - ((t3 - r3) - w3a)
    y0_3 = r3 - w3
    use2 = (~quick) & (i1 > 16)
    use3 = use2 & (i2 > 49)
    r = np.where(use3, r3, np.where(use2, r2, r1))
    w = np.where(use3, w3, np.where(use2, w2, w1))
    y0m = np.where(use3, y0_3, np.where(use2, y0_2, y0_1))
    y1m = (r - y0m) - w
    neg = hx < 0
    y0m = np.where(neg, -y0m, y0m)
    y1m = np.where(neg, -y1m, y1m)
    nm = np.where(neg, -n, n)
    n_out = np.where(b0, 0, np.where(b1, b1n, nm))
    y0 = np.where(b0, x, np.where(b1, b1y0, y0m))
    y1 = np.where(b0, F(0.0), np.where(b1, b1y1, y1m))
    return n_out, y0, y1


def _check(x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 0:
        x = x.reshape(1)
    if not np.all(np.isfinite(x)):
        raise ValueError("non-finite argument")
    return x


def sin(x):
    x = _check(x)
    ix = hi(x) & 0x7FFFFFFF
    direct = ix <= 0x3FE921FB
    n, y0, y1 = rem_pio2(x)
    ks = kernel_sin(y0, y1, 1)
    kc = kernel_cos(y0, y1)
    m = n & 3
    red = np.where(m == 0, ks, np.where(m == 1, kc, np.where(m == 2, -ks, -kc)))
    return np.where(direct, kernel_sin(x, F(0.0), 0), red)


def cos(x):
    x = _check(x)
    ix = hi(x) & 0x7FFFFFFF
    direct = ix <= 0x3FE921FB
    n, y0, y1 = rem_pio2(x)
    ks = kernel_sin(y0, y1, 1)
    kc = kernel_cos(y0, y1)
    m = n & 3
    red = np.where(m == 0, kc, np.where(m == 1, -ks, np.where(m == 2, -kc, ks)))
    return np.where(direct, kernel_cos(x, F(0.0)), red)
