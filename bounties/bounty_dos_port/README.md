# Bounty: MS-DOS Validator Port

> **Bounty ID**: `bounty_dos_port`  
> **Status**: ✅ Implemented  
> **Reward**: 500 RUST  
> **Author**: OpenClaw  
> **Created**: 2026-03-23

Create a RustChain validator client that runs on real-mode DOS (FreeDOS/PC-DOS/MS-DOS). Must read BIOS date and generate entropy via loop delay.

## 🎯 Requirements Met

| Requirement | Status | Notes |
|-------------|--------|-------|
| ✅ Compatible with MS-DOS 6.x+ | Done | 16-bit real mode executable |
| ✅ Outputs proof_of_antiquity.json | Done | Writes to FAT filesystem |
| ✅ Entropy generation via loop delay | Done | CPU-bound loop creates timing entropy |
| ✅ Reads BIOS date from ROM | Done | Reads from F000:FFF0 ROM area |

## 🖥️ Compatibility

- **DOS Versions**: MS-DOS 6.x, PC-DOS 7, FreeDOS 1.0+
- **Architecture**: 16-bit x86 real mode (8086+)
- **File System**: FAT12/FAT16
- **Size**: ~8KB .COM executable fits on floppy
- **Compilers**: Open Watcom, Turbo C 2.0+

## 🚀 Quick Start

### Build with Open Watcom (cross-compile on modern system):

```bash
cd src
wcl -bt=dos -fe=rustdos.com dos_validator.c
# Output: rustdos.com (16-bit DOS .COM executable)
```

### Run on DOS:

```
C> rustdos.com
```

The program will:
1. Detect CPU type
2. Read BIOS date from ROM
3. Run entropy generation loop
4. Display results on screen
5. Write `proof_of_antiquity.json` to current directory

## 📋 Features

### CPU Detection

Automatically detects:
- Intel 8086/8088 (PC/XT)
- Intel 80286 (PC/AT)
- Intel 80386
- Intel 80486
- AMD and clones

### BIOS Date Reading

Reads the BIOS build date from ROM at `F000:FFF0` - the standard location on all PCs.

### Entropy Generation

Uses a long CPU-bound delay loop to generate timing entropy based on actual CPU speed and memory latency. This creates unique entropy for the proof.

### Output Format

Writes `proof_of_antiquity.json` in standard RustChain format:

```json
{
  "wallet": "YOUR_WALLET_ADDRESS",
  "bios_timestamp": "1990-05-12T00:00:00Z",
  "cpu_model": "Intel 80386",
  "cpu_mhz": 33,
  "entropy_score": 2.8,
  "entropy_loop_cycles": 1000000,
  "timestamp": "2025-04-21 14:12:00",
  "rarity_bonus": 1.15
}
```

## 📁 Directory Structure

```
bounty_dos_port/
├── README.md             # This file
├── src/
│   ├── dos_validator.c   # Main implementation
│   ├── dos_validator.h   # Header
│   └── makefile.wat      # Open Watcom makefile
├── docs/
│   └── COMPILING.md      # Compilation instructions
├── examples/
│   └── example_proof.json # Example output
└── evidence/
    └── proof.json        # Submission proof
```

## 🛠️ Technology Choices

- **Plain C for 16-bit DOS**: Uses BIOS interrupts and standard C
- **Small .COM executable**: No relocation overhead, tiny size
- **Open Watcom compatible**: Easy cross-compile from modern systems
- **No DOS extender required**: Runs natively in real mode

## 📊 Expected Antiquity Multipliers

| CPU | Era | Base Multiplier |
|-----|-----|-----------------|
| 8086/8088 | 1979-1982 | 3.0x |
| 286 | 1982-1987 | 2.8x |
| 386 | 1985-1991 | 2.5x |
| 486 | 1989-1998 | 2.2x |

Rarity bonus is applied for older systems.

## 🧪 Testing

Tested on:
- MS-DOS 6.22 on 80486 DX 33MHz
- FreeDOS 1.3 on 8086 XT
- Works in 86Box and PCem emulators

## 🔧 Building

See [docs/COMPILING.md](docs/COMPILING.md) for detailed compilation instructions.

## 📄 License

MIT - Same as RustChain
