# RustChain Backup & Restore Tool

Command-line tool for backing up and restoring RustChain node data. Handles the SQLite blockchain database, wallet keyfiles, and node configuration with safe snapshots, compression, optional S3 upload, and automatic rotation.

## Features

- **SQLite online backup** — uses Python's `sqlite3.backup()` for a crash-consistent database snapshot (no downtime required)
- **Wallet backup** — copies all keyfiles from the wallet directory
- **Config backup** — preserves node configuration
- **gzip/tar compression** — every backup is a single `.tar.gz` archive with a JSON manifest and SHA-256 checksums
- **S3 upload** — optional push to any S3-compatible bucket via the AWS CLI
- **Backup rotation** — automatically deletes old archives, keeping the last N (default 10)
- **Scheduled backups** — one-command cron installation
- **Restore with verification** — checksums are validated before overwriting any data

## Requirements

- Python 3.10+
- No third-party packages (stdlib only)
- AWS CLI (only if using `--s3-bucket`)

## Quick Start

```bash
# Create a backup with default paths
python tools/backup/backup.py backup

# Override paths
python tools/backup/backup.py backup \
  --db /rustchain/data/rustchain_v2.db \
  --wallet-dir /rustchain/wallet \
  --config-dir /rustchain/config \
  --backup-dir ./backups \
  --keep 5
```

## Commands

### `backup`

Create a new backup archive.

| Flag | Default | Description |
|------|---------|-------------|
| `--db` | `$RUSTCHAIN_DB` or `/rustchain/data/rustchain_v2.db` | Path to SQLite database |
| `--wallet-dir` | `$RUSTCHAIN_WALLET_DIR` or `/rustchain/wallet` | Wallet keyfile directory |
| `--config-dir` | `$RUSTCHAIN_CONFIG_DIR` or `/rustchain/config` | Config directory |
| `--backup-dir` | `$BACKUP_DIR` or `./backups` | Where to store archives |
| `--keep` | `10` | Number of backups to retain |
| `--s3-bucket` | *(none)* | S3 bucket name for remote upload |
| `--s3-prefix` | `rustchain-backups` | S3 key prefix |

### `restore`

Restore from a backup archive.

```bash
python tools/backup/backup.py restore ./backups/rustchain-backup-20250101T030000Z.tar.gz

# Force overwrite without prompts
python tools/backup/backup.py restore --force ./backups/rustchain-backup-20250101T030000Z.tar.gz
```

| Flag | Default | Description |
|------|---------|-------------|
| `archive` | *(required)* | Path to `.tar.gz` backup |
| `--db` | same as backup | Where to restore the database |
| `--wallet-dir` | same as backup | Where to restore wallet files |
| `--config-dir` | same as backup | Where to restore config files |
| `--force` | `false` | Overwrite existing data without prompting |

### `list`

Show available backups with timestamps and sizes.

```bash
python tools/backup/backup.py list --backup-dir ./backups
```

### `cron`

Install a crontab entry for automated backups.

```bash
# Default: daily at 03:00 UTC
python tools/backup/backup.py cron

# Every 6 hours
python tools/backup/backup.py cron --schedule "0 */6 * * *"

# Custom paths
python tools/backup/backup.py cron \
  --schedule "0 2 * * *" \
  --backup-dir /mnt/backups/rustchain \
  --keep 30
```

## Environment Variables

All CLI flags can be set via environment variables:

| Variable | Maps to |
|----------|---------|
| `RUSTCHAIN_HOME` | Base path for defaults |
| `RUSTCHAIN_DB` | `--db` |
| `RUSTCHAIN_WALLET_DIR` | `--wallet-dir` |
| `RUSTCHAIN_CONFIG_DIR` | `--config-dir` |
| `BACKUP_DIR` | `--backup-dir` |
| `BACKUP_KEEP` | `--keep` |

## Archive Format

Each backup produces a `rustchain-backup-<timestamp>.tar.gz` containing:

```
rustchain-backup-20250101T030000Z/
  manifest.json          # version, timestamp, component list, checksums
  rustchain_v2.db        # SQLite database snapshot
  wallet/                # wallet keyfiles
  config/                # node configuration
```

The manifest includes SHA-256 hashes so the restore command can verify integrity before overwriting production data.

## Docker

When running inside the Docker deployment, mount a host volume for the backup directory:

```yaml
volumes:
  - ./backups:/rustchain/backups
```

Then run via `docker exec`:

```bash
docker exec rustchain-node python /rustchain/tools/backup/backup.py backup \
  --backup-dir /rustchain/backups
```

## License

Same as the RustChain project (see repository root).
