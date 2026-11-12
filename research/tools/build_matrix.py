"""Write research/literature_matrix.csv.

Rows are entered by hand from what was actually read (see 'evidence'). Bibliographic
columns (title, authors, year, venue, DOI) are filled from the verified records in
research/sources/, never typed by hand. 'not stated in abstract' / 'full text not read'
mark information that was not verified.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)

NA = "not determinable (full text not read)"

# key: (evidence, map/system, key initialisation, sequence generation, permutation, diffusion,
#       decryption, metrics, attack models considered, reported strengths, identified limitations,
#       relation to this project)
ROWS = {
    "sharma2022hsm": ("full text read (supplied PDF)", "2D Hénon-Sine map (2D-HSM)",
        "256-bit key split into eight 32-bit words; XOR pairs -> 16 subkeys mapped (mod 1) to ICs and parameters of two 2D-HSM instances",
        "two chaotic matrices S1, S2 of image size (8-bit elements)",
        "two rounds of confusion with roles of S1/S2 swapped", "diffusion inside each round plus an embedded diffusion between rounds",
        "reverse order of the encryption steps", "histogram, correlation, key sensitivity, NPCR/UACI, local Shannon entropy, speed",
        "key sensitivity, differential (NPCR/UACI); no executed KPA/CPA attack", "large nominal key space (2^256); 1-pixel random border makes ciphertexts differ per run",
        "security argued from statistics; random border adds randomness without a defined nonce model",
        "reference workflow only; its key mapping, border, round structure and diffusion are explicitly NOT reused"),
    "chebsine2019": ("abstract only", "2D Chebyshev-Sine map", NA, NA, "row shift and column mixing ('linear mixed layer')",
        "Chinese-remainder-theorem based diffusion", NA, "chaos ranges, trajectory, statistics (per abstract)",
        "differential and chosen-plaintext resistance claimed (per abstract)", "wide chaotic range, ergodicity (per abstract)",
        "abstract states 'low time efficiency'", "closest Chebyshev+Sine composition; different map (no Ikeda stage) and different cipher"),
    "lu2025sinecheb": ("abstract only", "2D improved Sine-Chebyshev map (2D-ISCM)", NA, NA,
        "cellular-automata permutation with plaintext-adaptive evolution rules; enhanced zigzag permutation",
        "two-way diffusion", NA, "security and performance experiments (per abstract)", NA,
        "enhanced randomness and parameter range (per abstract)", "plaintext-adaptive rules (a pattern repeatedly attacked in the cryptanalysis literature)",
        "closest Sine+Chebyshev map in recent work; slide deck cites it with wrong authors (Lu, Xie) - registry lists Zhang, Chai, Cao, Gan, Lu, Xie"),
    "sineikeda2023": ("full text read (publisher OA PDF)", "Sine-Ikeda modulated map: Ikeda map plus additive l*sin(pi*x_n), l*sin(pi*y_n)",
        "seed ICs fixed in the paper (x0=1.8888887, y0=0.9234567); harmonic means of generated sequences become new seeds; control parameters changed each iteration",
        "chaotic sequences used directly as keys", "not part of the paper (key generator only)", "not part of the paper",
        "not applicable", "bifurcation, Lyapunov exponent, cycle length, ApEn, NIST SP 800-22 (100 x 10^6 bits, alpha 0.001)",
        "none executed", "hyperchaotic, wide parameter range (per authors)",
        "no encryption scheme; additive sine modulation differs from ISC's Ikeda -> sin -> T2 composition",
        "closest Ikeda+sine map; ISC differs structurally (composition, Chebyshev T2 stage)"),
    "ikedahenon2017": ("abstract only", "Ikeda map (permutation) + Hénon map (gray-level change)", NA, NA,
        "rows and columns shuffled by Ikeda map, applied twice (before and after substitution)", "gray levels changed by Hénon map",
        NA, "key sensitivity, statistical tests (per abstract)", NA, "efficiency (per abstract)", NA,
        "closest Ikeda-based image cipher found; Ikeda used only for row/column shuffling"),
    "cao2013lhi": ("abstract only", "hybrid chaotic map (constituents not stated in abstract)",
        "MD5 used as part of initial condition and control parameter", NA, NA, NA, NA, "security, robustness, efficiency (per abstract)",
        "plaintext-chosen and differential attacks named as motivation", "embedding into carrier images",
        "slide deck lists authors 'Cao, C.; Li, K.; Chang, Q.' but Crossref/OpenAlex list a single author, Yang Cao",
        "plaintext-hash-dependent initialisation pattern"),
    "hikal2020": ("abstract only", "mixture of chaotic maps (slide deck: Ikeda, Arnold cat, enhanced Lorenz; not confirmed from abstract)",
        NA, NA, NA, NA, "explained and formulated (per abstract)", "statistical, brute force, differential (per abstract)",
        "statistical, brute-force, differential", "large key space, real-time speed (per abstract)", NA,
        "hybrid-map palmprint cipher; not a single 2D composed map"),
    "hua2019cosine": ("abstract only", "cosine-transform-based chaotic system (CTBCS) built from two seed maps", NA, NA,
        "high-efficiency scrambling separating adjacent pixels", "random-order substitution spreading a change to all pixels", NA,
        "chaos complexity; security comparison (per abstract)", NA, "complex dynamics", NA,
        "composition of maps via a cosine transform: related 'map composition' idea"),
    "zhu2018sha256": ("abstract only", "chaos + SHA-256",
        "SHA-256 of the plaintext generates a padding sequence; plaintext-related disturbance added to chaotic sequence", NA,
        "scrambling with plaintext-dependent sequence", "cipher/plaintext feedback with dynamic index", NA, "key space, key sensitivity, ... (per abstract)",
        "chosen-plaintext resistance claimed", "per-plaintext keystreams", "decryptor must obtain plaintext-dependent data (key-management issue)",
        "representative plaintext-hash-dependent design; this project uses a public nonce instead"),
    "medical2026chacha": ("abstract only", "none (ChaCha20)",
        "HKDF from shared master secret and fresh session nonce -> independent encryption, permutation, authentication keys",
        "ChaCha20 keystream", "keyed permutation (per abstract)", "chained diffusion", NA, "avalanche etc. (per abstract)", NA,
        "plaintext-independent, authenticated, standards-based", NA,
        "closest envelope: HKDF + nonce + chained diffusion + HMAC already published; our ISC envelope is not novel"),
    "jcta2025blockauth": ("abstract only", "DNA-chaos core",
        "X25519 session secret expanded by HKDF-SHA256 into four domain-separated subkeys; chaotic seeds from plaintext hash and block coordinates",
        NA, "permutation (subkey)", "DNA operations and diffusion (subkeys)", NA, NA, NA,
        "block-wise encrypt-then-MAC (truncated HMAC-SHA256), tamper localisation", NA,
        "prior use of HKDF domain separation + EtM around a chaotic core"),
    "farajallah2016auth": ("abstract only", "modified 2D cat map (confusion) + 32-bit logistic / modified skew tent map (diffusion)",
        NA, NA, "modified 2-D cat map", "logistic or finite skew tent map", NA, NA, NA, "speed, robustness (per abstract)", NA,
        "integer-domain chaotic layers (avoids floating point)"),
    "fridrich1998": ("abstract only", "discretised invertible 2D maps (Baker map example)", NA, NA,
        "discretised chaotic map acting as a permutation", "simple diffusion mechanism composed with the permutation", NA, NA, NA,
        "origin of the permutation-diffusion architecture", "discretised map is a permutation, not chaotic",
        "background for confusion-diffusion structure"),
    "solak2010fridrich": ("abstract only", "Fridrich's scheme", "-", "-", "-", "-", "-", "-", "chosen-ciphertext attack revealing the secret permutation",
        "-", "algebraic weaknesses", "permutation-recovery attacks to test"),
    "xie2017fridrich": ("bibliographic record only", "Fridrich's scheme", "-", "-", "-", "-", "-", "-", "cryptanalysis (title)", "-", NA, "permutation-diffusion cryptanalysis"),
    "li2008permutation": ("bibliographic record only", "permutation-only ciphers (general)", "-", "-", "-", "-", "-", "-",
        "known/chosen-plaintext (title)", "-", "permutation-only ciphers break under plaintext attacks (title)", "permutation alone insufficient"),
    "jolfaei2016": ("abstract only", "permutation-only image ciphers (general)", "-", "-", "-", "-", "-", "-",
        "chosen-plaintext: permutation recovered completely regardless of structure", "-",
        "all permutation-only ciphers broken by CPA with a bounded number of chosen images", "motivates mandatory diffusion and nonce-dependent permutation"),
    "entropy2022crypt2dhyper": ("abstract only", "2D hyperchaotic map scheme (attacked)", "-", "-", "permutation", "forward + backward diffusion", "-", "-",
        "CPA and CCA; diffusion reduces to two simple diffusions + modular addition; equivalent key recovered (<2 h for 256x256)", "-",
        "complex-looking diffusion was algebraically simple", "pattern our attack suite must test"),
    "entropy2023crypt2dhyper": ("abstract only", "2D hyperchaotic map from two 1D maps (attacked)", "-", "-", "row-column permutation",
        "forward + backward diffusion with ciphertext feedback", "-", "-",
        "CPA: diffusion equivalent to global diffusion; plaintext-independent sequences let equivalent keystreams be read off", "-",
        "ciphertext feedback did not prevent CPA", "plaintext-independent keystream under fixed key is the weakness a nonce must remove"),
    "li2018entropy": ("full text read (arXiv)", "chaotic cipher with information-entropy-based sensitivity (attacked)", "-", "-", "-", "-", "-",
        "evaluated the paper's metrics", "differential attack recovers equivalent key of each operation (1 round)", "-",
        "short orbits of digital chaos; invalid plaintext-sensitivity mechanism; questionable metrics", "lessons list"),
    "li2018autoblocking": ("full text read (arXiv)", "chaotic cipher with ECG-derived key and autoblocking (attacked)", "-", "-", "-", "-", "-", "-",
        "known-plaintext: one pair yields an equivalent mask key", "-", "equivalent key from one known pair", "KPA test required"),
    "embedded2019crypt": ("abstract read (arXiv)", "3rd-order hyperbolic sine chaotic system (attacked)", "-", "-", "sort-based permutation", "-", "-", "-",
        "differential (2 chosen images) and CPA (one 3x400 image exploiting sort stability)", "-", "sort-based permutation leaks", "avoid sort-based index generation"),
    "li2019yearreview": ("full text read (arXiv)", "survey of 2018 image ciphers and attacks", "-", "-", "-", "-", "-", "-", "-", "-",
        "misused security metrics; ignored lessons; weak digital PRNG periods unanalysed; no application scenario", "checklist for our design and paper"),
    "preishuber2018": ("abstract only", "survey + constructed insecure ciphers", "-", "-", "-", "-", "-",
        "common statistical tests", "-", "-", "tests are necessary but not sufficient; insecure schemes pass them; speed/security motivations questionable",
        "motivates attack-driven evaluation and AEAD baseline"),
    "alvarez2006": ("full text read (arXiv)", "guidelines", "-", "-", "-", "-", "-", "-", "-", "-",
        "14 rules: define key, key space, key generation, digital degradation, KPA/CPA, chaos-specific attacks, key space > 2^100",
        "design checklist"),
    "reliability2019devices": ("full text read (arXiv)", "Cubic map", "-", "-", "-", "-", "decryption across devices",
        "-", "-", "-", "two IEEE-754 compliant devices produced different keys; decryption failed",
        "cross-platform reproducibility is a correctness requirement for ISC (sin/cos)"),
    "grebogi1988": ("abstract only", "chaotic attractors under round-off", "-", "-", "-", "-", "-", "-", "-", "-",
        "expected period scales as eps^(-d/2) (d: correlation dimension)", "frame for ISC finite-precision cycle results"),
}


def main():
    bib = {r["key"]: r for r in csv.DictReader(open(os.path.join(RESEARCH, "sources", "bibliography.csv"), encoding="utf-8"))}
    ver = {r["key"]: r for r in csv.DictReader(open(os.path.join(RESEARCH, "sources", "verification.csv"), encoding="utf-8"))}
    cols = ["key", "title", "authors", "year", "venue", "doi", "evidence", "map_or_system", "key_initialisation",
            "sequence_generation", "permutation", "diffusion", "decryption", "evaluation_metrics", "attack_models",
            "reported_strengths", "identified_limitations", "relation_to_this_project"]
    out = []
    for k, vals in ROWS.items():
        b = bib.get(k) or ver[k]
        out.append(dict(zip(cols, [k, b["title"], b["authors"], b["year"], b["venue"], b["doi"]] + list(vals))))
    with open(os.path.join(RESEARCH, "literature_matrix.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(len(out), "rows")


if __name__ == "__main__":
    main()
