"""A7: ciphertext statistics (a category of its own: statistics are not security evidence).

Constructions (fresh nonces): V-FULL (isc_cipher), V-CHACHA (controlled comparison), AES-256-GCM and
ChaCha20-Poly1305 (standard AEAD baselines). Metrics on the ciphertext body reshaped to (H, W[, 3]):
histogram chi-square (255 dof), global Shannon entropy, local Shannon entropy (k = 30 random non-overlapping
blocks of 1936 pixels, the parameters of [wu2013localentropy]; compared empirically with the AEAD outputs,
not with the paper's critical values), adjacent-pixel correlation H/V/D with Fisher 95% intervals.
NIST STS on 100 ciphertext bodies of 125,000 bytes (gray 250x500 crops) for V-FULL, V-CHACHA and AES-GCM.
"""

import os

import numpy as np
from scipy.stats import chi2

import isc_cipher

from .common import Run, public_key
from .constructions import aead_body, seal
from .exp_nist import SEQ_BYTES, run_sts_batches


def images(full):
    from skimage import data
    imgs = {n: getattr(data, n)() for n in ["camera", "astronaut", "coffee", "chelsea", "moon", "brick", "grass",
                                             "gravel", "text", "checkerboard", "rocket", "cat"]}
    yy, xx = np.indices((256, 256))
    synth = {"zeros": np.zeros((256, 256), np.uint8), "all255": np.full((256, 256), 255, np.uint8),
             "hgrad": xx.astype(np.uint8), "vgrad": yy.astype(np.uint8),
             "checker": (((xx // 8 + yy // 8) % 2) * 255).astype(np.uint8),
             "single_bright": np.pad(np.full((1, 1), 255, np.uint8), ((128, 127), (128, 127))),
             "random": np.random.default_rng(7).integers(0, 256, (256, 256), dtype=np.uint8)}
    synth.update({k + "_rgb": np.repeat(v[:, :, None], 3, axis=2) for k, v in list(synth.items())[:2]})
    allimg = {**imgs, **synth}
    if not full:
        allimg = {"camera": imgs["camera"][:64, :64], "random": synth["random"][:64, :64]}
    return {k: np.ascontiguousarray(v) for k, v in allimg.items()}


def entropy(b):
    c = np.bincount(b, minlength=256).astype(float)
    p = c[c > 0] / c.sum()
    return float(-(p * np.log2(p)).sum())


def local_entropy(flat, rng, k=30, tb=1936):
    if flat.size < k * tb:
        return None
    nb = flat.size // tb
    sel = rng.choice(nb, k, replace=False)
    return float(np.mean([entropy(flat[i * tb:(i + 1) * tb]) for i in sel]))


def correlations(img):
    a = img.astype(np.float64)
    if a.ndim == 2:
        a = a[:, :, None]
    out = {}
    for name, (x, y) in {"H": (a[:, :-1], a[:, 1:]), "V": (a[:-1, :], a[1:, :]), "D": (a[:-1, :-1], a[1:, 1:])}.items():
        x, y = x.ravel(), y.ravel()
        r = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else float("nan")
        n = x.size
        if np.isfinite(r) and abs(r) < 1:
            z = np.arctanh(r)
            se = 1 / np.sqrt(n - 3)
            out[name] = [r, float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se))]
        else:
            out[name] = [r, None, None]
    return out


def metrics(body, shape, rng):
    b = np.frombuffer(body, np.uint8)
    cnt = np.bincount(b, minlength=256)
    e = b.size / 256
    x2 = float(((cnt - e) ** 2 / e).sum())
    return {"hist_chi2": x2, "hist_chi2_p": float(chi2.sf(x2, 255)), "entropy": entropy(b),
            "local_entropy": local_entropy(b, rng), "corr": correlations(b.reshape(shape))}


def a7(mode):
    full = mode == "full"
    imgs = images(full)
    n_nist = 100 if full else 2
    cfg = {"images": {k: list(v.shape) for k, v in imgs.items()}, "constructions": ["V-FULL", "V-CHACHA", "AES-256-GCM", "ChaCha20-Poly1305"],
           "nonces": "fresh random per encryption (recorded)", "nist_sequences": n_nist,
           "nist_crops": "250x500 crops of camera, moon, brick, grass, gravel at rows 0..262 step 14 (20 per image), columns 0/12"}
    run = Run("A7_stats", mode, cfg)
    rng = np.random.default_rng(77)
    key = public_key("A7")
    rows, nonces = [], []
    for name, img in imgs.items():
        h, w = img.shape[:2]
        c = 3 if img.ndim == 3 else 1
        p = img.tobytes()
        rows.append({"image": name, "construction": "plaintext", **metrics(p, img.shape, rng)})
        for cons in cfg["constructions"]:
            if cons == "V-FULL":
                z = isc_cipher.encrypt_bytes(key, p, h, w, c)
                body = z[36:-32]
                nonces.append([name, cons, z[12:28].hex()])
            elif cons == "V-CHACHA":
                nn = os.urandom(16)
                body = seal(cons, key, nn, p, h, w, c)[36:-32]
                nonces.append([name, cons, nn.hex()])
            else:
                nn = os.urandom(12)
                body = aead_body(cons, os.urandom(32), p, h, w, c, nn)
                nonces.append([name, cons, nn.hex()])
            rows.append({"image": name, "construction": cons, **metrics(body, img.shape, rng)})
        run.log(f"{name} done")
    run.write_json("raw/metrics.json", rows)
    run.write_json("raw/nonces.json", nonces)
    # NIST on ciphertext bodies
    from skimage import data
    srcs = [data.camera(), data.moon(), data.brick(), data.grass(), data.gravel()]
    crops = []
    for s in srcs:
        for i in range(20):
            r0, c0 = (i // 2) * 26 + (i % 2) * 7, (i % 2) * 12
            crops.append(np.ascontiguousarray(s[r0:r0 + 250, c0:c0 + 500]))
    crops = crops[:n_nist]
    paths = {k: run.path("raw", f"cipher_{k}.bin") for k in ("V-FULL", "V-CHACHA", "AES-256-GCM")}
    with open(paths["V-FULL"], "xb") as f1, open(paths["V-CHACHA"], "xb") as f2, open(paths["AES-256-GCM"], "xb") as f3:
        for i, cr in enumerate(crops):
            p = cr.tobytes()
            assert len(p) == SEQ_BYTES
            f1.write(isc_cipher.encrypt_bytes(key, p, 250, 500, 1)[36:-32])
            f2.write(seal("V-CHACHA", key, os.urandom(16), p, 250, 500, 1)[36:-32])
            f3.write(aead_body("AES-256-GCM", os.urandom(32), p, 250, 500, 1, os.urandom(12)))
            if i % 10 == 0:
                run.log(f"nist ciphertexts {i}")
    sts = run_sts_batches(run, paths, run.log)
    return run.finish({"metrics_rows": len(rows), "sts": sts, "note": "statistics only; not evidence of security"})
