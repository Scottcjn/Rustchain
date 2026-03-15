#!/usr/bin/env python3
"""
RustChain Node Backup & Restore Tool

Automated backup and restore for RustChain node data including:
- SQLite blockchain database
- Wallet keyfiles
- Node configuration
- Hardware fingerprint profiles

Supports compression, S3 upload, scheduled cron jobs, and backup rotation.
"""

import argparse
import datetime
import gzip
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

__version__ = "1.0.0"

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
logger = logging.getLogger("rustchain-backup")

# ---------------------------------------------------------------------------
# Default paths (overridable via env or CLI flags)
# ---------------------------------------------------------------------------
DEFAULT_RUSTCHAIN_HOME = os.environ.get("RUSTCHAIN_HOME", "/rustchain")
DEFAULT_DB_PATH = os.environ.get(
    "RUSTCHAIN_DB",
    os.path.join(DEFAULT_RUSTCHAIN_HOME, "data", "rustchain_v2.db"),
)
DEFAULT_WALLET_DIR = os.environ.get(
    "RUSTCHAIN_WALLET_DIR",
    os.path.join(DEFAULT_RUSTCHAIN_HOME, "wallet"),
)
DEFAULT_CONFIG_DIR = os.environ.get(
    "RUSTCHAIN_CONFIG_DIR",
    os.path.join(DEFAULT_RUSTCHAIN_HOME, "config"),
)
DEFAULT_BACKUP_DIR = os.environ.get("BACKUP_DIR", "./backups")
DEFAULT_KEEP = int(os.environ.get("BACKUP_KEEP", "10"))

MANIFEST_NAME = "manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sha256_file(path: str) -> str:
    """Return hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def timestamp_label() -> str:
    return datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def sizeof_fmt(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


# ---------------------------------------------------------------------------
# SQLite safe backup
# ---------------------------------------------------------------------------
def backup_sqlite(db_path: str, dest_path: str) -> bool:
    """Use the SQLite online-backup API for a consistent snapshot."""
    if not os.path.isfile(db_path):
        logger.warning("Database not found: %s — skipping", db_path)
        return False

    logger.info("Backing up SQLite database: %s", db_path)
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(dest_path)
        src.backup(dst)
        dst.close()
        src.close()
        logger.info(
            "Database snapshot saved (%s)", sizeof_fmt(os.path.getsize(dest_path))
        )
        return True
    except Exception as exc:
        logger.error("SQLite backup failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Directory copy helper
# ---------------------------------------------------------------------------
def backup_directory(src_dir: str, dest_dir: str, label: str) -> bool:
    if not os.path.isdir(src_dir):
        logger.warning("%s directory not found: %s — skipping", label, src_dir)
        return False

    logger.info("Backing up %s: %s", label, src_dir)
    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
    return True


# ---------------------------------------------------------------------------
# Compression
# ---------------------------------------------------------------------------
def compress_archive(source_dir: str, archive_path: str) -> str:
    """Create a gzip-compressed tar archive. Returns the archive path."""
    logger.info("Compressing backup to %s", archive_path)
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
    size = os.path.getsize(archive_path)
    logger.info("Archive created: %s (%s)", archive_path, sizeof_fmt(size))
    return archive_path


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------
def upload_to_s3(archive_path: str, bucket: str, prefix: str = "rustchain-backups"):
    """Upload the archive to an S3 bucket using the AWS CLI."""
    key = f"{prefix}/{os.path.basename(archive_path)}"
    logger.info("Uploading to s3://%s/%s", bucket, key)
    try:
        subprocess.check_call(
            ["aws", "s3", "cp", archive_path, f"s3://{bucket}/{key}"],
            stdout=subprocess.DEVNULL,
        )
        logger.info("Upload complete: s3://%s/%s", bucket, key)
    except FileNotFoundError:
        logger.error("AWS CLI not found. Install it or upload manually.")
    except subprocess.CalledProcessError as exc:
        logger.error("S3 upload failed (exit %d). Check credentials.", exc.returncode)


# ---------------------------------------------------------------------------
# Backup rotation
# ---------------------------------------------------------------------------
def rotate_backups(backup_dir: str, keep: int):
    """Delete old backup archives, keeping the most recent `keep` files."""
    archives = sorted(
        [
            f
            for f in Path(backup_dir).glob("rustchain-backup-*.tar.gz")
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if len(archives) <= keep:
        return
    for old in archives[keep:]:
        logger.info("Rotating out old backup: %s", old.name)
        old.unlink()


# ---------------------------------------------------------------------------
# Main backup routine
# ---------------------------------------------------------------------------
def run_backup(
    db_path: str,
    wallet_dir: str,
    config_dir: str,
    backup_dir: str,
    keep: int,
    s3_bucket: str | None = None,
    s3_prefix: str = "rustchain-backups",
) -> str | None:
    """
    Execute a full backup:
      1. Snapshot SQLite DB
      2. Copy wallet keyfiles
      3. Copy config files
      4. Write manifest with checksums
      5. Compress to .tar.gz
      6. Optionally upload to S3
      7. Rotate old backups

    Returns the path to the final archive, or None on failure.
    """
    ts = timestamp_label()
    staging = tempfile.mkdtemp(prefix=f"rustchain-backup-{ts}-")
    snapshot_dir = os.path.join(staging, f"rustchain-backup-{ts}")
    os.makedirs(snapshot_dir)

    manifest = {
        "version": __version__,
        "timestamp": ts,
        "components": [],
    }

    # 1. SQLite
    db_dest = os.path.join(snapshot_dir, "rustchain_v2.db")
    if backup_sqlite(db_path, db_dest):
        manifest["components"].append(
            {
                "type": "database",
                "file": "rustchain_v2.db",
                "sha256": sha256_file(db_dest),
                "size": os.path.getsize(db_dest),
            }
        )

    # 2. Wallet
    wallet_dest = os.path.join(snapshot_dir, "wallet")
    if backup_directory(wallet_dir, wallet_dest, "wallet"):
        manifest["components"].append({"type": "wallet", "directory": "wallet"})

    # 3. Config
    config_dest = os.path.join(snapshot_dir, "config")
    if backup_directory(config_dir, config_dest, "config"):
        manifest["components"].append({"type": "config", "directory": "config"})

    if not manifest["components"]:
        logger.error("Nothing was backed up. Aborting.")
        shutil.rmtree(staging, ignore_errors=True)
        return None

    # 4. Write manifest
    manifest_path = os.path.join(snapshot_dir, MANIFEST_NAME)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # 5. Compress
    os.makedirs(backup_dir, exist_ok=True)
    archive_name = f"rustchain-backup-{ts}.tar.gz"
    archive_path = os.path.join(backup_dir, archive_name)
    compress_archive(snapshot_dir, archive_path)

    # 6. S3 upload
    if s3_bucket:
        upload_to_s3(archive_path, s3_bucket, s3_prefix)

    # 7. Rotate
    rotate_backups(backup_dir, keep)

    # Cleanup staging
    shutil.rmtree(staging, ignore_errors=True)

    logger.info("Backup complete: %s", archive_path)
    return archive_path


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------
def run_restore(
    archive_path: str,
    db_path: str,
    wallet_dir: str,
    config_dir: str,
    force: bool = False,
):
    """
    Restore a RustChain backup archive.

    Steps:
      1. Extract the archive
      2. Verify manifest checksums
      3. Restore database (with optional overwrite confirmation)
      4. Restore wallet files
      5. Restore config files
    """
    if not os.path.isfile(archive_path):
        logger.error("Archive not found: %s", archive_path)
        sys.exit(1)

    staging = tempfile.mkdtemp(prefix="rustchain-restore-")
    logger.info("Extracting %s", archive_path)

    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(staging)

    # Find the snapshot directory inside staging
    entries = os.listdir(staging)
    if len(entries) != 1:
        logger.error("Unexpected archive structure")
        sys.exit(1)
    snapshot_dir = os.path.join(staging, entries[0])

    # Load manifest
    manifest_path = os.path.join(snapshot_dir, MANIFEST_NAME)
    if not os.path.isfile(manifest_path):
        logger.error("Manifest not found in archive — is this a valid backup?")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    logger.info(
        "Backup timestamp: %s  |  Components: %d",
        manifest.get("timestamp", "unknown"),
        len(manifest.get("components", [])),
    )

    for comp in manifest.get("components", []):
        ctype = comp["type"]

        if ctype == "database":
            src = os.path.join(snapshot_dir, comp["file"])
            # Verify checksum
            actual = sha256_file(src)
            if actual != comp.get("sha256"):
                logger.error(
                    "Checksum mismatch for database! Expected %s, got %s",
                    comp["sha256"],
                    actual,
                )
                if not force:
                    sys.exit(1)
                logger.warning("--force specified, continuing despite mismatch")

            if os.path.isfile(db_path) and not force:
                answer = input(
                    f"Database already exists at {db_path}. Overwrite? [y/N] "
                )
                if answer.lower() != "y":
                    logger.info("Skipping database restore")
                    continue

            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            shutil.copy2(src, db_path)
            logger.info("Database restored to %s", db_path)

        elif ctype == "wallet":
            src = os.path.join(snapshot_dir, comp["directory"])
            if os.path.isdir(wallet_dir) and not force:
                answer = input(
                    f"Wallet directory exists at {wallet_dir}. Overwrite? [y/N] "
                )
                if answer.lower() != "y":
                    logger.info("Skipping wallet restore")
                    continue
            os.makedirs(wallet_dir, exist_ok=True)
            shutil.copytree(src, wallet_dir, dirs_exist_ok=True)
            logger.info("Wallet restored to %s", wallet_dir)

        elif ctype == "config":
            src = os.path.join(snapshot_dir, comp["directory"])
            if os.path.isdir(config_dir) and not force:
                answer = input(
                    f"Config directory exists at {config_dir}. Overwrite? [y/N] "
                )
                if answer.lower() != "y":
                    logger.info("Skipping config restore")
                    continue
            os.makedirs(config_dir, exist_ok=True)
            shutil.copytree(src, config_dir, dirs_exist_ok=True)
            logger.info("Config restored to %s", config_dir)

    shutil.rmtree(staging, ignore_errors=True)
    logger.info("Restore complete.")


# ---------------------------------------------------------------------------
# List backups
# ---------------------------------------------------------------------------
def list_backups(backup_dir: str):
    """Print available backup archives with timestamps and sizes."""
    archives = sorted(
        Path(backup_dir).glob("rustchain-backup-*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not archives:
        print("No backups found in", backup_dir)
        return

    print(f"{'#':<4} {'Timestamp':<20} {'Size':<12} {'File'}")
    print("-" * 72)
    for i, a in enumerate(archives, 1):
        ts = a.stem.replace("rustchain-backup-", "").replace(".tar", "")
        print(f"{i:<4} {ts:<20} {sizeof_fmt(a.stat().st_size):<12} {a.name}")


# ---------------------------------------------------------------------------
# Cron installer
# ---------------------------------------------------------------------------
def install_cron(
    schedule: str,
    db_path: str,
    wallet_dir: str,
    config_dir: str,
    backup_dir: str,
    keep: int,
):
    """Install a crontab entry for scheduled backups."""
    script = os.path.abspath(__file__)
    python = sys.executable
    cmd = (
        f"{python} {script} backup"
        f" --db {db_path}"
        f" --wallet-dir {wallet_dir}"
        f" --config-dir {config_dir}"
        f" --backup-dir {backup_dir}"
        f" --keep {keep}"
    )
    cron_line = f"{schedule} {cmd} >> /var/log/rustchain-backup.log 2>&1"

    try:
        existing = subprocess.check_output(["crontab", "-l"], stderr=subprocess.DEVNULL).decode()
    except (subprocess.CalledProcessError, FileNotFoundError):
        existing = ""

    if cmd in existing:
        logger.info("Cron job already installed.")
        return

    new_cron = existing.rstrip("\n") + "\n" + cron_line + "\n"
    proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE)
    proc.communicate(input=new_cron.encode())
    if proc.returncode == 0:
        logger.info("Cron job installed: %s", schedule)
    else:
        logger.error("Failed to install cron job.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rustchain-backup",
        description="Backup and restore tool for RustChain node data",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # -- backup --
    bp = sub.add_parser("backup", help="Create a new backup")
    bp.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite database")
    bp.add_argument(
        "--wallet-dir", default=DEFAULT_WALLET_DIR, help="Path to wallet directory"
    )
    bp.add_argument(
        "--config-dir", default=DEFAULT_CONFIG_DIR, help="Path to config directory"
    )
    bp.add_argument(
        "--backup-dir", default=DEFAULT_BACKUP_DIR, help="Directory to store backups"
    )
    bp.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help="Number of backups to retain (default: 10)",
    )
    bp.add_argument("--s3-bucket", default=None, help="S3 bucket for remote upload")
    bp.add_argument(
        "--s3-prefix",
        default="rustchain-backups",
        help="S3 key prefix (default: rustchain-backups)",
    )

    # -- restore --
    rp = sub.add_parser("restore", help="Restore from a backup archive")
    rp.add_argument("archive", help="Path to .tar.gz backup archive")
    rp.add_argument("--db", default=DEFAULT_DB_PATH, help="Restore database to path")
    rp.add_argument(
        "--wallet-dir", default=DEFAULT_WALLET_DIR, help="Restore wallet to directory"
    )
    rp.add_argument(
        "--config-dir", default=DEFAULT_CONFIG_DIR, help="Restore config to directory"
    )
    rp.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting",
    )

    # -- list --
    lp = sub.add_parser("list", help="List available backups")
    lp.add_argument(
        "--backup-dir", default=DEFAULT_BACKUP_DIR, help="Directory with backups"
    )

    # -- cron --
    cp = sub.add_parser("cron", help="Install a cron job for scheduled backups")
    cp.add_argument(
        "--schedule",
        default="0 3 * * *",
        help="Cron schedule expression (default: daily at 03:00 UTC)",
    )
    cp.add_argument("--db", default=DEFAULT_DB_PATH)
    cp.add_argument("--wallet-dir", default=DEFAULT_WALLET_DIR)
    cp.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    cp.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR)
    cp.add_argument("--keep", type=int, default=DEFAULT_KEEP)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "backup":
        result = run_backup(
            db_path=args.db,
            wallet_dir=args.wallet_dir,
            config_dir=args.config_dir,
            backup_dir=args.backup_dir,
            keep=args.keep,
            s3_bucket=args.s3_bucket,
            s3_prefix=args.s3_prefix,
        )
        if result is None:
            sys.exit(1)

    elif args.command == "restore":
        run_restore(
            archive_path=args.archive,
            db_path=args.db,
            wallet_dir=args.wallet_dir,
            config_dir=args.config_dir,
            force=args.force,
        )

    elif args.command == "list":
        list_backups(args.backup_dir)

    elif args.command == "cron":
        install_cron(
            schedule=args.schedule,
            db_path=args.db,
            wallet_dir=args.wallet_dir,
            config_dir=args.config_dir,
            backup_dir=args.backup_dir,
            keep=args.keep,
        )


if __name__ == "__main__":
    main()
