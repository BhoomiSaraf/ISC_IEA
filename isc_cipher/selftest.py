"""Profile self-test (algorithm_design.md §11.2 step 9), run once per process per (profile, backend).

Profile 1: SIN/COS bit patterns and a short ISC trajectory are compared with expected values
produced by the independent C oracle (official fdlibm 5.3 sources; isc_cipher_kat/oracle), stored in
_selftest_vectors.py. Profile 2 (host libm, comparison only) has no portable expected values and
is accepted without a self-test, which is why it is non-normative.
"""

import struct

from .errors import ProfileError

_DONE = set()


def _f(h):
    return struct.unpack(">d", bytes.fromhex(h))[0]


def _h(v):
    return struct.pack(">d", float(v)).hex()


def run_selftest(profile, backend):
    if profile == 2:
        if backend != "numpy":
            raise ProfileError("profile 2 requires the numpy backend")
        return
    if profile != 1:
        raise ProfileError("unknown profile")
    from ._selftest_vectors import TRAJ, TRIG
    if backend == "reference":
        from . import fdlibm_ref as F
        from .isc_step import step_ref
        for a, s, c in TRIG:
            x = _f(a)
            if _h(F.sin(x)) != s or _h(F.cos(x)) != c:
                raise ProfileError("profile 1 self-test failed (sin/cos)")
        x, y = _f(TRAJ["x0"]), _f(TRAJ["y0"])
        for _ in range(TRAJ["steps"]):
            x, y = step_ref(x, y)
        if (_h(x), _h(y)) != (TRAJ["x"], TRAJ["y"]):
            raise ProfileError("profile 1 self-test failed (trajectory)")
    elif backend == "numpy":
        import numpy as np
        from . import fdlibm_np as F
        from .isc_step import step_vec
        args = np.array([_f(a) for a, _, _ in TRIG])
        s = [_h(v) for v in F.sin(args)]
        c = [_h(v) for v in F.cos(args)]
        if s != [t[1] for t in TRIG] or c != [t[2] for t in TRIG]:
            raise ProfileError("profile 1 self-test failed (sin/cos)")
        x = np.array([_f(TRAJ["x0"])])
        y = np.array([_f(TRAJ["y0"])])
        for _ in range(TRAJ["steps"]):
            x, y = step_vec(x, y, 1)
        if (_h(x[0]), _h(y[0])) != (TRAJ["x"], TRAJ["y"]):
            raise ProfileError("profile 1 self-test failed (trajectory)")
    else:
        raise ProfileError("unknown backend")


def ensure_selftest(profile, backend):
    if (profile, backend) not in _DONE:
        run_selftest(profile, backend)
        _DONE.add((profile, backend))
