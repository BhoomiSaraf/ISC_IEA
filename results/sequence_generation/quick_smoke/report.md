# ISC sequence-generation experiment `quick_smoke`

Generated automatically by `isc_seq.experiment`; every number below was computed in this run (see `results.json`, `manifest.json`).

## Setup

Frozen ISC map, canonical evaluation `isc_seq.isc_map.isc_step`:

```
t_n = c - d/(1 + x_n^2 + y_n^2)
X_n = 1 + a(x_n cos t_n - y_n sin t_n)
Y_n = a(x_n sin t_n + y_n cos t_n)
x_{n+1} = 2 sin^2(w X_n) - 1
y_{n+1} = 2 sin^2(w Y_n) - 1
```

| parameter | value |
|---|---|
| a | 0.900000 |
| c | 0.400000 |
| d | 6.000000 |
| omega | 10.000000 |

| setting | value |
|---|---|
| sequences (independent initial conditions) | 10 |
| initial conditions | PCG64(seed=20261025), uniform in [-1, 1)^2 (initial_conditions.csv) |
| transient iterations discarded | 1000 |
| bits per sequence | 100000 |
| map iterations per sequence | 50000 |
| NIST alpha / serial m / ApEn m / block M | 0.01 / 16 / 10 / 128 |
| python / numpy / scipy | 3.11.9 / 2.0.2 / 1.17.1 |
| platform | Windows-10-10.0.22631-SP0 |
| run time (s) | 41 |

## Raw trajectory (sequence 0)

| metric | x | y |
|---|---|---|
| min | -1.000000 | -1.000000 |
| max | 1.000000 | 1.000000 |
| mean | -0.033952 | -0.054180 |
| P(value > 0) | 0.470440 | 0.470980 |
| Shannon entropy, 256 bins (bits) | 7.686149 | 7.653886 |

N = 50000; lag-0 correlation(x, y) = 0.010618; joint entropy H(x,y) on 256x256 bins = 14.393742 bits.

Autocorrelation (white-noise 95% band: +/-0.008765):

| lag | ACF x | ACF y |
|---|---|---|
| 1 | -0.101822 | 0.010034 |
| 2 | 0.005488 | -0.001066 |
| 3 | 0.004434 | -0.001272 |
| 4 | -0.007265 | -0.002741 |
| 5 | -0.003013 | -0.003347 |
| 6 | 0.003771 | -0.002926 |
| 7 | 0.001964 | 0.001501 |
| 8 | -0.002982 | -0.004214 |
| 9 | 0.006010 | 0.001605 |
| 10 | -0.006912 | -0.001413 |

Lags outside the band: x 1/10, y 1/10.

2-D histogram entropy versus sample size (the estimate is bounded by log2 N and rises with N):

| N | H(x,y) bits | normalised | log2 N |
|---|---|---|---|
| 10000 | 12.881117 | 0.805070 | 13.287712 |
| 50000 | 14.393742 | 0.899609 | 15.609640 |

## Extraction methods: descriptive bit statistics

Computed on the concatenation of the first 10 sequences.

| method | ones fraction | monobit p | P(b_i = b_i+1) | byte chi2 p | byte entropy (bits) |
|---|---|---|---|---|---|
| sign | 0.470534 | 0.000000 | 0.514386 | 0.000000 | 7.938423 |
| arccos8 | 0.493095 | 2.218e-43 | 0.499983 | 1.739e-69 | 7.994937 |
| frac8 | 0.499497 | 0.314416 | 0.499763 | 0.923734 | 7.998707 |
| mantissa8 | 0.498724 | 0.010711 | 0.500347 | 0.253499 | 7.998445 |
| mantissa8_xor | 0.499873 | 0.799496 | 0.501094 | 0.102422 | 7.998362 |

## NIST SP 800-22 (implemented subset, multi-sequence protocol)

m = 10 sequences per method. A test passes when the proportion of sequences with p >= 0.01 is at least 0.8956 and (for m >= 55) the p-value uniformity P_T >= 0.0001. Template-matching, linear-complexity and random-excursion tests are not implemented here; `bitstreams/*.bin` can be fed to the official NIST STS for those.

| test | sign | arccos8 | frac8 | mantissa8 | mantissa8_xor |
|---|---|---|---|---|---|
| Frequency | FAIL (0/10) | FAIL (1/10) | PASS (10/10) | PASS (9/10) | PASS (10/10) |
| BlockFrequency | FAIL (0/10) | FAIL (7/10) | PASS (10/10) | PASS (9/10) | PASS (10/10) |
| Runs | FAIL (0/10) | FAIL (5/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) |
| LongestRun | FAIL (0/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) |
| Rank | PASS (10/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) |
| FFT | PASS (10/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) |
| Serial_1 | FAIL (2/10) | FAIL (1/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) |
| Serial_2 | PASS (10/10) | FAIL (4/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) |
| ApproximateEntropy | FAIL (0/10) | FAIL (4/10) | PASS (10/10) | PASS (10/10) | PASS (10/10) |
| CumulativeSums_fwd | FAIL (0/10) | FAIL (1/10) | PASS (10/10) | PASS (9/10) | PASS (10/10) |
| CumulativeSums_bwd | FAIL (0/10) | FAIL (1/10) | PASS (10/10) | PASS (9/10) | PASS (10/10) |

| method | tests passed | tests run |
|---|---|---|
| sign | 3 | 11 |
| arccos8 | 3 | 11 |
| frac8 | 11 | 11 |
| mantissa8 | 11 | 11 |
| mantissa8_xor | 11 | 11 |

## Finite-precision periodicity (Brent's algorithm)

mu = pre-period (first iterate on the cycle), lambda = period. 'not found' means no cycle within the step budget, which is a lower-bound statement only.

| case | orbits | cycles found | lambda range | mu range | lambda geo. mean | step budget |
|---|---|---|---|---|---|---|
| isc_step float32 | 2 | 1 | 74595 .. 74595 | 521234 .. 521234 | 74595 | 2000000 |
| isc_step float64 quantised 8 bits | 3 | 3 | 65 .. 440 | 19 .. 364 | 233 | 200000 |
| isc_step float64 quantised 10 bits | 3 | 3 | 188 .. 796 | 120 .. 325 | 304 | 200000 |
| isc_step float64 | 1 | 0 | - | - | - | 20000 |

## Files

`config.json`, `environment.json`, `initial_conditions.csv`, `raw_trajectory_seq000.npz`, `raw_stats_seq000.json`, `entropy_vs_n_seq000.csv`, `bit_stats.csv`, `nist/summary.csv`, `nist/pvalues_<method>.csv`, `bitstreams/<method>.bin` (packed MSB-first, sequences concatenated), `periodicity.csv`, `results.json`, `manifest.json` (SHA-256 of every file).
