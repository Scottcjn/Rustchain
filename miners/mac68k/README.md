# RustChain Macintosh 68K Proof-of-Antiquity Native Miner

Native Proof-of-Antiquity miner implementation for classic Macintosh systems running System 7.x through Mac OS 8.1 (Motorola 68000, 68020, 68030, 68040).

## Anti-Spoof & Hardware Attestation Mechanisms
1. **Synertek/Rockwell 6522 VIA Timer Drift Profiling**:
   - Samples micro-intervals of the VIA timer against computational busyloops to evaluate hardware silicon jitter variance ($\sigma^2$).
   - Basilisk II, Mini vMac, and unthrottled host virtualization collapse jitter variance to zero, instantly flagging emulation and forcing multiplier to 0.0x.
2. **68K Instruction Pipeline Hazard Profiling**:
   - Executes multi-step non-linear arithmetic and bitwise cascades that trigger microarchitectural execution stalls on physical 680x0 execution units.
3. **Macintosh ROM Checksum Verification**:
   - Computes standard Apple 32-bit additive checksum of system ROM segments and verifies them against known emulator ROM dumps (e.g., Quadra 610/650/800 `F1ACAD13`).
4. **MacTCP / Serial Proxy Bridge Relay**:
   - Designed to emit formatted JSON payloads over MacTCP (OT) or serial SLIP/PPP bridge for machines lacking NuBus/PDS Ethernet adapters.

## Toolchain & Compilation

### 1. Cross-compiling with Retro68
```bash
# Build classic 68K Mac binary using Retro68 GCC toolchain
m68k-apple-macos-gcc -O2 -Wall miner_mac68k.c -o miner_mac68k
```

### 2. Compiling with MPW (Macintosh Programmer's Workshop)
```mpw
SC -model far miner_mac68k.c
ILink -model far -t APPL -c "????' miner_mac68k.c.o "{Libraries}MacRuntime.o" -o miner_mac68k
```

### 3. POSIX / Verification Host Build
```bash
gcc -Wall -Wextra -Werror -O2 miner_mac68k.c -o miner_mac68k
./miner_mac68k [WALLET_ADDRESS]
```

## Usage on Classic Mac OS
Launch `miner_mac68k` from Finder or classic MPW Shell:
```
miner_mac68k RTC8b1fb717791b0a7b72649342b5c7c7bd822786af
```
