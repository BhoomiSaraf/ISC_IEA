"""Stage 5b: unbiased bounded integers, S-box and permutation (algorithm_design.md §8.2-8.4).

Words are BE32 of the next 4 stream bytes, consumed strictly in order. WordSource prefetches
exactly 4 bytes per planned draw and fetches further words only when a rejection occurs, so the
stream's consumption equals 4 x (draws + rejections), as specified.
"""

TWO32 = 1 << 32


class WordSource:
    def __init__(self, stream, planned_draws):
        self._stream = stream
        self._buf = stream.take(4 * planned_draws) if planned_draws > 0 else b""
        self._pos = 0
        self.words_used = 0

    def next_word(self):
        if self._pos + 4 > len(self._buf):
            self._buf = self._buf[self._pos:] + self._stream.take(4)
            self._pos = 0
        w = int.from_bytes(self._buf[self._pos:self._pos + 4], "big")
        self._pos += 4
        self.words_used += 1
        return w


def bounded(src, s):
    """Lemire's method: uniform integer in [0, s) for 1 <= s <= 2^32 (algorithm_design.md §8.2)."""
    if not 1 <= s <= TWO32:
        raise ValueError("bound out of range")
    m = src.next_word() * s
    lo = m % TWO32
    if lo < s:
        t = (TWO32 - s) % s
        while lo < t:
            m = src.next_word() * s
            lo = m % TWO32
    return m >> 32


def build_sbox(stream):
    """S = Fisher-Yates over [0..255] with j = Bounded(sbox, i + 1), i = 255..1. Returns (S, S_inv)."""
    src = WordSource(stream, 255)
    s = list(range(256))
    for i in range(255, 0, -1):
        j = bounded(src, i + 1)
        s[i], s[j] = s[j], s[i]
    inv = [0] * 256
    for v in range(256):
        inv[s[v]] = v
    return s, inv


def build_permutation(stream, n):
    """pi = Fisher-Yates over [0..n-1] with j = Bounded(perm, i + 1), i = n-1..1 (gather convention)."""
    src = WordSource(stream, n - 1)
    pi = list(range(n))
    for i in range(n - 1, 0, -1):
        j = bounded(src, i + 1)
        pi[i], pi[j] = pi[j], pi[i]
    return pi


def apply_permutation(p, pi):
    """q_k = p[pi[k]]."""
    return bytes(p[i] for i in pi)


def invert_permutation(q, pi):
    """p[pi[k]] = q_k."""
    p = bytearray(len(q))
    for k, i in enumerate(pi):
        p[i] = q[k]
    return bytes(p)
