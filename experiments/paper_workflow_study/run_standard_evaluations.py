"""Comprehensive Security Analysis Suite on the Exact MTAP (Sharma et al. 2022) Standard Dataset.
Evaluates the Enhanced ISC-IEA Architecture:
  - Frozen 2D hyperchaotic ISC map
  - SIV Plaintext-Coupled Nonce (Misuse-Resistant Authenticated Encryption)
  - 2D Inter-Round Matrix Transposition (Row-to-Column Diffusion)
  - Adaptive Fisher-Yates Permutation
  - Dynamic Galois Field Inversion S-Box (Candidate S2)
  - 2-Round Cascade

Evaluates:
  1. Table 1: Lena 512x512 Grayscale Adjacent Pixel Correlation (Horizontal, Vertical, Diagonal)
  2. Tables 2, 3, 4: USC-SIPI Grayscale Benchmark (5.1.09 - 5.1.14, 5.2.08, boat.512, lena_512_gray)
     - NPCR (Ideal: 99.6094%)
     - UACI (Ideal: 33.4635%)
     - LOCSE (Ideal: 7.902469, Critical Interval [7.901516, 7.903423])
     - Global Shannon Entropy (Ideal: 8.000000)
     - Histogram Chi-Square & p-value (Uniformity test)
  3. Figure 6: Grayscale 5.1.12 (Couple 256x256) Plain vs. Cipher and Flat Histograms
  4. Figures 7 & 8: RGB Baboon (512x512x3) Plain vs. Cipher and Separate R, G, B Histograms
  5. Figures 9 & 10: RGB Peppers (512x512x3) Key Sensitivity:
     - Plain image
     - Cipher with Key K1
     - Cipher with Key K2 (1-bit flipped: K1[0] ^ 1)
     - Difference image |C1 - C2| (and difference percentage / NPCR)
     - Decryption with correct Key K1 (exact recovery)
     - Decryption with wrong Key K2 (pure noise)
  6. Secret Key Sensitivity (NBCR across 16 key bits)
  7. Speed and Throughput Benchmark
"""

import json
import math
import os
import sys
import time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

sys.path.insert(0, os.path.abspath("."))
from experiments.paper_workflow_study.cipher_pipeline import ISCImageCipher


DATASET_DIR = "experiments/paper_workflow_study/standard_dataset"
RESULTS_DIR = "experiments/paper_workflow_study/results"
PLOTS_DIR = "experiments/paper_workflow_study/plots"
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 1. HISTOGRAM & CHI-SQUARE FLATNESS
# -----------------------------------------------------------------------------
def analyze_histogram(image_bytes: bytes) -> dict:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256)
    expected = len(arr) / 256.0
    chi2 = float(np.sum((counts - expected) ** 2 / expected))
    p_val = float(stats.chi2.sf(chi2, 255))
    return {
        "chi2": round(chi2, 2),
        "p_value": p_val,
        "is_uniform": p_val > 0.01,
        "counts": counts.tolist(),
    }


# -----------------------------------------------------------------------------
# 2. ADJACENT PIXEL CORRELATION (APC)
# -----------------------------------------------------------------------------
def compute_apc_single_channel(mat: np.ndarray, num_samples: int = 5000, seed: int = 42) -> dict:
    """Computes Horizontal, Vertical, and Diagonal correlation coefficients."""
    h, w = mat.shape
    rng = np.random.RandomState(seed)

    # Horizontal pairs: (x, y) and (x, y+1)
    xs_h = rng.randint(0, h, num_samples)
    ys_h = rng.randint(0, w - 1, num_samples)
    u_h = mat[xs_h, ys_h].astype(np.float64)
    v_h = mat[xs_h, ys_h + 1].astype(np.float64)
    r_h = float(np.corrcoef(u_h, v_h)[0, 1])

    # Vertical pairs: (x, y) and (x+1, y)
    xs_v = rng.randint(0, h - 1, num_samples)
    ys_v = rng.randint(0, w, num_samples)
    u_v = mat[xs_v, ys_v].astype(np.float64)
    v_v = mat[xs_v + 1, ys_v].astype(np.float64)
    r_v = float(np.corrcoef(u_v, v_v)[0, 1])

    # Diagonal pairs: (x, y) and (x+1, y+1)
    xs_d = rng.randint(0, h - 1, num_samples)
    ys_d = rng.randint(0, w - 1, num_samples)
    u_d = mat[xs_d, ys_d].astype(np.float64)
    v_d = mat[xs_d + 1, ys_d + 1].astype(np.float64)
    r_d = float(np.corrcoef(u_d, v_d)[0, 1])

    return {
        "horizontal": round(r_h, 6),
        "vertical": round(r_v, 6),
        "diagonal": round(r_d, 6),
    }


def compute_apc(img_matrix: np.ndarray, num_samples: int = 5000) -> dict:
    if img_matrix.ndim == 2:
        return compute_apc_single_channel(img_matrix, num_samples)
    elif img_matrix.ndim == 3:
        ch_names = ["R", "G", "B"]
        res = {}
        h_list, v_list, d_list = [], [], []
        for i, name in enumerate(ch_names):
            ch_res = compute_apc_single_channel(img_matrix[:, :, i], num_samples)
            res[name] = ch_res
            h_list.append(ch_res["horizontal"])
            v_list.append(ch_res["vertical"])
            d_list.append(ch_res["diagonal"])
        res["average"] = {
            "horizontal": round(float(np.mean(h_list)), 6),
            "vertical": round(float(np.mean(v_list)), 6),
            "diagonal": round(float(np.mean(d_list)), 6),
        }
        return res


# -----------------------------------------------------------------------------
# 3. DIFFERENTIAL ATTACK (NPCR & UACI)
# -----------------------------------------------------------------------------
def compute_npcr_uaci(c1: bytes, c2: bytes) -> tuple:
    a1 = np.frombuffer(c1, dtype=np.uint8)
    a2 = np.frombuffer(c2, dtype=np.uint8)
    n = len(a1)
    diff_mask = a1 != a2
    npcr = (float(np.sum(diff_mask)) / n) * 100.0
    uaci = (float(np.sum(np.abs(a1.astype(np.float64) - a2.astype(np.float64)))) / (255.0 * n)) * 100.0
    return round(npcr, 6), round(uaci, 6)


# -----------------------------------------------------------------------------
# 4. ENTROPY: GLOBAL SHANNON & LOCALIZED (LOCSE)
# -----------------------------------------------------------------------------
def compute_shannon_entropy(byte_data: bytes) -> float:
    arr = np.frombuffer(byte_data, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256)
    p = counts[counts > 0] / len(arr)
    return float(-np.sum(p * np.log2(p)))


def compute_locse(img_matrix: np.ndarray, num_blocks: int = 30, block_size: int = 44) -> dict:
    """Computes Localized Shannon Entropy (LOCSE) over n=30 random 44x44 (TB=1936) sub-images."""
    h, w = img_matrix.shape[:2]
    rng = np.random.RandomState(42)
    mat = img_matrix[:, :, 0] if img_matrix.ndim == 3 else img_matrix

    entropies = []
    max_x = h - block_size
    max_y = w - block_size
    for _ in range(num_blocks):
        x = rng.randint(0, max_x)
        y = rng.randint(0, max_y)
        sub = mat[x : x + block_size, y : y + block_size]
        h_val = compute_shannon_entropy(sub.tobytes())
        entropies.append(h_val)

    locse_mean = float(np.mean(entropies))
    locse_std = float(np.std(entropies))
    # Standard critical interval for n=30, TB=1936 at alpha=0.05: [7.901515, 7.903423]
    passed = 7.901515 <= locse_mean <= 7.903423
    return {
        "locse_mean": round(locse_mean, 6),
        "locse_std": round(locse_std, 6),
        "locse_ideal": 7.902469,
        "critical_interval": [7.901516, 7.903423],
        "passed": passed,
    }


# -----------------------------------------------------------------------------
# 5. KEY SENSITIVITY & NBCR
# -----------------------------------------------------------------------------
def evaluate_nbcr(img_bytes: bytes, key: bytes, nonce: bytes, shape: tuple = None, sample_bits: int = 16) -> dict:
    cipher_base = ISCImageCipher(key, nonce, use_siv=True)
    c_base, n_base = cipher_base.encrypt(img_bytes, shape=shape, raw=True)
    c_base_bits = np.unpackbits(np.frombuffer(c_base, dtype=np.uint8))
    total_bits = len(c_base_bits)

    nbcr_enc_list = []
    nbcr_dec_list = []

    for bit_idx in range(sample_bits):
        byte_idx = bit_idx // 8
        bit_pos = bit_idx % 8
        key_mod = bytearray(key)
        key_mod[byte_idx] ^= (1 << bit_pos)

        cipher_mod = ISCImageCipher(bytes(key_mod), nonce, use_siv=True)
        c_mod, _ = cipher_mod.encrypt(img_bytes, shape=shape, raw=True)
        c_mod_bits = np.unpackbits(np.frombuffer(c_mod, dtype=np.uint8))
        ham_enc = int(np.sum(c_base_bits ^ c_mod_bits))
        nbcr_enc_list.append(ham_enc / total_bits)

        p_wrong = cipher_mod.decrypt(c_base, shape=shape, synth_nonce=n_base, verify_auth=False)
        p_wrong_bits = np.unpackbits(np.frombuffer(p_wrong, dtype=np.uint8))
        orig_bits = np.unpackbits(np.frombuffer(img_bytes, dtype=np.uint8))
        ham_dec = int(np.sum(orig_bits ^ p_wrong_bits))
        nbcr_dec_list.append(ham_dec / total_bits)

    return {
        "mean_nbcr_enc": round(float(np.mean(nbcr_enc_list)), 6),
        "mean_nbcr_dec": round(float(np.mean(nbcr_dec_list)), 6),
        "std_nbcr_enc": round(float(np.std(nbcr_enc_list)), 6),
        "sample_bits_tested": sample_bits,
    }


def main():
    print("==========================================================================")
    print("Executing Benchmark Suite on Enhanced ISC-IEA (Exact MTAP Dataset)")
    print("==========================================================================")

    k1 = b"ISC_ENCRYPTION_MASTER_KEY_256B!!"
    nonce = b"ISC_NONCE_128BIT"
    cipher1 = ISCImageCipher(k1, nonce, use_siv=True)

    # 1-bit perturbed key for sensitivity tests
    k2 = bytearray(k1)
    k2[0] ^= 0x01
    cipher2 = ISCImageCipher(bytes(k2), nonce, use_siv=True)

    results = {}

    # -------------------------------------------------------------------------
    # PART A: Table 1 - Lena 512x512 Grayscale APC Benchmark
    # -------------------------------------------------------------------------
    print("\n--- Part A: Table 1 - Lena 512x512 Grayscale APC ---")
    lena_gray_path = os.path.join(DATASET_DIR, "lena_512_gray.npy")
    lena_gray = np.load(lena_gray_path)
    lena_bytes = lena_gray.tobytes()

    t0 = time.perf_counter()
    lena_cipher_bytes, lena_synth = cipher1.encrypt(lena_bytes, shape=lena_gray.shape, raw=True)
    t_enc_lena = time.perf_counter() - t0
    lena_dec_bytes = cipher1.decrypt(lena_cipher_bytes, shape=lena_gray.shape, synth_nonce=lena_synth)
    assert lena_dec_bytes == lena_bytes, "Decryption failure on Lena512!"
    lena_cipher_mat = np.frombuffer(lena_cipher_bytes, dtype=np.uint8).reshape(512, 512)

    apc_lena_plain = compute_apc(lena_gray)
    apc_lena_cipher = compute_apc(lena_cipher_mat)
    print(f"Lena Plain Correlation:  H = {apc_lena_plain['horizontal']:+.6f}, V = {apc_lena_plain['vertical']:+.6f}, D = {apc_lena_plain['diagonal']:+.6f}")
    print(f"Lena Cipher Correlation: H = {apc_lena_cipher['horizontal']:+.6f}, V = {apc_lena_cipher['vertical']:+.6f}, D = {apc_lena_cipher['diagonal']:+.6f}")

    results["table1_lena512"] = {
        "plain_apc": apc_lena_plain,
        "cipher_apc": apc_lena_cipher,
        "enc_time_sec": round(t_enc_lena, 4),
    }

    # -------------------------------------------------------------------------
    # PART B: USC-SIPI Grayscale Dataset (Tables 2, 3, 4)
    # -------------------------------------------------------------------------
    print("\n--- Part B: USC-SIPI Grayscale Dataset Benchmark (Tables 2, 3, 4) ---")
    gray_images = [
        ("5.1.09.npy", "5.1.09 (256x256)"),
        ("5.1.10.npy", "5.1.10 (256x256)"),
        ("5.1.11.npy", "5.1.11 (256x256)"),
        ("5.1.12.npy", "5.1.12 Couple (256x256)"),
        ("5.1.13.npy", "5.1.13 (256x256)"),
        ("5.1.14.npy", "5.1.14 (256x256)"),
        ("5.2.08.npy", "5.2.08 (512x512)"),
        ("boat.512.npy", "boat.512 (512x512)"),
        ("lena_512_gray.npy", "lena.512 (512x512)"),
    ]

    gray_benchmark = {}
    for fname, desc in gray_images:
        fpath = os.path.join(DATASET_DIR, fname)
        img = np.load(fpath)
        img_bytes = img.tobytes()

        # Encrypt
        t0 = time.perf_counter()
        c_bytes, n_synth = cipher1.encrypt(img_bytes, shape=img.shape, raw=True)
        t_enc = time.perf_counter() - t0

        # Exact decryption check
        p_rec = cipher1.decrypt(c_bytes, shape=img.shape, synth_nonce=n_synth)
        assert p_rec == img_bytes, f"Decryption failed for {fname}"

        c_mat = np.frombuffer(c_bytes, dtype=np.uint8).reshape(img.shape)

        # Differential test (flip pixel at midpoint)
        img_mod = bytearray(img_bytes)
        img_mod[len(img_mod) // 2] ^= 0x01
        c_mod, _ = cipher1.encrypt(bytes(img_mod), shape=img.shape, raw=True)
        npcr, uaci = compute_npcr_uaci(c_bytes, c_mod)

        # Entropies
        h_glob = compute_shannon_entropy(c_bytes)
        locse = compute_locse(c_mat)

        # Histogram flatness
        hist = analyze_histogram(c_bytes)

        # APC
        apc_c = compute_apc(c_mat)

        print(f"[{desc:22s}] NPCR: {npcr:.4f}% | UACI: {uaci:.4f}% | Global H: {h_glob:.6f} | LOCSE: {locse['locse_mean']:.6f} ({'PASS' if locse['passed'] else 'FAIL'}) | chi2: {hist['chi2']}")

        gray_benchmark[fname] = {
            "name": desc,
            "shape": list(img.shape),
            "npcr": npcr,
            "uaci": uaci,
            "global_entropy": round(h_glob, 6),
            "locse": locse,
            "hist_chi2": hist["chi2"],
            "hist_p": hist["p_value"],
            "cipher_apc": apc_c,
            "enc_time_sec": round(t_enc, 4),
        }

    results["usc_sipi_grayscale_benchmark"] = gray_benchmark

    # -------------------------------------------------------------------------
    # PART C: Figure 6 - 5.1.12 Couple Grayscale Encryption & Histograms
    # -------------------------------------------------------------------------
    print("\n--- Part C: Generating Figure 6 (5.1.12 Couple Grayscale) ---")
    c5112_path = os.path.join(DATASET_DIR, "5.1.12.npy")
    c5112_img = np.load(c5112_path)
    c5112_bytes = c5112_img.tobytes()
    c5112_cipher_bytes, c5112_synth = cipher1.encrypt(c5112_bytes, shape=c5112_img.shape, raw=True)
    c5112_cipher_img = np.frombuffer(c5112_cipher_bytes, dtype=np.uint8).reshape(c5112_img.shape)

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes[0, 0].imshow(c5112_img, cmap="gray")
    axes[0, 0].set_title("(a) Plain Image (5.1.12 Couple)")
    axes[0, 0].axis("off")

    axes[0, 1].hist(c5112_img.ravel(), bins=256, range=[0, 256], color="steelblue", alpha=0.85)
    axes[0, 1].set_title("(b) Plain Image Histogram")
    axes[0, 1].set_xlim([0, 256])

    axes[1, 0].imshow(c5112_cipher_img, cmap="gray")
    axes[1, 0].set_title("(c) Encrypted Image (5.1.12)")
    axes[1, 0].axis("off")

    axes[1, 1].hist(c5112_cipher_img.ravel(), bins=256, range=[0, 256], color="crimson", alpha=0.85)
    axes[1, 1].set_title("(d) Encrypted Image Histogram (Flat)")
    axes[1, 1].set_xlim([0, 256])

    fig6_path = os.path.join(PLOTS_DIR, "Figure_6_Grayscale_5_1_12.png")
    plt.tight_layout()
    plt.savefig(fig6_path, dpi=150)
    plt.close(fig)
    print(f"  Saved Figure 6 to: {fig6_path}")

    # -------------------------------------------------------------------------
    # PART D: Figures 7 & 8 - Baboon RGB Encryption & Channel Histograms
    # -------------------------------------------------------------------------
    print("\n--- Part D: Generating Figures 7 & 8 (Baboon 512x512x3 RGB) ---")
    baboon_path = os.path.join(DATASET_DIR, "baboon_512_rgb.npy")
    baboon_img = np.load(baboon_path)
    baboon_bytes = baboon_img.tobytes()

    t0 = time.perf_counter()
    baboon_c_bytes, baboon_synth = cipher1.encrypt(baboon_bytes, shape=baboon_img.shape, raw=True)
    t_enc_baboon = time.perf_counter() - t0
    baboon_dec_bytes = cipher1.decrypt(baboon_c_bytes, shape=baboon_img.shape, synth_nonce=baboon_synth)
    assert baboon_dec_bytes == baboon_bytes, "Decryption failure on Baboon RGB!"
    baboon_c_img = np.frombuffer(baboon_c_bytes, dtype=np.uint8).reshape(baboon_img.shape)

    # Figure 7: Plain Baboon + R, G, B Histograms
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    axes[0].imshow(baboon_img)
    axes[0].set_title("(a) Plain Baboon")
    axes[0].axis("off")

    colors = [("red", "Red Channel"), ("green", "Green Channel"), ("blue", "Blue Channel")]
    for idx, (col, label) in enumerate(colors):
        axes[idx + 1].hist(baboon_img[:, :, idx].ravel(), bins=256, range=[0, 256], color=col, alpha=0.7)
        axes[idx + 1].set_title(f"Plain {label}")
        axes[idx + 1].set_xlim([0, 256])
    fig7_path = os.path.join(PLOTS_DIR, "Figure_7_Baboon_Plain_RGB.png")
    plt.tight_layout()
    plt.savefig(fig7_path, dpi=150)
    plt.close(fig)
    print(f"  Saved Figure 7 to: {fig7_path}")

    # Figure 8: Cipher Baboon + R, G, B Histograms
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    axes[0].imshow(baboon_c_img)
    axes[0].set_title("(a) Encrypted Baboon")
    axes[0].axis("off")

    for idx, (col, label) in enumerate(colors):
        axes[idx + 1].hist(baboon_c_img[:, :, idx].ravel(), bins=256, range=[0, 256], color=col, alpha=0.7)
        axes[idx + 1].set_title(f"Encrypted {label} (Flat)")
        axes[idx + 1].set_xlim([0, 256])
    fig8_path = os.path.join(PLOTS_DIR, "Figure_8_Baboon_Cipher_RGB.png")
    plt.tight_layout()
    plt.savefig(fig8_path, dpi=150)
    plt.close(fig)
    print(f"  Saved Figure 8 to: {fig8_path}")

    apc_baboon_plain = compute_apc(baboon_img)
    apc_baboon_cipher = compute_apc(baboon_c_img)
    results["baboon_rgb"] = {
        "plain_apc": apc_baboon_plain,
        "cipher_apc": apc_baboon_cipher,
        "enc_time_sec": round(t_enc_baboon, 4),
        "r_hist_chi2": analyze_histogram(baboon_c_img[:, :, 0].tobytes())["chi2"],
        "g_hist_chi2": analyze_histogram(baboon_c_img[:, :, 1].tobytes())["chi2"],
        "b_hist_chi2": analyze_histogram(baboon_c_img[:, :, 2].tobytes())["chi2"],
    }

    # -------------------------------------------------------------------------
    # PART E: Figures 9 & 10 - Peppers RGB Key Sensitivity Benchmark
    # -------------------------------------------------------------------------
    print("\n--- Part E: Generating Figures 9 & 10 (Peppers 512x512x3 RGB Key Sensitivity) ---")
    peppers_path = os.path.join(DATASET_DIR, "peppers_512_rgb.npy")
    peppers_img = np.load(peppers_path)
    peppers_bytes = peppers_img.tobytes()

    # Encrypt with K1
    c1_bytes, c1_synth = cipher1.encrypt(peppers_bytes, shape=peppers_img.shape, raw=True)
    c1_img = np.frombuffer(c1_bytes, dtype=np.uint8).reshape(peppers_img.shape)

    # Encrypt with K2 (1-bit flipped)
    c2_bytes, c2_synth = cipher2.encrypt(peppers_bytes, shape=peppers_img.shape, raw=True)
    c2_img = np.frombuffer(c2_bytes, dtype=np.uint8).reshape(peppers_img.shape)

    # Difference image |C1 - C2|
    diff_c1_c2 = np.abs(c1_img.astype(np.int16) - c2_img.astype(np.int16)).astype(np.uint8)
    npcr_k, uaci_k = compute_npcr_uaci(c1_bytes, c2_bytes)
    print(f"Key Sensitivity Difference: NPCR(|C1 - C2|) = {npcr_k:.4f}% | UACI(|C1 - C2|) = {uaci_k:.4f}%")

    # Figure 9: Plain, Cipher K1, Cipher K2, Difference |C1 - C2|
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    axes[0].imshow(peppers_img)
    axes[0].set_title("(a) Plain Peppers")
    axes[0].axis("off")

    axes[1].imshow(c1_img)
    axes[1].set_title("(b) Cipher C1 (Key K1)")
    axes[1].axis("off")

    axes[2].imshow(c2_img)
    axes[2].set_title("(c) Cipher C2 (Key K2=K1^1)")
    axes[2].axis("off")

    axes[3].imshow(diff_c1_c2)
    axes[3].set_title(f"(d) Diff |C1-C2|\n(NPCR={npcr_k:.2f}%)")
    axes[3].axis("off")

    fig9_path = os.path.join(PLOTS_DIR, "Figure_9_Key_Sensitivity_Encryption.png")
    plt.tight_layout()
    plt.savefig(fig9_path, dpi=150)
    plt.close(fig)
    print(f"  Saved Figure 9 to: {fig9_path}")

    # Figure 10: Decryption Key Sensitivity
    # Decrypt C1 with correct key K1
    p_correct = cipher1.decrypt(c1_bytes, shape=peppers_img.shape, synth_nonce=c1_synth)
    p_correct_img = np.frombuffer(p_correct, dtype=np.uint8).reshape(peppers_img.shape)

    # Decrypt C1 with wrong key K2 (bypassing auth check to visualize noise)
    p_wrong = cipher2.decrypt(c1_bytes, shape=peppers_img.shape, synth_nonce=c1_synth, verify_auth=False)
    p_wrong_img = np.frombuffer(p_wrong, dtype=np.uint8).reshape(peppers_img.shape)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].imshow(c1_img)
    axes[0].set_title("(a) Encrypted Image C1")
    axes[0].axis("off")

    axes[1].imshow(p_correct_img)
    axes[1].set_title("(b) Decrypted with K1 (Exact)")
    axes[1].axis("off")

    axes[2].imshow(p_wrong_img)
    axes[2].set_title("(c) Decrypted with Wrong K2")
    axes[2].axis("off")

    fig10_path = os.path.join(PLOTS_DIR, "Figure_10_Key_Sensitivity_Decryption.png")
    plt.tight_layout()
    plt.savefig(fig10_path, dpi=150)
    plt.close(fig)
    print(f"  Saved Figure 10 to: {fig10_path}")

    # NBCR test on 5.1.12 (16 bits)
    print("\n--- Computing Secret Key NBCR (16 Key Bits) on 5.1.12 ---")
    nbcr_results = evaluate_nbcr(c5112_bytes, k1, nonce, shape=c5112_img.shape, sample_bits=16)
    print(f"  Mean NBCR (Enc): {nbcr_results['mean_nbcr_enc']:.6f} (Ideal 0.500000)")
    print(f"  Mean NBCR (Dec): {nbcr_results['mean_nbcr_dec']:.6f} (Ideal 0.500000)")
    results["nbcr_key_sensitivity"] = nbcr_results

    # Save full results JSON
    out_json = os.path.join(RESULTS_DIR, "standard_dataset_results.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[DONE] All standard evaluations saved to: {out_json}")


if __name__ == "__main__":
    main()
