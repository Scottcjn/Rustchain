#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

CC=${CC:-gcc}
ITERS=${ITERS:-2000000}
OUT_DIR=${OUT_DIR:-./results}
mkdir -p "$OUT_DIR"

CFLAGS_COMMON="-O3 -std=c11 -Wall"

$CC $CFLAGS_COMMON vecperm_bench.c -o vecperm_bench_scalar
./vecperm_bench_scalar "$ITERS" | tee "$OUT_DIR/scalar_or_host.json"

if $CC -dM -E - < /dev/null | grep -q '__powerpc64__'; then
  $CC $CFLAGS_COMMON -maltivec -mvsx vecperm_bench.c -o vecperm_bench_power8
  ./vecperm_bench_power8 "$ITERS" | tee "$OUT_DIR/power8_vecperm.json"
fi

echo "Wrote results to $OUT_DIR"
