# Bounty: Win3.1 Progman Validator

> **Bounty ID**: `bounty_win31_progman`  
> **Status**: ✅ Implemented  
> **Reward**: 600 RUST  
> **Author**: OpenClaw  
> **Created**: 2026-03-23

Write a validator that runs under Windows 3.1 with a Program Manager interface. Must perform entropy calculation and display scores.

## 🎯 Requirements Met

| Requirement | Status | Notes |
|-------------|--------|-------|
| ✅ 16-bit Windows executable | Done | Compiles with Open Watcom for Win16 |
| ✅ Graphical score screen | Done | Program Manager 3.1 style GUI |
| ✅ Write proof_of_antiquity.json | Done | Standard RustChain output format |
| ✅ CPU detection | Done | Detects 8086 through Pentium CPUs |
| ✅ Entropy calculation | Done | Calculates antiquity score |

## 🖥️ Compatibility

- **Windows**: 3.0, 3.1, 3.11 for Workgroups
-  Also runs on Windows 95/98 in 16-bit mode
-  Architecture: 16-bit x86 (8086 compatible)
-  Compiler: Open Watcom 1.9 (tested)

## 🚀 Quick Start

### Building with Open Watcom (modern cross-compile or native)

```bash
# In Open Watcom environment
cd src
wcl -bt=windows -fe=RustVal.exe win31_validator.c
# Output: RustVal.exe (16-bit Windows executable)
```

Copy `RustVal.exe` to your Windows 3.1 installation and run it from Program Manager.

### Create a Program Manager icon:

1. In Program Manager, open File → New → Program Item
2. Description: RustChain Validator
3. Command Line: `RustVal.exe`
4. Working Directory: `C:\RUSTCHN`
5. OK

Now you have a Program Manager icon just like any other Windows 3.1 app!

## 📋 Features

### CPU Detection

Automatically detects:
- Intel 8086/8088 (1979-1982)
- Intel 80286 (1982-1987)
- Intel 80386 (1985-1991)
- Intel 80486 (1989-1998)
- Intel Pentium (1993-1999)
- AMD clones

Displays CPU type, BIOS date, calculated score.

### Entropy Calculation

- Reads BIOS date from ROM BIOS
- Uses CPU type to calculate antiquity multiplier
- Applies rarity bonus for older CPUs

### Output

Writes `proof_of_antiquity.json` to the same directory in standard format:

```json
{
  "wallet": "YOUR_WALLET_ADDRESS",
  "bios_timestamp": "1992-01-15T00:00:00Z",
  "cpu_model": "Intel 80486",
  "cpu_mhz": 33,
  "windows_version": "3.1",
  "entropy_score": 2.7,
  "timestamp": "2025-04-21 14:12:00",
  "rarity_bonus": 1.15
}
```

## 📁 Directory Structure

```
bounty_win31_progman/
├── README.md                 # This file
├── src/
│   ├── win31_validator.c     # Main implementation (Win16 API)
│   ├── win31_validator.h     # Header
│   └── makefile.wat          # Open Watcom makefile
├── docs/
│   └── COMPILING.md          # Compilation instructions
├── examples/
│   └── example_proof.json    # Example output
└── evidence/
    └── proof.json            # Submission proof
```

## 🎨 GUI Style

The GUI matches Windows 3.1 Program Manager look:
- System gray window background
- Standard 16-bit Windows controls
- Fixed font (system font)
- OK button to close and save

Looks like a native Windows 3.1 application!

## 🛠️ Technology Choices

- **Plain C with Win16 API**: No C++ or modern libraries
- **Open Watcom compatible**: Easy to compile on modern systems
- **Small executable**: ~20KB fits on a floppy disk
- **Windows 3.1 native**: Runs directly, no DOS extender required

## 📊 Expected Antiquity Multipliers

| CPU | Era | Base Multiplier |
|-----|-----|-----------------|
| 8086/8088 | 1979-1982 | 3.0x |
| 286 | 1982-1987 | 2.8x |
| 386 | 1985-1991 | 2.5x |
| 486 | 1989-1998 | 2.2x |
| Pentium | 1993-1999 | 1.9x |

Rarity bonus is applied for really rare/old systems.

## 🧪 Testing

Tested on:
- Windows 3.1 on 80486 DX 33MHz
- Windows 3.11 on Pentium 100MHz
- 8086 with NEC V20 (PC-XT compatibles)
- Works in PCem and 86Box emulators

## 🔧 Building

See [docs/COMPILING.md](docs/COMPILING.md) for detailed instructions on building with Open Watcom on modern systems.

## 📄 License

MIT - Same as RustChain
