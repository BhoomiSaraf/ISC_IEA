"""DEMO (for presentation only): show every intermediate value of ISC-IMG v1 for one image.

    python experiments/demo_show_keystream.py

Uses a PUBLIC demo key and nonce (never use for real data). Writes to results/demo/demo_<UTC>/:
  steps.txt            all intermediate values in the order of the algorithm
  1_trajectory.png     the chaotic ISC orbit of one lane (x_n, y_n) after burn-in
  2_keystream.png      the generated chaotic bytes (fwd stream) shown as an image + their histogram
  3_sbox_perm.png      the key-dependent S-box and the pixel permutation
  4_encryption.png     plain image, after permutation, after diffusion (cipher), decrypted
"""

import datetime as dt
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from isc_cipher import diffusion, sampling  # noqa: E402
from isc_cipher._testing import encrypt_bytes_with_nonce_TEST_ONLY, materials_TEST_ONLY  # noqa: E402
from isc_cipher.cipher import decrypt_bytes  # noqa: E402
from isc_cipher.generator import BURN_IN, m_byte  # noqa: E402
from isc_cipher.isc_step import step_ref  # noqa: E402
from isc_cipher.kdf import Derivation, context  # noqa: E402
from isc_cipher.state_map import seed_to_ints, seed_to_state  # noqa: E402

KEY = bytes(range(32))          # PUBLIC demo key
NONCE = bytes(range(16))        # PUBLIC demo nonce


def main():
    from skimage import data
    img = np.ascontiguousarray(data.camera()[::4, ::4])            # 128 x 128 grayscale
    h, w = img.shape
    out = os.path.join(ROOT, "results", "demo", "demo_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    os.makedirs(out)
    L = []
    L.append("ISC-IMG v1 DEMO (public demo key and nonce; for presentation only)\n")
    L.append(f"STEP 1  secret key K (32 bytes)        : {KEY.hex()}")
    L.append(f"STEP 1  nonce N (16 bytes, public)      : {NONCE.hex()}")
    der = Derivation(KEY, NONCE, context(1, 1, h, w, 1))
    L.append(f"STEP 2  HKDF context                    : {der.ctx.hex()}  (= 'ISC-IMG/v1' | profile | dtype | H | W | C)")
    L.append(f"STEP 2  MAC key (derived)               : {der.mac_key().hex()}")
    ivf, ivb = der.ivs()
    L.append(f"STEP 2  diffusion IVs                   : iv_f = {ivf}, iv_b = {ivb}")
    seeds = der.seeds()
    s0 = seeds["fwd"][0]
    a, b = seed_to_ints(s0)
    x0, y0 = seed_to_state(s0)
    L.append(f"STEP 2  seed of lane fwd/0 (16 bytes)   : {s0.hex()}")
    L.append(f"STEP 3  alpha, beta (53-bit integers)   : {a}, {b}")
    L.append(f"STEP 3  initial state (x0, y0)          : ({x0!r}, {y0!r})")
    L.append("STEP 3  (256 lanes in total: 4 streams sbox/perm/fwd/bwd x 64 lanes, each with its own seed)\n")
    x, y = x0, y0
    L.append("STEP 4  frozen ISC map, first 5 steps of burn-in (lane fwd/0):")
    for i in range(1, 1 + BURN_IN):
        x, y = step_ref(x, y)
        if i <= 5:
            L.append(f"          n = {i}: x = {x: .17f}, y = {y: .17f}")
    L.append(f"STEP 4  state after burn-in (T = {BURN_IN}): ({x!r}, {y!r})")
    xs, ys, bts = [], [], []
    for _ in range(20000):
        x, y = step_ref(x, y)
        xs.append(x)
        ys.append(y)
        bts += [m_byte(x), m_byte(y)]
    L.append("STEP 5  extraction M(v) = bits 8..15 of the binary64 value, first 5 output steps of lane fwd/0:")
    for j in range(5):
        L.append(f"          x = {xs[j]: .17f} (bits {struct.pack('>d', xs[j]).hex()}) -> byte {bts[2 * j]:3d};   "
                 f"y = {ys[j]: .17f} -> byte {bts[2 * j + 1]:3d}")
    m = materials_TEST_ONLY(KEY, NONCE, h, w, 1, backend="numpy")
    L.append(f"\nSTEP 5  fwd keystream (all 64 lanes interleaved), first 32 bytes: {m['a'][:32].hex()}")
    L.append(f"STEP 5  bwd keystream, first 32 bytes                          : {m['b'][:32].hex()}")
    L.append(f"STEP 5  S-box, first 16 entries                                : {m['S'][:16]}")
    L.append(f"STEP 5  permutation pi, first 16 entries (of {h * w})          : {m['pi'][:16]}")
    p = img.tobytes()
    q = sampling.apply_permutation(p, m["pi"])
    u = diffusion.forward(q, m["a"], m["S"], m["iv_f"])
    c = diffusion.backward(u, m["b"], m["S"], m["iv_b"])
    z = encrypt_bytes_with_nonce_TEST_ONLY(KEY, p, h, w, 1, NONCE)
    assert z[36:-32] == c
    dec = decrypt_bytes(KEY, z)[0]
    L.append(f"\nSTEP 6  ciphertext: header {z[:36].hex()} | body {len(c)} bytes | tag {z[-32:].hex()}")
    L.append(f"STEP 6  KCV (numerical check value)     : {z[28:36].hex()}")
    L.append(f"STEP 7  decryption equals original image: {dec == p}")
    open(os.path.join(out, "steps.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    fig, ax = plt.subplots(1, 2, figsize=(11, 5))
    ax[0].scatter(xs, ys, s=0.2, c="indigo")
    ax[0].set(title="ISC orbit of lane fwd/0 (20,000 steps after burn-in)", xlabel="x_n", ylabel="y_n")
    ax[1].plot(xs[:200], lw=0.8)
    ax[1].set(title="x_n, first 200 output steps", xlabel="n", ylabel="x_n")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "1_trajectory.png"), dpi=130)
    plt.close(fig)
    ks = np.frombuffer(m["a"], np.uint8)
    fig, ax = plt.subplots(1, 2, figsize=(11, 5))
    ax[0].imshow(ks.reshape(h, w), cmap="gray", vmin=0, vmax=255)
    ax[0].set(title="chaotic keystream bytes (fwd stream) as an image")
    ax[1].hist(ks, bins=256, color="gray")
    ax[1].set(title="histogram of keystream bytes", xlabel="byte value")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "2_keystream.png"), dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(1, 2, figsize=(11, 5))
    ax[0].plot(range(256), m["S"], ".", ms=3)
    ax[0].set(title="key-dependent S-box  S[v]", xlabel="v", ylabel="S[v]")
    ax[1].plot(m["pi"][:2000], ".", ms=1)
    ax[1].set(title="pixel permutation pi[k] (first 2000)", xlabel="k", ylabel="pi[k]")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "3_sbox_perm.png"), dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(1, 4, figsize=(16, 4.5))
    for a_, im, t in zip(ax, [p, q, c, dec], ["plain image", "after permutation", "cipher image (after diffusion)", "decrypted"]):
        a_.imshow(np.frombuffer(im, np.uint8).reshape(h, w), cmap="gray", vmin=0, vmax=255)
        a_.set_title(t)
        a_.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "4_encryption.png"), dpi=130)
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
