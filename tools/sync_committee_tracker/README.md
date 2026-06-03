# RustChain Sync Committee Rotation Tracker

Small, dependency-free tracker for the sync committee rotation state requested in
#2561. It derives the active committee from `/epoch` plus `/api/miners`, records
epoch snapshots in SQLite, and exposes dashboard, JSON, and Prometheus metrics.

## Run Once

```bash
python tools/sync_committee_tracker/sync_committee_tracker.py \
  --node-url https://rustchain.org \
  --db /tmp/sync_committee_history.db
```

Print Prometheus metrics once:

```bash
python tools/sync_committee_tracker/sync_committee_tracker.py \
  --node-url https://rustchain.org \
  --db /tmp/sync_committee_history.db \
  --metrics
```

## Dashboard

```bash
python tools/sync_committee_tracker/sync_committee_tracker.py \
  --node-url https://rustchain.org \
  --db /tmp/sync_committee_history.db \
  --serve \
  --port 8096
```

Then open:

- `http://127.0.0.1:8096/` for the dashboard
- `http://127.0.0.1:8096/api/sync-committee` for JSON
- `http://127.0.0.1:8096/metrics` for Prometheus metrics

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `RUSTCHAIN_NODE_URL` | `https://rustchain.org` | Node API base URL |
| `SYNC_COMMITTEE_DB` | `sync_committee_history.db` | SQLite history path |
| `SYNC_COMMITTEE_SIZE` | `8` | Number of committee members |
| `SYNC_COMMITTEE_ROTATION_EPOCHS` | `1` | Epochs between expected rotations |

The selection is deterministic for a given epoch and miner set: miners are
ordered by `sha256("<epoch>:<miner_id>")`, then the first N miners become the
committee.
