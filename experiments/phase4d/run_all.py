"""Run the full Phase 4D P0/P1 experiment sequence in order."""
import subprocess
import sys

SCRIPTS = [
    "inspect_key_derivation.py",
    "nonce_analysis.py",
    "chosen_plaintext.py",
    "diffusion_analysis.py",
    "permutation_analysis.py",
    "sbox_analysis.py",
    "keyspace_analysis.py",
    "authentication_analysis.py",
    "claim_evidence.py",
]

if __name__ == "__main__":
    for s in SCRIPTS:
        print(f"\n=== {s} ===")
        r = subprocess.run([sys.executable, s])
        if r.returncode != 0:
            print(f"FAILED: {s}", file=sys.stderr)
            sys.exit(1)
