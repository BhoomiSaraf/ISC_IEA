"""Standard-library-only worker for A11 on the second environment (E2, WSL Ubuntu, no NumPy).

    python3 -I -m isc_eval.xplat_worker decrypt <dir>              decrypt *.isci with R1, write decrypt_results.json
    python3 -I -m isc_eval.xplat_worker encrypt <dir> <count>      R1-encrypt random images, write *.isci + *.plain
    python3 -I -m isc_eval.xplat_worker mathproxy <out_dir>        host math.sin/cos on the KAT arguments + trajectories
Run from the project root. Keys are PUBLIC test keys (isc_eval.common.public_key).
"""

import gzip
import hashlib
import json
import os
import platform
import random
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isc_cipher import ISCError, decrypt_bytes, encrypt_bytes  # noqa: E402
from isc_eval.common import public_key  # noqa: E402

KEY_LABEL = "A11/xplat"


def cmd_decrypt(d):
    key = public_key(KEY_LABEL)
    res = {"platform": platform.platform(), "python": sys.version, "results": {}}
    for name in sorted(os.listdir(d)):
        if not name.endswith(".isci"):
            continue
        z = open(os.path.join(d, name), "rb").read()
        try:
            p, h, w, c = decrypt_bytes(key, z, backend="reference")
            res["results"][name] = {"ok": True, "sha256": hashlib.sha256(p).hexdigest(), "dims": [h, w, c]}
        except ISCError as e:
            res["results"][name] = {"ok": False, "error": type(e).__name__}
    json.dump(res, open(os.path.join(d, "decrypt_results.json"), "w"), indent=1)


def cmd_encrypt(d, count):
    key = public_key(KEY_LABEL)
    rnd = random.Random(20261026)
    os.makedirs(d, exist_ok=True)
    for i in range(count):
        h, w, c = 16, 16, rnd.choice([1, 3])
        p = bytes(rnd.randrange(256) for _ in range(h * w * c))
        z = encrypt_bytes(key, p, h, w, c, backend="reference")
        open(os.path.join(d, f"img{i:03d}.isci"), "wb").write(z)
        open(os.path.join(d, f"img{i:03d}.plain"), "wb").write(p)
    json.dump({"platform": platform.platform(), "python": sys.version, "count": count},
              open(os.path.join(d, "encrypt_info.json"), "w"), indent=1)


def cmd_mathproxy(out):
    import math
    from isc_cipher.isc_step import step_ref
    os.makedirs(out, exist_ok=True)
    vec = os.path.join(ROOT, "isc_cipher_kat", "vectors")
    h = hashlib.sha256()
    lines = []
    for f in ("trig_kat.txt.gz", "trig_kat_ext.txt.gz"):
        for line in gzip.open(os.path.join(vec, f), "rt"):
            if line.startswith("#"):
                continue
            a = line.split()[0]
            x = struct.unpack(">d", bytes.fromhex(a))[0]
            s = struct.pack(">d", math.sin(x)).hex() + " " + struct.pack(">d", math.cos(x)).hex()
            lines.append(a + " " + s)
    with gzip.open(os.path.join(out, "math_trig.txt.gz"), "wt") as g:
        g.write("\n".join(lines) + "\n")
    traj = json.load(open(os.path.join(vec, "traj_kat.json")))["trajectories"]
    with open(os.path.join(out, "math_traj.bin"), "wb") as g:
        for t in traj:
            x = struct.unpack(">d", bytes.fromhex(t["x0"]))[0]
            y = struct.unpack(">d", bytes.fromhex(t["y0"]))[0]
            for _ in range(t["steps"]):
                try:
                    x, y = step_ref(x, y, sin=math.sin, cos=math.cos)
                except ValueError:
                    x = y = float("nan")
                g.write(struct.pack(">dd", x, y))
    json.dump({"platform": platform.platform(), "python": sys.version}, open(os.path.join(out, "info.json"), "w"))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "decrypt":
        cmd_decrypt(sys.argv[2])
    elif c == "encrypt":
        cmd_encrypt(sys.argv[2], int(sys.argv[3]))
    elif c == "mathproxy":
        cmd_mathproxy(sys.argv[2])
    else:
        sys.exit("unknown command")
