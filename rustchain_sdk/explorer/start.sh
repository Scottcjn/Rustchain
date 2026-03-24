#!/bin/bash
# RustChain Explorer - Quick Start Script
# Starts the explorer server on port 8080

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Install dependencies if needed
if [ -f "requirements.txt" ]; then
    echo "📦 Installing dependencies..."
    pip3 install -q -r requirements.txt
fi

# Configuration
export RUSTCHAIN_API_BASE="${RUSTCHAIN_API_BASE:-https://rustchain.org}"
export EXPLORER_PORT="${EXPLORER_PORT:-8080}"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           RustChain Explorer                             ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Starting server...                                      ║"
echo "║  URL: http://localhost:${EXPLORER_PORT}                        ║"
echo "║  API: ${RUSTCHAIN_API_BASE}"
echo "║                                                          ║"
echo "║  Press Ctrl+C to stop                                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Start server
python3 explorer_server.py
