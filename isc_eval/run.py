"""Gate A dispatcher:  python -m isc_eval.run <ID> --mode diagnostic|full

IDs: A1 A2 A3 A4 A5 A6 A6e A6e23 A7 A8 A9 A10 A11i A11ii A11iii A12 A13 A14 A15
"""

import argparse
import importlib

TABLE = {
    "A1": ("exp_misuse", "a1"), "A8": ("exp_misuse", "a8"), "A9": ("exp_misuse", "a9"),
    "A2": ("exp_integrity", "a2"), "A13": ("exp_integrity", "a13"),
    "A12": ("exp_nist", "a12"),
    "A11i": ("exp_numeric", "a11_xplat"), "A11ii": ("exp_numeric", "a11_hostlibm_proxy"), "A11iii": ("exp_numeric", "a11_kcv"),
    "A6": ("exp_states", "a6"), "A6e": ("exp_merge", "a6e"), "A6e23": ("exp_merge_p23", "a6e"),
    "A5": ("exp_sensitivity", "a5"), "A3": ("exp_sensitivity", "a3"),
    "A7": ("exp_stats", "a7"),
    "A15": ("exp_predict", "a15"), "A4": ("exp_predict", "a4"),
    "A14": ("exp_perf", "a14"), "A10": ("exp_perf", "a10"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment", choices=sorted(TABLE))
    ap.add_argument("--mode", choices=["diagnostic", "full"], required=True)
    a = ap.parse_args()
    mod, fn = TABLE[a.experiment]
    getattr(importlib.import_module(f"isc_eval.{mod}"), fn)(a.mode)


if __name__ == "__main__":
    main()
