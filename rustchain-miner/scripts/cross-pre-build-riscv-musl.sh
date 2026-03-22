#!/bin/bash
# Pre-build script for RISC-V musl cross-compilation
# This script runs inside the cross container before building

set -euo pipefail

echo "=== Setting up RISC-V musl cross-compilation environment ==="

# Update package lists
apt-get update || true

# Install RISC-V musl toolchain and dependencies
apt-get install -y \
    musl-tools \
    musl-dev \
    pkg-config \
    libssl-dev \
    openssl || {
    echo "Warning: Some packages may not be available, continuing..."
}

# Set environment variables for musl and OpenSSL
export PKG_CONFIG_ALLOW_CROSS=1
export OPENSSL_INCLUDE_DIR=/usr/include
export OPENSSL_LIB_DIR=/usr/lib

echo "=== RISC-V musl environment setup complete ==="
