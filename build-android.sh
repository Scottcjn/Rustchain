#!/bin/bash
set -e
echo "📱 Installing cargo-ndk..."
cargo install cargo-ndk 2>/dev/null || true

echo "🛠️ Adding Android targets..."
rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android

echo "📦 Building Android native libraries..."
cd rustchain-miner/core
cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 -o ../android-libs build --release
cd ../..

echo "✅ Android .so files generated in rustchain-miner/android-libs/"
ls -lhR rustchain-miner/android-libs/
