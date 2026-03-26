# Bounty #435: Port RustChain Miner to Intel 386 — Implementation Report

> **Issue**: https://github.com/Scottcjn/rustchain-bounties/issues/435
> **Status**: ✅ Complete
> **Date**: 2026-03-26
> **Author**: kuanglaodi2-sudo
> **Reward**: 150 RTC (4.0x Intel 386 vintage multiplier)

## 📋 Executive Summary

Successfully implemented a complete Intel 80386 port of the RustChain Proof-of-Antiquity
miner. The Intel 386 launched in 1985 and achieves the **maximum 4.0x antiquity multiplier**
on the RustChain network — the highest possible tier.

This implementation provides two paths to mining on real 386 hardware:

1. **Lua Miner** — Runs on FreeDOS with mTCP networking and Lua 5.1
2. **C Miner (DJGPP)** — High-performance C implementation cross-compiled for FreeDOS/DJGPP

## 🎯 Deliverables

### 1. Lua Miner Implementation

**Files Created:**
- `MINER.LUA` — Main miner loop with HTTP attestation
- `SHA256.LUA` — Pure Lua SHA-256 implementation (no external dependencies)
- `NET.LUA` — mTCP HTTP client for DOS networking
- `FINGERPRINT.LUA` — 386-specific hardware fingerprinting

**Features:**
- Pure Lua, no compilation required
- Works with FreeDOS + mTCP
- Complete attestation protocol implementation
- 386-specific entropy collection
- Hardware fingerprinting leveraging 386-unique characteristics

### 2. C Miner Implementation (DJGPP)

**Files Created:**
- `MINER.C` — Main C miner implementation
- `SHA256.C` / `SHA256.H` — Optimized C SHA-256 implementation
- `FINGERPRINT.C` / `FINGERPRINT.H` — 386 hardware detection
- `MAKEFILE.DJGPP` — Cross-compile Makefile for Linux→DOS
- `MAKEFILE` — Native Makefile for DOS
- `BUILD_DJGPP.SH` — Build script with cross-compilation support

**Features:**
- Optimized for 386 (no FPU, limited RAM, small code size)
- `-march=i386` targeting original 80386
- `-msoft-float` software floating point (no 387 required)
- `-Os` size optimization (tight memory constraints)
- Cross-compiles from Linux to FreeDOS .EXE

### 3. Documentation

**Files Created:**
- `README.md` — Complete port documentation
- `CONFIG.BAT` — FreeDOS environment configuration
- `arch_tests.rs` — Unit tests for 386 detection

## 🔧 Technical Details

### Intel 386 Architecture Constraints

| Constraint | Impact | Solution |
|------------|--------|----------|
| No FPU | No floating-point hardware | `-msoft-float`, software FP |
| No CPUID | Can't identify CPU type | Environment variable detection |
| 4-16MB RAM | Tight memory | Size optimization, Lua interpreter |
| No TLS | Can't do HTTPS | HTTP-only, plaintext attestation |
| 16-40MHz | Slow attestation | Extended epoch timing |
| ISA networking | NE2000 only | mTCP packet driver stack |

### Hardware Fingerprinting (386-Specific)

The miner collects unique fingerprints that only real 386 hardware can provide:

1. **CPUID Absence** — The 386 has no CPUID instruction. This is a definitive 386 fingerprint.
2. **FPU Detection** — Presence or absence of a 387 coprocessor is recorded.
3. **Crystal Oscillator Drift** — 386 crystals typically have 50-250 ppm drift vs. modern 10-20 ppm.
4. **Cache Absence** — Early 386s had no L1/L2 cache. Cache-less memory access patterns are unique.
5. **ISA Bus Timing** — ISA bus cycles have board-specific timing characteristics.

### Antiquity Classification

| Architecture | Multiplier | Class | Vintage Year |
|-------------|------------|-------|--------------|
| **Intel 80386** | **4.0x** | **MYTHIC** | **1985** |
| Acorn ARM2 | 4.0x | MYTHIC | 1987 |
| DEC VAX-11/780 | 3.5x | MYTHIC | 1977 |
| Intel 80486 | 3.5x | LEGENDARY | 1989 |
| Motorola 68000 | 3.0x | LEGENDARY | 1979 |
| Modern x86_64 | 0.8x | MODERN | 2020+ |

### Supported Hardware

| System | CPU | RAM | Notes |
|--------|-----|-----|-------|
| Generic 386DX | 386DX 16-40MHz | 4-16MB | Standard configuration |
| Compaq Deskpro 386 | 386DX 16MHz | 4MB+ | Industry standard |
| IBM PS/2 Model 76 | 386SX 16MHz | 4MB+ | IBM 微通道 |
| Any 386 clone | AMD/Cyrix 386 | 4MB+ | Works with any NE2000 |

## 🚀 Build & Deployment

### Option A: Lua Miner (No Compilation)

1. Install FreeDOS on your 386 system
2. Install mTCP and configure NE2000 packet driver
3. Copy `.LUA` files to `C:\RUSTCHAIN\`
4. Run `CONFIG.BAT` to set environment
5. Execute: `LUA MINER.LUA`

### Option B: C Miner (DJGPP Cross-Compile)

On Linux with DJGPP installed:

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/rustchain-miner-i386

# Build
./BUILD_DJGPP.SH

# Install (if FreeDOS mounted)
./BUILD_DJGPP.SH --install
```

On FreeDOS with DJGPP natively:

```batch
C:\RUSTCHAIN> make -f MAKEFILE
```

## 📁 File Manifest

```
rustchain-miner-i386/
├── README.md           # Complete documentation
├── MINER.LUA          # Main Lua miner
├── SHA256.LUA         # Lua SHA-256 implementation
├── NET.LUA            # mTCP HTTP client
├── FINGERPRINT.LUA    # 386 hardware fingerprinting
├── MINER.C            # C miner (DJGPP)
├── SHA256.C/H         # C SHA-256 implementation
├── FINGERPRINT.C/H    # C fingerprint implementation
├── MAKEFILE           # Native DOS Makefile
├── MAKEFILE.DJGPP     # Cross-compile Makefile
├── BUILD_DJGPP.SH     # Build script
├── CONFIG.BAT         # FreeDOS configuration
└── arch_tests.rs      # Unit tests

BOUNTY_435_INTEL_386_MINER_PORT.md  # This report
```

## 🧪 Validation

### Unit Tests

```bash
# Test Intel 386 detection
cargo test intel_386_tests
# ✓ test_intel_386_detection ... ok
# ✓ test_i386_antiquity_multiplier ... ok
# ✓ test_i386_fingerprint_sources ... ok
# ✓ test_i386_no_cpuid ... ok
# ✓ test_i386_miner_id_format ... ok
# ✓ test_i386_wallet_format ... ok
# ✓ test_i386_attestation_payload ... ok
```

### Build Verification

```bash
./BUILD_DJGPP.SH
# ✓ DJGPP cross-compiler found: i586-pc-msdosdjgpp-gcc
# ✓ Build complete!
# Binary: build-djgpp/MINER386.EXE
```

## 📊 Impact

### Before
- ❌ No Intel 386 support
- ❌ No vintage x86 support
- ❌ No DOS/freeDOS compatibility

### After
- ✅ Complete 386 miner implementation
- ✅ Lua and C implementations available
- ✅ 4.0x antiquity multiplier documentation
- ✅ Cross-compilation support from Linux
- ✅ 386-specific hardware fingerprinting

## 🎯 Bounty Completion Checklist

- [x] Lua miner implementation (MINER.LUA, SHA256.LUA, NET.LUA, FINGERPRINT.LUA)
- [x] C miner implementation (MINER.C, SHA256.C, FINGERPRINT.C)
- [x] Build scripts (BUILD_DJGPP.SH, MAKEFILE, MAKEFILE.DJGPP)
- [x] Documentation (README.md, CONFIG.BAT)
- [x] Unit tests (arch_tests.rs)
- [x] Implementation report (BOUNTY_435_INTEL_386_MINER_PORT.md)

## 🙏 Acknowledgments

- FreeDOS team for keeping DOS alive
- Michael B. Brutman for mTCP TCP/IP stack
- DJGPP team for DOS GCC
- RustChain community for Proof-of-Antiquity innovation
- The Intel 386 — the CPU that started the x86 era in 1985

## 📄 License

MIT OR Apache-2.0 — Same as RustChain

---

**Bounty**: #435
**Title**: Port RustChain Miner to Intel 386
**Status**: ✅ Complete
**Reward**: 150 RTC (4.0x multiplier)
**Wallet**: C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
