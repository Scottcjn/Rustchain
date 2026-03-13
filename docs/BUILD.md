# Building the PS1 Miner

## Prerequisites

### Option 1: PSn00bSDK (Recommended)

PSn00bSDK is a modern, open-source development kit for PS1.

**Linux:**
```bash
git clone https://github.com/LM-Softland/PSn00bSDK
cd PSn00bSDK
make
sudo make install
```

**Windows:**
```bash
# Download pre-built toolchain from:
# https://github.com/LM-Softland/PSn00bSDK/releases

# Extract to C:\PSn00bSDK
# Add C:\PSn00bSDK\bin to PATH
```

### Option 2: MIPS Cross-Compiler

**Ubuntu/Debian:**
```bash
sudo apt-get install gcc-mips-linux-gnu binutils-mips-linux-gnu
```

**macOS (Homebrew):**
```bash
brew install mips-linux-gnu-binutils
# GCC requires building from source
```

**Windows:**
- Install WSL2 and use Linux instructions, OR
- Download pre-built MIPS toolchain

## Building

### Linux/macOS

```bash
cd ps1_miner
make clean && make
```

Output: `rustchain_ps1_miner.bin`

### Windows (PowerShell)

```powershell
cd ps1_miner
mingw32-make clean
mingw32-make
```

## Testing

### With DuckStation Emulator

1. Install DuckStation: https://www.duckstation.org/
2. Load the binary:
   - File → Run Binary
   - Select `rustchain_ps1_miner.bin`
3. View output in emulator console

### With Real PS1 Hardware

**Method 1: PS1 Link Cable**
```bash
make install
```

**Method 2: Memory Card**
1. Format a memory card with a modded PS1
2. Copy the binary using a file manager (FreeMcBoot)
3. Run from homebrew launcher

**Method 3: CD-R**
1. Create a PS1 executable format
2. Burn to CD-R
3. Run on modded PS1 or dev console

## Troubleshooting

### "mips-linux-gnu-gcc: not found"
Install the MIPS cross-compiler (see Prerequisites).

### "psxgpu.h: not found"
Install PSn00bSDK or set `PSNOOBSDK` environment variable.

### Linker errors
Ensure PS1 SDK libraries are installed:
```bash
# PSn00bSDK includes these
ls $PSNOOBSDK/lib/libpsx*.a
```

### Binary won't run on real hardware
- Ensure you're using a modded PS1 or dev console
- Check that the binary is in correct format
- Try running in emulator first

## File Sizes

| File | Size |
|------|------|
| `rustchain_ps1_miner.bin` | ~50-100 KB |
| Memory card usage | 1 block (8 KB) |

## Next Steps

1. Set up serial connection (see SETUP.md)
2. Run the PC bridge software
3. Test attestation with RustChain node
