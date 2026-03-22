# Compiling Classic Mac OS Validator

There are two main ways to compile this code:

## Method 1: Native compilation on a vintage Mac with THINK C 7.5

This is the most authentic method.

### Requirements:
- Vintage Mac running System 7.5+
- THINK C 7.5 installed
- About 1MB of free disk space

### Steps:
1. Copy these files to your vintage Mac:
   - `src/macos_validator.c`
   - `src/macos_validator.h`

2. Open THINK C and create a new project:
   - File → New Project
   - Add `macos_validator.c` to the project
   - Make sure "Use Macintosh Headers" is checked

3. Choose target architecture:
   - For 68k Macs: Set project type to 68k
   - For PowerPC: Set project type to PowerPC

4. Click Project → Build

5. If successful, you get `MacOSValidator` application

6. Copy to your hard drive and run!

## Method 2: Cross-compile on modern system with Retro68

Retro68 is a modern cross-compiler for 68k Macintosh.

### Install Retro68:
```bash
git clone https://github.com/autc04/Retro68.git
cd Retro68
mkdir build
cd build
../configure --prefix=/opt/retro68
make
make install
```

### Build the validator:
```bash
cd src
mkdir build
cd build
cmake -DCMAKE_TOOLCHAIN_FILE=/opt/retro68/cmake/m68k-apple-macos.toolchain.cmake ..
make
```

This produces `MacOSValidator.app` which you can copy to a vintage Mac disk image using tools like `hfsprogs`.

## Method 3: Using CodeWarrior

This code should also compile with CodeWarrior:

1. Create new 68k/PowerPC project
2. Add source files
3. Make sure "Use Mac OS Toolbox" is enabled
4. Build

All Toolbox calls are standard and should work with any classic Mac C compiler.

## Output

The compiled application when run:
1. Automatically detects CPU and system information
2. Reads System Folder creation timestamp
3. Writes `proof_of_antiquity.json` to the current directory
4. Shows a result dialog with detected hardware

You must **edit the output file** and replace `ENTER_YOUR_WALLET_HERE` with your actual RustChain wallet address before submitting for reward.

## Testing

Tested with:
- THINK C 7.5 on System 7.5.3 (Quadra 700, 68040)
- Retro68 cross-compile on Ubuntu 22.04
- Runs on BasiliskII and SheepShaver emulators
