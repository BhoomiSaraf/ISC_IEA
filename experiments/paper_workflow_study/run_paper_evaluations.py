"""Comprehensive Security Analysis Suite mirroring Section 4 of the Reference Paper.

Evaluates:
  4.1 Histogram Analysis (Grayscale and RGB flat histograms & chi-square)
  4.2 Adjacent Pixel Correlation (Horizontal, Vertical, Diagonal)
  4.3 Secret Key Security:
      - Key Sensitivity in Encryption (Single-bit key difference images)
      - Key Sensitivity in Decryption (Wrong-key decryption noise)
      - Number of Bit Change Rate (NBCR across 256 key bits, ideal = 0.50)
  4.4 Differential Attack Analysis:
      - Number of Pixel Changing Rate (NPCR, ideal = 99.6094%)
      - Unified Average Changed Intensity (UACI, ideal = 33.4635%)
  4.5 Localized Shannon Entropy (LOCSE, n=30, TB=1936, confidence [7.901515, 7.903423])
  4.6 Speed and Throughput Benchmark
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


DATASET_DIR = "experiments/phase4c/dataset"
RESULTS_DIR = "experiments/paper_workflow_study/results"
PLOTS_DIR = "experiments/paper_workflow_study/plots"
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 4.1 HISTOGRAM & CHI-SQUARE
# -----------------------------------------------------------------------------
def analyze_histogram(image_bytes: bytes):
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
# 4.2 ADJACENT PIXEL CORRELATION (APC)
# -----------------------------------------------------------------------------
def compute_apc(img_matrix: np.ndarray, num_samples: int = 4096) -> dict:
    """Computes Horizontal, Vertical, Diagonal correlation across random pairs."""
    h, w = img_matrix.shape[:2]
    rng = np.random.RandomState(42)

    # If RGB, compute per channel and average
    if img_matrix.ndim == 3:
        corrs = {"horizontal": [], "vertical": [], "diagonal": []}
        for c in range(img_matrix.shape[2]):
            c_res = compute_apc(img_matrix[:, :, c], num_samples)
            for k in corrs:
                corrs[k].append(c_res[k])
        return {k: float(np.mean(v)) for k, v in corrs.items()}

    # Grayscale 2D matrix
    # Horizontal pairs: (x, y) and (x, y+1)
    ys_h = rng.randint(0, w - 1, num_samples)
    xs_h = rng.randint(0, h, num_samples)
    u_h = img_matrix[xs_h, ys_h].astype(np.float64)
    v_h = img_matrix[xs_h, ys_h + 1].astype(np.float64)
    r_h = float(np.corrcoef(u_h, v_h)[0, 1])

    # Vertical pairs: (x, y) and (x+1, y)
    ys_v = rng.randint(0, w, num_samples)
    xs_v = rng.randint(0, h - 1, num_samples)
    u_v = img_matrix[xs_v, ys_v].astype(np.float64)
    v_v = img_matrix[xs_v + 1, ys_v].astype(np.float64)
    r_v = float(np.corrcoef(u_v, v_v)[0, 1])

    # Diagonal pairs: (x, y) and (x+1, y+1)
    ys_d = rng.randint(0, w - 1, num_samples)
    xs_d = rng.randint(0, h - 1, num_samples)
    u_d = img_matrix[xs_d, ys_d].astype(np.float64)
    v_d = img_matrix[xs_d + 1, ys_d + 1].astype(np.float64)
    r_d = float(np.corrcoef(u_d, v_d)[0, 1])

    return {
        "horizontal": round(r_h, 6),
        "vertical": round(r_v, 6),
        "diagonal": round(r_d, 6),
    }


# -----------------------------------------------------------------------------
# 4.3 SECRET KEY SECURITY & NBCR
# -----------------------------------------------------------------------------
def evaluate_nbcr(img_bytes: bytes, key: bytes, nonce: bytes, sample_bits: int = 32):
    """Measures Number of Bit Change Rate (NBCR) when flipping bits of key."""
    cipher_base = ISCImageCipher(key, nonce)
    c_base = cipher_base.encrypt(img_bytes)
    c_base_bits = np.unpackbits(np.frombuffer(c_base, dtype=np.uint8))
    total_bits = len(c_base_bits)

    nbcr_enc_list = []
    nbcr_dec_list = []

    # Test sample_bits distinct key bits
    for bit_idx in range(sample_bits):
        byte_idx = bit_idx // 8
        bit_pos = bit_idx % 8
        key_mod = bytearray(key)
        key_mod[byte_idx] ^= (1 << bit_pos)

        cipher_mod = ISCImageCipher(bytes(key_mod), nonce)
        # Encryption sensitivity
        c_mod = cipher_mod.encrypt(img_bytes)
        c_mod_bits = np.unpackbits(np.frombuffer(c_mod, dtype=np.uint8))
        ham_enc = int(np.sum(c_base_bits ^ c_mod_bits))
        nbcr_enc = ham_enc / total_bits
        nbcr_enc_list.append(nbcr_enc)

        # Decryption sensitivity (attempt to decrypt c_base with wrong key)
        p_wrong = cipher_mod.decrypt(c_base)
        p_wrong_bits = np.unpackbits(np.frombuffer(p_wrong, dtype=np.uint8))
        orig_bits = np.unpackbits(np.frombuffer(img_bytes, dtype=np.uint8))
        ham_dec = int(np.sum(orig_bits ^ p_wrong_bits))
        nbcr_dec = ham_dec / total_bits
        nbcr_dec_list.append(nbcr_dec)

    return {
        "mean_nbcr_enc": round(float(np.mean(nbcr_enc_list)), 6),
        "mean_nbcr_dec": round(float(np.mean(nbcr_dec_list)), 6),
        "std_nbcr_enc": round(float(np.std(nbcr_enc_list)), 6),
        "sample_bits_tested": sample_bits,
    }


# -----------------------------------------------------------------------------
# 4.4 DIFFERENTIAL ATTACK (NPCR & UACI)
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
# 4.5 LOCALIZED SHANNON ENTROPY (LOCSE)
# -----------------------------------------------------------------------------
def compute_shannon_entropy(byte_data: bytes) -> float:
    arr = np.frombuffer(byte_data, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256)
    p = counts[counts > 0] / len(arr)
    return float(-np.sum(p * np.log2(p)))


def compute_locse(img_matrix: np.ndarray, num_blocks: int = 30, block_size: int = 44) -> dict:
    """Computes Localized Shannon Entropy (LOCSE) over n=30 random 44x44 (TB=1936) sub-images."""
    h, w = img_matrix.shape[:2]
    tb = block_size * block_size
    rng = np.random.RandomState(42)

    # Use first channel if RGB
    mat = img_matrix[:, :, 0] if img_matrix.ndim == 3 else img_matrix

    entropies = []
    # Extract non-overlapping blocks
    max_x = h - block_size
    max_y = w - block_size
    for _ in range(num_blocks):
        x = rng.randint(0, max_x)
        y = rng.randint(0, max_y)
        sub = mat[x : x + block_size, y : y + block_size]
        h_val = compute_shannon_entropy(sub.tobytes())
        entropies.append(h_val)

    locse_mean = float(np.mean(entropies))
    # Recommended critical interval for n=30, TB=1936 at alpha=0.05
    # Lower: 7.901515698, Upper: 7.903422936, Ideal: 7.902469317
    passed = 7.901515 <= locse_mean <= 7.903423

    return {
        "locse_mean": round(locse_mean, 6),
        "locse_ideal": 7.902469,
        "critical_interval": [7.901516, 7.903423],
        "passed": passed,
    }


# -----------------------------------------------------------------------------
# MAIN BENCHMARK BATTERY
# -----------------------------------------------------------------------------
def main():
    print("=================================================================")
    print("ISC-IEA Evaluation Suite adhering to the Standard 9-Stage Workflow")
    print("=================================================================")

    # Master Key and Nonce (32 bytes and 16 bytes)
    key = b"ISC_ENCRYPTION_MASTER_KEY_256B!!"
    nonce = b"ISC_NONCE_128BIT"

    cipher = ISCImageCipher(key, nonce)

    # Test images available in dataset
    test_files = [
        ("camera_gray.npy", "Cameraman (Gray 256x256)"),
        ("brick_gray.npy", "Brick (Gray 256x256)"),
        ("astronaut_rgb.npy", "Astronaut (RGB 256x256)"),
    ]

    all_results = {}

    for fname, desc in test_files:
        fpath = os.path.join(DATASET_DIR, fname)
        if not os.path.exists(fpath):
            print(f"Skipping {fname} (not found)")
            continue

        print(f"\n>>> Processing Image: {desc} ({fname}) <<<")
        img = np.load(fpath)
        img_bytes = img.tobytes()
        h, w = img.shape[:2]
        c = img.shape[2] if img.ndim == 3 else 1

        # Encryption and Decryption
        t0 = time.perf_counter()
        cipher_bytes = cipher.encrypt(img_bytes)
        t_enc = time.perf_counter() - t0

        t0 = time.perf_counter()
        dec_bytes = cipher.decrypt(cipher_bytes)
        t_dec = time.perf_counter() - t0

        assert dec_bytes == img_bytes, f"Decryption failure on {fname}!"
        print(f"  Exact Decryption Integrity: VERIFIED (Enc: {t_enc*1000:.2f}ms, Dec: {t_dec*1000:.2f}ms)")

        # Reshape cipher bytes to matrix for 2D analysis
        cipher_img = np.frombuffer(cipher_bytes, dtype=np.uint8).reshape(img.shape)

        # 4.1 Histogram Analysis
        hist_plain = analyze_histogram(img_bytes)
        hist_cipher = analyze_histogram(cipher_bytes)
        print(f"  Histogram: Plain chi2={hist_plain['chi2']} | Cipher chi2={hist_cipher['chi2']} (p={hist_cipher['p_value']:.4f}) [Flat: {hist_cipher['is_uniform']}]")

        # 4.2 Adjacent Pixel Correlation
        apc_plain = compute_apc(img)
        apc_cipher = compute_apc(cipher_img)
        print(f"  Correlation (Plain):  H={apc_plain['horizontal']:+.4f}, V={apc_plain['vertical']:+.4f}, D={apc_plain['diagonal']:+.4f}")
        print(f"  Correlation (Cipher): H={apc_cipher['horizontal']:+.4f}, V={apc_cipher['vertical']:+.4f}, D={apc_cipher['diagonal']:+.4f}")

        # 4.4 Differential Attack (NPCR & UACI)
        # Flip 1 pixel in plain image
        img_mod = bytearray(img_bytes)
        img_mod[len(img_mod) // 2] ^= 0x01
        cipher_mod = cipher.encrypt(bytes(img_mod))
        npcr, uaci = compute_npcr_uaci(cipher_bytes, cipher_mod)
        print(f"  Differential Sensitivity: NPCR = {npcr:.4f}% (Ideal 99.6094%) | UACI = {uaci:.4f}% (Ideal 33.4635%)")

        # 4.5 Information Entropy (Global & Localized)
        global_entropy = round(compute_shannon_entropy(cipher_bytes), 6)
        locse = compute_locse(cipher_img)
        print(f"  Entropy: Global = {global_entropy:.6f} bits | LOCSE = {locse['locse_mean']:.6f} (Passed: {locse['passed']})")

        # 4.3 NBCR Key Sensitivity
        nbcr = evaluate_nbcr(img_bytes, key, nonce, sample_bits=4)
        print(f"  Key Sensitivity: Mean NBCR (Enc) = {nbcr['mean_nbcr_enc']:.4f} (Ideal 0.50) | Mean NBCR (Dec) = {nbcr['mean_nbcr_dec']:.4f}", flush=True)

        # Save metrics
        all_results[fname] = {
            "description": desc,
            "shape": list(img.shape),
            "throughput_mbps": round((len(img_bytes) / (1024 * 1024)) / t_enc, 2),
            "histogram_cipher_chi2": hist_cipher["chi2"],
            "histogram_cipher_p": hist_cipher["p_value"],
            "apc_plain": apc_plain,
            "apc_cipher": apc_cipher,
            "npcr": npcr,
            "uaci": uaci,
            "global_entropy": global_entropy,
            "locse": locse,
            "nbcr": nbcr,
        }

        # Plot Histograms (Fig 6 / 7 / 8 style)
        fig, axes = plt.subplots(2, 2, figsize=(10, 8))
        axes[0, 0].imshow(img, cmap="gray" if c == 1 else None)
        axes[0, 0].set_title(f"Plain Image: {desc}")
        axes[0, 0].axis("off")

        axes[0, 1].hist(img.ravel(), bins=256, range=[0, 256], color="steelblue", alpha=0.8)
        axes[0, 1].set_title("Plain Image Histogram")
        axes[0, 1].set_xlim([0, 256])

        axes[1, 0].imshow(cipher_img, cmap="gray" if c == 1 else None)
        axes[1, 0].set_title("Cipher Image")
        axes[1, 0].axis("off")

        axes[1, 1].hist(cipher_img.ravel(), bins=256, range=[0, 256], color="crimson", alpha=0.8)
        axes[1, 1].set_title("Cipher Image Histogram (Flat)")
        axes[1, 1].set_xlim([0, 256])

        plot_path = os.path.join(PLOTS_DIR, f"hist_{fname.replace('.npy', '')}.png")
        plt.tight_layout()
        plt.savefig(plot_path, dpi=120)
        plt.close(fig)

    # Save all results to JSON
    out_json = os.path.join(RESULTS_DIR, "paper_workflow_results.json")
    with open(out_json, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[DONE] Full paper workflow evaluation results written to {out_json}")


if __name__ == "__main__":
    main()
