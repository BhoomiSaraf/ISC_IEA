"""NIST SP 800-22 Rev. 1a worked examples (section 2.x.8) and protocol checks."""

import numpy as np
import pytest

from isc_seq import nist

# 100-bit example sequence used in several SP 800-22 worked examples.
EPS100 = ("11001001000011111101101010100010001000010110100011"
          "00001000110100110001001100011001100010100010111000")
EPS128 = ("11001100000101010110110001001100111000000000001001"
          "00110101010001000100111101011010000000110101111100"
          "1100111001101101100010110010")


def close(a, b, tol=1e-6):
    return abs(a - b) < tol


def test_frequency_example():
    assert close(nist.frequency(EPS100), 0.109599)


def test_block_frequency_example():
    assert close(nist.block_frequency(EPS100, M=10), 0.706438)


def test_runs_example():
    assert close(nist.runs(EPS100), 0.500798)


def test_longest_run_example():
    # SP 800-22 reports chi2 = 4.882605 and P = 0.180609; recomputing igamc(3/2, chi2/2)
    # gives 0.180598, so the published P carries a ~1e-5 rounding difference.
    assert len(EPS128) == 128
    assert close(nist.longest_run(EPS128), 0.180609, tol=2e-5)


def brute_universal(eps, L, Q):
    import math
    blocks = [int(eps[i:i + L], 2) for i in range(0, len(eps) - len(eps) % L, L)]
    last = {}
    for i, b in enumerate(blocks[:Q], start=1):
        last[b] = i
    total = 0.0
    for i, b in enumerate(blocks[Q:], start=Q + 1):
        total += math.log2(i - last.get(b, 0))
        last[b] = i
    K = len(blocks) - Q
    fn = total / K
    expected, variance = nist._UNIVERSAL_TABLE[L]
    c = 0.7 - 0.8 / L + (4 + 32 / L) * K ** (-3 / L) / 15
    return math.erfc(abs(fn - expected) / (math.sqrt(2) * c * math.sqrt(variance / K)))


def test_universal_matches_independent_computation():
    # The worked example in SP 800-22 section 2.9.8 is internally inconsistent with its own
    # sigma formula, so the implementation is checked against an independent computation
    # that follows the formula (and the reference STS code) instead.
    rng = np.random.Generator(np.random.PCG64(9))
    eps = "".join(map(str, rng.integers(0, 2, 400_000)))
    assert close(nist.universal(eps), brute_universal(eps, 6, 640), tol=1e-12)


def test_battery_protocol_on_reference_prng():
    """All implemented tests pass the SP 800-22 protocol on m=60 PCG64 sequences.

    The DFT and universal worked examples in SP 800-22 could not be reproduced from their
    printed inputs, so this protocol-level check is the main validation for those tests.
    """
    table = {}
    for s in range(60):
        rng = np.random.Generator(np.random.PCG64(1000 + s))
        res = nist.run_battery(rng.integers(0, 2, 400_000, dtype=np.uint8))
        for k, p in res.items():
            table.setdefault(k, []).append(p)
    summary = nist.evaluate(table)
    assert "Universal" in summary and "FFT" in summary
    failed = {k: v for k, v in summary.items() if not v["pass"]}
    assert not failed, failed


def test_serial_example():
    p1, p2 = nist.serial("0011011101", m=3)
    assert close(p1, 0.808792) and close(p2, 0.670320)


def test_approximate_entropy_example():
    assert close(nist.approximate_entropy(EPS100, m=2), 0.235301)


def test_cumulative_sums_example():
    fwd, bwd = nist.cumulative_sums(EPS100)
    assert close(fwd, 0.219194) and close(bwd, 0.114866)


def brute_rank(mat):
    m = [row[:] for row in mat]
    rank, rows, cols = 0, len(m), len(m[0])
    for c in range(cols):
        piv = next((r for r in range(rank, rows) if m[r][c]), None)
        if piv is None:
            continue
        m[rank], m[piv] = m[piv], m[rank]
        for r in range(rows):
            if r != rank and m[r][c]:
                m[r] = [a ^ b for a, b in zip(m[r], m[rank])]
        rank += 1
    return rank


def test_gf2_rank_matches_bruteforce():
    rng = np.random.default_rng(5)
    mats = rng.integers(0, 2, (200, 8, 8))
    mats[:20, 3] = mats[:20, 1]  # force some rank deficiency
    rows = (mats * (1 << np.arange(7, -1, -1))).sum(axis=2)
    got = nist.gf2_rank(rows, 8)
    expect = [brute_rank(m.tolist()) for m in mats]
    assert got.tolist() == expect


def test_rank_probabilities_32():
    full, m1, rest = nist._rank_probabilities(32, 32)
    assert close(full, 0.2888, 1e-4) and close(m1, 0.5776, 1e-4) and close(rest, 0.1336, 1e-4)


def test_battery_reference_generator_mostly_passes():
    rng = np.random.Generator(np.random.PCG64(12345))
    eps = rng.integers(0, 2, 400_000, dtype=np.uint8)
    res = nist.run_battery(eps)
    assert all(0.0 <= p <= 1.0 for p in res.values())
    assert sum(p >= 0.01 for p in res.values()) >= len(res) - 1


def test_battery_detects_bias():
    rng = np.random.Generator(np.random.PCG64(1))
    eps = (rng.random(400_000) < 0.47).astype(np.uint8)
    assert nist.frequency(eps) < 1e-6
    assert nist.runs(eps) == 0.0


def test_protocol_evaluation():
    m = 100
    good = {"T": list(np.linspace(0.005, 0.995, m))}
    out = nist.evaluate(good)["T"]
    assert out["proportion_ok"] and out["uniformity_ok"] and out["pass"]
    bad = {"T": [0.001] * 10 + [0.5] * 90}
    out = nist.evaluate(bad)["T"]
    assert not out["proportion_ok"] and not out["pass"]
    few = nist.evaluate({"T": [0.5] * 10})["T"]
    assert few["uniformity_p"] is None


def test_proportion_range_matches_sp800_22():
    lo, hi = nist.proportion_range(1000)
    assert close(lo, 0.99 - 3 * np.sqrt(0.99 * 0.01 / 1000))
    assert pytest.approx(lo, abs=1e-4) == 0.980561
