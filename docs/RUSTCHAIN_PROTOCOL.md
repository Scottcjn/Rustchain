# RustChain Protocol Specification

## Overview

RustChain is a **Proof-of-Antiquity** blockchain that rewards real vintage hardware with higher mining multipliers than modern machines. The network uses **6+1 hardware fingerprint checks** to prevent VMs and emulators from earning rewards.

**Native Token**: RTC (RustChain Token)  
**Consensus**: RIP-200 Proof of Antiquity  
**Epoch Time**: 10 minutes  
**Base Reward**: 1.5 RTC per epoch (distributed among active miners)

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RustChain Network                        │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Miner   │    │  Miner   │    │  Miner   │              │
│  │ (PowerPC)│    │ (x86_64) │    │ (SPARC)  │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                     │
│       └───────────────┼───────────────┘                     │
│                       ▼                                     │
│              ┌─────────────────┐                            │
│              │  Attestation    │                            │
│              │     Server      │                            │
│              │ (rustchain.org) │                            │
│              └────────┬────────┘                            │
│                       │                                     │
│                       ▼                                     │
│              ┌─────────────────┐                            │
│              │   Epoch Settlement  │                        │
│              │   & Reward Dist.  │                            │
│              └─────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Role | URL |
|-----------|------|-----|
| **Attestation Server** | Validates hardware fingerprints, tracks miners | `https://rustchain.org` |
| **Block Explorer** | View miners, epochs, rewards | `https://rustchain.org/explorer` |
| **wRTC Bridge** | Bridge RTC to Solana (wRTC) | `https://bottube.ai/bridge` |

---

## RIP-200 Proof of Antiquity Consensus

### Core Principle

**Older hardware earns more.** RustChain inverts traditional blockchain economics by rewarding hardware longevity instead of raw compute power.

### Antiquity Multipliers

| Hardware Tier | Era | Multiplier | Examples |
|---------------|-----|------------|----------|
| **MYTHIC** | Pre-1990 | 3.5x - 4.0x | DEC VAX, Acorn ARM2, Inmos Transputer |
| **LEGENDARY** | 1990-1995 | 2.7x - 3.0x | Motorola 68000, Sun SPARC, SGI MIPS |
| **ANCIENT** | 1996-2010 | 2.0x - 2.5x | PowerPC G4/G5, PS3 Cell BE |
| **EXOTIC** | 2011-2019 | 1.4x - 1.8x | RISC-V, IBM POWER8, Pentium 4 |
| **MODERN** | 2020+ | 0.8x - 1.2x | Apple Silicon, Modern x86_64 |
| **PENALTY** | Mass-farmable | 0.0005x | ARM NAS/SBC clusters |

### Reward Calculation

```
miner_reward = (base_reward × miner_multiplier) / total_weighted_miners

where:
  base_reward = 1.5 RTC per epoch
  miner_multiplier = hardware antiquity multiplier (see table above)
  total_weighted_miners = Σ(all active miners' multipliers)
```

**Example** (8 miners online):
- PowerPC G4 (2.5x): 0.30 RTC/epoch ≈ 43 RTC/day
- Modern x86 (0.8x): 0.12 RTC/epoch ≈ 17 RTC/day

---

## Hardware Fingerprinting (6+1 Checks)

RustChain uses **6 hardware fingerprint checks** that no VM or emulator can fake. These checks exploit physical properties of real silicon that age and degrade uniquely.

```
┌─────────────────────────────────────────────────────────────┐
│ Hardware Fingerprint Validation Pipeline                    │
├─────────────────────────────────────────────────────────────┤
│ 1. Clock-Skew & Oscillator Drift  ← Silicon aging patterns  │
│ 2. Cache Timing Fingerprint       ← L1/L2/L3 latency maps   │
│ 3. SIMD Unit Identity             ← AltiVec/SSE/NEON flags  │
│ 4. Thermal Drift Entropy          ← Heat curve uniqueness   │
│ 5. Instruction Path Jitter        ← Microarchitecture sig   │
│ 6. Anti-Emulation Detection       ← VM/emu detection        │
│                                                             │
│ +1. Server-Side AI Validation   ← Cross-check all above     │
└─────────────────────────────────────────────────────────────┘
```

### Check Details

#### 1. Clock-Skew & Oscillator Drift
- **What**: Measures crystal oscillator imperfections
- **Why**: Real crystals drift with age/temperature; VMs use perfect synthetic clocks
- **Detection**: VMs fail because their clock is too precise

#### 2. Cache Timing Fingerprint
- **What**: Maps L1/L2/L3 cache latency patterns
- **Why**: Each CPU has unique cache timing due to manufacturing variance
- **Detection**: VMs share host cache patterns; emulators have wrong timings

#### 3. SIMD Unit Identity
- **What**: Tests AltiVec (PowerPC), SSE/AVX (x86), NEON (ARM)
- **Why**: SIMD execution patterns are architecture-specific
- **Detection**: SheepShaver (G4 emulator) fails AltiVec timing tests

#### 4. Thermal Drift Entropy
- **What**: Monitors thermal response curves under load
- **Why**: Real hardware has unique thermal mass and dissipation
- **Detection**: VMs have uniform/flat thermal response

#### 5. Instruction Path Jitter
- **What**: Measures microarchitectural execution variance
- **Why**: Branch prediction, pipelining create unique jitter patterns
- **Detection**: Emulators have deterministic (wrong) timing

#### 6. Anti-Emulation Detection
- **What**: Active probes for VM/emu artifacts
- **Why**: Emulators leak host information
- **Detection**: CPUID tricks, ROM hashing, instruction timing

### Server-Side AI Validation

The attestation server doesn't trust self-reported data. It performs:

- **Cross-validation**: SIMD features vs claimed architecture
- **ROM clustering detection**: Multiple "different" machines with identical ROM hashes = emulator farm
- **Timing distribution analysis**: Real oscillators have imperfections; synthetic ones are too perfect
- **Thermal anomaly flagging**: VMs have uniform thermal response

---

## Attestation Flow

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│    Miner     │         │   Server     │         │   Epoch      │
│              │         │              │         │  Settlement  │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │  1. Hardware Fingerprint │                        │
       │  ─────────────────────>│                        │
       │                        │                        │
       │                        │  2. AI Validation      │
       │                        │  ──────────┐           │
       │                        │            │           │
       │                        │  <─────────┘           │
       │                        │                        │
       │  3. Attestation Result │                        │
       │  <────────────────────│                        │
       │                        │                        │
       │  (repeat every 5 min)  │                        │
       │                        │                        │
       │                        │  4. Epoch Complete     │
       │                        │  (every 10 min)        │
       │                        │───────────────────────>│
       │                        │                        │
       │                        │  5. Calculate Rewards  │
       │                        │                        │
       │  6. Reward Distributed │                        │
       │  <─────────────────────────────────────────────│
       │                        │                        │
```

### Step-by-Step

1. **Miner starts** → Runs 6 hardware fingerprint checks locally
2. **Fingerprint submission** → Sends results to attestation server
3. **Server validation** → AI cross-validates against known patterns
4. **Attestation accepted** → Miner marked as "active" for current epoch
5. **Epoch completes** (10 min) → Server calculates rewards
6. **Reward distribution** → RTC credited to miner wallet

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Node health status |
| `/api/miners` | GET | List active miners |
| `/epoch` | GET | Current epoch info |
| `/wallet/balance?miner_id=X` | GET | Check wallet balance |
| `/attest` | POST | Submit hardware fingerprint |

---

## Token Economics

### Supply & Distribution

| Category | Allocation | Notes |
|----------|------------|-------|
| **Mining Rewards** | 70% | Distributed via epochs |
| **Bounty Pool** | 20% | Code contributions, docs, bounties |
| **Dev Fund** | 10% | Core development, infrastructure |

### RTC Value

- **Reference Rate**: 1 RTC ≈ $0.10 USD
- **Bridge**: RTC ↔ wRTC (Solana SPL token)
- **Trading**: Available on Raydium DEX

### Bridge to Solana

```bash
# Bridge RTC to wRTC (Solana)
Visit: https://bottube.ai/bridge

# Trade on Raydium
https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
```

---

## API Reference

### GET /health

Check node health status.

**Request**:
```bash
curl -sk https://rustchain.org/health
```

**Response**:
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 3966,
  "db_rw": true
}
```

### GET /api/miners

List all active miners.

**Request**:
```bash
curl -sk https://rustchain.org/api/miners
```

**Response**:
```json
{
  "miners": [
    {
      "miner_id": "scott-laptop",
      "architecture": "x86_64",
      "multiplier": 0.8,
      "last_attestation": "2026-04-09T11:30:00Z",
      "status": "active"
    }
  ],
  "total_active": 8
}
```

### GET /epoch

Get current epoch information.

**Request**:
```bash
curl -sk https://rustchain.org/epoch
```

**Response**:
```json
{
  "epoch": 15847,
  "started_at": "2026-04-09T11:30:00Z",
  "ends_at": "2026-04-09T11:40:00Z",
  "active_miners": 8,
  "total_reward": 1.5
}
```

### GET /wallet/balance

Check wallet balance.

**Request**:
```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott-laptop"
```

**Response**:
```json
{
  "miner_id": "scott-laptop",
  "balance_rtc": 42.573
}
```

### POST /attest

Submit hardware fingerprint (miner only).

**Request**:
```bash
curl -sk -X POST https://rustchain.org/attest \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "scott-laptop",
    "architecture": "x86_64",
    "fingerprints": {...},
    "signature": "..."
  }'
```

**Response**:
```json
{
  "accepted": true,
  "next_attestation": 300
}
```

---

## Glossary

| Term | Definition |
|------|------------|
| **RIP-200** | RustChain Improvement Proposal 200 — the Proof-of-Antiquity consensus protocol |
| **Proof of Antiquity** | Consensus mechanism that rewards older hardware with higher multipliers |
| **Attestation** | Process of proving real hardware via fingerprint checks |
| **Epoch** | 10-minute reward cycle |
| **Antiquity Multiplier** | Hardware age bonus (0.0005x - 4.0x) |
| **RTC** | RustChain Token — native cryptocurrency |
| **wRTC** | Wrapped RTC on Solana (SPL token) |
| **DePIN** | Decentralized Physical Infrastructure Network |
| **BCOS** | Beacon Certified Open Source — license compliance system |

---

## Quick Start

### Install Miner

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

### Check Balance

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### View Explorer

https://rustchain.org/explorer

---

## Contributing

### First PR (10 RTC Bonus)

New contributors get **10 RTC** for their first merged PR:
- Fix a typo in any `.md` file
- Add a missing link
- Clarify confusing instructions
- Update outdated version numbers

### Bounty Tiers

| Tier | RTC Range | Examples |
|------|-----------|----------|
| Micro | 1-10 RTC | Docs fixes, typos |
| Standard | 20-50 RTC | Features, integrations |
| Major | 75-100 RTC | Security, protocol |
| Critical | 100-200 RTC | Vulnerabilities |

**Browse bounties**: https://github.com/Scottcjn/rustchain-bounties/issues

---

## Resources

- **GitHub**: https://github.com/Scottcjn/Rustchain
- **Bounties**: https://github.com/Scottcjn/rustchain-bounties
- **Explorer**: https://rustchain.org/explorer
- **Whitepaper**: `docs/WHITEPAPER.md`
- **BoTTube**: https://bottube.ai (AI video platform)

---

*Last updated: 2026-04-09*  
*Protocol version: RIP-200*
