#!/usr/bin/env python3
"""
RustChain Data Export Tool
==========================
Bounty #49 Implementation
"""

import os
import sys
import json
import csv
import time
import sqlite3
import argparse
import requests
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Iterator

# Configuration
DEFAULT_API_URL = "http://127.0.0.1:8099"
DEFAULT_DB_PATH = "./rustchain_v2.db"

class RustChainExporter:
    def __init__(self, api_url: str = None, db_path: str = None, admin_key: str = None):
        self.api_url = api_url or DEFAULT_API_URL
        self.db_path = db_path or DEFAULT_DB_PATH
        self.admin_key = admin_key or os.environ.get("RC_ADMIN_KEY")
        self.use_db = os.path.exists(self.db_path)

    def _verify_auth(self):
        if not self.admin_key:
            raise PermissionError("RC_ADMIN_KEY not set. Authorization required for data export.")

    def _fetch_from_api(self, endpoint: str) -> Any:
        try:
            self._verify_auth()
            resp = requests.get(
                f"{self.api_url}{endpoint}", 
                headers={"X-Admin-Key": self.admin_key},
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                print("Unauthorized: Invalid RC_ADMIN_KEY")
        except Exception as e:
            print(f"API Error ({endpoint}): {e}")
        return None

    def _stream_query_db(self, query: str, params: tuple = ()) -> Iterator[Dict]:
        """Stream query results to save memory"""
        self._verify_auth()
        if not self.use_db:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break
                for row in rows:
                    yield dict(row)
            conn.close()
        except Exception as e:
            print(f"DB Error: {e}")

    def _escape_csv(self, value: Any) -> str:
        """Protect against CSV injection"""
        s = str(value)
        if s.startswith(('=', '+', '-', '@')):
            return "'" + s
        return s

    def export_miners(self) -> Iterator[Dict]:
        return self._stream_query_db("""
            SELECT miner, device_arch, device_family, ts_ok, arch_validation_score
            FROM miner_attest_recent
        """)

    def export_epochs(self) -> Iterator[Dict]:
        return self._stream_query_db("SELECT * FROM epoch_state ORDER BY epoch DESC")

    def export_balances(self) -> Iterator[Dict]:
        return self._stream_query_db("SELECT miner_pk, balance_rtc, amount_i64 FROM balances")

    def export_attestations(self, start_date: str = None, end_date: str = None) -> Iterator[Dict]:
        query = "SELECT * FROM hall_of_rust"
        params = []
        if start_date or end_date:
            query += " WHERE "
            if start_date:
                start_ts = int(datetime.fromisoformat(start_date).timestamp())
                query += "first_attestation >= ?"
                params.append(start_ts)
            if end_date:
                if start_date: query += " AND "
                end_ts = int(datetime.fromisoformat(end_date).timestamp())
                query += "last_attestation <= ?"
                params.append(end_ts)
        return self._stream_query_db(query, tuple(params))

    def save_stream(self, data_iterator: Iterator[Dict], filename: str, fmt: str, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        base_path = Path(output_dir) / filename
        
        first_row = next(data_iterator, None)
        if first_row is None:
            print(f"No data to export for {filename}")
            return

        if fmt == "json":
            # For streaming JSON we use an array format but it's less memory efficient 
            # than JSONL unless we write one by one
            with open(base_path.with_suffix(".json"), 'w') as f:
                f.write("[\n")
                f.write(json.dumps(first_row, indent=2))
                for entry in data_iterator:
                    f.write(",\n")
                    f.write(json.dumps(entry, indent=2))
                f.write("\n]")
        elif fmt == "jsonl":
            with open(base_path.with_suffix(".jsonl"), 'w') as f:
                f.write(json.dumps(first_row) + "\n")
                for entry in data_iterator:
                    f.write(json.dumps(entry) + "\n")
        elif fmt == "csv":
            keys = first_row.keys()
            with open(base_path.with_suffix(".csv"), 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                # Escape the first row
                writer.writerow({k: self._escape_csv(v) for k, v in first_row.items()})
                for entry in data_iterator:
                    writer.writerow({k: self._escape_csv(v) for k, v in entry.items()})
        
        print(f"Exported data to {base_path}.{fmt}")

def main():
    parser = argparse.ArgumentParser(description="RustChain Data Export Tool")
    parser.add_argument("--format", choices=["csv", "json", "jsonl"], default="csv", help="Export format")
    parser.add_argument("--output", default="exports/", help="Output directory")
    parser.add_argument("--key", help="RC_ADMIN_KEY for authentication")
    parser.add_argument("--db", help="Local SQLite DB path")
    parser.add_argument("--from", dest="start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="end_date", help="End date (YYYY-MM-DD)")

    args = parser.parse_args()
    
    try:
        exporter = RustChainExporter(db_path=args.db, admin_key=args.key)
        print(f"Starting RustChain data export (Format: {args.format})...")
        
        # Run exports
        exporter.save_stream(exporter.export_miners(), "miners", args.format, args.output)
        exporter.save_stream(exporter.export_epochs(), "epochs", args.format, args.output)
        exporter.save_stream(exporter.export_balances(), "balances", args.format, args.output)
        exporter.save_stream(exporter.export_attestations(args.start_date, args.end_date), "attestations", args.format, args.output)
        
        print("Export complete.")
    except PermissionError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
