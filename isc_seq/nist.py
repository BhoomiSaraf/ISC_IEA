"""Subset of NIST SP 800-22 Rev. 1a statistical tests, with the multi-sequence protocol.

Implemented (section numbers of SP 800-22 Rev. 1a):
    2.1  Frequency (monobit)          2.2  Frequency within a block
    2.3  Runs                         2.4  Longest run of ones in a block
    2.5  Binary matrix rank (32x32)   2.6  Discrete Fourier transform (spectral)
    2.9  Maurer's universal           2.11 Serial (2 p-values)
    2.12 Approximate entropy          2.13 Cumulative sums (forward, backward)

Not implemented here: non-overlapping / overlapping template matching, linear
complexity, random excursions (variant).  Run the official NIST STS on the
saved bitstreams for those.

Protocol (SP 800-22 section 4.2): a test is applied to m independent sequences
of n bits.  It is judged on
  * proportion of sequences with p >= alpha, which must lie within
    p_hat +/- 3 sqrt(p_hat (1 - p_hat) / m), p_hat = 1 - alpha;
  * uniformity of the p-values: chi-square over 10 equal bins,
    P_T = igamc(9/2, chi2/2) >= 0.0001 (only meaningful for m >= 55).
"""

import math

import numpy as np
from scipy.special import erfc, gammaincc
from scipy.stats import norm

ALPHA = 0.01
UNIFORMITY_THRESHOLD = 1e-4
UNIFORMITY_MIN_SEQUENCES = 55


def _bits(eps):
    if isinstance(eps, str):
        return np.frombuffer(eps.encode(), dtype=np.uint8) - ord("0")
    return np.asarray(eps, dtype=np.uint8)


def frequency(eps):
    e = _bits(eps)
    n = e.size
    s = 2 * int(e.sum()) - n
    return float(erfc(abs(s) / math.sqrt(n) / math.sqrt(2)))


def block_frequency(eps, M=128):
    e = _bits(eps)
    N = e.size // M
    pi = e[: N * M].reshape(N, M).mean(axis=1)
    chi2 = 4.0 * M * float(np.sum((pi - 0.5) ** 2))
    return float(gammaincc(N / 2.0, chi2 / 2.0))


def runs(eps):
    e = _bits(eps)
    n = e.size
    pi = e.mean()
    if abs(pi - 0.5) >= 2.0 / math.sqrt(n):
        return 0.0
    v = 1 + int(np.count_nonzero(e[1:] != e[:-1]))
    return float(erfc(abs(v - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi))))


_LONGEST_RUN_TABLE = [
    # (min n, M, class lower edge, class upper edge, probabilities)
    (750000, 10000, 10, 16, [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]),
    (6272, 128, 4, 9, [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]),
    (128, 8, 1, 4, [0.2148, 0.3672, 0.2305, 0.1875]),
]


def _longest_run_of_ones(block):
    padded = np.concatenate(([0], block, [0])).astype(np.int8)
    d = np.diff(padded)
    starts = np.flatnonzero(d == 1)
    ends = np.flatnonzero(d == -1)
    return int((ends - starts).max()) if starts.size else 0


def longest_run(eps):
    e = _bits(eps)
    n = e.size
    for min_n, M, lo, hi, probs in _LONGEST_RUN_TABLE:
        if n >= min_n:
            break
    else:
        raise ValueError("longest_run needs n >= 128")
    N = n // M
    blocks = e[: N * M].reshape(N, M)
    longest = np.array([_longest_run_of_ones(b) for b in blocks])
    v = np.bincount(np.clip(longest, lo, hi) - lo, minlength=hi - lo + 1)
    probs = np.array(probs)
    chi2 = float(np.sum((v - N * probs) ** 2 / (N * probs)))
    K = len(probs) - 1
    return float(gammaincc(K / 2.0, chi2 / 2.0))


def gf2_rank(rows, ncols):
    """Rank over GF(2) of a stack of matrices given as integer rows.

    rows: int array of shape (N, R); bit j of rows[i, r] is column j of row r.
    """
    rows = np.array(rows, dtype=np.uint64)
    N, R = rows.shape
    rank = np.zeros(N, dtype=np.int64)
    idx = np.arange(R)
    for bit in range(ncols - 1, -1, -1):
        has = ((rows >> np.uint64(bit)) & np.uint64(1)).astype(bool)
        elig = has & (idx[None, :] >= rank[:, None])
        sel_m = np.flatnonzero(elig.any(axis=1))
        if sel_m.size == 0:
            continue
        piv = np.argmax(elig[sel_m], axis=1)
        r = rank[sel_m]
        tmp = rows[sel_m, r].copy()
        rows[sel_m, r] = rows[sel_m, piv]
        rows[sel_m, piv] = tmp
        prow = rows[sel_m, r]
        sub = rows[sel_m]
        mask = ((sub >> np.uint64(bit)) & np.uint64(1)).astype(bool)
        mask[np.arange(sel_m.size), r] = False
        rows[sel_m] = np.where(mask, sub ^ prow[:, None], sub)
        rank[sel_m] += 1
    return rank


def _rank_probabilities(M, Q):
    def prob(r):
        p = 2.0 ** (r * (Q + M - r) - M * Q)
        for i in range(r):
            p *= (1 - 2.0 ** (i - Q)) * (1 - 2.0 ** (i - M)) / (1 - 2.0 ** (i - r))
        return p
    full = prob(M)
    minus1 = prob(M - 1)
    return full, minus1, 1.0 - full - minus1


def binary_matrix_rank(eps, M=32, Q=32):
    e = _bits(eps)
    N = e.size // (M * Q)
    if N == 0:
        raise ValueError("sequence too short for binary_matrix_rank")
    mats = e[: N * M * Q].reshape(N, M, Q).astype(np.uint64)
    weights = np.uint64(1) << np.arange(Q - 1, -1, -1, dtype=np.uint64)
    rows = (mats * weights).sum(axis=2, dtype=np.uint64)
    rank = gf2_rank(rows, Q)
    f_m = int(np.sum(rank == M))
    f_m1 = int(np.sum(rank == M - 1))
    rest = N - f_m - f_m1
    p_full, p_m1, p_rest = _rank_probabilities(M, Q)
    chi2 = ((f_m - p_full * N) ** 2 / (p_full * N)
            + (f_m1 - p_m1 * N) ** 2 / (p_m1 * N)
            + (rest - p_rest * N) ** 2 / (p_rest * N))
    return float(math.exp(-chi2 / 2.0))


def dft(eps):
    e = _bits(eps)
    n = e.size
    x = 2.0 * e - 1.0
    m = np.abs(np.fft.fft(x))[: n // 2]
    T = math.sqrt(math.log(1 / 0.05) * n)
    N0 = 0.95 * n / 2.0
    N1 = int(np.count_nonzero(m < T))
    d = (N1 - N0) / math.sqrt(n * 0.95 * 0.05 / 4.0)
    return float(erfc(abs(d) / math.sqrt(2)))


_UNIVERSAL_TABLE = {
    # L: (expected value, variance)
    1: (0.7326495, 0.690), 2: (1.5374383, 1.338), 3: (2.4016068, 1.901),
    4: (3.3112247, 2.358), 5: (4.2534266, 2.705), 6: (5.2177052, 2.954),
    7: (6.1962507, 3.125), 8: (7.1836656, 3.238), 9: (8.1764248, 3.311),
    10: (9.1723243, 3.356), 11: (10.170032, 3.384), 12: (11.168765, 3.401),
    13: (12.168070, 3.410), 14: (13.167693, 3.416), 15: (14.167488, 3.419),
    16: (15.167379, 3.421),
}
_UNIVERSAL_L = [(1059061760, 16), (496435200, 15), (231669760, 14), (107560960, 13),
                (49643520, 12), (22753280, 11), (10342400, 10), (4654080, 9),
                (2068480, 8), (904960, 7), (387840, 6)]


def universal(eps, L=None, Q=None):
    e = _bits(eps)
    n = e.size
    if L is None:
        L = next((l for min_n, l in _UNIVERSAL_L if n >= min_n), None)
        if L is None:
            raise ValueError("universal needs n >= 387840 (or explicit L, Q)")
    if Q is None:
        Q = 10 * 2 ** L
    nblocks = n // L
    K = nblocks - Q
    weights = 1 << np.arange(L - 1, -1, -1)
    vals = (e[: nblocks * L].reshape(nblocks, L).astype(np.int64) * weights).sum(axis=1)
    # Last-occurrence table: initialised on the first Q blocks, updated over the K test blocks.
    tbl = [0] * (2 ** L)
    vals = vals.tolist()
    for i, v in enumerate(vals[:Q], start=1):
        tbl[v] = i
    total = 0.0
    for i, v in enumerate(vals[Q:], start=Q + 1):
        total += math.log2(i - tbl[v])
        tbl[v] = i
    fn = total / K
    expected, variance = _UNIVERSAL_TABLE[L]
    c = 0.7 - 0.8 / L + (4 + 32 / L) * K ** (-3 / L) / 15
    sigma = c * math.sqrt(variance / K)
    return float(erfc(abs(fn - expected) / (math.sqrt(2) * sigma)))


def _pattern_counts(e, m):
    if m == 0:
        return np.array([e.size])
    n = e.size
    ext = np.concatenate((e, e[: m - 1])).astype(np.int64)
    vals = np.zeros(n, dtype=np.int64)
    for j in range(m):
        vals = (vals << 1) | ext[j: j + n]
    return np.bincount(vals, minlength=2 ** m)


def serial(eps, m=16):
    e = _bits(eps)
    n = e.size

    def psi2(k):
        if k <= 0:
            return 0.0
        v = _pattern_counts(e, k).astype(np.float64)
        return (2.0 ** k / n) * float(np.sum(v * v)) - n

    p0, p1, p2 = psi2(m), psi2(m - 1), psi2(m - 2)
    d1 = p0 - p1
    d2 = p0 - 2 * p1 + p2
    return (float(gammaincc(2.0 ** (m - 2), d1 / 2.0)),
            float(gammaincc(2.0 ** (m - 3), d2 / 2.0)))


def approximate_entropy(eps, m=10):
    e = _bits(eps)
    n = e.size

    def phi(k):
        c = _pattern_counts(e, k).astype(np.float64) / n
        c = c[c > 0]
        return float(np.sum(c * np.log(c)))

    apen = phi(m) - phi(m + 1)
    chi2 = 2.0 * n * (math.log(2) - apen)
    return float(gammaincc(2.0 ** (m - 1), chi2 / 2.0))


def cumulative_sums(eps):
    """Returns (forward p-value, backward p-value)."""
    e = _bits(eps)
    n = e.size
    x = 2 * e.astype(np.int64) - 1
    out = []
    for seq in (x, x[::-1]):
        z = int(np.max(np.abs(np.cumsum(seq))))
        sq = math.sqrt(n)
        k1 = np.arange(math.trunc((-n / z + 1) / 4), math.trunc((n / z - 1) / 4) + 1)
        k2 = np.arange(math.trunc((-n / z - 3) / 4), math.trunc((n / z - 1) / 4) + 1)
        s1 = np.sum(norm.cdf((4 * k1 + 1) * z / sq) - norm.cdf((4 * k1 - 1) * z / sq))
        s2 = np.sum(norm.cdf((4 * k2 + 3) * z / sq) - norm.cdf((4 * k2 + 1) * z / sq))
        out.append(float(1.0 - s1 + s2))
    return tuple(out)


def run_battery(eps, serial_m=16, apen_m=10, block_M=128):
    """Run every implemented test on one sequence.  Returns {test_name: p_value}."""
    e = _bits(eps)
    n = e.size
    res = {
        "Frequency": frequency(e),
        "BlockFrequency": block_frequency(e, block_M),
        "Runs": runs(e),
        "LongestRun": longest_run(e),
        "Rank": binary_matrix_rank(e),
        "FFT": dft(e),
    }
    if n >= 387840:
        res["Universal"] = universal(e)
    s1, s2 = serial(e, serial_m)
    res["Serial_1"], res["Serial_2"] = s1, s2
    res["ApproximateEntropy"] = approximate_entropy(e, apen_m)
    res["CumulativeSums_fwd"], res["CumulativeSums_bwd"] = cumulative_sums(e)
    return res


def proportion_range(m, alpha=ALPHA):
    p = 1 - alpha
    half = 3 * math.sqrt(p * (1 - p) / m)
    return p - half, p + half


def uniformity_p(pvalues):
    counts = np.histogram(np.clip(pvalues, 0, 1), bins=10, range=(0, 1))[0]
    m = len(pvalues)
    chi2 = float(np.sum((counts - m / 10.0) ** 2 / (m / 10.0)))
    return float(gammaincc(9 / 2.0, chi2 / 2.0))


def evaluate(pvalue_table, alpha=ALPHA):
    """pvalue_table: {test: [p for each sequence]} -> per-test protocol summary."""
    out = {}
    for test, ps in pvalue_table.items():
        ps = np.asarray(ps, dtype=np.float64)
        m = ps.size
        lo, hi = proportion_range(m, alpha)
        prop = float(np.mean(ps >= alpha))
        prop_ok = lo <= prop
        if m >= UNIFORMITY_MIN_SEQUENCES:
            pt = uniformity_p(ps)
            uni_ok = pt >= UNIFORMITY_THRESHOLD
        else:
            pt, uni_ok = None, None
        out[test] = {
            "m": m, "passed": int(np.sum(ps >= alpha)), "proportion": prop,
            "proportion_min": lo, "proportion_ok": bool(prop_ok),
            "uniformity_p": pt, "uniformity_ok": uni_ok,
            "pass": bool(prop_ok and (uni_ok is not False)),
        }
    return out
