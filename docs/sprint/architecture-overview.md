# RustChain Architecture Overview

> A technical reference for the RustChain network: consensus, topology, reward mechanics, and protocols.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RustChain Network                                │
│                                                                         │
│   ┌──────────┐     P2P Gossip     ┌──────────────┐                     │
│   │  Miner A │ ─────────────────► │              │                     │
│   └──────────┘                    │   Beacon     │                     │
│                                   │   Nodes      │                     │
│   ┌──────────┐     Attestation    │  (RIP-200)   │                     │
│   │  Miner B │ ─────────────────► │              │                     │
│   └──────────┘                    └──────┬───────┘                     │
│                                          │ Validated                   │
│   ┌──────────┐     Attestation           │ Attestations                │
│   │  Miner C │ ─────────────────►        │                             │
│   └──────────┘                    ┌──────▼───────┐                     │
│                                   │    Block     │                     │
│         ▲                         │   Producer   │                     │
│         │  Epoch Rewards          │              │                     │
│         │  (RTC payout)           └──────┬───────┘                     │
│         │                                │ Signed Block                │
│         │                         ┌──────▼───────┐                     │
│         └─────────────────────────│    Ledger    │                     │
│                                   │  (Ergo-     │                     │
│                                   │  anchored)  │                     │
│                                   └─────────────┘                     │
│                                                                         │
│   x402 Payment Layer ────────────────────────────── Any HTTP Client    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Data flow summary:**
1. **Miners** run hardware fingerprinting and submit attestations every 10 minutes
2. **Beacon Nodes** validate attestations (check authenticity, reject VMs/spoofing)
3. **Block Producer** bundles valid attestations into blocks
4. **Ledger** stores the canonical chain; settlement hashes are anchored to Ergo

---

## Proof of Antiquity (PoA)

Proof of Antiquity is RustChain's consensus mechanism. It rewards hardware age and physical authenticity — not hash rate.

### The Full Pipeline

```
Physical Hardware
      │
      ▼
┌─────────────────────────────────────────────────┐
│            Hardware Fingerprint                 │
│  ① Clock-skew & oscillator drift               │
│  ② Cache timing (L1/L2/L3 latency profile)     │
│  ③ SIMD unit identity (AltiVec/SSE/NEON)       │
│  ④ Thermal drift entropy                        │
│  ⑤ Instruction-path jitter map                 │
│  ⑥ Anti-emulation checks (VM/hypervisor detect)│
└───────────────────┬─────────────────────────────┘
                    │
                    ▼
         Multiplier Assigned
         (1.0× modern → 2.5× vintage PowerPC)
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│              Attestation Package                │
│  • miner_id  • hardware fingerprint hash        │
│  • timestamp • multiplier claim                 │
│  • signature (private key)                      │
└───────────────────┬─────────────────────────────┘
                    │  submitted every 10 min
                    ▼
          Beacon Node Validation
          (accept / reject / flag)
                    │
                    ▼
              Epoch (144 slots)
              ~24 hours total
                    │
                    ▼
         Epoch Settlement — Reward
         proportional to weight:
         share = (multiplier / total_weight) × 1.5 RTC
```

### Antiquity Multipliers

| Hardware Era | Example | Multiplier |
|-------------|---------|-----------|
| Pre-2000 vintage | Pentium III, 486 | 2.5× – 3.0× |
| PowerPC G4 (1999-2005) | Power Mac G4 | 2.5× |
| PowerPC G5 (2003-2006) | Power Mac G5 | 2.0× |
| Early x86 (2000-2008) | Pentium 4 | 1.5× |
| Core 2 era (2006-2011) | Core 2 Duo | 1.3× |
| Modern x86_64 | Current Intel/AMD | 1.0× |
| Apple Silicon | M1/M2/M3 | 1.2× |
| VM / Emulator | Any | ~0.000000001× |

---

## Fleet Detection (RIP-201)

RIP-201 is RustChain's "immune system" — it prevents reward farming via hardware spoofing, cloned attestations, or coordinated fleet attacks.

### How It Works

```
Incoming Attestation Stream
          │
          ▼
┌─────────────────────────────────────────┐
│          RIP-201 Fleet Detector         │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  Fingerprint Uniqueness Check    │   │
│  │  • Is this fingerprint seen      │   │
│  │    from >1 IP in this epoch?     │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │  Bucket Normalization (RIP-201b) │   │
│  │  • Are timing values suspiciously│   │
│  │    round / identical across IDs? │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │  Behavioral Heuristics           │   │
│  │  • Submission cadence too perfect│   │
│  │  • Identical jitter signatures   │   │
│  │  • Entropy values cluster tightly│   │
│  └──────────────────────────────────┘   │
└────────────┬──────────────┬─────────────┘
             │              │
        ✅ Clean        ⚠️ Flagged
             │              │
        Pass to         Quarantine &
        Block Producer  Rate-limit
                            │
                       Repeated flags
                            │
                       Permanent ban
                       (epoch-level)
```

### Key Rules

- One physical CPU = one reward slot per epoch (RIP-200 §3.1)
- Identical hardware fingerprints from different IPs → both flagged
- Suspiciously uniform timing buckets → bucket normalization applied
- After 3 flags in one epoch → miner banned for that epoch
- Repeat offenders → flagged for manual review

---

## Epoch Settlement

Epochs divide time into ~24-hour windows (144 slots × 10 minutes each). At the end of each epoch, rewards are calculated and distributed.

### Settlement Calculation

```python
# Pseudocode — see epoch-settlement.md for full spec

def settle_epoch(epoch_id):
    miners = get_active_miners(epoch_id)  # submitted attestation in last 20 min
    total_weight = sum(m.multiplier for m in miners)

    for miner in miners:
        share = (miner.multiplier / total_weight) * EPOCH_POT  # 1.5 RTC
        credit_wallet(miner.wallet, share)

    anchor_to_ergo(epoch_id, settlement_hash)
```

**Epoch pot:** 1.5 RTC distributed per epoch  
**Participation requirement:** At least one attestation in the final 20-minute window  
**Settlement delay:** ~5 minutes (Ergo anchoring latency)

---

## P2P Gossip Layer

Nodes communicate via a lightweight gossip protocol over TCP:

```
Node A ──── gossip ────► Node B
  ▲                        │
  │                        │ forward
  │                        ▼
  └───────────────────── Node C
```

**Message types propagated:**
- `ATTESTATION` — miner proof packages (TTL: current epoch)
- `BLOCK` — finalized block announcements
- `PEER_LIST` — known node addresses (for network discovery)
- `EPOCH_SIGNAL` — epoch boundary notifications
- `FLEET_FLAG` — RIP-201 ban propagation across nodes

**Protocol properties:**
- Fanout: each node forwards to ~8 peers
- Deduplication: message ID hash prevents re-broadcast loops
- Max TTL: 3 hops for attestations, 5 hops for blocks
- Transport: TCP with optional TLS (self-signed accepted)

---

## x402 Payment Protocol

RustChain implements [HTTP 402 / x402](https://x402.org) for machine-to-machine micropayments — enabling agent economy and API monetization.

### Flow

```
Client (Agent/User)           RustChain Node / Service
        │                              │
        │──── GET /api/premium ───────►│
        │                              │
        │◄─── 402 Payment Required ────│
        │     x-payment-details: ...   │
        │     amount: 0.01 RTC         │
        │     wallet: RTC...           │
        │                              │
        │──── POST /wallet/pay ───────►│  (signs with wallet key)
        │     x-payment-receipt: ...   │
        │                              │
        │──── GET /api/premium ───────►│
        │     Authorization: Bearer .. │
        │                              │
        │◄─── 200 OK + data ───────────│
```

**Use cases:**
- Agents paying for data feeds, compute, or storage on-chain
- API rate limiting with per-call micropayments
- Content gating on the BottuTube agent video platform
- Cross-node service billing in the agent economy (RIP-302)

---

## Component Summary

| Component | Role | Protocol |
|-----------|------|----------|
| Miner | Hardware attestation, PoA proof generation | HTTP POST to Beacon |
| Beacon Node | Validate attestations, run RIP-201 | P2P gossip + REST API |
| Block Producer | Bundle attestations → blocks | Internal |
| Ledger | Canonical chain storage | Ergo-anchored |
| x402 Layer | Micropayment authorization | HTTP 402 |
| wRTC Bridge | Cross-chain liquidity (Solana) | FlameBridge |

---

*See also: `docs/protocol-overview.md`, `docs/epoch-settlement.md`, `docs/hardware-fingerprinting.md`, `rips/`*
