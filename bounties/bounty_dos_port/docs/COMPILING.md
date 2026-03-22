# Compiling MS-DOS Validator

There are several ways to compile this for MS-DOS:

## Method 1: Cross-compile on modern Linux with Open Watcom

This is the easiest method.

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
# Set up environment
export PATH=/usr/bin/watcom/binl:$PATH
export WATCOM=/usr/bin/watcom

# Build
wmake -f makefile.wat

# Output: rustdos.com (16-bit DOS .COM executable)
```

### Transfer to DOS:

You can use:
- `mtools` to copy directly to a floppy image
- `hdiutil` to create a hard disk image
- `cp` to a FAT partition on a virtual disk

Copy `rustdos.com` to your DOS disk and run it from the DOS prompt.

## Method 2: Native compilation on MS-DOS with Turbo C

If you have Turbo C 2.0 running on DOS:

1. Copy `dos_validator.c` and `dos_validator.h` to your DOS system
2. Open Turbo C
3. Create a new project, add the source file
4. Set memory model to **tiny** (.COM output)
5. Compile -> produces `rustdos.com`

## Method 3: Using GCC with DJGPP (32-bit DOS extender)

This code should also compile with DJGPP for 32-bit protected mode:

```bash
gcc -O2 -o rustdos.exe dos_validator.c
```

But the bounty requires real-mode DOS, so the .COM version is preferred.

## Running on DOS

Once you have `rustdos.com` on your DOS system:

```dos
C> rustdos.com
```

The program will:
1. Detect your CPU
2. Read the BIOS date from ROM
3. Run a long entropy-generating loop (takes a few seconds on older CPUs)
4. Print the results to the console
5. Write `proof_of_antiquity.json` to the current directory

The default wallet address is already filled in, but you can edit it if needed.

## Testing in emulators

Tested working on:
- 86Box with MS-DOS 6.22 on 80486
- PCem with FreeDOS on 8086 XT
- VirtualBox with FreeDOS 1.3

The .COM file is about 8KB - fits easily on a floppy disk.

## Notes

- Real-mode 16-bit DOS requires 8086+ CPU
- Works on all DOS versions from 3.3 through FreeDOS 1.3+
- No extended memory or DOS extender required
- Writes output to current directory on FAT filesystem
