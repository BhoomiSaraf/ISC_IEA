#!/bin/sh
# Build the fdlibm C oracle from the unmodified netlib sources (run inside WSL Ubuntu, or any Linux x86_64).
#   -O0 -ffp-contract=off : one IEEE binary64 operation per C operation, no FMA contraction
#   -fno-builtin          : do not let the compiler substitute its own sin/cos
#   -D__LITTLE_ENDIAN     : x86_64 is little endian; fdlibm.h does not detect it automatically
#   x86_64 gcc uses SSE2 for double arithmetic (no x87 excess precision)
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/../../third_party/fdlibm/netlib_5.3"
OUT="$HERE/build"
mkdir -p "$OUT"
( cd "$SRC" && sha256sum -c SHA256SUMS.txt )
FLAGS="-O0 -ffp-contract=off -fno-builtin -D__LITTLE_ENDIAN -w"
for f in s_sin s_cos k_sin k_cos e_rem_pio2 k_rem_pio2 s_fabs s_floor s_scalbn s_copysign; do
  gcc $FLAGS -I"$SRC" -c "$SRC/$f.c" -o "$OUT/$f.o"
done
gcc -O0 -ffp-contract=off -fno-builtin -o "$OUT/oracle" "$HERE/oracle.c" "$OUT"/*.o
gcc --version | head -1 > "$OUT/BUILD_INFO.txt"
uname -srm >> "$OUT/BUILD_INFO.txt"
echo "flags: $FLAGS" >> "$OUT/BUILD_INFO.txt"
sha256sum "$OUT/oracle" >> "$OUT/BUILD_INFO.txt"
cat "$OUT/BUILD_INFO.txt"
