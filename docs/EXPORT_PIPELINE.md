# RustChain Attestation & Reward Data Export Pipeline (`#49`, `#1113`, `#8359`)

`tools/rustchain_export.py` extracts RustChain attestation, epoch, reward, miner, and wallet balance records into standard analytics formats (`CSV`, `JSON`, `JSONL`, `Parquet`) with date-range filtering, SHA-256 integrity checksums, and Gini/Lorenz token distribution metrics.

## Features
- **5 Standard Tables Exported**:
  - `miners.{csv,json,jsonl,parquet}` — Miner IDs, hardware architecture, model, antiquity multiplier, last attestation timestamp, and cumulative RTC earnings.
  - `epochs.{csv,json,jsonl,parquet}` — Epoch number, settlement timestamp, pot size (RTC), settlement flag, and active miner count.
  - `rewards.{csv,json,jsonl,parquet}` — Per-epoch, per-miner RTC reward payouts.
  - `attestations.{csv,json,jsonl,parquet}` — Hardware attestation log (`miner_id`, `timestamp`, `architecture`, `device_info`, `passed`).
  - `balances.{csv,json,jsonl,parquet}` — All-wallet RTC balances (`wallet_id`, `amount_rtc`, `updated_at`, `is_founder`).
- **Token Distribution & Gini Analytics (`distribution_summary.json`)**:
  - Computes Gini coefficient across all wallets and non-founder wallets (`#1113`, `#8359`), Top-10 non-founder holders, and 10-decile Lorenz curve coordinates.
- **Dual Execution Modes**:
  - **API Mode (Default)**: Works against `https://50.28.86.131` without direct SSH or SQLite database access.
  - **SQLite DB Mode (`--db-path`)**: Opens `rustchain_v2.db` in read-only URI mode (`?mode=ro`) for full historical table exports.

## Usage Examples

```bash
# Export CSV tables from live node API
python3 tools/rustchain_export.py --format csv --output data/

# Export filtered JSONL tables for a specific date range
python3 tools/rustchain_export.py --format jsonl --from 2025-12-01 --to 2026-02-01 --output data/

# Export Parquet tables from a local SQLite database backup
python3 tools/rustchain_export.py --format parquet --db-path /root/rustchain/rustchain_v2.db --output data/
```
