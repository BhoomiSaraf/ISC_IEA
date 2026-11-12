# Duplicates, backups, caches, size (Stage 4)

Status: duplicates **VERIFIED** by SHA-256. No file deleted or moved; any removal is **REQUIRES APPROVAL**.

| Artifact | Copies | SHA-256 | Authoritative | Notes |
|---|---|---|---|---|
| `ISC_PBL_Evaluation_...Updated.pptx` (8.3 MB) | ISC_PBL, cipher repo, GitHub root | identical (a19d26b7...) | GitHub root | not referenced by code |
| `Ikeda_Sine_Chebyshev_Map_Analysis.pdf` (0.9 MB) | same three | identical (90ba39b1...) | GitHub root | |
| `Madhu_MTAP_SecondPaper (2).pdf` | ISC_PBL, cipher repo | identical (851fe846...) | keep off GitHub | third-party copyright |
| `script/` (3), `plots/` (24) | ISC_PBL, cipher repo, GitHub root | identical per file | GitHub root | legacy scripts regenerate plots |
| `phase_3b_results_build.json` vs `isc_pbl/phase_3b_results.json` | cipher repo / ISC_PBL | bytes differ, parsed JSON equal | `isc_pbl/phase_3b_results.json` | `experiments/phase3b/finalize_deliverables.py` reads the `_build` file (not on GitHub) and writes the other |

Inside GitHub there is no internal duplication of these; the ~15 MB duplication existed only across the two original folders.

## Historical backups — keep
`isc_pbl/isc_sequence_characterization_v1_backup.py`, `isc_pbl/isc_sequence_characterization_step1_1_v1_backup.py`, `isc_pbl/results/sequence_characterization_v1_backup/` are pre-freeze v1 artifacts: **historical evidence**, already preserved in Git. Do not delete; moving to an `archive/` directory is optional and needs approval (docs cite current paths).

## Caches
`__pycache__`/`.pytest_cache` exist locally; all are `.gitignore`d; none tracked; not removed.

## Size
Tracked ≈ 72 MB (3,913 result files). Working tree incl. `.git` ≈ 406 MB. Local-only ignored: `third_party/nist_sts` (≈144 MB in the cipher repo).
