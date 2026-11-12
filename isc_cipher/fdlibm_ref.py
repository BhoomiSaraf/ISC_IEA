"""Profile 1 reference (R1): fdlibm 5.3 sin/cos in pure CPython binary64 arithmetic.

Transcribed from the archived netlib sources (third_party/fdlibm/netlib_5.3: s_sin.c, s_cos.c,
e_rem_pio2.c, k_sin.c, k_cos.c; SHA-256 in SHA256SUMS.txt). Only the branches reachable for
|x| < 2^19*pi/2 are implemented; the large-argument branch (k_rem_pio2.c) raises.

Arithmetic model (algorithm_design.md §7.1): every Python float operation below is one IEEE
binary64 operation with round-to-nearest-even (CPython evaluates each bytecode operation as one C
double operation; no fused multiply-add). Expressions keep the C parse tree of the original code.
Constants are built from their exact bit patterns as printed in the sources.

Copyright notice of the original code (preserved as required by its licence):
  Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
  Developed at SunSoft, a Sun Microsystems, Inc. business.
  Permission to use, copy, modify, and distribute this software is freely granted,
  provided that this notice is preserved.
"""

import struct

_pack_d = struct.Struct("<d").pack
_unpack_q = struct.Struct("<Q").unpack
_pack_q = struct.Struct("<Q").pack
_unpack_d = struct.Struct("<d").unpack


def hi(x):
    """Signed high 32-bit word of the binary64 encoding (C: __HI(x), an int)."""
    h = _unpack_q(_pack_d(x))[0] >> 32
    return h - 0x100000000 if h & 0x80000000 else h


def from_words(hw, lw):
    return _unpack_d(_pack_q(((hw & 0xFFFFFFFF) << 32) | (lw & 0xFFFFFFFF)))[0]


# --- constants (exact bit patterns from the fdlibm sources) -------------------------------
one = from_words(0x3FF00000, 0x00000000)
half = from_words(0x3FE00000, 0x00000000)
# k_sin.c
S1 = from_words(0xBFC55555, 0x55555549)
S2 = from_words(0x3F811111, 0x1110F8A6)
S3 = from_words(0xBF2A01A0, 0x19C161D5)
S4 = from_words(0x3EC71DE3, 0x57B1FE7D)
S5 = from_words(0xBE5AE5E6, 0x8A2B9CEB)
S6 = from_words(0x3DE5D93A, 0x5ACFD57C)
# k_cos.c
C1 = from_words(0x3FA55555, 0x5555554C)
C2 = from_words(0xBF56C16C, 0x16C15177)
C3 = from_words(0x3EFA01A0, 0x19CB1590)
C4 = from_words(0xBE927E4F, 0x809C52AD)
C5 = from_words(0x3E21EE9E, 0xBDB4B1C4)
C6 = from_words(0xBDA8FAE9, 0xBE8838D4)
# e_rem_pio2.c
invpio2 = from_words(0x3FE45F30, 0x6DC9C883)
pio2_1 = from_words(0x3FF921FB, 0x54400000)
pio2_1t = from_words(0x3DD0B461, 0x1A626331)
pio2_2 = from_words(0x3DD0B461, 0x1A600000)
pio2_2t = from_words(0x3BA3198A, 0x2E037073)
pio2_3 = from_words(0x3BA3198A, 0x2E000000)
pio2_3t = from_words(0x397B839A, 0x252049C1)
NPIO2_HW = (
    0x3FF921FB, 0x400921FB, 0x4012D97C, 0x401921FB, 0x401F6A7A, 0x4022D97C,
    0x4025FDBB, 0x402921FB, 0x402C463A, 0x402F6A7A, 0x4031475C, 0x4032D97C,
    0x40346B9C, 0x4035FDBB, 0x40378FDB, 0x403921FB, 0x403AB41B, 0x403C463A,
    0x403DD85A, 0x403F6A7A, 0x40407E4C, 0x4041475C, 0x4042106C, 0x4042D97C,
    0x4043A28C, 0x40446B9C, 0x404534AC, 0x4045FDBB, 0x4046C6CB, 0x40478FDB,
    0x404858EB, 0x404921FB,
)


def kernel_sin(x, y, iy):
    ix = hi(x) & 0x7FFFFFFF
    if ix < 0x3E400000:                      # |x| < 2**-27
        if int(x) == 0:
            return x
    z = x * x
    v = z * x
    r = S2 + z * (S3 + z * (S4 + z * (S5 + z * S6)))
    if iy == 0:
        return x + v * (S1 + z * r)
    return x - ((z * (half * y - v * r) - y) - v * S1)


def kernel_cos(x, y):
    ix = hi(x) & 0x7FFFFFFF
    if ix < 0x3E400000:                      # |x| < 2**-27
        if int(x) == 0:
            return one
    z = x * x
    r = z * (C1 + z * (C2 + z * (C3 + z * (C4 + z * (C5 + z * C6)))))
    if ix < 0x3FD33333:                      # |x| < 0.3
        return one - (0.5 * z - (z * r - x * y))
    if ix > 0x3FE90000:                      # x > 0.78125
        qx = 0.28125
    else:
        qx = from_words(ix - 0x00200000, 0)  # x/4
    hz = 0.5 * z - qx
    a = one - qx
    return a - (hz - (z * r - x * y))


def rem_pio2(x):
    """Returns (n, y0, y1). Reachable branches only (|x| <= 2^19*pi/2)."""
    hx = hi(x)
    ix = hx & 0x7FFFFFFF
    if ix <= 0x3FE921FB:                     # |x| ~<= pi/4
        return 0, x, 0.0
    if ix < 0x4002D97C:                      # |x| < 3pi/4, n = +-1
        if hx > 0:
            z = x - pio2_1
            if ix != 0x3FF921FB:
                y0 = z - pio2_1t
                y1 = (z - y0) - pio2_1t
            else:                            # near pi/2
                z = z - pio2_2
                y0 = z - pio2_2t
                y1 = (z - y0) - pio2_2t
            return 1, y0, y1
        z = x + pio2_1
        if ix != 0x3FF921FB:
            y0 = z + pio2_1t
            y1 = (z - y0) + pio2_1t
        else:
            z = z + pio2_2
            y0 = z + pio2_2t
            y1 = (z - y0) + pio2_2t
        return -1, y0, y1
    if ix <= 0x413921FB:                     # |x| ~<= 2^19*(pi/2), medium size
        t = abs(x)
        n = int(t * invpio2 + half)          # two operations, then C truncation (value > 0)
        fn = float(n)
        r = t - fn * pio2_1
        w = fn * pio2_1t
        if n < 32 and ix != NPIO2_HW[n - 1]:
            y0 = r - w
        else:
            j = ix >> 20
            y0 = r - w
            i = j - ((hi(y0) >> 20) & 0x7FF)
            if i > 16:                       # 2nd iteration
                t = r
                w = fn * pio2_2
                r = t - w
                w = fn * pio2_2t - ((t - r) - w)
                y0 = r - w
                i = j - ((hi(y0) >> 20) & 0x7FF)
                if i > 49:                   # 3rd iteration
                    t = r
                    w = fn * pio2_3
                    r = t - w
                    w = fn * pio2_3t - ((t - r) - w)
                    y0 = r - w
        y1 = (r - y0) - w
        if hx < 0:
            return -n, -y0, -y1
        return n, y0, y1
    raise ValueError("fdlibm large-argument branch is outside profile 1")


def sin(x):
    ix = hi(x) & 0x7FFFFFFF
    if ix <= 0x3FE921FB:
        return kernel_sin(x, 0.0, 0)
    if ix >= 0x7FF00000:
        return x - x
    n, y0, y1 = rem_pio2(x)
    m = n & 3
    if m == 0:
        return kernel_sin(y0, y1, 1)
    if m == 1:
        return kernel_cos(y0, y1)
    if m == 2:
        return -kernel_sin(y0, y1, 1)
    return -kernel_cos(y0, y1)


def cos(x):
    ix = hi(x) & 0x7FFFFFFF
    if ix <= 0x3FE921FB:
        return kernel_cos(x, 0.0)
    if ix >= 0x7FF00000:
        return x - x
    n, y0, y1 = rem_pio2(x)
    m = n & 3
    if m == 0:
        return kernel_cos(y0, y1)
    if m == 1:
        return -kernel_sin(y0, y1, 1)
    if m == 2:
        return -kernel_cos(y0, y1)
    return kernel_sin(y0, y1, 1)
