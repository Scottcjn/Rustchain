// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import csv
import argparse
import sys
import os
from datetime import datetime
import requests
from typing import Dict, List, Optional, Any

DB_PATH = 'node/rustchain.db'
API_BASE_URL = 'https://50.28.86.131/api'

class RustchainExporter:
    def __init__(self, use_api: bool = False):
        self.use_api = use_api
        self.session = requests.Session() if use_api else None

    def get_miners_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        if self.use_api:
            try:
                response = self.session.get(f"{API_BASE_URL}/miners", verify=False, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"API fetch failed for miners: {e}", file=sys.stderr)
                return []

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM miners"
            params = []

            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("created_at >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("created_at <= ?")
                    params.append(end_date)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_epochs_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        if self.use_api:
            try:
                response = self.session.get(f"{API_BASE_URL}/epochs", verify=False, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"API fetch failed for epochs: {e}", file=sys.stderr)
                return []

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM epochs"
            params = []

            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("timestamp >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("timestamp <= ?")
                    params.append(end_date)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_rewards_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM rewards"
            params = []

            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("timestamp >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("timestamp <= ?")
                    params.append(end_date)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_attestations_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM attestations"
            params = []

            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("timestamp >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("timestamp <= ?")
                    params.append(end_date)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_balances_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM balances"
            params = []

            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append("updated_at >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("updated_at <= ?")
                    params.append(end_date)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(self, data: List[Dict], filepath: str):
        if not data:
            print(f"No data to export to {filepath}")
            return

        fieldnames = list(data[0].keys())
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"Exported {len(data)} records to {filepath}")

    def export_to_json(self, data: List[Dict], filepath: str):
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, default=str)
        print(f"Exported {len(data)} records to {filepath}")

    def export_to_jsonl(self, data: List[Dict], filepath: str):
        with open(filepath, 'w', encoding='utf-8') as jsonlfile:
            for record in data:
                json.dump(record, jsonlfile, default=str)
                jsonlfile.write('\n')
        print(f"Exported {len(data)} records to {filepath}")

    def export_data(self, data_type: str, format_type: str, output_path: str,
                   start_date: Optional[str] = None, end_date: Optional[str] = None):

        data_methods = {
            'miners': self.get_miners_data,
            'epochs': self.get_epochs_data,
            'rewards': self.get_rewards_data,
            'attestations': self.get_attestations_data,
            'balances': self.get_balances_data
        }

        if data_type not in data_methods:
            raise ValueError(f"Invalid data type: {data_type}")

        data = data_methods[data_type](start_date, end_date)

        export_methods = {
            'csv': self.export_to_csv,
            'json': self.export_to_json,
            'jsonl': self.export_to_jsonl
        }

        if format_type not in export_methods:
            raise ValueError(f"Invalid format: {format_type}")

        export_methods[format_type](data, output_path)

def main():
    parser = argparse.ArgumentParser(description='RustChain Data Export Tool')
    parser.add_argument('data_type', choices=['miners', 'epochs', 'rewards', 'attestations', 'balances'],
                        help='Type of data to export')
    parser.add_argument('format', choices=['csv', 'json', 'jsonl'],
                        help='Output format')
    parser.add_argument('-o', '--output', required=True,
                        help='Output file path')
    parser.add_argument('--start-date', type=str,
                        help='Start date filter (YYYY-MM-DD format)')
    parser.add_argument('--end-date', type=str,
                        help='End date filter (YYYY-MM-DD format)')
    parser.add_argument('--api', action='store_true',
                        help='Use API as data source instead of local SQLite')

    args = parser.parse_args()

    # Validate dates if provided
    if args.start_date:
        try:
            datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            print("Error: start-date must be in YYYY-MM-DD format", file=sys.stderr)
            sys.exit(1)

    if args.end_date:
        try:
            datetime.strptime(args.end_date, '%Y-%m-%d')
        except ValueError:
            print("Error: end-date must be in YYYY-MM-DD format", file=sys.stderr)
            sys.exit(1)

    # Check if database exists when not using API
    if not args.api and not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    try:
        exporter = RustchainExporter(use_api=args.api)
        exporter.export_data(args.data_type, args.format, args.output,
                            args.start_date, args.end_date)

    except Exception as e:
        print(f"Export failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
