# Documentation and portability audit (Stage 3)

Status: audit **VERIFIED**; documentation changes **REQUIRES APPROVAL / not applied** (proposals only).

## Root README (`README.md`, 1,757 bytes)
Accurate and modest, but missing: installation/environment, dependency tiers, how to reproduce each experiment, where raw data live, third-party attribution (fdlibm, NIST STS), citation/license, limitations list (only a one-line disclaimer). Proposed additions: `proposed/README_additions.md`. No LICENSE file exists for the project's own code — the project license is an author decision and is **not** chosen here.

## `isc_pbl/PROJECT_STATUS_SUMMARY.md`
Header states "Generated: 11 November 2026" yet it is the pre-3B summary: no Phase 3B–5 results appear in it (grep for "3B/Phase 4/Phase 5" returned no hits in the first lines checked). It also describes paths as `C:\Users\bhoom\Desktop\ISC_PBL`. Proposal: replace with a status page that points to `experiments/phase5/PHASE_5_FINAL_EVIDENCE_REPORT.md` and this follow-up (see the final report). Not rewritten: the original is a historical document and the user must approve replacing it.

## Cross-repository specifications — VERIFIED present
All five documents cited by `isc_cipher/{cipher,container,kdf}.py` exist in GitHub under `isc_pbl/`: `container_v2_binary_specification.md`, `extraction_backend_compatibility_specification.md`, `hkdf_profile_binding_specification.md`, `phase_3a_implementation_plan.md`, `phase_3b_validation_readiness.md` (hash-identical to ISC_PBL). They are referenced by bare filename in code comments; **proposed** to add the prefix `isc_pbl/` (comment-only change; not applied) — authoritative copy = `isc_pbl/`.

## Hardcoded paths
| Location | Finding |
|---|---|
| `experiments/phase3b/finalize_deliverables.py:8` | `ISC_PBL = r"C:\Users\bhoom\Desktop\ISC_PBL"` — **still exists on this machine**; script copies 3 CSVs + JSON there with backslash-joined strings and reads `../../phase_3b_results_build.json` relative to cwd (that file is not on GitHub). Not portable; destination semantics = "write deliverables into the ISC_PBL folder". |
| `isc_cipher_kat/oracle/build/BUILD_INFO.txt` | records build path `/mnt/c/Users/bhoom/...` (provenance record, harmless). |
| `experiments/phase5/*.md`, `isc_pbl/*.md` | Windows paths in prose/links (documentation only). |
| Other `*.py` | no other absolute paths found by grep of `C:\Users`, `bhoom`, `Desktop`. |

Proposed portable form (`proposed/finalize_deliverables_portable.py`): same copy semantics, destination from `--dest` (default `<repo>/isc_pbl`), `pathlib` joins, input JSON path via `--build-json`. Original file left untouched. Note: on GitHub, `isc_pbl/` already contains the deliverables, so the script is a historical record and need not be re-run.

Not audited here: working-directory assumptions in the other experiment scripts (several use relative `raw/...` paths and must be run from their own directory).
