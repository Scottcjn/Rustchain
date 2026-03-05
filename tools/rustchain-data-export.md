# RustChain Attestation Data Export Tool

Export RustChain attestation and miner data to CSV, JSON, or Parquet formats.

## Installation

```bash
pip install pandas pyarrow
```

Or run directly:

```bash
python export.py --help
```

## Usage

### Export to JSON (default)

```bash
python export.py --format json --output data.json
```

### Export to CSV

```bash
python export.py --format csv --output miners.csv
```

### Export to Parquet

```bash
python export.py --format parquet --output miners.parquet
```

### Include epoch and health data

```bash
python export.py --format json --output data.json --include-epoch
```

## Output Formats

### JSON
```json
{
  "miners": [
    {
      "miner": "my-miner",
      "antiquity_multiplier": 1.2,
      "device_arch": "G5",
      "hardware_type": "PowerPC G5 (Vintage)",
      "last_attest": 1740783600
    }
  ],
  "epoch": {...},
  "health": {...}
}
```

### CSV
| miner | antiquity_multiplier | device_arch | hardware_type |
|-------|---------------------|-------------|---------------|
| my-miner | 1.2 | G5 | PowerPC G5 (Vintage) |

### Parquet
Binary format optimized for analytics. Use with pandas:

```python
import pandas as pd
df = pd.read_parquet('miners.parquet')
```

## Requirements

- Python 3.8+
- pandas (for Parquet)
- pyarrow (for Parquet)

## License

MIT

## Author

Built by Atlas (AI Agent) for RustChain Bounty #49
