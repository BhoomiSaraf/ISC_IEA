"""A2 (forgery and tampering) and A13 (parser robustness, generator-before-authentication instrumentation)."""

import os

import numpy as np

import isc_cipher
from isc_cipher import ISCError, cipher
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY

from .common import Run, public_key, public_nonce
from .constructions import seal, unseal


def _decrypt_fn(variant, key):
    if variant == "V-FULL":
        return lambda z: isc_cipher.decrypt_bytes(key, z)[0]
    return lambda z: unseal(variant, key, z)


def _make(variant, key, nonce, data, h, w, c):
    if variant == "V-FULL":
        return encrypt_bytes_with_nonce_TEST_ONLY(key, data, h, w, c, nonce)
    return seal(variant, key, nonce, data, h, w, c)


def a2(mode):
    big = (512, 512, 3) if mode == "full" else (16, 16, 3)
    cfg = {"small": [4, 6, 3], "large": list(big), "random_flips_large": 10000 if mode == "full" else 200,
           "wrong_keys": 1000 if mode == "full" else 20, "constructions": ["V-FULL", "V-CHACHA"]}
    run = Run("A2_tamper", mode, cfg)
    rng = np.random.default_rng(2)
    rows = []
    for variant in cfg["constructions"]:
        key = public_key("A2/" + variant)
        dec = _decrypt_fn(variant, key)
        small = bytes(rng.integers(0, 256, 72, dtype=np.uint8))
        z = _make(variant, key, public_nonce("A2/a/" + variant), small, 4, 6, 3)
        other = _make(variant, key, public_nonce("A2/b/" + variant), small, 4, 6, 3)
        hb, wb, cb = big
        zl = _make(variant, key, public_nonce("A2/c/" + variant), bytes(rng.integers(0, 256, hb * wb * cb, dtype=np.uint8)), hb, wb, cb)
        assert dec(z) == small
        counts = {}
        originals = {z, zl}

        def attempt(case, blob, dec=dec):
            r = counts.setdefault(case, {"attempts": 0, "accepted": 0, "exceptions": {}, "noop_unchanged_skipped": 0})
            if bytes(blob) in originals:          # e.g. swapping two identical fields: not a modification
                r["noop_unchanged_skipped"] += 1
                return
            r["attempts"] += 1
            try:
                dec(bytes(blob))
                r["accepted"] += 1
            except ISCError as e:
                r["exceptions"][type(e).__name__] = r["exceptions"].get(type(e).__name__, 0) + 1
        for i in range(len(z)):
            for b in range(8):
                t = bytearray(z)
                t[i] ^= 1 << b
                attempt("every_bit_flip_small", t)
        for _ in range(cfg["random_flips_large"]):
            t = bytearray(zl)
            t[int(rng.integers(len(zl)))] ^= 1 << int(rng.integers(8))
            attempt("random_bit_flip_large", t)
        for k in range(1, 65):
            attempt("truncate", z[:-k])
            attempt("extend", z + bytes(k))
        for lo, hi in ((12, 28), (28, 36), (len(z) - 32, len(z))):
            attempt("swap_nonce_kcv_tag", z[:lo] + other[lo:hi] + z[hi:])
        for h, w, c in ((6, 4, 3), (1, 72, 1), (72, 1, 1), (8, 9, 1), (3, 8, 3)):
            t = bytearray(z)
            t[7] = c
            t[8:10] = h.to_bytes(2, "big")
            t[10:12] = w.to_bytes(2, "big")
            attempt("relabel_dims_same_n", t)
        t = bytearray(z)
        t[5] = 2
        attempt("profile_change", t)
        for _ in range(cfg["wrong_keys"]):
            dk = _decrypt_fn(variant, os.urandom(32))
            r = counts.setdefault("wrong_key", {"attempts": 0, "accepted": 0, "exceptions": {}})
            r["attempts"] += 1
            try:
                dk(z)
                r["accepted"] += 1
            except ISCError as e:
                r["exceptions"][type(e).__name__] = r["exceptions"].get(type(e).__name__, 0) + 1
        accepted = sum(v["accepted"] for v in counts.values())
        rows.append({"construction": variant, "cases": counts, "total_attempts": sum(v["attempts"] for v in counts.values()),
                     "accepted": accepted, "attack_succeeded": accepted > 0})
        run.log(f"{variant}: attempts {rows[-1]['total_attempts']}, accepted {accepted}")
    return run.finish({"results": rows, "criterion": "attack succeeds if any modified ciphertext or wrong key is accepted"})


def a13(mode):
    cfg = {"random_blobs": 100000 if mode == "full" else 1000, "mutations": 100000 if mode == "full" else 1000}
    run = Run("A13_parser", mode, cfg)
    rng = np.random.default_rng(13)
    key = public_key("A13")
    z = encrypt_bytes_with_nonce_TEST_ONLY(key, bytes(48), 4, 4, 3, public_nonce("A13"))
    calls = {"generator": 0}
    real = cipher._build_generators

    def spy(*a, **k):
        calls["generator"] += 1
        return real(*a, **k)
    cipher._build_generators = spy
    outcomes = {}
    undocumented = []
    try:
        for i in range(cfg["random_blobs"] + cfg["mutations"]):
            if i < cfg["random_blobs"]:
                blob = bytes(rng.integers(0, 256, int(rng.integers(0, 200)), dtype=np.uint8))
                if rng.random() < 0.5 and len(blob) >= 12:
                    blob = b"ISCI" + bytes([1, int(rng.integers(1, 3)), 1, int(rng.choice([1, 3]))]) + blob[8:]
            else:
                t = bytearray(z)
                for _ in range(int(rng.integers(1, 6))):
                    op = rng.integers(3)
                    if op == 0 and len(t):
                        t[int(rng.integers(len(t)))] = int(rng.integers(256))
                    elif op == 1 and len(t):
                        del t[int(rng.integers(len(t)))]
                    else:
                        t.insert(int(rng.integers(len(t) + 1)), int(rng.integers(256)))
                blob = bytes(t)
            try:
                isc_cipher.decrypt_bytes(key, blob)
                name = "ACCEPTED" if blob != z else "accepted_unmodified"
            except ISCError as e:
                name = type(e).__name__
            except Exception as e:  # undocumented exception type = finding
                name = "UNDOCUMENTED:" + type(e).__name__
                undocumented.append(repr(e)[:200])
            outcomes[name] = outcomes.get(name, 0) + 1
    finally:
        cipher._build_generators = real
    accepted_modified = outcomes.get("ACCEPTED", 0)
    return run.finish({"outcomes": outcomes, "generator_calls": calls["generator"],
                       "generator_calls_equal_accepted": calls["generator"] == outcomes.get("accepted_unmodified", 0) + accepted_modified,
                       "undocumented_exceptions": undocumented[:20],
                       "finding": bool(undocumented) or accepted_modified > 0 or calls["generator"] > outcomes.get("accepted_unmodified", 0)})
