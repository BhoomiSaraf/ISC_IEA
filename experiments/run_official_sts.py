"""Run the official NIST STS 2.1.2 on the saved ISC bitstreams (execution stage).

Stage 1 of 2.  This script only executes the official `assess` binary and stores
its raw outputs; `experiments/analyze_official_sts.py` parses them and writes the
summaries and the report.

    python experiments/run_official_sts.py --run-id sts212_default_20261025

Inputs (read-only):
    results/sequence_generation/default_20261025/bitstreams/<method>.bin
    third_party/nist_sts/build_linux/assess   (built from the official sources)
Outputs: results/nist_sts_official/<run_id>/  (refuses to reuse an existing directory)
"""

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isc_seq import sts_official as so  # noqa: E402

STS_URL = "https://csrc.nist.gov/CSRC/media/Projects/Random-Bit-Generation/documents/sts-2_1_2.zip"
SP_URL = "https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-22r1a.pdf"
STS_PAGE = "https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software"
DISTRO = "Ubuntu-24.04"

APPENDIX_B_FILES = [  # (name, file, binary format?)
    ("pi", "data.pi", False), ("e", "data.e", False), ("sha1", "data.sha1", True),
    ("sqrt2", "data.sqrt2", False), ("sqrt3", "data.sqrt3", False),
]

# SP 800-22 Rev. 1a section 2.6.8 example sequence (n = 100).
DFT_EXAMPLE = ("11001001000011111101101010100010001000010110100011"
               "00001000110100110001001100011001100010100010111000")

LOG = None


def log(msg):
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wsl(cmd):
    return subprocess.run(["wsl", "-d", DISTRO, "--", "bash", "-c", cmd],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode(errors="replace").strip()


def provenance(run_dir, sts_dir, download_dir, build_dir):
    pdir = os.path.join(run_dir, "provenance")
    os.makedirs(pdir)
    src_files = {}
    pristine = os.path.join(sts_dir, "src_pristine", "sts-2.1.2", "sts-2.1.2")
    for base in ("src", "include", "makefile"):
        p = os.path.join(pristine, base)
        paths = [p] if os.path.isfile(p) else [os.path.join(p, f) for f in sorted(os.listdir(p))]
        for fp in paths:
            rel = os.path.relpath(fp, pristine).replace(os.sep, "/")
            src_files[rel] = sha256_file(fp)
            built = os.path.join(build_dir, rel)
            if sha256_file(built) != src_files[rel]:
                raise RuntimeError(f"build tree differs from official source: {rel}")
    info = {
        "suite": "NIST Statistical Test Suite (STS) 2.1.2",
        "source_page": STS_PAGE,
        "source_url": STS_URL,
        "source_zip_sha256": sha256_file(os.path.join(download_dir, "sts-2_1_2.zip")),
        "source_zip_bytes": os.path.getsize(os.path.join(download_dir, "sts-2_1_2.zip")),
        "source_http_headers": open(os.path.join(download_dir, "headers.txt"), encoding="utf-8").read(),
        "release_notes_from_page": ("sts-2_1_2.zip dated July 9, 2014: minor source corrections (non-overlapping "
                                    "template skip, overlapping template pi values). sts-2.1.1 (2010-08-11), "
                                    "sts-2.1 (2010-04-27)."),
        "documentation": "NIST SP 800-22 Rev. 1a (April 2010)",
        "documentation_url": SP_URL,
        "documentation_sha256": sha256_file(os.path.join(download_dir, "SP800-22r1a.pdf")),
        "source_file_sha256": src_files,
        "build_tree_identical_to_official_source": True,
        "build": {
            "host": DISTRO + " under WSL2",
            "command": "make   (official makefile, unmodified; CC = /usr/bin/gcc, flags -c -Wall)",
            "toolchain": wsl("gcc --version | head -1; make --version | head -1; ldd --version | head -1; uname -srm"),
            "assess_sha256": sha256_file(os.path.join(build_dir, "assess")),
            "warnings": "5 compiler warnings (unused variables, misleading indentation); see build.log",
        },
        "driver_host": {"python": sys.version.split()[0], "platform": platform.platform()},
    }
    with open(os.path.join(pdir, "sts_provenance.json"), "x", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    with open(os.path.join(build_dir, "build.log"), encoding="utf-8") as src, \
            open(os.path.join(pdir, "build.log"), "x", encoding="utf-8") as dst:
        dst.write(src.read())
    log(f"provenance recorded; assess sha256 {info['build']['assess_sha256']}")
    return info


def input_inventory(run_dir, seq_run, methods, n_bits):
    """Hash every input bitstream and each 1,000,000-bit sequence inside it."""
    manifest = json.load(open(os.path.join(seq_run, "manifest.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(seq_run, "config.json"), encoding="utf-8"))
    if cfg["bits_per_sequence"] != n_bits:
        raise RuntimeError("bits_per_sequence differs from the STS stream length")
    if n_bits % 32:
        raise RuntimeError("assess reads binary input in 4-byte words; n must be a multiple of 32")
    rows, files = [], {}
    nbytes = n_bits // 8
    for m in methods:
        path = os.path.join(seq_run, "bitstreams", f"{m}.bin")
        digest = sha256_file(path)
        recorded = manifest[f"bitstreams/{m}.bin"]["sha256"]
        if digest != recorded:
            raise RuntimeError(f"{m}.bin hash {digest} does not match the sequence-run manifest {recorded}")
        size = os.path.getsize(path)
        n_seq = size // nbytes
        if size != n_seq * nbytes or n_seq != cfg["n_sequences"]:
            raise RuntimeError(f"{m}.bin size {size} is not {cfg['n_sequences']} x {nbytes}")
        files[m] = {"path": os.path.relpath(path, ROOT).replace(os.sep, "/"), "sha256": digest,
                    "bytes": size, "sequences": n_seq}
        with open(path, "rb") as f:
            for i in range(n_seq):
                chunk = f.read(nbytes)
                rows.append({"method": m, "sequence": i, "id": f"{m}:{i:03d}", "byte_offset": i * nbytes,
                             "sha256": hashlib.sha256(chunk).hexdigest()})
    idir = os.path.join(run_dir, "inputs")
    os.makedirs(idir)
    with open(os.path.join(idir, "input_files.json"), "x", encoding="utf-8") as f:
        json.dump(files, f, indent=2)
    with open(os.path.join(idir, "input_sequences.csv"), "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log(f"inputs verified against {seq_run}/manifest.json: {len(rows)} sequences")
    return files


def run_one(label, workdir, sts_root, assess, input_path, n_bits, n_streams, binary, tests=None,
            generator=0, generator_dir="AlgorithmTesting"):
    so.prepare_workdir(workdir, sts_root, generator_dir)
    t0 = time.time()
    stdin = so.menu_answers(so.to_wsl_path(input_path) if input_path else None, n_streams, binary, tests, generator)
    log(f"start {label}: n={n_bits} streams={n_streams} binary={binary} tests={'all' if tests is None else tests} "
        f"generator={generator} stdin={stdin!r}")
    rc, out = so.run_assess(workdir, assess, input_path, n_bits, n_streams, binary, DISTRO,
                            os.path.join(workdir, "assess_stdout.log"), tests, generator)
    complete = "Statistical Testing Complete" in out
    errors = [ln.strip() for ln in out.splitlines() if "ERROR" in ln.upper()]
    log(f"end {label}: returncode={rc} complete={complete} errors={len(errors)} elapsed={time.time() - t0:.0f}s")
    return {"label": label, "returncode": rc, "complete": complete, "stdout_errors": errors,
            "elapsed_s": round(time.time() - t0, 1), "stdin": stdin, "n_bits": n_bits,
            "n_streams": n_streams, "binary": binary, "tests": tests or "all", "generator": generator}


def main():
    global LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--sequence-run", default=os.path.join(ROOT, "results", "sequence_generation", "default_20261025"))
    ap.add_argument("--sts-dir", default=os.path.join(ROOT, "third_party", "nist_sts"))
    ap.add_argument("--methods", default="sign,arccos8,frac8,mantissa8,mantissa8_xor")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    run_dir = os.path.join(ROOT, "results", "nist_sts_official", args.run_id)
    if os.path.exists(run_dir):
        raise FileExistsError(run_dir)
    os.makedirs(run_dir)
    LOG = os.path.join(run_dir, "execution_log.txt")
    build_dir = os.path.join(args.sts_dir, "build_linux")
    download_dir = os.path.join(args.sts_dir, "download")
    assess = os.path.join(build_dir, "assess")
    methods = args.methods.split(",")
    n_bits = 1_000_000
    log(f"command: {' '.join(sys.argv)}")

    provenance(run_dir, args.sts_dir, download_dir, build_dir)
    files = input_inventory(run_dir, args.sequence_run, methods, n_bits)

    config = {"run_id": args.run_id, "sequence_run": os.path.relpath(args.sequence_run, ROOT).replace(os.sep, "/"),
              "stream_length_bits": n_bits, "methods": methods, "parameters": so.DEFAULT_PARAMETERS,
              "input_format": "binary (assess mode 1): packed bytes, MSB first, read 4 bytes at a time; "
                              "the saved .bin files are used unchanged (no conversion)",
              "tests": "all 15 tests of STS 2.1.2", "wsl_distro": DISTRO, "jobs": []}
    raw = os.path.join(run_dir, "raw")
    jobs = []
    for name, fname, binary in APPENDIX_B_FILES:
        jobs.append(dict(label=f"appendix_b/{name}", workdir=os.path.join(raw, "appendix_b", name),
                         input_path=os.path.join(build_dir, "data", fname), n_bits=n_bits, n_streams=1,
                         binary=binary))
    ex = os.path.join(raw, "examples")
    os.makedirs(ex)
    dft_file = os.path.join(ex, "sp800-22_2.6.8_epsilon.txt")
    with open(dft_file, "x", encoding="ascii") as f:
        f.write(DFT_EXAMPLE + "\n")
    jobs.append(dict(label="examples/dft_2.6.8", workdir=os.path.join(ex, "dft_2.6.8"), input_path=dft_file,
                     n_bits=100, n_streams=1, binary=False, tests=["FFT"]))
    jobs.append(dict(label="examples/gsha1_n1000000_all", workdir=os.path.join(ex, "gsha1_n1000000_all"),
                     input_path=None, n_bits=1_000_000, n_streams=1, binary=False, generator=9,
                     generator_dir="G-SHA1"))
    jobs.append(dict(label="examples/universal_2.9.8", workdir=os.path.join(ex, "universal_2.9.8"),
                     input_path=None, n_bits=1_048_576, n_streams=1, binary=False, tests=["Universal"],
                     generator=9, generator_dir="G-SHA1"))
    for m in methods:
        jobs.append(dict(label=f"methods/{m}", workdir=os.path.join(raw, "methods", m),
                         input_path=os.path.join(ROOT, files[m]["path"]), n_bits=n_bits,
                         n_streams=files[m]["sequences"], binary=True))
    os.makedirs(os.path.join(raw, "appendix_b"))
    os.makedirs(os.path.join(raw, "methods"))

    results = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one, j["label"], j["workdir"], build_dir, assess, j["input_path"], j["n_bits"],
                            j["n_streams"], j["binary"], j.get("tests"), j.get("generator", 0),
                            j.get("generator_dir", "AlgorithmTesting")): j for j in jobs}
        for fut in cf.as_completed(futs):
            j = futs[fut]
            try:
                r = fut.result()
            except Exception as exc:  # recorded, never hidden
                r = {"label": j["label"], "exception": repr(exc), "complete": False}
                log(f"FAILED {j['label']}: {exc!r}")
            r["workdir"] = os.path.relpath(j["workdir"], run_dir).replace(os.sep, "/")
            r["input"] = None if j["input_path"] is None else os.path.relpath(j["input_path"], ROOT).replace(os.sep, "/")
            r["generator_dir"] = j.get("generator_dir", "AlgorithmTesting")
            results.append(r)
    config["jobs"] = sorted(results, key=lambda r: r["label"])
    with open(os.path.join(run_dir, "run_config.json"), "x", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    log("execution stage finished")


if __name__ == "__main__":
    main()
