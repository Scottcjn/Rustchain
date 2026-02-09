# RustChain Architecture Overview

System architecture and design documentation for RustChain blockchain.

---

## Table of Contents

- [System Overview](#system-overview)
- [Core Components](#core-components)
- [Consensus Mechanism](#consensus-mechanism)
- [Network Architecture](#network-architecture)
- [Data Flow](#data-flow)
- [Security Model](#security-model)
- [Scalability](#scalability)
- [Technology Stack](#technology-stack)

---

## System Overview

RustChain is a Proof-of-Antiquity blockchain that rewards vintage hardware preservation through hardware fingerprinting and time-weighted consensus.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RustChain Network                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │   Miners     │      │ Attestation  │      │     Ergo     │ │
│  │  (G4/G5/x86) │─────▶│    Nodes     │─────▶│   Anchor     │ │
│  └──────────────┘      └──────────────┘      └──────────────┘ │
│         │                      │                      │         │
│         │ Fingerprint          │ Epoch Settlement     │         │
│         │ Attestation          │ Hash                 │         │
│         ▼                      ▼                      ▼         │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │  Hardware    │      │   Rewards    │      │  Immutable   │ │
│  │ Validation   │      │ Distribution │      │   Ledger     │ │
│  └──────────────┘      └──────────────┘      └──────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **1 CPU = 1 Vote**: Each unique hardware device gets exactly one vote per epoch
2. **Antiquity Weighting**: Older hardware receives higher mining multipliers (0.8x - 2.5x)
3. **Anti-Emulation**: 6-point fingerprinting prevents VM/emulator spoofing
4. **Economic Rationality**: Cheaper to buy vintage hardware than to emulate it
5. **Immutable Anchoring**: Epoch settlements anchored to Ergo blockchain

---

## Core Components

### 1. Miner Layer

**Purpose**: Submit hardware attestations and earn RTC rewards

**Components**:
- Hardware fingerprint collector (6-point validation)
- Ed25519 signature generator
- Attestation submission client
- Balance monitoring

**Platforms**:
- Linux (x86_64, ppc64le)
- macOS (Intel, Apple Silicon, PowerPC)
- Windows (x86_64)
- IBM POWER8

**Key Files**:
- `miners/linux/rustchain_linux_miner.py`
- `miners/macos/rustchain_mac_miner_v2.4.py`
- `miners/windows/rustchain_windows_miner.py`
- `miners/linux/fingerprint_checks.py`

### 2. Attestation Node Layer

**Purpose**: Validate hardware fingerprints and manage epoch consensus

**Components**:
- Flask REST API server
- SQLite database
- Hardware fingerprint validator
- Epoch settlement engine
- P2P gossip protocol
- Ergo anchor client

**Key Files**:
- `node/rustchain_v2_integrated_v2.2.1_rip200.py` (main server)
- `node/rewards_implementation_rip200.py` (RIP-200 rewards)
- `node/rustchain_p2p_gossip.py` (P2P sync)
- `node/rustchain_ergo_anchor.py` (Ergo integration)
- `node/hardware_binding_v2.py` (anti-spoof)

### 3. Wallet Layer

**Purpose**: Manage RTC tokens and transactions

**Components**:
- Ed25519 keypair management
- BIP39 seed phrase generation
- Transaction signing
- Balance queries
- GUI interfaces

**Key Files**:
- `wallet/rustchain_wallet_secure.py` (secure GUI wallet)
- `wallet/rustchain_wallet_gui.py` (simple GUI wallet)
- `wallet/rustchain_wallet_ppc.py` (PowerPC wallet)

### 4. Blockchain Anchor Layer

**Purpose**: Provide immutability through Ergo blockchain anchoring

**Components**:
- Ergo node client
- Settlement hash generator
- Transaction broadcaster
- Verification system

**Key Files**:
- `node/rustchain_ergo_anchor.py`
- `ergo-anchor/rustchain_ergo_anchor.py`

---

## Consensus Mechanism

### RIP-200: Proof-of-Attestation

**Overview**: 1 CPU = 1 Vote, weighted by hardware antiquity

```
┌─────────────────────────────────────────────────────────────┐
│                    Epoch Lifecycle (24 hours)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Slot 0-143 (10 min/slot):                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Miners submit attestations                        │  │
│  │    - 6-point hardware fingerprint                    │  │
│  │    - Ed25519 signature                               │  │
│  │    - Hardware serial binding                         │  │
│  │                                                       │  │
│  │ 2. Node validates fingerprints                       │  │
│  │    - Check clock skew, cache timing, SIMD, etc.     │  │
│  │    - Detect VMs/emulators                           │  │
│  │    - Bind hardware to wallet                        │  │
│  │                                                       │  │
│  │ 3. Eligible miners enrolled in epoch                │  │
│  │    - Each unique hardware = 1 vote                  │  │
│  │    - Multiplier assigned by antiquity               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Slot 144 (Epoch Settlement):                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Calculate reward distribution                     │  │
│  │    - Epoch pot: 1.5 RTC                             │  │
│  │    - Weight = multiplier × 1 vote                   │  │
│  │    - Share = (miner_weight / total_weight) × pot   │  │
│  │                                                       │  │
│  │ 2. Distribute rewards to wallets                    │  │
│  │    - Update balance in database                     │  │
│  │    - Record in ledger                               │  │
│  │                                                       │  │
│  │ 3. Anchor settlement to Ergo                        │  │
│  │    - Generate settlement hash                       │  │
│  │    - Broadcast Ergo transaction                     │  │
│  │    - Store Ergo TX ID                               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Antiquity Multipliers

| Hardware Age | Tier | Multiplier | Example |
|--------------|------|------------|---------|
| 30+ years | Ancient | 3.5x | Commodore 64, Apple II |
| 25-29 years | Sacred | 3.0x | Pentium, PowerPC 601 |
| 20-24 years | Vintage | 2.5x | PowerPC G4, Pentium III |
| 15-19 years | Classic | 2.0x | Core 2 Duo, PowerPC G5 |
| 10-14 years | Retro | 1.5x | First-gen Core i7 |
| 5-9 years | Modern | 1.0x | Skylake, Ryzen |
| 0-4 years | Recent | 0.8x | Current hardware |

**Decay Formula**: 15% annual decay for vintage hardware (>5 years old)

### Reward Calculation

```python
# For each epoch:
epoch_pot = 1.5 RTC

# Calculate total weight
total_weight = sum(miner.multiplier for miner in enrolled_miners)

# Distribute rewards
for miner in enrolled_miners:
    miner_weight = miner.multiplier × 1  # 1 vote per hardware
    miner_share = (miner_weight / total_weight) × epoch_pot
    miner.balance += miner_share
```

**Example**:
```
Epoch 61:
- PowerPC G4 (2.5x): 0.30 RTC
- PowerPC G5 (2.0x): 0.24 RTC
- Modern x86 (1.0x): 0.12 RTC
- Total: 0.66 RTC distributed (44% of pot)
```

---

## Network Architecture

### Node Topology

```
┌─────────────────────────────────────────────────────────────┐
│                     RustChain Network                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Primary Node (50.28.86.131)                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ - Full attestation validation                        │  │
│  │ - Epoch settlement                                   │  │
│  │ - REST API (public)                                  │  │
│  │ - P2P gossip hub                                     │  │
│  │ - Database: rustchain_v2.db                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          │ P2P Gossip                       │
│                          │                                  │
│         ┌────────────────┼────────────────┐                │
│         │                │                │                │
│         ▼                ▼                ▼                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│  │ Relay    │    │ Relay    │    │ Archive  │            │
│  │ Node 1   │◄──▶│ Node 2   │◄──▶│ Node     │            │
│  └──────────┘    └──────────┘    └──────────┘            │
│       │               │                │                   │
│       │               │                │                   │
│       ▼               ▼                ▼                   │
│  ┌─────────────────────────────────────────┐              │
│  │         Miner Network (1000s)           │              │
│  │  - Linux miners                         │              │
│  │  - macOS miners                         │              │
│  │  - PowerPC miners                       │              │
│  │  - Windows miners                       │              │
│  └─────────────────────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### P2P Gossip Protocol

**Message Types**:
1. **PING/PONG** - Health checks
2. **PEER_ANNOUNCE** - Peer discovery
3. **INV_ATTESTATION** - Attestation announcement (hash only)
4. **GET_ATTESTATION** - Request full attestation data
5. **INV_EPOCH** - Epoch settlement announcement
6. **GET_EPOCH** - Request epoch data

**Gossip Flow**:
```
Node A                    Node B                    Node C
  |                         |                         |
  |--- INV (attest hash) -->|                         |
  |                         |--- INV (attest hash) -->|
  |                         |                         |
  |                         |<-- GETDATA -------------|
  |                         |                         |
  |                         |--- DATA (full attest) ->|
  |                         |                         |
```

**CRDT State Merging**:
- Conflict-free replicated data types
- Eventual consistency
- No single point of failure
- Byzantine fault tolerant (BFT)

---

## Data Flow

### Attestation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Attestation Lifecycle                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Miner collects fingerprint                             │
│     ┌──────────────────────────────────────────────────┐   │
│     │ - Clock skew: drift_ppm, jitter_ns              │   │
│     │ - Cache timing: L1/L2/L3 latency                │   │
│     │ - SIMD identity: instruction set, pipeline bias │   │
│     │ - Thermal entropy: idle/load temp, variance     │   │
│     │ - Instruction jitter: mean, stddev              │   │
│     │ - Behavioral heuristics: hypervisor detection   │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  2. Sign with Ed25519                                      │
│     ┌──────────────────────────────────────────────────┐   │
│     │ message = fingerprint + timestamp + miner_id    │   │
│     │ signature = Ed25519_sign(message, private_key)  │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  3. Submit to node                                         │
│     ┌──────────────────────────────────────────────────┐   │
│     │ POST /attest/submit                             │   │
│     │ {                                               │   │
│     │   "miner_id": "...",                           │   │
│     │   "fingerprint": {...},                        │   │
│     │   "signature": "..."                           │   │
│     │ }                                               │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  4. Node validates                                         │
│     ┌──────────────────────────────────────────────────┐   │
│     │ - Verify Ed25519 signature                      │   │
│     │ - Check 6-point fingerprint                     │   │
│     │ - Detect VM/emulator (thermal, hypervisor)      │   │
│     │ - Bind hardware serial to wallet                │   │
│     │ - Calculate antiquity multiplier                │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  5. Enroll in epoch                                        │
│     ┌──────────────────────────────────────────────────┐   │
│     │ - Add to miner_registry table                   │   │
│     │ - Record attestation in attestations table      │   │
│     │ - Increment enrolled_miners count               │   │
│     │ - Return multiplier to miner                    │   │
│     └──────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Transaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Transaction Lifecycle                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Create transaction                                     │
│     ┌──────────────────────────────────────────────────┐   │
│     │ from_address = "sender_RTC"                     │   │
│     │ to_address = "recipient_RTC"                    │   │
│     │ amount_rtc = 5.0                                │   │
│     │ nonce = current_timestamp                       │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  2. Sign transaction                                       │
│     ┌──────────────────────────────────────────────────┐   │
│     │ message = from + to + amount + nonce            │   │
│     │ signature = Ed25519_sign(message, private_key)  │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  3. Submit to node                                         │
│     ┌──────────────────────────────────────────────────┐   │
│     │ POST /wallet/transfer/signed                    │   │
│     │ {                                               │   │
│     │   "from_address": "...",                       │   │
│     │   "to_address": "...",                         │   │
│     │   "amount_rtc": 5.0,                           │   │
│     │   "nonce": 1739112225,                         │   │
│     │   "signature": "...",                          │   │
│     │   "public_key": "..."                          │   │
│     │ }                                               │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  4. Node validates                                         │
│     ┌──────────────────────────────────────────────────┐   │
│     │ - Verify Ed25519 signature                      │   │
│     │ - Check nonce not reused (replay protection)    │   │
│     │ - Verify sufficient balance                     │   │
│     │ - Validate addresses                            │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  5. Execute transaction                                    │
│     ┌──────────────────────────────────────────────────┐   │
│     │ - Deduct from sender balance                    │   │
│     │ - Add to recipient balance                      │   │
│     │ - Record in ledger table                        │   │
│     │ - Store nonce in nonces table                   │   │
│     │ - Generate TX hash                              │   │
│     └──────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  6. Return result                                          │
│     ┌──────────────────────────────────────────────────┐   │
│     │ {                                               │   │
│     │   "ok": true,                                   │   │
│     │   "tx_hash": "...",                            │   │
│     │   "new_balance_rtc": 7.456789                  │   │
│     │ }                                               │   │
│     └──────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Model

### Multi-Layer Security

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Architecture                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: Cryptographic Security                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ - Ed25519 signatures (256-bit security)             │  │
│  │ - SHA256 hashing                                    │  │
│  │ - Nonce-based replay protection                     │  │
│  │ - BIP39 seed phrases (128-256 bit entropy)          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Layer 2: Hardware Fingerprinting                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ - 6-point fingerprint validation                    │  │
│  │ - VM/emulator detection (thermal, hypervisor)       │  │
│  │ - Hardware serial binding                           │  │
│  │ - Drift detection and challenges                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Layer 3: Network Security                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ - TLS 1.2+ encryption                               │  │
│  │ - Rate limiting (100 req/min)                       │  │
│  │ - DDoS protection                                   │  │
│  │ - Firewall rules                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Layer 4: Consensus Security                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ - Byzantine Fault Tolerance (BFT)                   │  │
│  │ - CRDT state merging                                │  │
│  │ - Ergo blockchain anchoring                         │  │
│  │ - P2P gossip verification                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Attack Vectors & Mitigations

| Attack | Mitigation |
|--------|------------|
| **VM Spoofing** | 6-point fingerprint detects VMs (0.0000000025x multiplier) |
| **Sybil Attack** | Hardware serial binding (1 wallet per hardware) |
| **Replay Attack** | Nonce-based replay protection |
| **51% Attack** | BFT consensus + Ergo anchoring |
| **Double Spend** | Transaction nonce + database ACID properties |
| **DDoS** | Rate limiting + Nginx reverse proxy |
| **Man-in-Middle** | TLS encryption + Ed25519 signatures |

---

## Scalability

### Current Capacity

| Metric | Current | Target (1 year) |
|--------|---------|-----------------|
| **Miners** | 11,614 | 100,000 |
| **TPS** | ~0.1 | ~10 |
| **Database Size** | ~500 MB | ~5 GB |
| **API Requests** | ~1,000/day | ~100,000/day |
| **Nodes** | 3 | 10+ |

### Scaling Strategies

1. **Horizontal Scaling**
   - Add more relay nodes
   - P2P gossip distributes load
   - Read replicas for API queries

2. **Database Optimization**
   - Indexed queries
   - Periodic VACUUM
   - Archive old epochs

3. **Caching**
   - Redis for balance queries
   - CDN for static content
   - Memcached for API responses

4. **Sharding** (Future)
   - Geographic sharding
   - Hardware tier sharding
   - Epoch-based sharding

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Server** | Flask 2.3.0 | REST API endpoints |
| **Database** | SQLite 3.35+ | Persistent storage |
| **Crypto** | PyNaCl 1.5.0 | Ed25519 signatures |
| **HTTP Client** | Requests 2.31.0 | API calls |
| **Web Server** | Nginx 1.18+ | Reverse proxy, SSL |

### Frontend

| Component | Technology | Purpose |
|-----------|------------|---------|
| **GUI** | Tkinter | Wallet interfaces |
| **Explorer** | Flask + Jinja2 | Web-based explorer |
| **CLI** | Python argparse | Command-line tools |

### Blockchain

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Anchoring** | Ergo Platform | Immutable settlement |
| **Consensus** | RIP-200 PoA | Epoch-based rewards |
| **P2P** | Custom gossip | Node synchronization |

### Monitoring

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Metrics** | Prometheus | Time-series metrics |
| **Dashboards** | Grafana | Visualization |
| **Logging** | systemd journald | Log aggregation |

### Development

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language** | Python 3.8+ | Primary language |
| **VCS** | Git | Version control |
| **CI/CD** | GitHub Actions | Automation |
| **Testing** | pytest | Unit/integration tests |

---

## System Diagrams

### Component Interaction

```
┌─────────────────────────────────────────────────────────────┐
│                    Component Diagram                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐                                              │
│  │  Miner   │                                              │
│  └────┬─────┘                                              │
│       │ Attestation                                        │
│       ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              Attestation Node                        │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │ │
│  │  │ Flask API  │  │  Database  │  │  P2P Sync  │    │ │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │ │
│  │        │               │               │            │ │
│  │        └───────┬───────┴───────┬───────┘            │ │
│  │                │               │                    │ │
│  │        ┌───────▼───────┐  ┌────▼────────┐          │ │
│  │        │   Validator   │  │   Rewards   │          │ │
│  │        │  (RIP-PoA)    │  │  (RIP-200)  │          │ │
│  │        └───────┬───────┘  └────┬────────┘          │ │
│  │                │               │                    │ │
│  └────────────────┼───────────────┼────────────────────┘ │
│                   │               │                      │
│                   ▼               ▼                      │
│            ┌──────────────────────────────┐              │
│            │      Ergo Anchor             │              │
│            │  - Settlement hash           │              │
│            │  - Immutable ledger          │              │
│            └──────────────────────────────┘              │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Additional Resources

- **Protocol Specification**: `docs/PROTOCOL.md`
- **API Reference**: `docs/API_REFERENCE.md`
- **Node Operator Guide**: `docs/NODE_OPERATOR_GUIDE.md`
- **RIP Documents**: `rips/docs/`

---

**Last Updated**: February 9, 2026  
**Architecture Version**: 2.2.1-rip200
