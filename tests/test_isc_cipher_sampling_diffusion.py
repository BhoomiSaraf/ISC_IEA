"""Gate C, stages 5b-6: bounded integers, S-box, permutation, diffusion and inverses (component level)."""

import random

import pytest

from isc_cipher import diffusion, sampling

TWO32 = 1 << 32


class WordStream:
    """Fake stream returning given 32-bit words (big-endian), counting consumption."""

    def __init__(self, words):
        self.data = b"".join(w.to_bytes(4, "big") for w in words)
        self.pos = 0

    def take(self, m):
        out = self.data[self.pos:self.pos + m]
        if len(out) != m:
            raise AssertionError("fake stream exhausted")
        self.pos += m
        return out


# ---------------------------------------------------------------- bounded integers (Lemire)
@pytest.mark.parametrize("s", [1, 2, 3, 5, 7, 255, 256, 1000, 2 ** 31 - 1, 2 ** 31, 2 ** 31 + 1, 2 ** 32 - 1, 2 ** 32])
def test_bounded_accepted_value_is_floor_ws(s):
    rng = random.Random(s)
    t = (TWO32 - s) % s
    for _ in range(2000):
        w = rng.randrange(TWO32)
        if (w * s) % TWO32 < t:
            continue
        src = sampling.WordSource(WordStream([w]), 1)
        assert sampling.bounded(src, s) == (w * s) >> 32 < s


def test_bounded_rejection_draws_next_word():
    # s = 3: t = (2^32 - 3) mod 3 = 1; w = 0 gives l = 0 < t -> rejected; next word used
    src = sampling.WordSource(WordStream([0, 0x80000000]), 1)
    assert sampling.bounded(src, 3) == 1 and src.words_used == 2


def test_bounded_rejects_out_of_range_bound():
    src = sampling.WordSource(WordStream([1, 2]), 1)
    for s in (0, TWO32 + 1):
        with pytest.raises(ValueError):
            sampling.bounded(src, s)


def accepted_count(s, v):
    """Number of 32-bit words w accepted by Lemire with floor(w*s/2^32) == v (exact arithmetic)."""
    t = (TWO32 - s) % s
    lo = -(-v * TWO32 // s)                       # ceil(v*2^32/s)
    hi = -(-(v + 1) * TWO32 // s)                 # ceil((v+1)*2^32/s)
    # l = w*s - v*2^32 for w in [lo, hi); accepted iff l >= t  <=>  w >= ceil((t + v*2^32)/s)
    first_ok = max(lo, -(-(t + v * TWO32) // s))
    return max(0, hi - first_ok)


@pytest.mark.parametrize("s", [1, 2, 3, 5, 6, 7, 100, 255, 256, 257, 1000, 4093])
def test_bounded_is_exactly_uniform(s):
    counts = {accepted_count(s, v) for v in range(s)}
    assert len(counts) == 1                       # every output value has the same number of accepted words


# ---------------------------------------------------------------- S-box
def ref_fisher_yates(words, n):
    """Independent re-implementation used only to compute expectations from crafted words."""
    it = iter(words)
    a = list(range(n))
    for i in range(n - 1, 0, -1):
        s = i + 1
        while True:
            w = next(it)
            m = w * s
            if (m % TWO32) >= (TWO32 - s) % s:
                break
        j = m >> 32
        a[i], a[j] = a[j], a[i]
    return a


def test_sbox_all_ones_words_gives_identity():
    S, Si = sampling.build_sbox(WordStream([0xFFFFFFFF] * 255))
    assert S == list(range(256)) and Si == list(range(256))


def test_sbox_matches_independent_fisher_yates_and_is_bijective():
    rng = random.Random(9)
    words = [rng.randrange(TWO32) for _ in range(400)]
    stream = WordStream(words)
    S, Si = sampling.build_sbox(stream)
    assert S == ref_fisher_yates(words, 256)
    assert sorted(S) == list(range(256)) and all(Si[S[v]] == v for v in range(256))
    assert stream.pos % 4 == 0 and stream.pos >= 4 * 255


def test_sbox_consumes_extra_word_on_rejection():
    # first draw is for i = 255, s = 256: t = 0, never rejects; force a rejection at s = 3 (i = 2)
    words = [0xFFFFFFFF] * 253 + [0, 0x80000000, 0x80000000]     # i=255..3 accept; i=2 rejects 0 then uses 0x80000000
    stream = WordStream(words + [0xFFFFFFFF])
    S, _ = sampling.build_sbox(stream)
    assert stream.pos == 4 * 256 and S == ref_fisher_yates(words + [0xFFFFFFFF], 256)


# ---------------------------------------------------------------- permutation
def test_permutation_spec_example():
    assert sampling.build_permutation(WordStream([0x80000000, 0xC0000000]), 3) == [0, 2, 1]


def test_permutation_n1_consumes_nothing():
    st = WordStream([])
    assert sampling.build_permutation(st, 1) == [0] and st.pos == 0


@pytest.mark.parametrize("n", [2, 3, 17, 256, 1000])
def test_permutation_bijective_and_matches_reference(n):
    rng = random.Random(n)
    words = [rng.randrange(TWO32) for _ in range(n + 50)]
    pi = sampling.build_permutation(WordStream(words), n)
    assert sorted(pi) == list(range(n)) and pi == ref_fisher_yates(words, n)


def test_gather_and_scatter_are_inverse():
    rng = random.Random(1)
    for n in (1, 2, 5, 300):
        pi = list(range(n))
        rng.shuffle(pi)
        p = bytes(rng.randrange(256) for _ in range(n))
        q = sampling.apply_permutation(p, pi)
        assert all(q[k] == p[pi[k]] for k in range(n))
        assert sampling.invert_permutation(q, pi) == p


# ---------------------------------------------------------------- diffusion
TOY_S = [(5 * v + 3) % 256 for v in range(256)]
TOY_SI = [(205 * (w - 3)) % 256 for w in range(256)]


def test_spec_example_forward_backward_and_inverses():
    q = bytes([10, 30, 20])
    a, b = bytes([1, 2, 3]), bytes([4, 5, 6])
    u = diffusion.forward(q, a, TOY_S, 7)
    c = diffusion.backward(u, b, TOY_S, 9)
    assert list(u) == [93, 116, 186] and list(c) == [56, 16, 240]
    assert diffusion.inverse_ref(c, a, b, TOY_SI, 7, 9) == q
    assert diffusion.inverse_np(c, a, b, TOY_SI, 7, 9) == q


def random_sbox(rng):
    S = list(range(256))
    rng.shuffle(S)
    Si = [0] * 256
    for v in range(256):
        Si[S[v]] = v
    return S, Si


@pytest.mark.parametrize("n", [1, 2, 3, 64, 1000, 4097])
def test_diffusion_inverse_random_and_extreme_inputs(n):
    rng = random.Random(n)
    S, Si = random_sbox(rng)
    for q in (bytes(n), bytes([255]) * n, bytes(rng.randrange(256) for _ in range(n))):
        a = bytes(rng.randrange(256) for _ in range(n))
        b = bytes(rng.randrange(256) for _ in range(n))
        for ivf, ivb in ((0, 0), (255, 255), (rng.randrange(256), rng.randrange(256))):
            c = diffusion.backward(diffusion.forward(q, a, S, ivf), b, S, ivb)
            assert diffusion.inverse_ref(c, a, b, Si, ivf, ivb) == q
            assert diffusion.inverse_np(c, a, b, Si, ivf, ivb) == q


def test_forward_recurrence_definition_independently():
    rng = random.Random(2)
    S, _ = random_sbox(rng)
    q = [rng.randrange(256) for _ in range(50)]
    a = [rng.randrange(256) for _ in range(50)]
    u = diffusion.forward(bytes(q), bytes(a), S, 77)
    prev = 77
    for k in range(50):
        prev = S[(q[k] + prev + a[k]) % 256]
        assert u[k] == prev
    b = [rng.randrange(256) for _ in range(50)]
    c = diffusion.backward(u, bytes(b), S, 11)
    nxt = 11
    for k in range(49, -1, -1):
        nxt = S[(u[k] + nxt + b[k]) % 256]
        assert c[k] == nxt
