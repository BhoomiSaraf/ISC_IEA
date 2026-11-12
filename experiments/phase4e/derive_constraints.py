"""Part A: exact mathematical formulation of the nonce-reuse constraint system.

Not a solver. Writes the formulation to results/constraint_formulation.json for the final
report. Equations are transcribed directly from isc_cipher/diffusion.py and
isc_cipher/sampling.py (re-read in this phase), not re-derived from memory.

Shared (key,nonce)-derived unknowns across M messages of identical length n:
    S        : bijection on Z_256           (the S-box, S_inv its inverse)
    pi       : permutation of {0..n-1}      (byte-position permutation)
    a        : n values in Z_256            (forward diffusion stream)
    b        : n values in Z_256            (backward diffusion stream)
    iv_f     : 1 value in Z_256
    iv_b     : 1 value in Z_256

Per-message (known) data:
    p^(i)    : n known plaintext bytes
    c^(i)    : n known ciphertext body bytes (НЕ header/tag)

Per-message derived (NOT free unknowns -- fully determined once the shared unknowns are
fixed, by direct forward simulation):
    q^(i)_k  = p^(i)_{pi(k)}
    u^(i)_k  = S[(q^(i)_k + u^(i)_{k-1} + a_k) mod 256],   u^(i)_{-1} = iv_f
    c^(i)_k  = S[(u^(i)_k + c^(i)_{k+1} + b_k) mod 256],   c^(i)_n   = iv_b

This is the key structural fact this phase relies on: u^(i) and the forward/backward chain
are NOT independent free variables to be "solved for" in the usual linear-algebra sense --
they are deterministic functions of (S, pi, a, b, iv_f, iv_b, p^(i)). The "constraint system"
is therefore not a linear system but a CSP/search problem over the finite space of
(S, pi, a, b, iv_f, iv_b) such that, for every known pair i,
    Encrypt(S, pi, a, b, iv_f, iv_b; p^(i)) == c^(i)   (all n bytes, exactly).

This reframes Phase 4D's "equation counting" into a search-space-reduction question: how
many candidate (S, pi, a, b, iv_f, iv_b) tuples remain consistent with M known pairs, and
does that shrink to a unique (or at least functionally-equivalent) tuple as M grows.
"""
import json
import os

import config


def build_formulation():
    return {
        "shared_unknowns": {
            "S": "bijection on Z_256 (256 byte values, constrained to be a permutation)",
            "S_inv": "inverse of S (not independent -- determined by S)",
            "pi": "permutation of {0..n-1} (byte-position permutation), fixed for a given (h,w,c)",
            "a": "n bytes in Z_256 (forward diffusion stream)",
            "b": "n bytes in Z_256 (backward diffusion stream)",
            "iv_f": "1 byte in Z_256",
            "iv_b": "1 byte in Z_256",
        },
        "per_message_known": {
            "p_i": "n known plaintext bytes (chosen/known by the attacker)",
            "c_i": "n known ciphertext BODY bytes (header/nonce/tag excluded per experimental validity rules)",
        },
        "per_message_derived_not_free": {
            "q_i_k": "p_i[pi(k)]",
            "u_i_k": "S[(q_i_k + u_i_{k-1} + a_k) mod 256], u_i_{-1} = iv_f",
            "c_i_k": "S[(u_i_k + c_i_{k+1} + b_k) mod 256], c_i_n = iv_b",
        },
        "key_structural_fact": (
            "u^(i) and c^(i) are deterministic functions of (S, pi, a, b, iv_f, iv_b, p^(i)); "
            "they are not independent free variables. The problem is a constraint-satisfaction "
            "search over (S, pi, a, b, iv_f, iv_b), not a linear system to invert."
        ),
        "equations_per_message": "2n byte-equality constraints (n forward S-applications implicitly "
                                  "checked via the final backward output matching c_i exactly over all n positions)",
        "bijectivity_constraints": {
            "S": "256 values must be a permutation of {0..255} (S injective & total)",
            "pi": "n values must be a permutation of {0..n-1}",
        },
        "cross_message_sharing": "S, pi, a, b, iv_f, iv_b are IDENTICAL across all M messages "
                                   "(this is the nonce-reuse premise); only p^(i) (hence q^(i), "
                                   "u^(i), c^(i)) vary per message.",
        "success_criterion": (
            "NOT exact recovery of (S, pi, a, b, iv_f, iv_b). Success = recovering ANY tuple "
            "(possibly a different, functionally-equivalent tuple) that correctly predicts "
            "c^(target) from p^(target), or equivalently decrypts an unseen c^(target) to the "
            "correct p^(target), for a message not among the known pairs."
        ),
    }


def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    formulation = build_formulation()
    path = os.path.join(config.RESULTS_DIR, "constraint_formulation.json")
    with open(path, "w") as f:
        json.dump(formulation, f, indent=2)
    print("wrote", path)


if __name__ == "__main__":
    main()
