"""A5 (key and nonce sensitivity) and A3 (differential propagation under a FIXED nonce).

NPCR/UACI critical values are computed from first principles under the ideal model used by Wu, Noonan
and Agaian [wu2011npcr]: two independent uniform byte images. NPCR ~ Binomial(n, 255/256) / n;
UACI = mean |X - Y| / 255 with the exact distribution of |X - Y| for independent uniform bytes.
"""

import numpy as np
from scipy.stats import norm

from isc_cipher.generator import build_streams
from isc_cipher.kdf import Derivation, context

from .common import Run, public_key, public_nonce
from .constructions import FixedNonceOracle, body_encrypt, materials


def hamming_frac(a, b):
    x = np.frombuffer(a, np.uint8) ^ np.frombuffer(b, np.uint8)
    return float(np.unpackbits(x).mean())


def a5(mode):
    full = mode == "full"
    cfg = {"stream_bytes": 100000 if full else 2000, "dims": [64, 64, 1],
           "flips": "all 256 key bits and 128 nonce bits" if full else "key bits 0, 255 and nonce bits 0, 127"}
    run = Run("A5_sensitivity", mode, cfg)
    key, nonce = public_key("A5"), public_nonce("A5")
    img = bytes(np.random.default_rng(5).integers(0, 256, 4096, dtype=np.uint8))

    def measure(k, nn):
        seeds = Derivation(k, nn, context(1, 1, 64, 64, 1)).seeds()
        st = build_streams(seeds, backend="numpy", profile=1)
        streams = {g: st[g].take(cfg["stream_bytes"]) for g in st}
        body = body_encrypt("V-FULL", materials(k, nn, 64, 64, 1), img)
        return streams, body
    base_s, base_b = measure(key, nonce)
    flips = [("key", i) for i in range(256)] + [("nonce", i) for i in range(128)] if full else \
        [("key", 0), ("key", 255), ("nonce", 0), ("nonce", 127)]
    rows = []
    for what, i in flips:
        k, nn = bytearray(key), bytearray(nonce)
        tgt = k if what == "key" else nn
        tgt[i // 8] ^= 0x80 >> (i % 8)
        s, b = measure(bytes(k), bytes(nn))
        rows.append({"flip": f"{what}[{i}]", **{f"stream_{g}": hamming_frac(s[g], base_s[g]) for g in s},
                     "ciphertext_body": hamming_frac(b, base_b)})
    n_tests = len(rows) * 5
    z = float(norm.ppf(1 - 0.01 / (2 * n_tests)))
    nbits_s, nbits_b = cfg["stream_bytes"] * 8, 4096 * 8
    out_of = [r["flip"] for r in rows if any(abs(r[k] - 0.5) > z * 0.5 / np.sqrt(nbits_s if k.startswith("stream") else nbits_b)
                                              for k in r if k != "flip")]
    run.write_json("raw/flips.json", rows)
    return run.finish({"flips": len(rows), "bonferroni_z": z, "outside_interval": out_of, "finding": bool(out_of),
                       "min_fraction": min(min(v for k, v in r.items() if k != "flip") for r in rows),
                       "max_fraction": max(max(v for k, v in r.items() if k != "flip") for r in rows)})


def ideal_npcr_uaci(n, alpha=0.05):
    p = 255 / 256
    npcr_mu, npcr_sd = p, np.sqrt(p * (1 - p) / n)
    d = np.arange(256)
    probs = np.array([256.0 if k == 0 else 2.0 * (256 - k) for k in d]) / 65536.0
    m = float((probs * d).sum() / 255)
    v = float((probs * (d / 255) ** 2).sum() - m ** 2)
    return {"npcr_mean": npcr_mu, "npcr_lower_critical": npcr_mu - norm.ppf(1 - alpha) * npcr_sd,
            "uaci_mean": m, "uaci_interval": [m - norm.ppf(1 - alpha / 2) * np.sqrt(v / n), m + norm.ppf(1 - alpha / 2) * np.sqrt(v / n)]}


def a3(mode):
    full = mode == "full"
    from skimage import data
    crops = {"camera": data.camera()[100:228, 100:228], "moon": data.moon()[100:228, 100:228],
             "text": data.text()[20:148, 100:228], "coffee": data.coffee()[100:228, 100:228],
             "random": np.random.default_rng(3).integers(0, 256, (128, 128), dtype=np.uint8)}
    if not full:
        crops = {"camera": crops["camera"]}
    n_keys = 5 if full else 1
    n_random_pos = 100 if full else 2
    cfg = {"images": list(crops), "crop": "128x128 (coffee: RGB)", "keys": n_keys, "positions": f"first, last, middle + {n_random_pos} random",
           "variants": ["V-FULL", "V-LINEAR", "V-CHACHA"], "nonce": "fixed per (key, dims) - nonce-misuse model", "alpha": 0.05}
    run = Run("A3_differential", mode, cfg)
    rng = np.random.default_rng(33)
    rows = []
    for variant in cfg["variants"]:
        for kk in range(n_keys):
            for name, img in crops.items():
                img = np.ascontiguousarray(img)
                h, w = img.shape[:2]
                c = 3 if img.ndim == 3 else 1
                orc = FixedNonceOracle(variant, public_key(f"A3/{kk}"), public_nonce(f"A3/{kk}"), h, w, c)
                p = img.tobytes()
                n = len(p)
                crit = ideal_npcr_uaci(n)
                base = np.frombuffer(orc.encrypt(p), np.uint8)
                positions = [0, n - 1, n // 2] + rng.integers(0, n, n_random_pos).tolist()
                for pos in positions:
                    q = bytearray(p)
                    q[pos] = (q[pos] + 1) % 256
                    cc = np.frombuffer(orc.encrypt(bytes(q)), np.uint8)
                    npcr = float(np.mean(cc != base))
                    uaci = float(np.mean(np.abs(cc.astype(int) - base.astype(int))) / 255)
                    rows.append({"variant": variant, "key": kk, "image": name, "position": int(pos), "npcr": npcr, "uaci": uaci,
                                 "npcr_fail": npcr < crit["npcr_lower_critical"],
                                 "uaci_fail": not crit["uaci_interval"][0] <= uaci <= crit["uaci_interval"][1]})
        sub = [r for r in rows if r["variant"] == variant]
        run.log(f"{variant}: {len(sub)} tests, NPCR fails {sum(r['npcr_fail'] for r in sub)}, UACI fails {sum(r['uaci_fail'] for r in sub)}")
    run.write_json("raw/differential.json", rows)
    summ = {}
    for v in cfg["variants"]:
        sub = [r for r in rows if r["variant"] == v]
        summ[v] = {"tests": len(sub), "npcr_fail": sum(r["npcr_fail"] for r in sub), "uaci_fail": sum(r["uaci_fail"] for r in sub),
                   "npcr_min": min(r["npcr"] for r in sub), "uaci_range": [min(r["uaci"] for r in sub), max(r["uaci"] for r in sub)],
                   "expected_false_fail_rate_each": 0.05}
    return run.finish({"by_variant": summ, "critical_values_128x128_gray": ideal_npcr_uaci(128 * 128),
                       "note": "fixed nonce only; NPCR/UACI under fresh nonces are not evidence"})
