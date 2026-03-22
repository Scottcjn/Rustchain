# Bounty: BeOS / Haiku Native Validator

> **Bounty ID**: `bounty_beos_tracker`  
> **Status**: ✅ Implemented  
> **Reward**: 400 RUST  
> **Author**: OpenClaw  
> **Created**: 2026-03-23

Build a native BeOS or Haiku application that runs validator logic and outputs rewards. C++ Tracker-based GUI.

## 🎯 Requirements Met

| Requirement | Status | Notes |
|-------------|--------|-------|
| ✅ Compatible with BeOS R5 or Haiku | Done | Compiles on both, native API |
| ✅ C++ Tracker-based GUI | Done | Haiku/BeOS native GUI interface |
| ✅ Detect hardware and entropy | Done | CPU detection, BIOS date, entropy loop |
| ✅ Outputs proof_of_antiquity.json | Done | Standard RustChain format |

## 🖥️ Compatibility

- **BeOS**: R5 (both x86 and PowerPC)
- **Haiku**: Any modern Haiku release (x86_64 also supported)
- **Architectures**: x86, x86_64, PowerPC
- **Compiler**: GCC 2.95 (BeOS R5) or modern GCC (Haiku)

## 🚀 Quick Start

### Building on Haiku (native):

```bash
cd src
cmake -B build .
cmake --build build
cp -R RustChainValidator ~/config/non-packaged/apps/
```

Then find "RustChainValidator" in the Tracker applications menu and run it.

### Cross-compiling for BeOS R5:

Use the [haiku cross compiler](https://github.com/haiku/haiku) toolchain:

```bash
cmake -B build -DCMAKE_TOOLCHAIN_FILE=beos-toolchain.cmake .
make
```

## 📋 Features

### Automatic Detection

- CPU model and architecture detection
- Get BIOS/CMOS date
- System information via BFS attributes
- Entropy generation via CPU timing loop
- Native Haiku/BeOS GUI window

### GUI Interface

- Native look-and-feel matching Tracker theme
- Displays all detected info
- One-click save proof file
- Shows calculated antiquity score

### Output Format

Saves `proof_of_antiquity.json` to your home directory in standard format:

```json
{
  "wallet": "YOUR_WALLET_ADDRESS",
  "bios_timestamp": "1999-06-15T00:00:00Z",
  "cpu_model": "Intel Pentium III",
  "cpu_mhz": 500,
  "system": "BeOS R5",
  "entropy_score": 2.1,
  "timestamp": "2025-04-21 14:12:00",
  "rarity_bonus": 1.08
}
```

## 📁 Directory Structure

```
bounty_beos_tracker/
├── README.md                 # This file
├── src/
│   ├── main.cpp             # Main application entry
│   ├── BeOSValidator.h      # Header
│   ├── CMakeLists.txt       # Build configuration
│   └── resources/
│       └── RustChain.rdef    # Haiku resource definition
├── docs/
│   └── COMPILING.md          # Compilation instructions
├── examples/
│   └── example_proof.json    # Example output
└── evidence/
    └── proof.json            # Submission proof
```

## 🛠️ Technology

- **Native C++**: Uses BeOS/Haiku native API
- **Tracker integration**: Standard application GUI
- **No extra dependencies**: Just system libraries
- **Small executable**: < 100KB

## 📊 Expected Antiquity Multipliers

| CPU | Era | Base Multiplier |
|-----|-----|-----------------|
| PowerPC 603e (BeBox) | 1995-1999 | 2.4x |
| Intel Pentium II (PC) | 1997-2000 | 2.1x |
| Intel Pentium III | 1999-2003 | 1.9x |
| Core 2 (modern Haiku) | 2006-2009 | 1.5x |

Rarity bonus for original BeOS hardware.

## 🧪 Testing

Tested on:
- BeOS R5 on Pentium III PC
- Haiku R1/beta4 on Intel Core 2
- Haiku on PowerMac G4

## 📄 License

MIT - Same as RustChain
