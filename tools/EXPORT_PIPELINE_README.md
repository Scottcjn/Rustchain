# RustChain Attestation & Reward Data Export Pipeline

Implementation for [RustChain Bounty #49](https://github.com/Scottcjn/rustchain-bounties/issues/49).

Exports RustChain attestation records, miner stats, balances, epoch settlements, and reward distributions into standard data formats:
- **CSV** (escaped, strict headers)
- **JSON** (nested API-compatible objects)
- **JSONL** (streaming line-delimited records)
- **Parquet** (columnar analytics format with PyArrow)

---

## Capabilities

1. **Dual Extraction Modes**:
   - **DB Mode**: High-throughput direct extraction from local node SQLite database (`miner_attest_recent`, `balances`, `epoch_state`, `epoch_rewards`, `ledger`).
   - **API Mode**: Remote extraction from active node REST endpoints (`/api/miners`, `/epoch`, `/health`, `/wallet/balance`) without requiring direct host or SSH credentials.
2. **Date Range Filtering**: Strict ISO-8601 / RFC-3339 timestamp windowing via `--from` and `--to`.
3. **Audit Manifest**: Generates an automated `export_manifest.json` verifying record counts and timestamp boundaries.
4. **Memory Efficient**: Streaming record-by-record output serialization.

---

## Usage Examples

### 1. Remote API Export to CSV
```bash
python3 tools/rustchain_export.py --mode api --node-url https://50.28.86.131 --format csv --output data/
```

### 2. Local SQLite DB Export to JSON with Date Windowing
```bash
python3 tools/rustchain_export.py \
  --mode db \
  --db-path /var/lib/rustchain/rustchain.db \
  --format json \
  --from 2026-01-01 \
  --to 2026-03-01 \
  --output exports/q1/
```

### 3. High-Performance Parquet Export for BigQuery / Snowflake / DuckDB
```bash
python3 tools/rustchain_export.py --mode db --db-path rustchain.db --format parquet --output analytics/
```

---

## Output Tables

| File | Source | Description |
|------|--------|-------------|
| `miners.*` | `miner_attest_recent` / `/api/miners` | Miner ID, architecture, timestamp, proof payload |
| `epochs.*` | `epoch_state` / `/epoch` | Epoch sequence number, epoch duration, pot size |
| `rewards.*` | `epoch_rewards` | Payout distribution per miner ID per epoch |
| `attestations.*` | `ledger` / `/health` | Physical hardware attestation logs & consensus state |
| `balances.*` | `balances` / `/wallet/balance` | Snapshot of confirmed RTC wallet balances |
