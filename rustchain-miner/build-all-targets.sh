#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# build-all-targets.sh — Cross-compile rustchain-miner for all supported targets
#
# Prerequisites:
#   1. Install cross: cargo install cross --locked
#   2. Docker must be running (cross uses Docker containers for cross-compilation)
#
# Usage:
#   chmod +x build-all-targets.sh
#   ./build-all-targets.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

TARGETS=(
    "x86_64-unknown-linux-musl"        # x86_64 Linux (static)
    "aarch64-unknown-linux-musl"       # ARM64 Linux (static)
    "powerpc64-unknown-linux-gnu"      # PowerPC 64-bit Linux (big-endian)
    "riscv64gc-unknown-linux-gnu"      # RISC-V 64-bit Linux (StarFive, SiFive, Milk-V)
)

BINARY="rustchain-miner"
OUTPUT_DIR="dist"

echo "╔══════════════════════════════════════════════════╗"
echo "║    RustChain Miner — Cross-Compilation Build     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

mkdir -p "$OUTPUT_DIR"

for target in "${TARGETS[@]}"; do
    echo "━━━ Building for ${target} ━━━"
    cross build --release --target "${target}"

    # Copy binary to dist/
    src="target/${target}/release/${BINARY}"
    dst="${OUTPUT_DIR}/${BINARY}-${target}"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        chmod +x "$dst"
        echo "  ✓ ${dst} ($(du -h "$dst" | cut -f1))"
    else
        echo "  ✗ Binary not found at ${src}"
    fi
    echo ""
done

echo "━━━ Cross-compilation complete ━━━"
echo ""
echo "Built binaries:"
ls -lh "${OUTPUT_DIR}/"
echo ""
echo "To run on the target machine:"
echo "  scp dist/rustchain-miner-<target> user@host:~/rustchain-miner"
echo "  ssh user@host './rustchain-miner --wallet your-wallet'"
