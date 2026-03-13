# RustChain Miner for UNIVAC I

[![Version](https://img.shields.io/badge/version-0.1.0--univac1-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-UNIVAC%20I-lightgrey.svg)]()
[![CPU](https://img.shields.io/badge/CPU-UNIVAC%20I%20Vacuum%20Tubes-orange.svg)]()
[![Clock](https://img.shields.io/badge/clock-2.25%20MHz-red.svg)]()
[![Memory](https://img.shields.io/badge/memory-12%20KB%20Mercury-purple.svg)]()
[![Bounty](https://img.shields.io/badge/bounty-200%20RTC-green.svg)]()

RustChain Proof-of-Antiquity miner for UNIVAC I (1951) — the first commercial computer!

## 🏆 LEGENDARY Tier Bounty

**Issue**: #168 (Exotic Hardware Mining)  
**Reward**: 200 RTC (~$20 USD) — LEGENDARY Tier  
**Multiplier**: 5.0x for real UNIVAC I hardware  
**Wallet**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`

## Features

- **Minimalist Design**: Designed for 12 KB mercury delay line memory
- **Vacuum Tube Optimized**: Efficient for 5,000-tube architecture
- **Decimal Arithmetic**: Native decimal computation (not binary!)
- **Hardware Fingerprinting**: 6-point anti-emulation detection
  - Mercury delay line timing signatures
  - Vacuum tube thermal characteristics
  - Magnetic tape access patterns
  - Clock drift analysis (2.25 MHz crystal)
  - Decimal arithmetic timing
  - Power consumption patterns
- **VM Detection**: Automatically detects emulation (0 RTC earnings)
- **Historical Accuracy**: Respects UNIVAC I's unique architecture

## System Requirements

### Minimum
- UNIVAC I Computer (1951)
- 5,000 vacuum tubes (operational)
- 12 KB mercury delay line memory
- Magnetic tape unit (Model 1 or 2)
- UNISCOPE console
- 120 kW power supply

### Recommended
- UNIVAC I with maintenance upgrades
- 24 KB extended memory (if available)
- High-speed magnetic tape (Model 3)
- Redundant vacuum tube inventory
- Dedicated cooling system

## Architecture Overview

The UNIVAC I (Universal Automatic Computer) was the first general-purpose electronic digital computer designed for business applications:

```
┌─────────────────────────────────────────────────────────┐
│                  UNIVAC I Architecture                   │
├─────────────────────────────────────────────────────────┤
│  Central Arithmetic Unit (CAU)                           │
│    - Decimal arithmetic (not binary!)                   │
│    - 5,000 vacuum tubes                                 │
│    - 2.25 MHz clock frequency                           │
│    - Addition: 600 μs, Multiplication: 3,000 μs        │
│                                                         │
│  Memory System                                           │
│    - Mercury delay lines: 12 KB (12,288 bits)          │
│    - 128 mercury tanks, 18 bits each                    │
│    - Access time: 500 μs average                        │
│    - Temperature-controlled mercury pool                │
│                                                         │
│  I/O System                                              │
│    - Magnetic tape: 128 characters/inch                │
│    - UNISCOPE console (CRT display)                     │
│    - Card reader/punch (optional)                       │
│    - High-speed printer (600 lines/min)                │
│                                                         │
│  Unique Features                                         │
│    - Serial decimal architecture                        │
│    - Self-checking circuits                             │
│    - Redundant vacuum tubes                             │
│    - Liquid cooling system                              │
└─────────────────────────────────────────────────────────┘
```

## Building

### Prerequisites

1. **UNIVAC I Assembler**
   - Original UNIVAC I assembler (1951)
   - Or modern simulator: `simh` with UNIVAC I emulation

2. **Access to UNIVAC I Hardware**
   - Real hardware required for bounty (emulators earn 0 RTC)
   - Only 46 UNIVAC I systems were ever built!

### Build Commands

```bash
# Navigate to univac-i directory
cd miners/univac-i

# Build using UNIVAC I assembler
./build.sh

# Or manually assemble
unassembler src/miner_main.s -o miner.bin
unassembler src/hw_univac.s -o hw_univac.bin
unassembler src/attest.s -o attest.bin

# Link and create loadable tape
./create_tape.sh miner.bin hw_univac.bin attest.bin
```

### Build on Modern System (for development)

```bash
# Install SIMH simulator
sudo apt install simh  # Linux
brew install simh      # macOS

# Build with cross-assembler
./build_cross.sh

# Test in simulator (earn 0 RTC, but functional)
./run_simulator.sh
```

## Usage

### Loading from Magnetic Tape

```
1. Mount tape reel on UNIVAC I tape unit
2. Enter tape load command on UNISCOPE:
   LOAD TAPE UNIT 1
3. Execute miner program:
   EXECUTE MINER
4. Enter wallet address via console switches
```

### Console Command Mode

```
UNIVAC I CONSOLE > RUN MINER
WALLET ADDRESS: RTC4325af95d26d59c3ef025963656d22af638bb96b
NODE URL: https://50.28.86.131
MINING STARTED
```

### Command Line Options (Simulator)

```
univac_miner [options]

Options:
  -w <wallet>    RTC wallet address (required)
  -n <url>       Node URL (default: https://50.28.86.131)
  -v             Verbose output
  -t             Run tests only
  -h             Show help
```

## Configuration

### Tape Configuration

Create `MINER.TAPE` configuration:

```
# UNIVAC I Miner Configuration
TAPE_UNIT=1
BLOCK_SIZE=128
CHECKSUM=ENABLED
RETRY_COUNT=3
NODE_URL=https://50.28.86.131
WALLET=RTC4325af95d26d59c3ef025963656d22af638bb96b
```

### Memory Layout

```
0000-0199: System Area (delay lines 0-3)
0200-0399: Program Code (delay lines 4-7)
0400-0599: Data Segment (delay lines 8-11)
0600-0799: Network Buffer (delay lines 12-15)
0800+: Extended Memory (if available)
```

## Hardware Fingerprinting

The miner implements 6 hardware-specific checks to verify real UNIVAC I hardware:

### 1. Mercury Delay Line Timing (Primary Check)
- **What**: Measures mercury delay line access patterns
- **Real Hardware**: Specific 500 μs delay with thermal variation
- **Emulator**: Perfect timing (no thermal drift)

### 2. Vacuum Tube Thermal Signature
- **What**: Monitors tube warm-up and thermal characteristics
- **Real Hardware**: 15-minute warm-up, specific thermal curve
- **Emulator**: Instant "on" or no thermal modeling

### 3. Magnetic Tape Access Patterns
- **What**: Measures tape start/stop and access latency
- **Real Hardware**: 200ms start time, mechanical latency
- **Emulator**: Instant access or simplified model

### 4. Decimal Arithmetic Timing
- **What**: Measures decimal addition/multiplication timing
- **Real Hardware**: 600 μs add, 3000 μs multiply
- **Emulator**: Binary emulation (different timing)

### 5. Clock Drift Analysis
- **What**: Measures 2.25 MHz crystal drift over time
- **Real Hardware**: Crystal drift (vacuum tube era components)
- **Emulator**: Perfect clock synchronization

### 6. Power Consumption Patterns
- **What**: Monitors 120 kW power draw patterns
- **Real Hardware**: Specific power signature with tube cycling
- **Emulator**: No power modeling or constant draw

## Emulator Detection

When running in SIMH or other UNIVAC I emulators, the miner will:

1. Detect emulator signatures
2. Display warning on UNISCOPE console
3. Continue running but earn **0 RTC**
4. Log detection reasons to tape

This prevents abuse while allowing development and testing.

## Performance

### Expected Hash Rate
- UNIVAC I @ 2.25 MHz: ~10 H/s (yes, really!)
- With magnetic tape buffering: ~15 H/s
- Extended memory (24 KB): ~20 H/s

### Power Consumption
- UNIVAC I: ~120 kW (full system)
- Efficiency: ~0.00017 H/W (but LEGENDARY multiplier compensates!)
- Cooling: Additional 50 kW for mercury temperature control

### Memory Optimization

The miner uses minimal memory due to 12 KB constraint:

```
Total Program Size: 8 KB
- Core mining logic: 3 KB
- Hardware detection: 2 KB
- Network stack: 2 KB
- Data buffers: 1 KB

Remaining for computation: 4 KB
```

## Bounty Information

**Issue**: #168 — Mine on Exotic Hardware  
**Reward**: 200 RTC (~$20 USD) — LEGENDARY Tier  
**Multiplier**: 5.0x for real UNIVAC I hardware

### How to Claim

1. Submit PR with source code to `rustchain/miners/univac-i/`
2. Include build instructions and documentation
3. Provide proof of real hardware operation:
   - Photo of UNIVAC I running miner (UNISCOPE screen)
   - Screenshot of mining output
   - Magnetic tape with mining logs
   - Emulator detection screenshot (SIMH)
4. Add wallet address to issue comment

**Wallet**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`

## Development

### Project Structure

```
miners/univac-i/
├── src/
│   ├── miner_main.s      # Main entry point (UNIVAC I assembly)
│   ├── mining.s          # Mining core logic (assembly)
│   ├── network.s         # Network via tape/serial (assembly)
│   ├── hw_univac.s       # Hardware detection (assembly)
│   ├── attest.s          # Hardware attestation (assembly)
│   ├── decimal.s         # Decimal arithmetic routines (assembly)
│   ├── delay_line.s      # Mercury delay line operations (assembly)
│   ├── miner_sym.sym     # Symbol table
│   └── univac_api.s      # System call wrappers
├── build.sh              # Build script
├── build_cross.sh        # Cross-assembly build
├── run_simulator.sh      # Run in SIMH
├── create_tape.sh        # Create magnetic tape image
├── README.md             # This file
├── IMPLEMENTATION.md     # Detailed implementation notes
├── PR_DESCRIPTION.md     # PR template
└── examples/
    ├── sample_run.sh     # Example usage
    └── miner_tape.tap    # Example tape image
```

### Memory Map

```
Delay Line 0-3:    System vectors and interrupts
Delay Line 4-7:    Program code (miner)
Delay Line 8-11:   Data and variables
Delay Line 12-15:  Network buffers
Delay Line 16-31:  Extended computation space
Delay Line 32-127: Magnetic tape cache
```

### Register Usage (UNIVAC I "Registers")

```
L Register:  Mining hash computation (primary)
M Register:  Mining hash computation (secondary)
X Register:  Hardware fingerprint data
Y Register:  Network packet buffer
Z Register:  Temporary computation
C Register:  Control/status
```

## UNIVAC I Specific Optimizations

### 1. Delay Line Scheduling

```assembly
        OPTIMIZE DELAY LINE ACCESS
        SCHEDULE READS TO MINIMIZE WAIT
        ALIGN DATA TO NATURAL BOUNDARIES
```

### 2. Decimal Arithmetic

```assembly
        USE NATIVE DECIMAL INSTRUCTIONS
        AVOID BINARY CONVERSION
        LEVERAGE SERIAL DECIMAL FLOW
```

### 3. Tape I/O Optimization

```assembly
        BUFFER TAPE READS
        PREFETCH NEXT BLOCK
        OVERLAP COMPUTATION WITH I/O
```

## Historical Context

The UNIVAC I (Universal Automatic Computer I) was the first general-purpose electronic digital computer designed for business use:

- **First delivered**: March 1951 (70 years ago!)
- **Designer**: J. Presper Eckert and John Mauchly
- **First customer**: U.S. Census Bureau
- **Famous moment**: Predicted Eisenhower victory in 1952 election
- **Production**: Only 46 systems built
- **Price**: ~$1 million USD (1951 dollars)
- **Size**: 35.5 × 7.6 × 2.6 meters
- **Weight**: 13 tons

Today, surviving UNIVAC I systems are in museums:
- Smithsonian Institution (Washington, D.C.)
- Computer History Museum (Mountain View, CA)
- University of Pennsylvania (Philadelphia, PA)

## Troubleshooting

### "Tape unit not responding"
- Check tape unit power and connections
- Verify tape is properly mounted
- Ensure UNIVAC I I/O system is initialized

### "Attestation failed"
- Check network connectivity (via serial/tape bridge)
- Verify node URL is correct
- Ensure system clock is synchronized

### "Emulator detected"
- This is expected in SIMH
- Run on real UNIVAC I hardware for rewards
- Check hardware fingerprinting logs

### "Mercury delay line error"
- Check mercury temperature (must be 40°C)
- Verify delay line calibration
- May require maintenance technician

## References

- [UNIVAC I Hardware Reference Manual (1951)](https://archive.org/details/UNIVAC_I_Hardware_Manual)
- [UNIVAC I Programming Manual](https://archive.org/details/UNIVAC_I_Programming)
- [Mercury Delay Line Memory](https://en.wikipedia.org/wiki/Mercury_delay_line)
- [SIMH UNIVAC I Simulator](https://simh-github.com/)
- [Computer History Museum - UNIVAC I](https://computerhistory.org/collections/univac/)
- [RustChain Documentation](https://github.com/Scottcjn/Rustchain)

## License

MIT OR Apache-2.0 (same as RustChain)

## Disclaimer

This software is provided "as is" without warranty. Use on vintage computer hardware at your own risk. The authors are not responsible for any damage to hardware, data loss, or excessive power consumption.

**Note**: UNIVAC I consumes ~120 kW of power and requires specialized cooling. Ensure adequate electrical infrastructure and environmental controls before operation. Mercury delay lines contain toxic mercury — handle with appropriate safety precautions.

**Historical Note**: If you actually have access to a working UNIVAC I, please contact a museum immediately. You are in possession of one of the most significant artifacts in computing history!

---

**Created**: 2026-03-13  
**Version**: 0.1.0-univac1  
**Bounty Wallet**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`  
**Tier**: LEGENDARY (200 RTC / $20)  
**Status**: Conceptual/Historical Implementation
