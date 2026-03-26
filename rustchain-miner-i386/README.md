# RustChain Miner for Intel 386 — 4.0x Antiquity Multiplier

> Port of the RustChain miner to Intel 80386 hardware (1985)
> Earns the **maximum 4.0x antiquity multiplier** on the RustChain network

## 🎯 Overview

This is a complete port of the RustChain Proof-of-Antiquity miner to the Intel 80386
architecture. The 386 launched in 1985 — over 40 years ago — and earns the highest
possible reward tier on the RustChain network.

### Why 386?

- **1985 architecture** — The CPU that started the x86 era
- **No FPU** (unless you have a 387) — Forces software floating point
- **16MHz-40MHz clock** — Every cycle counts
- **4.0x multiplier** — Maximum tier, 4x what a modern Ryzen earns
- **Real hardware only** — Absolutely nobody emulates a 386 to farm crypto

## 📋 Requirements

### Hardware

| Component | Notes |
|-----------|-------|
| 386 system | 386DX or 386SX, any speed |
| RAM | 4MB minimum (8MB+ recommended) |
| Network card | NE2000 compatible ISA |
| Boot media | Floppy, CF-to-IDE adapter, or HDD |
| Coprocessor | Optional 387 (detected as fingerprint) |

### Software

- **Option A**: FreeDOS + mTCP + Lua 5.1
- **Option B**: FreeDOS + DJGPP + custom C miner
- **Option C**: ELKS Linux + Lua interpreter

## 🔧 Installation

### Option A: Lua on FreeDOS (Recommended)

1. **Get FreeDOS**: Download from https://www.freedos.org/
2. **Install mTCP**: Copy `MTCP.EXE` and packet driver to your FreeDOS system
3. **Copy Lua**: Copy `LUA.COM` (DOS Lua 5.1 binary) to your system
4. **Copy miner**:
   ```
   COPY MINER.LUA C:\RUSTCHAIN\
   COPY SHA256.LUA C:\RUSTCHAIN\
   COPY NET.LUA C:\RUSTCHAIN\
   COPY FINGERPRINT.LUA C:\RUSTCHAIN\
   ```
5. **Configure**:
   ```batch
   SET RUSTCHAIN_WALLET=C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
   SET RUSTCHAIN_NODE=https://rustchain.org
   ```
6. **Run**:
   ```batch
   CD C:\RUSTCHAIN
   LUA MINER.LUA
   ```

### Option B: DJGPP C Miner

1. **Install DJGPP**: Download from http://www.delorie.com/djgpp/
2. **Build**:
   ```bash
   make -f Makefile.djgpp
   ```
3. **Run**:
   ```batch
   MINER386 C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
   ```

### Option C: ELKS Linux

1. **Get ELKS**: Build from https://github.com/jbruchon/elks
2. **Get Lua**: Build Lua 5.1 for ELKS or use the small Lua interpreter
3. **Run**:
   ```bash
   export RUSTCHAIN_WALLET=C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
   lua miner.lua
   ```

## 🔐 Hardware Fingerprinting

The Intel 386 miner generates a unique hardware fingerprint leveraging:

### 386-Specific Entropy Sources

1. **Clock Crystal Drift** — The 386's crystal oscillator has massive drift compared
   to modern CPUs. This drift pattern is unique to each board and can't be emulated.

2. **No-FPU Detection** — Absence of a 387 coprocessor is itself a fingerprint.
   The miner detects whether a 387 is present and includes this in the attestation.

3. **ISA Bus Timing** — ISA bus cycles have specific timing characteristics that
   vary between motherboards. Memory-mapped I/O access patterns reveal board-specific
   timing quirks.

4. **Memory Access Patterns** — Early 386s had no L1/L2 cache. Cache-less memory
   access patterns are distinctly different from cached modern CPUs.

5. **Interrupt Controller** — The 8259 PIC interrupt controller timing and the
   way the 386 handles interrupts creates board-specific fingerprints.

6. **CPUID Absence** — The original 386 did not have the CPUID instruction.
   Attempting CPUID returns 0 and this itself is a strong vintage fingerprint.

## 📡 Network Protocol

The miner communicates with the RustChain node over HTTP (TLS is not available
on 386-era systems):

```
GET /attest/challenge
POST /attest/submit
```

### Attestation Payload

```json
{
  "miner": "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
  "miner_id": "i386-dos-xxxx-xxxx",
  "nonce": "<challenge-nonce>",
  "report": {
    "nonce": "<nonce>",
    "commitment": "<sha256-commitment>",
    "derived": {
      "mean_ns": 1234.5,
      "variance_ns": 567.8,
      "sample_count": 48
    },
    "entropy_score": 567.8
  },
  "device": {
    "family": "i386",
    "arch": "Intel 80386",
    "model": "i386",
    "cpu": "Intel 80386DX-40",
    "cores": 1,
    "memory_kb": 4096
  },
  "signals": {
    "macs": ["xx:xx:xx:xx:xx:xx"],
    "hostname": "RUSTCHAIN-386"
  },
  "fingerprint": {
    "checks": {
      "fpu_present": {"passed": false, "data": {"has_387": false}},
      "cpuid_works": {"passed": false, "data": {"cpuid_result": 0}},
      "cache_present": {"passed": false, "data": {"cache_size_kb": 0}},
      "crystal_drift": {"passed": true, "data": {"drift_ppm": 250}}
    },
    "all_passed": true
  },
  "miner_version": "1.0.0-i386"
}
```

## 📊 Antiquity Multiplier

| Architecture | Multiplier | Class | Vintage Year |
|-------------|------------|-------|--------------|
| Intel 80386 | **4.0x** | MYTHIC | 1985 |
| Acorn ARM2 | 4.0x | MYTHIC | 1987 |
| DEC VAX-11/780 | 3.5x | MYTHIC | 1977 |
| Motorola 68000 | 3.0x | LEGENDARY | 1979 |
| Modern x86_64 | 0.8x | MODERN | 2020+ |

## 🏗️ Build from Source

### Lua Miner (Any Platform)

No build required. The Lua miner is platform-independent.

### C Miner (DJGPP Cross-Compile)

```bash
# Install DJGPP cross-compiler (on Linux)
apt install djgpp  # Debian/Ubuntu
# or
pacman -S djgpp    # Arch

# Build
cd rustchain-miner-i386
make -f Makefile.djgpp

# Output: MINER386.EXE
```

### Native Build on 386

```batch
# On your 386 system with FreeDOS and DJGPP installed
C:\> CD C:\RUSTCHAIN
C:\RUSTCHAIN> MAKE
```

## 📁 File Structure

```
rustchain-miner-i386/
├── README.md                    # This file
├── MINER.LUA                    # Main Lua miner
├── SHA256.LUA                   # SHA256 implementation in Lua
├── NET.LUA                      # mTCP HTTP client
├── FINGERPRINT.LUA              # 386-specific fingerprinting
├── MINER.C                      # C implementation (DJGPP)
├── SHA256.C                     # SHA256 in C
├── FINGERPRINT.C                # C fingerprint implementation
├── NET_DJGPP.C                  # DJGPP TCP/IP client
├── MAKEFILE                     # Native Makefile
├── MAKEFILE.DJGPP               # DJGPP cross-compile Makefile
└── CONFIG.BAT                   # FreeDOS configuration batch
```

## ⚠️ Known Limitations

1. **No TLS** — 386-era systems cannot handle modern TLS. The miner uses HTTP only.
2. **Slow attestation** — Each attestation cycle may take several minutes on a slow 386.
3. **Limited RAM** — With only 4-8MB, memory is tight. The Lua miner uses ~500KB.
4. **No multiprocessing** — 386 doesn't support SMP. Single core only.
5. **Floppy reliability** — Floppy disks are unreliable. Use CF-to-IDE adapter.

## 🔗 Resources

- [FreeDOS](http://www.freedos.org/) — Free DOS operating system
- [mTCP](http://www.brutman.com/mTCP/) — TCP/IP stack for DOS
- [DJGPP](http://www.delorie.com/djgpp/) — GCC for DOS
- [ELKS](https://github.com/jbruchon/elks) — Embeddable Linux Kernel Subset
- [Lua](https://www.lua.org/) — Lightweight scripting language
- [RustChain](https://rustchain.org) — Proof-of-Antiquity blockchain

## 📄 License

MIT OR Apache-2.0 — Same as RustChain

## 🙏 Acknowledgments

- The FreeDOS team for keeping DOS alive
- Michael B. Brutman for mTCP
- The DJGPP team for DOS GCC
- The RustChain community for supporting vintage hardware preservation
