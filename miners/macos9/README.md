# RustChain Mac OS 9.2 (PowerPC) Miner Port via POSIX Shim

Implementation for [RustChain Bounty #440](https://github.com/Scottcjn/rustchain-bounties/issues/440).

Enables native Proof-of-Antiquity mining on PowerPC Macintosh hardware running Mac OS 9.2 (Power Macintosh G3, iMac G3, PowerBook G3/G4, Power Mac G4) using a lightweight POSIX compatibility shim.

Ecosystem Multiplier: **1.4x Retro Multiplier**

---

## Architectural Components

1. **POSIX Shim Layer (`posix_shim.h`, `posix_shim.c`)**:
   - BSD Sockets (`socket()`, `connect()`, `send()`, `recv()`, `close()`) wrapped over Open Transport (OT) / Carbon sockets.
   - High-resolution timing (`gettimeofday()`, `time()`) calibrated via Macintosh Toolbox `Microseconds` trap.
   - Bundled pure C SHA-256 cryptographic digest engine (eliminates OpenSSL dependency).
2. **Miner Client (`miner_macos9.c`)**:
   - Constructs canonical HTTP attestation requests.
   - Encodes hardware fingerprint (`device_arch: powerpc_g4`, `device_family: mac_os_9`).
   - Submits Proof-of-Antiquity attestation envelopes directly to active node API (`50.28.86.131`).

---

## Compilation & Toolchains

### Option A: Retro68 Cross-Compiler (Linux / macOS Host)
```bash
# Compile using powerpc-apple-macos-gcc
powerpc-apple-macos-gcc -O2 -mpowerpc posix_shim.c miner_macos9.c -o miner_macos9.bin
```

### Option B: Metrowerks CodeWarrior Pro 8 (Inside Mac OS 9)
1. Create a new `Mac OS C Stationary` project targetting PowerPC Carbon/Classic.
2. Add `posix_shim.c`, `posix_shim.h`, and `miner_macos9.c` to the project window.
3. Link with `OpenTransportAppPPC.lib` and `MSL_All_PPC.lib`.
4. Build `miner_macos9.app`.
