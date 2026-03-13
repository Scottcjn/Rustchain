# Build Guide - RustChain DOS/XT Miner

This guide explains how to build the RustChain miner for IBM PC/XT and compatible systems.

## Quick Start

```batch
cd miners\dos-xt
build.bat
```

If the build succeeds, you'll have `miner.com` ready to run.

## Prerequisites

### 1. Open Watcom C Compiler

The miner is built with Open Watcom, a modern C compiler with DOS support.

**Download**: https://github.com/open-watcom/open-watcom-v2/releases

**Installation** (Windows):
1. Download the latest installer (`owcom-*.exe`)
2. Run installer, choose default options
3. Install to `C:\WATCOM` (recommended)

**Verify Installation**:
```batch
C:\WATCOM\BINW\wcc.exe -v
```

Should output version information.

### 2. mTCP Library (Optional - for Networking)

If you want network functionality (required for actual mining):

**Download**: http://www.brutman.com/mTCP/

**Installation**:
1. Download `mtcpXX.zip` (latest version)
2. Extract to `C:\MTCP`
3. The library files should be in `C:\MTCP\LIB`

**Note**: The current build script compiles without mTCP by default. See "Building with Networking" below.

### 3. DOS Development Environment

You can build in:
- **Native DOS**: Boot into MS-DOS or PC DOS
- **DOSBox**: Emulated DOS environment
- **Windows Command Prompt**: Cross-compile for DOS
- **WSL/ Linux**: Cross-compile with Watcom

**Recommended**: Build in Windows Command Prompt for easiest setup.

## Environment Setup

### Windows Command Prompt

```batch
REM Set Watcom environment variables
SET WATCOM=C:\WATCOM
SET PATH=%WATCOM%\BINW;%PATH%
SET INCLUDE=%WATCOM%\H
SET LIB=%WATCOM%\LIB286;%WATCOM%\LIB286\DOS
```

### DOSBox

```batch
# In DOSBox configuration (dosbox.conf):
[autoexec]
MOUNT C C:\
C:
SET WATCOM=C:\WATCOM
SET PATH=%WATCOM%\BINW;%PATH%
```

### Makefile (Alternative)

For Make users, a Makefile is provided:

```makefile
# Build
make

# Clean
make clean

# Build with networking
make MTCP=1
```

## Build Process

### Step 1: Navigate to Source Directory

```batch
cd rustchain\miners\dos-xt
```

### Step 2: Run Build Script

```batch
build.bat
```

This will:
1. Check Watcom installation
2. Set up environment variables
3. Compile all source files
4. Link into `miner.com`
5. Clean up object files

### Step 3: Verify Build

```batch
dir miner.com
```

You should see a file around 20-40 KB in size.

### Step 4: Test Run

```batch
miner.com -h
```

Should display help information.

## Build Options

### Memory Models

The miner uses **Tiny Memory Model** (-ml) which:
- Combines code and data in one 64 KB segment
- Produces .COM files (smaller, faster loading)
- Maximum size: 64 KB total

Other models (not used):
- **Small** (-ms): Separate code/data, each < 64 KB
- **Medium** (-mm): Code > 64 KB, data < 64 KB
- **Compact** (-mc): Code < 64 KB, data > 64 KB
- **Large** (-ml): Both > 64 KB

### Optimization Levels

Current build uses `-ox` (maximum optimization):

```batch
wcc -ml -bt=dos -ox -s source.c
```

Options:
- `-ox`: Maximum optimization
- `-ox+`: Aggressive optimization (may increase size)
- `-s`: Remove stack overflow check (saves space)
- `-zq`: Quiet mode (less output)

For debugging, use:
```batch
wcc -ml -bt=dos -d2 -v source.c
```
- `-d2`: Debug information
- `-v`: Verbose output

## Building with Networking

### Option 1: Using build_mtcp.bat

```batch
build_mtcp.bat
```

This script:
1. Checks for mTCP installation
2. Includes mTCP headers and libraries
3. Links against mTCP

### Option 2: Manual Build with mTCP

```batch
REM Set mTCP paths
SET MTCP=C:\MTCP
SET INCLUDE=%INCLUDE%;%MTCP%\INC
SET LIB=%LIB%;%MTCP%\LIB

REM Compile with mTCP
wcc -ml -bt=dos -ox -s -I%MTCP%\INC src\network.c

REM Link with mTCP libraries
wlink system dos ^
    file main.obj ^
    file hw_xt.obj ^
    file pit.obj ^
    file attest.obj ^
    file network.obj ^
    library %MTCP%\LIB\mtcp.lib ^
    name miner.com
```

### Option 3: WATTCP Alternative

If you prefer WATTCP:

```batch
REM Download WATTCP from: http://www.wattcp.com/
SET WATTCP=C:\WATTCP

wcc -ml -bt=dos -ox -s -I%WATTCP%\INC src\network.c

wlink system dos ^
    file main.obj ^
    file hw_xt.obj ^
    file pit.obj ^
    file attest.obj ^
    file network.obj ^
    library %WATTCP%\LIB\wattcp.lib ^
    name miner.com
```

## Troubleshooting

### "wcc.exe not found"

**Problem**: Watcom compiler not in PATH

**Solution**:
```batch
SET PATH=C:\WATCOM\BINW;%PATH%
```

### "Cannot open include file"

**Problem**: INCLUDE path not set correctly

**Solution**:
```batch
SET INCLUDE=C:\WATCOM\H
```

### "Unresolved external"

**Problem**: Missing library during linking

**Solution**:
- Check LIB environment variable
- Ensure all .obj files are present
- For networking, verify mTCP/WATTCP library is linked

### "Out of memory"

**Problem**: Not enough conventional memory

**Solution**:
- Build in Windows or DOSBox (more memory available)
- Use EMM386 to free conventional memory
- Remove TSRs and device drivers

### Linker Errors

**Common Issues**:

1. **Duplicate symbols**:
   ```
   Error! E2028: _main is defined more than once
   ```
   **Fix**: Ensure each function is defined only once.

2. **Missing symbols**:
   ```
   Error! E2029: '_inp' not defined
   ```
   **Fix**: Include correct headers (`<dos.h>` for inp/outp).

3. **Stack overflow**:
   ```
   Warning! W4015: Stack size too small
   ```
   **Fix**: Increase stack size in linker options.

## Testing the Build

### DOSBox Testing

1. Mount directory in DOSBox:
   ```
   mount c c:\users\yourname\.openclaw-autoclaw\workspace\rustchain\miners\dos-xt
   c:
   ```

2. Run miner:
   ```
   miner.com -h
   ```

3. Test with wallet:
   ```
   miner.com -w RTCtest123456789
   ```

### Real Hardware Testing

1. Copy `miner.com` to floppy disk or hard drive
2. Boot IBM PC/XT with DOS
3. Run:
   ```
   A:\>miner.com -w RTCyourwallet
   ```

### Automated Testing

```batch
@echo off
REM test.bat - Automated build test

echo Building...
build.bat
if errorlevel 1 exit /b 1

echo Testing help...
miner.com -h > nul
if errorlevel 1 exit /b 1

echo Testing with dummy wallet...
echo N | miner.com -w RTCtest123456789 > test_output.txt

echo Checking output...
find "IBM PC/XT" test_output.txt > nul
if errorlevel 1 (
    echo Test FAILED
    exit /b 1
)

echo Test PASSED
del test_output.txt
exit /b 0
```

## Build Artifacts

After successful build:

```
miners/dos-xt/
├── miner.com          # Main executable (20-40 KB)
├── src/               # Source files
├── build.bat          # Build script
├── build_mtcp.bat     # Build with networking
├── README.md          # User documentation
└── BUILD.md           # This file
```

## Distribution

### Creating Release Package

```batch
@echo off
REM package_release.bat

SET VERSION=0.1.0
SET RELEASE_DIR=release\v%VERSION%

mkdir %RELEASE_DIR%
copy miner.com %RELEASE_DIR%
copy README.md %RELEASE_DIR%
copy build.bat %RELEASE_DIR%
copy ..\..\docs\LICENSE %RELEASE_DIR%

REM Create ZIP
zip -r release\v%VERSION%\rustchain-dos-xt-v%VERSION%.zip %RELEASE_DIR%

echo Release package created: release\v%VERSION%\rustchain-dos-xt-v%VERSION%.zip
```

### File Sizes

Expected sizes:
- `miner.com`: 20-40 KB (without networking)
- `miner.com`: 40-60 KB (with mTCP)
- Source code: ~100 KB total
- Documentation: ~50 KB

## Performance Tuning

### Reduce Size

```batch
# Use smaller runtime library
wcc -ml -bt=dos -ox -s -zq -0 source.c

# Link with smaller libraries
wlink system dos ... option stub=256
```

### Increase Speed

```batch
# Aggressive optimization
wcc -ml -bt=dos -ox+ -s -zq source.c

# Unroll loops (manual in source)
```

### Memory Optimization

```c
/* Use near pointers for small data */
char near buffer[256];

/* Use far pointers for large data */
char far large_buffer[4096];

/* Overlay support for large code */
#pragma overlay(myfunc)
void myfunc(void) { ... }
```

## References

- [Open Watcom User's Guide](https://open-watcom.github.io/)
- [mTCP Programmer's Guide](http://www.brutman.com/mTCP/)
- [IBM PC/XT Technical Reference](https://archive.org/details/IBM_PC_XT_Technical_Reference)
- [DOS Memory Models](https://www.cs.virginia.edu/~evans/cs216/guides/memory.html)

---

**Last Updated**: 2026-03-13  
**Build Version**: 0.1.0-xt
