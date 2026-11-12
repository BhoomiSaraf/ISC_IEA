"""A1 (nonce reuse, findings F1-F5), A8 (permutation recovery on V-FULL), A9 (nonce-respecting F1', F5').

Attacker code uses ONLY oracle answers; ground truth (materials) is used only for scoring.
"""

import os
import time

import numpy as np

from .common import Run, public_key, public_nonce
from .constructions import AEADS, FixedNonceOracle, aead_seal, seal

H, W, C = 64, 64, 1
N_EL = H * W * C


def rand_img(rng, n=N_EL):
    return bytes(rng.integers(0, 256, n, dtype=np.uint8))


def camera_crop():
    from skimage import data
    return bytes(np.ascontiguousarray(data.camera()[200:200 + H, 200:200 + W]).tobytes())


def frac_equal(a, b):
    a = np.frombuffer(bytes(a), np.uint8)
    b = np.frombuffer(bytes(b), np.uint8)
    return float(np.mean(a == b))


# ----------------------------------------------------------------- attacker procedures (oracle only)
def attack_position_coding(enc, n, decode_q=None):
    """Recover pi from ceil(log256 n) position-coded images. decode_q maps a body to q (identity for V-PERM)."""
    digits = 1
    while 256 ** digits < n:
        digits += 1
    idx = np.arange(n)
    pos = np.zeros(n, dtype=np.int64)
    for d in range(digits):
        img = ((idx >> (8 * d)) & 0xFF).astype(np.uint8).tobytes()
        q = enc(img)
        if decode_q:
            q = decode_q(q)
        pos += np.frombuffer(q, np.uint8).astype(np.int64) << (8 * d)
    return pos.tolist(), digits


def linear_q_from_body(c, c0):
    """V-LINEAR structure (S = identity, key-independent): q = second difference of (c - c0) mod 256."""
    dc = (np.frombuffer(c, np.uint8).astype(np.int64) - np.frombuffer(c0, np.uint8).astype(np.int64)) % 256
    du = (dc - np.append(dc[1:], 0)) % 256
    dq = (du - np.insert(du[:-1], 0, 0)) % 256
    return dq.astype(np.uint8).tobytes()


def scatter(q, pi_hat):
    p = bytearray(len(q))
    for k, j in enumerate(pi_hat):
        if 0 <= j < len(q):
            p[j] = q[k]
    return bytes(p)


def build_attack(variant, oracle_enc, n):
    """Returns (pi_hat or None, D_hat or None, queries_used, notes). Pre-registered methods only."""
    q0 = [0]

    def enc(p):
        q0[0] += 1
        return oracle_enc(p)
    if variant == "V-STREAM" or variant in ("AES-256-GCM", "ChaCha20-Poly1305"):
        zero = bytes(n)
        ks = enc(zero)                                   # c XOR p with p = 0
        return None, (lambda c: bytes(a ^ b for a, b in zip(c, ks))), q0[0], "keystream from one known pair"
    if variant == "V-PERM":
        pi_hat, _ = attack_position_coding(enc, n)
        return pi_hat, (lambda c: scatter(c, pi_hat)), q0[0], "position coding"
    if variant in ("V-LINEAR", "V-FULL", "V-CHACHA"):
        # the V-LINEAR method; for V-FULL / V-CHACHA it is an (exploratory) transfer attempt
        c0 = enc(bytes(n))
        pi_hat, _ = attack_position_coding(enc, n, decode_q=lambda c: linear_q_from_body(c, c0))
        return pi_hat, (lambda c: scatter(linear_q_from_body(c, c0), pi_hat)), q0[0], \
            "zero image + key-independent linear inversion + position coding"
    return None, None, 0, "no pre-registered method"


def codebook_attack(oracle_enc, n):
    """Exploratory: full codebook for n = 1 (256 queries)."""
    assert n == 1
    table = {oracle_enc(bytes([v])): bytes([v]) for v in range(256)}
    return (lambda c: table.get(bytes(c), b"\x00")), 256


# ----------------------------------------------------------------- A1
def a1(mode):
    cfg = {"dims": [H, W, C], "trials_F1": 10 if mode == "full" else 2, "pairs_F2": 10 if mode == "full" else 2,
           "heldout_F4": 20 if mode == "full" else 3, "threshold": 0.99,
           "exploratory_cap_seconds": 8 * 3600 if mode == "full" else 120}
    run = Run("A1_misuse", mode, cfg)
    rng = np.random.default_rng(1)
    key, nonce = public_key("A1"), public_nonce("A1")
    nonce12 = public_nonce("A1/aead", 12)
    cam = camera_crop()
    rows = []
    for name in ("V-STREAM", "V-PERM", "V-LINEAR", "V-FULL", "V-CHACHA") + AEADS:
        t0 = time.time()
        if name in AEADS:
            def enc(p, name=name):
                return aead_seal(name, key, p, H, W, C, nonce12)[12:-16]
            truth_pi = None
        else:
            orc = FixedNonceOracle(name, key, nonce, H, W, C)
            enc = orc.encrypt
            truth_pi = orc.m["pi"]
        row = {"construction": name, "kind": "AEAD baseline" if name in AEADS else
               ("controlled comparison" if name == "V-CHACHA" else "experimental"),
               "setting": "nonce reuse (fixed K, N, dims)"}
        p = rand_img(rng)
        row["F1_equality"] = all(enc(p) == enc(p) for _ in range(cfg["trials_F1"]))
        f2 = []
        for _ in range(cfg["pairs_F2"]):
            p1, p2 = rand_img(rng), rand_img(rng)
            c1, c2 = enc(p1), enc(p2)
            f2.append(frac_equal(bytes(a ^ b for a, b in zip(c1, c2)), bytes(a ^ b for a, b in zip(p1, p2))))
        row["F2_xor_min_fraction"] = min(f2)
        row["F2_xor_leak"] = min(f2) >= cfg["threshold"]
        pi_hat, D, q_used, method = build_attack(name, enc, N_EL)
        row["method"] = method
        row["queries"] = q_used
        row["pre_registered"] = name not in ("V-FULL", "V-CHACHA")
        if pi_hat is not None and truth_pi is not None:
            row["F3_pi_fraction_correct"] = float(np.mean(np.array(pi_hat) == np.array(truth_pi)))
            row["F3_permutation_recovered"] = row["F3_pi_fraction_correct"] >= cfg["threshold"]
        if D is not None:
            f4 = [frac_equal(D(enc(h)), h) for h in (rand_img(rng) for _ in range(cfg["heldout_F4"]))]
            row["F4_min_fraction"] = min(f4)
            row["F4_equivalent_key"] = min(f4) >= cfg["threshold"]
            row["F5_fraction"] = frac_equal(D(enc(cam)), cam)
            row["F5_decrypts_other_ciphertext"] = row["F5_fraction"] >= cfg["threshold"]
        else:
            row["F4_equivalent_key"] = row["F5_decrypts_other_ciphertext"] = "not applicable (no method)"
        row["seconds"] = round(time.time() - t0, 2)
        run.log(f"{name}: {row}")
        rows.append(row)
    # exploratory: codebook for n = 1 on V-FULL and V-CHACHA
    explo = []
    for name in ("V-FULL", "V-CHACHA"):
        orc = FixedNonceOracle(name, key, nonce, 1, 1, 1)
        D, q = codebook_attack(orc.encrypt, 1)
        ok = all(D(orc.encrypt(bytes([v]))) == bytes([v]) for v in range(256))
        explo.append({"construction": name, "attack": "codebook, n = 1 (exploratory)", "queries": q,
                      "F4_F5_full_recovery_for_n1": ok})
    run.write_json("raw/findings.json", {"nonce_reuse": rows, "exploratory": explo})
    return run.finish({"nonce_reuse_findings": rows, "exploratory": explo,
                       "note": "Nonce-misuse model only. Each finding is judged by its own criterion (gate_a_plan.md §2.1)."})


# ----------------------------------------------------------------- A8
def a8(mode):
    run = Run("A8_perm", mode, {"dims": [H, W, C], "construction": "V-FULL", "nonce": "fixed"})
    orc = FixedNonceOracle("V-FULL", public_key("A8"), public_nonce("A8"), H, W, C)
    pi_hat, digits = attack_position_coding(orc.encrypt, N_EL)
    frac = float(np.mean(np.array(pi_hat) == np.array(orc.m["pi"])))
    return run.finish({"queries": digits, "pi_fraction_correct": frac, "permutation_recovered": frac >= 0.99,
                       "chance_level": 1 / N_EL})


# ----------------------------------------------------------------- A9
def a9(mode):
    cfg = {"dims": [H, W, C], "fresh_nonce_trials": 10 if mode == "full" else 3, "transfer_images": 20 if mode == "full" else 3}
    run = Run("A9_nonce_respecting", mode, cfg)
    rng = np.random.default_rng(9)
    key = public_key("A9")
    rows = []
    for name in ("V-STREAM", "V-PERM", "V-LINEAR", "V-FULL", "V-CHACHA") + AEADS:
        p = rand_img(rng)
        if name in AEADS:
            bodies = [aead_seal(name, key, p, H, W, C, os.urandom(12))[12:-16] for _ in range(cfg["fresh_nonce_trials"])]
        else:
            bodies = [seal(name, key, os.urandom(16), p, H, W, C)[36:-32] for _ in range(cfg["fresh_nonce_trials"])]
        row = {"construction": name, "setting": "nonce-respecting (fresh random nonces)",
               "F1prime_equal_bodies": len(set(bodies)) < len(bodies)}
        # equivalent key from N1 (pre-registered methods), applied under N2
        if name in AEADS:
            n1 = public_nonce("A9/n1/" + name, 12)

            def enc1(x, name=name, n1=n1):
                return aead_seal(name, key, x, H, W, C, n1)[12:-16]
        else:
            orc = FixedNonceOracle(name, key, public_nonce("A9/n1/" + name), H, W, C)
            enc1 = orc.encrypt
        _, D, _, method = build_attack(name, enc1, N_EL)
        if D is None:
            row["F5prime"] = "not applicable (no equivalent key)"
        else:
            agree = []
            for _ in range(cfg["transfer_images"]):
                x = rand_img(rng)
                if name in AEADS:
                    c2 = aead_seal(name, key, x, H, W, C, os.urandom(12))[12:-16]
                else:
                    c2 = seal(name, key, os.urandom(16), x, H, W, C)[36:-32]
                agree.append(frac_equal(D(c2), x))
            m = float(np.mean(agree))
            sigma = np.sqrt((1 / 256) * (255 / 256) / (N_EL * len(agree)))
            row.update({"F5prime_mean_agreement": m, "threshold": 1 / 256 + 3 * sigma,
                        "F5prime_transfer_success": m > 1 / 256 + 3 * sigma, "method": method})
        run.log(f"{name}: {row}")
        rows.append(row)
    return run.finish({"nonce_respecting_findings": rows})
