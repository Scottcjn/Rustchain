#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RustChain attestation data export pipeline.

Exports miners, epochs, rewards, attestations, and balances to CSV, JSON,
JSONL, or Parquet.  Works against the live node API (no DB access required)
or a local SQLite database for full historical data.

Usage (API mode):
    python3 rustchain_export.py --format csv --output data/
    python3 rustchain_export.py --format parquet --output data/ --from 2026-01-01

Usage (DB mode):
    python3 rustchain_export.py --mode db --db rustchain.db --format json --output data/
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_TABLES = ("miners", "epochs", "rewards", "attestations", "balances")
MICRO_RTC = 1_000_000

# Column order for each export table (used as default headers).
TABLE_COLUMNS: dict[str, list[str]] = {
    "miners": ["miner_id", "device_arch", "last_attest", "total_earnings_rtc"],
    "epochs": ["epoch", "timestamp", "pot_size", "settled"],
    "rewards": ["miner_id", "epoch", "amount_rtc"],
    "attestations": ["miner_id", "timestamp", "device_arch", "hardware_type"],
    "balances": ["miner_id", "amount_rtc"],
}

# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------


def parse_date(value: str | None) -> int | None:
    """Parse *YYYY-MM-DD*, ISO-8601, or a bare Unix timestamp into an int."""
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


def in_range(ts: Any, lo: int | None, hi: int | None) -> bool:
    if ts in (None, ""):
        return True
    try:
        v = int(float(ts))
    except (TypeError, ValueError):
        return True
    if lo is not None and v < lo:
        return False
    if hi is not None and v > hi:
        return False
    return True


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------


def to_rtc(value: Any) -> float:
    """Coerce *value* to an RTC float.  Values >= 1 000 000 are treated as
    micro-RTC and divided automatically (heuristic fallback)."""
    if value is None:
        return 0.0
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return 0.0
    if abs(amount) >= MICRO_RTC:
        return round(amount / MICRO_RTC, 6)
    return round(amount, 6)


def micro_to_rtc(value: Any) -> float:
    """Convert a *micro-RTC* value (always divided by 1M) to RTC."""
    if value is None:
        return 0.0
    try:
        return round(float(value) / MICRO_RTC, 6)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# HTTP helpers  (stdlib only – no ``requests`` dependency)
# ---------------------------------------------------------------------------


def fetch_json(url: str, timeout: float = 15.0) -> Any:
    """GET *url* and return parsed JSON."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "RustChain-DataExport/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"fetch failed ({url}): {exc}") from exc


# ---------------------------------------------------------------------------
# Streaming writers
# ---------------------------------------------------------------------------


def _parquet_cell(value: Any) -> str | None:
    """Coerce a cell to a string for pyarrow string columns."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


class _CSVWriter:
    """Append-mode CSV writer backed by an open file handle."""

    def __init__(self, fh: io.TextIOBase, columns: list[str]) -> None:
        self._columns = columns
        self._writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        self._writer.writeheader()
        self._fh = fh

    def write_row(self, row: dict[str, Any]) -> None:
        self._writer.writerow(_sanitize_row(row, self._columns))

    def close(self) -> None:
        self._fh.close()


class _JSONWriter:
    """Writes ``[\n  ...items...\n]\n`` incrementally without building a
    complete list in memory.  Items are written as they arrive."""

    def __init__(self, fh: io.TextIOBase) -> None:
        self._fh = fh
        self._fh.write("[\n")
        self._count = 0

    def write_row(self, row: dict[str, Any]) -> None:
        if self._count:
            self._fh.write(",\n")
        json.dump(row, self._fh, sort_keys=True, ensure_ascii=False)
        self._count += 1

    def close(self) -> None:
        self._fh.write("\n]\n")
        self._fh.close()


class _JSONLWriter:
    """One JSON object per line – naturally streaming."""

    def __init__(self, fh: io.TextIOBase) -> None:
        self._fh = fh

    def write_row(self, row: dict[str, Any]) -> None:
        self._fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")

    def close(self) -> None:
        self._fh.close()


class _ParquetWriter:
    """Collects rows in memory then writes a single Parquet file via
    *pyarrow*.  pyarrow is the only non-stdlib dependency and is optional."""

    def __init__(self, path: Path, columns: list[str]) -> None:
        try:
            import pyarrow as pa  # noqa: F811
            import pyarrow.parquet as pq  # noqa: F811
        except ImportError as exc:
            raise RuntimeError(
                "parquet format requires pyarrow: pip install pyarrow"
            ) from exc
        self._path = path
        self._columns = columns
        self._buffers: dict[str, list[Any]] = {c: [] for c in columns}
        self._pa = pa
        self._pq = pq

    def write_row(self, row: dict[str, Any]) -> None:
        for col in self._columns:
            self._buffers[col].append(_parquet_cell(row.get(col)))

    def close(self) -> None:
        arrays = [
            self._pa.array(self._buffers[c], type=self._pa.string())
            for c in self._columns
        ]
        table = self._pa.table(arrays, names=self._columns)
        self._pq.write_table(table, self._path)


class _Writer:
    """Unified interface returned by ``make_writer``."""

    def __init__(self, writer: Any, path: Path | None = None) -> None:
        self._writer = writer
        self._path = path

    def write_row(self, row: dict[str, Any]) -> None:
        self._writer.write_row(row)

    def close(self) -> None:
        self._writer.close()


def _sanitize_row(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    """Prefix spreadsheet-dangerous strings to prevent formula injection."""
    out: dict[str, Any] = {}
    for col in columns:
        val = row.get(col)
        if isinstance(val, str) and val and val[0] in "=+-@\t\r\n":
            val = "'" + val
        out[col] = val
    return out


def make_writer(
    path: Path, fmt: str, columns: list[str]
) -> _Writer:
    if fmt == "csv":
        fh = path.open("w", newline="", encoding="utf-8")
        return _Writer(_CSVWriter(fh, columns), path)
    if fmt == "json":
        fh = path.open("w", encoding="utf-8")
        return _Writer(_JSONWriter(fh), path)
    if fmt == "jsonl":
        fh = path.open("w", encoding="utf-8")
        return _Writer(_JSONLWriter(fh), path)
    if fmt == "parquet":
        return _Writer(_ParquetWriter(path, columns), path)
    raise ValueError(f"unsupported format: {fmt}")


# ---------------------------------------------------------------------------
# API mode
# ---------------------------------------------------------------------------


class APIClient:
    """Thin wrapper around the RustChain public HTTP API."""

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _get(self, path: str) -> Any:
        return fetch_json(f"{self._base}{path}", timeout=self._timeout)

    def miners(self) -> list[dict[str, Any]]:
        data = self._get("/api/miners")
        return data if isinstance(data, list) else data.get("miners", [])

    def epoch(self) -> dict[str, Any]:
        return self._get("/epoch")

    def balance(self, miner_id: str) -> dict[str, Any]:
        q = urllib.parse.urlencode({"miner_id": miner_id})
        try:
            return self._get(f"/wallet/balance?{q}")
        except RuntimeError:
            return {}

    def history(self, miner_id: str, limit: int = 200) -> list[dict[str, Any]]:
        q = urllib.parse.urlencode({"miner_id": miner_id, "limit": limit})
        try:
            data = self._get(f"/wallet/history?{q}")
            return data.get("transactions", [])
        except RuntimeError:
            return []


def export_api(
    client: APIClient,
    *,
    start_ts: int | None = None,
    end_ts: int | None = None,
    miner_id_filter: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Gather all five tables from the live API.

    API mode produces *snapshot* data: current miners, current epoch,
    current balances, and the best-effort attestation records embedded
    in the miner list.  Per-epoch reward history is not fully available
    via the public API; the ``rewards`` table will contain only the
    ``wallet/history`` entries with ``type == "reward"`` when a
    ``--miner-id`` filter is supplied.
    """
    raw_miners = client.miners()

    # --- miners + attestations ---
    miners: list[dict[str, Any]] = []
    attestations: list[dict[str, Any]] = []
    for m in raw_miners:
        mid = m.get("miner") or m.get("miner_id") or ""
        if miner_id_filter and mid != miner_id_filter:
            continue
        la = m.get("last_attest")
        if not in_range(la, start_ts, end_ts):
            continue
        row = {
            "miner_id": mid,
            "device_arch": m.get("device_arch", ""),
            "last_attest": la,
            "total_earnings_rtc": "",
        }
        miners.append(row)
        attestations.append(
            {
                "miner_id": mid,
                "timestamp": la,
                "device_arch": m.get("device_arch", ""),
                "hardware_type": m.get("hardware_type", ""),
            }
        )

    # --- balances ---
    balances: list[dict[str, Any]] = []
    for m in miners:
        if not m["miner_id"]:
            continue
        b = client.balance(m["miner_id"])
        bal = (
            to_rtc(b["amount_rtc"])
            if "amount_rtc" in b
            else micro_to_rtc(b.get("amount_i64", 0))
        )
        balances.append({"miner_id": m["miner_id"], "amount_rtc": bal})
        m["total_earnings_rtc"] = bal

    # --- epochs (current only) ---
    try:
        ep = client.epoch()
        ts_est = int(datetime.now(timezone.utc).timestamp())  # approx
        epochs: list[dict[str, Any]] = [
            {
                "epoch": ep.get("epoch", ""),
                "timestamp": ts_est,
                "pot_size": ep.get("epoch_pot", ""),
                "settled": "",
            }
        ]
    except RuntimeError:
        epochs = []

    # --- rewards (from wallet/history, miner_id filter required) ---
    rewards: list[dict[str, Any]] = []
    if miner_id_filter:
        for tx in client.history(miner_id_filter):
            if tx.get("type") == "reward":
                rewards.append(
                    {
                        "miner_id": miner_id_filter,
                        "epoch": tx.get("epoch", ""),
                        "amount_rtc": to_rtc(tx.get("amount", 0)),
                    }
                )

    return {
        "miners": miners,
        "epochs": epochs,
        "rewards": rewards,
        "attestations": attestations,
        "balances": balances,
    }


# ---------------------------------------------------------------------------
# DB mode
# ---------------------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cur.fetchone() is not None


def _query(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params)]


def export_db(
    db_path: Path,
    *,
    start_ts: int | None = None,
    end_ts: int | None = None,
    miner_id_filter: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Read from the five canonical SQLite tables."""
    conn = sqlite3.connect(str(db_path))
    try:
        attestations = _safe_query_table(conn, "miner_attest_recent", "ts_ok", start_ts, end_ts)
        balances_raw = _safe_query_table(conn, "balances", None, None, None)
        epochs_raw = _safe_query_table(conn, "epoch_state", "settled_ts", start_ts, end_ts)
        rewards_raw = _safe_query_table(conn, "epoch_rewards", None, None, None)
    finally:
        conn.close()

    # Normalise miners from attestations
    miners: list[dict[str, Any]] = []
    for a in attestations:
        mid = a.get("miner") or a.get("miner_id") or ""
        if miner_id_filter and mid != miner_id_filter:
            continue
        miners.append(
            {
                "miner_id": mid,
                "device_arch": a.get("device_arch", ""),
                "last_attest": a.get("ts_ok", ""),
                "total_earnings_rtc": "",
            }
        )

    # Normalise balances
    balances: list[dict[str, Any]] = []
    for b in balances_raw:
        mid = b.get("miner_id") or b.get("miner_pk") or b.get("wallet") or b.get("address") or ""
        if miner_id_filter and mid != miner_id_filter:
            continue
        bal = (
            micro_to_rtc(b["amount_i64"])
            if "amount_i64" in b
            else to_rtc(b.get("amount", b.get("amount_rtc", 0)))
        )
        balances.append({"miner_id": mid, "amount_rtc": bal})

    # Fill total_earnings on miners from balances
    bal_map = {b["miner_id"]: b["amount_rtc"] for b in balances}
    for m in miners:
        m["total_earnings_rtc"] = bal_map.get(m["miner_id"], "")

    # Normalise epochs
    epochs: list[dict[str, Any]] = []
    for e in epochs_raw:
        epochs.append(
            {
                "epoch": e.get("epoch", ""),
                "timestamp": e.get("settled_ts", ""),
                "pot_size": e.get("epoch_pot", e.get("pot_size", "")),
                "settled": e.get("settled", e.get("status", "")),
            }
        )

    # Normalise rewards
    rewards: list[dict[str, Any]] = []
    for r in rewards_raw:
        mid = r.get("miner_id") or r.get("miner") or ""
        if miner_id_filter and mid != miner_id_filter:
            continue
        rewards.append(
            {
                "miner_id": mid,
                "epoch": r.get("epoch", ""),
                "amount_rtc": (
                    micro_to_rtc(r["amount_i64"])
                    if "amount_i64" in r
                    else to_rtc(r.get("amount_rtc", r.get("amount", 0)))
                ),
            }
        )

    # Normalise attestations for output
    att_out: list[dict[str, Any]] = []
    for a in attestations:
        mid = a.get("miner") or a.get("miner_id") or ""
        if miner_id_filter and mid != miner_id_filter:
            continue
        att_out.append(
            {
                "miner_id": mid,
                "timestamp": a.get("ts_ok", ""),
                "device_arch": a.get("device_arch", ""),
                "hardware_type": a.get("hardware_type", ""),
            }
        )

    return {
        "miners": miners,
        "epochs": epochs,
        "rewards": rewards,
        "attestations": att_out,
        "balances": balances,
    }


def _safe_query_table(
    conn: sqlite3.Connection,
    table: str,
    ts_col: str | None,
    start_ts: int | None,
    end_ts: int | None,
) -> list[dict[str, Any]]:
    """Query a table; return ``[]`` if the table doesn't exist."""
    if not _table_exists(conn, table):
        return []
    where: list[str] = []
    params: list[Any] = []
    if ts_col and start_ts is not None:
        where.append(f"{ts_col} >= ?")
        params.append(start_ts)
    if ts_col and end_ts is not None:
        where.append(f"{ts_col} <= ?")
        params.append(end_ts)
    sql = f"SELECT * FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    return _query(conn, sql, tuple(params))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run(
    output_dir: Path,
    fmt: str,
    *,
    mode: str = "api",
    db_path: Path | None = None,
    base_url: str = "https://rustchain.org",
    start_ts: int | None = None,
    end_ts: int | None = None,
    miner_id: str | None = None,
    tables: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Main export entry-point.  Returns ``{table_name: file_path}``."""
    target_tables = tables or ALL_TABLES
    suffix = fmt if fmt != "parquet" else "parquet"

    if mode == "api":
        client = APIClient(base_url)
        data = export_api(
            client,
            start_ts=start_ts,
            end_ts=end_ts,
            miner_id_filter=miner_id,
        )
    else:
        if db_path is None:
            raise ValueError("--db is required in db mode")
        data = export_db(
            db_path,
            start_ts=start_ts,
            end_ts=end_ts,
            miner_id_filter=miner_id,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    for tbl in target_tables:
        rows = data.get(tbl, [])
        cols = TABLE_COLUMNS.get(tbl, sorted({k for r in rows for k in r}) if rows else [])
        path = output_dir / f"{tbl}.{suffix}"
        writer = make_writer(path, fmt, cols)
        for row in rows:
            writer.write_row(row)
        writer.close()
        written[tbl] = str(path)

    # Manifest
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "mode": mode,
        "format": fmt,
        "tables": {t: len(data.get(t, [])) for t in target_tables},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    written["manifest"] = str(manifest_path)

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Export RustChain attestation data to CSV, JSON, JSONL, or Parquet.",
    )
    p.add_argument(
        "--format",
        choices=("csv", "json", "jsonl", "parquet"),
        default="csv",
        dest="fmt",
        help="Output format (default: csv)",
    )
    p.add_argument("--output", type=Path, required=True, help="Output directory")
    p.add_argument("--mode", choices=("api", "db"), default="api")
    p.add_argument("--db", type=Path, default=None, help="SQLite database path (db mode)")
    p.add_argument("--base-url", default="https://rustchain.org", help="Node base URL (api mode)")
    p.add_argument("--from", dest="from_date", default=None, help="Start date (YYYY-MM-DD or unix ts)")
    p.add_argument("--to", dest="to_date", default=None, help="End date (YYYY-MM-DD or unix ts)")
    p.add_argument("--miner-id", default=None, help="Export data for a single miner only")
    p.add_argument(
        "--table",
        dest="tables",
        action="append",
        choices=list(ALL_TABLES),
        default=None,
        help="Export only this table (repeatable)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start_ts = parse_date(args.from_date)
    end_ts = parse_date(args.to_date)
    tables = tuple(args.tables) if args.tables else None

    written = run(
        args.output,
        args.fmt,
        mode=args.mode,
        db_path=args.db,
        base_url=args.base_url,
        start_ts=start_ts,
        end_ts=end_ts,
        miner_id=args.miner_id,
        tables=tables,
    )
    print(json.dumps({"ok": True, "files": written}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
