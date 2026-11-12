"""Run one experiment worker under a supervisor with a VERIFIED stop (Windows):

    python -m isc_eval.supervise --wall-seconds 7200 --min-free-mb 200 -- -m isc_eval.run A6e23 --mode full

* The worker is started with subprocess.Popen (same interpreter, -E -s, cwd = project root) and its stdout is teed to a file.
* Every 5 s the supervisor records the worker's working set and the system's free RAM.
* If the wall-clock limit is exceeded or free RAM falls below --min-free-mb, it runs
  `taskkill /PID <pid> /T /F` on the whole process tree, waits, and verifies that the pid is gone.
* The record (exit code, killed flag and reason, verified termination, peak memory, run directory
  announced by the worker as "RUN_DIR <path>") is written to
  results/encryption_experiments/supervisor/<UTC>.json, together with <UTC>.stdout.txt.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time

from . import memwatch
from .common import OUT_ROOT, ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wall-seconds", type=float, required=True)
    ap.add_argument("--min-free-mb", type=float, default=200)
    ap.add_argument("worker", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    worker = a.worker[1:] if a.worker[:1] == ["--"] else a.worker
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = os.path.join(OUT_ROOT, "supervisor")
    os.makedirs(d, exist_ok=True)
    out_txt = open(os.path.join(d, ts + ".stdout.txt"), "x", encoding="utf-8")
    cmd = [sys.executable, "-E", "-s"] + worker      # -E -s: ignore PYTHON* env and user site; -m keeps ROOT importable
    rec = {"utc_start": ts, "command": cmd, "wall_seconds_limit": a.wall_seconds, "min_free_mb": a.min_free_mb,
           "run_dir": None, "killed": False, "kill_reason": None, "taskkill_returncode": None,
           "verified_terminated": None, "exit_code": None, "worker_peak_working_set_mb": None,
           "min_system_available_mb": None, "samples": 0}
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    rec["pid"] = p.pid

    def pump():
        for line in p.stdout:
            out_txt.write(line)
            out_txt.flush()
            sys.stdout.write(line)
            sys.stdout.flush()
            if line.startswith("RUN_DIR ") and rec["run_dir"] is None:
                rec["run_dir"] = line[8:].strip()
    th = threading.Thread(target=pump, daemon=True)
    th.start()
    while p.poll() is None:
        m = memwatch.other_process_mb(p.pid)
        if m:
            rec["worker_peak_working_set_mb"] = round(max(rec["worker_peak_working_set_mb"] or 0, m[1]), 1)
        _, avail = memwatch.system_mb()
        if avail is not None:
            rec["min_system_available_mb"] = round(min(rec["min_system_available_mb"] or 1e12, avail), 1)
        rec["samples"] += 1
        reason = None
        if time.time() - t0 > a.wall_seconds:
            reason = f"wall-clock limit {a.wall_seconds} s exceeded"
        elif avail is not None and avail < a.min_free_mb:
            reason = f"system available RAM {avail:.0f} MB < {a.min_free_mb} MB"
        if reason:
            rec["killed"], rec["kill_reason"] = True, reason
            rec["taskkill_returncode"] = subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                                                        capture_output=True).returncode
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            break
        time.sleep(5)
    if p.poll() is None:
        p.wait(timeout=30)
    th.join(timeout=10)
    rec["exit_code"] = p.returncode
    rec["verified_terminated"] = not memwatch.process_alive(p.pid)
    rec["wall_seconds"] = round(time.time() - t0, 1)
    out_txt.close()
    with open(os.path.join(d, ts + ".json"), "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    print("SUPERVISOR " + json.dumps(rec))
    sys.exit(0 if (rec["exit_code"] == 0 and not rec["killed"]) else 1)


if __name__ == "__main__":
    main()
