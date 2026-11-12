"""Section 10: compile the 16-item security claim-evidence table from the other scripts'
results/ JSON files. Run after inspect_key_derivation.py, nonce_analysis.py, chosen_plaintext.py,
diffusion_analysis.py, permutation_analysis.py, sbox_analysis.py, keyspace_analysis.py,
authentication_analysis.py.
"""
import json
import os

import config as cfg

OUT = os.path.join(cfg.RESULTS_DIR, "claim_evidence_table.json")

CLASS_SUPPORTED_IMPL = "supported_by_implementation"
CLASS_SUPPORTED_EXP = "supported_by_experiment"
CLASS_PARTIAL = "partially_supported"
CLASS_UNPROVEN = "unproven"
CLASS_CONTRADICTED = "contradicted"

TABLE = [
    {
        "claim": "1. Key-dependent sequence generation",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "key_derivation_audit.json: all 256 lane seeds, mac/kcv keys, ivs change "
                    "when key changes, confirmed by direct re-derivation.",
    },
    {
        "claim": "2. Nonce-dependent sequence generation",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "key_derivation_audit.json + nonce_analysis.json 4.1: all derived material "
                    "changes with nonce (key fixed).",
    },
    {
        "claim": "3. Bijective confusion (permutation)",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "permutation_analysis.json: Fisher-Yates output verified to be a bijection "
                    "of [0,n) for n in {16,256,4096}.",
    },
    {
        "claim": "4. Nonlinear substitution (S-box)",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "sbox_analysis.json: bijectivity confirmed; DDT/LAT computed showing a "
                    "random-permutation-like (not specially hardened) nonlinearity profile. "
                    "Nonlinear in the sense of 'not affine/not simply predictable from a linear "
                    "model', not claimed to be optimally nonlinear.",
    },
    {
        "claim": "5. Bidirectional diffusion",
        "classification": CLASS_PARTIAL,
        "evidence": "diffusion_analysis.json D2/D3: forward is strictly causal forward "
                    "(k->k..N-1), backward is strictly causal backward (k->0..k) -- CONFIRMED. "
                    "Combined gives near-full (not universally 100%) dependency: the exhaustive "
                    "8x8 matrix shows 99.58% density with a confirmed, reproducible exception "
                    "mechanism (modular-additive cancellation). 'Bidirectional' as a qualitative "
                    "description is accurate; 'full diffusion for every input' is not an "
                    "absolute guarantee.",
    },
    {
        "claim": "6. High statistical uniformity (of ciphertext bytes)",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "Phase 4B/4C: encrypted-body entropy 7.95-7.9992 bits/byte across 63+22 "
                    "images; chi-square results mostly non-significant. This is a STATISTICAL "
                    "finding, explicitly NOT treated as a security proof per the spec's own "
                    "framing and this phase's constraints.",
    },
    {
        "claim": "7. Plaintext sensitivity",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "Phase 4B/4C NPCR~99.7-99.83%/UACI~33.5% + this phase's chosen_plaintext.json "
                    "single-bit propagation (99.0-99.98% of bytes differing). Both independently "
                    "measured; consistent.",
    },
    {
        "claim": "8. Key sensitivity",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "Phase 4B/4C key-sensitivity NPCR~99.6%/UACI~33.5%/Hamming-fraction~0.4998. "
                    "Not independently re-measured in Phase 4D (out of this phase's P0/P1 scope; "
                    "cited from prior phase, not re-verified against raw files here).",
    },
    {
        "claim": "9. Authentication and tamper detection",
        "classification": CLASS_SUPPORTED_EXP,
        "evidence": "authentication_analysis.json: header/body/tag bit-flips and truncation all "
                    "rejected before generator construction (monkeypatch-confirmed); wrong key "
                    "rejected. Consistent with Phase 4A's more exhaustive bit-flip sweep.",
    },
    {
        "claim": "10. Resistance to CPA (chosen-plaintext attack)",
        "classification": CLASS_UNPROVEN,
        "evidence": "chosen_plaintext.json rules out ONE specific classical structure (XOR "
                    "two-time-pad cancellation) and shows no obvious leakage for several "
                    "structured inputs under a SINGLE fixed (key,nonce). This is NOT a general "
                    "CPA-resistance proof or security reduction (e.g. no IND-CPA game is "
                    "defined or analyzed). No security argument exists in the codebase or this "
                    "audit establishing IND-CPA security.",
    },
    {
        "claim": "11. Resistance to KPA (known-plaintext attack)",
        "classification": CLASS_UNPROVEN,
        "evidence": "nonce_analysis.json's equation-counting discussion (Track B) notes that "
                    "under NONCE REUSE, 2+ known-plaintext/ciphertext pairs give more linear-"
                    "equation-count than unknowns (S, a, b, ivs), which is a necessary but not "
                    "sufficient condition for solvability given the problem's actual nonlinear, "
                    "hidden-intermediate-state structure (u is never revealed). No working "
                    "recovery attack was constructed or demonstrated. Explicitly UNPROVEN in "
                    "both directions -- neither shown broken nor shown safe.",
    },
    {
        "claim": "12. Resistance to CCA (chosen-ciphertext attack)",
        "classification": CLASS_PARTIAL,
        "evidence": "authentication_analysis.json: encrypt-then-MAC with auth strictly before "
                    "any decryption/generator work is a RECOGNIZED STRUCTURAL MITIGATION against "
                    "naive CCA (an attacker cannot submit arbitrary modified ciphertexts and "
                    "observe decryption behavior beyond 'Malformed' vs 'AuthenticationError'). "
                    "This is 'partially supported' rather than 'resistant' because (a) no formal "
                    "IND-CCA argument is made, and (b) the Malformed/AuthenticationError "
                    "distinction is itself a (minor, format-validity-only) information leak if a "
                    "deployment surfaces it to an attacker -- see error_oracle_shape finding.",
    },
    {
        "claim": "13. Resistance to differential cryptanalysis",
        "classification": CLASS_UNPROVEN,
        "evidence": "sbox_analysis.json's DDT shows a random-permutation-like (not specially "
                    "hardened) differential profile for the S-BOX IN ISOLATION. High NPCR from "
                    "prior phases is explicitly NOT used as evidence here per spec constraint. "
                    "No differential characteristic was constructed through the FULL "
                    "permutation+diffusion chain, and the per-message S-box/permutation "
                    "re-randomization changes the applicable threat model from fixed-S-box block "
                    "ciphers in ways not analyzed here. UNPROVEN in either direction.",
    },
    {
        "claim": "14. Resistance to linear cryptanalysis",
        "classification": CLASS_UNPROVEN,
        "evidence": "sbox_analysis.json's LAT shows a max bias (0.266) typical of an "
                    "UN-hardened random permutation, markedly worse than a designed S-box like "
                    "AES's. No linear characteristic was constructed through the full "
                    "permutation+diffusion chain. UNPROVEN in either direction; the standalone "
                    "S-box metric alone does not establish full-cipher resistance OR vulnerability.",
    },
    {
        "claim": "15. Resistance to brute force",
        "classification": CLASS_PARTIAL,
        "evidence": "keyspace_analysis.json: nominal key space is 256 bits with no structural "
                    "bit-discarding found in the key->HKDF path. This makes NAIVE brute force "
                    "over the key space computationally infeasible BY DEFINITION of 256-bit "
                    "nominal strength, assuming no shortcut attack exists -- but EFFECTIVE "
                    "security (whether any shortcut/structural attack reduces this) is UNKNOWN "
                    "per this audit's explicit finding. No brute-force attempt was made "
                    "(prohibited by spec).",
    },
    {
        "claim": "16. Overall cryptographic security",
        "classification": CLASS_UNPROVEN,
        "evidence": "No formal security proof, reduction, or peer-reviewed cryptanalysis exists "
                    "for the custom permutation + modular-additive-chained-diffusion "
                    "construction. Phases 4A-4D establish correct implementation of the "
                    "DESCRIBED algorithm, strong descriptive statistics, and no CONFIRMED "
                    "exploitable break -- but this is categorically different from a security "
                    "proof. 256-bit keys, HKDF, HMAC, high NPCR/UACI/entropy do NOT, "
                    "individually or combined, establish overall security, per this phase's "
                    "explicit constraint and standard cryptographic practice.",
    },
]


def main():
    with open(OUT, "w") as f:
        json.dump(TABLE, f, indent=2)
    for row in TABLE:
        print(f"{row['claim']:<55} {row['classification']}")


if __name__ == "__main__":
    main()
