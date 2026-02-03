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
import sqlite3
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Configuration
DEFAULT_API_URL = "http://127.0.0.1:8099"
DEFAULT_DB_PATH = "./rustchain_v2.db"

class RustChainExporter:
    def __init__(self, api_url: str = None, db_path: str = None):
        self.api_url = api_url or DEFAULT_API_URL
        self.db_path = db_path or DEFAULT_DB_PATH
        self.use_db = os.path.exists(self.db_path)

    def _fetch_from_api(self, endpoint: str) -> Any:
        try:
            resp = requests.get(f"{self.api_url}{endpoint}", timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"API Error ({endpoint}): {e}")
        return None

    def _query_db(self, query: str, params: tuple = ()) -> List[Dict]:
        if not self.use_db:
            return []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"DB Error: {e}")
            return []

    def export_miners(self) -> List[Dict]:
        """Export all miner IDs, architectures, and last attestation info"""
        if self.use_db:
            return self._query_db("""
                SELECT miner, device_arch, device_family, ts_ok, arch_validation_score
                FROM miner_attest_recent
            """)
        else:
            data = self._fetch_from_api("/api/miners")
            return data.get("miners", []) if data else []

    def export_epochs(self) -> List[Dict]:
        """Export epoch history"""
        if self.use_db:
            return self._query_db("SELECT * FROM epoch_state ORDER BY epoch DESC")
        return [] # Limited API support for full history

    def export_balances(self) -> List[Dict]:
        """Export current RTC balances"""
        if self.use_db:
            return self._query_db("SELECT miner_pk, balance_rtc, amount_i64 FROM balances")
        return []

    def export_rewards(self) -> List[Dict]:
        """Export per-miner per-epoch reward amounts"""
        if self.use_db:
            try:
                return self._query_db("SELECT * FROM epoch_rewards ORDER BY epoch DESC")
            except:
                return []
        return []

    def export_ledger(self) -> List[Dict]:
        """Export full transaction/reward ledger"""
        if self.use_db:
            try:
                return self._query_db("SELECT * FROM ledger ORDER BY ts DESC")
            except:
                return []
        return []

    def export_attestations(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Export detailed attestation logs from Hall of Rust"""
        if self.use_db:
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
            return self._query_db(query, tuple(params))
        return []

    def save(self, data: List[Dict], filename: str, fmt: str, output_dir: str):
        if not data:
            print(f"No data to export for {filename}")
            return

        os.makedirs(output_dir, exist_ok=True)
        base_path = Path(output_dir) / filename
        
        if fmt == "json":
            with open(base_path.with_suffix(".json"), 'w') as f:
                json.dump(data, f, indent=2)
        elif fmt == "jsonl":
            with open(base_path.with_suffix(".jsonl"), 'w') as f:
                for entry in data:
                    f.write(json.dumps(entry) + "\n")
        elif fmt == "csv":
            if not data: return
            keys = data[0].keys()
            with open(base_path.with_suffix(".csv"), 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
        
        print(f"Exported {len(data)} records to {base_path}.{fmt}")

def main():
    parser = argparse.ArgumentParser(description="RustChain Data Export Tool")
    parser.add_argument("--format", choices=["csv", "json", "jsonl"], default="csv", help="Export format")
    parser.add_argument("--output", default="exports/", help="Output directory")
    parser.add_argument("--api", help="Node API URL")
    parser.add_argument("--db", help="Local SQLite DB path")
    parser.add_argument("--from", dest="start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="end_date", help="End date (YYYY-MM-DD)")

    args = parser.parse_args()
    
    exporter = RustChainExporter(api_url=args.api, db_path=args.db)
    
    print(f"Starting RustChain data export (Format: {args.format})...")
    
    # Run exports
    miners = exporter.export_miners()
    exporter.save(miners, "miners", args.format, args.output)
    
    epochs = exporter.export_epochs()
    exporter.save(epochs, "epochs", args.format, args.output)
    
    balances = exporter.export_balances()
    exporter.save(balances, "balances", args.format, args.output)
    
    rewards = exporter.export_rewards()
    exporter.save(rewards, "rewards", args.format, args.output)
    
    ledger = exporter.export_ledger()
    exporter.save(ledger, "ledger", args.format, args.output)
    
    attestations = exporter.export_attestations(args.start_date, args.end_date)
    exporter.save(attestations, "attestations", args.format, args.output)
    
    print("Export complete.")

if __name__ == "__main__":
    main()
