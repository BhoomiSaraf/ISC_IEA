"""Statistical diagnostics for raw ISC trajectories and extracted bitstreams.

These are descriptive checks; NIST SP 800-22 testing lives in nist.py.
"""

import math

import numpy as np
from scipy import stats as sps


def shannon_entropy(counts):
    counts = np.asarray(counts, dtype=np.float64).ravel()
    p = counts[counts > 0] / counts.sum()
    return float(-np.sum(p * np.log2(p)))


def acf(seq, max_lag=10):
    """Sample autocorrelation r_k for k = 1..max_lag (biased estimator, as in the legacy scripts)."""
    s = np.asarray(seq, dtype=np.float64)
    s = s - s.mean()
    denom = float(s @ s)
    return np.array([float(s[k:] @ s[:-k]) / denom for k in range(1, max_lag + 1)])


def acf_band(n, z=1.96):
    """Approximate 95% band for the ACF of white noise of length n."""
    return z / math.sqrt(n)


def raw_trajectory_stats(xs, ys, max_lag=10, bins=256):
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    n = xs.size
    hx, _ = np.histogram(xs, bins=bins, range=(-1, 1))
    hy, _ = np.histogram(ys, bins=bins, range=(-1, 1))
    hxy, _, _ = np.histogram2d(xs, ys, bins=bins, range=[[-1, 1], [-1, 1]])
    return {
        "n": int(n),
        "min_x": float(xs.min()), "max_x": float(xs.max()),
        "min_y": float(ys.min()), "max_y": float(ys.max()),
        "mean_x": float(xs.mean()), "mean_y": float(ys.mean()),
        "p_x_gt_0": float(np.mean(xs > 0)), "p_y_gt_0": float(np.mean(ys > 0)),
        "corr_xy_lag0": float(np.corrcoef(xs, ys)[0, 1]),
        "acf_x": acf(xs, max_lag).tolist(),
        "acf_y": acf(ys, max_lag).tolist(),
        "acf_band_95": acf_band(n),
        "H_x_bits": shannon_entropy(hx),
        "H_y_bits": shannon_entropy(hy),
        "H_xy_bits": shannon_entropy(hxy),
        "bins": bins,
    }


def entropy_vs_n(xs, ys, ns, bins=256):
    """2-D histogram entropy on the first N points for each N in `ns` (shows sample-size bias)."""
    rows = []
    for n in ns:
        if n > len(xs):
            continue
        hxy, _, _ = np.histogram2d(xs[:n], ys[:n], bins=bins, range=[[-1, 1], [-1, 1]])
        h = shannon_entropy(hxy)
        rows.append({"n": int(n), "H_xy_bits": h, "H_xy_normalized": h / math.log2(bins * bins),
                     "log2_n_bound": math.log2(n)})
    return rows


def bit_stats(bits):
    """Bias, lag-1 bit correlation, and byte-level uniformity of a 0/1 array."""
    bits = np.asarray(bits, dtype=np.uint8)
    n = bits.size
    ones = int(bits.sum())
    z = (2 * ones - n) / math.sqrt(n)
    same = float(np.mean(bits[1:] == bits[:-1]))
    nbytes = n // 8
    by = np.packbits(bits[: nbytes * 8], bitorder="big")
    counts = np.bincount(by, minlength=256)
    expected = nbytes / 256.0
    chi2 = float(((counts - expected) ** 2 / expected).sum())
    return {
        "n_bits": int(n),
        "ones_fraction": ones / n,
        "monobit_z": z,
        "monobit_p": math.erfc(abs(z) / math.sqrt(2)),
        "p_bit_equals_next": same,
        "byte_chi2": chi2,
        "byte_chi2_p": float(sps.chi2.sf(chi2, 255)),
        "byte_entropy_bits": shannon_entropy(counts),
    }
