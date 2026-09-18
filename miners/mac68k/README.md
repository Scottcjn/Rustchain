# RustChain Vintage Macintosh 68K Miner (Bounty #23)

Autonomous PoA attestation miner for vintage Motorola 680x0 Macintosh hardware (68000, 68020, 68030, 68040) running System 7.x, Mac OS 8, or Mac OS 9. Earns the **1.8x - 2.5x antiquity multiplier**.

## Hardware & Environment Support

- **Target Systems:** Macintosh Plus, SE, SE/30, IIci, Quadra 650/700/800, PowerBook 100-series.
- **Networking:** MacTCP or OpenTransport over Ethernet (NuBus/PDS), LocalTalk bridge, or SLIP/PPP.
- **Cross-Compiler:** Retro68 (m68k-apple-macos-gcc), MPW, or Think C.

## Anti-Virtualization & Emulator Traps

To protect Proof of Antiquity rewards, `miner68k` enforces three hardware validation checks:
1. **ROM Checksum Verification:** Probes hardware ROM base and tests against 24 known emulator dump signatures (e.g. Quadra 650 `0xF1ACAD13` used by Basilisk II).
2. **VIA 6522 Timer Drift:** Measures physical clock jitter between the 6522 Versatile Interface Adapter and the 680x0 CPU instruction pipeline. Emulators with uniform clocks fail this test.
3. **FPU Latency Calibration:** Evaluates Motorola 68881/68882 trigonometric cycle variance against software emulation.

## Build Instructions

```bash
# Build native test executable
gcc -O2 miner68k.c -o miner68k

# Build for 68K Classic Mac with Retro68
m68k-apple-macos-gcc -O2 -s miner68k.c -o miner68k.bin
```

## Running

```bash
./miner68k RTC8b1fb717791b0a7b72649342b5c7c7bd822786af
```
