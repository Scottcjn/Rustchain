# Pioneer Miner Ports: WASM & Android

## Overview
This PR adds support for compiling the RustChain miner to two new architectures/runtimes:
- **WebAssembly (wasm32-unknown-unknown)**: Enables in-browser mining via Web Workers.
- **Android ARM64 (aarch64-linux-android)**: Enables native mobile mining on Android devices.

## Architecture
The mining core (`rustchain-core`) has been extracted into a `no_std`/WASM-compatible library containing only the cryptographic hashing logic. This allows it to compile to any target supported by LLVM.

## Quick Start

### Build WASM Miner
```bash
./build-wasm.sh
```
Outputs to `wasm-miner/pkg/` (includes `.wasm`, `.js` glue, and TypeScript definitions).

### Build Android Miner
```bash
./build-android.sh
```
Outputs to `rustchain-miner/android-libs/` (contains `.so` for arm64-v8a, armeabi-v7a, x86_64).

## Integration
- **Web**: Import `wasm-miner/pkg/wasm_miner.js` and call `find_nonce(data, start, difficulty)`.
- **Android**: Load `librustchain_core.so` via JNI in your Kotlin/Java app.

## Verification
Run `cargo test -p rustchain-core` to verify hash determinism across all architectures.
