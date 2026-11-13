"""Unit and Invertibility Tests for Diffusion Candidates (Original, A, B, C)."""

import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("experiments/diffusion_study"))

from original.diffusion import encrypt as orig_encrypt, decrypt as orig_decrypt
from candidate_a.diffusion import encrypt as ca_encrypt, decrypt as ca_decrypt
from candidate_b.diffusion import encrypt as cb_encrypt, decrypt as cb_decrypt
from candidate_c.diffusion import encrypt as cc_encrypt, decrypt as cc_decrypt


class TestDiffusionCandidates(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.RandomState(1337)
        self.S = list(range(256))
        self.rng.shuffle(self.S)
        self.S_inv = [0] * 256
        for i, v in enumerate(self.S):
            self.S_inv[v] = i

        self.iv_f = 0x37
        self.iv_b = 0x89
        self.iv_f4 = [0x11, 0x22, 0x33, 0x44]
        self.iv_b4 = [0x55, 0x66, 0x77, 0x88]

    def test_original_invertibility(self):
        for n in [1, 4, 16, 64, 256, 1024]:
            q = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            a = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            b = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            c = orig_encrypt(q, a, b, self.S, self.iv_f, self.iv_b)
            rec_ref = orig_decrypt(c, a, b, self.S_inv, self.iv_f, self.iv_b, backend="reference")
            rec_np = orig_decrypt(c, a, b, self.S_inv, self.iv_f, self.iv_b, backend="numpy")
            self.assertEqual(q, rec_ref, f"Original ref failed at n={n}")
            self.assertEqual(q, rec_np, f"Original numpy failed at n={n}")

    def test_candidate_a_invertibility(self):
        for rounds in [1, 2, 4]:
            for n in [1, 4, 16, 64, 256, 1024]:
                q = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
                a = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
                b = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
                c = ca_encrypt(q, a, b, self.S, self.iv_f, self.iv_b, rounds=rounds)
                rec = ca_decrypt(c, a, b, self.S_inv, self.iv_f, self.iv_b, rounds=rounds)
                self.assertEqual(q, rec, f"Candidate A failed at n={n}, rounds={rounds}")

    def test_candidate_b_invertibility(self):
        for n in [1, 4, 16, 64, 256, 1024]:
            q = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            a = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            b = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            d = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            e = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
            c = cb_encrypt(q, a, b, d, e, self.S, (self.iv_f, 0x42), (self.iv_b, 0x99))
            rec = cb_decrypt(c, a, b, d, e, self.S, self.S_inv, (self.iv_f, 0x42), (self.iv_b, 0x99))
            self.assertEqual(q, rec, f"Candidate B failed at n={n}")

    def test_candidate_c_invertibility(self):
        for rounds in [2, 4, 6]:
            for n in [4, 16, 64, 256, 1024]:
                q = bytes(self.rng.randint(0, 256, n, dtype=np.uint8))
                a = bytes(self.rng.randint(0, 256, n * rounds, dtype=np.uint8))
                b = bytes(self.rng.randint(0, 256, n * rounds, dtype=np.uint8))
                c = cc_encrypt(q, a, b, self.S, self.iv_f4, self.iv_b4, rounds=rounds)
                rec = cc_decrypt(c, a, b, self.S, self.iv_f4, self.iv_b4, rounds=rounds)
                self.assertEqual(q, rec, f"Candidate C failed at n={n}, rounds={rounds}")


if __name__ == "__main__":
    unittest.main()

