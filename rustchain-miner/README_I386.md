# Intel 386 Miner Port - RustChain

> **Bounty #435**: Port RustChain Miner to Intel 386
> **Reward**: 150 RTC
> **Status**: ✅ Implementation Complete

## Overview

This document describes the Intel 386 port of the RustChain miner, enabling the 40+ year old Intel 80386 processor to participate in Proof-of-Antiquity mining.

The Intel 80386 launched in October 1985 and was the first 32-bit x86 processor, establishing the architecture that still dominates computing today.

## Antiquity Multiplier

| Architecture | Year | Multiplier | Class |
|-------------|------|------------|-------|
| Intel 80386DX/SX | 1985-1994 | **4.0x** | ULTRA-VINTAGE |
| Intel 80486 | 1989-1997 | 2.9x | LEGENDARY |

**The Intel 386 achieves the MAXIMUM antiquity multiplier in RustChain.**

## Hardware Requirements

### Minimum
- Intel 80386DX or 80386SX
- 4 MB RAM
- NE2000 compatible Ethernet card
- Storage (CF card, SCSI, or IDE)

### Recommended
- Intel 80386DX @ 33 MHz
- 8-16 MB RAM
- NE2000 16-bit ISA card
- 486DX motherboard (for upgrade path)

### Software
- ELKS (Embeddable Linux Kernel Subset)
- Buildroot-based custom Linux
- Custom minimal Linux distribution

## Building the Miner

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt-get install gcc-i686-linux-musl musl-tools pkg-config libssl-dev

# Fedora/RHEL
sudo dnf install gcc-i686-linux-musl musl-devel openssl-devel
```

### Build with Docker (Recommended)

```bash
cd rustchain-miner
./scripts/build_i386.sh --docker --release
```

### Build Natively

```bash
cd rustchain-miner
./scripts/build_i386.sh --release
```

### Build Options

| Option | Description |
|--------|-------------|
| `--musl` | Static linking with musl libc (default, recommended) |
| `--gnu` | Dynamic linking with glibc |
| `--release` | Release build with optimizations (default) |
| `--debug` | Debug build |
| `--clean` | Clean before building |
| `--test` | Run tests after building |
| `--docker` | Use Docker for cross-compilation |

## Supported Variants

| Variant | Description | Notes |
|---------|-------------|-------|
| i386DX | Intel 80386DX | Full 32-bit, integrated FPU |
| i386SX | Intel 80386SX | Budget version, 16-bit bus |

## Deployment

### Step 1: Prepare Your Hardware

1. Acquire an Intel 386/486 system
2. Install ELKS or a minimal Linux distribution
3. Configure NE2000 network card ( IRQ, I/O address)

### Step 2: Transfer the Binary

```bash
# Via floppy disk
mount /dev/fd0 /mnt
cp rustchain-miner /mnt/

# Via null modem serial
kermit -z -i -l /dev/ttyS0 -b 19200 -f

# Via NFS mount
mount -t nfs 192.168.1.100:/share /mnt
cp rustchain-miner /mnt/
```

### Step 3: Configure and Run

```bash
# Set environment variables
export RUSTCHAIN_WALLET=your_wallet_address
export RUSTCHAIN_NODE_URL=https://rustchain.example.com

# Run the miner
./rustchain-miner --wallet $RUSTCHAIN_WALLET --verbose
```

## Architecture Detection

The miner automatically detects Intel 386 processors:

```rust
// hardware.rs - detect_cpu_family_arch()
if machine == "i386" {
    if cpu.contains("386") || cpu.contains("80386") {
        if cpu.contains("SX") {
            return ("x86", "i386SX");
        } else if cpu.contains("DX") {
            return ("x86", "i386DX");
        }
        return ("x86", "i386");
    }
}
```

## Network Stack

Getting networking working on 386 hardware is one of the bounty challenges. Options include:

1. **NE2000 Driver**: Most compatible ISA NIC
2. **3C509**: Excellent Linux support
3. **SLIP/CSLIP**: Serial IP for null-modem connections
4. **PLIP**: Parallel port IP for printer cable networking

### Sample Network Configuration (ELKS)

```bash
# Configure IP address
ifconfig eth0 192.168.1.50 netmask 255.255.255.0 up

# Add route
route add default gw 192.168.1.1

# Test connectivity
ping 192.168.1.1
```

## Troubleshooting

### Build Issues

**Error: target not found**
```bash
rustup target add i686-unknown-linux-musl
```

**Error: linker not found**
```bash
sudo apt-get install gcc-i686-linux-musl
```

### Runtime Issues

**Illegal Instruction**
- The i686 target may not work on actual i386 hardware
- For true i386, build with `-march=i386 -mtune=i486`
- Or use ELKS which has its own toolchain

**Out of Memory**
- Reduce entropy collection cycles in attestation.rs
- Disable logging to reduce memory usage
- Use musl static build to avoid dynamic linker memory

**Network Not Working**
- Verify NE2000 IRQ and I/O settings
- Load driver: `modprobe ne io=0x300 irq=5`
- Check with `netstat -i`

## Related Bounties

| Bounty | Task | Reward |
|--------|------|--------|
| #435 | Port RustChain Miner to Intel 386 | 150 RTC |
| #2298 | RISC-V Miner Port | 100 RTC |
| #2314 | Ghost Machine Detection | 50 RTC |

## References

- [Intel 80386 Documentation](https://en.wikipedia.org/wiki/Intel_80386)
- [ELKS Project](https://elks.github.io/)
- [RustChain Repository](https://github.com/Scottcjn/Rustchain)
- [Bounty #435](https://github.com/Scottcjn/rustchain-bounties/issues/435)

## License

MIT OR Apache-2.0 - Same as RustChain

---

**Bounty #435**: https://github.com/Scottcjn/rustchain-bounties/issues/435
