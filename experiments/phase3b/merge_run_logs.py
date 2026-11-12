"""Concatenate Stage A/B run logs plus environment info into phase_3b_run_log.txt."""
import platform
import sys

import numpy
import scipy

lines = []
lines.append(f"Phase 3B run log")
lines.append(f"Python: {sys.version}")
lines.append(f"Platform: {platform.platform()}")
lines.append(f"NumPy: {numpy.__version__}  SciPy: {scipy.__version__}")
lines.append("")
lines.append("=== pilot_benchmark.py ===")
with open("raw/pilot_benchmark.json") as f:
    lines.append(f.read())
lines.append("")
lines.append("=== stage_a_primary.py ===")
with open("raw/stage_a_run_log.txt") as f:
    lines.append(f.read())
lines.append("")
lines.append("=== stage_b_burnin.py ===")
with open("raw/stage_b_run_log.txt") as f:
    lines.append(f.read())

with open("../../phase_3b_run_log.txt", "w") as f:
    f.write("\n".join(lines))
print("wrote ../../phase_3b_run_log.txt")
