# Dependency and environment audit (Stage 3)

Status: audit **VERIFIED** (imports scanned with grep over all `*.py`; installed versions from `pip list` on this machine). No packages were installed. Proposed files are in `proposed/` and are **not applied**.

Recorded environment (matches the local install): Python 3.11.9, NumPy 2.4.6, SciPy 1.17.1, Matplotlib 3.10.0. Also installed: pandas 2.2.3, scikit-image 0.26.0, Pillow 11.1.0, ImageIO 2.38.1, cryptography 50.0.0, nistrng 1.2.3, pytest 9.1.1. **Not installed:** z3-solver, pooch, scikit-learn, mpmath (checked only by import scan/`pip list`; a missing import was not tested by running).

The four-package set is **not** the complete dependency set.

## Classification
| Tier | Packages | Where used |
|---|---|---|
| 1. Core runtime (cipher) | `numpy` | `isc_cipher/*` imports only numpy (+ stdlib: hmac, hashlib, struct, os) |
| 1b. Map/sequence tooling | `numpy`, `scipy` | `isc_seq/*` (scipy.special, scipy.stats) |
| 2. Test/dev | `pytest`, `cryptography`, `scikit-image` (roundtrip test uses `skimage.data`), `mpmath` (optional; test uses `importorskip`) | `tests/` |
| 3. Research/experiment | `matplotlib`, `pandas`, `scipy`, `scikit-image` (+`Pillow`), `scikit-learn` (`isc_eval/exp_predict.py`), `cryptography` (AEAD baselines in `isc_eval/constructions.py`) | `experiments/`, `isc_eval/` |
| 4. Optional image data | `scikit-image`, **`pooch`** (needed by skimage to download non-bundled sample images; the 2 unavailable Phase 4C candidates) | `experiments/phase4c/acquire_images.py` |
| 5. Optional cryptanalysis | **`z3-solver`** | `experiments/phase4e/solver_benchmarks.py`, `toy_solver.py` |
| 5b. KAT generation | `mpmath` | `isc_cipher_kat/make_kat_ext.py` |
| 6. Legacy ISC_PBL scripts | `nistrng` (only `script/*.py`; the production `isc_seq/nist.py` is a separate in-repo implementation using scipy) | `script/` |
| External system tools | WSL Ubuntu + gcc/make for the official NIST STS `assess` (`isc_seq/sts_official.py`, `experiments/run_official_sts.py`); a Linux oracle binary in `isc_cipher_kat/oracle/` | optional |

## Optional packages
| Package | Needed for | Mandatory? | Install | Notes |
|---|---|---|---|---|
| z3-solver | SMT attempts in Phase 4E / follow-up Part I | No | `pip install z3-solver` (PyPI lists many versions incl. 4.8.x–4.15.x; ships wheels bundling libz3, no system binary) | Specific version not chosen here; pin when used. Adds a large binary wheel. Not installed. |
| pooch | downloading extra `skimage.data` images | No | `pip install pooch` | Network at runtime; affects dataset reproducibility (downloaded files must be hashed). |
| scikit-learn | `isc_eval/exp_predict.py` | No | `pip install scikit-learn` | |
| mpmath | KAT accuracy check, one test | No | `pip install mpmath` | test is skipped if absent |

## Proposed files (not applied)
`proposed/requirements.txt` (core: numpy, scipy), `proposed/requirements-dev.txt` (adds pytest, cryptography, scikit-image), `proposed/requirements-experiments.txt` (adds matplotlib, pandas, scikit-learn, Pillow, nistrng), `proposed/requirements-optional.txt` (z3-solver, pooch, mpmath). Pins use the installed versions (known good here); **no lock file was generated** and no claim is made that other versions work. No `pyproject.toml` exists.

## Reproduction commands (to be verified against script interfaces before publication)
Environment: `python -m venv .venv`, activate, `pip install -r requirements-dev.txt`. Test suite: `python -m pytest tests/` (`ISC_SLOW=1` includes slow tests; from README). Interfaces of the experiment scripts (`experiments/run_sequence_experiment.py`, `run_official_sts.py`, `phase*/…`) were **not** individually verified for flags in this pass; do not document flags until checked.

## Test-suite run
A local run of `python -m pytest tests -q -x` was started; see `final_project_readiness_report.md` for its outcome (it was slow; status is recorded there, not assumed).
