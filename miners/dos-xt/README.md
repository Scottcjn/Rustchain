# RustChain Miner for IBM PC/XT

[![Version](https://img.shields.io/badge/version-0.1.0--xt-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-IBM%20PC%2FXT-lightgrey.svg)]()
[![CPU](https://img.shields.io/badge/CPU-Intel%208088-orange.svg)]()
[![Bounty](https://img.shields.io/badge/bounty-150%20RTC-green.svg)]()

RustChain Proof-of-Antiquity miner for vintage IBM PC/XT hardware (1981-1987).

## Features

- **Native 8088 Code**: Compiled for real-mode x86 (8088/8086)
- **Hardware Fingerprinting**: 6-point anti-emulation detection
  - PIT (8253/8254) timer drift measurement
  - ISA bus timing analysis
  - BIOS string verification
  - CMOS RTC drift detection
  - CPU cycle timing
  - Memory timing patterns
- **Vintage Multiplier**: Earn 2.5x rewards on real hardware
- **VM Detection**: Automatically detected in DOSBox/86Box (0 RTC earnings)
- **Tiny Memory Model**: < 64 KB total footprint
- **mTCP Support**: Lightweight TCP/IP stack for DOS

## System Requirements

### Minimum
- IBM PC/XT or compatible
- Intel 8088 @ 4.77 MHz
- 256 KB RAM
- PC DOS 2.0 or MS-DOS 2.x
- NE2000-compatible network card (for networked mining)

### Recommended
- 512 KB RAM
- PC DOS 3.3 or later
- 10 MB hard drive
- NE2000 or 3C503 network card

## Building

### Prerequisites

1. **Open Watcom C Compiler** (v2.0 or later)
   - Download: https://github.com/open-watcom/open-watcom-v2
   - Install to `C:\WATCOM`

2. **mTCP Library** (optional, for networking)
   - Download: http://www.brutman.com/mTCP/
   - Extract to `C:\MTCP`

### Environment Setup

```batch
SET WATCOM=C:\WATCOM
SET PATH=%WATCOM%\BINW;%PATH%
SET INCLUDE=%WATCOM%\H
SET LIB=%WATCOM%\LIB286;%WATCOM%\LIB286\DOS
```

### Build Commands

```batch
cd miners\dos-xt

# Build without networking (offline mode)
build.bat

# Build with mTCP networking (requires mTCP)
build_mtcp.bat
```

### Manual Build

```batch
# Compile source files
wcc -ml -bt=dos -ox -s src\main.c
wcc -ml -bt=dos -ox -s src\hw_xt.c
wcc -ml -bt=dos -ox -s src\pit.c
wcc -ml -bt=dos -ox -s src\attest.c
wcc -ml -bt=dos -ox -s src\network.c

# Link into .COM file (tiny memory model)
wlink system dos file main.obj file hw_xt.obj file pit.obj file attest.obj file network.c name miner.com
```

## Usage

### Basic Usage

```batch
miner.com -w RTC4325af95d26d59c3ef025963656d22af638bb96b
```

### Command Line Options

```
miner.com [options]

Options:
  -w <wallet>    RTC wallet address (required)
  -n <url>       Node URL (default: https://50.28.86.131)
  -v             Verbose output
  -h             Show help

Environment Variables:
  RTC_WALLET     Wallet address
  RTC_NODE_URL   Node URL
```

### Examples

```batch
# Mine with wallet address
miner.com -w RTCxxxxxxxxxxxxxxxxxxxx

# Use custom node
miner.com -w RTCxxxxxxxxxxxxxxxxxxxx -n https://rustchain.org

# Verbose mode
miner.com -w RTCxxxxxxxxxxxxxxxxxxxx -v
```

## Configuration

### Network Setup (mTCP)

Create `MTCP.CFG` in the same directory as `miner.com`:

```
# mTCP Configuration
PACKETINT 0x60
IPADDR 192.168.1.100
NETMASK 255.255.255.0
GATEWAY 192.168.1.1
NAMESERVER 8.8.8.8
```

### Load Packet Driver

Before running the miner, load your network card's packet driver:

```batch
# For NE2000 card at I/O port 0x300
NE2000.COM 0x60 0x300 0 0

# For 3C503 card
3C503.COM 0x60 0x280 0 0
```

Then run the miner:

```batch
miner.com -w RTCxxxxxxxxxxxxxxxxxxxx
```

## Hardware Fingerprinting

The miner implements 6 hardware-specific checks to verify real vintage hardware:

### 1. PIT Timer Drift (Primary Check)
- **What**: Measures 8253/8254 PIT crystal oscillator drift
- **Real Hardware**: 1190-1196 ticks/sec (varies per chip)
- **Emulator**: Exactly 1193 ticks/sec (too precise)

### 2. ISA Bus Timing
- **What**: Measures I/O port access latency
- **Real Hardware**: 100-300ns per I/O operation
- **Emulator**: Near-zero latency

### 3. BIOS String Analysis
- **What**: Reads BIOS ROM at F000:FFF0
- **Real Hardware**: "IBM", "AMI", "Award", "Phoenix"
- **Emulator**: Generic or unknown BIOS

### 4. CPU Cycle Timing
- **What**: Measures fixed computation time
- **Real Hardware**: Consistent 8088 cycle counts
- **Emulator**: Cycle-approximate, too consistent

### 5. CMOS RTC Drift
- **What**: Measures MC146818 RTC drift over time
- **Real Hardware**: Crystal drift (seconds/hour)
- **Emulator**: Synced to host clock (no drift)

### 6. Memory Timing
- **What**: DRAM refresh cycle effects
- **Real Hardware**: Measurable refresh overhead
- **Emulator**: No physical refresh

## Emulator Detection

When running in DOSBox or 86Box, the miner will:

1. Detect emulator signatures
2. Display warning message
3. Continue running but earn **0 RTC**
4. Log detection reasons

This prevents abuse while allowing development and testing.

## Troubleshooting

### "Network initialization failed"
- Ensure packet driver is loaded
- Check `MTCP.CFG` configuration
- Verify network card I/O port settings

### "Attestation failed"
- Check network connectivity
- Verify node URL is correct
- Ensure system clock is accurate

### "Emulator detected"
- This is expected in DOSBox/86Box
- Run on real hardware for rewards
- Check hardware fingerprinting logs

## Performance

### Expected Hash Rate
- IBM PC/XT (8088 @ 4.77 MHz): ~100 H/s
- IBM PC AT (286 @ 6 MHz): ~500 H/s
- 386SX (16 MHz): ~2000 H/s

### Power Consumption
- IBM PC/XT: ~100W
- Efficiency: ~1 H/W (but vintage multiplier compensates)

## Bounty Information

**Issue**: #422 (or #27 for DOS/8086)
**Reward**: 150 RTC (~$15 USD)
**Multiplier**: 2.5x for real IBM PC/XT hardware

### How to Claim

1. Submit PR with source code to `rustchain/miners/dos-xt/`
2. Include build instructions and documentation
3. Provide proof of real hardware operation:
   - Photo of IBM PC/XT running miner
   - Screenshot of mining output
   - Emulator detection screenshot (DOSBox)
4. Add wallet address to issue comment

**Wallet**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`

## Development

### Project Structure

```
miners/dos-xt/
├── src/
│   ├── main.c          # Main entry point
│   ├── miner.h         # Miner core definitions
│   ├── hw_xt.h/.c      # Hardware detection (XT-specific)
│   ├── pit.h/.c        # PIT timer operations
│   ├── attest.h/.c     # Hardware attestation
│   └── network.h/.c    # Network stack (mTCP wrapper)
├── build.bat           # Build script
├── build_mtcp.bat      # Build with mTCP
└── README.md           # This file
```

### Memory Map

```
0x00000 - 0x0FFFF: Real Mode IVT
0x10000 - 0x9FFFF: DOS Conventional Memory (576 KB available)
0xA0000 - 0xBFFFF: Video Memory
0xC0000 - 0xFFFFF: ROM Area (BIOS, Video BIOS, Adapter ROMs)
```

Miner uses < 64 KB in tiny memory model.

## References

- [Intel 8088 Datasheet](https://archive.org/details/intel8088)
- [IBM PC/XT Technical Reference](https://archive.org/details/IBM_PC_XT_Technical_Reference)
- [8253/8254 PIT Datasheet](https://archive.org/details/8253-8254-datasheet)
- [mTCP Documentation](http://www.brutman.com/mTCP/)
- [Open Watcom Documentation](https://open-watcom.github.io/)
- [RustChain Documentation](https://github.com/Scottcjn/Rustchain)

## License

MIT OR Apache-2.0 (same as RustChain)

## Disclaimer

This software is provided "as is" without warranty. Use on vintage hardware at your own risk. The authors are not responsible for any damage to hardware or data loss.

---

**Created**: 2026-03-13  
**Version**: 0.1.0-xt  
**Bounty Wallet**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`
