#!/bin/bash
# Pre-build script for RISC-V cross-compilation
# This script runs inside the cross container before building

set -euo pipefail

echo "=== Setting up RISC-V cross-compilation environment ==="

# Update package lists
apt-get update || true

# Install RISC-V toolchain and dependencies
apt-get install -y \
    gcc-riscv64-linux-gnu \
    g++-riscv64-linux-gnu \
    libc6-dev-riscv64-cross \
    pkg-config \
    libssl-dev \
    openssl \
    qemu-user-static || {
    echo "Warning: Some packages may not be available, continuing..."
}

# Set environment variables for OpenSSL
export OPENSSL_INCLUDE_DIR=/usr/include
export OPENSSL_LIB_DIR=/usr/lib/riscv64-linux-gnu
export PKG_CONFIG_ALLOW_CROSS=1

echo "=== RISC-V environment setup complete ==="
echo "OPENSSL_INCLUDE_DIR=$OPENSSL_INCLUDE_DIR"
echo "OPENSSL_LIB_DIR=$OPENSSL_LIB_DIR"
