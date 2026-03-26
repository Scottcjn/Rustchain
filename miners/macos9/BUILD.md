# Building the Mac OS 9 Miner — Build Instructions

Detailed instructions for compiling `macos9_miner` on Mac OS 9 using
**Metrowerks CodeWarrior Pro 8** or cross-compiling using **Retro68**.

---

## Method 1: CodeWarrior Pro 8 (Native Mac OS 9)

### Prerequisites

1. **Metrowerks CodeWarrior Pro 8** (or CW Pro 7/9)
   - Must include MacOS Lib and MacTCP/OT headers
2. **GUSI 2.x** library (`GUSI.lib`)
   - Available from: <http://www.softwarenetz.de/gusi/>
   - Install to: `CodeWarrior:Metrowerks CodeWarrior:My Projects:GUSI:`
3. **Mac OS 9.2.2** running natively (or in SheepShaver emulator)

### Project Setup

1. **Launch CodeWarrior Pro 8**
2. **File → New Project**
   - Stationery: **Mac OS C++ Stationery** → **MacOS PPC Console App**
   - Save as: `macos9_miner.mcp`

3. **Add Source Files** (Project → Add Files):
   ```
   macos9_miner.c   ← Your miner
   posix_shim.c     ← POSIX shim
   sha256.c         ← SHA-256
   json_min.c       ← JSON parser
   ```

4. **Add GUSI Library**:
   - Project → Add Files → `GUSI.lib`
   - Target: **Mac OS 9 PPC**

5. **Linker Settings** (Edit → Project Settings):
   ```
   Target:           Mac OS 9 PPC
   Processor:        PowerPC
   Linker:           PPC Linker
   
   Libraries:
     MacOS Lib      ← Standard toolbox
     MacTCP Lib     ← Networking
     GUSI Lib       ← BSD sockets
   
   Segment Configuration:
     Code Segment:  .text
     Data Segment:  .data
   ```

6. **Compiler Settings** (Edit → PPC Project Settings):
   ```
   Language:
     C++ Exceptions:  Off (CW Pro 8 doesn't support RTTI well)
     Runtime Type:   MacOS C++ Runtime
     Structured Ex:  Off
   
   PPC:
     Architecture:   G3/G4 (default)
     Native:        Yes
     Vector Unit:    SPE (if targeting G4 with AltiVec)
   ```

### Header Search Paths

Add to **"C/C++" → "Precompile"** in project settings:
```
:MyProjects:GUSI:Headers:
:CodeWarrior:Metrowerks CodeWarrior:Suites:MacOS:Headers:
:CodeWarrior:Metrowerks CodeWarrior:Suites:MacOS:Libraries:
:CodeWarrior:Metrowerks CodeWarrior:Suites:MacOS:TAR:Includes:
```

### Building

1. **Project → Remove Precompiled Headers** (first build)
2. **Project → Build** (or ⌘B)
3. Output: `macos9_miner` (Mach-O PPC executable)

### Troubleshooting CodeWarrior

| Error | Fix |
|-------|-----|
| `undefined: socket` | Add `GUSI.lib` to linker, add `GUSI.h` to sources |
| `undefined: htons` | Include `posix_shim.h` before `GUSI.h` |
| `GUSI conflicts with OpenTransport` | Use `GUSIConfigureSocket`(NULL) before first socket |
| `Out of memory` at link | Set `Segments: .data` size to 0x10000 in linker |

---

## Method 2: Retro68 (Cross-Compiler, Modern macOS/Linux)

### Prerequisites

```bash
# Install Retro68 (macOS)
brew install retro68

# Verify installation
ppc-linux-gcc --version
# Should show something like: powerpc-geeko-linux-gnu-gcc (Retro68)
```

### Environment

Retro68 provides a PowerPC cross-compiler targeting Mac OS 9.
The target is **powerpc-geeko-linux-gnu** (not native Linux PPC — it
generates Mach-O binaries for the classic Mac OS runtime).

### Build with Makefile

A `Makefile.retro68` is included. Usage:

```bash
cd miners/macos9
make -f Makefile.retro68 clean
make -f Makefile.retro68
```

### Manual Build

```bash
PPC_PREFIX=/usr/local/bin/powerpc-geeko-linux-gnu-

$PPC_PREFIX-gcc \
  -nostdinc \
  -I./include-retro68 \
  -fno-exceptions \
  -fno-rtti \
  -O2 \
  -fschedule-insns \
  -mcpu=750 \
  -o macos9_miner \
  macos9_miner.c \
  posix_shim.c \
  sha256.c \
  json_min.c \
  -lm
```

### Retro68 Header Setup

Retro68 ships headers in:
```
/usr/local/share/retro68/macos_developer_headers/
```

Key directories:
```
GlobalSDK/
 Headers/
    CIncludes/        ← Standard C headers
    MacOS/            ← Mac Toolbox headers
    OpenTransport/    ← OT headers
    GUSI/             ← GUSI headers
  Libraries/
    GUSI/
      GUSI.lib
```

---

## Method 3: MPW (Apple Macintosh Programmer's Workshop)

MPW is Apple's historical development environment for classic Mac OS.

### Setup

1. Get MPW from:
   - <https://www.macintoshgarden.org/apps/macintosh-programmers-workshop>
   - Or Apple's historical archive

2. Required MPW tools:
   - `MrC` or `MPW C` compiler
   - `MWLink` linker
   - ` rez` resource compiler

### Build Commands (MPW Shell)

```
# Set paths
Set SrcDir "MyProjects:macos9_miner:"
Set PPCLib ":Libraries:"

# Compile each source file
MrC -model far -proc 750 -o "{SrcDir}macos9_miner.o" "{SrcDir}macos9_miner.c"
MrC -model far -proc 750 -o "{SrcDir}posix_shim.o" "{SrcDir}posix_shim.c"
MrC -model far -proc 750 -o "{SrcDir}sha256.o" "{SrcDir}sha256.c"
MrC -model far -proc 750 -o "{SrcDir}json_min.o" "{SrcDir}json_min.c"

# Link
MWLink PPC
  -model far
  -proc 750
  -seg1addr 0x10000000
  -seg2addr 0x20000000
  -seg5addr 0x50000000
  -o "{SrcDir}macos9_miner"
  "{SrcDir}macos9_miner.o"
  "{SrcDir}posix_shim.o"
  "{SrcDir}sha256.o"
  "{SrcDir}json_min.o"
  ":Libraries:MacOSLib"
  ":Libraries:GUSI:GUSI.lib"
  ":Libraries:MacTCP:MacTCP.lib"
```

### MPW Notes

- MPW uses **far model** by default (data > 32K in bank)
- Always use `-model far` for all compilations
- Use **68K/PPC Mixed Mode** for G4 optimizations
- MPW `MrC` does not support C99 — use ANSI C (C89) only

---

## Installation on Mac OS 9

### Transferring the Executable

**Option A: Local Network (AppleShare)**
```bash
# On modern machine:
scp macos9_miner admin@192.168.1.100:Desktop/
```

**Option B: Floppy Disk / CD-ROM**
- Format a floppy as Mac OS Extended
- Copy the executable
- Transfer to vintage Mac

**Option C: File Exchange (Web)**
- Host on a web server accessible from Mac OS 9
- Download via Netscape Navigator or Internet Explorer

### Running

1. **Double-click** `macos9_miner` in Finder
2. **Control Panels → Monitors** — Set to 256 colors minimum
3. **Control Panels → Memory** — Virtual Memory OFF recommended for mining
4. Terminal output appears in **Mac OS 9 Terminal** (if using MPW shell)

### SheepsShaver (Emulator)

```bash
# SheepShaver command line on modern macOS:
SheepShaver \
  --disk MacOS9_2.img \
  --cdrom /dev/disk2 \
  --ether slirp \
  --keycodes \
  --modelid iMac,1 \
  --config /path/to/sheepshaverPrefs

# Inside SheepShaver:
# 1. Mount the folder containing macos9_miner
# 2. Double-click to run
```

---

## Verifying the Build

### File Type Check (Mac OS)

```
# In Mac OS 9 Terminal or ResEdit:
GetFileInfo macos9_miner

# Expected output:
# type: 'APPL'
# creator: 'CWIE' (CodeWarrior IDE)
# size: ~200-300 KB
```

### Running with Verbose

```bash
./macos9_miner -wallet RTC... -w test-miner -v

# Expected output:
# [*] RustChain Mac OS 9 Miner starting...
# [*] POSIX shim initialized (GUSI 2.x)
# [*] Calibrating timing... done.
# [*] Slot 0 | FP: a3f... | 12450 us
# [+] Slot 0 attested successfully
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Error -1 on slot 0` | Network unreachable | Check Open Transport config |
| `DNS lookup failed` | GUSI OT not initialized | Call `posix_shim_init()` first |
| Crash on `socket()` | GUSI not linked | Add GUSI.lib to project |
| `Segmentation fault` | Stack overflow | Reduce `SHA256_Update` buffer size |
| Miner runs but no attestations | Wrong wallet | Provide valid RTC address with `-wallet` |
| 0 H/s on G3 | Byte order mismatch | Check `htonl`/`ntohl` on PowerPC |

---

## GUSI 2.x Setup Notes

GUSI (Grand Unified Socket Interface) is the core library enabling BSD sockets
on Mac OS 9 via Open Transport. Install it as follows:

1. **Download GUSI 2.3** from your preferred archive
2. Copy `GUSI` folder to `:Extensions:`
3. **Extensions Manager** → Enable `GUSI 2.x`
4. **Control Panels → TCP/IP** → Configure for Ethernet/PPP

For GUSI source (if building from scratch):
```bash
# GUSI source tree
GUSI/
  GUSI.h
  GUSISocket.c
  GUSIConnect.c
  GUSISend.c
  GUSIRecv.c
  GUSIClose.c
  GUSIDNS.c
  GUSI.lib   ← link with this
```
