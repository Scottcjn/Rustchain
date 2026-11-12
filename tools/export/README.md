# RustChain Attestation Data Export

`rustchain_export.py` extracts RustChain miner, epoch, reward, attestation,
and balance data into standard formats (CSV, JSON, JSONL, Parquet) for
analysis, reporting, tax preparation, and compliance.

Works in two modes:

- **API mode** (`--mode api`, default) – reads the live node REST API. No
  database access required.
- **DB mode** (`--mode db`) – reads a local SQLite node database for full
  historical data.

## Requirements

- Python 3.10+
- `pyarrow` only for `--format parquet` (`pip install pyarrow`)

Everything else uses the Python standard library.

## Usage

### CSV export from the live API (default)

```bash
python3 rustchain_export.py --format csv --output data/
```

Writes `data/miners.csv`, `data/epochs.csv`, `data/rewards.csv`,
`data/attestations.csv`, `data/balances.csv`, and a `data/manifest.json`.

### JSON / JSONL / Parquet

```bash
python3 rustchain_export.py --format json --output data/
python3 rustchain_export.py --format jsonl --output data/
python3 rustchain_export.py --format parquet --output data/   # needs pyarrow
```

### Export from a local SQLite node database

```bash
python3 rustchain_export.py --mode db --db /path/to/rustchain.db --format csv --output data/
```

The tool reads the canonical node tables when present:

- `miner_attest_recent` → `miners`, `attestations`
- `epoch_state` → `epochs`
- `epoch_rewards` → `rewards`
- `balances` → `balances`

Missing tables export as empty files (graceful degradation), so the tool also
works against partial backup snapshots.

### Date-range filtering

`--from` and `--to` accept `YYYY-MM-DD`, ISO-8601 timestamps, or bare Unix
timestamps. Filtering applies to timestamp-bearing rows:

- API mode: `last_attest` in `/api/miners`
- DB mode: `miner_attest_recent.ts_ok`, `epoch_state.settled_ts`

```bash
python3 rustchain_export.py --from 2025-12-01 --to 2026-02-01 --format csv --output data/
python3 rustchain_export.py --from 1700000000 --to 1800000000 --output data/
```

### Single-miner export

```bash
python3 rustchain_export.py --miner-id eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC --output data/
```

In API mode, supplying `--miner-id` also pulls reward entries from
`/wallet/history` into `rewards.<format>`.

### Table subset

```bash
python3 rustchain_export.py --table miners --table balances --output data/
```

### Alternate node

```bash
python3 rustchain_export.py --base-url https://50.28.86.131 --output data/
```

## Output schema

| Table | Columns | API source | DB source |
|-------|---------|------------|-----------|
| `miners` | `miner_id`, `device_arch`, `last_attest`, `total_earnings_rtc` | `/api/miners` + `/wallet/balance` | `miner_attest_recent` + `balances` |
| `epochs` | `epoch`, `timestamp`, `pot_size`, `settled` | `/epoch` (current epoch only) | `epoch_state` |
| `rewards` | `miner_id`, `epoch`, `amount_rtc` | `/wallet/history` (with `--miner-id`) | `epoch_rewards` |
| `attestations` | `miner_id`, `timestamp`, `device_arch`, `hardware_type` | `/api/miners` (`last_attest` snapshot) | `miner_attest_recent` |
| `balances` | `miner_id`, `amount_rtc` | `/wallet/balance` per miner | `balances` |

Amounts are normalized to RTC: micro-RTC fields (`amount_i64`, 1 RTC = 1 000 000
micro-RTC) are divided automatically; `amount_rtc` fields are passed through.

A `manifest.json` is always written alongside the tables with the mode,
format, per-table row counts, and generation timestamp.

## Streaming / large datasets

CSV, JSONL, and JSON write rows incrementally to the output file; the tool
never builds an unbounded in-memory list of rows for those formats. JSON is
written as a well-formed array using an incremental writer (the file is
streamed item-by-item). Parquet buffers rows in memory and writes a single
file at the end (a future improvement could batch-flush row groups for
very large databases).

## API-only mode limitations (documented honestly)

The public API exposes *current snapshot state*, not full history:

- **`epochs`** contains only the current epoch (no historical epoch list is
  published).
- **`rewards`** is empty unless `--miner-id` is supplied, in which case
  `rewards` is populated from the `reward` entries in
  `/wallet/history?miner_id=...` (bounded by that endpoint's pagination).
- **`total_earnings_rtc`** on `miners` is the *current balance* (the public
  API does not expose lifetime earnings).
- **`attestations`** is a point-in-time snapshot derived from each miner's
  `last_attest` + device fields in `/api/miners`, not a full attestation log.

For complete historical exports, run against the node SQLite database with
`--mode db`.

## CSV safety

CSV cells beginning with `=`, `+`, `-`, `@`, tab, or newline are prefixed
with a single quote to neutralize spreadsheet formula injection.

## Tests

```bash
cd tools/export
python3 -m pytest -q test_export.py
```

The test suite is fully offline: it monkeypatches HTTP access with canned
fixtures matching `docs/API.md` response shapes and builds temporary SQLite
databases. It covers format creation and parseability, CSV escaping, date
filters, API/DB column parity, single-miner filtering, table subsets, the
manifest, and streaming-writer mechanics.

## License

MIT – SPDX-License-Identifier: MIT