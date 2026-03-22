# Compiling Windows 3.1 Validator

There are two main ways to compile this code for 16-bit Windows:

## Method 1: Cross-compile on modern Linux with Open Watcom

This is the easiest method for modern systems.

### Install Open Watcom:

```bash
# Ubuntu/Debian:
sudo apt install openwatcom

# Or build from source:
# https://github.com/open-watcom/open-watcom-v2
```

### Build:

```bash
cd src
# Set up Open Watcom environment (if not in path)
export PATH=/usr/bin/watcom/binl:$PATH
export WATCOM=/usr/bin/watcom

# Build
wmake -f makefile.wat

# Output: RustVal.exe (16-bit Windows executable)
```

### Transfer to Windows 3.1:

You can use:
- `hfsprogs` to copy to a hard disk image
- `rawrite` to put on a floppy disk image
- Transfer via serial/null modem from modern PC to vintage

## Method 2: Native compilation on Windows 3.1

If you have a working Windows 3.1 development environment:

1. Copy these files to your Windows 3.1 machine:
   - `win31_validator.c`
   - `win31_validator.h`
   - `makefile.wat`

2. Open the Watcom IDE or use wmake:
   ```
   wmake -f makefile.wat
   ```

3. You get `RustVal.exe`

## Method 3: Microsoft Visual C++ 1.52 (16-bit)

This code should also compile with Microsoft Visual C++ 1.52:

```
cl /ALwin win31_validator.c
```

The `ALwin` means large memory model for Windows.

## Testing

You can test in emulators:

### 86Box / PCem

1. Install Windows 3.1 in the emulator
2. Copy `RustVal.exe` to the C: drive
3. In Program Manager, File → New → Program Item
4. Add the icon and run it

Expected output:
- A window opens showing detected CPU
- BIOS date from ROM
- Calculated score
- Saves `proof_of_antiquity.json`

You must edit the output file and replace `ENTER_YOUR_WALLET_HERE` with your actual RustChain wallet address.

## Notes

- This is a 16-bit x86 executable, requires 8086+ CPU
- Works on Windows 3.0, 3.1, 3.11, and also Windows 95/98
- The executable is small (~20KB) and fits on a floppy disk
- Uses only Win16 API calls, no 32-bit extensions
