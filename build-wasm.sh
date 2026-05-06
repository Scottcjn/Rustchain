#!/bin/bash
set -e
echo "🔧 Installing wasm-pack..."
cargo install wasm-pack 2>/dev/null || true

echo "📦 Building WASM miner (release mode)..."
cd wasm-miner
wasm-pack build --target web --release
cd ..

echo "✅ WASM artifacts generated in wasm-miner/pkg/"
ls -lh wasm-miner/pkg/
