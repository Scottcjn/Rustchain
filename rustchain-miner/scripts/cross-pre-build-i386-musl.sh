#!/bin/bash
# Pre-build script for i386-musl cross-compilation
# Bounty #435: Port RustChain Miner to Intel 386
#
# This script sets up the environment for cross-compiling
# the RustChain miner for Intel 386 (i686) with musl libc.
# Static linking is recommended for vintage systems.

set -e

echo "Setting up i386-musl cross-compilation environment..."

# Install i386-musl toolchain on Ubuntu/Debian
if command -v apt-get &> /dev/null; then
    echo "Installing i386-musl cross-toolchain..."
    sudo apt-get update
    sudo apt-get install -y \
        gcc-i686-linux-musl \
        musl-tools \
        musl-dev \
        pkg-config \
        libssl-dev
fi

# Install i386-musl toolchain on Fedora/RHEL
if command -v dnf &> /dev/null; then
    echo "Installing i386-musl cross-toolchain..."
    sudo dnf install -y \
        gcc-i686-linux-musl \
        musl-devel \
        openssl-devel
fi

echo "i386-musl cross-compilation environment ready!"
echo "Building with musl provides static binaries - ideal for vintage systems."
