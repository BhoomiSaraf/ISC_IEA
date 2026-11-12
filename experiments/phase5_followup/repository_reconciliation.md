# Repository reconciliation (Stage 1)

Status: **VERIFIED** (read-only; SHA-256 per file). Script: `verification/reconcile.py`. Full matrix: `results/reconciliation_matrix.csv` (one row per path).

Command: `python experiments/phase5_followup/verification/reconcile.py --a ../ISC_PBL --b ../sine_chebyshev_ikeda_analysis --g . --out experiments/phase5_followup/results`

Sources actually inspected: all three local directories — `C:\Users\bhoom\Desktop\ISC_PBL`, `...\sine_chebyshev_ikeda_analysis`, `...\ISC_IEA` (checkout of GitHub `main` @ b99633c, clean). The GitHub remote itself was not separately fetched. No separate "uploaded archive" was identified; the zip files on the Desktop (`ISC_PBL.zip`, `sine_chebyshev_ikeda_analysis*.zip`) were **not opened or compared**.
Excluded from comparison: `.git`, `__pycache__`, `.pytest_cache`, `.venv`.

## Layout mapping
GitHub root = cipher-repo layout; ISC_PBL's content lives under `isc_pbl/`.

## Result: no file differs in content
| Comparison | IDENTICAL | DIFFERENT | Only in source | Only in GitHub |
|---|---|---|---|---|
| ISC_PBL vs GitHub `isc_pbl/` | 196 | **0** | 30 | 0 |
| Cipher repo vs GitHub root | 4,470 | **0** | 167 | 3 |

### Only in ISC_PBL (30) — all accounted for
- `ISC_PBL_Evaluation_...Updated.pptx`, `Ikeda_Sine_Chebyshev_Map_Analysis.pdf`: hash-identical to the copies at GitHub root.
- `Madhu_MTAP_SecondPaper (2).pdf`: third-party paper, deliberately not on GitHub; identical in both original folders.
- `plots/` (24 files), `script/` (3 files): byte-identical to the same directories in the cipher repo and at GitHub root (not repeated under `isc_pbl/`).

### Only in cipher repo (167)
| Group | n | Classification | Action |
|---|---|---|---|
| `third_party/nist_sts/{build_linux,download,src_pristine}` | 153 | third-party, excluded by `.gitignore` | keep out of git; rebuild by hash per `third_party/nist_sts/README.md` |
| `research/sources/fulltext/*` | 12 | third-party papers, excluded by `.gitignore` | keep out |
| `Madhu_MTAP_SecondPaper (2).pdf` | 1 | third-party paper | keep out |
| `phase_3b_results_build.json` | 1 | DUPLICATE (parsed-JSON-equal to `isc_pbl/phase_3b_results.json`; bytes differ in formatting) | see duplicate audit |

### Only in GitHub (3)
`.gitignore`, `README.md`, and this untracked follow-up directory.

## Conclusions
1. GitHub contains every eligible file from both original folders byte-for-byte; nothing is stale or divergent.
2. The only originals absent from GitHub are intentional exclusions (NIST STS tree, paper PDFs) and one duplicate JSON.
3. Consequence: the official STS `assess` binary behind `results/nist_sts_official/` cannot be rebuilt from GitHub alone; only the URL/SHA-256/rebuild steps are tracked.
4. Not verified: the Desktop zip files; the GitHub web copy beyond the local clean checkout.
