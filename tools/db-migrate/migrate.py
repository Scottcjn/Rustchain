#!/usr/bin/env python3
"""
RustChain Database Migration Runner
====================================

Versioned schema migration tool for the RustChain SQLite database.

Usage:
    python migrate.py up [--db PATH] [--dir PATH]     Apply all pending migrations
    python migrate.py down [--db PATH] [--dir PATH]   Roll back the most recent migration
    python migrate.py status [--db PATH] [--dir PATH] Show applied/pending migrations
    python migrate.py create NAME                      Scaffold a new migration file

The runner stores applied migration state in a `_migrations` table inside the
target database.  Each migration file lives under migrations/ and contains
paired `-- UP` and `-- DOWN` SQL blocks.
"""

import argparse
import glob
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
DEFAULT_DB = os.environ.get("RUSTCHAIN_DB_PATH", "./rustchain_v2.db")

TRACKING_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS _migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  INTEGER NOT NULL,
    checksum    TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_tracking_table(conn: sqlite3.Connection) -> None:
    conn.execute(TRACKING_TABLE_DDL)
    conn.commit()


def _applied_versions(conn: sqlite3.Connection) -> dict:
    """Return {version: (name, applied_at, checksum)} for every applied migration."""
    _ensure_tracking_table(conn)
    rows = conn.execute(
        "SELECT version, name, applied_at, checksum FROM _migrations ORDER BY version"
    ).fetchall()
    return {r[0]: {"name": r[1], "applied_at": r[2], "checksum": r[3]} for r in rows}


def _checksum(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _parse_migration(filepath: str) -> Tuple[str, str]:
    """Parse a migration file and return (up_sql, down_sql)."""
    content = Path(filepath).read_text(encoding="utf-8")

    up_match = re.search(r"--\s*UP\b(.*?)(?=--\s*DOWN\b|$)", content, re.DOTALL | re.IGNORECASE)
    down_match = re.search(r"--\s*DOWN\b(.*?)$", content, re.DOTALL | re.IGNORECASE)

    up_sql = up_match.group(1).strip() if up_match else ""
    down_sql = down_match.group(1).strip() if down_match else ""

    return up_sql, down_sql


def _discover_migrations(migrations_dir: str) -> List[dict]:
    """Return sorted list of migration descriptors found on disk."""
    pattern = os.path.join(migrations_dir, "V*__*.sql")
    files = sorted(glob.glob(pattern))

    migrations = []
    for fp in files:
        basename = os.path.basename(fp)
        # Expected format: V{version}__{description}.sql
        m = re.match(r"V(\d+)__(.+)\.sql$", basename)
        if not m:
            continue
        version = m.group(1)
        name = m.group(2).replace("_", " ")
        up_sql, down_sql = _parse_migration(fp)
        migrations.append({
            "version": version,
            "name": name,
            "file": fp,
            "up_sql": up_sql,
            "down_sql": down_sql,
            "checksum": _checksum(up_sql),
        })
    return migrations


def _run_sql_block(conn: sqlite3.Connection, sql: str) -> None:
    """Execute a block of SQL statements separated by semicolons."""
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        conn.execute(stmt)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_up(db_path: str, migrations_dir: str) -> int:
    """Apply all pending migrations in order."""
    conn = sqlite3.connect(db_path)
    _ensure_tracking_table(conn)
    applied = _applied_versions(conn)
    available = _discover_migrations(migrations_dir)

    pending = [m for m in available if m["version"] not in applied]
    if not pending:
        print("Nothing to migrate — database is up to date.")
        conn.close()
        return 0

    errors = 0
    for mig in pending:
        print(f"  Applying V{mig['version']}  {mig['name']} ... ", end="", flush=True)
        if not mig["up_sql"]:
            print("SKIP (empty UP block)")
            continue
        try:
            _run_sql_block(conn, mig["up_sql"])
            conn.execute(
                "INSERT INTO _migrations (version, name, applied_at, checksum) VALUES (?, ?, ?, ?)",
                (mig["version"], mig["name"], int(time.time()), mig["checksum"]),
            )
            conn.commit()
            print("OK")
        except Exception as exc:
            conn.rollback()
            print(f"FAILED\n    Error: {exc}")
            errors += 1
            break  # stop on first failure

    conn.close()
    return 1 if errors else 0


def cmd_down(db_path: str, migrations_dir: str) -> int:
    """Roll back the most recently applied migration."""
    conn = sqlite3.connect(db_path)
    applied = _applied_versions(conn)
    if not applied:
        print("Nothing to roll back — no migrations have been applied.")
        conn.close()
        return 0

    available = {m["version"]: m for m in _discover_migrations(migrations_dir)}
    latest_version = max(applied.keys())
    mig = available.get(latest_version)

    if not mig:
        print(f"Migration file for V{latest_version} not found on disk. Cannot roll back.")
        conn.close()
        return 1

    print(f"  Rolling back V{mig['version']}  {mig['name']} ... ", end="", flush=True)
    if not mig["down_sql"]:
        print("SKIP (empty DOWN block)")
        conn.close()
        return 0

    try:
        _run_sql_block(conn, mig["down_sql"])
        conn.execute("DELETE FROM _migrations WHERE version = ?", (mig["version"],))
        conn.commit()
        print("OK")
    except Exception as exc:
        conn.rollback()
        print(f"FAILED\n    Error: {exc}")
        conn.close()
        return 1

    conn.close()
    return 0


def cmd_status(db_path: str, migrations_dir: str) -> int:
    """Print a table of applied and pending migrations."""
    conn = sqlite3.connect(db_path)
    _ensure_tracking_table(conn)
    applied = _applied_versions(conn)
    available = _discover_migrations(migrations_dir)
    conn.close()

    if not available:
        print("No migration files found.")
        return 0

    print(f"Database: {db_path}")
    print(f"Migrations directory: {migrations_dir}")
    print()
    print(f"{'Version':<10} {'Name':<45} {'State':<10} {'Applied At'}")
    print("-" * 90)

    for mig in available:
        v = mig["version"]
        if v in applied:
            ts = applied[v]["applied_at"]
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            state = "applied"
            # Check for checksum drift
            if applied[v]["checksum"] != mig["checksum"]:
                state = "MODIFIED"
        else:
            dt = ""
            state = "pending"
        print(f"V{v:<9} {mig['name']:<45} {state:<10} {dt}")

    applied_count = sum(1 for m in available if m["version"] in applied)
    pending_count = len(available) - applied_count
    print()
    print(f"Total: {len(available)}  Applied: {applied_count}  Pending: {pending_count}")
    return 0


def cmd_create(name: str, migrations_dir: str) -> int:
    """Create a new empty migration file with the next version number."""
    available = _discover_migrations(migrations_dir)
    if available:
        next_version = max(int(m["version"]) for m in available) + 1
    else:
        next_version = 18  # Continue from the node's current schema_version (17)

    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    filename = f"V{next_version:04d}__{slug}.sql"
    filepath = os.path.join(migrations_dir, filename)

    content = f"""\
-- Migration: {name}
-- Version: {next_version}
-- Created: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

-- UP
-- Write your forward migration SQL here.


-- DOWN
-- Write your rollback SQL here.

"""
    Path(filepath).write_text(content, encoding="utf-8")
    print(f"Created {filepath}")
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="migrate",
        description="RustChain database migration runner",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="Path to the SQLite database (default: $RUSTCHAIN_DB_PATH or ./rustchain_v2.db)",
    )
    parser.add_argument(
        "--dir",
        default=MIGRATIONS_DIR,
        help="Path to migrations directory (default: ./migrations/)",
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("up", help="Apply all pending migrations")
    sub.add_parser("down", help="Roll back the most recent migration")
    sub.add_parser("status", help="Show migration status")

    create_parser = sub.add_parser("create", help="Create a new migration file")
    create_parser.add_argument("name", help="Short description for the migration")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "up":
        return cmd_up(args.db, args.dir)
    elif args.command == "down":
        return cmd_down(args.db, args.dir)
    elif args.command == "status":
        return cmd_status(args.db, args.dir)
    elif args.command == "create":
        return cmd_create(args.name, args.dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
