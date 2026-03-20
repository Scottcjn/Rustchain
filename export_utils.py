// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import csv
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

DB_PATH = 'rustchain.db'
EXPORT_DIR = 'exports'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_export_dir():
    """Create export directory if it doesn't exist"""
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

def get_db_connection():
    """Get database connection with context manager pattern"""
    return sqlite3.connect(DB_PATH)

def dict_factory(cursor, row):
    """Convert sqlite3 row to dictionary"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def extract_attestation_data(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract attestation records with optional date filtering"""
    with get_db_connection() as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()

        query = """
        SELECT
            id,
            node_id,
            attestation_type,
            hardware_data,
            fingerprint_hash,
            timestamp,
            status,
            verification_score,
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
        return cursor.fetchall()

def extract_mining_data(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract mining records with optional date filtering"""
    with get_db_connection() as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()

        query = """
        SELECT
            id,
            block_height,
            miner_id,
            hardware_type,
            multiplier,
            base_reward,
            adjusted_reward,
            timestamp,
            difficulty,
            hash_rate
        FROM mining_records
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

        query += " ORDER BY block_height DESC"

        cursor.execute(query, params)
        return cursor.fetchall()

def extract_node_health_data() -> List[Dict[str, Any]]:
    """Extract node health status records"""
    with get_db_connection() as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()

        query = """
        SELECT
            node_id,
            status,
            last_seen,
            version,
            sync_height,
            peer_count,
            uptime_seconds,
            hardware_verified
        FROM node_status
        ORDER BY last_seen DESC
        """

        cursor.execute(query)
        return cursor.fetchall()

def export_to_csv(data: List[Dict[str, Any]], filename: str) -> str:
    """Export data to CSV format"""
    ensure_export_dir()
    filepath = os.path.join(EXPORT_DIR, filename)

    if not data:
        logger.warning(f"No data to export to {filename}")
        return filepath

    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for row in data:
            # Handle JSON fields by converting to string
            processed_row = {}
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    processed_row[key] = json.dumps(value)
                else:
                    processed_row[key] = value
            writer.writerow(processed_row)

    logger.info(f"Exported {len(data)} records to {filepath}")
    return filepath

def export_to_json(data: List[Dict[str, Any]], filename: str) -> str:
    """Export data to JSON format"""
    ensure_export_dir()
    filepath = os.path.join(EXPORT_DIR, filename)

    export_metadata = {
        'export_timestamp': datetime.utcnow().isoformat(),
        'record_count': len(data),
        'format': 'json'
    }

    export_data = {
        'metadata': export_metadata,
        'data': data
    }

    with open(filepath, 'w', encoding='utf-8') as jsonfile:
        json.dump(export_data, jsonfile, indent=2, default=str)

    logger.info(f"Exported {len(data)} records to {filepath}")
    return filepath

def export_to_parquet(data: List[Dict[str, Any]], filename: str) -> str:
    """Export data to Parquet format (requires pandas and pyarrow)"""
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        logger.error("Parquet export requires pandas and pyarrow: pip install pandas pyarrow")
        raise ImportError("Missing dependencies for Parquet export")

    ensure_export_dir()
    filepath = os.path.join(EXPORT_DIR, filename)

    if not data:
        logger.warning(f"No data to export to {filepath}")
        return filepath

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Handle JSON columns by converting to string
    for col in df.columns:
        if df[col].dtype == 'object':
            # Check if any values are dict/list
            sample_values = df[col].dropna().head(5)
            if any(isinstance(v, (dict, list)) for v in sample_values):
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)

    # Write parquet file
    table = pa.Table.from_pandas(df)
    pq.write_table(table, filepath)

    logger.info(f"Exported {len(data)} records to {filepath}")
    return filepath

def get_export_stats() -> Dict[str, int]:
    """Get statistics about available data for export"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        # Count attestations
        cursor.execute("SELECT COUNT(*) FROM attestations")
        stats['attestations'] = cursor.fetchone()[0]

        # Count mining records
        cursor.execute("SELECT COUNT(*) FROM mining_records")
        stats['mining_records'] = cursor.fetchone()[0]

        # Count active nodes
        cursor.execute("SELECT COUNT(*) FROM node_status WHERE status = 'active'")
        stats['active_nodes'] = cursor.fetchone()[0]

        # Get date ranges
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM attestations")
        result = cursor.fetchone()
        if result[0]:
            stats['attestation_date_range'] = {'start': result[0], 'end': result[1]}

        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM mining_records")
        result = cursor.fetchone()
        if result[0]:
            stats['mining_date_range'] = {'start': result[0], 'end': result[1]}

        return stats

def generate_timestamp_suffix() -> str:
    """Generate timestamp suffix for export filenames"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def cleanup_old_exports(max_age_days: int = 30):
    """Remove export files older than specified days"""
    if not os.path.exists(EXPORT_DIR):
        return

    current_time = datetime.now().timestamp()
    max_age_seconds = max_age_days * 24 * 3600

    removed_count = 0
    for filename in os.listdir(EXPORT_DIR):
        filepath = os.path.join(EXPORT_DIR, filename)
        if os.path.isfile(filepath):
            file_age = current_time - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                os.remove(filepath)
                removed_count += 1

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old export files")
