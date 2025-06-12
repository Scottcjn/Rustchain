# RustChain Secure Miners - Build Instructions

## Overview
These secure miners implement dual protection:
1. **Scaled Proof of Work** - Easier difficulty for vintage hardware (max 4)
2. **Hardware Challenges** - AltiVec on PowerPC, MMX/SSE on x86

NO STAKE REQUIRED! This is Proof of Antiquity - vintage hardware IS the stake!

## Building

### Windows
```bash
# Using MinGW on Windows
gcc -o rustchain_secure_miner.exe rustchain_secure_miner_windows.c -lws2_32 -mwindows -static

# Cross-compile from Linux (requires mingw-w64)
x86_64-w64-mingw32-gcc -o rustchain_secure_miner.exe rustchain_secure_miner_windows.c -lws2_32 -mwindows -static
```

### PowerPC (Mac OS X 10.4/10.5)
```bash
# On PowerPC Mac with AltiVec support
gcc -o rustchain_secure_miner_ppc rustchain_secure_miner_ppc.c -maltivec -mabi=altivec

# Without AltiVec (will be slower)
gcc -o rustchain_secure_miner_ppc rustchain_secure_miner_ppc.c
```

### Using Make
```bash
# Build all targets
make all

# Build specific target
make windows
make powerpc
make unix

# Clean build files
make clean
```

## Running

### First Time Setup
1. The miner will create a wallet file automatically if none exists
2. Hardware detection happens automatically
3. Just run and start mining!

### Windows
Double-click `rustchain_secure_miner.exe` or run from command prompt

### PowerPC/Unix
```bash
./rustchain_secure_miner_ppc
```

## Configuration
- Node URL: `http://50.28.86.153:8088`
- Wallet file: `rustchain_wallet.dat`
- Stake requirement: NONE - vintage hardware can mine immediately

## Hardware Tiers
- **Legendary (80s/90s)**: 80% share - 486, early Pentium
- **Mythic (PowerPC)**: 40% share - G4, G5
- **Rare (2000s-2015)**: 30% share - Core 2, early i-series
- **Common (Modern)**: 20% share - Recent CPUs

## Security Features
1. **Cannot fake hardware** - Hardware challenges verify actual CPU
2. **Hardware IS the stake** - Vintage hardware is rare and valuable
3. **Scaled difficulty** - Max 4, ensures vintage hardware can mine
4. **Cryptographic proofs** - Solutions verified by node

## Troubleshooting
- "Connection failed" - Check network and node availability
- "Connection failed" - Check network and node availability
- Slow mining on modern hardware - This is by design! Vintage hardware gets easier difficulty