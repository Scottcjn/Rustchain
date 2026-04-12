# RustChain Development Guide

## Project Overview

RustChain is a Proof-of-Antiquity blockchain that rewards vintage hardware. Older computers earn more than newer ones.

## Quick Start

```bash
# Install miner
curl -fsSL https://rustchain.org/install.sh | bash -s -- --wallet YOUR-NAME

# Run miner (24h minimum for rewards)
rustchain-miner --wallet YOUR-NAME
```

## Key Commands

```bash
# Check wallet balance (use miner_id, NOT wallet_id)
curl "https://50.28.86.131/wallet/balance?miner_id=YOUR-NAME"

# Check epoch info
curl "https://50.28.86.131/epoch"
```

## Important Notes

- API parameter is `miner_id` — NOT `wallet_id` (common mistake!)
- Node endpoint: https://50.28.86.131
- Minimum mining time: 24 hours for rewards
- Hardware fingerprint checks: 6 types, 4-of-6 needed per epoch

## Bounty Hunting

See [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties) for open bounties.
Payment: RTC tokens sent to your registered wallet name.
