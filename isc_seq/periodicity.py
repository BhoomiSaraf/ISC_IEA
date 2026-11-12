"""Finite-precision periodicity of the ISC map.

Any deterministic map on a finite state space is eventually periodic.  For an
orbit s_0, s_1, ... we report the pre-period mu (index of the first state on the
cycle) and the period lambda, found with Brent's algorithm.

The legacy script/final_validation.py used Floyd's algorithm and reported the
*meeting index*, which is a multiple of lambda, not lambda itself.
`floyd_meeting_index` reproduces that quantity so the two can be reconciled.
"""

import numpy as np

from .isc_map import FROZEN_PARAMS, isc_step


def make_map(dtype=np.float64, quant_bits=None, params=FROZEN_PARAMS, step=isc_step):
    """Return f(state) -> state for a 2-tuple state in the given precision.

    dtype       np.float32 or np.float64 arithmetic
    quant_bits  if set, round x and y to multiples of 2**-quant_bits after every
                step (a fixed-point state with 2*quant_bits+2 bits)
    """
    dtype = np.dtype(dtype).type
    scale = None if quant_bits is None else dtype(2.0 ** quant_bits)

    def f(state):
        x, y = step(state[0], state[1], params)
        x, y = dtype(x), dtype(y)
        if scale is not None:
            x = np.round(x * scale) / scale
            y = np.round(y * scale) / scale
        return (x, y)

    return f


def brent(f, s0, max_steps):
    """Brent's cycle detection.  Returns (mu, lam), or None if no cycle within max_steps.

    max_steps bounds the number of f evaluations in the period-finding phase,
    which needs roughly mu + 2*lam evaluations or less.
    """
    power = lam = 1
    tortoise = s0
    hare = f(s0)
    evals = 1
    while tortoise != hare:
        if power == lam:
            tortoise = hare
            power *= 2
            lam = 0
        hare = f(hare)
        lam += 1
        evals += 1
        if evals > max_steps:
            return None

    tortoise = hare = s0
    for _ in range(lam):
        hare = f(hare)
    mu = 0
    while tortoise != hare:
        tortoise = f(tortoise)
        hare = f(hare)
        mu += 1
    return mu, lam


def floyd_meeting_index(f, s0, max_iter):
    """Reproduce the value returned by find_cycle() in script/final_validation.py.

    Tortoise starts at s_0, hare at s_1; at loop index i the tortoise is at
    s_{i-1} and the hare at s_{2i-1}.  The first i with equality is returned.
    It satisfies i % lam == 0 and i - 1 >= mu; it is not the period.
    """
    t, h = s0, f(s0)
    for i in range(1, max_iter):
        if t == h:
            return i
        t = f(t)
        h = f(f(h))
    return None


def as_state(x0, y0, dtype):
    dtype = np.dtype(dtype).type
    return (dtype(x0), dtype(y0))
