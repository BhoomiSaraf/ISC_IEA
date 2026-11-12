"""Stages 4-5a: lanes, burn-in, output steps and byte extraction (algorithm_design.md §2, §6.2, §8.1).

stream  : one of ("sbox", "perm", "fwd", "bwd"), each with L = 64 lanes (256 lanes per message)
lane    : one ISC orbit, initial state from its own HKDF seed (state_map)
burn-in : T = 1024 steps per lane by default (build_streams(..., burn_in=T) accepts any T), never output
output step: every lane of the stream advances once, then emits B(x_l), B(y_l) for l = 0..63
extraction B(v), selectable per message (container EXTRACTION field, Phase 3A):
  EXTRACTION_MANTISSA8_V1 (1, default)       : m_byte(v)      = (bits(v) >> 8) & 0xFF
  EXTRACTION_K14_SCALED_MODULO_V1 (2)         : frac_byte*(v)  = floor(|v| * 1e14) mod 256
    (the k=14 scaled-floor-modulo transformation characterized in Step 1.1; frac_byte_scalar is a
    pure-Python, NumPy-free reimplementation for RefStream, frac_byte (isc_seq.extract) is reused,
    lazily imported, for NpStream only -- see extraction_backend_compatibility_specification.md)
Bytes are consumed strictly in order; take(m) runs only the output steps needed.

Backends: "reference" (R1, pure Python, profile 1 only) and "numpy" (V1, profiles 1 and 2).

Calling build_streams()/RefStream()/NpStream() without the extraction argument reproduces the
original mantissa8_v1-only behaviour byte-for-byte: this is the single most load-bearing backward-
compatibility guarantee in this file (see phase_3a_implementation_plan.md).
"""

import math
import struct

from .errors import ProfileError
from .kdf import LANES, STREAMS
from .state_map import seed_to_state

BURN_IN = 1024
BYTES_PER_STEP = 2 * LANES

EXTRACTION_MANTISSA8_V1 = 1
EXTRACTION_K14_SCALED_MODULO_V1 = 2
EXTRACTIONS = (EXTRACTION_MANTISSA8_V1, EXTRACTION_K14_SCALED_MODULO_V1)

_pack_d = struct.Struct(">d").pack


def m_byte(v):
    return _pack_d(v)[6]          # big-endian byte 6 = bits 8..15 of the binary64 encoding


def frac_byte_scalar(v):
    """Pure-Python, NumPy-free equivalent of isc_seq.extract.frac_byte for one float64 value.

    B(v) = floor(|v| * 1e14) mod 256. Returns a plain Python int in [0, 255]. |v| <= 1 for every
    value the ISC recurrence actually produces, so |v| * 1e14 <= 1e14 < 2**53: the floor is exact
    in float64 and math.floor/np.floor cannot disagree on an already-identical input (see
    extraction_backend_compatibility_specification.md §3, §6).
    """
    return math.floor(abs(float(v)) * 1e14) % 256


_SCALAR_EXTRACT = {
    EXTRACTION_MANTISSA8_V1: m_byte,
    EXTRACTION_K14_SCALED_MODULO_V1: frac_byte_scalar,
}


class RefStream:
    """R1 stream: list of [x, y] lane states, scalar steps."""

    def __init__(self, states, step, extraction=EXTRACTION_MANTISSA8_V1):
        self.states = [list(s) for s in states]
        self._step = step
        self._buf = bytearray()
        self.steps = 0
        self.consumed = 0
        if extraction not in _SCALAR_EXTRACT:
            raise ValueError("unknown extraction identifier")
        self.extraction = extraction
        self._extract = _SCALAR_EXTRACT[extraction]

    def burn_in(self, t):
        for s in self.states:
            x, y = s
            for _ in range(t):
                x, y = self._step(x, y)
            s[0], s[1] = x, y

    def _output_step(self):
        buf = self._buf
        step = self._step
        extract = self._extract
        for s in self.states:
            x, y = step(s[0], s[1])
            s[0], s[1] = x, y
            buf.append(extract(x))
            buf.append(extract(y))
        self.steps += 1

    def take(self, m):
        while len(self._buf) < m:
            self._output_step()
        out = bytes(self._buf[:m])
        del self._buf[:m]
        self.consumed += m
        return out

    def final_state_bytes(self):
        out = b"".join(_pack_d(x) + _pack_d(y) for x, y in self.states)
        return out + self.steps.to_bytes(8, "big")


class NpStream:
    """V1 stream: float64 arrays of the 64 lane states, vectorised steps."""

    def __init__(self, x, y, profile, extraction=EXTRACTION_MANTISSA8_V1):
        import numpy as np
        self._np = np
        self.x = np.array(x, dtype=np.float64)
        self.y = np.array(y, dtype=np.float64)
        self.profile = profile
        self._buf = b""
        self.steps = 0
        self.consumed = 0
        if extraction not in EXTRACTIONS:
            raise ValueError("unknown extraction identifier")
        self.extraction = extraction

    def take(self, m):
        np = self._np
        from .isc_step import step_vec
        need = m - len(self._buf)
        if need > 0:
            k = -(-need // BYTES_PER_STEP)
            xs = np.empty((k, LANES), dtype=np.float64)
            ys = np.empty((k, LANES), dtype=np.float64)
            x, y = self.x, self.y
            for j in range(k):
                x, y = step_vec(x, y, self.profile)
                xs[j] = x
                ys[j] = y
            self.x, self.y = x, y
            self.steps += k
            if self.extraction == EXTRACTION_MANTISSA8_V1:
                mb = np.stack([xs, ys], axis=-1).view(np.uint64)      # (k, 64, 2): lane-minor, x before y
                new = ((mb >> np.uint64(8)) & np.uint64(0xFF)).astype(np.uint8).tobytes()
            else:
                from isc_seq.extract import frac_byte          # lazy: optional dependency, numpy path only
                bx = frac_byte(xs)
                by = frac_byte(ys)
                new = np.stack([bx, by], axis=-1).astype(np.uint8).tobytes()   # same (k, 64, 2) layout
            self._buf += new
        out = self._buf[:m]
        self._buf = self._buf[m:]
        self.consumed += m
        return out

    def final_state_bytes(self):
        np = self._np
        st = np.stack([self.x, self.y], axis=-1).astype(">f8").tobytes()
        return st + self.steps.to_bytes(8, "big")


def build_streams(seeds, backend="numpy", profile=1, burn_in=BURN_IN, extraction=EXTRACTION_MANTISSA8_V1):
    """Initialise all 4 x 64 lanes from their seeds and burn them in. Returns {stream: Stream}.

    extraction (default EXTRACTION_MANTISSA8_V1) selects the byte-extraction function applied by
    every returned stream's take(); omitting it reproduces the original, single-extraction
    behaviour byte-for-byte for every existing call site.
    """
    if extraction not in EXTRACTIONS:
        raise ValueError("unknown extraction identifier")
    states = {g: [seed_to_state(s) for s in seeds[g]] for g in STREAMS}
    if backend == "reference":
        if profile != 1:
            raise ProfileError("the reference backend implements profile 1 only")
        from .isc_step import step_ref
        out = {}
        for g in STREAMS:
            st = RefStream(states[g], step_ref, extraction=extraction)
            st.burn_in(burn_in)
            out[g] = st
        return out
    if backend == "numpy":
        if profile not in (1, 2):
            raise ProfileError("unknown profile")
        import numpy as np
        from .isc_step import step_vec
        x = np.array([s[0] for g in STREAMS for s in states[g]], dtype=np.float64)   # 256 lanes, stream-major
        y = np.array([s[1] for g in STREAMS for s in states[g]], dtype=np.float64)
        for _ in range(burn_in):
            x, y = step_vec(x, y, profile)
        return {g: NpStream(x[i * LANES:(i + 1) * LANES], y[i * LANES:(i + 1) * LANES], profile,
                             extraction=extraction)
                for i, g in enumerate(STREAMS)}
    raise ValueError("backend must be 'reference' or 'numpy'")


def kcv_state_bytes(streams):
    """state_bytes of §10.1: per stream in canonical order, 64 x (BE64 x, BE64 y) then BE64(steps)."""
    return b"".join(streams[g].final_state_bytes() for g in STREAMS)
