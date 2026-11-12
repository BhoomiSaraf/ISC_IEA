"""Shared helpers for the Phase 3B experiment scripts. New code; does not modify production files.

Imports isc_cipher/isc_seq (production, read-only) and, for the MI estimator only, imports (does
not modify) the frozen ISC_PBL/isc_sequence_characterization.py Miller-Madow + permutation-null +
circular-shift-null methodology, re-implemented here for discrete byte-domain data (256x256 bins
over [0,256) integers) since the frozen function operates on continuous phase-space floats over
[-1,1] and cannot be called directly on byte arrays.
"""
import math
import os
import sys

import numpy as np
from scipy import stats as sps

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from isc_cipher.kdf import Derivation, context, STREAMS, LANES  # noqa: E402
from isc_cipher.generator import build_streams, BYTES_PER_STEP  # noqa: E402
from isc_seq import nist as isc_nist  # noqa: E402

BYTES_PER_LANE_PRIMARY = 125_000   # Section 2.4 target; confirmed feasible by pilot_benchmark.py
BYTES_PER_LANE_BURNIN = 20_000     # Section 4 burn-in sweep; smaller, per pilot measured throughput

SEED_CONFIGS = {
    "seedA": (bytes.fromhex("11" * 32), bytes.fromhex("22" * 16)),
    "seedB": (bytes.fromhex("33" * 32), bytes.fromhex("44" * 16)),
    "seedC": (bytes.fromhex("55" * 32), bytes.fromhex("66" * 16)),
}


def get_seeds(key, nonce):
    ctx = context(profile=1, dtype=1, h=0, w=0, c=1)
    return Derivation(key, nonce, ctx).seeds()


def generate(seed_label, extraction, burn_in, bytes_per_lane, streams_subset=None):
    """Returns {stream: bytes} with len == bytes_per_lane*64 for each requested stream."""
    key, nonce = SEED_CONFIGS[seed_label]
    seeds = get_seeds(key, nonce)
    streams = build_streams(seeds, backend="numpy", profile=1, burn_in=burn_in, extraction=extraction)
    m = bytes_per_lane * LANES
    out = {}
    for g in (streams_subset or STREAMS):
        out[g] = streams[g].take(m)
    return out


def lane_subsequence(stream_bytes, lane_idx):
    """Extract one lane's own output byte sequence from a round-robin-interleaved stream.

    Layout (generator.py NpStream.take): round r emits 128 bytes = [lane0_x,lane0_y,...,lane63_x,
    lane63_y]; lane l's own x,y pair sits at offset 2*l within each 128-byte round.
    """
    arr = np.frombuffer(stream_bytes, dtype=np.uint8)
    n_rounds = arr.size // BYTES_PER_STEP
    arr = arr[: n_rounds * BYTES_PER_STEP].reshape(n_rounds, 64, 2)
    return arr[:, lane_idx, :].reshape(-1)  # x0,y0,x1,y1,...


def shannon_entropy_bytes(byte_arr):
    counts = np.bincount(byte_arr, minlength=256).astype(np.float64)
    p = counts[counts > 0] / counts.sum()
    return float(-np.sum(p * np.log2(p))), counts


def chisquare_uniform(counts):
    n = counts.sum()
    expected = n / 256.0
    chi2 = float(np.sum((counts - expected) ** 2 / expected))
    p = float(sps.chi2.sf(chi2, 255))
    return chi2, p


def acf_biased(seq, max_lag=100):
    """Same biased estimator as isc_seq.stats.acf, explicitly disclosed as biased (see report)."""
    s = seq.astype(np.float64)
    s = s - s.mean()
    denom = float(s @ s)
    if denom == 0:
        return np.zeros(max_lag)
    return np.array([float(s[k:] @ s[:-k]) / denom for k in range(1, max_lag + 1)])


def bonferroni_bound(n_samples, n_tests, alpha=0.05):
    z_fam = sps.norm.isf(alpha / (2 * n_tests))
    return z_fam / math.sqrt(n_samples)


def mutual_information_bytes(byte_seq_a, byte_seq_b, n_perm=200, n_shift=100, seed=42):
    """Miller-Madow-corrected MI between two aligned byte sequences in [0,255].

    Re-implements, for discrete byte data, the exact methodology of
    ISC_PBL/isc_sequence_characterization.py:analyze_joint_distribution_2d (351-458): plug-in MI,
    analytical Miller-Madow bias (R-1)(C-1)/(2N ln2), i.i.d. permutation-null trials, and
    circular-time-shift null surrogates. The frozen file is imported conceptually (formula reused),
    not imported as code, because that function histograms continuous floats over [-1,1] with
    np.histogram2d, not integer bytes over [0,256) — bins/range differ, logic is identical.
    """
    a = byte_seq_a.astype(np.int64)
    b = byte_seq_b.astype(np.int64)
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    bins = 256

    def mi_of(x_idx, y_idx):
        c2d = np.bincount(x_idx * bins + y_idx, minlength=bins * bins).reshape(bins, bins)
        pxy = c2d / float(n)
        px = pxy.sum(axis=1)
        py = pxy.sum(axis=0)
        outer = px[:, None] * py[None, :]
        nz = (pxy > 0) & (outer > 0)
        return float(np.sum(pxy[nz] * np.log2(pxy[nz] / outer[nz])))

    raw_mi = mi_of(a, b)
    bias = ((bins - 1) * (bins - 1)) / (2.0 * n * math.log(2.0))

    rng = np.random.default_rng(seed)
    perm_mis = np.empty(n_perm)
    for i in range(n_perm):
        perm_mis[i] = mi_of(a, rng.permutation(b))
    shift_mis = np.empty(n_shift)
    lags = rng.integers(max(1, n // 100), max(2, n - n // 100), size=n_shift)
    for i, lag in enumerate(lags):
        shift_mis[i] = mi_of(a, np.roll(b, int(lag)))

    return {
        "n": int(n),
        "raw_mi_bits": raw_mi,
        "miller_madow_bias_bits": bias,
        "adjusted_mi_bits": max(0.0, raw_mi - bias),
        "perm_null_trials": n_perm,
        "perm_null_mean_bits": float(perm_mis.mean()),
        "perm_null_std_bits": float(perm_mis.std()),
        "perm_empirical_p": float(np.mean(perm_mis >= raw_mi)),
        "shift_null_trials": n_shift,
        "shift_null_mean_bits": float(shift_mis.mean()),
        "shift_null_std_bits": float(shift_mis.std()),
        "shift_empirical_p": float(np.mean(shift_mis >= raw_mi)),
    }
