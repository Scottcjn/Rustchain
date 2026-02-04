#!/usr/bin/env python3
"""
RustChain Data Export Pipeline
==============================
Bounty #49 Implementation
"""

import os
import sys
import json
import csv
import time
import os
import sys
import json
import csv
import sqlite3
import argparse
import requests
import hashlib
import hmac
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Generator

# Configuration
DEFAULT_API_URL = os.environ.get('RUSTCHAIN_NODE_URL', 'http://127.0.0.1:8099')
DEFAULT_DB_PATH = "./rustchain_v2.db"

def sanitize_csv_value(value: Any) -> Any:
    """Protect against CSV injection attacks"""
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return "'" + value
    return value

class RustChainExporter:
    def __init__(self, api_url: str = None, db_path: str = None, admin_key: str = None):
        self.api_url = api_url or DEFAULT_API_URL
        self.db_path = db_path or DEFAULT_DB_PATH
        self.admin_key = admin_key or os.environ.get("RC_ADMIN_KEY")
        self.use_db = os.path.exists(self.db_path)
        
        if not self.admin_key:
            print("ERROR: RC_ADMIN_KEY environment variable required for export.", file=sys.stderr)
            sys.exit(1)

    def _fetch_from_api(self, endpoint: str) -> Any:
        try:
            headers = {"X-API-Key": self.admin_key}
            resp = requests.get(f"{self.api_url}{endpoint}", headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"API Error ({endpoint}): {e}")
        return None

    def _query_db_stream(self, query: str, params: tuple = (), batch_size: int = 1000) -> Generator[Dict, None, None]:
        if not self.use_db:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    for row in rows:
                        yield dict(row)
        except Exception as e:
            print(f"DB Error: {e}")

    def export_miners(self) -> Generator[Dict, None, None]:
        """Export all miner IDs, architectures, and last attestation info"""
        if self.use_db:
            return self._query_db_stream("""
                SELECT miner, device_arch, device_family, ts_ok, arch_validation_score
                FROM miner_attest_recent
            """)
        else:
            data = self._fetch_from_api("/api/miners")
            results = data.get("miners", []) if data else []
            for r in results: yield r

    def export_balances(self) -> Generator[Dict, None, None]:
        """Export current RTC balances"""
        if self.use_db:
            return self._query_db_stream("SELECT miner_pk, balance_rtc, amount_i64 FROM balances")
        return iter([])

    def save_stream(self, generator: Generator[Dict, None, None], filename: str, fmt: str, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        base_path = Path(output_dir) / filename
        count = 0
        
        if fmt == "json":
            # For JSON we still need to collect all to make a valid array, 
            # or we could write a manual array stream. Let's do a basic manual one.
            with open(base_path.with_suffix(".json"), 'w') as f:
                f.write("[\n")
                for entry in generator:
                    if count > 0: f.write(",\n")
                    f.write("  " + json.dumps(entry))
                    count += 1
                f.write("\n]")
        elif fmt == "jsonl":
            with open(base_path.with_suffix(".jsonl"), 'w') as f:
                for entry in generator:
                    f.write(json.dumps(entry) + "\n")
                    count += 1
        elif fmt == "csv":
            try:
                first_entry = next(generator)
                keys = first_entry.keys()
                with open(base_path.with_suffix(".csv"), 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    # Sanitize and write first
                    writer.writerow({k: sanitize_csv_value(v) for k, v in first_entry.items()})
                    count = 1
                    for entry in generator:
                        writer.writerow({k: sanitize_csv_value(v) for k, v in entry.items()})
                        count += 1
            except StopIteration:
                pass
        
        print(f"Exported {count} records to {base_path}.{fmt}")

def main():
    parser = argparse.ArgumentParser(description="RustChain Data Export Tool")
    parser.add_argument("--format", choices=["csv", "json", "jsonl"], default="csv", help="Export format")
    parser.add_argument("--output", default="exports/", help="Output directory")
    parser.add_argument("--api", help="Node API URL")
    parser.add_argument("--db", help="Local SQLite DB path")
    parser.add_argument("--key", help="Admin API Key (or set RC_ADMIN_KEY)")

    args = parser.parse_args()
    
    exporter = RustChainExporter(api_url=args.api, db_path=args.db, admin_key=args.key)
    
    print(f"Starting RustChain data export (Format: {args.format})...")
    
    # Run exports
    exporter.save_stream(exporter.export_miners(), "miners", args.format, args.output)
    exporter.save_stream(exporter.export_balances(), "balances", args.format, args.output)
    
    print("Export complete.")

if __name__ == "__main__":
    main()
