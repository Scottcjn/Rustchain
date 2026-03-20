# SPDX-License-Identifier: MIT

import sqlite3
import os
import shutil
import tempfile
import logging
import sys
import glob
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'node', 'rustchain_v2.db')
BACKUP_PATTERN = os.path.join(os.path.dirname(__file__), 'node', 'rustchain_v2.db.bak*')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backup_verify.log'),
        logging.StreamHandler()
    ]
)

def find_latest_backup():
    """Find the most recent backup file."""
    backup_files = glob.glob(BACKUP_PATTERN)
    if not backup_files:
        return None

    # Sort by modification time, newest first
    backup_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return backup_files[0]

def verify_backup_integrity(backup_path):
    """Run SQLite integrity check on backup."""
    try:
        with sqlite3.connect(backup_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            return result[0] == 'ok'
    except Exception as e:
        logging.error(f"Integrity check failed: {e}")
        return False

def verify_table_existence(backup_path, required_tables):
    """Check that all required tables exist in backup."""
    try:
        with sqlite3.connect(backup_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = {row[0] for row in cursor.fetchall()}

            missing_tables = set(required_tables) - existing_tables
            if missing_tables:
                logging.error(f"Missing tables in backup: {missing_tables}")
                return False
            return True
    except Exception as e:
        logging.error(f"Table verification failed: {e}")
        return False

def get_table_row_counts(db_path):
    """Get row counts for all tables."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            counts = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            return counts
    except Exception as e:
        logging.error(f"Row count failed: {e}")
        return {}

def verify_data_consistency(live_db_path, backup_path):
    """Compare row counts between live DB and backup."""
    live_counts = get_table_row_counts(live_db_path)
    backup_counts = get_table_row_counts(backup_path)

    if not live_counts or not backup_counts:
        return False

    inconsistencies = []
    for table in live_counts:
        if table not in backup_counts:
            inconsistencies.append(f"Table {table} missing from backup")
        elif live_counts[table] != backup_counts[table]:
            inconsistencies.append(
                f"Table {table}: live={live_counts[table]}, backup={backup_counts[table]}"
            )

    if inconsistencies:
        logging.warning(f"Data inconsistencies found: {inconsistencies}")
        return False
    return True

def verify_backup(live_db_path=None, backup_path=None):
    """Main backup verification function."""
    if not live_db_path:
        live_db_path = DB_PATH

    if not backup_path:
        backup_path = find_latest_backup()
        if not backup_path:
            logging.error("No backup files found")
            return False

    logging.info(f"Verifying backup: {backup_path}")

    # Required tables for rustchain
    required_tables = ['balances', 'miner_attest_recent', 'headers', 'ledger']

    # Run all verification checks
    checks = [
        ("File exists", os.path.exists(backup_path)),
        ("File readable", os.access(backup_path, os.R_OK)),
        ("SQLite integrity", verify_backup_integrity(backup_path)),
        ("Required tables", verify_table_existence(backup_path, required_tables)),
    ]

    # Only run data consistency if live DB exists
    if os.path.exists(live_db_path):
        checks.append(("Data consistency", verify_data_consistency(live_db_path, backup_path)))

    all_passed = True
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        logging.info(f"{check_name}: {status}")
        if not result:
            all_passed = False

    if all_passed:
        logging.info("Backup verification completed successfully")
    else:
        logging.error("Backup verification failed")

    return all_passed

if __name__ == "__main__":
    success = verify_backup()
    sys.exit(0 if success else 1)
