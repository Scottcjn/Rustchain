# RustChain PlayStation 1 Miner

**"Fossil Edition"** - Mining RustChain on a 30-year-old game console!

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Platform](https://img.shields.io/badge/Platform-PlayStation%201-orange)](https://en.wikipedia.org/wiki/PlayStation_(console))
[![CPU](https://img.shields.io/badge/CPU-MIPS%20R3000A%20@%2033.87%20MHz-blue)](https://en.wikipedia.org/wiki/MIPS_architecture)
[![Antiquity](https://img.shields.io/badge/Antiquity%20Multiplier-2.8x-brightgreen)](https://github.com/Scottcjn/Rustchain)

## Overview

This project ports the RustChain miner to Sony PlayStation 1, making it the **first blockchain miner to run on PS1 hardware**. The PS1 uses a **MIPS R3000A CPU** with only **2 MB RAM**, presenting unique challenges for blockchain attestation.

### Key Features

- ✅ **MIPS R3000A optimized** - Native code for PS1 CPU
- ✅ **Hardware fingerprinting** - BIOS, CD-ROM, RAM timing
- ✅ **Serial bridge** - PC acts as network gateway
- ✅ **Memory card storage** - Wallet saved to memory card
- ✅ **2.8x antiquity multiplier** - Per RIP-304
- ✅ **Anti-emulation** - Detects real hardware vs emulators

## Architecture

```
┌─────────────────┐     Serial (9600 bps)     ┌──────────────┐
│  PlayStation 1  │◄─────────────────────────►│  PC Bridge   │
│  (MIPS R3000A)  │    TX/RX + GND            │  (Python)    │
│  Runs miner ROM │                           │  → Node API  │
└─────────────────┘                           └──────────────┘
                                                      │
                                                      ▼
                                              ┌──────────────┐
                                              │ RustChain    │
                                              │ Node         │
                                              └──────────────┘
```

## Quick Start

### 1. Build the PS1 Miner

```bash
cd ps1_miner
make
# Output: rustchain_ps1_miner.bin
```

### 2. Set Up Serial Connection

Connect PS1 controller port to PC via USB-to-TTL adapter:

```
USB-TTL     PS1 Controller Port
--------    -------------------
GND    ──── Pin 1 (GND)
TX     ──── Pin 3 (RX)
RX     ──── Pin 2 (TX)
```

⚠️ **WARNING:** Do NOT connect +3.3V pins!

### 3. Run PC Bridge

```bash
cd ps1_bridge
pip install -r requirements.txt
python bridge.py -p COM3 -w ps1-miner
```

### 4. Run PS1 Miner

Load `rustchain_ps1_miner.bin` on your PS1 (via FreeMcBoot or homebrew launcher).

## Hardware Requirements

| Component | Requirement |
|-----------|-------------|
| **PS1** | Any model (SCPH-1000 to SCPH-5903) |
| **Serial Adapter** | USB-to-TTL (CP2102, FTDI, CH340) |
| **PC** | Windows/Linux/macOS with USB |
| **Memory Card** | For wallet storage (optional) |

## Software Requirements

| Component | Version |
|-----------|---------|
| **PSn00bSDK** | Latest (for building) |
| **MIPS GCC** | Any MIPS cross-compiler |
| **Python** | 3.8+ (for bridge) |
| **DuckStation** | Optional (for testing) |

## Documentation

- **[BUILD.md](docs/BUILD.md)** - How to build the miner
- **[SETUP.md](docs/SETUP.md)** - Hardware setup guide
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common issues
- **[PS1_PORT_PLAN.md](PS1_PORT_PLAN.md)** - Full implementation plan

## Project Structure

```
rustchain-ps1-port/
├── ps1_miner/           # PS1 miner source code
│   ├── main.c          # Main miner loop
│   ├── sha256.c/h      # SHA-256 implementation
│   ├── serial.c/h      # Serial driver
│   ├── fingerprint.c/h # Hardware fingerprinting
│   ├── memcard.c/h     # Memory card I/O
│   └── Makefile        # Build configuration
├── ps1_bridge/         # PC bridge software
│   ├── bridge.py       # Main bridge program
│   └── requirements.txt
├── docs/               # Documentation
│   ├── BUILD.md
│   ├── SETUP.md
│   └── TROUBLESHOOTING.md
├── PS1_PORT_PLAN.md    # Implementation plan
└── README.md           # This file
```

## Performance

| Metric | Value |
|--------|-------|
| **CPU** | MIPS R3000A @ 33.87 MHz |
| **RAM Usage** | ~512 KB |
| **Binary Size** | ~50-100 KB |
| **Attestation Time** | ~30-60 seconds |
| **Power Consumption** | ~10W (PS1 idle) |

## Antiquity Multiplier

Per RIP-304, PS1 qualifies for **2.8x multiplier**:

| Hardware | Multiplier |
|----------|------------|
| PS1 (MIPS R3000A) | **2.8x** |
| N64 (MIPS R4300i) | 2.5x |
| PowerPC G4 | 2.5x |
| Modern x86 | 1.0x |

## Security

### Anti-Emulation

The miner detects real hardware via:
- Controller port jitter
- CD-ROM mechanical timing
- RAM timing variance
- GTE (GPU) timing

Emulators have near-zero jitter and will be rejected.

### Fingerprint Validation

Each attestation includes:
- BIOS version hash
- CD-ROM access timing
- RAM timing (nanoseconds)
- Controller port variance

## Wallet

**Bounty Wallet:** `RTC4325af95d26d59c3ef025963656d22af638bb96b`

This wallet receives the 150 RTC bounty for completing the PS1 port.

## Testing

### Emulator Testing

```bash
# Test in DuckStation
duckstation --batch rustchain_ps1_miner.bin
```

### Real Hardware Testing

1. Transfer binary to PS1
2. Connect serial adapter
3. Run bridge on PC
4. Start miner on PS1

## Known Limitations

1. **Slow serial** - 9600 bps limits attestation speed
2. **2 MB RAM** - Limits features and buffer sizes
3. **No FPU** - SHA-256 is software-only
4. **Serial required** - No built-in Ethernet

## Future Improvements

- [ ] PS1 Network Adapter support (Ethernet)
- [ ] Faster serial rates (115200 bps)
- [ ] OLED display for status
- [ ] Dual PS1 mining via link cable
- [ ] Overclocking support (for dev consoles)

## References

- [RIP-304: Retro Console Mining](https://github.com/Scottcjn/Rustchain/issues/488)
- [RIP-200: 1 CPU = 1 Vote](https://github.com/Scottcjn/Rustchain/blob/main/rips/docs/RIP-0200-round-robin-1cpu1vote.md)
- [PSn00bSDK](https://github.com/LM-Softland/PSn00bSDK)
- [PS1 Hardware Reference](https://psx-spx.consoledev.net/)
- [MIPS R3000A Datasheet](https://en.wikipedia.org/wiki/MIPS_R3000)

## License

- **PS1 Miner:** Apache 2.0 (part of RustChain)
- **SHA-256:** Public domain
- **Bridge:** Apache 2.0

## Credits

- **Original RustChain:** Scottcjn / Elyan Labs
- **PS1 Port:** @48973 (subagent: 马)
- **PSn00bSDK:** LM-Softland
- **Inspired by:** DOS Miner, Pico Bridge

---

*"Every CPU deserves dignity" — Even a 30-year-old game console.* 🦀🎮

**Part of the RustChain Ecosystem:**
- [RustChain](https://github.com/Scottcjn/Rustchain) - Proof-of-Antiquity blockchain
- [BoTTube](https://bottube.ai) - AI video platform
- [Beacon](https://github.com/Scottcjn/beacon-skill) - Agent communication protocol
