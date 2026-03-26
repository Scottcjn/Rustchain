# RustChain Mac OS 9 Miner

A POSIX-compatible RustChain miner client for **Mac OS 9.2.2 on PowerPC G3/G4**,
using a lightweight POSIX shim layer via GUSI 2.x (Grand Unified Socket Interface).

## 🏆 Rewards

Mac OS 9 on PowerPC hardware earns the **retro x86 equivalent multiplier (1.4x)**
for RustChain proof-of-antiquity mining attestations.

## 📋 Requirements

### Target Hardware
- Power Mac G3 (233–400 MHz)
- Power Mac G4 (AGP, 350 MHz – 1.42 GHz)
- iMac G3 (233–700 MHz)
- iBook G3 (300–600 MHz)
- PowerBook G3/G4 (All models)

### Software
- **Mac OS 9.2.2** (Classic environment, not OS X)
- **CodeWarrior Pro 8** or **Retro68** toolchain
- **GUSI 2.x** (Grand Unified Socket Interface)
- **MacTCP** / **Open Transport** (for networking)

## 📁 Files

| File | Description |
|------|-------------|
| `macos9_miner.c` | Main miner client — attestation loop, HTTP, timing |
| `posix_shim.h` | POSIX API header — BSD sockets, time, memory |
| `posix_shim.c` | POSIX shim implementation via GUSI 2.x + Toolbox |
| `sha256.h` | SHA-256 public domain implementation header |
| `sha256.c` | SHA-256 implementation (no OpenSSL) |
| `json_min.h` | Minimal JSON parser header |
| `json_min.c` | Minimal JSON parser implementation |
| `BUILD.md` | Detailed build instructions for CodeWarrior and Retro68 |
| `Makefile` | Retro68 build makefile |

## ⚙️ Quick Build (Retro68)

```bash
# Install Retro68 (https://github.com/autc0930/Retro68)
brew install retro68  # macOS / Linux

# Navigate to this directory
cd miners/macos9

# Build
make -f Makefile.retro68

# Run on Mac OS 9 (SheepShaver/QEMU):
#   Copy 'macos9_miner' to your Mac OS 9 system and execute
```

## ⚙️ Build (CodeWarrior Pro 8)

1. Create new **Mac OS C++ Stationery** project
2. Add source files: `macos9_miner.c`, `posix_shim.c`, `sha256.c`, `json_min.c`
3. Add GUSI 2.x import library (`GUSI.lib`)
4. Add **MacOS Lib** and **MacTCP Lib** to project
5. Set **Target** → **Mac OS 9**
6. Set **Processor** → **PowerPC**
7. Build → **Debug** or **Release**

## 🚀 Usage

```bash
# Basic usage (requires wallet)
./macos9_miner -wallet RTC... -w my-mac-miner

# Verbose mode
./macos9_miner -wallet RTC... -w my-mac-miner -v

# Custom node
./macos9_miner -wallet RTC... -h rustchain.org -p 443
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-wallet <addr>` | RTC wallet address for rewards | *(required)* |
| `-w <id>` | Worker/miner identifier | `macos9-ppc-miner-v1` |
| `-h <host>` | RustChain node hostname | `rustchain.org` |
| `-p <port>` | RustChain node port | `443` |
| `-v` | Verbose output | off |

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────────┐
│              macos9_miner (Main Loop)                  │
│  ┌──────────────┐ ┌────────────┐ ┌──────────────────┐  │
│  │ TimingProof  │ │ AttestReq  │ │ HTTP POST Client │  │
│  │ (PPC TB Reg) │ │ Builder    │ │ (GUSI Sockets)   │  │
│  └──────────────┘ └────────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    POSIX Shim Layer                      │
│  ┌──────────────┐ ┌────────────┐ ┌──────────────────┐  │
│  │  BSD Sockets │ │  time/     │ │  malloc/free     │  │
│  │  (GUSI 2.x)  │ │  Microsec  │ │  (CW StdLib)     │  │
│  └──────────────┘ └────────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────────────┤
│              Mac OS 9 / Open Transport                   │
│  ┌──────────────┐ ┌────────────┐ ┌──────────────────┐  │
│  │   MacTCP     │ │  Toolbox   │ │  Thread Manager  │  │
│  │  (OT API)    │ │  Traps     │ │  (Coop. Threads) │  │
│  └──────────────┘ └────────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 🧩 POSIX Shim Details

The POSIX shim provides BSD-compatible APIs on Mac OS 9:

| POSIX API | Mac OS 9 Implementation |
|-----------|------------------------|
| `socket()` | GUSISocket → Open Transport |
| `connect()` | GUSIConnect → OT |
| `send()` / `recv()` | GUSISend / GUSIRecv |
| `gettimeofday()` | Microseconds Toolbox trap |
| `malloc()` / `free()` | NewPtr / DisposPtr |
| `gethostbyname()` | OTInetNameToAddress |

## 📊 Expected Performance

| Hardware | Estimated Hash Rate | Notes |
|----------|--------------------:|-------|
| Power Mac G3 400MHz | ~15 H/s | Classic 68k-class PPC |
| Power Mac G4 450MHz | ~30 H/s | AGP graphics model |
| Power Mac G4 1.0GHz | ~80 H/s | G4 with Velocity Engine |
| iBook G3 500MHz | ~20 H/s | Laptop, power-efficient |

*Hash rates are estimates based on SHA-256 compression round performance.
Actual rates depend on system load and Mac OS version.*

## 🧪 Testing

### SheepShaver (Emulator)
```bash
# Build for Mac OS 9 in SheepShaver
./macos9_miner -wallet RTC... -w test-miner -v
```

### QEMU with Mac OS 9
```bash
# Run the miner in QEMU-hosted Mac OS 9
./macos9_miner -wallet RTC... -w qemu-test -v
```

## 📜 Prior Art

- **GUSI 2.x** — Grand Unified Socket Interface, BSD sockets on Mac OS
  <https://www.softausland.net/info/usi/>
- **Retro68** — Modern cross-compiler for classic Mac OS
  <https://github.com/autc0930/Retro68>
- **A/UX** — Apple's Unix for 68K Macs (proof vintage Apple hardware runs POSIX)
- **MkLinux** — Microkernel Linux for PowerPC Macs

## ⚠️ Notes

- This is a **demonstration/educational** implementation.
- For production mining on vintage hardware, consider the PowerPC G4 miner
  in `miners/ppc/g4/` which runs under OS X or Linux.
- Mac OS 9 has cooperative threading — no preemptive multitasking.
- Open Transport networking requires Mac OS 9.1 or later.

## 📄 License

Same as the RustChain project (see repository root).
