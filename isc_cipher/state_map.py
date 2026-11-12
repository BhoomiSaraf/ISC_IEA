"""Stage 3: seed -> ISC initial state on the 2^106-point grid (algorithm_design.md §5).

    alpha = BE64(s[0:8]) >> 11,  beta = BE64(s[8:16]) >> 11
    x0 = float(alpha) * 2^-52 - 1.0,  y0 = float(beta) * 2^-52 - 1.0
Lemma 1 (exactness) and Lemma 2 (uniform 2^22-to-1) are tested in tests/test_isc_cipher_kdf_state.py.
"""

TWO_M52 = 2.0 ** -52       # exact power of two


def seed_to_ints(seed):
    if len(seed) != 16:
        raise ValueError("seed must be 16 bytes")
    return int.from_bytes(seed[0:8], "big") >> 11, int.from_bytes(seed[8:16], "big") >> 11


def int_to_coord(m):
    return float(m) * TWO_M52 - 1.0


def seed_to_state(seed):
    a, b = seed_to_ints(seed)
    return int_to_coord(a), int_to_coord(b)
