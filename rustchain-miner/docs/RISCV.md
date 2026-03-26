# RustChain Miner — RISC-V Platform Guide

**RISC-V is classified as EXOTIC vintage hardware with a 1.4x antiquity multiplier.**

## Overview

RISC-V is an open Instruction Set Architecture (ISA) that has emerged as a viable vintage computing platform starting around 2010. Unlike x86 and ARM, RISC-V is royalty-free and openly documented, making it an attractive platform for heterogeneous computing and blockchain mining.

## Supported Hardware

### SiFive Freedom U740 (HiFive Unmatched)

- **Architecture:** RV64GC (RISC-V 64-bit, General + Compressed)
- **CPU:** SiFive U74-MC (4x U74 cores + 1x E51 management core)
- **Memory:** Up to 16 GB DDR4
- **Form Factor:** PCIe desktop board
- **Antiquity Multiplier:** 1.4x
- **ISA Extensions:** IMACFDu

### StarFive JH7110 (VisionFive 2)

- **Architecture:** RV64GC
- **CPU:** 4x SiFive P550-compatible cores
- **Memory:** 2–8 GB LPDDR4
- **Form Factor:** Single-board computer (SBC)
- **Antiquity Multiplier:** 1.4x
- **Notes:** First RISC-V SBC with significant community support

### StarFive JH7100 (VisionFive v1)

- **Architecture:** RV64GC
- **CPU:** 2x StarFive custom cores
- **Memory:** 2–4 GB
- **Form Factor:** SBC
- **Antiquity Multiplier:** 1.4x

### Allwinner D1 (Nezha / Lichee RV)

- **Architecture:** RV64GC
- **CPU:** T-Head C906 (single core)
- **Memory:** 1 GB DDR3
- **Form Factor:** SBC / Module
- **Antiquity Multiplier:** 1.4x

### T-Head C910

- **Architecture:** RV64GCV (with Vector extension)
- **CPU:** Multi-core high-performance RISC-V
- **Use Case:** AI accelerators, edge computing
- **Antiquity Multiplier:** 1.4x

## Building for RISC-V

### Prerequisites

```bash
# Install rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Add RISC-V target
rustup target add riscv64gc-unknown-linux-gnu

# Install cross (for cross-compilation)
cargo install cross
```

### Native Build (on RISC-V hardware)

```bash
cd rustchain-miner
cargo build --release --target riscv64gc-unknown-linux-gnu
sudo cp target/riscv64gc-unknown-linux-gnu/release/rustchain-miner /usr/local/bin/
rustchain-miner --version
```

### Cross-Compilation (from x86_64)

Using the provided `cross.toml`:

```bash
# Install cross
cargo install cross

# Build for RISC-V glibc target
cross build --release --target riscv64gc-unknown-linux-gnu

# Build for RISC-V musl target (static binary)
cross build --release --target riscv64gc-unknown-linux-musl
```

### Using the Build Scripts

```bash
# Build all targets (including RISC-V)
./build-all-targets.sh

# RISC-V specific build
./scripts/build_riscv.sh

# Cross-compile with musl libc
./scripts/cross-pre-build-riscv.sh
```

## Memory Alignment Notes

RISC-V uses the LP64 (Long Pointer 64) memory model:

| Type      | Size (64-bit) |
|-----------|--------------|
| char      | 1 byte       |
| short     | 2 bytes      |
| int       | 4 bytes      |
| long      | 8 bytes      |
| long long | 8 bytes      |
| pointer   | 8 bytes      |

Natural alignment is used: fields are aligned to their own size. This is consistent with x86_64 (LP64) but different from aarch64 (which also uses LP64).

## ISA Extensions for Mining

The following RISC-V ISA extensions are relevant for RustChain mining:

- **M** — Integer Multiply/Divide: Required for hash computation
- **A** — Atomic Operations: Required for concurrent mining threads
- **F/D** — Floating Point: Optional, for future SIMD optimizations
- **V** — Vector: Future use for parallel hash operations

## Verifying RISC-V Detection

Run the miner with debug logging to verify hardware detection:

```bash
RUST_LOG=debug ./rustchain-miner
```

Expected output for RISC-V hardware:

```
[INFO] Platform: Linux (riscv64)
[INFO] CPU: SiFive U74-MC (RISC-V, 5 cores)
[INFO] Family: RISC-V, Arch: SiFive U74
[INFO] Antiquity Multiplier: 1.4x (EXOTIC)
```

## Troubleshooting

### "error: cannot find target riscv64gc-unknown-linux-gnu"

```bash
rustup target add riscv64gc-unknown-linux-gnu
```

### "instruction fetch fault" or boot issues

Ensure your SBI (Supervisor Binary Interface) firmware is up to date. The HiFive Unmatched requires the latest OpenSBI.

### Cross-compilation fails with "could not find native static library"

Install RISC-V toolchain:

```bash
# Debian/Ubuntu
sudo apt install gcc-riscv64-linux-gnu

# macOS (via Homebrew)
brew install riscv-tools
```

## References

- [RISC-V International](https://riscv.org/)
- [SiFive Documentation](https://www.sifive.com/documentation/)
- [StarFive VisionFive 2](https://doc-en.rvboards.org/)
- [Allwinner D1 SDK](https://github.com/smaeul/sun20iw1p1)
