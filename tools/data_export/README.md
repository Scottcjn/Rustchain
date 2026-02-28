# RustChain Data Export Pipeline

Export RustChain attestation and reward data to CSV, JSON, or JSONL.

## Features

- 📊 Export miners, balances, epochs, network stats
- 📁 Multiple formats: CSV, JSON, JSONL
- 📅 Date range filtering
- ⚡ API-only mode (works remotely)

## Usage

```bash
# Export to CSV
python rustchain_export.py --format csv --output data/

# Export to JSON
python rustchain_export.py --format json --output data/

# Date range
python rustchain_export.py --from 2025-12-01 --to 2026-02-01
```

## Output Files

- `miners.csv/json/jsonl` - All miner info
- `balances.csv/json/jsonl` - Per-miner balances
- `epochs.csv/json/jsonl` - Epoch data
- `network_stats.json/jsonl` - Network statistics

## Reward

Implements **Bounty #49** - Attestation Data Export Pipeline (25 RTC)

## License

MIT
