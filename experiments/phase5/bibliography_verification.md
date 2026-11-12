# Phase 5 — Bibliography Verification

Source: `research/sources/bibliography.csv` (87 entries) and `research/references.md`, both pre-existing in Repo B with their own CrossRef-verification tooling (`research/tools/verify_references.py`, `research/tools/crossref_fetch.py`).

## Verification status (re-read directly in this phase, not re-run against CrossRef live)

- **87 total bibliographic entries.**
- **85/87 (97.7%) carry no recorded `crossref_error`** — i.e., were previously resolved against CrossRef by the repository's own tooling with a successful DOI match.
- **2/87 entries have a recorded error**, already flagged by the existing tooling, not newly discovered here:
  - `satellite2024review` — CrossRef HTTP 404 (DOI/entry not found)
  - `arroyo2008logistic` — CrossRef HTTP 404 (DOI/entry not found)

These two entries require either a corrected DOI/key or removal before manuscript submission — **flagged, not fixed, in this phase** (fixing a citation is in-scope for manuscript preparation, which is explicitly out of scope for Phase 5).

## Categories present (spot-checked by key-name sampling, not every row individually re-read in full)

- Original chaotic-map / chaos-based cryptography literature (e.g. `fridrich1998`, `chen2004cat`, `kocarev2001`)
- Information theory foundation (`shannon1949`)
- Image-encryption evaluation methodology (NPCR/UACI/entropy papers — present by key-name pattern, not individually re-verified against their cited formulas in this phase)
## Foundational citations confirmed present (checked directly in this pass)

HKDF: `rfc5869` (Krawczyk & Eronen 2010) and `krawczyk2010` (the HKDF scheme paper). HMAC: `rfc2104` (Krawczyk, Bellare, Canetti 1997). NIST SP 800-22: `sp80022` (Bassham et al. 2010). SHA-256: `fips1804`. AES (needed for the Phase 4D S-box DDT/LAT comparison baseline): `fips197`. Nonce-misuse resistance: `rfc8452` (AES-GCM-SIV) — directly relevant to the Phase 4D/4E nonce-reuse discussion. Two recent (2026) image-encryption-with-HKDF/HMAC papers (`medical2026chacha`, `jcta2025blockauth`) are also present and relevant to related-work framing.

## What this phase did NOT do

- Did not re-run `verify_references.py` live against CrossRef (no new network verification was performed; relied on the pre-existing `crossref_error` column's prior run).
- Did not verify that every citation's claimed content actually supports the specific sentence it would be attached to in a future manuscript — that is a manuscript-writing-time task, not a Phase 5 evidence-consolidation task.
- Did not invent, add, or remove any bibliography entries.
