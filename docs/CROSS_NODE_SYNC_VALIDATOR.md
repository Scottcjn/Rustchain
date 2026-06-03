# Cross-Node Sync Validator

This tool validates RustChain consistency across multiple nodes and reports discrepancies.

## Script

`tools/node_sync_validator.py`

## What It Checks

1. Health endpoint availability (`/health`)
2. Epoch/slot consistency (`/epoch`)
3. Tip age drift (`tip_age_slots`, threshold configurable)
4. Miner list consistency for nodes in the same `(epoch, slot)` group (`/api/miners`)
5. Full paginated miner-set hashing using `/api/miners` pagination metadata
6. Enrolled miner and miner total consistency for same-epoch/same-slot nodes
7. Aggregate stat consistency for same-epoch/same-slot nodes (`/api/stats`)
8. Sampled balance consistency for miners seen on all same-epoch/same-slot nodes (`/wallet/balance`)

Epoch and slot mismatches are reported first. Miner, hash, stat, and sampled-balance
comparisons are scoped to nodes that are already on the same epoch and slot so normal
propagation lag does not produce duplicate hard-failure signals.

## Usage

```bash
python3 tools/node_sync_validator.py \
  --nodes https://50.28.86.131 https://50.28.86.153 http://76.8.228.245:8099 \
  --output-json /tmp/node_sync_report.json \
  --output-text /tmp/node_sync_report.txt
```

The default node set is the same three live nodes shown above, so `--nodes` is optional
when checking the public deployment.

The JSON report includes per-node miner pagination metadata, `miner_set_complete`, the
computed miner-set hash, and the same-epoch/same-slot node groups used for deeper miner
and stats comparisons.

## Notes

- Default mode uses `verify=False` to support self-signed certificates.
- Use `--verify-ssl` to enforce certificate checks.
- Script is cron-friendly and can run periodically for monitoring.
