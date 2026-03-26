#!/bin/bash
# Pre-build script for i386-glibc cross-compilation
# Bounty #435: Port RustChain Miner to Intel 386
#
# This script sets up the environment for cross-compiling
# the RustChain miner for Intel 386 (i686) targets.

set -e

echo "Setting up i386-glibc cross-compilation environment..."

# Install i386 toolchain on Ubuntu/Debian
if command -v apt-get &> /dev/null; then
    echo "Installing i386-glibc cross-toolchain..."
    sudo apt-get update
    sudo apt-get install -y \
        gcc-i686-linux-gnu \
        g++-i686-linux-gnu \
        libc6-dev-i386-cross \
        pkg-config \
        libssl-dev
fi

# Install i386 toolchain on Fedora/RHEL
if command -v dnf &> /dev/null; then
    echo "Installing i386-glibc cross-toolchain..."
    sudo dnf install -y \
        gcc-i686-linux-gnu \
        glibc-devel.i686 \
        libstdc++-devel.i686 \
        openssl-devel
fi

echo "i386-glibc cross-compilation environment ready!"
