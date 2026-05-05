# RISC-V Architecture Support

This document describes RISC-V support in the RustChain miner (`rustchain-miner`).

## Supported Hardware

| Board | SoC | Architecture | Multiplier | Status |
|-------|-----|-------------|------------|--------|
| StarFive VisionFive 2 | JH7110 (SiFour RISC-V) | `riscv64gc` | 1.1x | Tested |
| SiFive Unmatched | FU740 (U74 core) | `riscv64gc` | 1.0x | Tested |
| Milk-V Pioneer | SG2380 (ESWIN) | `riscv64gc` | 0.9x | Tested |
| Generic RISC-V 64-bit | Any RV64GC | `riscv64gc` | 0.95x | Fallback |

## Building for RISC-V

### Native Build (on RISC-V Linux)

```bash
cargo build --release --target riscv64gc-unknown-linux-gnu
./target/riscv64gc-unknown-linux-gnu/release/rustchain-miner --wallet YOUR_WALLET
```

### Cross-Compile (from x86_64 Linux)

```bash
# Install cross tool
cargo install cross --locked

# Cross-compile for RISC-V
cross build --release --target riscv64gc-unknown-linux-gnu
```

### GitHub Actions CI

RISC-V `riscv64gc-unknown-linux-gnu` is included in the CI matrix in `.github/workflows/cross-compile.yml`.

## Architecture Detection

The miner detects RISC-V boards by matching the CPU brand string in `/proc/cpuinfo`:

- `starfive`, `jh7110`, `visionfive` → `RISC-V / starfive_jh7110`
- `sifive`, `fu740`, `hifive` → `RISC-V / sifive_unmatched`
- `milk-v`, `sg2380`, `pioneer` → `RISC-V / milkv_pioneer`
- Generic `riscv`, `rv64` → `RISC-V / riscv_modern`

## SIMD / Vector Extension

RISC-V does not yet have a stable, widely-adopted SIMD standard. The RISC-V
Vector Extension (RVV) is still evolving (versions 0.7, 0.8, 1.0 coexist).

The miner detects vector unit availability via `/proc/cpuinfo`:

- `RVV-1.0` — stable RVV 1.0 (VisionFive 2 starfive-sdk firmware)
- `RVV-0.7` — draft RVV 0.7 (older toolchains)
- `RVV` — vector extension detected, version undetermined

The miner uses a **scalar fallback** for all RISC-V targets to ensure
correctness across toolchain versions.

## Anti-Emulation / QEMU Detection

RISC-V systems are frequently emulated with QEMU (especially for development).
The miner checks for QEMU indicators on RISC-V Linux:

1. `/proc/cpuinfo` model name matching: `qemu-riscv`, `riscv,qemu`, `virt, qemu`
2. `/proc/device-tree/compatible` for `qemu` string
3. Standard MAC OUI checks for virtual NICs (QEMU uses `52:54:00` OUI)
4. Hypervisor flag in `/proc/cpuinfo` (if running under KVM)

## Cache Hierarchy Notes

The JH7110 (VisionFive 2) cache hierarchy:

- L1 I/D cache: 32 KiB per core
- L2 cache: 512 KiB (shared, off-cluster)
- L3 cache: none on VisionFive 2

The cache-timing fingerprint (`cache_timing.rs`) uses the same buffer-size
sweeping approach but is parameterized for RISC-V cache geometry. The
coefficient-of-variation (CV) threshold of 0.02 (2%) is preserved from x86_64.

## Year Estimation

RISC-V is a young architecture. Year estimates for RISC-V hardware:

| Arch Tier | Estimated Vintage Year |
|-----------|----------------------|
| `starfive_jh7110` | 2023 |
| `sifive_unmatched` | 2021 |
| `milkv_pioneer` | 2023 |
| `riscv_modern` | 2022+ |

## Troubleshooting

### QEMU-emulated RISC-V warning

If you see `riscv_vm:qemu-riscv` in the anti-emulation check output, the
miner detected it is running under QEMU. Real hardware attestation requires
physical RISC-V silicon.

**Fix:** Run on real hardware (VisionFive 2, SiFive Unmatched, Milk-V Pioneer).

### Vector extension not detected

Ensure your Linux kernel is compiled with RISC-V vector support and that
`/proc/cpuinfo` contains `v` in the ISA string:

```
isa       : rv64imafdc_zicsr_zifencei_zba_zbb_v
```

If missing, your kernel does not expose the vector unit.

### JH7110 performance

The StarFive JH7110 is a 1.5 GHz quad-core RISC-V processor. Hash rates are
significantly lower than x86_64/ARM due to lack of hardware acceleration.
The 1.1x multiplier compensates partially.
