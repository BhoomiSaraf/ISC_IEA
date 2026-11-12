# Official NIST STS 2.1.2 evaluation of ISC bitstreams (`sts212_default_20261025`)

Scope: statistical testing of the bitstreams saved by the sequence-generation run `results/sequence_generation/default_20261025`. No encryption. Every number below is parsed from the raw official outputs under `raw/` (see `analysis/` and `manifest.json`).

## 1. Setup and provenance

| item | value |
|---|---|
| suite | NIST Statistical Test Suite (STS) 2.1.2 |
| source | https://csrc.nist.gov/CSRC/media/Projects/Random-Bit-Generation/documents/sts-2_1_2.zip (listed on https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software) |
| source zip SHA-256 / bytes | `0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157` / 43915127 |
| documentation | NIST SP 800-22 Rev. 1a (April 2010): https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-22r1a.pdf (SHA-256 `38aba1b34a7fa52c440790d6e0cabf498e4b525177b3b6cebb399ab8ccf031d2`) |
| source modifications | none: build tree verified file-by-file against the official zip (provenance/sts_provenance.json) |
| build host | Ubuntu-24.04 under WSL2 |
| toolchain | gcc (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0; GNU Make 4.3; ldd (Ubuntu GLIBC 2.39-0ubuntu8.6) 2.39; Linux 6.18.54.1-microsoft-standard-WSL2 x86_64 |
| build command | make   (official makefile, unmodified; CC = /usr/bin/gcc, flags -c -Wall) |
| build warnings | 5 compiler warnings (unused variables, misleading indentation); see build.log |
| assess SHA-256 | `d2a91cc977bdcc6497ca2a749fccdcda197a91521c6d71d5d3342c1f4b44b30b` |

Test parameters are the defaults compiled into `assess.c` and were not changed:

| parameter | value |
|---|---|
| blockFrequencyBlockLength | 128 |
| nonOverlappingTemplateBlockLength | 9 |
| overlappingTemplateBlockLength | 9 |
| approximateEntropyBlockLength | 10 |
| serialBlockLength | 16 |
| linearComplexitySequenceLength | 500 |
| ALPHA | 0.010000 |

Input: the saved `bitstreams/<method>.bin` files, used unchanged with assess input mode 1 (binary): bytes are read 4 at a time and expanded MSB first, which is exactly how the files were written (np.packbits, bitorder='big'). Each file holds 100 consecutive 125,000-byte sequences. Because 1,000,000 is a multiple of 32, no bits are dropped or shifted between sequences. No conversion was performed. File hashes were checked against the sequence-generation manifest before running; per-sequence SHA-256 identifiers are in `inputs/input_sequences.csv`.

| method | file | SHA-256 | sequences |
|---|---|---|---|
| sign | results/sequence_generation/default_20261025/bitstreams/sign.bin | `d67e60866db4c863...` | 100 |
| arccos8 | results/sequence_generation/default_20261025/bitstreams/arccos8.bin | `27eec9d3f76510ea...` | 100 |
| frac8 | results/sequence_generation/default_20261025/bitstreams/frac8.bin | `87b200f999837f88...` | 100 |
| mantissa8 | results/sequence_generation/default_20261025/bitstreams/mantissa8.bin | `c6b280a57ee429e1...` | 100 |
| mantissa8_xor | results/sequence_generation/default_20261025/bitstreams/mantissa8_xor.bin | `7f736d3ca448433a...` | 100 |

## 2. Validation of the build against SP 800-22 Appendix B

The five official sample files (1,000,000 bits each) were run through the built `assess` with default parameters. **78/80** Appendix B p-values were reproduced exactly (6 decimals); the largest absolute difference is 1.0e-06.

| sample | test | Appendix B | official build | isc_seq.nist |
|---|---|---|---|---|
| e | Cusum-Forward | 0.669887 | 0.669886 | 0.669886 |
| e | Cusum-Reverse | 0.724266 | 0.724265 | 0.724265 |

These differ only in the 6th decimal. The independent Python implementation gives the same value as the official build, so the difference is most likely last-digit rounding in the published table (the cumulative-sums P-value sums many normal-CDF terms) rather than a build defect. It has no effect on any decision at alpha = 0.01.

The earlier Python implementation (`isc_seq.nist`) on the same files: **53/55** of the Appendix B values it covers reproduced to 6 decimals.

| sample | test | Appendix B | isc_seq.nist |
|---|---|---|---|
| e | Cusum-Forward | 0.669887 | 0.669886 |
| e | Cusum-Reverse | 0.724266 | 0.724265 |

## 3. Coverage

All 15 tests of STS 2.1.2 (the complete SP 800-22 Rev. 1a battery) were executed on every sequence of every method. Executed is not the same as applicable: the random-excursion tests apply only to sequences with at least 500 cycles (J), and their results are reported for the applicable sequences only.

| method | sequences submitted | sequences read by assess | run complete | assess exit code | stdout errors | parse problems | finalAnalysisReport mismatches |
|---|---|---|---|---|---|---|---|
| sign | 100 | 100 | yes | 1 | 0 | 0 | 0 |
| arccos8 | 100 | 100 | yes | 1 | 0 | 0 | 0 |
| frac8 | 100 | 100 | yes | 1 | 0 | 0 | 0 |
| mantissa8 | 100 | 100 | yes | 1 | 0 | 0 | 0 |
| mantissa8_xor | 100 | 100 | yes | 1 | 0 | 0 | 0 |

`assess` returns 1 from `main()` after a normal run, so exit code 1 is expected. 'finalAnalysisReport mismatches' counts series where the independently recomputed metrics differ from the official summary file.


## 4. Results per method and test

For each p-value series, a flag is raised when the number of passing sequences (p >= 0.01) is outside the official proportion interval, or when the p-value uniformity P-value is < 0.0001. Both are computed exactly as `finalAnalysisReport.txt` does. Tests with several series (Cumulative Sums 2, Serial 2, Non-overlapping Template 148, Random Excursions 8, Random Excursions Variant 18) are summarised as flagged/total series. 'Chance tail p' is the binomial probability of at least that many flagged series if every series were flagged independently with its null probability. It is an interpretation aid only, because template series are not independent.

### sign

| test | status | sequences used | excluded (not applicable) | flagged series | lowest pass proportion | lowest uniformity P | chance tail p | verdict |
|---|---|---|---|---|---|---|---|---|
| Frequency | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| BlockFrequency | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| CumulativeSums | EXECUTED | 100 | 0 | 2/2 | 0.000000 | 6.19e-188 | 1.25e-05 | FLAGGED (2/2 series; more than chance) |
| Runs | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| LongestRun | EXECUTED | 100 | 0 | 1/1 | 0.020000 | 6.19e-188 | 0.003532 | FLAGGED |
| Rank | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.058984 | 1.000000 | no series flagged |
| FFT | EXECUTED | 100 | 0 | 1/1 | 0.880000 | 7.08e-16 | 0.003532 | FLAGGED |
| NonOverlappingTemplate | EXECUTED | 100 | 0 | 136/148 | 0.000000 | 6.19e-188 | 0.000000 | FLAGGED (136/148 series; more than chance) |
| OverlappingTemplate | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| Universal | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| ApproximateEntropy | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| RandomExcursions | NOT_APPLICABLE | 0 | 100 | 0/8 | n/a | n/a | n/a | not evaluated: no applicable sequences |
| RandomExcursionsVariant | NOT_APPLICABLE | 0 | 100 | 0/18 | n/a | n/a | n/a | not evaluated: no applicable sequences |
| Serial | EXECUTED | 100 | 0 | 2/2 | 0.000000 | 6.19e-188 | 1.25e-05 | FLAGGED (2/2 series; more than chance) |
| LinearComplexity | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.494392 | 1.000000 | no series flagged |

| series | passed/applicable | proportion range (official) | uniformity P | flag |
|---|---|---|---|---|
| Frequency | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| BlockFrequency | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| CumulativeSums forward | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| CumulativeSums reverse | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Runs | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| LongestRun | 2/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Rank | 100/100 | 96..101 | 0.058984 | - |
| FFT | 88/100 | 96..101 | 7.08e-16 | PROPORTION UNIFORMITY |
| OverlappingTemplate | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Universal | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| ApproximateEntropy | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Serial p_value1 | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Serial p_value2 | 96/100 | 96..101 | 6.02e-07 | UNIFORMITY |
| LinearComplexity | 99/100 | 96..101 | 0.494392 | - |

| series | applicable | passed | flag | official report rule: sample / passed / flag | applicable but printed 0.000000 |
|---|---|---|---|---|---|
| RandomExcursions x=-4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=-3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=-2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=-1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-9 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-8 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-7 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-6 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-5 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+5 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+6 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+7 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+8 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+9 | 0 | 0 | no | 0 / 0 / no | 0 |

### arccos8

| test | status | sequences used | excluded (not applicable) | flagged series | lowest pass proportion | lowest uniformity P | chance tail p | verdict |
|---|---|---|---|---|---|---|---|---|
| Frequency | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| BlockFrequency | EXECUTED | 100 | 0 | 1/1 | 0.210000 | 1.90e-179 | 0.003532 | FLAGGED |
| CumulativeSums | EXECUTED | 100 | 0 | 2/2 | 0.000000 | 6.19e-188 | 1.25e-05 | FLAGGED (2/2 series; more than chance) |
| Runs | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| LongestRun | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.122325 | 1.000000 | no series flagged |
| Rank | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.851383 | 1.000000 | no series flagged |
| FFT | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.699313 | 1.000000 | no series flagged |
| NonOverlappingTemplate | EXECUTED | 100 | 0 | 81/148 | 0.040000 | 6.19e-188 | 2.36e-156 | FLAGGED (81/148 series; more than chance) |
| OverlappingTemplate | EXECUTED | 100 | 0 | 1/1 | 0.840000 | 1.17e-27 | 0.003532 | FLAGGED |
| Universal | EXECUTED | 100 | 0 | 1/1 | 0.690000 | 1.82e-67 | 0.003532 | FLAGGED |
| ApproximateEntropy | EXECUTED | 100 | 0 | 1/1 | 0.000000 | 6.19e-188 | 0.003532 | FLAGGED |
| RandomExcursions | NOT_APPLICABLE | 0 | 100 | 0/8 | n/a | n/a | n/a | not evaluated: no applicable sequences |
| RandomExcursionsVariant | NOT_APPLICABLE | 0 | 100 | 0/18 | n/a | n/a | n/a | not evaluated: no applicable sequences |
| Serial | EXECUTED | 100 | 0 | 2/2 | 0.000000 | 6.19e-188 | 1.25e-05 | FLAGGED (2/2 series; more than chance) |
| LinearComplexity | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.759756 | 1.000000 | no series flagged |

| series | passed/applicable | proportion range (official) | uniformity P | flag |
|---|---|---|---|---|
| Frequency | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| BlockFrequency | 21/100 | 96..101 | 1.90e-179 | PROPORTION UNIFORMITY |
| CumulativeSums forward | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| CumulativeSums reverse | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Runs | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| LongestRun | 99/100 | 96..101 | 0.122325 | - |
| Rank | 100/100 | 96..101 | 0.851383 | - |
| FFT | 99/100 | 96..101 | 0.699313 | - |
| OverlappingTemplate | 84/100 | 96..101 | 1.17e-27 | PROPORTION UNIFORMITY |
| Universal | 69/100 | 96..101 | 1.82e-67 | PROPORTION UNIFORMITY |
| ApproximateEntropy | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Serial p_value1 | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| Serial p_value2 | 0/100 | 96..101 | 6.19e-188 | PROPORTION UNIFORMITY |
| LinearComplexity | 99/100 | 96..101 | 0.759756 | - |

| series | applicable | passed | flag | official report rule: sample / passed / flag | applicable but printed 0.000000 |
|---|---|---|---|---|---|
| RandomExcursions x=-4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=-3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=-2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=-1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursions x=+4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-9 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-8 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-7 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-6 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-5 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=-1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+1 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+2 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+3 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+4 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+5 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+6 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+7 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+8 | 0 | 0 | no | 0 / 0 / no | 0 |
| RandomExcursionsVariant x=+9 | 0 | 0 | no | 0 / 0 / no | 0 |

### frac8

| test | status | sequences used | excluded (not applicable) | flagged series | lowest pass proportion | lowest uniformity P | chance tail p | verdict |
|---|---|---|---|---|---|---|---|---|
| Frequency | EXECUTED | 100 | 0 | 0/1 | 0.970000 | 0.145326 | 1.000000 | no series flagged |
| BlockFrequency | EXECUTED | 100 | 0 | 0/1 | 0.980000 | 0.494392 | 1.000000 | no series flagged |
| CumulativeSums | EXECUTED | 100 | 0 | 0/2 | 0.970000 | 0.534146 | 1.000000 | no series flagged |
| Runs | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.911413 | 1.000000 | no series flagged |
| LongestRun | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.080519 | 1.000000 | no series flagged |
| Rank | EXECUTED | 100 | 0 | 0/1 | 0.970000 | 0.971699 | 1.000000 | no series flagged |
| FFT | EXECUTED | 100 | 0 | 0/1 | 0.980000 | 0.090936 | 1.000000 | no series flagged |
| NonOverlappingTemplate | EXECUTED | 100 | 0 | 0/148 | 0.960000 | 0.000818 | 1.000000 | no series flagged |
| OverlappingTemplate | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.678686 | 1.000000 | no series flagged |
| Universal | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.058984 | 1.000000 | no series flagged |
| ApproximateEntropy | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.383827 | 1.000000 | no series flagged |
| RandomExcursions | EXECUTED | 54 | 46 | 0/8 | 0.981481 | 0.045675 | 1.000000 | no series flagged |
| RandomExcursionsVariant | EXECUTED | 54 | 46 | 0/18 | 0.962963 | 0.020548 | 1.000000 | no series flagged |
| Serial | EXECUTED | 100 | 0 | 0/2 | 0.980000 | 0.020548 | 1.000000 | no series flagged |
| LinearComplexity | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.474986 | 1.000000 | no series flagged |

| series | passed/applicable | proportion range (official) | uniformity P | flag |
|---|---|---|---|---|
| Frequency | 97/100 | 96..101 | 0.145326 | - |
| BlockFrequency | 98/100 | 96..101 | 0.494392 | - |
| CumulativeSums forward | 97/100 | 96..101 | 0.616305 | - |
| CumulativeSums reverse | 98/100 | 96..101 | 0.534146 | - |
| Runs | 100/100 | 96..101 | 0.911413 | - |
| LongestRun | 99/100 | 96..101 | 0.080519 | - |
| Rank | 97/100 | 96..101 | 0.971699 | - |
| FFT | 98/100 | 96..101 | 0.090936 | - |
| OverlappingTemplate | 100/100 | 96..101 | 0.678686 | - |
| Universal | 99/100 | 96..101 | 0.058984 | - |
| ApproximateEntropy | 99/100 | 96..101 | 0.383827 | - |
| Serial p_value1 | 98/100 | 96..101 | 0.554420 | - |
| Serial p_value2 | 100/100 | 96..101 | 0.020548 | - |
| LinearComplexity | 100/100 | 96..101 | 0.474986 | - |

| series | applicable | passed | flag | official report rule: sample / passed / flag | applicable but printed 0.000000 |
|---|---|---|---|---|---|
| RandomExcursions x=-4 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursions x=-3 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursions x=-2 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursions x=-1 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursions x=+1 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursions x=+2 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursions x=+3 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursions x=+4 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursionsVariant x=-9 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=-8 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=-7 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=-6 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursionsVariant x=-5 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursionsVariant x=-4 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=-3 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=-2 | 54 | 52 | no | 54 / 52 / no | 0 |
| RandomExcursionsVariant x=-1 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursionsVariant x=+1 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=+2 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=+3 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=+4 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=+5 | 54 | 54 | no | 54 / 54 / no | 0 |
| RandomExcursionsVariant x=+6 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursionsVariant x=+7 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursionsVariant x=+8 | 54 | 53 | no | 54 / 53 / no | 0 |
| RandomExcursionsVariant x=+9 | 54 | 54 | no | 54 / 54 / no | 0 |

### mantissa8

| test | status | sequences used | excluded (not applicable) | flagged series | lowest pass proportion | lowest uniformity P | chance tail p | verdict |
|---|---|---|---|---|---|---|---|---|
| Frequency | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.719747 | 1.000000 | no series flagged |
| BlockFrequency | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.759756 | 1.000000 | no series flagged |
| CumulativeSums | EXECUTED | 100 | 0 | 0/2 | 0.990000 | 0.048716 | 1.000000 | no series flagged |
| Runs | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.719747 | 1.000000 | no series flagged |
| LongestRun | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.474986 | 1.000000 | no series flagged |
| Rank | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.514124 | 1.000000 | no series flagged |
| FFT | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.115387 | 1.000000 | no series flagged |
| NonOverlappingTemplate | EXECUTED | 100 | 0 | 0/148 | 0.960000 | 0.000145 | 1.000000 | no series flagged |
| OverlappingTemplate | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.275709 | 1.000000 | no series flagged |
| Universal | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.062821 | 1.000000 | no series flagged |
| ApproximateEntropy | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.657933 | 1.000000 | no series flagged |
| RandomExcursions | EXECUTED | 69 | 31 | 0/8 | 0.985507 | 0.015065 | 1.000000 | no series flagged |
| RandomExcursionsVariant | EXECUTED | 69 | 31 | 0/18 | 0.956522 | 0.023812 | 1.000000 | no series flagged |
| Serial | EXECUTED | 100 | 0 | 0/2 | 0.990000 | 0.289667 | 1.000000 | no series flagged |
| LinearComplexity | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.657933 | 1.000000 | no series flagged |

| series | passed/applicable | proportion range (official) | uniformity P | flag |
|---|---|---|---|---|
| Frequency | 99/100 | 96..101 | 0.719747 | - |
| BlockFrequency | 99/100 | 96..101 | 0.759756 | - |
| CumulativeSums forward | 99/100 | 96..101 | 0.275709 | - |
| CumulativeSums reverse | 99/100 | 96..101 | 0.048716 | - |
| Runs | 100/100 | 96..101 | 0.719747 | - |
| LongestRun | 100/100 | 96..101 | 0.474986 | - |
| Rank | 100/100 | 96..101 | 0.514124 | - |
| FFT | 100/100 | 96..101 | 0.115387 | - |
| OverlappingTemplate | 100/100 | 96..101 | 0.275709 | - |
| Universal | 99/100 | 96..101 | 0.062821 | - |
| ApproximateEntropy | 99/100 | 96..101 | 0.657933 | - |
| Serial p_value1 | 99/100 | 96..101 | 0.289667 | - |
| Serial p_value2 | 99/100 | 96..101 | 0.350485 | - |
| LinearComplexity | 100/100 | 96..101 | 0.657933 | - |

| series | applicable | passed | flag | official report rule: sample / passed / flag | applicable but printed 0.000000 |
|---|---|---|---|---|---|
| RandomExcursions x=-4 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursions x=-3 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursions x=-2 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursions x=-1 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursions x=+1 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursions x=+2 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursions x=+3 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursions x=+4 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=-9 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursionsVariant x=-8 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursionsVariant x=-7 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursionsVariant x=-6 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursionsVariant x=-5 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=-4 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=-3 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursionsVariant x=-2 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=-1 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=+1 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=+2 | 69 | 66 | no | 69 / 66 / no | 0 |
| RandomExcursionsVariant x=+3 | 69 | 66 | no | 69 / 66 / no | 0 |
| RandomExcursionsVariant x=+4 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=+5 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=+6 | 69 | 68 | no | 69 / 68 / no | 0 |
| RandomExcursionsVariant x=+7 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursionsVariant x=+8 | 69 | 69 | no | 69 / 69 / no | 0 |
| RandomExcursionsVariant x=+9 | 69 | 69 | no | 69 / 69 / no | 0 |

### mantissa8_xor

| test | status | sequences used | excluded (not applicable) | flagged series | lowest pass proportion | lowest uniformity P | chance tail p | verdict |
|---|---|---|---|---|---|---|---|---|
| Frequency | EXECUTED | 100 | 0 | 0/1 | 0.980000 | 0.032923 | 1.000000 | no series flagged |
| BlockFrequency | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.779188 | 1.000000 | no series flagged |
| CumulativeSums | EXECUTED | 100 | 0 | 0/2 | 0.980000 | 0.534146 | 1.000000 | no series flagged |
| Runs | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.678686 | 1.000000 | no series flagged |
| LongestRun | EXECUTED | 100 | 0 | 0/1 | 0.980000 | 0.834308 | 1.000000 | no series flagged |
| Rank | EXECUTED | 100 | 0 | 0/1 | 0.980000 | 0.419021 | 1.000000 | no series flagged |
| FFT | EXECUTED | 100 | 0 | 0/1 | 0.990000 | 0.678686 | 1.000000 | no series flagged |
| NonOverlappingTemplate | EXECUTED | 100 | 0 | 1/148 | 0.950000 | 0.017912 | 0.407681 | 1/148 series flagged; consistent with chance |
| OverlappingTemplate | EXECUTED | 100 | 0 | 0/1 | 0.980000 | 0.129620 | 1.000000 | no series flagged |
| Universal | EXECUTED | 100 | 0 | 0/1 | 1.000000 | 0.554420 | 1.000000 | no series flagged |
| ApproximateEntropy | EXECUTED | 100 | 0 | 0/1 | 0.970000 | 0.834308 | 1.000000 | no series flagged |
| RandomExcursions | EXECUTED | 66 | 34 | 0/8 | 0.969697 | 0.008879 | 1.000000 | no series flagged |
| RandomExcursionsVariant | EXECUTED | 66 | 34 | 1/18 | 0.984848 | 7.81e-05 | 0.011430 | 1/18 series flagged; borderline (chance tail p < 0.05) |
| Serial | EXECUTED | 100 | 0 | 0/2 | 1.000000 | 0.090936 | 1.000000 | no series flagged |
| LinearComplexity | EXECUTED | 100 | 0 | 0/1 | 0.980000 | 0.851383 | 1.000000 | no series flagged |

| series | passed/applicable | proportion range (official) | uniformity P | flag |
|---|---|---|---|---|
| Frequency | 98/100 | 96..101 | 0.032923 | - |
| BlockFrequency | 99/100 | 96..101 | 0.779188 | - |
| CumulativeSums forward | 98/100 | 96..101 | 0.911413 | - |
| CumulativeSums reverse | 100/100 | 96..101 | 0.534146 | - |
| Runs | 99/100 | 96..101 | 0.678686 | - |
| LongestRun | 98/100 | 96..101 | 0.834308 | - |
| Rank | 98/100 | 96..101 | 0.419021 | - |
| FFT | 99/100 | 96..101 | 0.678686 | - |
| OverlappingTemplate | 98/100 | 96..101 | 0.129620 | - |
| Universal | 100/100 | 96..101 | 0.554420 | - |
| ApproximateEntropy | 97/100 | 96..101 | 0.834308 | - |
| Serial p_value1 | 100/100 | 96..101 | 0.997823 | - |
| Serial p_value2 | 100/100 | 96..101 | 0.090936 | - |
| LinearComplexity | 98/100 | 96..101 | 0.851383 | - |

| series | applicable | passed | flag | official report rule: sample / passed / flag | applicable but printed 0.000000 |
|---|---|---|---|---|---|
| RandomExcursions x=-4 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursions x=-3 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursions x=-2 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursions x=-1 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursions x=+1 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursions x=+2 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursions x=+3 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursions x=+4 | 66 | 64 | no | 66 / 64 / no | 0 |
| RandomExcursionsVariant x=-9 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=-8 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=-7 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=-6 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=-5 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursionsVariant x=-4 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursionsVariant x=-3 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursionsVariant x=-2 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=-1 | 66 | 66 | yes | 66 / 66 / yes | 0 |
| RandomExcursionsVariant x=+1 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=+2 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=+3 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursionsVariant x=+4 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=+5 | 66 | 66 | no | 66 / 66 / no | 0 |
| RandomExcursionsVariant x=+6 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursionsVariant x=+7 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursionsVariant x=+8 | 66 | 65 | no | 66 / 65 / no | 0 |
| RandomExcursionsVariant x=+9 | 66 | 65 | no | 66 / 65 / no | 0 |

### Flagged series in methods with at most a few flags

Each flag below is shown with the official uniformity P-value and the same chi-square computed with the exact expected count m/10. The official code truncates m/10 to an integer, which inflates the statistic when m is not a multiple of 10. The official flag is what counts; the second column only shows how sensitive it is.

| method | series | passed/m | official proportion range | uniformity P (official) | uniformity P (exact m/10) | flag |
|---|---|---|---|---|---|---|
| mantissa8_xor | NonOverlappingTemplate template141 | 95/100 | 96..101 | 0.534146 | 0.534146 | proportion  |
| mantissa8_xor | RandomExcursionsVariant x=-1 | 66/66 | 62..67 | 7.81e-05 | 0.000338 | uniformity |

**Excluded random-excursion sequences.** A sequence is excluded from both random-excursion tests when its walk has fewer than 500 cycles (J). For i.i.d. uniform bits with n = 10^6, J is approximately |Z| * sqrt(n) for a standard normal Z, so about 38% of sequences are expected to be excluded. Per method (J recomputed from the input bits and checked against stats.txt):

| method | J min | J median | J max | applicable (J >= 500) | sequences |
|---|---|---|---|---|---|
| sign | 1 | 11 | 64 | 0 | 100 |
| arccos8 | 1 | 46 | 309 | 0 | 100 |
| frac8 | 13 | 587 | 2982 | 54 | 100 |
| mantissa8 | 3 | 682 | 2361 | 69 | 100 |
| mantissa8_xor | 31 | 648 | 2945 | 66 | 100 |

SP 800-22 section 4.2.2 asks for at least 55 sequences for the uniformity assessment. Where fewer sequences are applicable, the uniformity P-value of the random-excursion tests is only indicative.

### Summary across methods

| test | sign | arccos8 | frac8 | mantissa8 | mantissa8_xor |
|---|---|---|---|---|---|
| Frequency | 1/1 flagged (100 seq.) | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| BlockFrequency | 1/1 flagged (100 seq.) | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| CumulativeSums | 2/2 flagged (100 seq.) | 2/2 flagged (100 seq.) | 0/2 flagged (100 seq.) | 0/2 flagged (100 seq.) | 0/2 flagged (100 seq.) |
| Runs | 1/1 flagged (100 seq.) | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| LongestRun | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| Rank | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| FFT | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| NonOverlappingTemplate | 136/148 flagged (100 seq.) | 81/148 flagged (100 seq.) | 0/148 flagged (100 seq.) | 0/148 flagged (100 seq.) | 1/148 flagged (100 seq.) |
| OverlappingTemplate | 1/1 flagged (100 seq.) | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| Universal | 1/1 flagged (100 seq.) | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| ApproximateEntropy | 1/1 flagged (100 seq.) | 1/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |
| RandomExcursions | not applicable (0 seq.) | not applicable (0 seq.) | 0/8 flagged (54 seq.) | 0/8 flagged (69 seq.) | 0/8 flagged (66 seq.) |
| RandomExcursionsVariant | not applicable (0 seq.) | not applicable (0 seq.) | 0/18 flagged (54 seq.) | 0/18 flagged (69 seq.) | 1/18 flagged (66 seq.) |
| Serial | 2/2 flagged (100 seq.) | 2/2 flagged (100 seq.) | 0/2 flagged (100 seq.) | 0/2 flagged (100 seq.) | 0/2 flagged (100 seq.) |
| LinearComplexity | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) | 0/1 flagged (100 seq.) |

## 5. Comparison with the previous Python evaluation

The earlier `isc_seq.nist` results (`results/sequence_generation/default_20261025/nist/`) were not modified. Per-sequence p-values on the same sequences, for the 12 series both implementations compute:

Largest absolute p-value difference over all 60 method x series pairs and 100 sequences: **5.00e-07**; sequences whose pass/fail decision at alpha = 0.01 differs: **0**. The official outputs are printed with 6 decimals, so differences up to 5e-7 are rounding.

Protocol-level differences: the earlier Python protocol flagged only proportions below the interval and computed uniformity from unrounded p-values with fractional expected counts. The official report also flags proportions above the interval, truncates the interval bounds to integers, reads p-values back as single-precision floats and uses integer expected counts (m/10). The previous evaluation also did not run template matching, linear complexity or random excursions.

## 6. Discrepancies investigated

**DFT worked example (SP 800-22 section 2.6.8).** The example sequence was run through the official binary with n = 100. It reports p = 0.646355 (stats below); `isc_seq.nist.dft` gives 0.646355. SP 800-22 prints N1 = 46, d = -1.376494, P = 0.168669. The official code and the earlier implementation agree with each other (N_l = 48 peaks below the threshold), not with the printed example. The printed example therefore cannot be reproduced from its stated input with the official 2.1.2 code.

```
FFT TEST
		-------------------------------------------
		COMPUTATIONAL INFORMATION:
		-------------------------------------------
		(a) Percentile = 96.000000
		(b) N_l        = 48.000000
		(c) N_o        = 47.500000
		(d) d          = 0.458831
		-------------------------------------------
SUCCESS		p_value = 0.646355
```

**Maurer universal illustration (section 2.9.4, L = 2, Q = 4).** The printed sum 7.169925 and fn = 1.1949875 are reproduced (recomputed fn = 1.1949875). The printed P = 0.767189 equals erfc(|fn - E| / (sqrt(2) * sqrt(variance))) = 0.767189, i.e. it uses sigma = sqrt(variance). The test description and the official code use sigma = c * sqrt(variance / K), which gives 0.063454 (`isc_seq.nist.universal`: 0.063454). The illustration is inconsistent with the formula; it is not an implementation error.

**Maurer universal example (section 2.9.8, G-SHA-1, n = 1,048,576).** It needs the G-SHA-1 bitstream. The STS built-in generator stores 32-bit SHA-1 words in `unsigned long` (`include/config.h`), which is 64 bits on this x86_64 Linux build. Run with the built-in generator, the official binary reproduces the printed K = 148516 and sigma = 0.002703, so the c * sqrt(variance / K) formula is confirmed, but its p-value is 0.000000 instead of 0.427733. The 1,000,000-bit built-in G-SHA-1 run also fails to reproduce Appendix B example 3 (table below), whereas the shipped `data.sha1` file does. The built-in generator output is therefore not valid on this platform. It is not even repeatable: an earlier trial run of the same job, made while preparing the harness and not archived, gave sum = 689001.559486 instead of the value below, which points to undefined behaviour. A Python replica of the generator did not reproduce `data.sha1` and was discarded. **The 2.9.8 example was not reproduced.**

```
UNIVERSAL STATISTICAL TEST
		--------------------------------------------
		COMPUTATIONAL INFORMATION:
		--------------------------------------------
		(a) L         = 7
		(b) Q         = 1280
		(c) K         = 148516
		(d) sum       = 689020.251015
		(e) sigma     = 0.002703
		(f) variance  = 3.125000
		(g) exp_value = 6.196251
		(h) phi       = 4.639367
		(i) WARNING:  4 bits were discarded.
		-----------------------------------------
FAILURE		p_value = 0.000000
```

| test | Appendix B (G-SHA-1) | built-in generator on this build |
|---|---|---|
| Frequency | 0.604458 | 0.000000 |
| Block Frequency (m = 128) | 0.091517 | 0.000000 |
| Cusum-Forward | 0.451231 | 0.000000 |
| Cusum-Reverse | 0.550134 | 0.000000 |
| Runs | 0.309757 | 0.000000 |
| Long Runs of Ones | 0.657812 | 0.000000 |
| Rank | 0.577829 | 0.000000 |
| Spectral DFT | 0.163062 | 0.000000 |
| Non-overlapping Templates (m = 9, B = 000000001) | 0.496601 | 0.000000 |
| Overlapping Templates (m = 9) | 0.339426 | 0.000000 |
| Universal | 0.411079 | 0.000000 |
| Approximate Entropy (m = 10) | 0.982885 | 0.000000 |
| Random Excursions (x = +1) | 0.000000 | 0.000000 |
| Random Excursions Variant (x = -1) | 0.000000 | 0.000000 |
| Linear Complexity (M = 500) | 0.309412 | 0.786315 |
| Serial (m = 16, del Psi^2_m) | 0.760793 | 0.000000 |

**Random-excursion reporting rule in finalAnalysisReport.** For sequences with fewer than 500 cycles the official code writes 0.000000 as the p-value. `finalAnalysisReport.txt` then drops every value <= 0, which would also drop a genuine p-value below 5e-7 printed as 0.000000. This analysis decides applicability from J in `stats.txt`, cross-checked against J recomputed from the input bits, and reports both counts. The 'applicable but printed 0.000000' column shows where the two rules differ.

**Overlapping template probabilities.** STS 2.1.2 contains a corrected pi table but overwrites it at run time with values from its `Pr(u, eta)` approximation. Results here are those of the official code as distributed.

## 7. Interpretation and limitations

- These are statistical tests of the bitstreams, which can only reject the hypothesis of i.i.d. uniform bits. A series without flags means these tests at this sample size detected no deviation. It does not show randomness, unpredictability or cryptographic security. The ISC generator is a deterministic, publicly specified map, and its security against an adversary who knows the map is not addressed by any test here.
- One sample of 100 sequences per method, all from one machine and one floating-point environment (see the sequence-generation run's environment.json). Multiple testing: 188 series per method, so isolated flags are expected by chance; see the chance tail p column.
- Random-excursion tests used only the applicable sequences. With fewer than 55 applicable sequences the uniformity statistic is unreliable, and with none the test is not evaluated.
- The official code's own known quirks (single-precision re-reading, the overlapping-template approximation, built-in generator portability) are documented above and were not altered.

## 8. Reproducing

```bash
# 1. official source (already downloaded; verify the hash)
curl -L -o third_party/nist_sts/download/sts-2_1_2.zip https://csrc.nist.gov/CSRC/media/Projects/Random-Bit-Generation/documents/sts-2_1_2.zip
sha256sum third_party/nist_sts/download/sts-2_1_2.zip   # 0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157
# 2. build in WSL Ubuntu 24.04 with the unmodified makefile
cd third_party/nist_sts && unzip -q download/sts-2_1_2.zip -d src_pristine \
  && cp -r src_pristine/sts-2.1.2/sts-2.1.2/. build_linux/
wsl -d Ubuntu-24.04 --cd <path>/third_party/nist_sts/build_linux -- make
# 3. execute and analyse (new run id each time; existing runs are never overwritten)
python experiments/run_official_sts.py --run-id <new id> --workers 6
python experiments/analyze_official_sts.py --run-id <new id>
```

The menu answers sent to `assess` for every job are in `run_config.json` (`jobs[].stdin`) and `raw/**/assess_stdout.log`; timestamps are in `execution_log.txt`.

## 9. Files

`provenance/` (source and build provenance, build log), `inputs/` (input hashes per file and per sequence), `run_config.json`, `execution_log.txt`, `raw/appendix_b/`, `raw/examples/`, `raw/methods/<method>/experiments/AlgorithmTesting/` (unaltered official outputs: results.txt, stats.txt, data*.txt, freq.txt, finalAnalysisReport.txt), `analysis/per_sequence_<method>.csv`, `analysis/series_summary.csv`, `analysis/test_summary.csv`, `analysis/appendix_b_validation.csv`, `analysis/python_vs_official.csv`, `analysis/worked_examples.json`, `analysis/summary.json`, `manifest.json` (SHA-256 of every file).
