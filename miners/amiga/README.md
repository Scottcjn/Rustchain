# RustChain AmigaOS Native Proof-of-Antiquity Miner

Native Proof-of-Antiquity miner implementation for Commodore Amiga systems (m68k / AmigaOS 3.x and PowerPC / AmigaOS 4.x).

## Key Features
- **Silicon Jitter & CIA Timer Drift Analysis**: Probes MOS 8520 / 6526 Complex Interface Adapter (CIA-A / CIA-B) register intervals to calculate microsecond variance against software busyloops, reliably distinguishing physical silicon from hypervisor/UAE cycles.
- **Custom Chipset DMA Register Probing**: Verifies OCS/ECS/AGA custom chipset bus contention (`$DFF000`) and DMA allocation cycles.
- **Kickstart ROM Fingerprinting**: Computes SHA-1 of Kickstart ROM segments and validates against known genuine mask ROMs vs emulator dump signatures.
- **Dual Architecture Support**: Clean C implementation targeting `m68k` (AmigaOS 3.0/3.1/3.9) and PowerPC (AmigaOS 4.x / WarpOS).

## Building & Cross-Compiling

### 1. Cross-compiling with VBCC (AmigaOS 3.x m68k)
```bash
vc +aos68k -O2 -c99 miner_amiga.c -o miner_amiga
```

### 2. Cross-compiling with Bebbo's GCC (m68k-amigaos)
```bash
m68k-amigaos-gcc -O2 -noixemul miner_amiga.c -o miner_amiga
```

### 3. Compiling for AmigaOS 4.x (PPC)
```bash
ppc-amigaos-gcc -O2 miner_amiga.c -o miner_amiga_ppc
```

### 4. POSIX / Emulator Host Test Build
```bash
gcc -Wall -Wextra -O2 miner_amiga.c -o miner_amiga
./miner_amiga [WALLET_ADDRESS]
```

## Usage on Amiga CLI / Shell
```amiga
1> miner_amiga RTC8b1fb717791b0a7b72649342b5c7c7bd822786af
```
