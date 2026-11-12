# ISC sequence-generation experiment `default_20261025`

Generated automatically by `isc_seq.experiment`; every number below was computed in this run (see `results.json`, `manifest.json`). Scope: sequence generation only; no encryption.

## Setup

Frozen ISC map:

```
t_n = c - d/(1 + x_n^2 + y_n^2)
X_n = 1 + a(x_n cos t_n - y_n sin t_n)
Y_n = a(x_n sin t_n + y_n cos t_n)
x_{n+1} = 2 sin^2(w X_n) - 1
y_{n+1} = 2 sin^2(w Y_n) - 1
```

| parameter | value |
|---|---|
| a | 0.9 |
| c | 0.4 |
| d | 6.0 |
| omega | 10.0 |

| setting | value |
|---|---|
| sequences (independent initial conditions) | 100 |
| initial conditions | PCG64(seed=20261025), uniform in [-1, 1)^2 (initial_conditions.csv) |
| transient iterations discarded | 5000 |
| bits per sequence | 1000000 |
| map iterations per sequence | 500000 |
| extraction methods | sign, arccos8, frac8, mantissa8, mantissa8_xor |
| NIST alpha / serial m / ApEn m / block M | 0.01 / 16 / 10 / 128 |
| python / numpy / scipy / isc_seq | 3.11.9 / 2.0.2 / 1.17.1 / 0.1.0 |
| platform | Windows-10-10.0.22631-SP0 (AMD64) |
| started (UTC) | 2026-10-25T15:58:33+00:00 |
| run time (s) | 996 |

## Floating-point evaluation: canonical vs legacy

Two evaluations of the same frozen equations exist in `isc_seq.isc_map`:

|  | `isc_step` (canonical) | `legacy_step` (legacy-exact) |
|---|---|---|
| squares | `x*x`, `s*s` (IEEE exactly rounded) | `x**2`, `np.sin(.)**2` (C `pow()` on NumPy scalars) |
| scalar vs vectorised | bit-identical (tested) | can differ by 1 ulp |
| matches `script/*.py` | per step to < 1e-13; orbits separate after tens of iterations | bit-identical (tested) |
| used in this run for | all sequences, bitstreams, NIST, raw statistics, all periodicity rows not labelled legacy | periodicity row `legacy_step float32 (0.1,0.1)` and the legacy reproduction check |

Because the map is chaotic, any 1-ulp difference grows to O(1) within tens of iterations, so a bitstream is reproducible only for the same evaluation, the same `sin`/`cos` implementation (platform C library / NumPy build) and the same float precision. Numbers here are reproducible on the recorded environment; on another platform compare `bitstreams/*.bin` by SHA-256 (`manifest.json`) before assuming identity. Statistical conclusions should not depend on that, but exact bit identity can.

## Completeness

| method | sequences expected | sequences with p-values | p-values per sequence | status |
|---|---|---|---|---|
| sign | 100 | 100 | 12 | complete |
| arccos8 | 100 | 100 | 12 | complete |
| frac8 | 100 | 100 | 12 | complete |
| mantissa8 | 100 | 100 | 12 | complete |
| mantissa8_xor | 100 | 100 | 12 | complete |

Recorded failures / incomplete items: 

- 10 periodicity orbit(s) reached the step budget without a detected cycle (recorded as such in periodicity.csv; this is a search limit, not an error)

## Raw trajectory (sequence 0)

| metric | x | y |
|---|---|---|
| min | -1.000000 | -1.000000 |
| max | 1.000000 | 1.000000 |
| mean | -0.036130 | -0.054740 |
| P(value > 0) | 0.468868 | 0.470510 |
| Shannon entropy, 256 bins (bits) | 7.692635 | 7.660641 |

N = 500000; lag-0 correlation(x, y) = 0.004167; joint entropy H(x,y) on 256x256 bins = 15.241132 bits.

Autocorrelation (white-noise 95% band: +/-0.002772):

| lag | ACF x | ACF y |
|---|---|---|
| 1 | -0.103911 | 0.009682 |
| 2 | 0.002289 | -0.008467 |
| 3 | -0.000357 | -0.001794 |
| 4 | -0.000757 | 0.001140 |
| 5 | 0.000594 | -0.000387 |
| 6 | 0.001704 | 0.001018 |
| 7 | -0.000536 | 0.001145 |
| 8 | 0.000673 | -0.001299 |
| 9 | -0.001055 | -0.001346 |
| 10 | -0.000412 | -0.000526 |

Lags outside the band: x 1/10, y 2/10 (about 1 in 20 is expected by chance for white noise).

2-D histogram entropy versus sample size (the estimate is bounded by log2 N and rises with N, so values are comparable only at equal N and binning):

| N | H(x,y) bits | normalised | log2 N |
|---|---|---|---|
| 10000 | 12.887417 | 0.805464 | 13.287712 |
| 50000 | 14.399437 | 0.899965 | 15.609640 |
| 100000 | 14.819057 | 0.926191 | 16.609640 |
| 200000 | 15.075227 | 0.942202 | 17.609640 |
| 500000 | 15.241132 | 0.952571 | 18.931569 |

## Extraction methods: descriptive bit statistics

Computed on the concatenation of the first 10 sequences (single pooled sample, not the NIST protocol).

| method | bits | ones fraction | monobit p | P(b_i = b_i+1) | byte chi2 p (255 dof) | byte entropy (bits) |
|---|---|---|---|---|---|---|
| sign | 10000000 | 0.469525 | 0.000000 | 0.514381 | 0.000000 | 7.937018 |
| arccos8 | 10000000 | 0.493203 | 0.000000 | 0.500465 | 0.000000 | 7.996509 |
| frac8 | 10000000 | 0.500060 | 0.706216 | 0.500105 | 0.967730 | 7.999876 |
| mantissa8 | 10000000 | 0.499999 | 0.996468 | 0.499879 | 0.039372 | 7.999829 |
| mantissa8_xor | 10000000 | 0.500013 | 0.935478 | 0.500063 | 0.934681 | 7.999872 |

## NIST SP 800-22 (implemented subset, multi-sequence protocol)

m = 100 sequences of 1000000 bits per method, each sequence from its own initial condition. A test passes when the proportion of sequences with p >= 0.01 is at least 0.9602 and, for m >= 55, the uniformity of the p-values gives P_T >= 0.0001. Cells show `PASS/FAIL (sequences passing/m, P_T)`. Template-matching, linear-complexity and random-excursion tests are not implemented here; `bitstreams/*.bin` can be given to the official NIST STS for those.

| test | sign | arccos8 | frac8 | mantissa8 | mantissa8_xor |
|---|---|---|---|---|---|
| Frequency | FAIL (0/100, P_T=6.187e-188) | FAIL (0/100, P_T=6.187e-188) | PASS (97/100, P_T=0.1453) | PASS (99/100, P_T=0.7197) | PASS (98/100, P_T=0.0329) |
| BlockFrequency | FAIL (0/100, P_T=6.187e-188) | FAIL (21/100, P_T=1.902e-179) | PASS (98/100, P_T=0.4944) | PASS (99/100, P_T=0.7598) | PASS (99/100, P_T=0.7792) |
| Runs | FAIL (0/100, P_T=6.187e-188) | FAIL (0/100, P_T=6.187e-188) | PASS (100/100, P_T=0.9114) | PASS (100/100, P_T=0.7197) | PASS (99/100, P_T=0.6787) |
| LongestRun | FAIL (2/100, P_T=6.187e-188) | PASS (99/100, P_T=0.1223) | PASS (99/100, P_T=0.0805) | PASS (100/100, P_T=0.4750) | PASS (98/100, P_T=0.8343) |
| Rank | PASS (100/100, P_T=0.0590) | PASS (100/100, P_T=0.8514) | PASS (97/100, P_T=0.9717) | PASS (100/100, P_T=0.5141) | PASS (98/100, P_T=0.4190) |
| FFT | FAIL (88/100, P_T=7.083e-16) | PASS (99/100, P_T=0.6993) | PASS (98/100, P_T=0.0909) | PASS (100/100, P_T=0.1154) | PASS (99/100, P_T=0.6787) |
| Universal | FAIL (0/100, P_T=6.187e-188) | FAIL (69/100, P_T=1.820e-67) | PASS (99/100, P_T=0.0590) | PASS (99/100, P_T=0.0628) | PASS (100/100, P_T=0.5544) |
| Serial_1 | FAIL (0/100, P_T=6.187e-188) | FAIL (0/100, P_T=6.187e-188) | PASS (98/100, P_T=0.5544) | PASS (99/100, P_T=0.2897) | PASS (100/100, P_T=0.9978) |
| Serial_2 | FAIL (96/100, P_T=6.022e-07) | FAIL (0/100, P_T=6.187e-188) | PASS (100/100, P_T=0.0205) | PASS (99/100, P_T=0.3505) | PASS (100/100, P_T=0.0909) |
| ApproximateEntropy | FAIL (0/100, P_T=6.187e-188) | FAIL (0/100, P_T=6.187e-188) | PASS (99/100, P_T=0.3838) | PASS (99/100, P_T=0.6579) | PASS (97/100, P_T=0.8343) |
| CumulativeSums_fwd | FAIL (0/100, P_T=6.187e-188) | FAIL (0/100, P_T=6.187e-188) | PASS (97/100, P_T=0.6163) | PASS (99/100, P_T=0.2757) | PASS (98/100, P_T=0.9114) |
| CumulativeSums_bwd | FAIL (0/100, P_T=6.187e-188) | FAIL (0/100, P_T=6.187e-188) | PASS (98/100, P_T=0.5341) | PASS (99/100, P_T=0.0487) | PASS (100/100, P_T=0.5341) |

Aggregate (number of p-value series meeting both protocol criteria):

| method | passed | of | failed tests |
|---|---|---|---|
| sign | 1 | 12 | Frequency, BlockFrequency, Runs, LongestRun, FFT, Universal, Serial_1, Serial_2, ApproximateEntropy, CumulativeSums_fwd, CumulativeSums_bwd |
| arccos8 | 3 | 12 | Frequency, BlockFrequency, Runs, Universal, Serial_1, Serial_2, ApproximateEntropy, CumulativeSums_fwd, CumulativeSums_bwd |
| frac8 | 12 | 12 | - |
| mantissa8 | 12 | 12 | - |
| mantissa8_xor | 12 | 12 | - |

Interpretation limits: these tests can reject a generator but cannot certify one. Passing the implemented subset means no deviation from i.i.d. uniform bits was detected by these statistics at this sample size; it is not evidence of cryptographic security (unpredictability, key-recovery resistance, resistance to attacks exploiting the known deterministic map). With many series evaluated, an isolated marginal failure can occur by chance; a method that fails several tests decisively is non-random.

## Finite-precision periodicity (Brent's algorithm)

Each orbit is iterated in the stated precision, with the state cast back to that precision after every step. 'quantised k bits' means float64 arithmetic with x and y rounded to multiples of 2^-k after every step (a finite state of about (2^(k+1)+1)^2 points). mu = pre-period (index of the first state on the cycle; the initial condition is index 0), lambda = period. The step budget bounds the number of map evaluations in Brent's period-finding phase; when it is exhausted the orbit is reported as 'no cycle within budget', which is a lower-bound statement only. Initial conditions: PCG64(seed + 1) in [-1, 1)^2, cast to the stated precision.

| case | dtype | quant bits | orbits | cycles found | mu range | lambda range | lambda geo. mean | step budget |
|---|---|---|---|---|---|---|---|---|
| legacy_step float32 (0.1,0.1) | float32 | - | 1 | 1 | 278509 .. 278509 | 24183 .. 24183 | 24183 | 4000000 |
| isc_step float32 (0.1,0.1) | float32 | - | 1 | 1 | 635185 .. 635185 | 74595 .. 74595 | 74595 | 4000000 |
| isc_step float32 | float32 | - | 10 | 3 | 398136 .. 1512078 | 74595 .. 74595 | 74595 | 4000000 |
| isc_step float64 quantised 8 bits | float64 | 8 | 10 | 10 | 6 .. 333 | 11 .. 440 | 115 | 4000000 |
| isc_step float64 quantised 10 bits | float64 | 10 | 10 | 10 | 2 .. 939 | 47 .. 796 | 501 | 4000000 |
| isc_step float64 quantised 12 bits | float64 | 12 | 10 | 10 | 442 .. 4648 | 3716 .. 3716 | 3716 | 4000000 |
| isc_step float64 quantised 14 bits | float64 | 14 | 10 | 10 | 640 .. 13577 | 218 .. 5354 | 3729 | 4000000 |
| isc_step float64 quantised 16 bits | float64 | 16 | 10 | 10 | 365 .. 33104 | 30180 .. 68314 | 58017 | 4000000 |
| isc_step float64 | float64 | - | 3 | 0 | - | - | - | 2000000 |

Per-orbit values (also in `periodicity.csv`):

| case | x0 | y0 | mu | lambda | budget |
|---|---|---|---|---|---|
| legacy_step float32 (0.1,0.1) | 0.1 | 0.1 | 278509 | 24183 | 4000000 |
| isc_step float32 (0.1,0.1) | 0.1 | 0.1 | 635185 | 74595 | 4000000 |
| isc_step float32 | 0.5738605856895447 | -0.4596106708049774 | no cycle within budget | - | 4000000 |
| isc_step float32 | 0.25911834836006165 | 0.3787618577480316 | 398136 | 74595 | 4000000 |
| isc_step float32 | 0.8169847130775452 | -0.7992818355560303 | 721950 | 74595 | 4000000 |
| isc_step float32 | -0.06406740099191666 | 0.3642343282699585 | no cycle within budget | - | 4000000 |
| isc_step float32 | -0.9601681232452393 | 0.9881325364112854 | no cycle within budget | - | 4000000 |
| isc_step float32 | 0.06500883400440216 | 0.32656341791152954 | no cycle within budget | - | 4000000 |
| isc_step float32 | 0.5556700825691223 | 0.9331681132316589 | no cycle within budget | - | 4000000 |
| isc_step float32 | 0.9371631145477295 | 0.9319955706596375 | 1512078 | 74595 | 4000000 |
| isc_step float32 | 0.5257415175437927 | 0.19100911915302277 | no cycle within budget | - | 4000000 |
| isc_step float32 | -0.2849830985069275 | 0.28704842925071716 | no cycle within budget | - | 4000000 |
| isc_step float64 quantised 8 bits | 0.5738605678108115 | -0.4596106719458737 | 58 | 11 | 4000000 |
| isc_step float64 quantised 8 bits | 0.2591183387534839 | 0.3787618556935153 | 62 | 11 | 4000000 |
| isc_step float64 quantised 8 bits | 0.8169846843724546 | -0.7992818461438946 | 125 | 440 | 4000000 |
| isc_step float64 quantised 8 bits | -0.06406740094590435 | 0.36423431456552935 | 153 | 440 | 4000000 |
| isc_step float64 quantised 8 bits | -0.9601681351751452 | 0.9881325235199367 | 6 | 440 | 4000000 |
| isc_step float64 quantised 8 bits | 0.06500883726942153 | 0.3265634155297965 | 333 | 65 | 4000000 |
| isc_step float64 quantised 8 bits | 0.5556700914076405 | 0.9331681127819684 | 311 | 65 | 4000000 |
| isc_step float64 quantised 8 bits | 0.9371631272805918 | 0.9319955410279346 | 154 | 440 | 4000000 |
| isc_step float64 quantised 8 bits | 0.5257415406555412 | 0.19100911983328173 | 95 | 49 | 4000000 |
| isc_step float64 quantised 8 bits | -0.28498310084202516 | 0.28704843777162425 | 24 | 440 | 4000000 |
| isc_step float64 quantised 10 bits | 0.5738605678108115 | -0.4596106719458737 | 346 | 728 | 4000000 |
| isc_step float64 quantised 10 bits | 0.2591183387534839 | 0.3787618556935153 | 164 | 47 | 4000000 |
| isc_step float64 quantised 10 bits | 0.8169846843724546 | -0.7992818461438946 | 827 | 728 | 4000000 |
| isc_step float64 quantised 10 bits | -0.06406740094590435 | 0.36423431456552935 | 678 | 728 | 4000000 |
| isc_step float64 quantised 10 bits | -0.9601681351751452 | 0.9881325235199367 | 4 | 796 | 4000000 |
| isc_step float64 quantised 10 bits | 0.06500883726942153 | 0.3265634155297965 | 670 | 728 | 4000000 |
| isc_step float64 quantised 10 bits | 0.5556700914076405 | 0.9331681127819684 | 939 | 728 | 4000000 |
| isc_step float64 quantised 10 bits | 0.9371631272805918 | 0.9319955410279346 | 517 | 728 | 4000000 |
| isc_step float64 quantised 10 bits | 0.5257415406555412 | 0.19100911983328173 | 2 | 244 | 4000000 |
| isc_step float64 quantised 10 bits | -0.28498310084202516 | 0.28704843777162425 | 597 | 728 | 4000000 |
| isc_step float64 quantised 12 bits | 0.5738605678108115 | -0.4596106719458737 | 3194 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | 0.2591183387534839 | 0.3787618556935153 | 4350 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | 0.8169846843724546 | -0.7992818461438946 | 1039 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | -0.06406740094590435 | 0.36423431456552935 | 4648 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | -0.9601681351751452 | 0.9881325235199367 | 2877 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | 0.06500883726942153 | 0.3265634155297965 | 442 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | 0.5556700914076405 | 0.9331681127819684 | 3717 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | 0.9371631272805918 | 0.9319955410279346 | 4038 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | 0.5257415406555412 | 0.19100911983328173 | 4218 | 3716 | 4000000 |
| isc_step float64 quantised 12 bits | -0.28498310084202516 | 0.28704843777162425 | 2444 | 3716 | 4000000 |
| isc_step float64 quantised 14 bits | 0.5738605678108115 | -0.4596106719458737 | 4729 | 218 | 4000000 |
| isc_step float64 quantised 14 bits | 0.2591183387534839 | 0.3787618556935153 | 640 | 4996 | 4000000 |
| isc_step float64 quantised 14 bits | 0.8169846843724546 | -0.7992818461438946 | 3451 | 4996 | 4000000 |
| isc_step float64 quantised 14 bits | -0.06406740094590435 | 0.36423431456552935 | 2675 | 5354 | 4000000 |
| isc_step float64 quantised 14 bits | -0.9601681351751452 | 0.9881325235199367 | 3271 | 5354 | 4000000 |
| isc_step float64 quantised 14 bits | 0.06500883726942153 | 0.3265634155297965 | 7845 | 4996 | 4000000 |
| isc_step float64 quantised 14 bits | 0.5556700914076405 | 0.9331681127819684 | 6626 | 4996 | 4000000 |
| isc_step float64 quantised 14 bits | 0.9371631272805918 | 0.9319955410279346 | 9330 | 5354 | 4000000 |
| isc_step float64 quantised 14 bits | 0.5257415406555412 | 0.19100911983328173 | 13577 | 4996 | 4000000 |
| isc_step float64 quantised 14 bits | -0.28498310084202516 | 0.28704843777162425 | 8757 | 4996 | 4000000 |
| isc_step float64 quantised 16 bits | 0.5738605678108115 | -0.4596106719458737 | 10426 | 68314 | 4000000 |
| isc_step float64 quantised 16 bits | 0.2591183387534839 | 0.3787618556935153 | 18453 | 68314 | 4000000 |
| isc_step float64 quantised 16 bits | 0.8169846843724546 | -0.7992818461438946 | 33104 | 68314 | 4000000 |
| isc_step float64 quantised 16 bits | -0.06406740094590435 | 0.36423431456552935 | 365 | 68314 | 4000000 |
| isc_step float64 quantised 16 bits | -0.9601681351751452 | 0.9881325235199367 | 6516 | 30180 | 4000000 |
| isc_step float64 quantised 16 bits | 0.06500883726942153 | 0.3265634155297965 | 1664 | 68314 | 4000000 |
| isc_step float64 quantised 16 bits | 0.5556700914076405 | 0.9331681127819684 | 7927 | 30180 | 4000000 |
| isc_step float64 quantised 16 bits | 0.9371631272805918 | 0.9319955410279346 | 3755 | 68314 | 4000000 |
| isc_step float64 quantised 16 bits | 0.5257415406555412 | 0.19100911983328173 | 12163 | 68314 | 4000000 |
| isc_step float64 quantised 16 bits | -0.28498310084202516 | 0.28704843777162425 | 3644 | 68314 | 4000000 |
| isc_step float64 | 0.5738605678108115 | -0.4596106719458737 | no cycle within budget | - | 2000000 |
| isc_step float64 | 0.2591183387534839 | 0.3787618556935153 | no cycle within budget | - | 2000000 |
| isc_step float64 | 0.8169846843724546 | -0.7992818461438946 | no cycle within budget | - | 2000000 |

Legacy reconciliation: with `legacy_step` in float32 from (0.1, 0.1), Brent gives mu = 278509, lambda = 24183. Floyd's meeting index as computed by `find_cycle` in `script/final_validation.py` (max_iter = 1000000) = 290196 = 12 x lambda. The value previously reported as 'Cycle_Length_Float32' is this meeting index, not the period.

## Legacy reproduction check

Lag-1 ACF of x recomputed with `legacy_step` (x0 = y0 = 0.1, transient 5000, N = 100000): -0.10157990695724047; value stored in `plots/final_validation/validation_report.csv`: -0.10157990695724044 (agree to < 1e-12).

## Reproducing this run

```bash
python experiments/run_sequence_experiment.py --config <run dir>/config.json --run-id <new id>
```

`config.json` holds the full merged configuration (seed, sizes, methods, NIST and periodicity settings); `environment.json` the interpreter, library versions and platform; `initial_conditions.csv` the exact initial conditions (repr of float64). Compare the new run's `manifest.json` hashes with this one.

## Files

`config.json`, `environment.json`, `initial_conditions.csv`, `raw_trajectory_seq000.npz`, `raw_stats_seq000.json`, `entropy_vs_n_seq000.csv`, `bit_stats.csv`, `nist/summary.csv`, `nist/pvalues_<method>.csv`, `bitstreams/<method>.bin` (packed MSB-first, sequences concatenated in initial-condition order), `periodicity.csv`, `results.json`, `report.md`, `manifest.json` (SHA-256 of every other file).
