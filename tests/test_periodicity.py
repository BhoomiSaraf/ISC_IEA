import numpy as np

from isc_seq.periodicity import as_state, brent, floyd_meeting_index, make_map


def toy_map(mu, lam):
    """Functional graph 0 -> 1 -> ... -> mu+lam-1 -> mu (tail mu, cycle lam)."""
    def f(s):
        return s + 1 if s + 1 < mu + lam else mu
    return f


def test_brent_on_known_cycles():
    for mu, lam in [(0, 1), (0, 7), (5, 1), (13, 29), (1000, 3), (3, 1000)]:
        assert brent(toy_map(mu, lam), 0, max_steps=10_000) == (mu, lam)


def test_brent_respects_budget():
    assert brent(toy_map(10_000, 10_000), 0, max_steps=100) is None


def test_floyd_meeting_index_is_multiple_of_period():
    for mu, lam in [(0, 7), (13, 29), (100, 3), (2, 50)]:
        i = floyd_meeting_index(toy_map(mu, lam), 0, 100_000)
        assert i % lam == 0 and i - 1 >= mu


def test_quantised_isc_map_cycles_quickly():
    f = make_map(np.float64, quant_bits=6)
    res = brent(f, as_state(0.1, 0.1, np.float64), max_steps=200_000)
    assert res is not None
    mu, lam = res
    s = as_state(0.1, 0.1, np.float64)
    for _ in range(mu):
        s = f(s)
    t = s
    for _ in range(lam):
        t = f(t)
    assert s == t
