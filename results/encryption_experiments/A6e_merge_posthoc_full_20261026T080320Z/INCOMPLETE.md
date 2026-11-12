# INCOMPLETE RUN: do not use as a completed A6(e) result

This marker was added on 2026-10-26, after the run was interrupted. No other file in this directory
was modified. The directory has no `summary.json` or `manifest.json` because `Run.finish()` was never
reached.

## What is usable
* `raw/part1_local_merging.json`: **Part 1 completed** (all spacings, coordinates and distances), and
  was written before the interruption. It is used as the Part 1 result of A6(e).

## What is not usable
* Part 2: only one line was logged before the process was killed (`log.txt`, last line,
  "P2 x after_1_step: distinct mean 988.0/1024"). It is **not** used as a result, for three reasons:
  * no raw file was written;
  * the distinct count used a 64-bit hash of the (x, y) pair, which is approximate, not exact;
  * the after-burn-in measurement never completed.
* Part 3: never started.

## Why it was interrupted (diagnosis)
* `part2()` used chunks of `(1 << 20) // 1024 = 1024` blocks, i.e. 1,048,576 lanes per `step_vec` call.
* Measured afterwards (`GetProcessMemoryInfo`): one `step_vec` step at 2^20 lanes has a peak working
  set of about 508 MB, because the fdlibm V1 kernel evaluates all branches with full-size temporaries.
  The input, output and index arrays come on top of that.
* About 0.7 GB of RAM was free at the time, so the process swapped heavily.
* Even without swapping, the after-burn-in measurement at this chunk size would take about
  1,024 steps × 2.8 s per chunk.
* The Git Bash `timeout 7200` wrapper did not terminate the Windows Python child. The process
  (PID 17720) was stopped manually with `taskkill /PID 17720 /F`. No exit status was recorded by the
  harness.

## Replacement
Parts 2 and 3 were re-run as a separate, memory-bounded run with its own config, seeds and manifest
(`A6e23_*` directories under `results/encryption_experiments/`); see `research/a6e_report.md`.
