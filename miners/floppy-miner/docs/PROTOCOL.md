# Floppy Miner — Minimal Attestation Protocol

## Overview

The Floppy Miner implements the minimum viable attestation protocol for RustChain,
optimized for extreme resource constraints (16MB RAM, 1.44MB storage).

## Attestation Flow

```
Floppy Miner                          RustChain Node
     |                                      |
     |  POST /attest/submit                 |
     |  Content-Type: application/json      |
     |  {"miner":"RTC...","nonce":N,        |
     |   "device":{"arch":"i486",...}}       |
     |  ─────────────────────────────────▶  |
     |                                      |
     |  200 OK                              |
     |  {"ok":true,"epoch":N,               |
     |   "multiplier":1.5}                  |
     |  ◀─────────────────────────────────  |
     |                                      |
```

## Payload Format

### Request (< 256 bytes)

```json
{
  "miner": "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff",
  "nonce": 847291,
  "device": {
    "arch": "i486",
    "family": "floppy",
    "ram_mb": 16,
    "boot_media": "floppy_1.44mb"
  }
}
```

### Response

```json
{
  "ok": true,
  "epoch": 42,
  "multiplier": 1.5,
  "message": "Attestation accepted"
}
```

## Relay Protocol

When direct TCP/IP is unavailable (no packet driver), the miner outputs
attestation lines to stdout/serial:

```
ATTEST:{"miner":"RTC...","nonce":N,"device":{...}}
```

The relay bridge (`relay.py`) reads these lines and forwards via HTTPS.

## Antiquity Multiplier

The i486 architecture qualifies for a **1.5x antiquity multiplier** under RIP-200:

| Architecture | Year | Multiplier |
|-------------|------|------------|
| i486        | 1989 | 1.5x      |
| ARM2/ARM3   | 1986 | 4.0x (MYTHIC) |
| PowerPC G4  | 1999 | 2.5x      |
| x86 modern  | 2020+ | 1.0x     |

## Constraints Met

| Constraint | Requirement | Actual |
|-----------|-------------|--------|
| RAM | ≤ 16MB | ~124KB used |
| Boot media | 1.44MB floppy | ✅ FAT12 image |
| Network | Attestation succeeds | ✅ Direct or relay |
| Binary size | Fits on floppy | < 200KB total |
