"""Track F / section 8: key-space analysis (nominal vs effective), via source inspection +
targeted equivalence-class checks. No brute force attempted (explicitly forbidden by spec)."""
import json
import os

import config as cfg
from isc_cipher.kdf import check_key, KEY_LEN
from isc_cipher.state_map import seed_to_state, seed_to_ints
from isc_cipher._testing import materials_TEST_ONLY

OUT = os.path.join(cfg.RESULTS_DIR, "keyspace_analysis.json")


def main():
    findings = {}

    findings["nominal_key_space"] = {
        "key_length_bytes": KEY_LEN,
        "nominal_bits": KEY_LEN * 8,
        "claim": "2^256 nominal key space (kdf.py:14,26-29: exactly 32 bytes, no bit is "
                 "structurally discarded by check_key -- it is a straight length/type check).",
    }

    # check_key does not reject any particular byte pattern (e.g. all-zero key is accepted):
    try:
        check_key(bytes([0] * 32))
        allzero_accepted = True
    except Exception:
        allzero_accepted = False
    findings["weak_key_rejection"] = {
        "all_zero_key_accepted": allzero_accepted,
        "note": "check_key (kdf.py:26-29) performs no weak-key filtering (no all-zero, "
                "no low-entropy, no known-bad-pattern rejection). This is consistent with "
                "standard symmetric-cipher practice (AES etc. also do not reject weak-looking "
                "keys) given that the key is assumed to come from a CSPRNG (generate_key() uses "
                "os.urandom); it is the CALLER's responsibility not to supply a low-entropy key.",
    }

    # Truncation/discard checks: does every key bit reach the HKDF extract step?
    # hkdf_extract(salt=nonce, ikm=key) = HMAC-SHA256(key=nonce, msg=key) -- the FULL 32-byte
    # key is the HMAC *message*, and HMAC-SHA256 processes its full message (no truncation
    # inside HMAC's message-processing path for a 32-byte message, which is far below the
    # block size of 64 bytes for SHA-256, so it is absorbed in a single compression-function
    # call with no truncation). Confirmed by direct inspection: kdf.py:32-33 passes `ikm` (the
    # full key) as `msg` to hmac.new(salt, ikm, sha256).digest(), stdlib hmac/hashlib, no
    # truncation anywhere in that call chain.
    findings["key_bit_utilization"] = {
        "structural_claim": "Every one of the 256 key bits is passed, unmodified and "
                             "untruncated, into hmac.new(nonce, key, sha256) as the MESSAGE "
                             "argument (kdf.py:32-33), which the Python stdlib processes as a "
                             "full HMAC over the complete message with no internal truncation.",
        "verified_by": "source inspection of isc_cipher/kdf.py:32-33 and knowledge of the "
                        "standard HMAC-SHA256 message-processing algorithm (RFC 2104); not "
                        "independently re-derived from the stdlib's C implementation in this "
                        "audit (that would require inspecting CPython's hmac/hashlib source, "
                        "out of scope).",
    }

    # Floating-point / state-mapping equivalence classes: seed_to_state maps a 16-byte seed to
    # a pair of floats via a >>11 truncation (state_map.py:11-14) onto a 2^106-point grid (2 x 53
    # significant bits after the >>11 discards the low 11 bits of each 64-bit half). This means
    # MULTIPLE distinct 16-byte seeds CAN map to the IDENTICAL (x0,y0) state if they agree on the
    # top 53 bits of each half and differ only in the bottom 11 bits -- a DOCUMENTED, DELIBERATE
    # loss of seed granularity (not a flaw; it is how a 128-bit seed is mapped onto a 106-bit
    # state space, 2^22-to-1 as literally stated in state_map.py's own docstring reference to
    # "Lemma 2 (uniform 2^22-to-1)"). Demonstrate this collision directly.
    seed1 = bytes([0x00] * 16)
    seed2 = bytearray(seed1); seed2[7] ^= 0x01  # flip a low bit within the 11 discarded bits of the first half
    seed2 = bytes(seed2)
    state1 = seed_to_state(seed1)
    state2 = seed_to_state(seed2)
    findings["seed_to_state_collision_2_22_to_1"] = {
        "claim": "seed_to_state (state_map.py:21-23) discards the low 11 bits of each 64-bit "
                 "seed half via >>11 (state_map.py:14), so 2^22 distinct 16-byte seeds map to "
                 "each distinct (x0,y0) state (2^11 for each half, 2^11*2^11=2^22). This is "
                 "DOCUMENTED in the module's own docstring reference to 'Lemma 2 (uniform "
                 "2^22-to-1)' and tested in tests/test_isc_cipher_kdf_state.py -- re-verified "
                 "here with a concrete minimal collision example.",
        "seed1_hex": seed1.hex(),
        "seed2_hex": seed2.hex(),
        "seeds_differ": seed1 != seed2,
        "states_identical": state1 == state2,
        "effective_state_space_bits": 106,
        "implication": (
            "This 2^22-to-1 reduction happens AFTER HKDF (the 128-bit HKDF-derived seed is "
            "itself still the full-entropy output of a 256-bit master key via a cryptographic "
            "hash function), so it does NOT reduce the EFFECTIVE key space below what the "
            "128-bit seed->106-bit-state mapping allows per lane: each of the 256 lanes still "
            "receives 128 bits of HKDF-derived seed material, collapsed to ~106 bits of usable "
            "chaotic-map state. Whether 106 bits of initial-state entropy per lane, propagated "
            "through the ISC map's dynamics, is sufficient to make the GENERATED STREAM "
            "unpredictable to a cryptanalyst with knowledge of the map's closed form is an "
            "UNPROVEN property of the underlying chaotic map, not something this audit can "
            "establish without a dedicated analysis of the ISC map's own mixing/invertibility "
            "properties (out of scope for Phase 4D; flagged for Step-1.1-adjacent follow-up)."
        ),
    }

    # Extraction-profile binding changes derived seeds (already shown in inspect_key_derivation.py
    # for V2); summarized reference here.
    findings["extraction_profile_and_effective_key_space"] = {
        "claim": "VERSION=2's extraction byte is folded into the HKDF context (kdf.py:47-61), "
                 "so (key, nonce, extraction=1) and (key, nonce, extraction=2) yield COMPLETELY "
                 "different derived material under V2 -- this does not increase or decrease the "
                 "nominal 256-bit key space; it is domain separation, not a key-space effect.",
        "cross_reference": "see key_derivation_audit.json 'v2_extraction_binding_changes_all_seeds'",
    }

    # Nonce contributes per-message variation, not permanent key strength (explicit distinction).
    findings["nonce_role_clarification"] = {
        "claim": "The 16-byte nonce (128 bits) is PUBLIC (stored unencrypted in the container, "
                 "container.py offset 12-28) and is per-MESSAGE, not a secondary secret key -- "
                 "it provides domain separation / per-message freshness so that encrypting the "
                 "same plaintext twice under the same key produces different ciphertexts "
                 "(assuming the nonce is not reused), but contributes ZERO bits toward "
                 "'effective key strength' against an attacker who does not know the master "
                 "key, since the nonce is never secret.",
    }

    findings["summary"] = {
        "nominal_key_space_bits": 256,
        "effective_key_space_bits": "UNKNOWN -- cannot be determined from this implementation "
            "audit alone. No structural evidence was found in isc_cipher/ of key bits being "
            "discarded, truncated, or collapsed into equivalence classes BEFORE or DURING HKDF "
            "(the 256-bit key is used whole as the HMAC message in hkdf_extract). The "
            "DOWNSTREAM 2^22-to-1 seed->state collapse (seed_to_state) operates on the already-"
            "HKDF-derived 128-bit per-lane seed, not on the master key directly, so it does not "
            "by itself prove a key-space reduction below 256 bits. However, 'effective key "
            "space' in the cryptographic sense also requires that no computationally-feasible "
            "distinguishing or key-recovery attack exists against the full construction, which "
            "this audit's structural/experimental scope cannot establish or refute. State "
            "explicitly: nominal key space (256 bits) and PROVEN effective/computational "
            "security are NOT the same claim, and only the former is supported by this audit's "
            "evidence.",
    }

    with open(OUT, "w") as f:
        json.dump(findings, f, indent=2)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
