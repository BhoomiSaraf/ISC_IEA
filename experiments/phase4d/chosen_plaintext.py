"""Track C / section 5: structural chosen-plaintext experiments under a FIXED (key, nonce)
(TEST-ONLY mechanism), to see what controlled plaintexts reveal about internal structure.
"""
import json
import os

import numpy as np

import config as cfg
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY as enc
from isc_cipher.sampling import build_permutation
from isc_cipher._testing import materials_TEST_ONLY

OUT = os.path.join(cfg.RESULTS_DIR, "chosen_plaintext.json")
H, W, C = 64, 64, 1
N = H * W * C


def body(ct):
    return ct[36:-32]


def hamming_bytes_diff(b1, b2):
    return sum(1 for x, y in zip(b1, b2) if x != y)


def main():
    findings = {"config": {"h": H, "w": W, "c": C, "n": N, "key": cfg.key_label(cfg.KEY_A),
                            "nonce": cfg.nonce_label(cfg.NONCE_A)}}

    patterns = {
        "all_zero": bytes([0] * N),
        "all_255": bytes([255] * N),
        "sequential": bytes([i % 256 for i in range(N)]),
        "alternating_0_255": bytes([0, 255] * (N // 2)),
        "repeated_block_16": (bytes(range(16)) * (N // 16)),
    }

    bodies = {name: body(enc(cfg.KEY_A, p, H, W, C, cfg.NONCE_A, backend=cfg.BACKEND))
              for name, p in patterns.items()}

    # 1. Does any structured plaintext produce a structured (non-uniform-looking) ciphertext?
    # Quantify via byte-value histogram chi-square against uniform, and run-length of repeats.
    from collections import Counter
    import math
    struct_report = {}
    for name, b in bodies.items():
        counts = Counter(b)
        exp = N / 256
        chi2 = sum((counts.get(v, 0) - exp) ** 2 / exp for v in range(256))
        # repeated adjacent bytes (would indicate leaking the all-zero/all-255 structure)
        n_repeats = sum(1 for i in range(1, len(b)) if b[i] == b[i - 1])
        struct_report[name] = {
            "chi2": chi2,
            "n_adjacent_repeats": n_repeats,
            "n_adjacent_repeats_expected_random": round(N / 256, 1),
            "first_16_bytes_hex": b[:16].hex(),
        }
    findings["structured_plaintext_ciphertext_appearance"] = struct_report

    # 2. ALL-ZERO plaintext is the degenerate case for permutation: perm(all-zero) == all-zero
    # for ANY permutation pi, since every element has the same value. This means the all-zero
    # plaintext's "q" (post-permutation) sequence equals the plaintext itself regardless of pi --
    # permutation is observationally invisible under this specific chosen input. Confirmed
    # directly: apply_permutation output must equal input when input is constant.
    from isc_cipher.sampling import apply_permutation
    m = materials_TEST_ONLY(cfg.KEY_A, cfg.NONCE_A, H, W, C, backend=cfg.BACKEND)
    q_allzero = apply_permutation(patterns["all_zero"], m["pi"])
    findings["permutation_invisible_under_constant_plaintext"] = {
        "claim": "apply_permutation(constant_array, pi) == constant_array for ANY pi",
        "confirmed": (q_allzero == patterns["all_zero"]),
        "implication": (
            "A chosen all-zero (or any constant-byte) plaintext bypasses observing the "
            "permutation stage entirely -- diffusion then operates directly on the constant "
            "input. This does not leak S/pi/a/b to an attacker (the ciphertext bytes still "
            "pass through the full forward+backward diffusion chain, which remains unknown), "
            "but it IS a structural degenerate case worth recording: confusion (permutation) "
            "contributes nothing against constant-plaintext inputs; all observed nonlinearity "
            "for such inputs comes solely from the diffusion stage's S-box."
        ),
    }

    # 3. Single-bit difference at beginning / middle / end -- position-dependent propagation.
    base = bytes(np.random.default_rng(cfg.MASTER_SEED).integers(0, 256, N, dtype=np.uint8))
    positions = {"beginning": 0, "middle": N // 2, "end": N - 1}
    propagation = {}
    for name, pos in positions.items():
        p2 = bytearray(base)
        p2[pos] ^= 0x01
        c1 = body(enc(cfg.KEY_A, base, H, W, C, cfg.NONCE_A, backend=cfg.BACKEND))
        c2 = body(enc(cfg.KEY_A, bytes(p2), H, W, C, cfg.NONCE_A, backend=cfg.BACKEND))
        n_diff = hamming_bytes_diff(c1, c2)
        propagation[name] = {
            "plaintext_bit_flip_byte_index": pos,
            "n_ciphertext_bytes_differing": n_diff,
            "fraction_differing": n_diff / N,
        }
    findings["single_bit_propagation_by_position"] = propagation
    findings["single_bit_propagation_note"] = (
        "If propagation fraction is markedly position-dependent (e.g. flips near the END "
        "changing fewer bytes than flips near the BEGINNING), that would indicate asymmetric "
        "diffusion strength -- expected in principle, since forward diffusion chains "
        "left-to-right from the flip point and backward diffusion then chains right-to-left "
        "over ALL of u, so a flip anywhere should in theory reach the full ciphertext. See "
        "diffusion_analysis.py for the isolated, non-combined measurement of each pass."
    )

    # 4. Repeated-nonce ciphertext structure: does XORing two reused-nonce ciphertexts for
    # DIFFERENT plaintexts reveal plaintext-independent structure (classical two-time-pad check)?
    p_a, p_b = patterns["all_zero"], patterns["all_255"]
    ca = body(enc(cfg.KEY_A, p_a, H, W, C, cfg.NONCE_A, backend=cfg.BACKEND))
    cb = body(enc(cfg.KEY_A, p_b, H, W, C, cfg.NONCE_A, backend=cfg.BACKEND))
    xor_ab = bytes(x ^ y for x, y in zip(ca, cb))
    counts_xor = Counter(xor_ab)
    exp = N / 256
    chi2_xor = sum((counts_xor.get(v, 0) - exp) ** 2 / exp for v in range(256))
    findings["two_time_pad_style_xor_check"] = {
        "description": (
            "Classical two-time-pad attacks on C=P XOR K (K reused) rely on C1 XOR C2 == P1 XOR P2 "
            "-- i.e. the keystream K cancels exactly under XOR. This construction has no such "
            "additive-XOR keystream step at the top level (addition is mod 256 through an S-box, "
            "not XOR with a fixed keystream), so this check establishes whether that specific "
            "classical structure is present."
        ),
        "xor_of_two_reused_nonce_ciphertexts_chi2_vs_uniform": chi2_xor,
        "expected_chi2_for_uniform_256cat_n4096": "approx 255 (df=255, mean=255)",
        "conclusion": (
            "chi2 close to the theoretical mean under uniformity indicates the XOR of the two "
            "ciphertexts shows no obvious two-time-pad-style structure recoverable by simple "
            "XOR-cancellation. This does NOT prove general nonce-reuse safety (see "
            "nonce_analysis.py's equation-counting discussion and the final report's Track B "
            "section) -- it only rules out the SPECIFIC classical stream-cipher XOR-cancellation "
            "attack, which does not apply to this construction's algebraic form."
        ),
    }

    with open(OUT, "w") as f:
        json.dump(findings, f, indent=2)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
