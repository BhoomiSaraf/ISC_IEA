"""Raw x/y trajectories of the frozen ISC map with configurable transient removal."""

import hashlib
import json

import numpy as np

from .isc_map import FROZEN_PARAMS, isc_step


def initial_conditions(seed, count, low=-1.0, high=1.0):
    """Deterministic initial conditions (x0, y0) drawn from PCG64(seed), uniform in [low, high).

    All `count` x0 values are drawn first, then all y0 values, so y0 depends on
    `count`: initial_conditions(s, 3) is not a prefix of initial_conditions(s, 10).
    Results stay reproducible because every run records the exact initial
    conditions it used; do not compare orbits across runs with different counts
    by index.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    x0 = rng.uniform(low, high, count)
    y0 = rng.uniform(low, high, count)
    return x0, y0


def generate_trajectory(x0, y0, n, transient=5000, params=FROZEN_PARAMS, dtype=np.float64, step=isc_step):
    """Iterate the map from (x0, y0), discard `transient` iterates, return the next `n`.

    Output index i holds iterate number transient + i + 1 (the initial condition
    itself is never returned).  `x0`, `y0` may be scalars or 1-D arrays of
    independent initial conditions; arrays give outputs of shape (n, K) that are
    bit-identical to running each initial condition on its own.
    """
    if n < 0 or transient < 0:
        raise ValueError("n and transient must be non-negative")
    x = np.asarray(x0, dtype=dtype)
    y = np.asarray(y0, dtype=dtype)
    if x.shape != y.shape or x.ndim > 1:
        raise ValueError("x0 and y0 must be scalars or 1-D arrays of equal length")
    if x.ndim == 0:
        x, y = x[()], y[()]

    for _ in range(transient):
        x, y = step(x, y, params)

    shape = (n,) + np.shape(x)
    xs = np.empty(shape, dtype=dtype)
    ys = np.empty(shape, dtype=dtype)
    for i in range(n):
        x, y = step(x, y, params)
        xs[i] = x
        ys[i] = y
    return xs, ys


def sha256_of_arrays(*arrays):
    h = hashlib.sha256()
    for arr in arrays:
        arr = np.ascontiguousarray(arr)
        h.update(str(arr.dtype).encode())
        h.update(str(arr.shape).encode())
        h.update(arr.tobytes())
    return h.hexdigest()


def save_trajectory(path, xs, ys, meta):
    """Save a raw trajectory as .npz (xs, ys, JSON metadata).  Refuses to overwrite."""
    import os
    if os.path.exists(path):
        raise FileExistsError(path)
    meta = dict(meta, sha256=sha256_of_arrays(xs, ys))
    with open(path, "xb") as f:
        np.savez_compressed(f, xs=xs, ys=ys, meta=json.dumps(meta))
    return meta["sha256"]


def load_trajectory(path):
    with np.load(path) as z:
        return z["xs"], z["ys"], json.loads(str(z["meta"]))
