#!/usr/bin/env bash
# Quick install script for RustChain Miner (clawrtc)
# Usage: curl -fsSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/Formula/install.sh | bash

set -euo pipefail

echo "==> Installing RustChain Miner (clawrtc)..."

# Check for Homebrew
if ! command -v brew &>/dev/null; then
  echo "Homebrew not found. Installing Homebrew first..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Tap and install
brew tap Scottcjn/rustchain https://github.com/Scottcjn/Rustchain.git
brew install clawrtc

echo ""
echo "==> clawrtc installed successfully!"
echo "    Run 'clawrtc --help' to get started."
echo "    Start mining: clawrtc mine --wallet YOUR_WALLET_ADDRESS"
