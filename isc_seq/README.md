# isc_seq — sequence generation for the frozen ISC map

Scope: the sequence-generation stage only. No permutation, diffusion,
encryption or decryption is implemented here.

The frozen map (unchanged from the validated scripts):

```
t_n     = c - d/(1 + x_n^2 + y_n^2)
X_n     = 1 + a(x_n cos t_n - y_n sin t_n)
Y_n     = a(x_n sin t_n + y_n cos t_n)
x_{n+1} = 2 sin^2(w X_n) - 1
y_{n+1} = 2 sin^2(w Y_n) - 1
a = 0.9, c = 0.4, d = 6.0, w = 10.0
```

`load_config` refuses any configuration whose parameters differ from these.

## Layout

| path | purpose |
|---|---|
| `isc_seq/isc_map.py` | frozen map: `isc_step` (canonical) and `legacy_step` (bit-exact copy of `script/*.py`) |
| `isc_seq/trajectory.py` | raw x/y trajectories, configurable transient removal, seeded initial conditions, `.npz` save with SHA-256 |
| `isc_seq/extract.py` | extraction methods `sign`, `arccos8`, `frac8`, `mantissa8`, `mantissa8_xor` |
| `isc_seq/periodicity.py` | Brent (mu, lambda) cycle detection, quantised-state maps, legacy Floyd meeting index |
| `isc_seq/stats.py` | ACF, histogram entropies, entropy versus N, bit bias, byte uniformity |
| `isc_seq/nist.py` | NIST SP 800-22 subset (11–12 p-values per sequence) and the multi-sequence protocol |
| `isc_seq/sts_official.py` | driver and parser for the official NIST STS 2.1.2 `assess` |
| `experiments/run_official_sts.py`, `analyze_official_sts.py` | official-suite execution and analysis |
| `isc_seq/experiment.py`, `isc_seq/report.py` | config-driven run, Markdown report, SHA-256 manifest |
| `experiments/run_sequence_experiment.py` | command-line entry point |
| `experiments/configs/default.json`, `quick.json` | run configurations |
| `tests/` | pytest suite |
| `results/sequence_generation/<run_id>/` | run outputs; an existing run directory is never overwritten |

Legacy material (`script/`, `plots/`, PDFs, PPTX) is read but never written.

## Usage

```bash
python -m pytest tests -q
python experiments/run_sequence_experiment.py --config experiments/configs/quick.json
python experiments/run_sequence_experiment.py --config experiments/configs/default.json
```

Use `--run-id <name>` to choose the output directory name. To repeat a run, pass
its saved `config.json` as `--config` and compare the new `manifest.json` hashes.

```python
from isc_seq.trajectory import generate_trajectory
from isc_seq.extract import extract

xs, ys = generate_trajectory(0.1, 0.1, n=100_000, transient=5000)  # iterates 5001..105000
bits = extract("mantissa8_xor", xs, ys, n_bits=800_000)
```

## Canonical vs legacy evaluation

Both functions evaluate the same frozen equations.

| | `isc_step` (canonical) | `legacy_step` (legacy-exact) |
|---|---|---|
| squares | `x*x`, `s*s` (exactly rounded) | `x**2`, `np.sin(.)**2` (C `pow()` on NumPy scalars) |
| scalar vs vectorised | bit-identical (tested) | can differ by 1 ulp |
| vs `script/*.py` | agrees per step to < 1e-13 | bit-identical (tested) |
| use | all new sequences and analyses | reproducing previously reported numbers only |

Because the map is chaotic, a 1-ulp difference grows to O(1) within tens of
iterations. Consequences:

* Canonical and legacy trajectories from the same initial condition are
  different sequences after a few dozen steps. New results are therefore not
  bit-comparable with numbers produced by `script/*.py`, though their
  statistics should be.
* Bit-exact reproducibility also needs the same `sin`/`cos` implementation
  (NumPy build / platform C library) and the same float precision. Every run
  records `environment.json` (versions, platform and SHA-256 of the
  `isc_seq` sources); compare bitstreams by SHA-256 across machines.
* float32 results depend on NumPy's promotion rules. Under NumPy >= 2 a
  float32 state stays float32 throughout; under NumPy 1.x the legacy
  expression silently computed intermediates in float64.

## Initial conditions

`initial_conditions(seed, count)` draws all x0 values, then all y0 values, so
the y0 of a given index changes with `count`. Every run saves the exact values
(`initial_conditions.csv`, and the x0/y0 columns of `periodicity.csv`).
Re-running a saved `config.json` regenerates the same values; orbits from runs
with different counts must be matched by value, not by index.

## Extraction methods

| method | bits / iteration | definition |
|---|---|---|
| `sign` | 2 | `x > 0`, `y > 0` (legacy baseline) |
| `arccos8` | 16 | byte of `arccos(-v)/pi`, v = x, y |
| `frac8` | 16 | `floor(|v| * 1e14) mod 256` |
| `mantissa8` | 16 | float64 mantissa bits 8..15 of x and y |
| `mantissa8_xor` | 8 | `mantissa8(x) XOR mantissa8(y)` |

Bits are emitted per iteration, x part before y part, MSB first.

## Statistical evaluation

`nist.py` implements frequency, block frequency, runs, longest run, matrix
rank, DFT, Maurer universal (n >= 387 840), serial (2 p-values), approximate
entropy and cumulative sums (2 p-values). It applies the SP 800-22 protocol:
proportion of sequences with p >= 0.01 inside the 3-sigma band, plus p-value
uniformity (for m >= 55). The worked examples of SP 800-22 are reproduced by the
tests, except the DFT and universal examples, which could not be reproduced from
their printed inputs. Those two tests are validated against an independent
computation and a protocol run on PCG64 output.

Not implemented in `isc_seq.nist`: template matching, linear complexity and random
excursions. These are covered by the official-suite run below.

Statistical tests can only reject a generator. Passing them is not evidence
of cryptographic security.

## Official NIST STS 2.1.2

`isc_seq/sts_official.py` drives NIST's own `assess` (built from the official source
in `third_party/nist_sts/`, see its README) and parses its raw outputs. It also
reproduces `finalAnalysisReport.txt` exactly, so each parsed report can be checked. Two
scripts run it:

```bash
python experiments/run_official_sts.py --run-id <id> --workers 6   # executes assess (WSL Ubuntu)
python experiments/analyze_official_sts.py --run-id <id>           # parses, summarises, writes the report
```

Outputs go to `results/nist_sts_official/<id>/`, with `official_nist_sts_report.md`.
The saved `bitstreams/<method>.bin` files are used unchanged: assess mode 1 reads
packed bytes MSB first, the same layout the files were written in.

Random Excursions (Variant) applicability is decided from the cycle count J of each
sequence, not from the printed 0.000000 that the official report uses. Sequences
that are not applicable are listed as such, not as failures.

## Periodicity

`periodicity.py` reports the pre-period mu and the period lambda separately
(Brent), for float32, float64 and k-bit quantised states, under a stated
step budget. "No cycle within budget" is a lower bound only. The legacy
`find_cycle` (Floyd) returned a meeting index, a multiple of lambda;
`floyd_meeting_index` reproduces it for reconciliation.
