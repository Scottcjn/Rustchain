# Bounty #2278: Ergo Anchor Chain Proof Verifier

**Claimed by:** @kuanglaodi2-sudo
**Reward:** 100 RTC
**Status:** OPEN

## Summary

Independent audit tool for verifying RustChain -> Ergo cross-chain anchors. Verifies that each anchor's commitment hash stored in the database matches the on-chain Ergo transaction and can be recomputed from `miner_attest_recent` data.

## Files

- `verify_anchors.py` — Main verification tool
- `README.md` — This file

## What It Does

For each anchor in `ergo_anchors` table:

1. **Reads** anchor record from `rustchain_v2.db`
2. **Fetches** the Ergo transaction from the Ergo node API (localhost:9053)
3. **Extracts** the Blake2b256 commitment from R4 register in transaction outputs
4. **Recomputes** the commitment from `miner_attest_recent` data at that epoch
5. **Compares**: `stored (DB) == on-chain (Ergo TX) == recomputed (miner data)`
6. **Reports** discrepancies with anchor IDs and detailed reasons

## Usage

```bash
# Verify all anchors (up to 50)
python verify_anchors.py

# Verify specific anchor
python verify_anchors.py --anchor-id 42

# Verify up to a RustChain height
python verify_anchors.py --rustchain-height 1000

# Use custom Ergo node
python verify_anchors.py --ergo-node http://my-ergo-node:9053

# Use custom DB path
python verify_anchors.py --db /path/to/rustchain_v2.db

# Offline mode (skip Ergo API, use local DB only)
python verify_anchors.py --offline

# JSON output (for CI/testing)
python verify_anchors.py --json

# Verbose debug output
python verify_anchors.py -v

# Combined: custom node, 100 anchors, JSON
python verify_anchors.py --ergo-node http://node:9053 --limit 100 --json
```

## Output Format

```
================================================================================
RustChain Ergo Anchor Verification — 3 anchor(s) checked
================================================================================

Anchor #1: TX abc123... | stored==onchain=[MATCH] | onchain==recomputed=[MATCH] | 10 miners
  RESULT: VERIFIED

Anchor #2: TX def456... | stored==onchain=[MATCH] | onchain==recomputed=[MISMATCH] | 8 miners
  RESULT: FAILED
  On-chain:   abc123def456...
  Recomputed: 789abc123456...

Anchor #3: TX ghi789... | [ERR] Ergo TX not found
--------------------------------------------------------------------------------
Summary: 1 verified, 1 failed, 1 errors
================================================================================
```

## JSON Output

```json
{
  "total": 3,
  "verified": 1,
  "failed": 1,
  "errors": 1,
  "anchors": [
    {
      "anchor_id": 1,
      "ergo_tx_id": "abc123...",
      "rustchain_height": 424,
      "tx_found": true,
      "stored_vs_onchain": "MATCH",
      "onchain_vs_recomputed": "MATCH",
      "miner_count": 10,
      "verified": true
    }
  ]
}
```

## R4 Register Format

The commitment hash is stored in Ergo box registers as:
- **Register**: R4 (some transactions use R5)
- **Format**: `0e20` + 32-byte Blake2b256 hash (hex: `0e` tag + `20` length + 64 hex chars = 68 chars total)
- **Also accepted**: raw 64-char hex (no prefix)

## Database Schema

### ergo_anchors (schema from rustchain_ergo_anchor.py)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| rustchain_height | INTEGER | RustChain block height |
| rustchain_hash | TEXT | RustChain block hash |
| commitment_hash | TEXT | Blake2b256 commitment hash |
| ergo_tx_id | TEXT | Ergo transaction ID |
| ergo_height | INTEGER | Ergo block height at confirmation |
| confirmations | INTEGER | Number of Ergo confirmations |
| status | TEXT | pending/confirming/confirmed |
| created_at | INTEGER | Unix timestamp |

### ergo_anchors (alternative schema from ergo_miner_anchor.py)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| tx_id | TEXT | Ergo transaction ID |
| commitment | TEXT | Blake2b256 commitment hash |
| miner_count | INTEGER | Number of miners in commitment |
| rc_slot | INTEGER | RustChain slot |
| created_at | INTEGER | Unix timestamp |

Both schemas are supported.

## Requirements

```bash
pip install requests
```

## Error Handling

- **Missing Ergo TX**: Reported as ERROR — TX not found
- **Missing R4 register**: Reported as ERROR — no commitment in TX outputs
- **MISMATCH (stored vs on-chain)**: Reported as FAIL — DB corrupted or TX overwritten
- **MISMATCH (on-chain vs recomputed)**: Reported as FAIL — miners data changed since anchor
- **No miner data**: Reported as ERROR — cannot recompute commitment
- **Offline mode**: Skips Ergo API calls, only reports what's available in DB

## Exit Codes

- `0` — All anchors verified successfully
- `1` — One or more anchors failed verification
- `1` — No anchors found (exit 0)

## Payout

- ETH/Base: `0x010A63e7Ee6E4925d2a71Bc93EA5374c9678869b`
- RTC: `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
- GitHub: @kuanglaodi2-sudo
