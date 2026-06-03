# Mempool Visualization Demo

This proof path verifies the explorer can display pending UTXO mempool activity.

## API

```bash
python tools/explorer-api/api.py
curl http://localhost:6100/api/mempool?limit=25
```

The response includes:

- `metrics.mempool_size`
- `metrics.total_fee_rtc`
- `metrics.max_fee_nrtc`
- `transactions[].tx_id`
- `transactions[].age_seconds`
- `transactions[].expires_in_seconds`

## Dashboard

Open the explorer dashboard and confirm the Mempool section renders:

- pending transaction count
- visible transaction count
- total fee pressure
- transaction history rows with age and expiry

Runtime screenshot: `docs/runtime-environment-issue-2564.png`
