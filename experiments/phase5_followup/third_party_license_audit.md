# Third-party license audit (Stage 4)

Method: read the files and notices; recomputed hashes; no license inferred from a project's name.

## fdlibm 5.3 — `third_party/fdlibm/netlib_5.3/` — VERIFIED
- Upstream: Netlib fdlibm 5.3, https://www.netlib.org/fdlibm/ (retrieval timestamps in `RETRIEVED_UTC.txt`).
- All 10 `.c` files and `fdlibm.h` carry Sun Microsystems' notice ("Permission to use, copy, modify, and distribute this software is freely granted, provided that this notice is preserved"). The bundled `SHA256SUMS.txt` is present. The `readme` is Sun's release note, not a license.
- The Python ports `isc_cipher/fdlibm_ref.py` and `fdlibm_np.py` are derivative; the root README does not yet credit fdlibm. **Proposed** (not applied): add an attribution line.

## NIST STS 2.1.2 — `third_party/nist_sts/` (not in Git) — REQUIRES MANUAL LICENSE VERIFICATION
- Upstream archive `sts-2_1_2.zip`; local SHA-256 recomputed = `0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157` (matches `third_party/nist_sts/README.md`).
- 62 source files; **no LICENSE/COPYING file**. The only license-type statement found is in `src/dfft.c` (those Fourier routines "released to the public domain"). Nothing equivalent for the rest. Its legal status is not established here.
- Mitigation: the tree is `.gitignore`d, so GitHub does not redistribute it; only the README (URL, hash, rebuild steps) is tracked.

## Other excluded third-party material
`research/sources/fulltext/*` and `Madhu_MTAP_SecondPaper (2).pdf` are cited papers; correctly kept out of GitHub.

## Python dependencies
Installed, not vendored (numpy, scipy, matplotlib, pandas, scikit-image, scikit-learn, cryptography, nistrng, mpmath, z3). Their licenses were not reviewed here; `nistrng` 1.2.3 in particular is unreviewed.

No third-party files were removed.
