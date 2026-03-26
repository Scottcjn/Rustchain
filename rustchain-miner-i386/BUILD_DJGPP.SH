#!/bin/bash
set -e

DJGPP_ROOT="${DJGPP_ROOT:-/opt/djgpp}"
TARGET_TRIPLE="i586-pc-msdosdjgpp"
CC="${TARGET_TRIPLE}-gcc"
CFLAGS="-march=i386 -mno-80387 -msoft-float -Os -Wall -DDJGPP -fno-builtin -fno-stack-protector"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SRC_DIR}/build-djgpp"
TARGET="${BUILD_DIR}/MINER386.EXE"

echo "========================================"
echo "  RustChain Intel 386 Miner Build"
echo "========================================"
echo ""

check_djgpp() {
    if ! command -v "$CC" &> /dev/null; then
        echo "Error: DJGPP cross-compiler not found"
        echo "Install: pacman -S djgpp (Arch) or apt install djgpp (Debian)"
        exit 1
    fi
    echo "✓ DJGPP found: $CC"
}

clean() {
    echo "Cleaning..."
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
}

build() {
    echo ""
    echo "Building..."
    mkdir -p "$BUILD_DIR"
    $CC $CFLAGS -c -o "$BUILD_DIR/SHA256.o" "${SRC_DIR}/SHA256.C"
    echo "  Compiled SHA256.C"
    $CC $CFLAGS -c -o "$BUILD_DIR/FINGERPRINT.o" "${SRC_DIR}/FINGERPRINT.C"
    echo "  Compiled FINGERPRINT.C"
    $CC $CFLAGS -c -o "$BUILD_DIR/MINER.o" "${SRC_DIR}/MINER.C"
    echo "  Compiled MINER.C"
    $CC $CFLAGS -o "$TARGET" "$BUILD_DIR/SHA256.o" "$BUILD_DIR/FINGERPRINT.o" "$BUILD_DIR/MINER.o" -lm
    "${TARGET_TRIPLE}-strip" "$TARGET"
    echo ""
    echo "✓ Build complete: $TARGET"
    ls -lh "$TARGET" 2>/dev/null || dir "$TARGET" 2>/dev/null || echo "  (size unavailable)"
}

case "${1:-}" in
    --clean) check_djgpp && clean && build ;;
    *) check_djgpp && [ -d "$BUILD_DIR" ] || build ;;
esac
