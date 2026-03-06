---
title: "RIP-0302: Cross-Epoch Reputation & Loyalty Rewards"
author: Scott Boudreaux (Elyan Labs)
status: Draft
type: Standards Track
category: Core
created: 2026-03-06
requires: RIP-0001, RIP-0007, RIP-0200, RIP-0201
license: Apache 2.0
---

# Summary

RIP-0302 introduces a **Cross-Epoch Reputation System** that rewards miners for long-term loyalty, consistent participation, and honest behavior across multiple epochs. This system creates a cumulative reputation score that compounds over time, making sustained honest mining more profitable than short-term gaming or fleet operations.

**Key Innovation:** Reputation is earned through consistent epoch participation and lost through misbehavior, creating a "skin in the game" mechanism that aligns miner incentives with network health.

# Abstract

RustChain's Proof-of-Antiquity consensus (RIP-0001) rewards hardware age, and the Fleet Immune System (RIP-201) prevents coordinated attacks. However, there's no mechanism to reward **temporal loyalty** — miners who consistently participate epoch after epoch.

RIP-0302 defines:

1. **Reputation Points (RP)** — earned per epoch of honest participation
2. **Reputation Multiplier** — compounds with antiquity multiplier for bonus rewards
3. **Reputation Decay** — lost through misbehavior or extended absence
4. **Loyalty Tiers** — milestone bonuses at 10, 50, 100, 500 epochs
5. **Reputation-Weighted Settlement** — reputation affects epoch reward distribution

# Motivation

## Why Reputation Matters

Current RustChain economics reward:
- **Old hardware** (via antiquity multiplier)
- **Diverse hardware** (via fleet bucket split)

But they don't reward:
- **Consistency** — showing up every epoch
- **Loyalty** — long-term participation
- **Good behavior** — clean attestation history

This creates a gap where a miner could:
1. Join for one epoch, collect rewards
2. Leave for 100 epochs
3. Return with full rewards, no penalty

RIP-0302 closes this gap by making **continuous participation valuable**.

## Economic Impact

| Miner Type | Without RIP-302 | With RIP-302 |
|------------|-----------------|--------------|
| Solo G4 (100 epochs) | 1.0x multiplier | 1.0x × 1.5x = 1.5x |
| Fleet (500 boxes, 5 epochs) | 1.0x multiplier | 1.0x × 1.05x = 1.05x |
| New miner (1 epoch) | 1.0x multiplier | 1.0x × 1.0x = 1.0x |
| Returning after 50 epoch absence | 1.0x multiplier | 0.7x (decay penalty) |

## Design Philosophy

> "Time rewards the faithful. Reputation is earned epoch by epoch, lost in a moment."

# Specification

## 1. Reputation Points (RP) System

### 1.1 Earning Reputation

Miners earn Reputation Points each epoch based on participation quality:

| Action | RP Earned | Description |
|--------|-----------|-------------|
| Epoch enrollment | +1 RP | Successfully enrolled in epoch |
| Clean attestation | +1 RP | All fingerprint checks passed |
| Full epoch participation | +3 RP | Participated entire epoch window |
| On-time settlement | +1 RP | Reward claimed within settlement window |
| Challenge response | +1 RP | Successfully responded to validator challenge |

**Maximum RP per epoch:** 7 RP

### 1.2 Reputation Score Calculation

```
reputation_score = min(5.0, 1.0 + (total_rp / 100))
```

- Starts at 1.0 (baseline)
- Caps at 5.0 (maximum reputation)
- Requires 400 RP to reach cap (≈57 epochs of perfect participation)

### 1.3 Reputation Multiplier

```
reputation_multiplier = 1.0 + ((reputation_score - 1.0) × 0.25)
```

| Reputation Score | Reputation Multiplier | Epochs to Achieve |
|------------------|----------------------|-------------------|
| 1.0 | 1.00x | 0 (new miner) |
| 2.0 | 1.25x | ~100 epochs |
| 3.0 | 1.50x | ~200 epochs |
| 4.0 | 1.75x | ~300 epochs |
| 5.0 | 2.00x | ~400 epochs |

## 2. Loyalty Tiers

Miners unlock loyalty bonuses at milestone epoch counts:

| Tier | Epochs | Bonus | Badge |
|------|--------|-------|-------|
| Bronze | 10 | +5% reward boost | `loyal_bronze` |
| Silver | 50 | +10% reward boost | `loyal_silver` |
| Gold | 100 | +20% reward boost | `loyal_gold` |
| Platinum | 500 | +50% reward boost | `loyal_platinum` |
| Diamond | 1000 | +100% reward boost | `loyal_diamond` |

### 2.1 Loyalty Bonus Calculation

```
loyalty_bonus = 1.0 + tier_bonus_percentage

Where tier_bonus_percentage:
  - Bronze (10 epochs): 0.05
  - Silver (50 epochs): 0.10
  - Gold (100 epochs): 0.20
  - Platinum (500 epochs): 0.50
  - Diamond (1000 epochs): 1.00
```

### 2.2 Combined Multiplier

```
final_multiplier = aged_antiquity_multiplier × reputation_multiplier × loyalty_bonus
```

**Example:** A G4 miner (2.5x antiquity) with 200 epochs (3.0 rep score, Silver tier):
```
final_multiplier = 2.5 × 1.50 × 1.10 = 4.125x
```

## 3. Reputation Decay

### 3.1 Decay Triggers

Reputation decays under these conditions:

| Trigger | Decay Amount | Description |
|---------|--------------|-------------|
| Missed epoch | -5 RP | Failed to enroll/participate |
| Failed attestation | -10 RP | Fingerprint check failed |
| Fleet detection | -25 RP | Flagged as fleet operator |
| Challenge failure | -15 RP | Failed validator challenge |
| Extended absence (10+ epochs) | -50 RP | Lost reputation for abandonment |

### 3.2 Decay Formula

```
new_rp = max(0, current_rp - decay_amount)
new_reputation_score = min(5.0, 1.0 + (new_rp / 100))
```

### 3.3 Reputation Recovery

Miners can recover lost reputation through consistent participation:
- Recovery rate: 1.5× normal RP earning for first 10 epochs after decay
- Prevents permanent exile while maintaining penalty significance

## 4. Epoch Reward Distribution

### 4.1 Reputation-Weighted Distribution

Within each hardware bucket (RIP-201), rewards are distributed by:

```
miner_share = (miner_weight × reputation_multiplier) / bucket_total_weighted

Where:
  miner_weight = time_aged_antiquity_multiplier × loyalty_bonus
  bucket_total_weighted = sum(miner_weight × reputation_multiplier) for all miners in bucket
```

### 4.2 Example Calculation

**Epoch pot:** 1.5 RTC  
**Active buckets:** 3 (vintage_powerpc, modern, exotic)  
**Bucket share:** 1.5 / 3 = 0.5 RTC per bucket

**vintage_powerpc bucket:**
- Miner A (G4, 100 epochs): weight = 2.5 × 1.5 × 1.20 = 4.5
- Miner B (G3, 10 epochs): weight = 2.8 × 1.25 × 1.05 = 3.675
- Total weighted: 4.5 + 3.675 = 8.175

**Rewards:**
- Miner A: 0.5 × (4.5 / 8.175) = 0.275 RTC
- Miner B: 0.5 × (3.675 / 8.175) = 0.225 RTC

## 5. Reputation Data Structure

### 5.1 Miner Reputation Record

```json
{
    "miner_id": "RTC_vintage_g4_001",
    "total_rp": 250,
    "reputation_score": 3.5,
    "reputation_multiplier": 1.625,
    "epochs_participated": 150,
    "epochs_consecutive": 45,
    "loyalty_tier": "silver",
    "loyalty_bonus": 1.10,
    "last_epoch": 1847,
    "decay_events": [
        {
            "epoch": 1820,
            "reason": "missed_epoch",
            "rp_lost": 5,
            "new_rp": 245
        }
    ],
    "attestation_history": {
        "total": 150,
        "passed": 148,
        "failed": 2,
        "pass_rate": 0.987
    },
    "challenge_history": {
        "total": 12,
        "passed": 12,
        "failed": 0,
        "pass_rate": 1.0
    }
}
```

### 5.2 Global Reputation State

```json
{
    "current_epoch": 1847,
    "total_miners": 1247,
    "reputation_holders": {
        "diamond": 3,
        "platinum": 18,
        "gold": 142,
        "silver": 389,
        "bronze": 695
    },
    "average_reputation_score": 2.34,
    "total_rp_distributed": 1847293
}
```

## 6. API Endpoints

### 6.1 Reputation Query

**GET `/api/reputation/<miner_id>`**

```bash
curl -sS "https://rustchain.org/api/reputation/RTC_vintage_g4_001"
```

**Response:**
```json
{
    "miner_id": "RTC_vintage_g4_001",
    "reputation_score": 3.5,
    "reputation_multiplier": 1.625,
    "loyalty_tier": "silver",
    "epochs_participated": 150,
    "total_rp": 250
}
```

### 6.2 Reputation Leaderboard

**GET `/api/reputation/leaderboard`**

```bash
curl -sS "https://rustchain.org/api/reputation/leaderboard?limit=10"
```

**Response:**
```json
{
    "leaderboard": [
        {
            "rank": 1,
            "miner_id": "RTC_powerpc_legend",
            "reputation_score": 5.0,
            "loyalty_tier": "diamond",
            "epochs_participated": 1247
        },
        {
            "rank": 2,
            "miner_id": "RTC_vintage_g4_042",
            "reputation_score": 4.8,
            "loyalty_tier": "platinum",
            "epochs_participated": 892
        }
    ],
    "total_miners": 1247
}
```

### 6.3 Epoch Reputation Summary

**GET `/api/reputation/epoch/<epoch_number>`**

```bash
curl -sS "https://rustchain.org/api/reputation/epoch/1847"
```

**Response:**
```json
{
    "epoch": 1847,
    "participating_miners": 847,
    "average_reputation": 2.41,
    "tier_distribution": {
        "diamond": 2,
        "platinum": 15,
        "gold": 128,
        "silver": 312,
        "bronze": 390
    },
    "total_rp_earned": 4821,
    "decay_events": 23
}
```

### 6.4 Reputation Calculator

**POST `/api/reputation/calculate`**

```bash
curl -sS -X POST "https://rustchain.org/api/reputation/calculate" \
  -H 'Content-Type: application/json' \
  -d '{"current_rp": 250, "epochs_participated": 150, "decay_events": 1}'
```

**Response:**
```json
{
    "reputation_score": 3.5,
    "reputation_multiplier": 1.625,
    "loyalty_tier": "silver",
    "loyalty_bonus": 1.10,
    "next_tier_epochs": 50,
    "projected_multiplier_at_gold": 1.925
}
```

## 7. Integration with Existing Systems

### 7.1 RIP-200 (Round-Robin Consensus)

Reputation multiplier applies to the pro-rata reward distribution:
```
final_reward = base_reward × reputation_multiplier × loyalty_bonus
```

### 7.2 RIP-201 (Fleet Immune System)

Reputation is tracked **per miner** within fleet buckets. Fleet detection triggers reputation decay, making fleet operations even less profitable.

### 7.3 RIP-0007 (Entropy Fingerprinting)

Failed fingerprint checks trigger reputation decay:
- Failed attestation: -10 RP
- Failed challenge: -15 RP

### 7.4 RIP-0304 (Retro Console Mining)

Console miners via Pico bridge earn reputation normally. The Pico bridge ID is tracked for reputation continuity.

## 8. Security Considerations

### 8.1 Reputation Grinding

**Attack:** Miner creates multiple identities and farms reputation.

**Mitigation:**
- Each miner requires unique hardware fingerprint (RIP-0007)
- Fleet detection (RIP-201) limits multi-account profitability
- Reputation is per-miner, not per-IP

### 8.2 Reputation Trading

**Attack:** Miners sell high-reputation accounts.

**Mitigation:**
- Miner ID tied to hardware fingerprint
- Transfer triggers reputation reset (optional governance parameter)
- Economic value of reputation < cost of hardware replacement

### 8.3 Selective Participation

**Attack:** Miner only participates in high-reward epochs.

**Mitigation:**
- Missed epoch penalty (-5 RP) makes selective participation unprofitable
- Extended absence penalty (-50 RP) for 10+ epoch gaps

### 8.4 False Positive Decay

**Attack:** Malicious actors trigger false fleet detection on competitors.

**Mitigation:**
- Fleet detection requires multiple signals (IP, fingerprint, timing)
- Minimum 4+ miners for fleet detection activation
- Governance appeal process for disputed decay events

## 9. Economic Analysis

### 9.1 Long-Term Miner Advantage

| Miner Profile | Epochs | Rep Multiplier | Loyalty Bonus | Combined |
|---------------|--------|----------------|---------------|----------|
| New miner | 1 | 1.00x | 1.00x | 1.00x |
| Casual miner | 25 | 1.25x | 1.05x | 1.31x |
| Dedicated miner | 100 | 1.50x | 1.20x | 1.80x |
| Veteran miner | 500 | 1.75x | 1.50x | 2.63x |
| Legend miner | 1000 | 2.00x | 2.00x | 4.00x |

### 9.2 Fleet Operator Disadvantage

A fleet operator with 100 identical boxes:
- All flagged by fleet detection: -25 RP each
- Shared bucket reduces per-box rewards
- Reputation penalty compounds economic penalty

**Result:** Fleet ROI drops from already-unprofitable to absurdly-unprofitable.

### 9.3 Network Health Benefits

1. **Reduced churn** — miners stay for reputation accumulation
2. **Predictable participation** — miners show up every epoch
3. **Honest behavior** — miners avoid risky attestation strategies
4. **Community stability** — long-term miners become network stewards

## 10. Implementation Roadmap

### Phase 1: Core Reputation System
- [x] Reputation scoring module
- [x] Database schema for reputation records
- [x] API endpoints for queries
- [ ] Integration with epoch settlement

### Phase 2: Loyalty Tiers
- [x] Tier calculation logic
- [x] Badge/unlock system
- [ ] Explorer integration for tier display
- [ ] Loyalty bonus distribution

### Phase 3: Decay & Recovery
- [x] Decay event triggers
- [x] Recovery rate logic
- [ ] Governance appeal process
- [ ] Audit logging

### Phase 4: Advanced Features
- [ ] Reputation-based validator weighting
- [ ] Cross-miner reputation delegation (future)
- [ ] Reputation NFT badges (optional)
- [ ] Leaderboard gamification

## 11. Backwards Compatibility

RIP-0302 is **backwards compatible**:
- New miners start at 1.0x reputation multiplier (no penalty)
- Existing miners begin earning RP from activation epoch
- No changes to existing reward distribution for miners without reputation

**Migration path:**
1. Deploy reputation tracking module
2. Initialize all existing miners at 0 RP (1.0x baseline)
3. Begin RP accumulation from first post-activation epoch
4. Optional: Airdrop bonus RP to pre-activation miners (governance decision)

## 12. Reference Implementation

### Files Created
- `rips/docs/RIP-0302-cross-epoch-reputation.md` — This specification
- `rips/python/rustchain/reputation_system.py` — Core reputation module
- `node/rip_302_reputation_patch.py` — Server integration patch
- `tools/cli/reputation_commands.py` — CLI commands
- `tests/test_reputation_system.py` — Test suite
- `examples/reputation_demo.py` — Runnable demonstration

### Files Modified
- `node/rustchain_v2_integrated_v2.2.1_rip200.py` — Reputation integration
- `tools/cli/rustchain_cli.py` — Reputation CLI commands
- `docs/api/README.md` — API documentation

## 13. Governance Considerations

### 13.1 Configurable Parameters

These parameters can be adjusted via governance:

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `RP_PER_EPOCH_MAX` | 7 | 5-10 | Maximum RP per epoch |
| `REPUTATION_CAP` | 5.0 | 3.0-10.0 | Maximum reputation score |
| `FLEET_DECAY_RP` | -25 | -10 to -50 | Fleet detection penalty |
| `LOYALTY_TIER_10` | 0.05 | 0.01-0.10 | Bronze tier bonus |
| `LOYALTY_TIER_50` | 0.10 | 0.05-0.20 | Silver tier bonus |
| `LOYALTY_TIER_100` | 0.20 | 0.10-0.30 | Gold tier bonus |
| `LOYALTY_TIER_500` | 0.50 | 0.25-0.75 | Platinum tier bonus |
| `LOYALTY_TIER_1000` | 1.00 | 0.50-2.00 | Diamond tier bonus |

### 13.2 Airdrop Proposal

Governance may vote on an initial reputation airdrop:
- **Proposal:** Grant 50 RP to all miners with 10+ epochs pre-activation
- **Rationale:** Reward early adopters and bootstrap reputation system
- **Cost:** No direct cost — affects future reward distribution only

## 14. Testing & Validation

### 14.1 Unit Tests
- Reputation score calculation
- Multiplier computation
- Tier determination
- Decay event processing

### 14.2 Integration Tests
- Epoch settlement with reputation weighting
- API endpoint responses
- CLI command execution

### 14.3 Simulation Tests
- 1000-epoch miner lifecycle simulation
- Fleet operator profitability analysis
- Network health metrics over time

## 15. Acknowledgments

- **RIP-0001** (Sophia Core Team) — Proof of Antiquity foundation
- **RIP-0007** (Sophia Core Team) — Entropy fingerprinting framework
- **RIP-0200** — Round-robin consensus design
- **RIP-0201** — Fleet detection immune system
- **RustChain Community** — Feedback on reputation economics

## 16. Copyright

This document is licensed under Apache License, Version 2.0.

---

**Remember:** "Reputation is earned epoch by epoch, but can be lost in a moment. Mine responsibly."
