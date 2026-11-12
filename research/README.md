# research/

Literature survey and design documents for the ISC image-encryption phase.

| file | content |
|---|---|
| `literature_review.md` | review across the 14 required areas, with an evidence level for every source |
| `literature_matrix.csv` | 27 structured rows; bibliographic columns come from the verified records, design columns only from what was read (`evidence` column) |
| `research_gap_analysis.md` | non-gaps, comparison with the closest work, defensible gaps G1-G5, risks |
| `proposed_contribution.md` | recommended direction A, alternatives B/C, explicit non-claims, open decisions |
| `threat_model.md` | purpose, data, keys/nonces, adversary, goals and whether each is provable or conjectured (checkpoint 2) |
| `algorithm_design.md` | ISC-IMG v1 specification: dependency chain and implementation status, equations, pseudocode, format, reversibility proof (checkpoint 2) |
| `design_comparison.md` | provenance of each element, closest methods, baselines, benefit hypotheses B1-B6, assessment of ISC as a keystream source (checkpoint 2) |
| `attack_plan.md` | pre-registered gates, attacks A1-A14, stop and redesign rules (checkpoint 2) |
| `checkpoint2_review_response.md` | issue-by-issue response to the checkpoint-2 review (revision 2 of the design) |
| `tools/check_spec_example.py` | standalone check of the hand-worked example in `algorithm_design.md` §12.1 (not cipher code) |
| `references.md` | 91 verified references (generated) |
| `sources/verification.csv` | OpenAlex verification status of every candidate |
| `sources/bibliography.csv` | Crossref metadata for every DOI |
| `sources/openalex/`, `sources/crossref/` | raw registry responses (cached, never overwritten) |
| `sources/abstracts.md` | abstracts reconstructed from OpenAlex, for reading only |
| `sources/fulltext/` | open-access texts that were read (arXiv / publisher OA). For private reading; do not redistribute |

Regenerate (network access to api.openalex.org and api.crossref.org needed only for new entries):

```bash
python -I research/tools/verify_references.py
python -I research/tools/crossref_fetch.py
python -I research/tools/make_references.py
python -I research/tools/build_matrix.py
```

Candidate references are listed in `research/tools/candidates.json`. To add one, add a key with a DOI
or the exact title and rerun. Unmatched titles are reported as `TITLE_MISMATCH` and must be resolved by hand.
