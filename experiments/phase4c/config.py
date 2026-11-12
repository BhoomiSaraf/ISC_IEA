"""Phase 4C configuration: paths, seeds, dataset/experiment sizing.

Independent of experiments/phase4b/ (not imported from it, per isolation
requirement) but follows the same conventions for reproducibility.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DATASET_DIR = os.path.join(ROOT, "dataset")
RESULTS_DIR = os.path.join(ROOT, "results")
PLOTS_DIR = os.path.join(ROOT, "plots")
LOGS_DIR = os.path.join(ROOT, "logs")

for _d in (DATASET_DIR, RESULTS_DIR, PLOTS_DIR, LOGS_DIR):
    os.makedirs(_d, exist_ok=True)

MASTER_SEED = 20261112  # fixed, arbitrary, documented (date this phase started)

# Same style as Phase 4B: frozen literal bytes for reproducible fixed
# key/nonce test fixtures. Independently generated for Phase 4C (different
# from Phase 4B's BASE_KEY/BASE_NONCE) via os.urandom() once, then frozen.
BASE_KEY = bytes.fromhex(
    "4f1e3a9d7c2b6e85a0d4f7b1c3e6a9d2f5b8c1e4a7d0f3b6c9e2a5d8f1b4c7e0"
)[:32]
BASE_NONCE = bytes.fromhex("9a3c7e1f5b8d2a6c4e0f7b9d1a3c5e8f")[:16]

assert len(BASE_KEY) == 32
assert len(BASE_NONCE) == 16

BACKEND = "numpy"
# NOTE: isc_cipher.generator.EXTRACTION_MANTISSA8_V1 == 1,
# EXTRACTION_K14_SCALED_MODULO_V1 == 2 (integers, not strings -- verified by
# reading isc_cipher/generator.py:32-33 directly, since encrypt_bytes's
# `extraction` kwarg takes the integer constant).
PROFILE_MANTISSA8 = 1
PROFILE_K14 = 2

# Natural-image resize target (longest side). Chosen to stay within the
# Phase 4B performance envelope (≈12-17s/encrypt at 512x512 gray; RGB is
# worse) while keeping real photographic content. See README.md for the
# pilot-based arithmetic behind this choice.
NATURAL_RESIZE = 256

# NPCR/UACI confirmatory trial budget -- REVISED after pilot_timing.py was
# actually run (logs/pilot_timing.json). The pilot's own first-pass "no
# reduction needed" note assumed ~26s/trial-pair; the measured reality was
# per_trial_sec_gray_256class=22.44s, per_trial_sec_rgb_256class=53.49s (this
# machine is evidently slower for this workload today than it was during
# Phase 4B, or Phase 4B's "256x256 RGB" performance number was in fact
# grayscale-only -- see README.md Track C note). The originally-planned
# 5 images x 4 positions x 3 key/nonce configs (gray) + 3 channel trials x 3
# configs (rgb) = 69 trials would cost ~1828s (~30 min), which is
# disproportionate for a confirmatory check. SCALED BACK to:
#   gray:  3 images x 3 positions x 2 key/nonce configs = 18 trials
#          -> 18 * 22.44s ~= 404s (~6.7 min)
#   rgb:   3 channels x 1 key/nonce config (1 image)    = 3 trials
#          -> 3 * 53.49s ~= 160s (~2.7 min)
#   total: 21 trials, ~564s (~9.4 min) -- see logs/pilot_timing.json for the
#   raw pilot measurements this arithmetic is based on.
NPCR_UACI_POSITIONS = ["top_left", "center", "bottom_right"]
NPCR_UACI_IMAGES_GRAY = ["astronaut_gray", "chelsea_gray", "hubble_deep_field_gray"]
NPCR_UACI_KEYNONCE_CONFIGS_GRAY = 2
NPCR_UACI_RGB_IMAGE = "astronaut_rgb"
NPCR_UACI_KEYNONCE_CONFIGS_RGB = 1
