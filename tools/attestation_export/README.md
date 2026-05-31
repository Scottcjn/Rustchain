# RustChain Attestation Export

`rustchain_export.py` exports RustChain miner, attestation, epoch, reward, and
balance data into standard analysis formats.

## API Mode

API mode works against the public node and does not require SSH or direct
database access. It tolerates the current self-signed certificate by default.

```bash
python3 tools/attestation_export/rustchain_export.py \
  --node-url https://50.28.86.131 \
  --format csv \
  --output data/
```

Supported formats:

- `csv`
- `json`
- `jsonl`
- `parquet` when `pyarrow` is installed

Date filters are inclusive and apply to rows with timestamp-like fields:

```bash
python3 tools/attestation_export/rustchain_export.py \
  --from 2026-05-01 \
  --to 2026-05-31 \
  --epoch 175-179 \
  --format jsonl \
  --output data/may-export
```

API mode writes:

- `miners.*` from `/api/miners`
- `epochs.*` from `/epoch` and requested `/rewards/epoch/{epoch}` rows
- `rewards.*` from `/rewards/epoch/{epoch}` plus wallet history rows
- `attestations.*` from the compact attestation fields exposed by `/api/miners`
- `balances.*` from `/wallet/balance?miner_id=...`

Use `--verify-tls` when the node has a trusted certificate.

## SQLite Mode

SQLite mode is for node operators with a local database snapshot. It exports
the richer tables directly:

```bash
python3 tools/attestation_export/rustchain_export.py \
  --db-path /var/lib/rustchain/rustchain.db \
  --format json \
  --output data/db-export
```

SQLite mode reads these tables when present:

- `miner_attest_recent`
- `balances`
- `epoch_state`
- `epoch_rewards`
- `ledger`

Missing tables are treated as empty exports so partial snapshots remain usable.

## Validation

```bash
python3 -m unittest tools/attestation_export/test_rustchain_export.py
python3 tools/attestation_export/rustchain_export.py \
  --node-url https://50.28.86.131 \
  --format json \
  --output /tmp/rustchain-export \
  --epoch 179
```
