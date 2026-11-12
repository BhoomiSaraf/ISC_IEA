# Repository Migration Plan — Consolidating `sine_chebyshev_ikeda_analysis` into `ISC_PBL`

**Document ID:** `ISC-PHASE2-MIGRATION-2026-01`
**Date:** 11 November 2026
**Status:** Plan only. **No migration has been performed.** The sibling repository has not been moved,
copied, renamed, or modified in any way during this investigation.

---

## 1. Source-file inventory

`[VERIFIED SOURCE]`, from a recursive `*.py` listing of `C:\Users\bhoom\Desktop\sine_chebyshev_ikeda_analysis`
(reproduced in full in `phase_2_source_code_architecture_audit.md §1`):
- `isc_cipher/` — 13 files (production cipher).
- `isc_seq/` — 9 files (research extraction/trajectory/stats utilities, including `frac_byte`).
- `isc_eval/` — 17 files (comparative evaluation harness, attacks A1-A15).
- `isc_cipher_kat/` — 4 Python files + a `vectors/` data directory (KAT reproducibility).
- `tests/` — 13 test files + `conftest.py`.
- `research/` — 18+ markdown/CSV design and review documents, plus a `tools/` subfolder with 5 scripts.
- `script/` — 3 historical validation scripts (`analyze.py`, `final_validation.py`,
  `final_freeze_validation.py`) — **note:** these filenames are identical to three files that already
  exist, unmodified, in `ISC_PBL\script\` (confirmed by directory listing of both locations). This is a
  **naming collision that must be resolved explicitly during migration** (see §8).
- `experiments/` — 4 scripts (`analyze_official_sts.py`, `demo_show_keystream.py`, `run_official_sts.py`,
  `run_sequence_experiment.py`).
- `third_party/fdlibm/netlib_5.3/` — the vendored Netlib fdlibm 5.3 C sources + `SHA256SUMS.txt`, hashed
  and verified by `gate_r.py: check_fdlibm_hashes` (`gate_r.py:70-79`).
- `third_party/nist_sts/` — vendored official NIST Statistical Test Suite sources, including a
  `build_linux/` subdirectory (**platform-specific binary/build artifact — see §4**).

## 2. Runtime dependencies

`[EXECUTED]`, `pip show` on the environment used throughout this audit:
- Python 3.11.9 (MSC v.1938, 64-bit) — matches Phase 1's reported environment exactly.
- `numpy==2.4.6`
- `cryptography==50.0.0` (used by tests to cross-check HKDF against an independent implementation, per
  Phase 1's `existing_implementation_audit.md §4.1`; **not** a runtime dependency of `isc_cipher` itself —
  `kdf.py` uses only stdlib `hmac`/`hashlib`, confirmed by reading `kdf.py:8-10`).
- `pytest==9.1.1`
- `nistrng==1.2.3` (used by `isc_seq`/Step 1.1's own NIST evaluation, per `final_step1_1_closure_report.md §3`).

**No `setup.py`, `pyproject.toml`, or `requirements.txt` exists anywhere in the repository**
(`[EXECUTED]`, directory search at repo root found none). All dependency management is implicit —
whatever is installed in the active Python environment. **This is a migration risk in itself** (see §8)
independent of the directory move.

## 3. Test and fixture dependencies

`[VERIFIED SOURCE]`: `tests/conftest.py` (4 lines, quoted in full) inserts
`ROOT = dirname(dirname(abspath(__file__)))` onto `sys.path`, i.e. it assumes **the repository root is
exactly two directory levels above `conftest.py`** (`tests/conftest.py` → `tests/` → repo root). This same
pattern is repeated verbatim in `isc_cipher_kat/gate_r.py:22-23`, `gate_r_ext.py:20-21`,
`make_kat.py:26-27`, `make_kat_ext.py:25-27` (which additionally inserts `isc_cipher_kat` itself onto
`sys.path`), and `isc_eval/xplat_worker.py:18-19`. **Every one of these files will break if moved to a
different nesting depth relative to the repository root** — this is the single most important structural
constraint on any migration.

`isc_eval/common.py:11-12` additionally hardcodes `OUT_ROOT = os.path.join(ROOT, "results",
"encryption_experiments")` — an **output-path assumption**, not just an import-path assumption; any
migration must either preserve a `results/encryption_experiments/` directory relative to the new root or
accept that historical diagnostic outputs referenced by Phase 1's `test_coverage_audit.md §4` ("Historical
Gate A Experiment Diagnostics: Archived in `sine_chebyshev_ikeda_analysis/results/encryption_experiments/`")
move with it.

## 4. Binary / data KAT artifacts

`[VERIFIED SOURCE]`: `isc_cipher_kat/vectors/` contains `PROVENANCE.json`, `cipher_kat.json`,
`stream_kat.json`, `traj_kat.json`, `trig_accuracy_by_branch.json`, and two gzip-compressed files
(`trig_kat.txt.gz`, `trig_kat_ext.txt.gz`) — these are **data, not code**, and must be copied byte-for-byte
(no text-mode line-ending conversion, which would corrupt the gzip files) to preserve `gate_r.py`'s
ability to verify against them. `third_party/fdlibm/netlib_5.3/` contains the vendored C source files
whose SHA-256 hashes are checked at runtime (`gate_r.py: check_fdlibm_hashes`) — any migration process that
alters file contents (e.g. a `git` checkout with `autocrlf` line-ending conversion on these `.c`/`.h`
files) would **break this specific check**, a concrete, non-hypothetical migration risk.
`third_party/nist_sts/build_linux/` is a **platform-specific (Linux) build artifact** — its relevance on
the current Windows development machine is unclear and should be explicitly checked (is it used by
anything invoked on Windows, or is it dead weight from a different environment the project was also
developed on?) before deciding whether to migrate it as-is, exclude it, or document it as
Linux-CI-only. `[OPEN QUESTION, not resolved in this pass]`

## 5. Environment/configuration dependencies

`[VERIFIED SOURCE + ANALYSIS]`: No `.env`, config file, or environment-variable dependency was found
referenced in any inspected file (`kdf.py`, `generator.py`, `cipher.py`, `gate_r.py`, `selftest.py` all use
only function arguments and hardcoded constants). The only "configuration" in the research track is
`ISC_PBL\results\sequence_characterization\configuration.json`, which belongs to the Step 1.1 workspace,
not the cipher repository, and must not be touched per the task's explicit restriction.

## 6. Relative-path assumptions (consolidated from §3-4)

All of: `tests/conftest.py`, `isc_cipher_kat/gate_r.py`, `gate_r_ext.py`, `make_kat.py`, `make_kat_ext.py`,
`isc_eval/common.py`, `isc_eval/xplat_worker.py` assume a **fixed two-level nesting depth below the repo
root**. A migration that preserves the *entire subtree* (`isc_cipher/`, `isc_seq/`, `isc_eval/`,
`isc_cipher_kat/`, `tests/`, `third_party/`, `research/`, `experiments/`) as a single unit, placed at a new
location, with all of these directories remaining **direct children of the same new root**, requires **no
code changes** to any of these path computations. A migration that instead tries to merge individual files
into `ISC_PBL`'s existing flat layout (mixing cipher files directly into `ISC_PBL`'s root alongside
`isc_sequence_characterization.py`) **would break every one of the `ROOT = dirname(dirname(...))`
computations** and must not be done without rewriting those lines.

## 7. Package imports that may break after migration

`[VERIFIED SOURCE]`: internal imports are all relative-package style within `isc_cipher`
(`from . import container, diffusion, sampling`, `cipher.py:15`) or absolute-from-root style elsewhere
(`from isc_cipher import kdf`, `gate_r.py:24`; `from isc_seq.extract import frac_byte`, as used in this
audit's own verification script). **Both styles depend on the repo root being on `sys.path`** — which is
arranged today by each entry-point script's own `sys.path.insert` (§3) or by `pytest`'s own rootdir
discovery via `conftest.py`. As long as the whole subtree moves together (§6), these imports resolve
identically at the new location; no import statement needs editing.

## 8. Naming collision: `script/` directory

`[VERIFIED SOURCE]`: Both `ISC_PBL\script\` and `sine_chebyshev_ikeda_analysis\script\` contain files
named `analyze.py`, `final_validation.py`, and `final_freeze_validation.py`. Per Phase 1's
`existing_implementation_audit.md §2` and this project's own stated history, `ISC_PBL`'s copies are the
"historical reference scripts, Sept 2026" that Step 1.1 explicitly preserved and must not be disturbed.
**A migration must not let the cipher repo's `script/` directory overwrite or merge with `ISC_PBL`'s
existing `script/` directory.** Recommendation (see §9): place the migrated cipher repository under its
own clearly-named subdirectory inside `ISC_PBL` (e.g. `ISC_PBL\cipher\` or `ISC_PBL\isc_img_v1\`), not
merged into `ISC_PBL`'s existing top-level layout, so this and any other naming collision is structurally
avoided rather than requiring per-file collision resolution.

## 9. Recommended unified repository structure

`[RECOMMENDATION]`:
```
ISC_PBL/                                  (existing root, git-initialized per §11)
├── (all existing Step 1.1 files, UNCHANGED — isc_sequence_characterization.py, results/, script/,
│    plots/, the 8 Phase 2 audit docs, etc.)
└── cipher/                               (NEW — the entire sine_chebyshev_ikeda_analysis subtree,
    │                                       moved as one unit, preserving internal nesting depth)
    ├── isc_cipher/
    ├── isc_seq/
    ├── isc_eval/
    ├── isc_cipher_kat/
    ├── tests/
    ├── third_party/
    ├── research/
    ├── experiments/
    └── script/                           (the cipher repo's OWN historical scripts — distinct directory
                                            from ISC_PBL/script/, no collision, both preserved)
```
This satisfies: (a) §6's nesting-depth constraint (every `ROOT = dirname(dirname(...))` inside the moved
subtree still resolves to `ISC_PBL/cipher/`, not `ISC_PBL/`, since the internal structure is unchanged —
**only the single mount point moves**); (b) §8's naming-collision avoidance; (c) the task's explicit
requirement to not modify the frozen Step 1.1 artifacts (none of them are touched, since they live outside
`cipher/`).

## 10. Commands needed to run Gate C, Gate A, Gate R from the consolidated repository

`[DERIVED from §6-7]`, assuming the structure in §9:
```
cd ISC_PBL/cipher
python -m pytest tests/test_isc_cipher_*.py        # Gate C
python -m pytest tests/test_isc_eval_harness.py     # Gate A
python -I isc_cipher_kat/gate_r.py --backend numpy --label <run-label>   # Gate R
```
identical to the commands used throughout this audit and Phase 1's audit, because the `ROOT`
auto-detection in each entry point recomputes correctly relative to wherever `cipher/` ends up, as long as
its own internal structure (§6) is preserved. **No command-line changes are needed**, only the `cd`
target, under the recommended structure.

## 11. Version control recommendation

`[VERIFIED SOURCE + RECOMMENDATION]`: Neither `ISC_PBL` nor `sine_chebyshev_ikeda_analysis` is currently a
git repository (confirmed by the environment metadata for `ISC_PBL`: "Is a git repository: false"; not
independently re-checked for the sibling repo in this pass, but no `.git` directory was observed in any
directory listing of it either — `[UNVERIFIED for the sibling repo specifically, flagged rather than
assumed]`). **Recommendation, per the task's own instruction**: initialize git **before** performing the
physical migration or any further implementation change, so that: (a) the migration itself is one
reviewable, revertible commit; (b) the existing manual `_v1_backup` file-copy discipline (already used
throughout `ISC_PBL` for Step 1.1 preservation) can be supplemented, not replaced, by proper branch/tag
history; (c) any accidental overwrite (e.g. the `script/` collision in §8) is trivially recoverable.
Suggested sequence: `git init` in `ISC_PBL` → commit current state as a baseline → perform the migration
as a second commit → tag the pre-migration state (e.g. `pre-cipher-migration`) for easy reference.

## 12. Explicitly not done

No file has been copied, moved, renamed, or deleted in either repository as part of producing this plan,
per the task's Section 13 restriction.
