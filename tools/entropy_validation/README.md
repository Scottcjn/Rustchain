# Entropy Profile Temporal Validation

Validates that miner's fingerprint data evolves naturally over time.

## Features

- Store fingerprint history per miner
- Detect frozen profiles (emulator)
- Detect noisy profiles (random spoofing)
- Validate expected drift (real hardware)

## Usage

```bash
# Validate a specific miner
python entropy_validator.py --miner_id WALLET --db_path rustchain.db

# Analyze all miners
python entropy_validator.py --analyze_all --db_path rustchain.db
```

## Implementation

- `miner_fingerprint_history` table storing last 10 snapshots
- Temporal consistency scoring function
- Variance-based anomaly detection

## Reward

Implements **Bounty #19** - Entropy Profile Temporal Validation (40 RTC)

## License

MIT
