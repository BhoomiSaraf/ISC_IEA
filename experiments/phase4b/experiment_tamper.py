"""Experiment J: basic container/tamper regression check (Section 14).

Phase 4A already tested authentication exhaustively (every bit-flip over multiple ciphertexts).
This is a small image-level regression check only, not a repeat of that suite.
"""

import json
import os

import numpy as np

import config
from isc_cipher import container
from isc_cipher.cipher import decrypt_bytes, encrypt_bytes
from isc_cipher.errors import AuthenticationError, Malformed, NumericalDivergenceError
from isc_cipher.kdf import generate_key


def flip_bit(data, byte_index, bit_index=0):
    arr = bytearray(data)
    arr[byte_index] ^= (1 << bit_index)
    return bytes(arr)


def run():
    key = config.BASE_KEY
    wrong_key = generate_key()
    img = np.full((32, 32), 77, dtype=np.uint8)
    ct = encrypt_bytes(key, img.tobytes(), 32, 32, 1)
    hdr, body, tag = container.parse(ct)
    hl = container.header_len(hdr.version)

    cases = []

    def try_decrypt(label, z, use_key=None):
        try:
            p, h, w, c = decrypt_bytes(use_key or key, z)
            cases.append({"case": label, "raised": False, "exception": None,
                          "note": "UNEXPECTED: plaintext returned without error"})
        except (AuthenticationError, Malformed, NumericalDivergenceError) as e:
            cases.append({"case": label, "raised": True, "exception": type(e).__name__, "note": str(e)})
        except Exception as e:  # noqa: BLE001
            cases.append({"case": label, "raised": True, "exception": type(e).__name__,
                          "note": f"raised an exception type not in the expected set: {e}"})

    try_decrypt("flip_body_bit", flip_bit(ct, hl + 1, 2))
    try_decrypt("flip_header_bit", flip_bit(ct, 8, 0))  # inside H field
    try_decrypt("flip_tag_bit", flip_bit(ct, len(ct) - 1, 0))
    try_decrypt("wrong_key", ct, use_key=wrong_key)
    try_decrypt("truncated_ciphertext", ct[:-5])

    out = os.path.join(config.RESULTS_DIR, "experiment_J_tamper.json")
    with open(out, "w") as f:
        json.dump(cases, f, indent=2)
    n_ok = sum(1 for c in cases if c["raised"] and "UNEXPECTED" not in c["note"])
    print(f"Tamper regression: {n_ok}/{len(cases)} cases correctly rejected.")
    for c in cases:
        print(" ", c["case"], "->", c["exception"], "|", c["note"][:80])
    return cases


if __name__ == "__main__":
    run()
