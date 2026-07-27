# SPDX-License-Identifier: MIT
"""
verify_backup.py - RustChain SQLite backup integrity verifier

Verifies the latest local backup against the live database and reports PASS/FAIL.
Extended features:
- Recency check: backup must be no more than 1 epoch behind the live DB.
- Alert on failure: optional webhook POST (JSON) and mailto fallback.
- SHA-256 digest of the verified backup file.
- Gzip-decompressed backup support (.db.gz / .db.gz*).
- --json for machine-readable output (CI / cron friendly).

Usage:
    # Default (reads /root/rustchain/*, live vs latest backup)
    python3 tools/verify_backup.py

    # Custom paths + webhook alert on failure
    python3 tools/verify_backup.py \\
        --backup-dir /root/rustchain/backups \\
        --pattern rustchain_v2*.db* \\
        --live-db /root/rustchain/rustchain_v2.db \\
        --on-fail-webhook https://hooks.example.com/rustchain-backup

    # Machine-readable JSON for cron / CI
    python3 tools/verify_backup.py --json
"""

from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json as _json
import logging
import os
import sqlite3
import smtplib
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from shutil import copy2
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("verify_backup")

REQUIRED_TABLES = [
    "balances",
    "miner_attest_recent",
    "headers",
    "ledger",
    "epoch_rewards",
]

SUPPORTED_BALANCE_COLUMNS = (
    "amount",
    "balance_rtc",
    "balance",
    "amount_i64",
)

MAX_EPOCH_DRIFT = 1


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Outcome of a single verification run."""

    ok: bool
    message: str
    backup_file: str | None = None
    sha256: str | None = None
    epoch_drift: int | None = None
    recency_ok: bool | None = None
    checks: list[dict[str, Any]] = None  # type: ignore[assignment]  # filled by __post_init__

    def __post_init__(self) -> None:
        if self.checks is None:
            self.checks = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "backup_file": self.backup_file,
            "sha256": self.sha256,
            "epoch_drift": self.epoch_drift,
            "recency_ok": self.recency_ok,
            "checks": self.checks,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def query_one(conn: sqlite3.Connection, sql: str) -> str:
    """Execute ``sql`` and return the first column of the first row as a str."""
    row = conn.execute(sql).fetchone()
    return "" if row is None or row[0] is None else str(row[0])


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?;",
        (table,),
    ).fetchone()
    return row is not None


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table});")}


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(query_one(conn, f"SELECT COUNT(*) FROM {table};") or 0)


def positive_balances(conn: sqlite3.Connection) -> int:
    columns = column_names(conn, "balances")
    for column in SUPPORTED_BALANCE_COLUMNS:
        if column in columns:
            return int(
                query_one(conn, f"SELECT COUNT(*) FROM balances WHERE {column} > 0;")
                or 0
            )
    raise sqlite3.OperationalError(
        f"balances table has no supported positive-balance column "
        f"(expected {', '.join(SUPPORTED_BALANCE_COLUMNS)})"
    )


def epoch_max(conn: sqlite3.Connection) -> int:
    v = query_one(conn, "SELECT COALESCE(MAX(epoch), 0) FROM epoch_rewards;")
    return int(v or 0)


def sha256_file(path: str) -> str:
    """Return the hex SHA-256 digest of ``path``."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Backup discovery
# ---------------------------------------------------------------------------


def latest_backup(backup_dir: str, pattern: str) -> str | None:
    """Return the most recently modified file matching ``pattern`` in ``backup_dir``."""
    candidates = glob.glob(os.path.join(backup_dir, pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def resolve_backup_file(path: str) -> tuple[str, bool]:
    """
    Resolve ``path`` to a real SQLite file on disk.

    If the file ends in ``.gz`` (or ``.db.gz``), it is decompressed into a
    temporary file that is returned. Returns ``(resolved_path, was_gzipped)``.
    """
    if not os.path.exists(path):
        return path, False  # let caller fail on missing-file with a clear message

    if path.endswith(".gz"):
        # Caller is responsible for cleaning up the temp file.
        tmp = tempfile.NamedTemporaryFile(
            prefix="backup-decompressed-", suffix=".db", delete=False
        )
        tmp.close()
        with gzip.open(path, "rb") as f_in, open(tmp.name, "wb") as f_out:
            for chunk in iter(lambda: f_in.read(65536), b""):
                f_out.write(chunk)
        return tmp.name, True

    return path, False


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _open_conn(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path)


def verify(
    live_db: str,
    backup_file: str,
    require_recency: bool = True,
) -> CheckResult:
    """
    Compare ``backup_file`` (a path to a SQLite DB) against ``live_db``.

    Checks performed:
    - File existence (backup and live).
    - SQLite ``PRAGMA integrity_check`` on the backup.
    - Required tables exist and have data in both databases.
    - Row counts are not more than 5 % behind the live DB (>= 1 row required).
    - At least one positive balance.
    - Epoch drift (max 1 epoch) when ``require_recency`` is True.

    On success ``CheckResult.ok`` is ``True`` and ``.message`` is ``"RESULT: PASS"``.
    On failure ``.ok`` is ``False`` and ``.message`` begins with ``"RESULT: FAIL"``.
    """
    checks: list[dict[str, Any]] = []
    backup_file = os.path.abspath(backup_file)

    # Existence
    if not os.path.exists(live_db):
        return CheckResult(
            ok=False,
            message=f"RESULT: FAIL (live db missing: {live_db})",
            backup_file=backup_file,
            checks=checks,
        )
    if not os.path.exists(backup_file):
        return CheckResult(
            ok=False,
            message=f"RESULT: FAIL (backup file missing: {backup_file})",
            backup_file=backup_file,
            checks=checks,
        )

    lconn = _open_conn(live_db)
    bconn = _open_conn(backup_file)
    ok = True

    # SHA-256 digest of the file being verified.
    try:
        digest = sha256_file(backup_file)
    except OSError as exc:
        bconn.close()
        lconn.close()
        return CheckResult(
            ok=False,
            message=f"RESULT: FAIL (cannot hash backup file: {exc})",
            backup_file=backup_file,
            checks=checks,
        )

    try:
        # Integrity check
        integrity = query_one(bconn, "PRAGMA integrity_check;")
        integ_ok = integrity.lower() == "ok"
        checks.append(
            {"name": "integrity_check", "ok": integ_ok, "value": integrity}
        )
        if not integ_ok:
            ok = False
            return CheckResult(
                ok=False,
                message="RESULT: FAIL (backup integrity check failed)",
                backup_file=backup_file,
                sha256=digest,
                checks=checks,
            )

        # Required tables
        for t in REQUIRED_TABLES:
            in_b = table_exists(bconn, t)
            in_l = table_exists(lconn, t)
            if not in_b:
                checks.append({"name": t, "ok": False, "value": "missing in backup"})
                ok = False
                continue
            if not in_l:
                checks.append({"name": t, "ok": False, "value": "missing in live db"})
                ok = False
                continue

            b_count = count_rows(bconn, t)
            l_count = count_rows(lconn, t)
            table_ok = b_count > 0 and (l_count - b_count) <= max(
                1, int(l_count * 0.05)
            )
            checks.append(
                {
                    "name": t,
                    "ok": table_ok,
                    "value": f"backup={b_count}, live={l_count}",
                }
            )
            if not table_ok:
                ok = False

        # Positive balances
        try:
            pos = positive_balances(bconn)
            pos_ok = pos > 0
            checks.append({"name": "positive_balances", "ok": pos_ok, "value": pos})
            if not pos_ok:
                ok = False
        except sqlite3.OperationalError as exc:
            checks.append({"name": "positive_balances", "ok": False, "value": str(exc)})
            ok = False

        # Recency: epoch drift between backup and live DB.
        b_epoch = epoch_max(bconn)
        l_epoch = epoch_max(lconn)
        epoch_drift = l_epoch - b_epoch
        recency_ok: bool | None = True
        if require_recency:
            recency_ok = epoch_drift <= MAX_EPOCH_DRIFT
            checks.append(
                {
                    "name": "epoch_drift",
                    "ok": recency_ok,
                    "value": f"backup_epoch={b_epoch}, live_epoch={l_epoch}, drift={epoch_drift}",
                }
            )
            if recency_ok is False:
                ok = False

        return CheckResult(
            ok=ok,
            message="RESULT: PASS" if ok else "RESULT: FAIL",
            backup_file=backup_file,
            sha256=digest,
            epoch_drift=epoch_drift,
            recency_ok=recency_ok,
            checks=checks,
        )

    except sqlite3.Error as exc:
        return CheckResult(
            ok=False,
            message=f"RESULT: FAIL (SQLite error: {exc})",
            backup_file=backup_file,
            sha256=digest,
            checks=checks,
        )
    finally:
        bconn.close()
        lconn.close()


# ---------------------------------------------------------------------------
# Alerts (bounty deliverable #7)
# ---------------------------------------------------------------------------


def _build_alert_payload(result: CheckResult, host: str | None = None) -> dict:
    return {
        "ok": result.ok,
        "ts": utcnow(),
        "host": host or os.uname().nodename,
        "backup_file": result.backup_file,
        "sha256": result.sha256,
        "epoch_drift": result.epoch_drift,
        "recency_ok": result.recency_ok,
        "message": result.message,
        "checks": result.checks,
    }


def send_webhook_alert(url: str, payload: dict, timeout: int = 10) -> None:
    """POST ``payload`` as JSON to ``url``. Best-effort; logs on failure."""
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "rustchain-verify-backup/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            log.info("webhook alert %s %s", resp.status, resp.read().decode("utf-8", errors="replace")[:200])
    except (urllib.error.URLError, OSError) as exc:
        log.error("webhook alert failed: %s", exc)


def send_mail_alert(
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
) -> None:
    """Send a plain-text alert email. Best-effort; logs on failure."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(username, password)
            server.send_message(msg)
        log.info("email alert sent to %s", to_addr)
    except Exception as exc:  # noqa: BLE001
        log.error("email alert failed: %s", exc)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def format_human(result: CheckResult) -> str:
    lines = [result.message]
    if result.backup_file:
        lines.append(f"  backup_file: {result.backup_file}")
    if result.sha256:
        lines.append(f"  sha256: {result.sha256}")
    if result.epoch_drift is not None:
        lines.append(
            f"  epoch_drift: {result.epoch_drift}"
            f"{' (PASS)' if result.recency_ok else ' (FAIL - >1 epoch behind)'}"
        )
    for c in result.checks:
        mark = "✅" if c["ok"] else "❌"
        lines.append(f"  {mark} {c['name']}: {c['value']}")
    return "\n".join(lines)


def format_json(result: CheckResult) -> str:
    return _json.dumps(asdict(result), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Verify latest RustChain SQLite backup integrity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--backup-dir",
        default="/root/rustchain/backups",
        help="Directory containing backup files (default: /root/rustchain/backups)",
    )
    p.add_argument(
        "--pattern",
        default="rustchain_v2*.db*",
        help="Glob pattern for backups (default: rustchain_v2*.db*)",
    )
    p.add_argument(
        "--live-db",
        default="/root/rustchain/rustchain_v2.db",
        help="Path to the live RustChain SQLite DB",
    )
    p.add_argument(
        "--backup-file",
        default=None,
        help="Override: explicit backup file path (ignores --backup-dir/--pattern)",
    )
    p.add_argument(
        "--no-recency",
        action="store_true",
        help="Skip the epoch-drift / recency check",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable lines",
    )
    p.add_argument(
        "--on-fail-webhook",
        default=None,
        help="Webhook URL: POST JSON alert if verification FAILs",
    )
    p.add_argument(
        "--on-fail-smtp-host",
        default=None,
        help="SMTP host for email alert (requires --on-fail-smtp-user, --password, --on-fail-to)",
    )
    p.add_argument("--on-fail-smtp-port", type=int, default=587)
    p.add_argument("--on-fail-smtp-user", default=None)
    p.add_argument("--on-fail-smtp-password", default=None)
    p.add_argument("--on-fail-smtp-from", default=None)
    p.add_argument(
        "--on-fail-to",
        default=None,
        help="Destination email for alert",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Select the backup file.
    backup_file: str | None
    if args.backup_file:
        backup_file = args.backup_file
    else:
        backup_file = latest_backup(args.backup_dir, args.pattern)

    if not backup_file or not os.path.exists(backup_file):
        result = CheckResult(
            ok=False,
            message=f"RESULT: FAIL (no backup found in {args.backup_dir} with pattern {args.pattern})",
            backup_file=backup_file,
        )
        _print_result(result, args)
        return 1

    # Decompress gzip on the fly.
    decompressed_path = backup_file
    was_gzipped = False
    decompressed_path, was_gzipped = resolve_backup_file(backup_file)
    result = CheckResult(
        ok=False,
        message="RESULT: FAIL (unexpected verification error)",
        backup_file=backup_file,
    )
    ok: bool = False
    try:
        result = verify(args.live_db, decompressed_path, require_recency=not args.no_recency)
        _print_result(result, args)
        ok = result.ok
    finally:
        if was_gzipped:
            try:
                os.unlink(decompressed_path)
            except OSError:
                pass
        if not ok and args.on_fail_webhook:
            send_webhook_alert(args.on_fail_webhook, _build_alert_payload(result))
        if not ok and args.on_fail_smtp_host:
            send_mail_alert(
                smtp_host=args.on_fail_smtp_host,
                smtp_port=args.on_fail_smtp_port,
                username=args.on_fail_smtp_user or "",
                password=args.on_fail_smtp_password or "",
                from_addr=args.on_fail_smtp_from or "noreply@rustchain",
                to_addr=args.on_fail_to or "",
                subject=f"[FAIL] RustChain backup verification ({utcnow()})",
                body=format_human(result),
            )

    return 0 if ok else 1


def _print_result(result: CheckResult, args: argparse.Namespace) -> None:
    if args.json:
        print(format_json(result))
    else:
        print(format_human(result))


if __name__ == "__main__":
    raise SystemExit(main())
