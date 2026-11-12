"""ISC-IMG v1: experimental lossless image cipher using the frozen ISC map (research prototype).

Specification: research/algorithm_design.md (revision 2). Confidentiality is UNPROVEN; integrity relies on
HMAC-SHA-256 (encrypt-then-MAC). Not for protecting real data.

Public API:
    generate_key() -> 32 bytes
    encrypt(key, image_uint8_array) -> bytes          (NumPy)
    decrypt(key, ciphertext) -> uint8 array            (NumPy)
    encrypt_bytes(key, data, h, w, c, backend) / decrypt_bytes(key, ciphertext, backend)
Backends: "numpy" (V1, default) and "reference" (R1, pure Python, no NumPy required).
"""

from .cipher import decrypt, decrypt_bytes, encrypt, encrypt_bytes
from .errors import (AuthenticationError, InvalidImage, InvalidKey, ISCError, Malformed,
                     NumericalDivergenceError, ProfileError)
from .kdf import generate_key

__version__ = "1.0.0-rev2"
