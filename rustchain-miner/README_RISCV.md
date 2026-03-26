# RustChain Miner — RISC-V Port

> **RISC-V is an open ISA classified as EXOTIC vintage hardware with a 1.4x antiquity multiplier.**

## What is RISC-V?

[RISC-V](https://riscv.org/) is a free and open ISA (Instruction Set Architecture) developed at UC Berkeley. Unlike x86 and ARM, RISC-V is not controlled by any single company, making it the world's most popular open-source processor architecture. RISC-V hardware has emerged as a vintage computing platform starting approximately in 2010.

## Supported RISC-V Platforms

| Platform | SoC | CPU | Cores | Memory | Form Factor |
|---|---|---|---|---|---|
| HiFive Unmatched | SiFive Freedom U740 | SiFive U74-MC | 4+1 | 16 GB | PCIe Desktop |
| VisionFive 2 | StarFive JH7110 | SiFive P550-compat | 4 | 2–8 GB | SBC |
| VisionFive v1 | StarFive JH7100 | StarFive custom | 2 | 2–4 GB | SBC |
| Allwinner D1 | Allwinner D1 | T-Head C906 | 1 | 1 GB | SBC |
| Lichee RV | T-Head C906 | T-Head C906 | 1 | 256 MB | Module |

## Quick Start

### Cross-compile from x86_64

```bash
# Install cross
cargo install cross

# Build for RISC-V glibc
cross build --release --target riscv64gc-unknown-linux-gnu

# Or use the script
./scripts/cross-pre-build-riscv.sh
```

### Native build (on RISC-V hardware)

```bash
# Add RISC-V target
rustup target add riscv64gc-unknown-linux-gnu

# Build
cargo build --release

# Run
./target/release/rustchain-miner --version
```

### Build all targets (including RISC-V)

```bash
./build-all-targets.sh
```

## Architecture Detection

The miner automatically detects the following RISC-V implementations:

- **SiFive** — U74, U54, E51 cores (HiFive Unmatched, Freedom U740)
- **StarFive** — JH7110 (VisionFive 2), JH7100 (VisionFive v1)
- **Allwinner** — D1 (Nezha SBC)
- **T-Head (Alibaba)** — C910 (high-performance), C906 (embedded)
- **Generic RISC-V** — Fallback for unknown implementations

## Antiquity Multiplier

RISC-V hardware receives a **1.4x EXOTIC** antiquity multiplier, reflecting:

1. **Open ISA** — No proprietary licensing restrictions
2. **Emerging vintage** — RISC-V hardware from ~2010+ qualifies as vintage
3. **Heterogeneous ecosystem** — Diverse implementations from multiple vendors
4. **Community value** — Open-source hardware attestation

See `docs/RISCV.md` for detailed hardware specifications and build instructions.

## Files

```
rustchain-miner/
├── README_RISCV.md                          # This file
├── docs/RISCV.md                            # Detailed RISC-V documentation
├── cross.toml                               # Cross-compilation configuration
├── scripts/
│   ├── build_riscv.sh                       # RISC-V build script
│   └── cross-pre-build-riscv.sh             # Cross-compile pre-build checks
└── src/
    ├── hardware.rs                          # RISC-V detection + 1.4x multiplier
    ├── arch_tests.rs                        # Architecture detection tests
    └── ...
```

## Hardware Detection Example

```
$ RUST_LOG=debug ./rustchain-miner

[INFO] rustchain-miner v0.1.0
[INFO] Detected platform: Linux (riscv64)
[INFO] CPU: SiFive U74-MC Processor
[INFO] Family: RISC-V, Architecture: SiFive U74
[INFO] Cores: 5 (4x U74 + 1x E51)
[INFO] Memory: 16 GB
[INFO] Antiquity multiplier: 1.4x (EXOTIC)
```

## Verification

Run the architecture tests:

```bash
cargo test --lib rustchain_miner::arch_tests -- --nocapture
```

Expected output includes tests for all supported RISC-V platforms.
