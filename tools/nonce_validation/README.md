# Nonce Binding & Attestation Replay Prevention

Server-side nonce tracking and replay prevention for RustChain attestation protocol.

## Features

- Server-side nonce tracking table (`used_nonces`)
- Duplicate nonce rejection
- Timestamp freshness validation (±60s default)
- Optional challenge-response flow
- TTL-based nonce expiry

## Usage

```bash
# Validate a nonce
python nonce_validator.py --db_path rustchain.db --miner_id wallet123 --nonce abc123 --timestamp 1700000000

# Show statistics
python nonce_validator.py --db_path rustchain.db --stats
```

## Implementation

- O(1) nonce lookup via indexed table
- Automatic expired nonce cleanup
- Configurable freshness window
- Challenge-response flow support

## Reward

Implements **Bounty #18** - Nonce Binding & Attestation Replay Prevention (40 RTC)

## License

MIT
