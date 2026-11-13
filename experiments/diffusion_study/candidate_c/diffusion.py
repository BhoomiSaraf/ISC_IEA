"""Candidate C: Reversible Block-Based Feistel Diffusion.

Processes 4-byte blocks through an R-round Generalized Feistel Network (GFN)
with inter-block chaining across both forward and backward passes.

Block size: B = 4 bytes.
Number of rounds R: experimental parameter (default R = 4).

Round Function:
  In round r = 0..R-1, for block (x0, x1, x2, x3):
    x1 = x1 ^ S[(x0 + subkeys[4r + 0]) mod 256]
    x2 = x2 ^ S[(x1 + subkeys[4r + 1]) mod 256]
    x3 = x3 ^ S[(x2 + subkeys[4r + 2]) mod 256]
    x0 = x0 ^ S[(x3 + subkeys[4r + 3]) mod 256]
    (x0, x1, x2, x3) = (x1, x2, x3, x0)  # branch rotation

Inter-block Chaining:
  Forward pass (i = 0..m-1):
    U_i = FeistelRound(P_i ^ U_{i-1}, subkeys_fwd[i], R)
  Backward pass (i = m-1..0):
    C_i = FeistelRound(U_i ^ C_{i+1}, subkeys_bwd[i], R)

Decryption / Inversion:
  Backward inverse (all i):
    U_i = FeistelInverse(C_i, subkeys_bwd[i], R) ^ C_{i+1}
  Forward inverse (all i):
    P_i = FeistelInverse(U_i, subkeys_fwd[i], R) ^ U_{i-1}
"""


def feistel_block_encrypt(block: list, subkeys: list, S: list, rounds: int) -> list:
    x0, x1, x2, x3 = block
    for r in range(rounds):
        idx = r * 4
        x1 = x1 ^ S[(x0 + subkeys[idx + 0]) & 0xFF]
        x2 = x2 ^ S[(x1 + subkeys[idx + 1]) & 0xFF]
        x3 = x3 ^ S[(x2 + subkeys[idx + 2]) & 0xFF]
        x0 = x0 ^ S[(x3 + subkeys[idx + 3]) & 0xFF]
        x0, x1, x2, x3 = x1, x2, x3, x0
    return [x0, x1, x2, x3]


def feistel_block_decrypt(block: list, subkeys: list, S: list, rounds: int) -> list:
    x0, x1, x2, x3 = block
    for r in range(rounds - 1, -1, -1):
        idx = r * 4
        # Inverse of branch rotation (x1, x2, x3, x0) -> (x0, x1, x2, x3)
        x1, x2, x3, x0 = x0, x1, x2, x3
        x0 = x0 ^ S[(x3 + subkeys[idx + 3]) & 0xFF]
        x3 = x3 ^ S[(x2 + subkeys[idx + 2]) & 0xFF]
        x2 = x2 ^ S[(x1 + subkeys[idx + 1]) & 0xFF]
        x1 = x1 ^ S[(x0 + subkeys[idx + 0]) & 0xFF]
    return [x0, x1, x2, x3]


def encrypt(q: bytes, a: bytes, b: bytes, S: list, iv_f4: list, iv_b4: list, rounds: int = 4) -> bytes:
    n = len(q)
    # Pad to multiple of 4 if necessary
    pad_len = (4 - (n % 4)) % 4
    if pad_len > 0:
        data = bytearray(q) + bytearray(pad_len)
    else:
        data = bytearray(q)

    m = len(data) // 4
    subkeys_needed_per_block = rounds * 4

    # Derive subkeys from a and b streams by cyclical expansion
    def get_subkeys(stream_bytes, block_idx):
        offset = (block_idx * subkeys_needed_per_block) % len(stream_bytes)
        keys = []
        for j in range(subkeys_needed_per_block):
            keys.append(stream_bytes[(offset + j) % len(stream_bytes)])
        return keys

    # Forward pass
    u = bytearray(len(data))
    prev = list(iv_f4)
    for i in range(m):
        idx = i * 4
        in_block = [data[idx + j] ^ prev[j] for j in range(4)]
        subk = get_subkeys(a, i)
        out_block = feistel_block_encrypt(in_block, subk, S, rounds)
        u[idx : idx + 4] = out_block
        prev = out_block

    # Backward pass
    c = bytearray(len(data))
    nxt = list(iv_b4)
    for i in range(m - 1, -1, -1):
        idx = i * 4
        in_block = [u[idx + j] ^ nxt[j] for j in range(4)]
        subk = get_subkeys(b, i)
        out_block = feistel_block_encrypt(in_block, subk, S, rounds)
        c[idx : idx + 4] = out_block
        nxt = out_block

    return bytes(c[:n])


def decrypt(c_bytes: bytes, a: bytes, b: bytes, S: list, iv_f4: list, iv_b4: list, rounds: int = 4) -> bytes:
    n = len(c_bytes)
    pad_len = (4 - (n % 4)) % 4
    if pad_len > 0:
        data = bytearray(c_bytes) + bytearray(pad_len)
    else:
        data = bytearray(c_bytes)

    m = len(data) // 4
    subkeys_needed_per_block = rounds * 4

    def get_subkeys(stream_bytes, block_idx):
        offset = (block_idx * subkeys_needed_per_block) % len(stream_bytes)
        keys = []
        for j in range(subkeys_needed_per_block):
            keys.append(stream_bytes[(offset + j) % len(stream_bytes)])
        return keys

    # Backward pass inverse (all i)
    u = bytearray(len(data))
    for i in range(m):
        idx = i * 4
        nxt = data[idx + 4 : idx + 8] if i + 1 < m else iv_b4
        curr = list(data[idx : idx + 4])
        subk = get_subkeys(b, i)
        dec_block = feistel_block_decrypt(curr, subk, S, rounds)
        u[idx : idx + 4] = [dec_block[j] ^ nxt[j] for j in range(4)]

    # Forward pass inverse (all i)
    q = bytearray(len(data))
    for i in range(m):
        idx = i * 4
        prev = u[idx - 4 : idx] if i > 0 else iv_f4
        curr_u = list(u[idx : idx + 4])
        subk = get_subkeys(a, i)
        dec_block = feistel_block_decrypt(curr_u, subk, S, rounds)
        q[idx : idx + 4] = [dec_block[j] ^ prev[j] for j in range(4)]

    return bytes(q[:n])

