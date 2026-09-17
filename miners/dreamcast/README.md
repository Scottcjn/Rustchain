# Sega Dreamcast (SH4 Linux) RustChain Miner & Build Guide

## Overview
This directory contains the native SH4 C client implementation and build guide for running the RustChain Proof-of-Antiquity miner on Sega Dreamcast (SH7750 RISC @ 200MHz, 16MB RAM, Broadband Adapter HIT-0400/HIT-0300).

- **Target Architecture**: `sh4` / `sh7750`
- **Target OS**: Linux 5.x / 6.x (`arch/sh/boards/mach-dreamcast/`)
- **Antiquity Multiplier**: **3.0x** (Highest on RustChain network)

---

## 1. Kernel Build & Configuration (Section 1: 50 RTC)

Mainline Linux kernel has native support for Sega Dreamcast G2 bus and BBA network interface.

### Toolchain Setup
```bash
# Ubuntu / Debian cross toolchain
sudo apt-get install gcc-sh4-linux-gnu binutils-sh4-linux-gnu
```

### Kernel Compilation
```bash
git clone --depth 1 https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git linux-sh4
cd linux-sh4

# Configure Dreamcast board
make ARCH=sh CROSS_COMPILE=sh4-linux-gnu- dreamcast_defconfig

# Ensure the following are enabled in .config:
# CONFIG_CPU_SUBTYPE_SH7750=y
# CONFIG_SH_DREAMCAST=y
# CONFIG_SH_DMA=y
# CONFIG_PCI=y
# CONFIG_NET_ETHERNET=y
# CONFIG_8139TOO=y (Realtek 8139 chipset on HIT-0400 BBA)
# CONFIG_BLK_DEV_INITRD=y
# CONFIG_TMPFS=y

make ARCH=sh CROSS_COMPILE=sh4-linux-gnu- zImage -j$(nproc)
```

---

## 2. SH4 Native Miner Client (Section 3: 50 RTC)

The C miner client (`miner_dreamcast.c`) provides:
1. **Zero-dependency SHA-256 Engine**: Embedded cryptography avoiding large OpenSSL binaries to fit in 16MB system RAM.
2. **Hardware Timing Calibration**:
   - Measures 16KB D-cache latency profiles specific to the SH7750 4-way set associative L1 cache.
   - Measures FPU pipeline jitter across transcendental float sequences.
3. **Anti-Emulation Protection**: Real SH4 CPU pipeline timing vs hypervisor / QEMU virtualization detection.

### Compilation
```bash
sh4-linux-gnu-gcc -O2 -m4 -ml miner_dreamcast.c -o miner_dreamcast
```

### Execution
```bash
./miner_dreamcast
```

---

## 3. MicroPython Embedded Port (Section 2: 25 RTC)

For rapid scripting on SH4 Linux:
```bash
git clone --depth 1 https://github.com/micropython/micropython.git
cd micropython/ports/unix
make CROSS_COMPILE=sh4-linux-gnu- CFLAGS_EXTRA="-m4 -ml" MICROPY_PY_USSL=0
```
Produces lightweight ~280KB binary perfectly sized for Dreamcast's 16MB footprint.
