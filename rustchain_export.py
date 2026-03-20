# SPDX-License-Identifier: MIT
"""
RustChain Data Export Tool - Extract attestation and reward data to multiple formats
"""

import argparse
import csv
import json
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union
import urllib.request
import urllib.error

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class RustChainExporter:
    def __init__(self, db_path: str = "rustchain.db", api_base: str = "https://50.28.86.131"):
        self.db_path = db_path
        self.api_base = api_base.rstrip('/')
        self.output_dir = Path("exports")

    def setup_output_dir(self, custom_dir: Optional[str] = None):
        """Create output directory if it doesn't exist"""
        if custom_dir:
            self.output_dir = Path(custom_dir)
        self.output_dir.mkdir(exist_ok=True)

    def fetch_api_data(self, endpoint: str) -> Optional[Dict]:
        """Fetch data from RustChain API endpoint"""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            print(f"API fetch failed for {endpoint}: {e}")
            return None

    def get_local_attestations(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Extract attestation data from local database"""
        attestations = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = """
                    SELECT
                        miner_id,
                        timestamp,
                        hardware_score,
                        vintage_multiplier,
                        attestation_hash,
                        status,
                        created_at
                    FROM attestations
                """
                params = []

                if start_date or end_date:
                    query += " WHERE "
                    conditions = []
                    if start_date:
                        conditions.append("timestamp >= ?")
                        params.append(start_date)
                    if end_date:
                        conditions.append("timestamp <= ?")
                        params.append(end_date)
                    query += " AND ".join(conditions)

                query += " ORDER BY timestamp DESC"

                cursor.execute(query, params)
                for row in cursor.fetchall():
                    attestations.append(dict(row))

        except sqlite3.Error as e:
            print(f"Database error: {e}")

        return attestations

    def get_local_rewards(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Extract reward data from local database"""
        rewards = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = """
                    SELECT
                        miner_id,
                        block_height,
                        reward_amount,
                        vintage_bonus,
                        timestamp,
                        transaction_hash
                    FROM rewards
                """
                params = []

                if start_date or end_date:
                    query += " WHERE "
                    conditions = []
                    if start_date:
                        conditions.append("timestamp >= ?")
                        params.append(start_date)
                    if end_date:
                        conditions.append("timestamp <= ?")
                        params.append(end_date)
                    query += " AND ".join(conditions)

                query += " ORDER BY timestamp DESC"

                cursor.execute(query, params)
                for row in cursor.fetchall():
                    rewards.append(dict(row))

        except sqlite3.Error as e:
            print(f"Database error: {e}")

        return rewards

    def get_api_miners(self) -> List[Dict]:
        """Fetch current miner data from API"""
        data = self.fetch_api_data("/api/miners")
        if data and "miners" in data:
            return data["miners"]
        return []

    def get_api_attestation_history(self) -> List[Dict]:
        """Fetch attestation history from API"""
        data = self.fetch_api_data("/api/attestations")
        if data and isinstance(data, list):
            return data
        elif data and "attestations" in data:
            return data["attestations"]
        return []

    def export_csv(self, data: List[Dict], filename: str):
        """Export data to CSV format"""
        if not data:
            print(f"No data to export for {filename}")
            return

        filepath = self.output_dir / filename
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"Exported {len(data)} records to {filepath}")

    def export_json(self, data: List[Dict], filename: str):
        """Export data to JSON format"""
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, default=str)
        print(f"Exported {len(data)} records to {filepath}")

    def export_jsonl(self, data: List[Dict], filename: str):
        """Export data to JSONL format (one JSON object per line)"""
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as jsonlfile:
            for record in data:
                jsonlfile.write(json.dumps(record, default=str) + '\n')
        print(f"Exported {len(data)} records to {filepath}")

    def export_parquet(self, data: List[Dict], filename: str):
        """Export data to Parquet format using pandas"""
        if not PANDAS_AVAILABLE:
            print(f"Pandas not available - skipping Parquet export for {filename}")
            return

        if not data:
            print(f"No data to export for {filename}")
            return

        try:
            df = pd.DataFrame(data)
            filepath = self.output_dir / filename
            df.to_parquet(filepath, index=False)
            print(f"Exported {len(data)} records to {filepath}")
        except Exception as e:
            print(f"Parquet export failed for {filename}: {e}")

    def run_export(self, formats: List[str], data_source: str, start_date: Optional[str] = None,
                   end_date: Optional[str] = None, output_dir: Optional[str] = None):
        """Main export orchestration"""
        self.setup_output_dir(output_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Collect data based on source
        if data_source in ['local', 'both']:
            print("Fetching local attestations...")
            local_attestations = self.get_local_attestations(start_date, end_date)
            if local_attestations:
                self._export_data_in_formats(local_attestations, f"attestations_local_{timestamp}", formats)

            print("Fetching local rewards...")
            local_rewards = self.get_local_rewards(start_date, end_date)
            if local_rewards:
                self._export_data_in_formats(local_rewards, f"rewards_local_{timestamp}", formats)

        if data_source in ['api', 'both']:
            print("Fetching API miners...")
            api_miners = self.get_api_miners()
            if api_miners:
                self._export_data_in_formats(api_miners, f"miners_api_{timestamp}", formats)

            print("Fetching API attestations...")
            api_attestations = self.get_api_attestation_history()
            if api_attestations:
                # Filter by date if specified
                if start_date or end_date:
                    api_attestations = self._filter_api_data_by_date(api_attestations, start_date, end_date)
                self._export_data_in_formats(api_attestations, f"attestations_api_{timestamp}", formats)

    def _export_data_in_formats(self, data: List[Dict], base_filename: str, formats: List[str]):
        """Export data in specified formats"""
        for fmt in formats:
            if fmt == 'csv':
                self.export_csv(data, f"{base_filename}.csv")
            elif fmt == 'json':
                self.export_json(data, f"{base_filename}.json")
            elif fmt == 'jsonl':
                self.export_jsonl(data, f"{base_filename}.jsonl")
            elif fmt == 'parquet':
                self.export_parquet(data, f"{base_filename}.parquet")

    def _filter_api_data_by_date(self, data: List[Dict], start_date: Optional[str], end_date: Optional[str]) -> List[Dict]:
        """Filter API data by date range"""
        filtered_data = []

        for record in data:
            # Look for timestamp-like fields
            record_date = None
            for field in ['timestamp', 'created_at', 'date', 'time']:
                if field in record and record[field]:
                    record_date = str(record[field])
                    break

            if not record_date:
                continue

            # Simple date comparison (assumes ISO format or similar)
            include_record = True
            if start_date and record_date < start_date:
                include_record = False
            if end_date and record_date > end_date:
                include_record = False

            if include_record:
                filtered_data.append(record)

        return filtered_data


def parse_date(date_str: str) -> str:
    """Parse and validate date string"""
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Data Export Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all data in CSV format
  python rustchain_export.py --format csv

  # Export attestations from last 30 days in JSON and Parquet
  python rustchain_export.py --format json parquet --start-date 2024-01-01

  # Export only API data to custom directory
  python rustchain_export.py --source api --output-dir /tmp/exports

  # Export with date range filtering
  python rustchain_export.py --start-date 2024-01-01 --end-date 2024-01-31
        """
    )

    parser.add_argument(
        '--format', '--formats',
        nargs='+',
        choices=['csv', 'json', 'jsonl', 'parquet'],
        default=['csv'],
        help='Export formats (default: csv)'
    )

    parser.add_argument(
        '--source',
        choices=['local', 'api', 'both'],
        default='both',
        help='Data source (default: both)'
    )

    parser.add_argument(
        '--start-date',
        type=parse_date,
        help='Start date for filtering (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end-date',
        type=parse_date,
        help='End date for filtering (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--output-dir',
        help='Output directory (default: ./exports)'
    )

    parser.add_argument(
        '--db-path',
        default='rustchain.db',
        help='SQLite database path (default: rustchain.db)'
    )

    parser.add_argument(
        '--api-base',
        default='https://50.28.86.131',
        help='RustChain API base URL (default: https://50.28.86.131)'
    )

    args = parser.parse_args()

    # Validate date range
    if args.start_date and args.end_date:
        if args.start_date > args.end_date:
            print("Error: start-date must be before end-date")
            sys.exit(1)

    # Check for parquet dependencies
    if 'parquet' in args.format and not PANDAS_AVAILABLE:
        print("Warning: pandas not installed - parquet export will be skipped")
        print("Install with: pip install pandas pyarrow")

    exporter = RustChainExporter(db_path=args.db_path, api_base=args.api_base)

    try:
        exporter.run_export(
            formats=args.format,
            data_source=args.source,
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir
        )
        print("Export completed successfully!")
    except KeyboardInterrupt:
        print("\nExport interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Export failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
