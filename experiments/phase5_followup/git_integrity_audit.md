# Git integrity audit (Stage 2)

Status: **VERIFIED** (inspected 2026-11-12; read-only, no Git mutation performed).

| Item | Finding |
|---|---|
| ISC_PBL, sine_chebyshev_ikeda_analysis | Not Git repositories (no `.git`). |
| ISC_IEA | Branch `main`, remote `origin` = https://github.com/BhoomiSaraf/ISC_IEA.git; 1 commit `b99633c`; no tags; no other branches. |
| Working tree at start | clean; now only `experiments/phase5_followup/` untracked. |
| Tracked files | 4,668 (3,913 under `results/`); ~72 MB content; no tracked caches. |
| Largest tracked files | 16 MB `results/encryption_experiments/A11_*/raw/E{1,2}/math_traj.bin` (x3); 12.5 MB bitstreams under `results/sequence_generation/default_20261025/bitstreams/`. All far below GitHub's 100 MB limit. |
| `.gitignore` | has caches, venvs, `.env`, NIST STS build/download/src, paper full texts. Missing: `.mypy_cache/ .ruff_cache/ *.egg-info/ .vscode/ .idea/`. Raw results correctly not ignored. |
| Git LFS | Not warranted (max 16 MB); keeping raw evidence in plain git preserves reviewer access. |

## History statement
The single commit is a **baseline snapshot**, not a record of phase milestones. Phase provenance lives in the reports (`isc_pbl/phase_*`, `experiments/phase5/evidence_inventory.md`) and file dates, not in Git. No history should be back-dated. If an earlier snapshot exists in the Desktop zips (not examined) it could be committed on a clearly labelled branch/tag — **requires approval**.

## Proposed commit sequence (not executed)
1. Reproducibility files (requirements, README/status refresh, `.gitignore` additions)
2. Phase 5 follow-up: reconciliation and housekeeping audits
3. Lyapunov recomputation
4. Phase 3B chi-square investigation
5. Further results as each stage completes (NIST STS, AEAD, dataset, benchmark, nonce-reuse)

No commit or push was made in this task.
