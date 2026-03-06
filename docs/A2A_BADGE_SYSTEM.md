# A2A Transaction Badge System

**Version:** 1.0  
**Status:** Implemented  
**Bounty:** #693  
**Last Updated:** 2026-03-07

---

## Table of Contents

1. [Overview](#overview)
2. [Badge Tiers](#badge-tiers)
3. [Getting Started](#getting-started)
4. [Verification Tooling](#verification-tooling)
5. [Integration Guide](#integration-guide)
6. [API Reference](#api-reference)
7. [Examples](#examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The A2A (Agent-to-Agent) Transaction Badge system recognizes and rewards agents participating in RustChain's machine economy through the x402 payment protocol.

### What are A2A Badges?

A2A badges are **soulbound NFTs** earned by agents based on their transaction activity. They represent:

- **Transaction Volume**: Number of A2A transactions completed
- **Network Building**: Unique agents transacted with
- **Protocol Usage**: Payment protocols utilized
- **Historical Significance**: Early adoption milestones

### Key Features

- ✅ **Automatic Tracking**: Transactions are tracked automatically
- ✅ **Real-time Verification**: Badge eligibility checked in real-time
- ✅ **Soulbound NFTs**: Badges are non-transferable (mostly)
- ✅ **Multi-Protocol Support**: Supports x402 and other protocols
- ✅ **CLI & API**: Both command-line and programmatic interfaces

---

## Badge Tiers

### Transaction Volume Badges

| Badge | Symbol | Rarity | Criteria |
|-------|--------|--------|----------|
| **A2A Pioneer** | 🤖💸🏆 | Legendary | First 100 agents with 10+ transactions |
| **A2A Trader** | 🤖💱📊 | Epic | 100+ A2A transactions |
| **A2A Merchant** | 🤖🏪💎 | Epic | 1,000+ A2A transactions |
| **A2A Whale** | 🤖🐋💰 | Legendary | 10,000+ A2A transactions |

### Network Badges

| Badge | Symbol | Rarity | Criteria |
|-------|--------|--------|----------|
| **A2A Connector** | 🤖🔗🌐 | Rare | 10+ unique counterparties |
| **A2A Hub** | 🤖🕸️👑 | Legendary | 100+ unique counterparties |

### Protocol Badges

| Badge | Symbol | Rarity | Criteria |
|-------|--------|--------|----------|
| **x402 Native** | 🤖⚡402 | Rare | 50+ transactions using only x402 |
| **Multi-Protocol** | 🤖🔄🔀 | Uncommon | Uses 3+ different protocols |

### Special Badges

| Badge | Symbol | Rarity | Criteria |
|-------|--------|--------|----------|
| **First A2A Payment** | 🤖1️⃣🎯 | Mythic | Participated in first network A2A tx |
| **A2A Volume King** | 🤖👑📈 | Legendary | Highest monthly volume (transferable) |

---

## Getting Started

### Prerequisites

- Python 3.8+
- RustChain node access (optional, for live verification)
- Wallet address to track

### Installation

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Install dependencies
pip install -r requirements.txt
```

### Quick Start

```bash
# List all available badges
python tools/a2a_badge_verifier.py list

# Check badge eligibility for a wallet
python tools/a2a_badge_verifier.py verify 0xYourWalletAddress

# Check progress toward a specific badge
python tools/a2a_badge_verifier.py progress 0xYourWalletAddress badge_a2a_trader

# Generate a full wallet report
python tools/a2a_badge_verifier.py report 0xYourWalletAddress --output report.json
```

---

## Verification Tooling

### Python Module

```python
from a2a_badge_verifier import A2ABadgeVerifier

# Initialize verifier
verifier = A2ABadgeVerifier()

# Verify a transaction
tx = verifier.verify_transaction(
    tx_hash="0x...",
    from_wallet="0x...",
    to_wallet="0x...",
    amount=100.0,
    timestamp=datetime.now(),
    protocol="x402"
)

# Check badge eligibility
badges = verifier.check_badge_eligibility("0xYourWallet")

# Get progress toward a badge
progress = verifier.get_progress("0xYourWallet", "badge_a2a_trader")
print(f"Progress: {progress.current_progress}/{progress.threshold}")
```

### Rust Implementation

```rust
use crate::a2a_badges::{A2ABadgeMinter, A2ATransaction, X402Validator};

// Initialize minter
let mut minter = A2ABadgeMinter::new();

// Record a transaction
let tx = A2ATransaction {
    tx_hash: "0x...".to_string(),
    from_wallet: "0x...".to_string(),
    to_wallet: "0x...".to_string(),
    amount: 100.0,
    timestamp: 1700000000,
    protocol: "x402".to_string(),
    block_height: 1000,
    tx_type: A2ATransactionType::X402Payment,
    verified: true,
};

minter.record_transaction(tx);

// Check and mint badges
let badges = minter.check_and_mint(&wallet, current_block, timestamp);
```

### x402 Header Validation

```python
from a2a_badge_verifier import A2ABadgeVerifier

verifier = A2ABadgeVerifier()

headers = {
    "X-Payment-Amount": "100.5",
    "X-Payment-From": "0x1234567890abcdef1234567890abcdef12345678",
    "X-Payment-To": "0xabcdef1234567890abcdef1234567890abcdef12",
    "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
}

is_valid, error = verifier.verify_x402_headers(headers)
if is_valid:
    print("✓ Valid x402 headers")
else:
    print(f"✗ Invalid: {error}")
```

---

## Integration Guide

### For Agent Developers

1. **Include x402 Headers** in all agent-to-agent payments:

```python
headers = {
    "X-Payment-Amount": str(amount),
    "X-Payment-From": your_wallet,
    "X-Payment-To": recipient_wallet,
    "X-Payment-TxHash": tx_hash,
    "X-Payment-Protocol": "x402",
    "X-Payment-Timestamp": str(int(time.time()))
}
```

2. **Track Your Transactions**:

```python
# Keep a local record of transactions
transactions = []

def make_payment(from_wallet, to_wallet, amount):
    tx_hash = send_payment(...)  # Your payment logic
    transactions.append({
        "tx_hash": tx_hash,
        "from": from_wallet,
        "to": to_wallet,
        "amount": amount,
        "timestamp": datetime.now()
    })
```

3. **Check Badge Progress**:

```python
# Periodically check badge eligibility
def check_badges(wallet):
    verifier = A2ABadgeVerifier()
    badges = verifier.check_badge_eligibility(wallet)
    
    earned = [b for b in badges if b.earned]
    for badge in earned:
        print(f"🏆 Earned: {badge.title}")
```

### For Node Operators

1. **Enable A2A Tracking** in node configuration:

```json
{
  "a2a_badges": {
    "enabled": true,
    "track_x402": true,
    "track_other_protocols": true,
    "schema_path": "schemas/relic_a2a_badges.json"
  }
}
```

2. **Export Transaction Data**:

```bash
# Export A2A transactions for analysis
python tools/a2a_badge_verifier.py report 0xWallet --output report.json
```

---

## API Reference

### A2ABadgeVerifier Class

#### `__init__(schema_path: Optional[str] = None)`

Initialize the verifier with optional custom schema path.

#### `verify_transaction(tx_hash, from_wallet, to_wallet, amount, timestamp, protocol, block_height) -> A2ATransaction`

Verify and record an A2A transaction.

**Parameters:**
- `tx_hash`: Transaction hash (0x-prefixed, 66 chars)
- `from_wallet`: Sender wallet address (0x-prefixed, 42 chars)
- `to_wallet`: Receiver wallet address
- `amount`: Transaction amount (positive float)
- `timestamp`: Transaction datetime
- `protocol`: Protocol used (default: "x402")
- `block_height`: Block height when transaction occurred

**Returns:** `A2ATransaction` object

**Raises:** `ValueError` if validation fails

#### `check_badge_eligibility(wallet_address: str) -> List[BadgeCriteria]`

Check which badges a wallet is eligible for.

**Returns:** List of `BadgeCriteria` objects

#### `get_progress(wallet_address: str, badge_id: str) -> Optional[BadgeCriteria]`

Get progress toward a specific badge.

**Returns:** `BadgeCriteria` with progress info, or `None`

#### `generate_badge_metadata(badge_id, wallet_address, earned_timestamp) -> Optional[Dict]`

Generate NFT metadata for an earned badge.

**Returns:** Badge metadata dictionary

#### `export_wallet_report(wallet_address: str) -> Dict`

Export comprehensive wallet report.

**Returns:** Dictionary with full wallet statistics and badge info

### BadgeCriteria Class

| Attribute | Type | Description |
|-----------|------|-------------|
| `badge_id` | str | Unique badge identifier |
| `title` | str | Display name |
| `criteria_type` | str | Type of criteria |
| `threshold` | int | Required value to earn |
| `current_progress` | int | Current progress |
| `earned` | bool | Whether badge is earned |
| `description` | str | Badge description |
| `rarity` | str | Badge rarity tier |

---

## Examples

### Example 1: Basic Usage

```python
from a2a_badge_verifier import A2ABadgeVerifier
from datetime import datetime

verifier = A2ABadgeVerifier()

# Simulate some transactions
for i in range(105):
    verifier.verify_transaction(
        tx_hash=f"0x{'a' * 64}{i}",
        from_wallet="0x1234567890abcdef1234567890abcdef12345678",
        to_wallet=f"0x{i:040x}",
        amount=10.0,
        timestamp=datetime.now(),
        protocol="x402",
        block_height=1000 + i
    )

# Check eligibility
badges = verifier.check_badge_eligibility("0x1234567890abcdef1234567890abcdef12345678")

print("Earned Badges:")
for badge in badges:
    if badge.earned:
        print(f"  ✓ {badge.title} ({badge.rarity})")
    else:
        pct = round(badge.current_progress / badge.threshold * 100, 1)
        print(f"  ○ {badge.title}: {pct}%")
```

### Example 2: CLI Usage

```bash
# List all badges
$ python tools/a2a_badge_verifier.py list

Available A2A Badges (10 total):

  🤖💸🏆 [Legendary] A2A Pioneer
     ID: badge_a2a_pioneer
     Awarded to agents among the first 100 to complete Agent-to-Agent transactions...

  🤖💱📊 [Epic] A2A Trader
     ID: badge_a2a_trader
     Awarded to agents who have completed 100+ verified A2A transactions...

# Verify wallet with mock data
$ python tools/a2a_badge_verifier.py verify 0x1234567890abcdef1234567890abcdef12345678 --mock

Badge Eligibility for 0x1234567890abcdef1234567890abcdef12345678:

EARNED (3):
  ✓ A2A Trader (Epic)
  ✓ A2A Connector (Rare)
  ✓ x402 Native (Rare)

PENDING (5):
  ○ A2A Merchant: 150/1000 (15.0%)
  ○ A2A Whale: 150/10000 (1.5%)
```

### Example 3: Generate Badge Metadata

```python
from a2a_badge_verifier import A2ABadgeVerifier
from datetime import datetime
import json

verifier = A2ABadgeVerifier()

metadata = verifier.generate_badge_metadata(
    badge_id="badge_a2a_pioneer",
    wallet_address="0x1234567890abcdef1234567890abcdef12345678",
    earned_timestamp=datetime.now()
)

print(json.dumps(metadata, indent=2))
```

### Example 4: Rust Integration

```rust
use a2a_badges::{A2ABadgeMinter, A2ATransaction, A2ATransactionType};

fn main() {
    let mut minter = A2ABadgeMinter::new();
    
    // Record transactions
    for i in 0..100 {
        let tx = A2ATransaction {
            tx_hash: format!("0x{}", "a".repeat(64)),
            from_wallet: "0x1234567890abcdef1234567890abcdef12345678".to_string(),
            to_wallet: format!("0x{:040x}", i),
            amount: 10.0,
            timestamp: 1700000000,
            protocol: "x402".to_string(),
            block_height: 1000 + i,
            tx_type: A2ATransactionType::X402Payment,
            verified: true,
        };
        minter.record_transaction(tx);
    }
    
    // Check and mint badges
    let badges = minter.check_and_mint(
        "0x1234567890abcdef1234567890abcdef12345678",
        1100,
        1700000000
    );
    
    println!("Minted {} badges", badges.len());
}
```

---

## Troubleshooting

### Common Issues

#### "Invalid wallet address format"

**Cause:** Wallet address must be 0x-prefixed, 42 characters (20 bytes hex)

**Solution:**
```python
# Correct format
wallet = "0x1234567890abcdef1234567890abcdef12345678"  # ✓

# Incorrect formats
wallet = "1234567890abcdef1234567890abcdef12345678"   # ✗ Missing 0x
wallet = "0x123"  # ✗ Too short
```

#### "Missing required headers"

**Cause:** x402 headers incomplete

**Solution:** Ensure all required headers are present:
- `X-Payment-Amount`
- `X-Payment-From`
- `X-Payment-To`
- `X-Payment-TxHash`

#### "Badge not found"

**Cause:** Invalid badge ID

**Solution:** Use `list` command to see available badge IDs:
```bash
python tools/a2a_badge_verifier.py list
```

#### "No data for wallet"

**Cause:** No transactions recorded for wallet

**Solution:** 
1. Record transactions first
2. Use `--mock` flag for testing with sample data

### Getting Help

- **Documentation:** See this file
- **Issues:** [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
- **Discord:** Join the RustChain Discord
- **Bounty Discussion:** [Bounty #693](bounties/bounty_693_a2a_transaction_badge.md)

---

## License

MIT License - See LICENSE file for details

---

*Part of RustChain Bounty #693 Implementation*
