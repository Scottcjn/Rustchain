# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import glob
import os
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import copy2


REQUIRED_TABLES = ["balances", "miner_attest_recent", "headers", "ledger", "epoch_rewards"]


@dataclass
class CheckResult:
    ok: bool
    lines: list[str]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> str:
    return f"[{now()}] {msg}"


def latest_backup(backup_dir: str, pattern: str) -> str | None:
    candidates = glob.glob(os.path.join(backup_dir, pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def query_one(conn: sqlite3.Connection, sql: str) -> str:
    row = conn.execute(sql).fetchone()
    return "" if row is None or row[0] is None else str(row[0])


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    # Validate table name to prevent SQL injection
    if not table.isidentifier():
        raise ValueError(f"Invalid table name: {table}")
    return int(query_one(conn, f"SELECT COUNT(*) FROM {table};") or 0)


def positive_balances(conn: sqlite3.Connection) -> int:
    return int(query_one(conn, "SELECT COUNT(*) FROM balances WHERE amount > 0;" ) or 0)


def epoch_max(conn: sqlite3.Connection) -> int:
    v = query_one(conn, "SELECT COALESCE(MAX(epoch), 0) FROM epoch_rewards;")
    return int(v or 0)


def verify(live_db: str, backup_file: str) -> CheckResult:
    lines: list[str] = [log(f"Backup: {backup_file}")]

    if not os.path.exists(live_db):
        return CheckResult(False, lines + [log(f"RESULT: FAIL (live db missing: {live_db})")])

    with tempfile.TemporaryDirectory(prefix="backup-verify-") as td:
        copied = os.path.join(td, Path(backup_file).name)
        copy2(backup_file, copied)

        bconn = sqlite3.connect(copied)
        lconn = sqlite3.connect(live_db)
        try:
            integrity = query_one(bconn, "PRAGMA integrity_check;")
            ok = integrity.lower() == "ok"
            lines.append(log(f"Integrity: {'PASS' if ok else 'FAIL'} ({integrity})"))
            if not ok:
                return CheckResult(False, lines + [log("RESULT: FAIL")])

            for t in REQUIRED_TABLES:
                b_count = count_rows(bconn, t)
                l_count = count_rows(lconn, t)
                table_ok = b_count > 0 and (l_count - b_count) <= max(1, int(l_count * 0.05))
                mark = "✅" if table_ok else "❌"
                lines.append(log(f"{t}: {b_count} rows (live: {l_count}) {mark}"))
                if not table_ok:
                    return CheckResult(False, lines + [log("RESULT: FAIL")])

            pos = positive_balances(bconn)
            pos_ok = pos > 0
            lines.append(log(f"balances (amount>0): {pos} {'✅' if pos_ok else '❌'}"))
            if not pos_ok:
                return CheckResult(False, lines + [log("RESULT: FAIL")])

            b_epoch = epoch_max(bconn)
            l_epoch = epoch_max(lconn)
            epoch_ok = (l_epoch - b_epoch) <= 1
            lines.append(log(f"epoch drift: backup={b_epoch}, live={l_epoch} {'✅' if epoch_ok else '❌'}"))
            if not epoch_ok:
                return CheckResult(False, lines + [log("RESULT: FAIL")])

            return CheckResult(True, lines + [log("RESULT: PASS")])
        finally:
            bconn.close()
            lconn.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify latest RustChain SQLite backup integrity")
    p.add_argument("--backup-dir", default="/root/rustchain/backups")
    p.add_argument("--pattern", default="rustchain_v2*.db*")
    p.add_argument("--live-db", default="/root/rustchain/rustchain_v2.db")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    bf = latest_backup(args.backup_dir, args.pattern)
    if not bf:
        print(log(f"RESULT: FAIL (no backup found in {args.backup_dir} with pattern {args.pattern})"))
        return 1

    result = verify(args.live_db, bf)
    print("\n".join(result.lines))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
