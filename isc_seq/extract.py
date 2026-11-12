"""Digital extraction: turn raw x/y trajectories into bitstreams.

Every method consumes the x and y values of each iteration and emits a fixed
number of bits per iteration, ordered x-part then y-part (interleaved by
iteration, MSB first).  Methods are deliberately independent so each can be
evaluated on its own.

sign          x>0, y>0                                 2 bits/iter  (legacy baseline)
arccos8       byte of u = arccos(-v)/pi for v = x, y   16 bits/iter
frac8         floor(|v| * 1e14) mod 256 for v = x, y   16 bits/iter
mantissa8     bits 8..15 of the float64 mantissa       16 bits/iter
mantissa8_xor mantissa8(x) XOR mantissa8(y)            8 bits/iter

Notes
-----
* x_{n+1} = 2 sin^2(wX) - 1 = -cos(2wX), so arccos(-x)/pi is 2wX folded into
  [0, 1].  If 2wX is spread over many periods this is close to uniform; whether
  it actually is must be measured, not assumed.
* frac8 and mantissa8 read low-order digits of the float64 state.  They depend
  on the exact floating-point evaluation (see isc_map docstring).
"""

from dataclasses import dataclass

import numpy as np


def _bytes_to_bits(byte_cols):
    """byte_cols: list of uint8 arrays of length N -> bits interleaved per iteration."""
    stacked = np.stack([np.asarray(b, dtype=np.uint8) for b in byte_cols], axis=-1)
    return np.unpackbits(stacked.reshape(-1), bitorder="big")


def _check(xs, ys):
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    if xs.shape != ys.shape or xs.ndim != 1:
        raise ValueError("xs and ys must be 1-D arrays of equal length")
    return xs, ys


def sign_bits(xs, ys):
    xs, ys = _check(xs, ys)
    return np.stack([xs > 0, ys > 0], axis=-1).reshape(-1).astype(np.uint8)


def arccos_byte(v):
    u = np.arccos(np.clip(-np.asarray(v, dtype=np.float64), -1.0, 1.0)) / np.pi
    return np.minimum(np.floor(u * 256.0), 255).astype(np.uint8)


def arccos8_bits(xs, ys):
    xs, ys = _check(xs, ys)
    return _bytes_to_bits([arccos_byte(xs), arccos_byte(ys)])


FRAC_SCALE = 1e14  # |v| < 1 so |v| * 1e14 < 2**53: floor is exact


def frac_byte(v):
    return (np.floor(np.abs(np.asarray(v, dtype=np.float64)) * FRAC_SCALE) % 256).astype(np.uint8)


def frac8_bits(xs, ys):
    xs, ys = _check(xs, ys)
    return _bytes_to_bits([frac_byte(xs), frac_byte(ys)])


MANTISSA_SHIFT = 8  # skip the 8 least-significant mantissa bits


def mantissa_byte(v):
    v = np.asarray(v, dtype=np.float64)
    raw = np.ascontiguousarray(v).view(np.uint64).reshape(v.shape)
    mant = raw & np.uint64((1 << 52) - 1)
    return ((mant >> np.uint64(MANTISSA_SHIFT)) & np.uint64(0xFF)).astype(np.uint8)


def mantissa8_bits(xs, ys):
    xs, ys = _check(xs, ys)
    return _bytes_to_bits([mantissa_byte(xs), mantissa_byte(ys)])


def mantissa8_xor_bits(xs, ys):
    xs, ys = _check(xs, ys)
    return _bytes_to_bits([mantissa_byte(xs) ^ mantissa_byte(ys)])


@dataclass(frozen=True)
class Extractor:
    name: str
    bits_per_iter: int
    func: object
    description: str

    def __call__(self, xs, ys):
        return self.func(xs, ys)

    def iterations_for(self, n_bits):
        return -(-n_bits // self.bits_per_iter)


METHODS = {
    e.name: e
    for e in [
        Extractor("sign", 2, sign_bits, "sign of x and y (threshold 0)"),
        Extractor("arccos8", 16, arccos8_bits, "8-bit quantisation of arccos(-v)/pi"),
        Extractor("frac8", 16, frac8_bits, "floor(|v|*1e14) mod 256"),
        Extractor("mantissa8", 16, mantissa8_bits, "float64 mantissa bits 8..15"),
        Extractor("mantissa8_xor", 8, mantissa8_xor_bits, "mantissa8(x) XOR mantissa8(y)"),
    ]
}


def extract(method, xs, ys, n_bits=None):
    """Extract bits with a named method, optionally truncated to exactly n_bits."""
    ext = METHODS[method]
    bits = ext(xs, ys)
    if n_bits is not None:
        if bits.size < n_bits:
            raise ValueError(f"{method}: need {ext.iterations_for(n_bits)} iterations for {n_bits} bits")
        bits = bits[:n_bits]
    return bits
