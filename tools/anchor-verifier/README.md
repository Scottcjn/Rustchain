# Ergo Anchor Chain Proof Verifier

Independent audit tool that verifies RustChain's Ergo blockchain anchors are real and correct.

## What It Does

1. **Reads** `ergo_anchors` table from `rustchain_v2.db`
2. **Fetches** actual Ergo transactions from node API
3. **Extracts** commitment hash from R5 register
4. **Recomputes** commitment from local attestation data
5. **Compares**: stored == on-chain == recomputed
6. **Reports** discrepancies with anchor IDs and reasons

## Usage

```bash
# Verify all anchors
python verify_anchors.py

# Custom paths
python verify_anchors.py --db /path/to/rustchain_v2.db --ergo http://node:9053

# Offline mode (DB-only, no Ergo API)
python verify_anchors.py --offline

# Last 10 anchors
python verify_anchors.py --limit 10

# JSON output (for CI/automation)
python verify_anchors.py --json
```

## Output

```
Anchor #1: TX 731d5d87ab12... | Commitment MATCH ✓ | 10 miners | Epoch 424
Anchor #2: TX a8f3c912de45... | Commitment MISMATCH ✗ | 3 miners | Epoch 425
  → Expected: abc123... Got: def456...
Anchor #3: TX pending12345... | Commitment TX_NOT_FOUND ? | 0 miners | Epoch 426

Summary: 1/3 anchors verified, 1 mismatches, 1 TX not found
```

## Tests

```bash
python -m pytest tools/anchor-verifier/test_verify_anchors.py -v
# 32 passed
```

## Exit Codes

- `0`: All anchors verified (or offline-only)
- `1`: Mismatches found

## Bounty

Closes https://github.com/Scottcjn/rustchain-bounties/issues/2278
