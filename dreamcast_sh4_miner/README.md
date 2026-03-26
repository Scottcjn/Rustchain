<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: 2026 RustChain Contributors -->
# RustChain Miner for Sega Dreamcast (SH4 Linux)

Reference implementation of the RustChain Proof-of-Antiquity miner for the
**Sega Dreamcast** running Linux, using the **Hitachi SH4 (SH7750)** CPU @
200MHz with the **Sega Broadband Adapter (BBA)** for network connectivity.

By running this miner on real Dreamcast hardware, you qualify for the
**3.0x SH4 antiquity multiplier** — the highest in the RustChain network.

## Hardware Requirements

| Component | Notes |
|-----------|-------|
| Sega Dreamcast (any region/revision) | SH4 @ 200MHz, 16MB RAM |
| Sega Broadband Adapter (HIT-0400) | 100Mbps Ethernet — preferred |
| GDEMU or SD card adapter | Boot media |
| CD-R (MIL-CD exploit) | Alternative boot method |
| Ethernet connection | TCP/IP networking |

## Architecture Overview

### SH4 CPU Features

- **SH7750R** or **SH7750** — Hitachi SuperH RISC architecture
- Full MMU with TLB
- Real FPU (single-precision and double-precision)
- 16KB I-cache + 16KB D-cache (split)
- TMU (Timer Unit) with 3 channels — used for clock-drift fingerprinting
- 27MHz system clock → 200MHz CPU clock via PLL

### SH4 Antiquity Multiplier: 3.0x

The SH4 was introduced in 1998 and first shipped in consumer hardware (Dreamcast)
in 1998/1999 — qualifying it as vintage hardware. The SH4 architecture receives
the **highest antiquity multiplier** in RustChain:

| Architecture | Multiplier | Era | Notes |
|---|---|---|---|
| SH4 / Dreamcast | **3.0x** | ANCIENT (1998) | Highest in network |
| PowerPC G4 | 2.5x | ANCIENT (2003) | Apple G4 only |
| DEC Alpha | 2.5x | ANCIENT (1992) | Pre-2000 only |
| x86_64 (modern) | 0.8x | MODERN | Baseline |

## Build Instructions

### Prerequisites

```bash
# Install SH4 cross-compilation toolchain (Debian/Ubuntu)
sudo apt-get install gcc-sh4-linux-gnu binutils-sh4-linux-gnu
```

### Build the Miner (Linux cross-compile)

```bash
cd dreamcast_sh4_miner
make clean
make
```

### Build Linux Kernel for Dreamcast

```bash
# Clone mainline kernel
git clone https://github.com/torvalds/linux.git
cd linux
make ARCH=sh CROSS_COMPILE=sh4-linux-gnu- dreamcast_defconfig
make ARCH=sh CROSS_COMPILE=sh4-linux-gnu- -j$(nproc)
```

## Hardware Fingerprinting

The Dreamcast SH4 miner uses 4 hardware signatures unique to the platform:

### 1. Clock Drift (SH4 TMU Timer)
The SH4's TMU (Timer Unit) has channel 0 driven by the 27MHz system clock.

### 2. Cache Timing Fingerprint
The SH4 has a split 16KB I-cache and 16KB D-cache with unique latency profiles.

### 3. FPU Jitter
The SH4 FPU implements IEEE 754 with unique pipelining characteristics.

### 4. Anti-Emulation Detection
Emulators do not perfectly replicate SH4 cache, TMU, or FPU timing.

## File Manifest

```
dreamcast_sh4_miner/
├── README.md              # This file
├── Makefile              # Cross-compile build system
├── miner.c               # Main miner entry point + attestation
├── fingerprint.c          # SH4 hardware fingerprinting
├── fingerprint.h         # Fingerprint interface definitions
├── networking.c          # BBA TCP/IP networking
├── networking.h          # Network interface definitions
├── sha256.S              # SH4-optimized SHA256 (assembly)
├── linux-build/          # Linux kernel build hints + configs
│   ├── README.md
│   └── dreamcast_defconfig
└── micropython/          # MicroPython build hints for SH4
    └── README.md
```

## License

SPDX-License-Identifier: MIT
SPDX-FileCopyrightText: 2026 RustChain Contributors
