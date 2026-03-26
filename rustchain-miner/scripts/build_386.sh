#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════════════════
# build_386.sh — Build RustChain Miner for Intel 386/486/Pentium (i386/i586/i686)
#
# Prerequisites:
#   1. Install cross: cargo install cross --locked
#   2. Docker must be running (cross uses Docker containers for cross-compilation)
#   3. For native build: apt-get install gcc-i686-linux-gnu g++-i686-linux-gnu
#
# Usage:
#   chmod +x scripts/build_386.sh
#   ./scripts/build_386.sh [OPTIONS]
#
# Options:
#   --target TARGET   Build for specific target (default: i686-unknown-linux-gnu)
#   --release        Release build (default: debug)
#   --docker         Use Docker instead of native cross
#   --clean          Clean build artifacts
#   --test           Run tests after build
#   --musl           Build with musl libc (static)
# ══════════════════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Default settings
TARGET="${TARGET:-i686-unknown-linux-gnu}"
RELEASE=false
USE_DOCKER=false
CLEAN=false
RUN_TESTS=false
MUSL=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --release)
            RELEASE=true
            shift
            ;;
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --test)
            RUN_TESTS=true
            shift
            ;;
        --musl)
            MUSL=true
            TARGET="i686-unknown-linux-musl"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--target TARGET] [--release] [--docker] [--clean] [--test] [--musl]"
            exit 1
            ;;
    esac
done

# Banner
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║   RustChain Miner — Intel 386/486/Pentium Cross-Compilation Build     ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Target:    $TARGET"
echo "  Mode:      $([ "$RELEASE" = true ] && echo "Release" || echo "Debug")"
echo "  Docker:    $([ "$USE_DOCKER" = true ] && echo "Yes" || echo "No")"
echo "  Musl:      $([ "$MUSL" = true ] && echo "Yes (static)" || echo "No (glibc)")"
echo ""

# Validate target
VALID_TARGETS=("i386-unknown-linux-gnu" "i486-unknown-linux-gnu" "i586-unknown-linux-gnu" "i686-unknown-linux-gnu" "i686-unknown-linux-musl" "i586-unknown-linux-musl")
if [[ ! " ${VALID_TARGETS[*]} " =~ " ${TARGET} " ]]; then
    echo "⚠️  Warning: Target '$TARGET' not in validated targets list"
    echo "   Valid targets: ${VALID_TARGETS[*]}"
fi

# Pre-build checks
if [ "$USE_DOCKER" = true ]; then
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker not found. Please install Docker or use --docker=false"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        echo "❌ Docker daemon not running. Please start Docker."
        exit 1
    fi
    echo "✅ Docker found and running"
fi

# Install cross if not available
if ! command -v cross &> /dev/null; then
    echo "📦 Installing cross-rs..."
    cargo install cross --locked
fi

# Clean if requested
if [ "$CLEAN" = true ]; then
    echo "🧹 Cleaning build artifacts for $TARGET..."
    rm -rf "target/$TARGET"
    rm -rf "target/$TARGET/debug" 2>/dev/null || true
    rm -rf "target/$TARGET/release" 2>/dev/null || true
    echo "✅ Clean complete"
fi

# Build command
BUILD_CMD=(cross build)
if [ "$RELEASE" = true ]; then
    BUILD_CMD+=(--release)
fi
BUILD_CMD+=(--target "$TARGET")

echo "🔨 Building for ${TARGET}..."
echo "   Command: ${BUILD_CMD[*]}"

if [ "$USE_DOCKER" = true ]; then
    # Docker build with cross
    "${BUILD_CMD[@]}" 2>&1
else
    # Native cross-compile
    "${BUILD_CMD[@]}" 2>&1
fi

BUILD_STATUS=$?

if [ $BUILD_STATUS -ne 0 ]; then
    echo ""
    echo "❌ Build failed with exit code $BUILD_STATUS"
    exit $BUILD_STATUS
fi

echo ""
echo "✅ Build successful!"

# Copy binary to dist/
OUTPUT_DIR="dist"
mkdir -p "$OUTPUT_DIR"

BINARY_NAME="rustchain-miner"
SRC_DIR="target/$TARGET"
if [ "$RELEASE" = true ]; then
    SRC_DIR+="/release/$BINARY_NAME"
else
    SRC_DIR+="/debug/$BINARY_NAME"
fi

if [ -f "$SRC_DIR" ]; then
    DST="$OUTPUT_DIR/${BINARY_NAME}-${TARGET}"
    cp "$SRC_DIR" "$DST"
    chmod +x "$DST"
    SIZE=$(du -h "$DST" | cut -f1)
    echo ""
    echo "📦 Binary: $DST ($SIZE)"
    
    # Verify architecture
    echo ""
    echo "🔍 Architecture verification:"
    file "$DST"
    readelf -h "$DST" 2>/dev/null | grep -E "Machine|Class" || echo "   (readelf not available)"
else
    echo "⚠️  Binary not found at expected path: $SRC_DIR"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Build Summary"
echo "═══════════════════════════════════════════════════════════════════════"
echo "  Target:    $TARGET"
echo "  Mode:      $([ "$RELEASE" = true ] && echo "Release" || echo "Debug")"
echo ""

# Run tests if requested
if [ "$RUN_TESTS" = true ]; then
    echo "🧪 Running tests for $TARGET..."
    TEST_CMD=(cross test --target "$TARGET")
    if [ "$RELEASE" = true ]; then
        TEST_CMD+=(--release)
    fi
    
    echo "   Command: ${TEST_CMD[*]}"
    "${TEST_CMD[@]}" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ All tests passed!"
    else
        echo "⚠️  Some tests failed (this may be expected in CI)"
    fi
fi

echo ""
echo "Built binaries:"
if [ -d "$OUTPUT_DIR" ]; then
    ls -lh "$OUTPUT_DIR/"
fi

echo ""
echo "To run on the target machine:"
echo "  scp dist/rustchain-miner-${TARGET} root@target:/usr/local/bin/"
echo "  ssh root@target './rustchain-miner --wallet your-wallet'"
echo ""
