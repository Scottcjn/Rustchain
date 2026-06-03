#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export RustChain attestation and reward data.

Supports the public node API for portable snapshots and a local SQLite database
for complete historical exports.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TABLES = ("miners", "epochs", "rewards", "attestations", "balances")
MICRO_RTC = 1_000_000


@dataclass(frozen=True)
class ExportOptions:
    mode: str
    output_format: str
    output_dir: Path
    node_url: str
    db_path: Path | None
    start_ts: int | None
    end_ts: int | None
    timeout: float
    insecure: bool


def parse_date(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        return int(text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if len(text) == 10:
        text += "T00:00:00+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def normalize_rtc(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return 0.0
    if abs(amount) >= MICRO_RTC:
        return amount / MICRO_RTC
    return amount


def normalize_micro_rtc(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value) / MICRO_RTC
    except (TypeError, ValueError):
        return 0.0


def balance_amount_rtc(row: dict[str, Any]) -> float:
    for column in ("amount_i64", "balance_urtc"):
        if column in row and row[column] is not None:
            return normalize_micro_rtc(row[column])
    return normalize_rtc(row.get("balance_rtc", row.get("amount")))


def in_range(timestamp: Any, start_ts: int | None, end_ts: int | None) -> bool:
    if timestamp in (None, ""):
        return True
    try:
        ts = int(float(timestamp))
    except (TypeError, ValueError):
        return True
    if start_ts is not None and ts < start_ts:
        return False
    if end_ts is not None and ts > end_ts:
        return False
    return True


def fetch_json(node_url: str, endpoint: str, timeout: float, insecure: bool) -> Any:
    url = f"{node_url.rstrip('/')}{endpoint}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "RustChain-Data-Export/1.0"},
    )
    context = None
    if insecure:
        import ssl

        context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def miners_from_api(options: ExportOptions) -> list[dict[str, Any]]:
    payload = fetch_json(options.node_url, "/api/miners", options.timeout, options.insecure)
    miners = payload.get("miners", payload) if isinstance(payload, dict) else payload
    rows = []
    for item in miners or []:
        miner_id = item.get("miner") or item.get("miner_id") or item.get("id") or ""
        last_attest = item.get("last_attest", item.get("last_attestation"))
        if not in_range(last_attest, options.start_ts, options.end_ts):
            continue
        balance = {}
        if miner_id:
            query = urllib.parse.urlencode({"miner_id": miner_id})
            try:
                balance = fetch_json(options.node_url, f"/wallet/balance?{query}", options.timeout, options.insecure)
            except RuntimeError:
                balance = {}
        rows.append(
            {
                "miner_id": miner_id,
                "device_family": item.get("device_family", ""),
                "device_arch": item.get("device_arch", ""),
                "hardware_type": item.get("hardware_type", ""),
                "antiquity_multiplier": item.get("antiquity_multiplier", ""),
                "entropy_score": item.get("entropy_score", ""),
                "last_attestation": last_attest,
                "total_earnings_rtc": balance.get("amount_rtc", ""),
            }
        )
    return rows


def epochs_from_api(options: ExportOptions) -> list[dict[str, Any]]:
    epoch = fetch_json(options.node_url, "/epoch", options.timeout, options.insecure)
    return [
        {
            "epoch": epoch.get("epoch", ""),
            "slot": epoch.get("slot", ""),
            "timestamp": "",
            "epoch_pot": epoch.get("epoch_pot", ""),
            "settled": "",
            "enrolled_miners": epoch.get("enrolled_miners", ""),
            "blocks_per_epoch": epoch.get("blocks_per_epoch", ""),
        }
    ]


def api_exports(options: ExportOptions) -> dict[str, list[dict[str, Any]]]:
    miners = miners_from_api(options)
    return {
        "miners": miners,
        "epochs": epochs_from_api(options),
        "balances": [
            {"miner_id": row["miner_id"], "amount_rtc": row["total_earnings_rtc"]}
            for row in miners
            if row.get("miner_id")
        ],
        "attestations": [
            {
                "miner_id": row["miner_id"],
                "timestamp": row["last_attestation"],
                "device_arch": row["device_arch"],
                "hardware_type": row["hardware_type"],
                "source": "api:/api/miners",
            }
            for row in miners
        ],
        "rewards": [],
    }


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def query_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params)]


def select_time_filtered(
    conn: sqlite3.Connection,
    table: str,
    timestamp_column: str | None,
    order_column: str | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, table):
        return []
    where = []
    params: list[Any] = []
    table_columns = columns(conn, table)
    if timestamp_column and timestamp_column in table_columns:
        if getattr(select_time_filtered, "start_ts", None) is not None:
            where.append(f"{timestamp_column} >= ?")
            params.append(select_time_filtered.start_ts)
        if getattr(select_time_filtered, "end_ts", None) is not None:
            where.append(f"{timestamp_column} <= ?")
            params.append(select_time_filtered.end_ts)
    sql = f"SELECT * FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if order_column and order_column in table_columns:
        sql += f" ORDER BY {order_column}"
    return query_rows(conn, sql, tuple(params))


def db_exports(options: ExportOptions) -> dict[str, list[dict[str, Any]]]:
    if options.db_path is None:
        raise ValueError("--db is required in db mode")
    setattr(select_time_filtered, "start_ts", options.start_ts)
    setattr(select_time_filtered, "end_ts", options.end_ts)
    conn = sqlite3.connect(options.db_path)
    try:
        attestations = select_time_filtered(conn, "miner_attest_recent", "ts_ok", "ts_ok")
        balances = select_time_filtered(conn, "balances", None)
        epoch_state = select_time_filtered(conn, "epoch_state", "settled_ts", "epoch")
        rewards = select_time_filtered(conn, "epoch_rewards", None, "epoch")
        ledger = select_time_filtered(conn, "ledger", "ts", "ts")
    finally:
        conn.close()

    balance_rows = []
    for row in balances:
        miner_id = row.get("miner_id") or row.get("miner_pk") or row.get("wallet") or row.get("address")
        balance_rows.append({"miner_id": miner_id, "amount_rtc": balance_amount_rtc(row)})

    return {
        "miners": [
            {
                "miner_id": row.get("miner"),
                "device_family": row.get("device_family", ""),
                "device_arch": row.get("device_arch", ""),
                "hardware_type": row.get("hardware_type", ""),
                "antiquity_multiplier": row.get("warthog_bonus", row.get("antiquity_multiplier", "")),
                "entropy_score": row.get("entropy_score", ""),
                "last_attestation": row.get("ts_ok"),
                "total_earnings_rtc": "",
            }
            for row in attestations
        ],
        "epochs": epoch_state,
        "rewards": rewards,
        "attestations": attestations,
        "balances": balance_rows,
        "ledger": ledger,
    }


DEFAULT_HEADERS = {
    "miners": [
        "antiquity_multiplier",
        "device_arch",
        "device_family",
        "entropy_score",
        "hardware_type",
        "last_attestation",
        "miner_id",
        "total_earnings_rtc",
    ],
    "epochs": [
        "blocks_per_epoch",
        "epoch",
        "epoch_pot",
        "enrolled_miners",
        "settled",
        "slot",
        "timestamp",
    ],
    "rewards": ["epoch", "miner_id", "share_i64", "amount_rtc"],
    "attestations": ["miner_id", "timestamp", "device_arch", "hardware_type", "source"],
    "balances": ["miner_id", "amount_rtc"],
    "ledger": ["ts", "epoch", "miner_id", "delta_i64", "reason"],
}


def write_csv(path: Path, rows: list[dict[str, Any]], default_headers: list[str] | None = None) -> None:
    if rows:
        fieldnames = sorted({key for row in rows for key in row.keys()})
    else:
        fieldnames = sorted(default_headers) if default_headers else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_exports(exports: dict[str, list[dict[str, Any]]], options: ExportOptions) -> None:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "jsonl" if options.output_format == "jsonl" else options.output_format
    for table in TABLES:
        rows = exports.get(table, [])
        path = options.output_dir / f"{table}.{suffix}"
        if options.output_format == "csv":
            write_csv(path, rows, DEFAULT_HEADERS.get(table))
        elif options.output_format == "json":
            write_json(path, rows)
        elif options.output_format == "jsonl":
            write_jsonl(path, rows)
    manifest = {
        "mode": options.mode,
        "format": options.output_format,
        "tables": {table: len(exports.get(table, [])) for table in TABLES},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(options.output_dir / "manifest.json", [manifest])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export RustChain data to CSV, JSON, or JSONL")
    parser.add_argument("--mode", choices=("api", "db"), default="api")
    parser.add_argument("--format", choices=("csv", "json", "jsonl"), default="csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", default="https://rustchain.org")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--from", dest="from_date")
    parser.add_argument("--to", dest="to_date")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification for legacy IP endpoints")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = ExportOptions(
        mode=args.mode,
        output_format=args.format,
        output_dir=args.output,
        node_url=args.node,
        db_path=args.db,
        start_ts=parse_date(args.from_date),
        end_ts=parse_date(args.to_date),
        timeout=args.timeout,
        insecure=args.insecure,
    )
    exports = api_exports(options) if options.mode == "api" else db_exports(options)
    write_exports(exports, options)
    print(json.dumps({"ok": True, "output": str(options.output_dir), "tables": list(TABLES)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
