# RIP-302: Cross-Epoch Reputation & Loyalty Rewards

**Implementation Complete** ✓

This directory contains the complete implementation of RIP-302, the Cross-Epoch Reputation & Loyalty Rewards system for RustChain.

## Overview

RIP-302 introduces a reputation system that rewards miners for:
- **Long-term loyalty** — Consistent epoch participation
- **Honest behavior** — Clean attestation history
- **Network commitment** — Continuous operation over time

The system creates cumulative reputation scores that compound with existing antiquity multipliers, making sustained honest mining more profitable than short-term gaming.

## Quick Start

### 1. Run the Demonstration

```bash
cd /path/to/rustchain
python examples/reputation_demo.py
```

This runs through 6 scenarios showing:
- Basic reputation accumulation
- Loyalty tier progression
- Reputation decay and recovery
- Reward distribution impact
- Fleet operator economics
- Reputation projections

### 2. Run the Test Suite

```bash
python tests/test_reputation_system.py
```

The test suite includes:
- 80+ unit tests
- Integration tests
- Edge case tests
- Economic simulation tests

### 3. Use the CLI Tools

```bash
# Get miner reputation
python tools/cli/reputation_commands.py reputation RTC_vintage_g4_001

# View leaderboard
python tools/cli/reputation_commands.py leaderboard --limit 10

# Global statistics
python tools/cli/reputation_commands.py stats

# Calculate projection
python tools/cli/reputation_commands.py projection RTC_miner --epochs 500

# Calculator
python tools/cli/reputation_commands.py calculate --rp 150 --epochs 75
```

## File Structure

```
rips/docs/RIP-0302-cross-epoch-reputation.md    # Full specification
rips/python/rustchain/reputation_system.py      # Core Python module
node/rip_302_reputation_patch.py                # Server integration
tools/cli/reputation_commands.py                # CLI commands
examples/reputation_demo.py                     # Runnable demos
tests/test_reputation_system.py                 # Test suite
```

## Core Concepts

### Reputation Points (RP)

Miners earn RP each epoch:

| Action | RP Earned |
|--------|-----------|
| Epoch enrollment | +1 |
| Clean attestation | +1 |
| Full participation | +3 |
| On-time settlement | +1 |
| Challenge response | +1 |
| **Maximum per epoch** | **7** |

### Reputation Score & Multiplier

```
reputation_score = min(5.0, 1.0 + (total_rp / 100))
reputation_multiplier = 1.0 + ((reputation_score - 1.0) × 0.25)
```

| RP | Score | Multiplier |
|----|-------|------------|
| 0 | 1.0 | 1.00x |
| 100 | 2.0 | 1.25x |
| 200 | 3.0 | 1.50x |
| 300 | 4.0 | 1.75x |
| 400+ | 5.0 | 2.00x |

### Loyalty Tiers

| Tier | Epochs | Bonus |
|------|--------|-------|
| None | 0-9 | 1.00x |
| Bronze | 10-49 | 1.05x |
| Silver | 50-99 | 1.10x |
| Gold | 100-499 | 1.20x |
| Platinum | 500-999 | 1.50x |
| Diamond | 1000+ | 2.00x |

### Combined Multiplier

```
final_multiplier = antiquity_multiplier × reputation_multiplier × loyalty_bonus
```

**Example:** G4 miner (2.5x) with 200 RP (1.5x) and Gold tier (1.20x):
```
2.5 × 1.5 × 1.20 = 4.5x total multiplier
```

### Decay Events

| Trigger | RP Lost |
|---------|---------|
| Missed epoch | -5 |
| Failed attestation | -10 |
| Fleet detection | -25 |
| Challenge failure | -15 |
| Extended absence (10+ epochs) | -50 |

## Integration Guide

### For Node Operators

1. **Install the reputation module:**
   ```bash
   cp rips/python/rustchain/reputation_system.py /path/to/node/
   cp node/rip_302_reputation_patch.py /path/to/node/
   ```

2. **Apply the server patch:**
   ```bash
   python node/rip_302_reputation_patch.py --apply /path/to/rustchain_node.py
   ```

3. **Initialize the database:**
   ```python
   from rip_302_reputation_patch import RIP302Integration
   integration = RIP302Integration(db_path="reputation.db")
   ```

4. **Add hooks to your node:**
   ```python
   # On epoch start
   integration.on_epoch_start(epoch)
   
   # On attestation submit
   rep_data = integration.on_attestation_submit(miner_id, data, passed)
   
   # On epoch settlement
   modified_rewards = integration.on_epoch_settlement(epoch, miners, rewards)
   ```

### For Miner Operators

No changes required! The reputation system works automatically:
- Continue mining as normal
- Reputation accumulates in the background
- Rewards increase automatically based on your reputation

To check your reputation:
```bash
curl https://rustchain.org/api/reputation/YOUR_MINER_ID
```

## API Reference

### GET `/api/reputation/<miner_id>`

Get reputation data for a specific miner.

**Response:**
```json
{
  "miner_id": "RTC_vintage_g4_001",
  "total_rp": 250,
  "reputation_score": 3.5,
  "reputation_multiplier": 1.625,
  "loyalty_tier": "silver",
  "loyalty_bonus": 1.10,
  "epochs_participated": 150
}
```

### GET `/api/reputation/leaderboard`

Get reputation leaderboard.

**Parameters:**
- `limit` (optional): Number of entries (default: 10)
- `tier` (optional): Filter by tier

### GET `/api/reputation/stats`

Get global reputation statistics.

### GET `/api/reputation/epoch/<epoch>`

Get reputation summary for a specific epoch.

### POST `/api/reputation/calculate`

Calculate reputation metrics from input data.

**Body:**
```json
{
  "current_rp": 250,
  "epochs_participated": 150
}
```

## Economic Impact

### Solo Miner Advantage

| Profile | Epochs | Combined Mult | Reward Increase |
|---------|--------|---------------|-----------------|
| New miner | 1 | 1.00x | baseline |
| Casual | 25 | 1.31x | +31% |
| Dedicated | 100 | 1.80x | +80% |
| Veteran | 500 | 2.63x | +163% |
| Legend | 1000 | 4.00x | +300% |

### Fleet Operator Disadvantage

Fleet operators face compounded penalties:
1. **RIP-201 bucket split** — rewards shared among fleet
2. **Fleet detection decay** — -25 RP per box
3. **Lower loyalty** — fewer epochs per box
4. **Reduced multiplier** — lower reputation score

**Result:** A $5M fleet operation earns ~$27/year, with a payback period of ~182,648 years.

## Testing

### Run All Tests

```bash
python tests/test_reputation_system.py
```

### Run Specific Test Classes

```bash
python -m unittest tests.test_reputation_system.TestMinerReputation -v
python -m unittest tests.test_reputation_system.TestReputationSystem -v
```

### Test Coverage

The test suite covers:
- ✓ Reputation score calculation
- ✓ Multiplier computation
- ✓ Loyalty tier determination
- ✓ Decay event processing
- ✓ Epoch participation tracking
- ✓ Leaderboard generation
- ✓ State serialization
- ✓ Edge cases (negative RP, caps, etc.)
- ✓ Integration scenarios
- ✓ Economic simulations

## Configuration

These parameters can be adjusted via governance:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RP_PER_EPOCH_MAX` | 7 | Maximum RP per epoch |
| `REPUTATION_CAP` | 5.0 | Maximum reputation score |
| `DECAY_MISSED_EPOCH` | 5 | RP lost for missing epoch |
| `DECAY_FAILED_ATTESTATION` | 10 | RP lost for failed attestation |
| `DECAY_FLEET_DETECTION` | 25 | RP lost for fleet detection |
| `DECAY_CHALLENGE_FAILURE` | 15 | RP lost for failed challenge |
| `DECAY_EXTENDED_ABSENCE` | 50 | RP lost for extended absence |

## Troubleshooting

### Common Issues

**Q: My reputation isn't increasing**
- Ensure you're participating in every epoch
- Check that your attestations are passing
- Verify you're claiming rewards within the settlement window

**Q: I lost reputation unexpectedly**
- Check for missed epochs (gap > 10 triggers extended absence penalty)
- Verify your attestation pass rate
- Check if you were flagged by fleet detection

**Q: How do I recover lost reputation?**
- Continue consistent participation
- Recovery bonus (1.5x RP) applies for 10 epochs after decay
- Avoid further decay events

### Getting Help

- Review the full specification: `rips/docs/RIP-0302-cross-epoch-reputation.md`
- Run the demo: `python examples/reputation_demo.py`
- Check test examples: `tests/test_reputation_system.py`

## Governance

RIP-302 parameters can be adjusted through the RustChain governance process:

1. Submit governance proposal with parameter changes
2. Community voting period (7 days)
3. Sophia AI evaluation
4. Validator ratification
5. Implementation via patch update

## Future Enhancements

Potential future additions:
- [ ] Reputation NFT badges
- [ ] Cross-miner reputation delegation
- [ ] Reputation-based validator weighting
- [ ] Leaderboard gamification
- [ ] Reputation airdrop for early adopters

## References

- **RIP-0001**: Proof of Antiquity consensus
- **RIP-0007**: Entropy fingerprinting
- **RIP-0200**: Round-robin consensus
- **RIP-0201**: Fleet immune system
- **RIP-0304**: Retro console mining

## License

This implementation is licensed under Apache License, Version 2.0.

---

**Remember:** "Reputation is earned epoch by epoch, but can be lost in a moment. Mine responsibly."
