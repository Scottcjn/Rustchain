# RustChain Network Snapshot Tool

A lightweight daily snapshot utility for the RustChain network.

## Features

- 📸 **Single-shot snapshots** — capture current network state
- 📊 **Daily CSV logs** — append miner data for trend analysis
- 🔄 **Watch mode** — periodic monitoring (e.g., every 60 seconds)
- 🌐 **Node-configurable** — works with any RustChain node endpoint
- 📁 **JSON + CSV export** — machine-readable and spreadsheet-friendly

## Usage

```bash
# Single snapshot
python rustchain_snapshot.py

# Daily CSV log
python rustchain_snapshot.py --daily

# Watch mode (60-second interval)
python rustchain_snapshot.py --watch 60

# Custom node + quiet mode (cron-safe)
python rustchain_snapshot.py --node https://your-node.example --quiet
```

## Output

- **JSON**: `snapshots/snapshot_YYYYMMDD_HHMMSS.json`
- **CSV**: `snapshots/miners_YYYYMMDD.csv`

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## License

MIT
