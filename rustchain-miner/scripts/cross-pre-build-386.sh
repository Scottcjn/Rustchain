#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════════════════
# cross-pre-build-386.sh — Pre-build script for Intel 386 cross-compilation
#
# This script runs inside the Docker container before the Rust build.
# It sets up the i386/i686 cross-compilation environment.
# ══════════════════════════════════════════════════════════════════════════════════════════
set -e

echo "[pre-build-386] Setting up Intel 386/486/Pentium cross-compilation environment..."

# Update package lists
echo "[pre-build-386] Updating package lists..."
apt-get update -qq

# Install 32-bit development tools and libraries
echo "[pre-build-386] Installing i386 cross-compilation toolchain..."
apt-get install -y --no-install-recommends \
    gcc-i686-linux-gnu \
    g++-i686-linux-gnu \
    libc6-dev-i386-cross \
    linux-libc-dev-i386-cross \
    libssl-dev:i386 \
    pkg-config:i386 \
    libc6-dev:i386 \
    gcc-multilib \
    || {
        echo "[pre-build-386] i386 cross-compile packages not available, continuing..."
        echo "[pre-build-386] (This may be OK if using Docker image with pre-installed toolchain)"
    }

# Install QEMU for i386 (for testing)
echo "[pre-build-386] Installing QEMU for i386 testing..."
apt-get install -y --no-install-recommends \
    qemu-system-x86 \
    qemu-user \
    || echo "[pre-build-386] QEMU installation skipped"

# Create symbolic links for 32-bit libraries
echo "[pre-build-386] Setting up library paths..."
mkdir -p /tmp/i386-libs

# Verify cross-compiler is available
if command -v i686-linux-gnu-gcc &> /dev/null; then
    echo "[pre-build-386] ✅ i686-linux-gnu-gcc found: $(i686-linux-gnu-gcc --version | head -1)"
else
    echo "[pre-build-386] ⚠️  i686-linux-gnu-gcc not found in PATH"
    echo "[pre-build-386] Cross-compilation may still work via Docker image defaults"
fi

# List installed packages for debugging
echo "[pre-build-386] Installed cross-compilation packages:"
dpkg -l 2>/dev/null | grep -E "i386|i686|cross" | head -20 || echo "  (none found)"

echo "[pre-build-386] Pre-build setup complete!"
