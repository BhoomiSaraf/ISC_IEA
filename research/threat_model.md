# Threat model and requirements: ISC-IMG v1 (revision 2)

Status: checkpoint 2, revision 2 (2026-10-26). Specification only, not implemented. The status labels
([IMPL], [TESTED], [PROVEN], [ASSUMED], [PROPOSED], [OPEN]) are those defined in `algorithm_design.md`.

## 1. Purpose and research framing

* ISC-IMG v1 is an **experimental** lossless image cipher. Its purpose is to *investigate* whether ISC-derived
  streams can serve as a keystream source inside a carefully engineered envelope, and to compare the result
  fairly with standard authenticated encryption.
* The ISC map is evaluated **as a component of an experimental cipher**, not proposed as a secure
  replacement for standard primitives. That stronger claim would need evidence this project cannot provide.
* For protecting real data, the recommendation is AES-256-GCM or ChaCha20-Poly1305 with unique nonces
  ([sp80038d], [rfc8439]), or AES-256-GCM-SIV where nonce reuse is a risk ([rfc8452]).

## 2. Supported data [PROPOSED]

| item | v1 |
|---|---|
| pixel type | `uint8` only; other dtypes are rejected |
| layouts | (H, W) grayscale or (H, W, 3), channel-last. Channel semantics (RGB/BGR) are not interpreted. Other channel counts are rejected. |
| limits | 1 ≤ H, W ≤ 65535, n = H·W·C ≤ 2^24 (this bounds lane lengths; `algorithm_design.md` §2) |
| shapes | any H, W within the limits, including 1×1, single row and single column; no padding |
| recovery | lossless: exact equality of shape, dtype and every element |
| files | the cipher works on arrays. The experiment code reads and writes lossless formats only. |

## 3. Secrets and public data

| item | secret? | specification |
|---|---|---|
| master key K | **yes** | 32 bytes from `os.urandom`; never logged or stored by the cipher [PROPOSED] |
| nonce N | no (public, authenticated) | 16 random bytes per encryption, generated internally [PROPOSED] |
| derived values (K_mac, K_kcv, iv, 256 lane seeds and initial states, S, π, streams) | yes, per message | functions of (K, N, header) through HKDF [PROPOSED] |
| algorithm, frozen ISC parameters (a = 0.9, c = 0.4, d = 6.0, ω = 10.0), profile, T, L | no | Kerckhoffs' principle |
| H, W, C, profile, version, KCV, tag | no (authenticated) | header (`algorithm_design.md` §10) |

## 4. Adversary

The adversary knows the specification and code, and sees every ciphertext.

| capability | used in experiments as |
|---|---|
| ciphertext-only | ciphertexts and headers |
| known plaintext (KPA) | (P, C, N) triples under the same K |
| nonce-respecting chosen plaintext (CPA) | encryption oracle; nonces chosen randomly by the encryptor |
| nonce-misusing chosen plaintext | the adversary forces one nonce for several chosen plaintexts. This models RNG failure, VM snapshot replay, or the deterministic "fixed key, no nonce" setting common in the literature. Outside the security model, but measured. |
| chosen ciphertext (CCA) | decryption oracle returning `reject` or the plaintext |
| tampering, truncation, replay, reordering | yes |
| computation | classical. Target 2^100 operations for "practical" attacks in the experiments; quantum adversaries are out of scope. |

Out of scope: side channels (except a constant-time tag comparison), key storage and distribution,
compromised endpoints, metadata privacy (dimensions are public), denial of service beyond input-size
limits, and traffic analysis.

## 5. Security goals: status and dependence on ISC

| goal | definition | status | depends on ISC? |
|---|---|---|---|
| **G-INT** integrity | no new (header, body, tag) is accepted | **[PROVEN]** under [ASSUMED] HMAC-SHA-256 PRF, by generic encrypt-then-MAC [bellare2008ae]: independent K_mac, tag over bytes [0, 36 + n), full 32-byte tag. Holds **even under nonce reuse**, because HMAC uses no nonce. | no |
| **G-CPA** confidentiality, nonce-respecting | IND-CPA for equal-shape images | **[OPEN], unproven.** Requires that ISC streams, S, π and a, b are unpredictable functions of per-message initial states. There is no reduction to any hard problem, and the effective security level is unknown (`algorithm_design.md` §5.4). | **yes** |
| **G-CCA** | IND-CCA | IND-CPA + INT-CTXT gives IND-CCA for encrypt-then-MAC [bellare2008ae]. **[OPEN]**, because G-CPA is. **HMAC cannot repair a weak encryption layer:** it stops forged or modified ciphertexts from being decrypted, but it does not hide the plaintext of honest ciphertexts. | yes |
| **G-KEY** | recovering K | K enters only HKDF-Extract. Recovering it from derived values requires breaking HKDF/HMAC [ASSUMED]. | no |
| **G-LANE** | recovering a lane's state for one message | **[OPEN]** (A4). Compromise exposes that message's stream bytes for the lane; other messages use unrelated seeds [ASSUMED HKDF]. | yes |
| **G-REPRO** | the same (K, N, header) gives the same streams on supported environments | **[OPEN]** until the KATs pass on E1 and E2 (A11). Run-time mismatch is reported by the KCV (`algorithm_design.md` §10.1). | yes (floating point) |
| **G-REPLAY** | replay detection | not provided (stateless), as for standard AEADs | no |

## 6. Nonce handling and the consequences of reuse

* **Generation.** N = `os.urandom(16)` inside `Encrypt`; no caller-supplied nonces in the public API
  [PROPOSED]. A test-only function in the attack harness allows forced reuse for experiment A1 only.
* **Uniqueness.** Probabilistic. For q encryptions under one key, P[some repeat] ≤ q(q−1)/2^129, which is
  below 2^-32 for q ≤ 2^48 [PROVEN, birthday bound for uniform N]. Reuse is not detectable by a
  stateless decryptor.
* **Exact consequences of reusing (K, N) with the same H, W, C, profile:**
  1. ctx and the HKDF inputs are identical, so S, π, a, b, iv and all lane states are identical. The
     encryption of the body becomes a **fixed deterministic permutation E of {0..255}^n** [PROVEN from
     the definitions].
  2. Equal plaintexts give equal bodies (equality leaks). The KCV is identical; tags differ only if the
     bodies differ.
  3. For different plaintexts, the backward pass makes every body byte depend on all u_k at positions
     k' ≥ k, and u_k depends on all q_{k'} with k' ≤ k. So two different images give bodies that differ
     almost everywhere. There is no XOR-of-plaintexts leak of the GCM/ChaCha20 kind, for V-FULL. This
     holds by construction, but it is **not a security claim**.
  4. The adversary can query E on chosen inputs. Attacks on deterministic permutation-diffusion
     ciphers (equivalent keys, codebooks for tiny n: for n = 1, E is a permutation of 256 values,
     recovered with 256 queries) then apply. Whether V-FULL is practically broken this way for
     realistic n is **[OPEN] (A1)**.
  5. Integrity (G-INT) is unaffected. Unlike GCM, reuse does not expose an authentication subkey.
* With reuse **across different dimensions**, ctx differs, so all derived values are unrelated
  (no structural relation is known).
* **Reference behaviour of the baselines.**
  * AES-GCM and ChaCha20-Poly1305 under nonce reuse leak p1 ⊕ p2. GCM additionally allows forgeries
    after reuse [bock2016nonce].
  * AES-GCM-SIV leaks only the equality of identical messages [rfc8452].

## 7. Guarantees of the baselines versus the experimental construction

| construction | confidentiality basis | integrity basis | status |
|---|---|---|---|
| AES-256-GCM [sp80038d] | AES as a block cipher; unique nonces | GHASH-based MAC; fails under nonce reuse | standardised; extensive public analysis |
| ChaCha20-Poly1305 [rfc8439] | ChaCha20 as a PRF; unique nonces | Poly1305 one-time MAC with per-nonce key | standardised; extensive public analysis |
| AES-256-GCM-SIV [rfc8452] | AES; misuse resistant (equality leak only) | as specified in RFC 8452 | standardised |
| V-CHACHA (our envelope, ChaCha20 streams) | ChaCha20 streams in our permutation-diffusion | HMAC encrypt-then-MAC | envelope [PROPOSED]; no published analysis of this composition |
| **ISC-IMG v1 (V-FULL)** | **ISC streams: unproven conjecture** | HMAC encrypt-then-MAC [PROVEN given HMAC PRF] | experimental |

Statistical tests, image metrics (entropy, correlation, NPCR/UACI) and HMAC authentication are **not**
evidence of the confidentiality of ISC-IMG v1, and are never presented as such.

## 8. Reproducibility requirements [PROPOSED]

* Deterministic encryption and decryption given (K, N, header, image).
* The profile id fixes floating-point semantics. Supported environments are E1 and E2 only, after the
  KATs pass (`algorithm_design.md` §7.3-7.4).
* Experiments record source hashes, dependency versions, OS, CPU flags and image hashes, and never K.
* Published known-answer vectors use a labelled public test key.

## 9. Performance targets (non-binding)

Encryption of a 512×512×3 image in under 30 s on E1 (research prototype). No speed advantage over
standard AEADs is expected or claimed.

## 10. Assumptions

1. HMAC-SHA-256 is a PRF; HKDF-SHA-256 is a secure KDF [ASSUMED, standard].
2. `os.urandom` output is uniform and unpredictable [ASSUMED, platform].
3. ISC-derived streams are unpredictable to the adversary [**research conjecture, unproven**].
4. Implementations conform to profile 1 [checked by KAT and KCV; not proven].
5. Nonces are not reused under one key [probabilistic; not enforced].
