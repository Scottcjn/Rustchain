# SPDX-License-Identifier: MIT

"""
Data export utilities for RustChain attestation data.
Provides API client, database queries, transformations, and format writers.
"""

import json
import sqlite3
import csv
import io
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path

# Configuration
API_BASE_URL = "https://50.28.86.131"
DB_PATH = "rustchain.db"
TIMEOUT = 30

logger = logging.getLogger(__name__)


class RustChainAPIClient:
    """Client for fetching live data from RustChain API"""

    def __init__(self, base_url: str = API_BASE_URL, timeout: int = TIMEOUT):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RustChain-Export-Tool/1.0',
            'Accept': 'application/json'
        })

    def get_miners(self) -> List[Dict[str, Any]]:
        """Fetch active miners data"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/miners",
                timeout=self.timeout,
                verify=False
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Failed to fetch miners: {e}")
            return []

    def get_health(self) -> Dict[str, Any]:
        """Fetch node health status"""
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=self.timeout,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch health: {e}")
            return {}

    def get_attestations(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetch attestation data"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/attestations",
                params={'limit': limit},
                timeout=self.timeout,
                verify=False
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Failed to fetch attestations: {e}")
            return []


class DatabaseManager:
    """SQLite database operations for attestation data"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_attestations(self, start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query attestations from database with optional date filtering"""
        query = """
            SELECT
                id, miner_id, timestamp, hardware_type, cpu_model,
                memory_gb, verification_status, multiplier, reward_rtc,
                block_height, attestation_hash, created_at
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

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return []

    def get_miner_stats(self) -> List[Dict[str, Any]]:
        """Get aggregated miner statistics"""
        query = """
            SELECT
                miner_id,
                COUNT(*) as total_attestations,
                AVG(multiplier) as avg_multiplier,
                SUM(reward_rtc) as total_rewards,
                MAX(timestamp) as last_attestation,
                hardware_type,
                cpu_model
            FROM attestations
            GROUP BY miner_id, hardware_type, cpu_model
            ORDER BY total_rewards DESC
        """

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Miner stats query failed: {e}")
            return []

    def get_verification_summary(self) -> Dict[str, Any]:
        """Get verification status summary"""
        query = """
            SELECT
                verification_status,
                COUNT(*) as count,
                AVG(multiplier) as avg_multiplier
            FROM attestations
            GROUP BY verification_status
        """

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query)
                rows = cursor.fetchall()
                return {row['verification_status']: dict(row) for row in rows}
        except Exception as e:
            logger.error(f"Verification summary query failed: {e}")
            return {}


class DataTransformer:
    """Data transformation and validation utilities"""

    @staticmethod
    def validate_attestation_record(record: Dict[str, Any]) -> bool:
        """Validate attestation record has required fields"""
        required_fields = ['miner_id', 'timestamp', 'verification_status']
        return all(field in record and record[field] is not None
                  for field in required_fields)

    @staticmethod
    def normalize_timestamp(timestamp: Union[str, int, float]) -> str:
        """Convert timestamp to ISO format string"""
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
            return dt.isoformat()
        except Exception:
            return str(timestamp)

    @staticmethod
    def sanitize_for_csv(value: Any) -> str:
        """Sanitize value for CSV output"""
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value).replace('\n', ' ').replace('\r', '')

    @staticmethod
    def enrich_attestation_data(records: List[Dict[str, Any]],
                               miners_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich attestation records with miner metadata"""
        miners_lookup = {m.get('miner_id'): m for m in miners_data}

        enriched = []
        for record in records:
            miner_id = record.get('miner_id')
            miner_info = miners_lookup.get(miner_id, {})

            enriched_record = record.copy()
            enriched_record.update({
                'miner_balance_rtc': miner_info.get('balance_rtc', 0),
                'miner_status': miner_info.get('status', 'unknown'),
                'last_seen': miner_info.get('last_seen'),
                'enriched_at': datetime.now(timezone.utc).isoformat()
            })
            enriched.append(enriched_record)

        return enriched


class ExportWriter:
    """Format-specific export writers"""

    @staticmethod
    def write_csv(data: List[Dict[str, Any]], output_path: str) -> bool:
        """Write data to CSV format"""
        if not data:
            logger.warning("No data to export to CSV")
            return False

        try:
            fieldnames = list(data[0].keys())

            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in data:
                    sanitized_row = {
                        k: DataTransformer.sanitize_for_csv(v)
                        for k, v in row.items()
                    }
                    writer.writerow(sanitized_row)

            logger.info(f"CSV export completed: {output_path}")
            return True
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False

    @staticmethod
    def write_json(data: List[Dict[str, Any]], output_path: str, indent: int = 2) -> bool:
        """Write data to JSON format"""
        try:
            export_data = {
                'export_timestamp': datetime.now(timezone.utc).isoformat(),
                'record_count': len(data),
                'records': data
            }

            with open(output_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, indent=indent, ensure_ascii=False)

            logger.info(f"JSON export completed: {output_path}")
            return True
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False

    @staticmethod
    def write_parquet(data: List[Dict[str, Any]], output_path: str) -> bool:
        """Write data to Parquet format using pandas/pyarrow"""
        try:
            import pandas as pd

            df = pd.DataFrame(data)
            df.to_parquet(output_path, engine='pyarrow', compression='snappy')

            logger.info(f"Parquet export completed: {output_path}")
            return True
        except ImportError:
            logger.error("Parquet export requires pandas and pyarrow: pip install pandas pyarrow")
            return False
        except Exception as e:
            logger.error(f"Parquet export failed: {e}")
            return False


def export_attestation_data(output_format: str, output_path: str,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           include_live_data: bool = True) -> bool:
    """Main export function that orchestrates the full pipeline"""

    # Initialize components
    api_client = RustChainAPIClient()
    db_manager = DatabaseManager()

    # Fetch data
    logger.info("Fetching attestation data from database...")
    attestations = db_manager.get_attestations(start_date, end_date)

    if not attestations:
        logger.warning("No attestation data found")
        return False

    # Enrich with live miner data if requested
    if include_live_data:
        logger.info("Fetching live miner data...")
        miners = api_client.get_miners()
        attestations = DataTransformer.enrich_attestation_data(attestations, miners)

    # Validate records
    valid_records = [
        record for record in attestations
        if DataTransformer.validate_attestation_record(record)
    ]

    if len(valid_records) != len(attestations):
        logger.warning(f"Filtered out {len(attestations) - len(valid_records)} invalid records")

    # Normalize timestamps
    for record in valid_records:
        if 'timestamp' in record:
            record['timestamp'] = DataTransformer.normalize_timestamp(record['timestamp'])

    # Export in requested format
    writer = ExportWriter()

    if output_format.lower() == 'csv':
        return writer.write_csv(valid_records, output_path)
    elif output_format.lower() == 'json':
        return writer.write_json(valid_records, output_path)
    elif output_format.lower() == 'parquet':
        return writer.write_parquet(valid_records, output_path)
    else:
        logger.error(f"Unsupported export format: {output_format}")
        return False


def get_export_summary(start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> Dict[str, Any]:
    """Generate export summary statistics"""
    db_manager = DatabaseManager()

    attestations = db_manager.get_attestations(start_date, end_date)
    miner_stats = db_manager.get_miner_stats()
    verification_summary = db_manager.get_verification_summary()

    return {
        'total_attestations': len(attestations),
        'date_range': {
            'start': start_date,
            'end': end_date
        },
        'unique_miners': len(set(a['miner_id'] for a in attestations)),
        'verification_breakdown': verification_summary,
        'top_miners': miner_stats[:5],
        'export_generated_at': datetime.now(timezone.utc).isoformat()
    }
