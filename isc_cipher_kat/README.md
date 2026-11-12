# isc_cipher_kat: known-answer vectors and Gate R tooling for ISC-IMG v1

| path | content | independent of `isc_cipher`? |
|---|---|---|
| `oracle/oracle.c`, `oracle/build_oracle.sh` | C oracle linking the **unmodified** fdlibm 5.3 sources (`third_party/fdlibm/netlib_5.3`, hashes verified at build). It implements the ISC step with the normative operation order (`research/algorithm_design.md` §6.1). Build: gcc 13.3.0, `-O0 -ffp-contract=off -fno-builtin -D__LITTLE_ENDIAN`, WSL Ubuntu 24.04 x86_64. | yes (C, official fdlibm) |
| `vectors/trig_kat.txt.gz` | 74,063 sin/cos results (arg, sin, cos as binary64 hex): fdlibm branch thresholds, ±64 ulp around k·π/2 (k = 1..15), special values, 50,000 uniform in [−24, 24], 20,000 log-uniform small magnitudes | yes (oracle) |
| `vectors/traj_kat.json` | 10 ISC trajectories × 100,000 steps: SHA-256 over every state (BE64 x ‖ BE64 y) plus checkpoints at steps 1, 10, …, 100,000 | yes (oracle) |
| `vectors/stream_kat.json` | public test key 00..1f, nonce 00..0f, shape 64×64×3: the 256 seeds, initial states, states after burn-in, the first 1024 bytes of each stream, states after 8 output steps | lane states and bytes: yes (oracle). Seeds come from `isc_cipher.kdf`, which is checked against RFC 5869 and `cryptography`. |
| `vectors/cipher_kat.json` | 6 shapes: S-box, IVs, π, stream prefixes, steps, KCV, body and ciphertext hashes, full ciphertext for n ≤ 300 | **no**: produced by R1. Checked by V1 (Windows) and by R1 on WSL (cross-implementation, not independent). |
| `vectors/PROVENANCE.json` | oracle build info, fdlibm hashes, generator script hash, test key and nonce | |
| `make_kat.py` | generates the vectors; refuses to overwrite | |
| `gate_r.py` | Gate R checks for one backend, writing to `results/cipher_validation/gate_r_<label>_<backend>_<UTC>/` | |

The test key and nonce are **public** and must never be used for real data.

Commands:

```bash
# build the oracle (inside WSL / Linux x86_64)
sh isc_cipher_kat/oracle/build_oracle.sh
# generate vectors (Windows, project root; calls the oracle through WSL)
python isc_cipher_kat/make_kat.py
# Gate R
python -I isc_cipher_kat/gate_r.py --backend numpy --label E1-windows
python -I isc_cipher_kat/gate_r.py --backend reference --label E1-windows
python3 -I isc_cipher_kat/gate_r.py --backend reference --label E2-wsl-ubuntu      # inside WSL, no NumPy needed
```
