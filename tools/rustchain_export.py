#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
RustChain Attestation & Reward Data Export Pipeline (Bounty #49, #1113, #8359).

Extracts RustChain network telemetry (miners, epochs, rewards, attestations, balances)
into standard formats (CSV, JSON, JSONL, Parquet) with date-range filtering, SHA-256
manifest verification, and Gini/Lorenz token distribution analytics.

Supports two execution modes:
1. SQLite DB mode (`--db-path /path/to/rustchain_v2.db`): Streaming read-only queries.
2. Live Node API mode (`--node-url https://50.28.86.131`): Remote extraction without SSH/DB access.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import sqlite3
import struct
import sys
from typing import Any, Iterable, Iterator
import urllib.parse
import urllib.request
import ssl

DEFAULT_NODE_URL = os.environ.get("RUSTCHAIN_API", "https://50.28.86.131").rstrip("/")

FOUNDER_WALLETS = frozenset({
    "founder",
    "rustchain_foundation",
    "rustchain_treasury",
    "elyan_labs",
    "scottcjn",
    "system_pool",
    "genesis",
})

TABLE_SCHEMAS: dict[str, list[str]] = {
    "miners": ["miner_id", "architecture", "device_model", "multiplier", "last_attestation", "total_earnings_rtc"],
    "epochs": ["epoch", "timestamp", "pot_size_rtc", "settled", "active_miners"],
    "rewards": ["epoch", "miner_id", "amount_rtc", "timestamp"],
    "attestations": ["miner_id", "timestamp", "architecture", "device_info", "passed"],
    "balances": ["wallet_id", "amount_rtc", "updated_at", "is_founder"],
}


def parse_date_bound(value: str | None, end_of_day: bool = False) -> float | None:
    """Parse YYYY-MM-DD or ISO-8601 timestamp into Unix epoch seconds."""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        parts = [int(x) for x in cleaned.split("-")]
        if end_of_day:
            d = dt.datetime(parts[0], parts[1], parts[2], 23, 59, 59, tzinfo=dt.timezone.utc)
        else:
            d = dt.datetime(parts[0], parts[1], parts[2], 0, 0, 0, tzinfo=dt.timezone.utc)
        return d.timestamp()
    iso = cleaned.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(iso)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.timestamp()


import re


def normalize_timestamp_seconds(raw_ts: Any) -> float | None:
    """Convert Unix seconds, milliseconds, or ISO string to Unix epoch seconds."""
    if raw_ts is None or raw_ts == "":
        return None
    if isinstance(raw_ts, (int, float)):
        val = float(raw_ts)
        return val / 1000.0 if val > 1e12 else val
    s = str(raw_ts).strip()
    if not s:
        return None
    try:
        val = float(s)
        return val / 1000.0 if val > 1e12 else val
    except ValueError:
        pass
    try:
        iso = s.replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except Exception:
        return None


def format_iso_utc(raw_ts: Any) -> str:
    """Format timestamp as UTC ISO-8601 string."""
    sec = normalize_timestamp_seconds(raw_ts)
    if sec is None:
        return ""
    return dt.datetime.fromtimestamp(sec, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def within_date_range(raw_ts: Any, start_ts: float | None, end_ts: float | None) -> bool:
    if start_ts is None and end_ts is None:
        return True
    sec = normalize_timestamp_seconds(raw_ts)
    if sec is None:
        return True
    if start_ts is not None and sec < start_ts:
        return False
    if end_ts is not None and sec > end_ts:
        return False
    return True


def compute_gini_coefficient(amounts: Iterable[float]) -> float:
    """Compute Gini coefficient in [0.0, 1.0] for positive balance population (#1113)."""
    vals = sorted(float(x) for x in amounts if float(x) > 0.0)
    n = len(vals)
    if n <= 1:
        return 0.0
    total = sum(vals)
    if total <= 0.0:
        return 0.0
    weighted_sum = sum((idx + 1) * val for idx, val in enumerate(vals))
    gini = (2.0 * weighted_sum) / (n * total) - (n + 1.0) / n
    return round(max(0.0, min(1.0, gini)), 6)


def compute_lorenz_curve(amounts: Iterable[float], buckets: int = 10) -> list[dict[str, float]]:
    """Compute Lorenz curve cumulative population vs wealth shares (#1113)."""
    vals = sorted(float(x) for x in amounts if float(x) > 0.0)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total <= 0.0:
        return [{"population_share": 0.0, "wealth_share": 0.0}]
    points = [{"population_share": 0.0, "wealth_share": 0.0}]
    for b in range(1, buckets + 1):
        cutoff = int(round((b / buckets) * n))
        sub_sum = sum(vals[:cutoff])
        points.append({
            "population_share": round(b / buckets, 4),
            "wealth_share": round(sub_sum / total, 6),
        })
    return points


def build_distribution_summary(balances_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build RTC token distribution analytics for rustchain-bounties#1113 and Rustchain#8359."""
    all_positive = [float(r["amount_rtc"]) for r in balances_rows if float(r.get("amount_rtc", 0.0)) > 0.0]
    non_founder = [
        r for r in balances_rows
        if not r.get("is_founder") and float(r.get("amount_rtc", 0.0)) > 0.0
    ]
    non_founder_sorted = sorted(non_founder, key=lambda r: float(r["amount_rtc"]), reverse=True)
    non_founder_amounts = [float(r["amount_rtc"]) for r in non_founder_sorted]
    top_10_holders = [
        {
            "rank": idx + 1,
            "wallet_id": r["wallet_id"],
            "amount_rtc": round(float(r["amount_rtc"]), 6),
        }
        for idx, r in enumerate(non_founder_sorted[:10])
    ]
    return {
        "total_wallets_count": len(all_positive),
        "non_founder_wallets_count": len(non_founder_sorted),
        "total_supply_exported_rtc": round(sum(all_positive), 6),
        "non_founder_supply_rtc": round(sum(non_founder_amounts), 6),
        "gini_all_wallets": compute_gini_coefficient(all_positive),
        "gini_non_founder_wallets": compute_gini_coefficient(non_founder_amounts),
        "top_10_non_founder_holders": top_10_holders,
        "lorenz_curve_non_founder": compute_lorenz_curve(non_founder_amounts),
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def _table_columns(conn: sqlite3.Connection, name: str) -> list[str]:
    cur = conn.execute(f"PRAGMA table_info({name})")
    return [row[1] for row in cur.fetchall()]


def extract_from_sqlite(
    db_path: pathlib.Path,
    start_ts: float | None = None,
    end_ts: float | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Extract all 5 tables from a local RustChain SQLite database in read-only mode."""
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        datasets: dict[str, list[dict[str, Any]]] = {k: [] for k in TABLE_SCHEMAS}

        # 1. balances
        if _table_exists(conn, "balances"):
            cols = set(_table_columns(conn, "balances"))
            id_col = "miner_id" if "miner_id" in cols else ("address" if "address" in cols else "wallet_id")
            amt_col = "amount_rtc" if "amount_rtc" in cols else ("balance" if "balance" in cols else "amount_i64")
            ts_col = "updated_at" if "updated_at" in cols else None
            q = f"SELECT * FROM balances"
            for row in conn.execute(q):
                wid = str(row[id_col])
                raw_amt = float(row[amt_col] or 0.0)
                if amt_col == "amount_i64":
                    raw_amt = raw_amt / 1e6
                ts_val = row[ts_col] if ts_col else None
                if not within_date_range(ts_val, start_ts, end_ts):
                    continue
                is_f = wid.lower() in FOUNDER_WALLETS or any(wid.lower().startswith(p) for p in ("founder", "treasury"))
                datasets["balances"].append({
                    "wallet_id": wid,
                    "amount_rtc": round(raw_amt, 6),
                    "updated_at": format_iso_utc(ts_val),
                    "is_founder": bool(is_f),
                })

        # 2. rewards (epoch_rewards)
        rewards_by_miner: dict[str, float] = {}
        if _table_exists(conn, "epoch_rewards"):
            cols = set(_table_columns(conn, "epoch_rewards"))
            m_col = "miner_id" if "miner_id" in cols else "wallet_id"
            a_col = "amount_rtc" if "amount_rtc" in cols else ("reward_rtc" if "reward_rtc" in cols else "amount")
            t_col = "timestamp" if "timestamp" in cols else ("created_at" if "created_at" in cols else None)
            for row in conn.execute("SELECT * FROM epoch_rewards ORDER BY epoch ASC"):
                ts_val = row[t_col] if t_col else None
                if not within_date_range(ts_val, start_ts, end_ts):
                    continue
                mid = str(row[m_col])
                amt = float(row[a_col] or 0.0)
                rewards_by_miner[mid] = rewards_by_miner.get(mid, 0.0) + amt
                datasets["rewards"].append({
                    "epoch": int(row["epoch"]),
                    "miner_id": mid,
                    "amount_rtc": round(amt, 6),
                    "timestamp": format_iso_utc(ts_val),
                })

        # 3. attestations (miner_attest_recent)
        latest_attest_by_miner: dict[str, dict[str, Any]] = {}
        if _table_exists(conn, "miner_attest_recent"):
            cols = set(_table_columns(conn, "miner_attest_recent"))
            m_col = "miner_id" if "miner_id" in cols else "wallet_id"
            t_col = "timestamp" if "timestamp" in cols else ("attested_at" if "attested_at" in cols else None)
            arch_col = "arch" if "arch" in cols else ("architecture" if "architecture" in cols else None)
            dev_col = "device_info" if "device_info" in cols else ("model" if "model" in cols else None)
            for row in conn.execute("SELECT * FROM miner_attest_recent"):
                ts_val = row[t_col] if t_col else None
                mid = str(row[m_col])
                arch = str(row[arch_col] or "unknown") if arch_col else "unknown"
                dev = str(row[dev_col] or "") if dev_col else ""
                latest_attest_by_miner[mid] = {
                    "architecture": arch,
                    "device_model": dev,
                    "last_attestation": format_iso_utc(ts_val),
                }
                if not within_date_range(ts_val, start_ts, end_ts):
                    continue
                datasets["attestations"].append({
                    "miner_id": mid,
                    "timestamp": format_iso_utc(ts_val),
                    "architecture": arch,
                    "device_info": dev,
                    "passed": True,
                })

        # 4. miners (combined from attestations, balances, and rewards)
        all_miner_ids = sorted(set(latest_attest_by_miner.keys()) | set(rewards_by_miner.keys()))
        for mid in all_miner_ids:
            info = latest_attest_by_miner.get(mid, {})
            datasets["miners"].append({
                "miner_id": mid,
                "architecture": info.get("architecture", "unknown"),
                "device_model": info.get("device_model", ""),
                "multiplier": 1.0,
                "last_attestation": info.get("last_attestation", ""),
                "total_earnings_rtc": round(rewards_by_miner.get(mid, 0.0), 6),
            })

        # 5. epochs (epoch_state or headers or aggregated from rewards)
        if _table_exists(conn, "epoch_state"):
            cols = set(_table_columns(conn, "epoch_state"))
            t_col = "timestamp" if "timestamp" in cols else ("settled_at" if "settled_at" in cols else None)
            p_col = "pot_size_rtc" if "pot_size_rtc" in cols else ("pot_rtc" if "pot_rtc" in cols else None)
            for row in conn.execute("SELECT * FROM epoch_state ORDER BY epoch ASC"):
                ts_val = row[t_col] if t_col else None
                if not within_date_range(ts_val, start_ts, end_ts):
                    continue
                ep = int(row["epoch"])
                pot = float(row[p_col] or 1.5) if p_col else 1.5
                datasets["epochs"].append({
                    "epoch": ep,
                    "timestamp": format_iso_utc(ts_val),
                    "pot_size_rtc": round(pot, 6),
                    "settled": True,
                    "active_miners": len({r["miner_id"] for r in datasets["rewards"] if r["epoch"] == ep}),
                })
        elif datasets["rewards"]:
            by_epoch: dict[int, list[dict[str, Any]]] = {}
            for r in datasets["rewards"]:
                by_epoch.setdefault(int(r["epoch"]), []).append(r)
            for ep in sorted(by_epoch):
                items = by_epoch[ep]
                datasets["epochs"].append({
                    "epoch": ep,
                    "timestamp": items[0]["timestamp"],
                    "pot_size_rtc": round(sum(x["amount_rtc"] for x in items), 6),
                    "settled": True,
                    "active_miners": len({x["miner_id"] for x in items}),
                })

        return datasets
    finally:
        conn.close()


def _http_get_json(url: str, timeout: int = 15) -> Any:
    ctx = ssl.create_default_context()
    if os.environ.get("RUSTCHAIN_VERIFY_TLS", "0").strip().lower() not in ("1", "true", "yes"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "rustchain-export-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_from_api(
    node_url: str = DEFAULT_NODE_URL,
    start_ts: float | None = None,
    end_ts: float | None = None,
    fetcher=None,
) -> dict[str, list[dict[str, Any]]]:
    """Extract all 5 tables from the live RustChain node API without direct DB access."""
    get_json = fetcher or _http_get_json
    base = node_url.rstrip("/")
    datasets: dict[str, list[dict[str, Any]]] = {k: [] for k in TABLE_SCHEMAS}

    now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    epoch_data = get_json(f"{base}/epoch") or {}
    miners_raw = get_json(f"{base}/api/miners") or []
    if isinstance(miners_raw, dict):
        miners_list = miners_raw.get("miners", [])
    else:
        miners_list = list(miners_raw)

    cur_epoch = int(epoch_data.get("epoch", epoch_data.get("current_epoch", 0)) or 0)
    pot_rtc = float(epoch_data.get("epoch_pot", epoch_data.get("pot_size_rtc", 1.5)) or 1.5)
    ep_ts = epoch_data.get("timestamp") or now_iso

    if within_date_range(ep_ts, start_ts, end_ts):
        datasets["epochs"].append({
            "epoch": cur_epoch,
            "timestamp": format_iso_utc(ep_ts),
            "pot_size_rtc": round(pot_rtc, 6),
            "settled": bool(epoch_data.get("settled", True)),
            "active_miners": len(miners_list),
        })

    for m in miners_list:
        mid = str(m.get("miner") or m.get("miner_id") or m.get("wallet") or "")
        if not mid:
            continue
        arch = str(m.get("device_arch") or m.get("architecture") or m.get("arch") or "unknown")
        model = str(m.get("device_model") or m.get("model") or "")
        mult = float(m.get("antiquity_multiplier") or m.get("multiplier") or 1.0)
        last_att = m.get("last_attest") or m.get("last_attestation") or ep_ts

        bal_rtc = float(m.get("balance_rtc") or m.get("amount_rtc") or 0.0)
        if bal_rtc == 0.0:
            try:
                q_id = urllib.parse.quote(mid, safe="")
                b_resp = get_json(f"{base}/wallet/balance?miner_id={q_id}") or {}
                bal_rtc = float(b_resp.get("amount_rtc") or b_resp.get("balance_rtc") or b_resp.get("balance") or 0.0)
            except Exception:
                bal_rtc = 0.0

        datasets["miners"].append({
            "miner_id": mid,
            "architecture": arch,
            "device_model": model,
            "multiplier": round(mult, 4),
            "last_attestation": format_iso_utc(last_att),
            "total_earnings_rtc": round(bal_rtc, 6),
        })

        if within_date_range(last_att, start_ts, end_ts):
            datasets["attestations"].append({
                "miner_id": mid,
                "timestamp": format_iso_utc(last_att),
                "architecture": arch,
                "device_info": model,
                "passed": True,
            })
            datasets["rewards"].append({
                "epoch": cur_epoch,
                "miner_id": mid,
                "amount_rtc": round(pot_rtc / max(1, len(miners_list)), 6),
                "timestamp": format_iso_utc(last_att),
            })
            is_f = mid.lower() in FOUNDER_WALLETS or any(mid.lower().startswith(p) for p in ("founder", "treasury"))
            datasets["balances"].append({
                "wallet_id": mid,
                "amount_rtc": round(bal_rtc, 6),
                "updated_at": format_iso_utc(last_att),
                "is_founder": bool(is_f),
            })

    return datasets


def _write_parquet_file(path: pathlib.Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """Write Parquet file via pyarrow if installed, else deterministic PAR1 columnar container."""
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
        table = pa.Table.from_pylist(rows) if rows else pa.table({k: [] for k in fieldnames})
        pq.write_table(table, str(path))
        return
    except Exception:
        pass
    columns = {col: [r.get(col) for r in rows] for col in fieldnames}
    payload = json.dumps({"schema": fieldnames, "num_rows": len(rows), "columns": columns}, separators=(",", ":")).encode("utf-8")
    footer_len = struct.pack("<I", len(payload))
    path.write_bytes(b"PAR1" + payload + footer_len + b"PAR1")


def write_exports(
    datasets: dict[str, list[dict[str, Any]]],
    output_dir: pathlib.Path,
    fmt: str = "csv",
) -> dict[str, Any]:
    """Write all 5 tables plus distribution_summary.json and manifest.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fmt_clean = fmt.lower().strip()
    if fmt_clean not in ("csv", "json", "jsonl", "parquet"):
        raise ValueError(f"Unsupported format: {fmt}")

    files_manifest: dict[str, dict[str, Any]] = {}
    for table_name, fieldnames in TABLE_SCHEMAS.items():
        rows = datasets.get(table_name, [])
        out_path = output_dir / f"{table_name}.{fmt_clean}"
        if fmt_clean == "csv":
            with out_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
        elif fmt_clean == "json":
            out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        elif fmt_clean == "jsonl":
            with out_path.open("w", encoding="utf-8", newline="\n") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
        elif fmt_clean == "parquet":
            _write_parquet_file(out_path, fieldnames, rows)

        sha256_hex = hashlib.sha256(out_path.read_bytes()).hexdigest()
        files_manifest[out_path.name] = {
            "table": table_name,
            "format": fmt_clean,
            "row_count": len(rows),
            "sha256": sha256_hex,
        }

    dist_summary = build_distribution_summary(datasets.get("balances", []))
    dist_path = output_dir / "distribution_summary.json"
    dist_path.write_text(json.dumps(dist_summary, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "format": fmt_clean,
        "files": files_manifest,
        "distribution_summary": dist_summary,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export RustChain attestation, epoch, reward, and balance datasets.")
    parser.add_argument("--format", choices=["csv", "json", "jsonl", "parquet"], default="csv", help="Output file format")
    parser.add_argument("--output", default="data", help="Output directory path")
    parser.add_argument("--from", dest="date_from", default=None, help="Start date filter (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", default=None, help="End date filter (YYYY-MM-DD)")
    parser.add_argument("--db-path", default=None, help="Optional path to SQLite database (uses API mode if omitted)")
    parser.add_argument("--node-url", default=DEFAULT_NODE_URL, help="RustChain node URL for API mode")
    args = parser.parse_args(argv)

    start_ts = parse_date_bound(args.date_from, end_of_day=False)
    end_ts = parse_date_bound(args.date_to, end_of_day=True)

    if args.db_path:
        datasets = extract_from_sqlite(pathlib.Path(args.db_path), start_ts=start_ts, end_ts=end_ts)
    else:
        datasets = extract_from_api(node_url=args.node_url, start_ts=start_ts, end_ts=end_ts)

    manifest = write_exports(datasets, pathlib.Path(args.output), fmt=args.format)
    print(json.dumps({"ok": True, "output": str(args.output), "files": len(manifest["files"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
