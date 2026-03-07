---
title: "RIP-0683: Console Bridge Integration Rework"
author: "RustChain Core Team"
status: "Accepted"
type: "Implementation"
category: "Core"
created: "2026-03-07"
requires: "RIP-0001, RIP-0007, RIP-0200, RIP-0201, RIP-0304"
license: "Apache 2.0"
---

# Summary

RIP-0683 implements the full integration of retro console mining into RustChain's
Proof of Antiquity consensus. This rework delivers:

1. **Real hardware integration** - Not mock data, but actual Pico bridge communication
2. **Rust core implementation** - Native Rust types and validation logic
3. **Python node integration** - Full integration with existing rustchain_v2 node
4. **Fleet immune system** - Dedicated `retro_console` bucket with anti-fleet detection
5. **Testable flow** - Complete test suite with verifiable run steps

# Abstract

This RIP implements the technical specifications from RIP-0304, enabling vintage
game consoles (NES, SNES, N64, Genesis, Game Boy, Saturn, PS1) to participate in
RustChain consensus via a Raspberry Pi Pico serial bridge.

Key deliverables:
- Rust core types for console CPU families
- Anti-emulation verification for console-specific timing
- Pico bridge firmware reference implementation
- Integration with existing RIP-200 round-robin consensus
- Fleet detection for console miners

# Motivation

RIP-0304 identified the opportunity but lacked implementation. RIP-0683 delivers:

1. **Economic incentive for preservation** - 500M+ vintage consoles can earn RTC
2. **Unfakeable silicon** - Physical timing characteristics prevent emulation
3. **Distributed participation** - Console miners get fair bucket allocation
4. **Real integration** - Touches actual code paths, not mock-only scaffolding

# Specification

## 1. Console CPU Families (Rust Core)

Console CPUs are added to the hardware tier system with specific aliases:

```rust
// Console-specific CPU families
pub const CONSOLE_CPU_FAMILIES: &[(&str, u32, f64)] = &[
    ("nes_6502", 1983, 2.8),      // Ricoh 2A03 (6502 derivative)
    ("snes_65c816", 1990, 2.7),   // Ricoh 5A22 (65C816)
    ("n64_mips", 1996, 2.5),      // NEC VR4300 (MIPS R4300i)
    ("genesis_68000", 1988, 2.5), // Motorola 68000
    ("gameboy_z80", 1989, 2.6),   // Sharp LR35902 (Z80 derivative)
    ("sms_z80", 1986, 2.6),       // Zilog Z80
    ("saturn_sh2", 1994, 2.6),    // Hitachi SH-2 (dual)
    ("ps1_mips", 1994, 2.8),      // MIPS R3000A
    ("gba_arm7", 2001, 2.3),      // ARM7TDMI
];
```

## 2. Pico Bridge Protocol

The bridge communicates via USB serial with the following message format:

```
# Attestation Request (Node → Pico)
ATTEST|<nonce>|<wallet>|<timestamp>\n

# Attestation Response (Pico → Node)
OK|<pico_id>|<console_arch>|<timing_data>|<hash_result>\n
ERROR|<error_code>\n
```

Timing data format (JSON embedded in response):
```json
{
  "ctrl_port_timing_mean_ns": 16667000,
  "ctrl_port_timing_stdev_ns": 1250,
  "ctrl_port_cv": 0.075,
  "rom_hash_time_us": 847000,
  "bus_jitter_samples": 500
}
```

## 3. Anti-Emulation Verification

Console miners use different checks than standard miners:

| Standard Check | Console Equivalent | Threshold |
|---------------|--------------------|-----------|
| `clock_drift` | `ctrl_port_timing` | CV > 0.0001 |
| `cache_timing` | `rom_execution_timing` | ±10% of baseline |
| `simd_identity` | N/A | Skipped |
| `thermal_drift` | Implicit in timing | CV > 0.0001 |
| `instruction_jitter` | `bus_jitter` | stdev > 500ns |

## 4. Fleet Bucket Integration

Console miners are assigned to `retro_console` bucket:

```python
HARDWARE_BUCKETS["retro_console"] = [
    "nes_6502", "snes_65c816", "n64_mips", "genesis_68000",
    "gameboy_z80", "sms_z80", "saturn_sh2", "ps1_mips", "gba_arm7",
    "6502", "65c816", "z80", "sh2",
]
```

Rewards split equally across active buckets (equal_split mode).

## 5. Security Model

### Challenge-Response Protocol

1. Node generates random nonce
2. Pico forwards nonce to console ROM
3. Console computes `SHA-256(nonce || wallet)` using native CPU
4. Pico measures execution time and relays result
5. Node verifies hash and timing profile

### Anti-Spoof Measures

- **Pico board ID** - Unique OTP ROM identifier (cannot be reprogrammed)
- **Timing profiles** - Real hardware has characteristic jitter distributions
- **ROM execution time** - Must match known CPU performance (e.g., N64 @ 93.75 MHz)
- **Fleet detection** - IP clustering, timing correlation analysis

# Implementation

## Files Modified

1. `rips/src/core_types.rs` - Console CPU families
2. `rips/src/proof_of_antiquity.rs` - Console anti-emulation logic
3. `rips/python/rustchain/fleet_immune_system.py` - retro_console bucket
4. `node/rustchain_v2_integrated_v2.2.1_rip200.py` - Bridge validation
5. `node/rip_200_round_robin_1cpu1vote.py` - Console multipliers

## Files Created

1. `rips/docs/RIP-0683-console-bridge-integration.md` - This specification
2. `miners/console/pico_bridge_firmware/pico_bridge.ino` - Reference firmware
3. `miners/console/n64_attestation_rom/` - N64 ROM source
4. `tests/test_console_miner_integration.py` - Integration tests
5. `docs/CONSOLE_MINING_SETUP.md` - Setup guide

# Reference Implementation

See accompanying code files for:
- Rust core types (`rips/src/core_types.rs`)
- Proof of antiquity validation (`rips/src/proof_of_antiquity.rs`)
- Pico bridge firmware (`miners/console/pico_bridge_firmware/`)
- Integration tests (`tests/test_console_miner_integration.py`)

# Testing

Run the test suite:

```bash
# Rust tests
cd rips && cargo test --lib

# Python integration tests
python3 tests/test_console_miner_integration.py

# End-to-end test with mock Pico
python3 tests/test_pico_bridge_sim.py
```

# Backwards Compatibility

- Existing miners unaffected
- Console miners use new code paths but same attestation API
- Fleet bucket system already supports new buckets

# Future Work

1. **Additional consoles** - Atari, Neo Geo, Dreamcast, GameCube
2. **Pico W standalone** - WiFi-enabled standalone operation
3. **Multi-console bridge** - One Pico, multiple controller ports
4. **Hardware anchor** - On-chain attestation via Ergo bridge

# Acknowledgments

- **Legend of Elya** - Proved N64 neural network inference
- **RIP-0304** - Original console mining specification
- **RIP-0201** - Fleet detection framework
- **Sophia Core Team** - Proof of Antiquity consensus

# Copyright

Licensed under Apache License, Version 2.0.
