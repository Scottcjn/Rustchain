# Bounty #693: A2A Transaction Badge

**Status:** Open  
**Reward:** Uber Dev Badge + RUST 1000 + A2A Pioneer Badge (NFT)  
**Difficulty:** Major  
**Category:** Badge System / Agent Economy  

---

## Overview

Implement a comprehensive badge system for recognizing and rewarding Agent-to-Agent (A2A) transactions on the RustChain network. This badge system will track, verify, and celebrate milestones in machine-to-machine economic activity using the x402 payment protocol.

---

## Background

RustChain agents now own Coinbase Base wallets and make machine-to-machine payments using the **x402 protocol** (HTTP 402 Payment Required). As the agent economy grows, we need a way to:

1. **Track** A2A transaction milestones
2. **Verify** legitimate agent-to-agent payments
3. **Reward** early adopters and high-volume agents
4. **Display** achievements via NFT badges

---

## Deliverables

### 1. Badge Criteria & Progress Logic

Define clear criteria for A2A transaction badges:

| Badge Tier | Criteria | Description |
|------------|----------|-------------|
| **A2A Pioneer** | First 100 A2A transactions | Early adopter of agent economy |
| **A2A Trader** | 100+ A2A transactions | Regular participant |
| **A2A Merchant** | 1,000+ A2A transactions | High-volume agent |
| **A2A Whale** | 10,000+ A2A transactions | Elite transaction volume |
| **A2A Connector** | Connected to 10+ unique agents | Network builder |
| **A2A Hub** | Connected to 100+ unique agents | Central network node |
| **x402 Native** | Only uses x402 protocol | Protocol purist |
| **Multi-Protocol** | Uses x402 + other protocols | Protocol agnostic |

### 2. Verification Tooling

Create tools to verify A2A transactions:

- **Transaction Validator**: Verify x402 payment headers
- **Agent Identity Checker**: Confirm wallet ownership
- **Milestone Tracker**: Track progress toward badge criteria
- **CLI Tool**: `clawrtc badge a2a verify <wallet>`

### 3. Documentation

- Badge specification document
- Integration guide for agent developers
- API reference for verification endpoints
- Example implementations

### 4. Tests & Examples

- Unit tests for verification logic
- Integration tests with mock x402 transactions
- Example agent implementations
- Sample badge metadata

---

## Technical Requirements

### x402 Protocol Integration

Agents must include proper x402 headers:

```http
HTTP/1.1 402 Payment Required
X-Payment-Amount: 100
X-Payment-From: 0x...
X-Payment-To: 0x...
X-Payment-TxHash: 0x...
```

### Badge Metadata Schema

```json
{
  "nft_id": "badge_a2a_pioneer",
  "title": "A2A Pioneer",
  "class": "Transaction Relic",
  "description": "Awarded to agents among the first 100 to complete Agent-to-Agent transactions using x402 protocol.",
  "emotional_resonance": {
    "state": "digital trailblazer",
    "trigger": "Agent completes 10+ verified A2A transactions",
    "timestamp": "2026-03-07T00:00:00Z"
  },
  "symbol": "🤖💸🏆",
  "visual_anchor": "two robot hands exchanging glowing tokens over x402 protocol glyph",
  "rarity": "Legendary",
  "soulbound": true,
  "criteria": {
    "type": "a2a_transactions",
    "threshold": 10,
    "timeframe": "all_time",
    "verification": "x402_headers"
  }
}
```

### Verification API

```python
from rustchain_badges import A2ABadgeVerifier

verifier = A2ABadgeVerifier()

# Verify a single transaction
result = verifier.verify_transaction(tx_hash, wallet_address)

# Check badge eligibility
badges = verifier.check_eligibility(wallet_address)

# Get progress toward next badge
progress = verifier.get_progress(wallet_address, "a2a_trader")
```

---

## Acceptance Criteria

- [ ] All badge tiers defined with clear criteria
- [ ] Verification tooling implemented and tested
- [ ] Documentation complete with examples
- [ ] Tests pass with >90% coverage
- [ ] Integration with existing badge system
- [ ] CLI tool functional
- [ ] Example agent implementation provided

---

## Resources

- [x402 Protocol Specification](https://github.com/coinbase/x402)
- [Existing Badge System](rips/src/nft_badges.rs)
- [Agent Wallets Documentation](docs/agent_wallets.md)
- [Base Network](https://base.org)

---

## Submission Guidelines

1. Fork the RustChain repository
2. Implement all deliverables
3. Submit a PR with comprehensive tests
4. Include example transaction logs
5. Tag maintainers for review

**Questions?** Open an issue or join the Discord.

---

*Last updated: 2026-03-07*
