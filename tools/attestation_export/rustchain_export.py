#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export RustChain attestation and reward data to CSV, JSON, or JSONL.

The exporter has two data sources:

* API mode uses the public node API and does not require database access.
* SQLite mode reads the node database directly when an operator provides it.

API mode intentionally exports the tables that can be reconstructed from the
public surface. SQLite mode exports richer attestation, reward, and ledger rows.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


DEFAULT_NODE_URL = "https://rustchain.org"
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 0.5
DEFAULT_HISTORY_LIMIT = 200
TABLES = ("miners", "epochs", "rewards", "attestations", "balances")


JsonObject = Dict[str, Any]
TableRows = Dict[str, List[JsonObject]]


class ExportError(RuntimeError):
    """Raised for operator-facing export failures."""


@dataclass(frozen=True)
class DateWindow:
    """Inclusive UTC timestamp window."""

    start_ts: Optional[int] = None
    end_ts: Optional[int] = None

    def includes(self, row: Mapping[str, Any], fields: Sequence[str]) -> bool:
        if self.start_ts is None and self.end_ts is None:
            return True

        timestamp = first_timestamp(row, fields)
        if timestamp is None:
            return True
        if self.start_ts is not None and timestamp < self.start_ts:
            return False
        if self.end_ts is not None and timestamp > self.end_ts:
            return False
        return True


def parse_date(value: Optional[str], *, end_of_day: bool = False) -> Optional[int]:
    """Parse YYYY-MM-DD, Unix seconds, or ISO-8601 into UTC Unix seconds."""

    if not value:
        return None

    text = value.strip()
    if text.isdigit():
        return int(text)

    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        date_value = dt.date.fromisoformat(text)
        if end_of_day:
            parsed = dt.datetime.combine(date_value, dt.time.max, tzinfo=dt.timezone.utc)
        else:
            parsed = dt.datetime.combine(date_value, dt.time.min, tzinfo=dt.timezone.utc)
        return int(parsed.timestamp())

    normalized = text.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.astimezone(dt.timezone.utc).timestamp())


def first_timestamp(row: Mapping[str, Any], fields: Sequence[str]) -> Optional[int]:
    """Return the first integer-like timestamp from a row."""

    for field in fields:
        raw_value = row.get(field)
        if raw_value in (None, ""):
            continue
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            continue
    return None


def utc_iso(timestamp: Any) -> Optional[str]:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return None
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_node_url(url: str) -> str:
    if not url:
        raise ExportError("node URL is required")
    return url.rstrip("/")


class ApiClient:
    """Small stdlib-only JSON client with retry and self-signed TLS support."""

    def __init__(
        self,
        node_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        verify_tls: bool = False,
    ) -> None:
        self.node_url = normalize_node_url(node_url)
        self.timeout = timeout
        self.retries = max(1, retries)
        self.retry_delay = max(0.0, retry_delay)
        self.context = None if verify_tls else ssl._create_unverified_context()

    def get_json(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        query = ""
        if params:
            clean = {key: value for key, value in params.items() if value is not None}
            query = "?" + urllib.parse.urlencode(clean) if clean else ""
        url = f"{self.node_url}{path}{query}"

        last_error: Optional[str] = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout, context=self.context) as response:
                    payload = response.read().decode("utf-8")
                return json.loads(payload)
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}: {exc.reason}"
                if exc.code == 404:
                    raise ExportError(f"{path} returned 404")
            except urllib.error.URLError as exc:
                last_error = f"connection error: {exc.reason}"
            except json.JSONDecodeError as exc:
                raise ExportError(f"{path} returned invalid JSON: {exc}") from exc

            if attempt < self.retries - 1:
                time.sleep(self.retry_delay)

        raise ExportError(f"{path} request failed after {self.retries} attempts: {last_error}")


def ensure_object(value: Any, context: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ExportError(f"{context} response must be a JSON object")
    return value


def ensure_list(value: Any, context: str) -> List[Any]:
    if not isinstance(value, list):
        raise ExportError(f"{context} response must be a JSON array")
    return value


def rows_from_miners_response(value: Any) -> List[JsonObject]:
    if isinstance(value, list):
        rows = value
    else:
        obj = ensure_object(value, "/api/miners")
        rows = obj.get("miners", [])

    miners: List[JsonObject] = []
    for row in ensure_list(rows, "/api/miners miners"):
        if isinstance(row, dict):
            miner = dict(row)
            for field in ("first_attest", "last_attest"):
                iso = utc_iso(miner.get(field))
                if iso:
                    miner[f"{field}_iso"] = iso
            miners.append(miner)
    return miners


def rows_from_epoch_response(value: Any) -> List[JsonObject]:
    epoch = ensure_object(value, "/epoch")
    row = dict(epoch)
    if "epoch" in row:
        row["epoch_number"] = row.get("epoch")
    return [row]


def rows_from_settlement_response(value: Any) -> tuple[List[JsonObject], List[JsonObject]]:
    obj = ensure_object(value, "/rewards/epoch")
    epoch_row = {
        "epoch": obj.get("epoch"),
        "timestamp": obj.get("timestamp"),
        "timestamp_iso": utc_iso(obj.get("timestamp")),
        "total_pot": obj.get("total_pot"),
        "total_distributed": obj.get("total_distributed"),
        "miner_count": obj.get("miner_count"),
        "settlement_hash": obj.get("settlement_hash"),
        "ergo_tx_id": obj.get("ergo_tx_id"),
    }

    reward_rows: List[JsonObject] = []
    rewards = obj.get("rewards", [])
    if isinstance(rewards, dict):
        for miner_id, amount in rewards.items():
            reward_rows.append(
                {
                    "epoch": obj.get("epoch"),
                    "timestamp": obj.get("timestamp"),
                    "timestamp_iso": utc_iso(obj.get("timestamp")),
                    "miner_id": miner_id,
                    "amount_rtc": amount,
                }
            )
    elif isinstance(rewards, list):
        for reward in rewards:
            if isinstance(reward, dict):
                row = dict(reward)
                row.setdefault("epoch", obj.get("epoch"))
                row.setdefault("timestamp", obj.get("timestamp"))
                row["timestamp_iso"] = utc_iso(row.get("timestamp"))
                reward_rows.append(row)

    return [epoch_row], reward_rows


def merge_epoch_row(existing: JsonObject, incoming: Mapping[str, Any]) -> None:
    """Merge settlement details into a current-epoch row without losing fields."""

    for key, value in incoming.items():
        if value in (None, "", []):
            continue
        if existing.get(key) in (None, "", []):
            existing[key] = value


def normalize_balance(miner_id: str, response: Any) -> JsonObject:
    if isinstance(response, dict):
        row = dict(response)
    else:
        row = {"ok": False, "error": "unexpected response"}
    row.setdefault("miner_id", miner_id)
    row.setdefault("amount_rtc", row.get("amount", 0))
    return row


def rows_from_history(miner_id: str, response: Any) -> List[JsonObject]:
    if isinstance(response, dict):
        transactions = response.get("transactions", response.get("transfers", []))
    else:
        transactions = response

    rows: List[JsonObject] = []
    for tx in ensure_list(transactions, "/wallet/history transactions"):
        if isinstance(tx, dict):
            row = dict(tx)
            row.setdefault("miner_id", miner_id)
            row["timestamp_iso"] = utc_iso(row.get("timestamp") or row.get("created_at"))
            rows.append(row)
    return rows


def export_from_api(
    client: ApiClient,
    *,
    date_window: DateWindow,
    reward_epochs: Optional[Sequence[int]] = None,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    include_wallet_history: bool = True,
) -> TableRows:
    tables: TableRows = {name: [] for name in TABLES}

    miners = rows_from_miners_response(client.get_json("/api/miners"))
    tables["miners"] = [
        row for row in miners if date_window.includes(row, ("last_attest", "first_attest"))
    ]

    current_epoch_rows = rows_from_epoch_response(client.get_json("/epoch"))
    tables["epochs"].extend(current_epoch_rows)

    epochs_to_fetch = list(reward_epochs or [])
    if not epochs_to_fetch and current_epoch_rows:
        current_epoch = current_epoch_rows[0].get("epoch")
        try:
            epochs_to_fetch = [int(current_epoch)]
        except (TypeError, ValueError):
            epochs_to_fetch = []

    epoch_rows_by_number = {row.get("epoch"): row for row in tables["epochs"]}
    for epoch in epochs_to_fetch:
        try:
            epoch_rows, reward_rows = rows_from_settlement_response(
                client.get_json(f"/rewards/epoch/{epoch}")
            )
        except ExportError as exc:
            if "404" in str(exc):
                continue
            raise
        for row in epoch_rows:
            epoch_number = row.get("epoch")
            if epoch_number in epoch_rows_by_number:
                merge_epoch_row(epoch_rows_by_number[epoch_number], row)
            elif date_window.includes(row, ("timestamp",)):
                tables["epochs"].append(row)
                epoch_rows_by_number[epoch_number] = row
        tables["rewards"].extend(
            row for row in reward_rows if date_window.includes(row, ("timestamp",))
        )

    miner_ids = sorted({str(row.get("miner")) for row in tables["miners"] if row.get("miner")})
    for miner_id in miner_ids:
        try:
            balance = normalize_balance(
                miner_id,
                client.get_json("/wallet/balance", {"miner_id": miner_id}),
            )
            tables["balances"].append(balance)
        except ExportError as exc:
            tables["balances"].append({"miner_id": miner_id, "ok": False, "error": str(exc)})

        if include_wallet_history:
            try:
                tables["rewards"].extend(
                    row
                    for row in rows_from_history(
                        miner_id,
                        client.get_json(
                            "/wallet/history",
                            {"miner_id": miner_id, "limit": history_limit},
                        ),
                    )
                    if date_window.includes(row, ("timestamp", "created_at"))
                )
            except ExportError:
                pass

    # API mode has a compact attestation surface on /api/miners. Make that
    # explicit instead of emitting a misleading empty attestations table.
    for miner in tables["miners"]:
        tables["attestations"].append(
            {
                "miner_id": miner.get("miner"),
                "first_attest": miner.get("first_attest"),
                "first_attest_iso": miner.get("first_attest_iso"),
                "last_attest": miner.get("last_attest"),
                "last_attest_iso": miner.get("last_attest_iso"),
                "device_arch": miner.get("device_arch"),
                "device_family": miner.get("device_family"),
                "hardware_type": miner.get("hardware_type"),
                "source": "api:mining_summary",
            }
        )

    return tables


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def query_table(
    conn: sqlite3.Connection,
    table_name: str,
    *,
    where: str = "",
    params: Sequence[Any] = (),
) -> List[JsonObject]:
    if not table_exists(conn, table_name):
        return []
    sql = f"SELECT * FROM {table_name}"
    if where:
        sql += f" WHERE {where}"
    cursor = conn.execute(sql, params)
    columns = [col[0] for col in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def export_from_sqlite(db_path: str, *, date_window: DateWindow) -> TableRows:
    if not os.path.exists(db_path):
        raise ExportError(f"database does not exist: {db_path}")

    tables: TableRows = {name: [] for name in TABLES}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = None
        tables["miners"] = query_table(conn, "miner_attest_recent")
        tables["attestations"] = query_table(conn, "miner_attest_recent")
        tables["balances"] = query_table(conn, "balances")
        tables["epochs"] = query_table(conn, "epoch_state")
        tables["rewards"] = query_table(conn, "epoch_rewards")

        ledger_rows = query_table(conn, "ledger")
        for row in ledger_rows:
            row = dict(row)
            row.setdefault("source_table", "ledger")
            tables["rewards"].append(row)

    timestamp_fields = ("timestamp", "created_at", "last_attest", "first_attest", "confirmed_at")
    for table_name, rows in tables.items():
        tables[table_name] = [row for row in rows if date_window.includes(row, timestamp_fields)]
    return tables


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = sorted({field for row in rows for field in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: stringify(row.get(field)) for field in fieldnames})


def stringify(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_json(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(list(rows), handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def write_parquet(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except ImportError as exc:
        raise ExportError("parquet output requires pyarrow") from exc

    normalized = [{key: stringify(value) for key, value in row.items()} for row in rows]
    pq.write_table(pa.Table.from_pylist(normalized), path)


def write_tables(tables: TableRows, output_dir: Path, output_format: str) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    writers = {
        "csv": (".csv", write_csv),
        "json": (".json", write_json),
        "jsonl": (".jsonl", write_jsonl),
        "parquet": (".parquet", write_parquet),
    }
    suffix, writer = writers[output_format]
    written: List[Path] = []

    for table_name in TABLES:
        rows = tables.get(table_name, [])
        path = output_dir / f"{table_name}{suffix}"
        writer(path, rows)
        written.append(path)
    return written


def parse_epoch_list(raw_values: Sequence[str]) -> List[int]:
    epochs: List[int] = []
    for raw in raw_values:
        for part in raw.split(","):
            token = part.strip()
            if not token:
                continue
            if "-" in token:
                start_raw, end_raw = token.split("-", 1)
                start = int(start_raw)
                end = int(end_raw)
                if end < start:
                    raise ExportError(f"invalid epoch range: {token}")
                epochs.extend(range(start, end + 1))
            else:
                epochs.append(int(token))
    return sorted(set(epochs))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export RustChain attestation and reward data.",
    )
    parser.add_argument("--node-url", default=DEFAULT_NODE_URL, help="RustChain node URL")
    parser.add_argument("--db-path", help="Optional local SQLite database path")
    parser.add_argument(
        "--format",
        choices=("csv", "json", "jsonl", "parquet"),
        default="csv",
        help="Output format",
    )
    parser.add_argument("--output", default="data", help="Output directory")
    parser.add_argument("--from", dest="from_date", help="Inclusive start date or Unix seconds")
    parser.add_argument("--to", dest="to_date", help="Inclusive end date or Unix seconds")
    parser.add_argument(
        "--epoch",
        action="append",
        default=[],
        help="Reward epoch or range to fetch, e.g. --epoch 175-179",
    )
    parser.add_argument("--history-limit", type=int, default=DEFAULT_HISTORY_LIMIT)
    parser.add_argument(
        "--no-wallet-history",
        action="store_true",
        help="Skip /wallet/history calls in API mode",
    )
    parser.add_argument(
        "--verify-tls",
        action="store_true",
        help="Verify TLS certificates instead of allowing the self-signed node cert",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    return parser


def summarize(tables: TableRows, written: Iterable[Path]) -> JsonObject:
    return {
        "tables": {name: len(rows) for name, rows in tables.items()},
        "files": [str(path) for path in written],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    date_window = DateWindow(
        start_ts=parse_date(args.from_date),
        end_ts=parse_date(args.to_date, end_of_day=True),
    )

    try:
        if args.db_path:
            tables = export_from_sqlite(args.db_path, date_window=date_window)
        else:
            client = ApiClient(
                args.node_url,
                timeout=args.timeout,
                retries=args.retries,
                verify_tls=args.verify_tls,
            )
            tables = export_from_api(
                client,
                date_window=date_window,
                reward_epochs=parse_epoch_list(args.epoch),
                history_limit=args.history_limit,
                include_wallet_history=not args.no_wallet_history,
            )

        written = write_tables(tables, Path(args.output), args.format)
        print(json.dumps(summarize(tables, written), indent=2, sort_keys=True))
        return 0
    except (ExportError, OSError, sqlite3.Error, ValueError) as exc:
        print(f"rustchain_export: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
