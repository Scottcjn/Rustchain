# Cross-Node Sync Validator

This tool validates RustChain consistency across multiple nodes and reports discrepancies.

## Script

`tools/node_sync_validator.py`

## What It Checks

1. Health endpoint availability (`/health`)
2. Epoch/slot consistency (`/epoch`)
3. Miner list consistency (`/api/miners`)
4. Tip age drift (`tip_age_slots`, threshold configurable)
5. Sampled balance consistency (`/wallet/balance`)

## Usage

```bash
python3 tools/node_sync_validator.py \
  --nodes https://rustchain.org https://50.28.86.153 http://76.8.228.245:8099 \
  --output-json /tmp/node_sync_report.json \
  --output-text /tmp/node_sync_report.txt
```

## Notes

- Default mode keeps certificate verification enabled for public HTTPS nodes.
- For private nodes, install the issuing CA certificate before enabling them in scheduled checks.
- Script is cron-friendly and can run periodically for monitoring.
