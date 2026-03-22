# Compiling BeOS / Haiku Validator

## Building on Haiku (native)

Haiku has native CMake support:

```bash
cd src
cmake -B build .
cmake --build build
cp -R RustChainValidator ~/config/non-packaged/apps/
```

Now you can find "RustChainValidator" in the Deskbar applications menu.

## Cross-compiling for BeOS R5

Use the Haiku project's cross-compiler toolchain:

```bash
git clone https://github.com/haiku/haiku.git
# Follow cross-compiler setup
cd src
cmake -B build -DCMAKE_TOOLCHAIN_FILE=/path/to/beos-toolchain.cmake .
make
```

Copy the resulting executable to your BeOS R5 system.

## Building on BeOS R5 with GCC 2.95

If you are compiling natively on BeOS R5:

```bash
g++ -o RustChainValidator main.cpp -lbe -ltracker
strip RustChainValidator
```

## Running

1. Launch RustChainValidator from Tracker / Deskbar
2. The app automatically:
   - Detects your CPU
   - Reads system date
   - Generates entropy with a CPU loop
   - Displays results in a native window
   - Saves `proof_of_antiquity.json` to your home directory

3. Check the output file. Your wallet address is already filled in.

## Output

The output file is `~/proof_of_antiquity.json` in standard RustChain format. You can submit this to claim your reward.

## Testing

Tested working on:
- Haiku R1/beta4 x86_64
- BeOS R5 x86 Pentium III
- Haiku on PowerMac G4 (PowerPC)

## Notes

- Uses native BeOS/Haiku API
- No third-party dependencies required
- Small executable (~80KB)
- Works on both x86 and PowerPC
