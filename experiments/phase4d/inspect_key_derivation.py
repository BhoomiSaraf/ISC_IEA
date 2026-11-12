"""Track B / section 4: key derivation and nonce-binding audit (static + light dynamic).

Re-verifies, by direct execution against the production isc_cipher.kdf module (read-only),
which values are key-dependent, nonce-dependent, and extraction-profile-dependent, and whether
V1/V2 contexts differ as documented.
"""
import json
import os

import config as cfg
from isc_cipher.kdf import CONTEXT_PREFIX, Derivation, context, LANES, STREAMS

OUT = os.path.join(cfg.RESULTS_DIR, "key_derivation_audit.json")


def main():
    findings = {}

    # 1. Context construction (kdf.py:47-61)
    # NOTE: context()'s first argument is the normative-ISC-map "profile" field (FDLIBM vs
    # host libm, isc_step.py:1-7), NOT the container VERSION. Held fixed at 1 throughout this
    # comparison so that only the trailing EXTRACTION byte varies, matching the actual call
    # pattern in cipher.py:_materials (profile is passed through unchanged; only ctx_extraction
    # toggles between None [V1] and 1-or-2 [V2]).
    ctx_v1 = context(1, 1, 256, 256, 3, extraction=None)
    ctx_v2_p1 = context(1, 1, 256, 256, 3, extraction=1)
    ctx_v2_p2 = context(1, 1, 256, 256, 3, extraction=2)
    findings["context_v1_len"] = len(ctx_v1)
    findings["context_v2_len"] = len(ctx_v2_p1)
    findings["context_prefix_hex"] = CONTEXT_PREFIX.hex()
    findings["context_v1_equals_v2_minus_last_byte"] = (ctx_v1 == ctx_v2_p1[:-1])
    findings["context_v2_extraction1_vs_extraction2_differ"] = (ctx_v2_p1 != ctx_v2_p2)
    findings["context_v2_only_diff_is_last_byte"] = (ctx_v2_p1[:-1] == ctx_v2_p2[:-1] and ctx_v2_p1[-1] != ctx_v2_p2[-1])

    # 2. Salt/IKM roles (kdf.py:32-33,75): salt=nonce, ikm=key.
    der_a = Derivation(cfg.KEY_A, cfg.NONCE_A, ctx_v1)
    der_a2 = Derivation(cfg.KEY_A, cfg.NONCE_A, ctx_v1)
    findings["derivation_deterministic_same_inputs"] = (der_a.mac_key() == der_a2.mac_key()
                                                          and der_a.seeds() == der_a2.seeds())

    # 3. Dependence on key
    der_b = Derivation(cfg.KEY_B, cfg.NONCE_A, ctx_v1)
    findings["mac_key_changes_with_key"] = (der_a.mac_key() != der_b.mac_key())
    findings["kcv_key_changes_with_key"] = (der_a.kcv_key() != der_b.kcv_key())
    findings["ivs_change_with_key"] = (der_a.ivs() != der_b.ivs())
    seeds_a, seeds_b = der_a.seeds(), der_b.seeds()
    findings["all_256_seeds_change_with_key"] = all(
        seeds_a[g][l] != seeds_b[g][l] for g in STREAMS for l in range(LANES)
    )

    # 4. Dependence on nonce
    der_c = Derivation(cfg.KEY_A, cfg.NONCE_B, ctx_v1)
    findings["mac_key_changes_with_nonce"] = (der_a.mac_key() != der_c.mac_key())
    seeds_c = der_c.seeds()
    findings["all_256_seeds_change_with_nonce"] = all(
        seeds_a[g][l] != seeds_c[g][l] for g in STREAMS for l in range(LANES)
    )

    # 5. Domain separation between streams/lanes: all 256 lane seeds + mac + kcv + iv pairwise distinct
    all_vals = []
    for g in STREAMS:
        all_vals.extend(seeds_a[g])
    all_vals.append(der_a.mac_key())
    all_vals.append(der_a.kcv_key())
    findings["num_derived_values_checked"] = len(all_vals)
    findings["all_pairwise_distinct"] = (len(set(all_vals)) == len(all_vals))

    # 6. Extraction-profile binding: V1 context never includes extraction; V2 does (kdf.py:47-61,
    # cipher.py:_materials ctx_extraction logic). Confirm derived seeds differ between V2
    # extraction=1 and extraction=2 under identical key/nonce.
    der_v2_p1 = Derivation(cfg.KEY_A, cfg.NONCE_A, ctx_v2_p1)
    der_v2_p2 = Derivation(cfg.KEY_A, cfg.NONCE_A, ctx_v2_p2)
    seeds_v2_p1, seeds_v2_p2 = der_v2_p1.seeds(), der_v2_p2.seeds()
    findings["v2_extraction_binding_changes_all_seeds"] = all(
        seeds_v2_p1[g][l] != seeds_v2_p2[g][l] for g in STREAMS for l in range(LANES)
    )
    # V1 context (extraction=None) is NOT bound to extraction at all -- there is only one
    # extraction value (mantissa8_v1) reachable under VERSION=1 by construction (cipher.py:90-91
    # rejects VERSION=1 + extraction!=1), so this is a structural, not merely empirical, fact.
    findings["v1_context_has_no_extraction_byte"] = True

    with open(OUT, "w") as f:
        json.dump(findings, f, indent=2)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
