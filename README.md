# ISC_IEA — Ikeda–Sine–Chebyshev (ISC) Image Encryption

Research codebase for an image-encryption construction built on the Iterative Sine–Chebyshev–Ikeda chaotic map: map characterization, a working authenticated cipher, and the experiments evaluating it.

## Layout

| Path | Contents |
|---|---|
| `isc_cipher/` | The cipher: HKDF-SHA-256 key derivation, 4 ISC generator streams × 64 lanes, Fisher–Yates S-box/permutation, forward + backward diffusion, ISCI container, HMAC-SHA-256 |
| `isc_cipher_kat/` | Known-answer-test generation |
| `isc_seq/` | ISC map, byte extraction, statistical/NIST tooling |
| `isc_eval/` | Evaluation harness (stats, misuse, AEAD baselines, performance) |
| `tests/` | pytest suite |
| `experiments/phase3b/` … `phase5/` | Multi-lane validation, image evaluation, natural images and profiling, structural cryptanalysis, nonce-reuse analysis, evidence consolidation |
| `results/`, `plots/` | Sequence generation, NIST STS, and encryption experiment outputs |
| `research/` | Design docs, threat model, literature review, bibliography |
| `isc_pbl/` | Step 1.1 map characterization, Phase 2 design/specification documents, Phase 3A/3B reports and results |
| `third_party/fdlibm/` | Deterministic sin/cos reference |

The official NIST STS 2.1.2 sources and build are not included (see `third_party/nist_sts/README.md`), and neither are full-text copies of cited papers.

## Running tests

```
python -m pytest tests/
```

Set `ISC_SLOW=1` to include the slow tests.

## Status

Start with `experiments/phase5/PHASE_5_FINAL_EVIDENCE_REPORT.md` for the consolidated, verified findings and limitations. This is an experimental research cipher with no formal security proof. Do not use it to protect real data.
