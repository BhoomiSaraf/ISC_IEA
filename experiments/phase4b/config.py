"""Phase 4B configuration: paths, seeds, dataset/experiment sizing.

This module hard-codes the runtime-budget decisions made from the pilot timing
measurements recorded in logs/pilot_timing.json / README.md. It does not modify
anything under isc_cipher/, isc_seq/ or isc_eval/.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
RESULTS_DIR = os.path.join(ROOT, "results")
PLOTS_DIR = os.path.join(ROOT, "plots")
LOGS_DIR = os.path.join(ROOT, "logs")

for _d in (RESULTS_DIR, PLOTS_DIR, LOGS_DIR):
    os.makedirs(_d, exist_ok=True)

# Fixed, deterministic master seed for all synthetic-image generation and all
# fixed test keys/nonces used in this phase. All randomness in this directory
# is derived from this value (numpy.random.default_rng(MASTER_SEED) or
# documented fixed byte strings below).
MASTER_SEED = 20261111  # fixed, arbitrary, documented

# Deterministic 32-byte key / 16-byte nonce used wherever "the exact same
# key+nonce" or "the exact same plaintext+nonce" is required by the
# experimental validity rules (plaintext-differential and key-sensitivity
# comparisons). Generated once via isc_cipher.generate_key()/os.urandom() and
# then frozen as literal bytes here so every run is reproducible without
# depending on process RNG state.
# Derived deterministically as sha256(b"phase4b-fixed-test-key-v1") / sha256(nonce label)[:16]
# -- not secret, not used for anything but reproducible experimental fixtures in this directory.
BASE_KEY = bytes.fromhex("c7979256783eef481247f4d57c70e1af686318a4d599c01a017cda7dd7820d6a")[:32]
BASE_NONCE = bytes.fromhex("2ba45bf57191bbcb43bbe7564eb8b483")[:16]

assert len(BASE_KEY) == 32
assert len(BASE_NONCE) == 16

# --- Dataset sizing -------------------------------------------------------
# Primary sizes used across correctness/histogram/entropy/correlation
# experiments (P0). 512x512 is included for recovery/performance only
# (P1/P2) because of its cost (see pilot timing).
PRIMARY_SIZES = [64, 128, 256]
EXTENDED_SIZES = [512]  # P1/P2, included only where explicitly noted

# --- NPCR/UACI and key-sensitivity trial budgets --------------------------
# Chosen after the mandatory pilot (see logs/pilot_timing.json). See
# README.md "Pilot-based runtime decisions" for the full arithmetic.
NPCR_UACI_SIZES_GRAY = [64, 128]          # full position x type sweep
NPCR_UACI_SIZE_GRAY_REDUCED = 256          # positions only, 1 image type
NPCR_UACI_RGB_SIZE = 64                    # channel-separate trials
NPCR_UACI_POSITIONS = ["begin", "middle", "end"]
NPCR_UACI_IMAGE_TYPES = ["high_texture_random", "gradient_horizontal", "checkerboard"]
NPCR_UACI_IMAGE_TYPES_REDUCED = ["high_texture_random"]

KEY_SENS_SIZES_GRAY = [64, 128]
KEY_SENS_SIZE_GRAY_REDUCED = 256
KEY_SENS_BIT_POSITIONS = list(range(0, 256, 16))      # 16 positions, full sizes
KEY_SENS_BIT_POSITIONS_REDUCED = list(range(0, 256, 32))  # 8 positions, 256x256

# --- Performance benchmarking ---------------------------------------------
PERF_SIZES = [64, 128, 256, 512]
PERF_REPS = {64: 7, 128: 7, 256: 5, 512: 3}  # fewer reps for the expensive sizes
PERF_WARMUP = 1

BACKEND = "numpy"
