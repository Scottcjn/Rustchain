# N64 Mining ROM — RustChain on Nintendo 64

Mine RTC tokens on real Nintendo 64 hardware using the MIPS R4300i CPU.
Earns the **MYTHIC 4.0x antiquity multiplier** — the highest tier in RustChain's proof-of-antiquity.

## Architecture

```
┌─────────────┐     serial/USB      ┌──────────────┐     HTTPS     ┌─────────────────┐
│  N64 ROM    │ ──────────────────▶ │  Host Relay   │ ────────────▶ │  RustChain Node  │
│  VR4300     │  attestation data   │  (Python)     │  /attest/     │  50.28.86.131    │
│  MIPS III   │ ◀────────────────── │  serial bridge │ ◀──────────── │  RIP-200         │
│  93.75 MHz  │  epoch rewards      │               │  rewards      │                  │
└─────────────┘                     └──────────────┘               └─────────────────┘
```

## Components

| File | Purpose |
|------|---------|
| `n64_miner.c` | N64 ROM source — attestation, fingerprinting, mining loop |
| `n64_miner.h` | Header — constants, structures, protocol definitions |
| `host_relay.py` | Host-side serial bridge — relays attestation to RustChain node |
| `fingerprint.c` | Hardware fingerprint — cache timing, Count register drift, RSP jitter |
| `fingerprint.h` | Fingerprint header |
| `test_host_relay.py` | Unit tests for host relay |
| `test_fingerprint.py` | Tests for fingerprint validation logic |
| `Makefile` | Build ROM with libdragon toolchain |

## Hardware Fingerprint (Anti-Emulation)

The N64 proves it's real hardware through:

1. **Count Register Drift** — MIPS Count register increments at CPU/2 (46.875 MHz). Emulators approximate this, real hardware has measurable jitter.
2. **Cache Timing Profile** — D-cache (8KB) and I-cache (16KB) latency sweep reveals real silicon characteristics.
3. **RSP Pipeline Jitter** — The Reality Signal Processor vector unit has timing patterns unique to real hardware.
4. **TLB Miss Latency** — Real MIPS TLB misses have consistent 30-cycle penalty; emulators vary.

Combined fingerprint hash is submitted with attestation.

## Attestation Protocol

```json
{
  "device_arch": "mips_r4300",
  "device_family": "N64",
  "fingerprint_hash": "<sha256 of hardware measurements>",
  "measurements": {
    "count_drift_ns": 213,
    "cache_d_latency_cycles": [2, 2, 2, 42, 42],
    "cache_i_latency_cycles": [1, 1, 1, 38, 38],
    "rsp_jitter_ns": 47,
    "tlb_miss_cycles": 31
  },
  "miner_id": "n64-miner-001",
  "epoch": 42
}
```

## Quick Start

### Build ROM (requires libdragon)
```bash
# Install libdragon: https://github.com/DragonMinded/libdragon
make

# Output: n64_miner.z64
```

### Run Host Relay
```bash
pip install pyserial requests

# With real N64 + EverDrive + serial adapter:
python host_relay.py --port /dev/ttyUSB0 --node https://rustchain.org --wallet RTC_YOUR_WALLET

# Demo mode (no hardware):
python host_relay.py --demo --node https://rustchain.org --wallet RTC_YOUR_WALLET
```

### Controller
- **A Button**: Toggle mining display
- **B Button**: Show wallet balance
- **Start**: Begin mining
- **L+R+Z**: Emergency stop

## RIP-200 Multiplier

| Architecture | Multiplier | Tier |
|---|---|---|
| **MIPS R4300i (N64)** | **4.0x** | **MYTHIC** |
| ARM2/ARM3 | 4.0x | MYTHIC |
| PowerPC G4 | 2.5x | LEGENDARY |
| PowerPC G5 | 2.0x | EPIC |
| ARM Cortex | 1.2x | COMMON |
| x86_64 | 1.0x | STANDARD |

## Bounty

Closes https://github.com/Scottcjn/Rustchain/issues/1877
