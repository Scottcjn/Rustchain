---
title: "RIP-0304: Retro Console Mining via Pico Serial Bridge"
author: Scott Boudreaux (Elyan Labs)
status: Draft
type: Standards Track
category: Core
created: 2026-02-28
requires: RIP-0001, RIP-0007, RIP-0200, RIP-0201
license: Apache 2.0
---

# Summary

This RIP formalizes the architecture for retro game console participation in
RustChain's Proof of Antiquity consensus. A Raspberry Pi Pico microcontroller
serves as a serial-to-controller bridge, enabling consoles from 1983 onward
(NES, SNES, N64, Genesis, Game Boy, Saturn, PS1) to attest hardware identity
and earn RTC rewards. This is, to our knowledge, the first blockchain to mine
on vintage game console silicon.

# Abstract

Vintage game consoles contain some of the most widely manufactured CPUs in
computing history — over 500 million units across the NES, SNES, N64, Genesis,
Game Boy, and PlayStation families alone. These consoles run CPUs dating back to
1975 (MOS 6502) through 1996 (MIPS R4300i), giving them extreme antiquity value
under RIP-0001.

RIP-304 defines:

1. A **Pico serial-to-controller bridge** that connects consoles to the
   RustChain network through their controller ports
2. **Console-specific CPU aliases** mapped to existing antiquity multipliers
3. **Controller port timing fingerprinting** as an anti-emulation mechanism
4. A dedicated **`retro_console` fleet bucket** under RIP-201
5. **Attestation payload extensions** for bridge-mediated hardware

# Motivation

## Why Consoles?

- **Ubiquity**: More NES units exist (61.9M) than most server CPUs ever
  manufactured. SNES (49.1M), N64 (32.9M), Genesis (30.8M), Game Boy (118.7M),
  PS1 (102.5M) add hundreds of millions more.
- **Extreme Antiquity**: The NES Ricoh 2A03 derives from the MOS 6502 (1975).
  The SNES Ricoh 5A22 uses the WDC 65C816 (1983). These CPUs predate the IBM PC.
- **Unfakeable Silicon**: Console hardware has physical timing characteristics
  (bus jitter, clock drift, controller port latency) that no software emulator
  reproduces at the nanosecond level.
- **Preservation Incentive**: RTC rewards create economic incentive to keep
  vintage consoles operational — directly aligned with PoA's sustainability goals.

## Proven Feasibility

The **Legend of Elya** project demonstrates real computation on Nintendo 64
hardware:

- 4-layer nano-GPT with 819,000 parameters
- Q8 quantized weights (868 KB) loaded into N64 RDRAM
- Running on the MIPS R4300i FPU at 93.75 MHz (float32, hard-float)
- Achieves 1-3 tokens/second on real hardware
- ROM format: `.z64` (big-endian MIPS)

If an N64 can run a neural network, it can certainly compute attestation hashes.

# Specification

## 1. Pico Serial-to-Controller Bridge

### Architecture

```
┌──────────────────────┐          ┌─────────────────────┐          ┌─────────────┐
│   RETRO CONSOLE      │          │   RASPBERRY PI PICO  │          │  RUSTCHAIN   │
│                      │          │   (RP2040, 264KB)    │          │  NODE        │
│  CPU ──── Bus ──┐    │          │                      │          │              │
│  PPU            │    │  Ctrl    │  PIO ← Controller    │   USB    │  /attest/    │
│  APU    Controller◄──┼──Port──► │    State Machine     ├──Serial──┤  submit      │
│         Port     │   │  Wires   │                      │  to PC   │              │
│                  │   │          │  Bus Timing Analysis  │  or WiFi │  Validates   │
│  Cartridge Slot  │   │          │  Entropy Collector    │          │  fingerprint │
│  (ROM + SRAM)    │   │          │  Attestation Builder  │          │              │
└──────────────────────┘          └─────────────────────┘          └─────────────┘
```

### How It Works

1. **The console runs a custom ROM** (cartridge) containing attestation logic.
   The ROM exercises the CPU (hash computation, timing loops) and outputs
   results through the controller port data lines.

2. **The Pico connects to the controller port** using a custom
   serial-to-controller adapter. The Pico's PIO (Programmable I/O) state
   machines implement the console's controller protocol at hardware speed
   (125 MHz PIO clock — sufficient for all console protocols).

3. **The Pico reads computation results** from the console via controller port
   data patterns and simultaneously measures bus timing at sub-microsecond
   resolution for hardware fingerprinting.

4. **The Pico relays attestation data** to the RustChain node via:
   - **USB Serial** to a host PC running the miner client (primary)
   - **WiFi** (Pico W variant) directly to the RustChain node (standalone)

### Controller Port Protocols

| Console | Protocol | Data Rate | Polling Rate | Timing Resolution |
|---------|----------|-----------|--------------|-------------------|
| NES     | Serial shift register (clock + latch + data) | 8 bits/poll | ~60 Hz | ~12 us/bit |
| SNES    | Serial shift register (16-bit extended NES) | 16 bits/poll | ~60 Hz | ~12 us/bit |
| N64     | Joybus (half-duplex, 3.3V) | 4 Mbit/s | On-demand | ~250 ns/bit |
| Genesis | 6-button parallel (active polling) | 6 bits/poll | ~60 Hz | ~16.7 ms/frame |
| Game Boy | Link cable SPI | 8 Kbit/s | Software-driven | ~122 us/bit |
| Saturn  | Parallel SMPC | 8+ bits/poll | ~60 Hz | ~16.7 ms/frame |
| PS1     | SPI-like serial | 250 Kbit/s | ~60 Hz | ~4 us/bit |

### Pico Hardware Requirements

- **Raspberry Pi Pico** (RP2040): $4 USD, dual ARM Cortex-M0+ @ 133 MHz
- **Pico W** variant adds WiFi for standalone operation
- **Custom adapter PCB** or hand-wired connector matching target console
- **Each RP2040 has a unique board ID** burned into OTP ROM — used as device
  identifier in attestation payloads

## 2. Console Hardware Tiers

Console CPUs map to existing antiquity multiplier families with console-specific
aliases for identification and fleet bucketing.

| Console | CPU | CPU Family | Release Year | Alias | Base Mult |
|---------|-----|------------|-------------|-------|-----------|
| NES/Famicom | Ricoh 2A03 (6502 derivative) | 6502 | 1983 | `nes_6502` | 2.8x |
| Game Boy | Sharp LR35902 (Z80 derivative) | Z80 | 1989 | `gameboy_z80` | 2.6x |
| Sega Master System | Zilog Z80 | Z80 | 1986 | `sms_z80` | 2.6x |
| Sega Genesis | Motorola 68000 | 68000 | 1988 | `genesis_68000` | 2.5x |
| SNES/Super Famicom | Ricoh 5A22 (65C816) | 65C816 | 1990 | `snes_65c816` | 2.7x |
| Sega Saturn | Hitachi SH-2 (dual) | SH-2 | 1994 | `saturn_sh2` | 2.6x |
| PlayStation 1 | MIPS R3000A | MIPS R3000 | 1994 | `ps1_mips` | 2.8x |
| Nintendo 64 | NEC VR4300 (MIPS R4300i) | MIPS R5000 | 1996 | `n64_mips` | 2.5x |
| Game Boy Advance | ARM7TDMI | ARM7 | 2001 | `gba_arm7` | 2.3x |

### Generic CPU Family Additions

These CPU families are used across multiple platforms (computers and consoles)
and receive a generic entry alongside console-specific aliases:

| Family | Base Mult | Used In |
|--------|-----------|---------|
| `6502` | 2.8x | NES, Apple II, Commodore 64, Atari 2600 |
| `65c816` | 2.7x | SNES, Apple IIGS |
| `z80` | 2.6x | Game Boy, Sega SMS, MSX, ZX Spectrum |
| `sh2` | 2.6x | Sega Saturn, Sega 32X |

### Antiquity Decay

Console multipliers follow the standard RIP-200 time-aging formula:

```
aged_multiplier = 1.0 + (base - 1.0) * (1 - 0.15 * chain_age_years)
```

Full decay to 1.0x after ~16.67 years of chain operation.

## 3. Console-Specific Fingerprinting

Consoles cannot run Python, access `/proc/cpuinfo`, or perform standard
fingerprint checks. Instead, the Pico bridge measures physical signals from
the console hardware:

### Controller Port Timing Fingerprint

Each console polls its controller port at a nominally fixed interval (e.g.,
60 Hz for NTSC). Real hardware exhibits measurable jitter:

- **Crystal oscillator drift**: The console's master clock has age-dependent
  frequency drift (same principle as RIP-0007 Check 1)
- **Bus contention jitter**: CPU/PPU/DMA bus arbitration creates variable
  controller port response times
- **Thermal drift**: Console temperature affects oscillator frequency

The Pico captures timing of each controller poll (mean, stdev, coefficient of
variation) over 500+ samples. This replaces the standard `clock_drift` check.

**Threshold**: CV below 0.0001 flags emulation (emulators poll at perfect
intervals with zero jitter).

### ROM Execution Timing

The cartridge ROM computes a SHA-256 of the attestation nonce using the
console's native CPU. The Pico measures execution time:

- Real N64 R4300i @ 93.75 MHz: ~847ms for a SHA-256
- Real NES 2A03 @ 1.79 MHz: significantly longer, with characteristic
  per-instruction timing
- Emulators running on modern CPUs at GHz speeds must artificially throttle,
  creating detectable timing quantization artifacts

### Anti-Emulation Signals

Software emulators (Project64, SNES9x, FCEUX, Mednafen, etc.) exhibit:

1. **Zero controller port jitter** — perfect timing from software polling loops
2. **Quantized execution timing** — modern CPU clock granularity leaks through
3. **Uniform thermal response** — no physical silicon temperature effects
4. **Perfect bus timing** — no DMA contention or bus arbitration artifacts

The Pico's PIO state machines sample at 125 MHz — fast enough to detect these
artifacts even on N64's 4 Mbit/s Joybus protocol.

## 4. Attestation Payload Format

Extends the standard RustChain attestation format (RIP-0007) with bridge and
console fields:

```json
{
    "miner": "n64-scott-unit1",
    "miner_id": "n64-pico-bridge-001",
    "nonce": "<from challenge>",
    "report": {
        "nonce": "<from challenge>",
        "commitment": "<sha256 computed by console CPU>",
        "derived": {
            "ctrl_port_timing_mean_ns": 16667000,
            "ctrl_port_timing_stdev_ns": 1250,
            "ctrl_port_cv": 0.075,
            "rom_hash_result": "<sha256 computed by console CPU>",
            "rom_hash_time_us": 847000,
            "bus_jitter_samples": 500
        },
        "entropy_score": 0.075
    },
    "device": {
        "family": "console",
        "arch": "n64_mips",
        "model": "Nintendo 64 NUS-001",
        "cpu": "NEC VR4300 (MIPS R4300i) 93.75MHz",
        "cores": 1,
        "memory_mb": 4,
        "bridge_type": "pico_serial",
        "bridge_firmware": "1.0.0"
    },
    "signals": {
        "pico_serial": "<RP2040 unique board ID>",
        "ctrl_port_protocol": "joybus",
        "rom_id": "rustchain_attest_n64_v1"
    },
    "fingerprint": {
        "all_passed": true,
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "passed": true,
                "data": {"cv": 0.075, "samples": 500}
            },
            "rom_execution_timing": {
                "passed": true,
                "data": {"hash_time_us": 847000}
            },
            "bus_jitter": {
                "passed": true,
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "passed": true,
                "data": {"emulator_indicators": []}
            }
        }
    }
}
```

### Bridge-Type Detection

Server-side `validate_fingerprint_data()` detects `bridge_type: "pico_serial"`
and accepts console-specific checks in place of standard checks:

| Standard Check | Console Equivalent | Source |
|---------------|--------------------|--------|
| `clock_drift` | `ctrl_port_timing` | Pico PIO measurement |
| `cache_timing` | `rom_execution_timing` | Pico elapsed timer |
| `simd_identity` | N/A (not applicable) | Skipped for consoles |
| `thermal_drift` | Implicit in ctrl_port_timing drift | Pico PIO measurement |
| `instruction_jitter` | `bus_jitter` | Pico PIO measurement |
| `anti_emulation` | `anti_emulation` | Timing CV threshold |

## 5. Fleet Bucket Integration (RIP-201)

Console miners receive their own fleet bucket (`retro_console`) to prevent:

1. **Drowning**: A few console miners shouldn't compete against dozens of x86
   miners in the `modern` bucket
2. **Domination**: A console farm shouldn't dominate the `exotic` bucket that
   includes POWER8, SPARC, and RISC-V machines

```python
HARDWARE_BUCKETS["retro_console"] = [
    "nes_6502", "snes_65c816", "n64_mips", "genesis_68000",
    "gameboy_z80", "sms_z80", "saturn_sh2", "ps1_mips", "gba_arm7",
    "6502", "65c816", "z80", "sh2",
]
```

Console farm mitigation follows existing RIP-201 fleet detection: IP clustering,
timing correlation, and fingerprint similarity analysis.

## 6. Security Considerations

### Controller Port Replay Attack

An attacker records real console timing data and replays it.

**Mitigation**: Challenge-response protocol. Each attestation requires a fresh
nonce from the node. The ROM on the console must compute `SHA-256(nonce || wallet)`
using the console's native CPU. The Pico cannot precompute this without knowing
the nonce in advance.

### Pico Firmware Spoofing

An attacker modifies Pico firmware to fabricate timing data.

**Mitigation**: The RP2040 has a unique board ID in OTP ROM that cannot be
reprogrammed. The attestation includes this ID, and the server tracks Pico IDs
like MAC addresses. Additionally, the ROM execution timing must match the
known performance profile of the claimed console CPU — a fabricated 847ms
SHA-256 time only makes sense for an R4300i at 93.75 MHz.

### Emulator + Fake Bridge

An attacker runs an emulator on a PC and writes software pretending to be a Pico.

**Mitigation**: Multiple layers:
- USB device descriptors identify real RP2040 vs generic serial adapters
- Controller port timing statistics from real hardware have specific
  distributions (non-Gaussian jitter from bus contention) that emulators
  cannot reproduce
- Timing CV below 0.0001 flags emulation (identical to existing RIP-0007
  check)

### Console Farm (100 real NES units)

**Mitigation**: RIP-201 fleet detection applies. All NES units land in the
`retro_console` bucket and share one bucket's worth of rewards. Fleet scoring
detects IP clustering and correlated attestation timing. Equal Bucket Split
ensures console miners receive a fair but bounded share.

## 7. Future Extensions

### Phase 2: Additional Consoles

| Console | CPU | Status |
|---------|-----|--------|
| Atari 2600 | MOS 6507 (6502 variant) | Feasible — paddle port I/O |
| Atari 7800 | Sally (6502C variant) | Feasible — controller port |
| Neo Geo | Motorola 68000 | Feasible — controller port |
| TurboGrafx-16 | HuC6280 (65C02) | Feasible — controller port |
| Dreamcast | Hitachi SH-4 | Feasible — Maple Bus via Pico |
| GameCube | IBM Gekko (PowerPC 750) | Feasible — controller port |

### Phase 3: Pico W Standalone Mode

The Pico W variant includes WiFi, enabling fully standalone operation:
console + Pico + power = mining node. No host PC required.

### Phase 4: Multi-Console Bridge

A single Pico board with multiple controller port connectors, allowing one
bridge to manage several consoles simultaneously.

# Reference Implementation

## Files Modified

- `node/rip_200_round_robin_1cpu1vote.py` — Console CPU aliases in
  `ANTIQUITY_MULTIPLIERS`
- `rips/python/rustchain/fleet_immune_system.py` — `retro_console` bucket in
  `HARDWARE_BUCKETS`
- `node/rustchain_v2_integrated_v2.2.1_rip200.py` — `console` family in
  `HARDWARE_WEIGHTS`, bridge-type detection in `validate_fingerprint_data()`

## Files Created

- `rips/docs/RIP-0304-retro-console-mining.md` — This specification

## Future Files (Not in This RIP)

- `miners/console/pico_bridge_firmware/` — RP2040 firmware per console
- `miners/console/n64_attestation_rom/` — N64 attestation ROM
- `miners/console/nes_attestation_rom/` — NES attestation ROM
- `miners/console/snes_attestation_rom/` — SNES attestation ROM

# Acknowledgments

- **Legend of Elya** — Proved neural network inference on N64 MIPS R4300i FPU
- **RIP-0001** (Sophia Core Team) — Proof of Antiquity consensus foundation
- **RIP-0007** (Sophia Core Team) — Entropy fingerprinting framework
- **RIP-0200** — 1 CPU = 1 Vote round-robin consensus
- **RIP-0201** — Fleet Detection Immune System

# Copyright

This document is licensed under Apache License, Version 2.0.
