#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Automated RustChain SQLite Backup Verification Script (Bounty #755).

Non-destructively validates the latest RustChain SQLite database backup:
1. Finds the latest backup file (`rustchain_v2*.db*` / `*.bak`) in `--backup-dir` or `--backup-file`.
2. Copies the backup to an isolated temporary directory so the backup and live DB are never modified.
3. Runs `PRAGMA integrity_check;` and verifies it returns `ok`.
4. Verifies all 5 required tables exist and contain valid rows:
   - `balances` (must have rows with positive balance > 0)
   - `miner_attest_recent`
   - `headers`
   - `ledger`
   - `epoch_rewards`
5. Compares row counts and maximum epoch against the live DB (`--live-db`), ensuring the backup
   is at most `--max-epoch-lag` (default 1) epoch behind.
6. Prints timestamped PASS/FAIL lines and exits 0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sqlite3
import sys
import tempfile
from typing import Any
import urllib.request

REQUIRED_TABLES = (
    "balances",
    "miner_attest_recent",
    "headers",
    "ledger",
    "epoch_rewards",
)


def _ts() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def find_latest_backup(backup_dir: pathlib.Path | None, backup_file: pathlib.Path | None = None) -> pathlib.Path | None:
    """Locate the newest SQLite backup file in backup_dir or explicit backup_file."""
    if backup_file is not None:
        return backup_file if backup_file.is_file() else None
    if backup_dir is None or not backup_dir.is_dir():
        return None
    candidates: list[pathlib.Path] = []
    for p in backup_dir.iterdir():
        if not p.is_file():
            continue
        name = p.name.lower()
        if ("rustchain" in name or name.endswith(".db") or name.endswith(".bak") or ".db." in name) and not name.endswith(("-wal", "-shm", ".log")):
            candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x.stat().st_mtime, x.name), reverse=True)
    return candidates[0]


def _query_db_metrics(db_path: pathlib.Path) -> dict[str, Any]:
    """Inspect a SQLite database in read-only mode (`?mode=ro`)."""
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        integrity_rows = conn.execute("PRAGMA integrity_check;").fetchall()
        integrity_ok = len(integrity_rows) == 1 and str(integrity_rows[0][0]).strip().lower() == "ok"

        existing_tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        table_counts: dict[str, int] = {}
        for tbl in REQUIRED_TABLES:
            if tbl in existing_tables:
                table_counts[tbl] = int(conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
            else:
                table_counts[tbl] = -1

        positive_balances = 0
        if "balances" in existing_tables:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(balances)").fetchall()]
            amt_col = next((c for c in ("amount_rtc", "balance", "amount_i64", "amount") if c in cols), None)
            if amt_col:
                positive_balances = int(
                    conn.execute(f"SELECT COUNT(*) FROM balances WHERE {amt_col} > 0").fetchone()[0]
                )

        max_epoch = None
        if "epoch_rewards" in existing_tables:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(epoch_rewards)").fetchall()]
            if "epoch" in cols:
                val = conn.execute("SELECT MAX(epoch) FROM epoch_rewards").fetchone()[0]
                if val is not None:
                    max_epoch = int(val)
        if max_epoch is None and "headers" in existing_tables:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(headers)").fetchall()]
            ep_col = next((c for c in ("epoch", "height", "slot") if c in cols), None)
            if ep_col:
                val = conn.execute(f"SELECT MAX({ep_col}) FROM headers").fetchone()[0]
                if val is not None:
                    max_epoch = int(val)

        return {
            "integrity_ok": integrity_ok,
            "integrity_messages": [str(r[0]) for r in integrity_rows],
            "table_counts": table_counts,
            "positive_balances": positive_balances,
            "max_epoch": max_epoch,
        }
    finally:
        conn.close()


def verify_backup(
    backup_path: pathlib.Path | None,
    live_db_path: pathlib.Path | None = None,
    max_epoch_lag: int = 1,
) -> tuple[bool, dict[str, Any], list[str]]:
    """Copy backup to temp dir, verify integrity & required tables, and compare with live DB."""
    logs: list[str] = []
    if backup_path is None or not backup_path.is_file():
        msg = f"[{_ts()}] Backup: MISSING (no valid backup file found)"
        logs.append(msg)
        logs.append(f"[{_ts()}] RESULT: FAIL (missing backup)")
        return False, {"ok": False, "error": "missing_backup"}, logs

    logs.append(f"[{_ts()}] Backup: {backup_path}")

    with tempfile.TemporaryDirectory(prefix="rustchain_backup_verify_") as tmp_dir:
        temp_copy = pathlib.Path(tmp_dir) / backup_path.name
        shutil.copy2(backup_path, temp_copy)

        try:
            bak_metrics = _query_db_metrics(temp_copy)
        except Exception as exc:
            logs.append(f"[{_ts()}] Integrity: FAIL ({exc})")
            logs.append(f"[{_ts()}] RESULT: FAIL")
            return False, {"ok": False, "error": str(exc)}, logs

    live_metrics: dict[str, Any] | None = None
    if live_db_path is not None and live_db_path.is_file():
        try:
            live_metrics = _query_db_metrics(live_db_path)
        except Exception as exc:
            logs.append(f"[{_ts()}] Live DB warning: {exc}")

    overall_ok = True
    if bak_metrics["integrity_ok"]:
        logs.append(f"[{_ts()}] Integrity: PASS")
    else:
        overall_ok = False
        logs.append(f"[{_ts()}] Integrity: FAIL ({', '.join(bak_metrics['integrity_messages'])})")

    table_results: dict[str, Any] = {}
    for tbl in REQUIRED_TABLES:
        cnt = bak_metrics["table_counts"].get(tbl, -1)
        live_cnt = live_metrics["table_counts"].get(tbl) if live_metrics else None
        tbl_ok = cnt > 0
        if tbl == "balances" and bak_metrics["positive_balances"] <= 0:
            tbl_ok = False
        if not tbl_ok:
            overall_ok = False
        mark = "✅" if tbl_ok else "❌"
        live_str = f" (live: {live_cnt})" if live_cnt is not None and live_cnt >= 0 else ""
        if cnt < 0:
            logs.append(f"[{_ts()}] {tbl}: MISSING TABLE{live_str} {mark}")
        else:
            logs.append(f"[{_ts()}] {tbl}: {cnt} rows{live_str} {mark}")
        table_results[tbl] = {"rows": cnt, "live_rows": live_cnt, "ok": tbl_ok}

    epoch_lag = 0
    if live_metrics and live_metrics.get("max_epoch") is not None and bak_metrics.get("max_epoch") is not None:
        epoch_lag = int(live_metrics["max_epoch"]) - int(bak_metrics["max_epoch"])
        if epoch_lag > max_epoch_lag:
            overall_ok = False
            logs.append(
                f"[{_ts()}] Epoch lag: {epoch_lag} epochs behind live (backup={bak_metrics['max_epoch']}, live={live_metrics['max_epoch']}, max_allowed={max_epoch_lag}) ❌"
            )
        else:
            logs.append(
                f"[{_ts()}] Epoch lag: {epoch_lag} epochs (backup={bak_metrics['max_epoch']}, live={live_metrics['max_epoch']}) ✅"
            )

    logs.append(f"[{_ts()}] RESULT: {'PASS' if overall_ok else 'FAIL'}")
    report = {
        "ok": overall_ok,
        "backup_file": str(backup_path),
        "integrity_ok": bak_metrics["integrity_ok"],
        "positive_balances": bak_metrics["positive_balances"],
        "tables": table_results,
        "backup_max_epoch": bak_metrics.get("max_epoch"),
        "live_max_epoch": live_metrics.get("max_epoch") if live_metrics else None,
        "epoch_lag": epoch_lag,
    }
    return overall_ok, report, logs


def _send_webhook_alert(webhook_url: str, report: dict[str, Any]) -> None:
    try:
        body = json.dumps({"text": f"RustChain DB Backup Verification FAILED: {report}"}).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate RustChain SQLite database backups (#755).")
    parser.add_argument("--backup-dir", default="/root/rustchain/backups", help="Directory containing backup DB files")
    parser.add_argument("--backup-file", default=None, help="Explicit backup file to verify")
    parser.add_argument("--live-db", default=None, help="Optional live SQLite DB path for row/epoch comparison")
    parser.add_argument("--max-epoch-lag", type=int, default=1, help="Maximum allowed epoch lag vs live DB")
    parser.add_argument("--webhook-url", default=None, help="Optional webhook URL to alert on failure")
    parser.add_argument("--json", action="store_true", help="Print JSON summary in addition to log lines")
    args = parser.parse_args(argv)

    b_file = pathlib.Path(args.backup_file) if args.backup_file else None
    b_dir = pathlib.Path(args.backup_dir) if args.backup_dir else None
    latest = find_latest_backup(b_dir, b_file)
    live_db = pathlib.Path(args.live_db) if args.live_db else None

    ok, report, logs = verify_backup(latest, live_db_path=live_db, max_epoch_lag=args.max_epoch_lag)
    for line in logs:
        print(line)
    if args.json:
        print(json.dumps(report))
    if not ok and args.webhook_url:
        _send_webhook_alert(args.webhook_url, report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
