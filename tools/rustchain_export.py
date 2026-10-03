#!/usr/bin/env python3
"""
RustChain Attestation & Reward Data Export Pipeline
Bounty #49 Implementation

Extracts RustChain attestation, reward, epoch, miner, and ledger data into
standard data formats (CSV, JSON, JSONL, Parquet) for financial compliance,
tax reporting, network analytics, and academic research.

Supports two modes:
1. DB Mode: Direct local or remote SQLite query against rustchain.db
2. API Mode: Remote querying against active node endpoints (/api/miners, /epoch, /health)
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

TABLES = ["miners", "epochs", "rewards", "attestations", "balances"]


def fetch_api_json(base_url: str, endpoint: str, timeout: int = 10) -> Optional[Any]:
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    req = Request(url, headers={"User-Agent": "RustChain-Export-Pipeline/1.0"})
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status == 200:
                data = resp.read().decode("utf-8")
                return json.loads(data)
    except Exception as e:
        sys.stderr.write(f"API Warning: failed to fetch {url}: {e}\n")
    return None


def filter_by_date(records: List[Dict[str, Any]], date_field: str, from_date: Optional[str], to_date: Optional[str]) -> List[Dict[str, Any]]:
    if not from_date and not to_date:
        return records

    from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if from_date else datetime.min.replace(tzinfo=timezone.utc)
    to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00")) if to_date else datetime.max.replace(tzinfo=timezone.utc)

    filtered = []
    for rec in records:
        val = rec.get(date_field)
        if not val:
            filtered.append(rec)
            continue
        try:
            if isinstance(val, (int, float)):
                record_dt = datetime.fromtimestamp(val, tz=timezone.utc)
            else:
                record_dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            if record_dt.tzinfo is None:
                record_dt = record_dt.replace(tzinfo=timezone.utc)
            if from_dt <= record_dt <= to_dt:
                filtered.append(rec)
        except Exception:
            filtered.append(rec)
    return filtered


def export_db_mode(db_path: str, from_date: Optional[str], to_date: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    data: Dict[str, List[Dict[str, Any]]] = {
        "miners": [],
        "epochs": [],
        "rewards": [],
        "attestations": [],
        "balances": [],
    }

    # Query tables if they exist
    existing_tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    # 1. Miners
    if "miner_attest_recent" in existing_tables:
        rows = cursor.execute("SELECT * FROM miner_attest_recent").fetchall()
        data["miners"] = [dict(r) for r in rows]
    elif "miners" in existing_tables:
        rows = cursor.execute("SELECT * FROM miners").fetchall()
        data["miners"] = [dict(r) for r in rows]

    # 2. Epochs
    if "epoch_state" in existing_tables:
        rows = cursor.execute("SELECT * FROM epoch_state").fetchall()
        data["epochs"] = [dict(r) for r in rows]
    elif "epochs" in existing_tables:
        rows = cursor.execute("SELECT * FROM epochs").fetchall()
        data["epochs"] = [dict(r) for r in rows]

    # 3. Rewards
    if "epoch_rewards" in existing_tables:
        rows = cursor.execute("SELECT * FROM epoch_rewards").fetchall()
        data["rewards"] = [dict(r) for r in rows]
    elif "rewards" in existing_tables:
        rows = cursor.execute("SELECT * FROM rewards").fetchall()
        data["rewards"] = [dict(r) for r in rows]

    # 4. Attestations
    if "ledger" in existing_tables:
        rows = cursor.execute("SELECT * FROM ledger").fetchall()
        data["attestations"] = [dict(r) for r in rows]
    elif "attestations" in existing_tables:
        rows = cursor.execute("SELECT * FROM attestations").fetchall()
        data["attestations"] = [dict(r) for r in rows]

    # 5. Balances
    if "balances" in existing_tables:
        rows = cursor.execute("SELECT * FROM balances").fetchall()
        data["balances"] = [dict(r) for r in rows]

    conn.close()

    # Apply date filters where applicable
    if from_date or to_date:
        data["attestations"] = filter_by_date(data["attestations"], "timestamp", from_date, to_date)
        data["epochs"] = filter_by_date(data["epochs"], "timestamp", from_date, to_date)
        data["rewards"] = filter_by_date(data["rewards"], "timestamp", from_date, to_date)

    return data


def export_api_mode(node_url: str, from_date: Optional[str], to_date: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
    data: Dict[str, List[Dict[str, Any]]] = {
        "miners": [],
        "epochs": [],
        "rewards": [],
        "attestations": [],
        "balances": [],
    }

    # Fetch miners from API
    miners_resp = fetch_api_json(node_url, "/api/miners")
    if miners_resp:
        miners_list = miners_resp if isinstance(miners_resp, list) else miners_resp.get("miners", [])
        for m in miners_list:
            if isinstance(m, dict):
                data["miners"].append(m)
                miner_id = m.get("miner_id") or m.get("id") or m.get("address")
                if miner_id:
                    bal_resp = fetch_api_json(node_url, f"/wallet/balance?miner_id={miner_id}")
                    if bal_resp and isinstance(bal_resp, dict):
                        data["balances"].append({
                            "miner_id": miner_id,
                            "balance": bal_resp.get("balance", 0),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        })
            elif isinstance(m, str):
                data["miners"].append({"miner_id": m, "retrieved_at": datetime.now(timezone.utc).isoformat()})

    # Fetch epoch state
    epoch_resp = fetch_api_json(node_url, "/epoch")
    if epoch_resp and isinstance(epoch_resp, dict):
        data["epochs"].append(epoch_resp)

    # Fetch health/attestations overview
    health_resp = fetch_api_json(node_url, "/health")
    if health_resp and isinstance(health_resp, dict):
        data["attestations"].append({
            "node_status": health_resp.get("status"),
            "active_miners_count": health_resp.get("miners_count", len(data["miners"])),
            "current_epoch": health_resp.get("epoch"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Filter date range
    if from_date or to_date:
        data["attestations"] = filter_by_date(data["attestations"], "timestamp", from_date, to_date)
        data["epochs"] = filter_by_date(data["epochs"], "timestamp", from_date, to_date)

    return data


def write_csv(filepath: str, records: List[Dict[str, Any]]):
    if not records:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return

    # Extract all unique keys across records
    keys = []
    seen = set()
    for rec in records:
        for k in rec.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def write_json(filepath: str, records: List[Dict[str, Any]]):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def write_jsonl(filepath: str, records: List[Dict[str, Any]]):
    with open(filepath, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_parquet(filepath: str, records: List[Dict[str, Any]]):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        if not records:
            table = pa.Table.from_arrays([], names=[])
        else:
            table = pa.Table.from_pylist(records)
        pq.write_table(table, filepath)
    except ImportError:
        sys.stderr.write("pyarrow not installed; falling back to JSON serialization for Parquet target.\n")
        write_json(filepath + ".json", records)


def run_pipeline(
    mode: str,
    target: str,
    output_dir: str,
    export_format: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, int]:
    os.makedirs(output_dir, exist_ok=True)

    if mode == "db":
        dataset = export_db_mode(target, from_date, to_date)
    else:
        dataset = export_api_mode(target, from_date, to_date)

    summary = {}
    for tbl in TABLES:
        records = dataset.get(tbl, [])
        filename = f"{tbl}.{export_format}"
        filepath = os.path.join(output_dir, filename)

        if export_format == "csv":
            write_csv(filepath, records)
        elif export_format == "json":
            write_json(filepath, records)
        elif export_format == "jsonl":
            write_jsonl(filepath, records)
        elif export_format == "parquet":
            write_parquet(filepath, records)
        else:
            raise ValueError(f"Unsupported format: {export_format}")

        summary[tbl] = len(records)

    # Output manifest checksum file
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "format": export_format,
        "tables": summary,
        "filters": {
            "from": from_date,
            "to": to_date
        }
    }
    with open(os.path.join(output_dir, "export_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="RustChain Attestation & Reward Data Export Pipeline (Bounty #49)")
    parser.add_argument("--mode", choices=["api", "db"], default="api", help="Operation mode: 'api' (remote node) or 'db' (local SQLite)")
    parser.add_argument("--node-url", default="https://50.28.86.131", help="Target node API URL (for api mode)")
    parser.add_argument("--db-path", default="rustchain.db", help="Path to local SQLite database (for db mode)")
    parser.add_argument("--format", choices=["csv", "json", "jsonl", "parquet"], default="csv", help="Export format")
    parser.add_argument("--output", default="data/", help="Output directory path")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date filter (YYYY-MM-DD or ISO 8601)")
    parser.add_argument("--to", dest="to_date", default=None, help="End date filter (YYYY-MM-DD or ISO 8601)")

    args = parser.parse_args()

    target = args.db_path if args.mode == "db" else args.node_url
    print(f"Starting RustChain Export [{args.mode.upper()} mode] -> Format: {args.format}, Target: {target}")
    summary = run_pipeline(
        mode=args.mode,
        target=target,
        output_dir=args.output,
        export_format=args.format,
        from_date=args.from_date,
        to_date=args.to_date,
    )
    print("Export complete. Summary:")
    for tbl, count in summary.items():
        print(f"  - {tbl}: {count} records -> {os.path.join(args.output, f'{tbl}.{args.format}')}")


if __name__ == "__main__":
    main()
