# RustChain Data Export

`rustchain_export.py` exports RustChain miner, epoch, reward, attestation, and balance data to CSV, JSON, or JSONL.

## API Mode

API mode works against public node endpoints and does not need database access.

```bash
python rustchain_export.py --mode api --format csv --output data/export
python rustchain_export.py --mode api --format jsonl --output data/export-jsonl --node https://rustchain.org
```

API mode uses:

- `GET /api/miners`
- `GET /epoch`
- `GET /wallet/balance?miner_id=...`

Because the public API only exposes current state, API mode emits current miners, current epoch, current balances, and a best-effort attestation snapshot from `/api/miners`.

## SQLite Mode

SQLite mode exports directly from a local node database and is the complete historical mode.

```bash
python rustchain_export.py --mode db --db rustchain.db --format csv --output data/export
python rustchain_export.py --mode db --db rustchain.db --format json --output data/export-json --from 2026-02-01 --to 2026-03-01
```

SQLite mode reads these tables when present:

- `miner_attest_recent` for `miners` and `attestations`
- `epoch_state` for `epochs`
- `epoch_rewards` for `rewards`
- `balances` for `balances`
- `ledger` for manifest-adjacent audit coverage

Missing tables export as empty files so the command can run against partial backup snapshots.

## Output Files

Each run writes:

- `miners.<format>`
- `epochs.<format>`
- `rewards.<format>`
- `attestations.<format>`
- `balances.<format>`
- `manifest.json`

CSV output includes headers and standard CSV escaping via Python's `csv` module. JSON output is a pretty-printed array. JSONL output writes one object per line for streaming-friendly analysis.

## Date Filtering

`--from` and `--to` accept `YYYY-MM-DD`, ISO timestamps, or Unix timestamps. Filtering applies to timestamp-bearing sources such as `miner_attest_recent.ts_ok`, `epoch_state.settled_ts`, and `ledger.ts`.
