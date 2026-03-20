// SPDX-License-Identifier: MIT
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

def get_table_counts(db_path, tables):
    """Get row counts for specified tables."""
    counts = {}
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                counts[table] = cursor.fetchone()[0]
    except Exception as e:
        logging.error(f"Count query failed for {db_path}: {e}")
        return None
    return counts

def verify_data_presence(backup_path):
    """Verify key tables have meaningful data."""
    checks = []

    try:
        with sqlite3.connect(backup_path) as conn:
            cursor = conn.cursor()

            # Check balances table has positive amounts
            cursor.execute("SELECT COUNT(*) FROM balances WHERE amount > 0;")
            positive_balances = cursor.fetchone()[0]
            checks.append(('balances_positive', positive_balances > 0))

            # Check recent attestations (within 24 hours)
            cutoff_time = int((datetime.now() - timedelta(hours=24)).timestamp())
            cursor.execute("SELECT COUNT(*) FROM miner_attest_recent WHERE timestamp > ?;", (cutoff_time,))
            recent_attestations = cursor.fetchone()[0]
            checks.append(('recent_attestations', recent_attestations > 0))

            # Check headers exist
            cursor.execute("SELECT COUNT(*) FROM headers;")
            header_count = cursor.fetchone()[0]
            checks.append(('headers_exist', header_count > 0))

            # Check ledger has transactions
            cursor.execute("SELECT COUNT(*) FROM ledger;")
            ledger_count = cursor.fetchone()[0]
            checks.append(('ledger_exists', ledger_count > 0))

            # Check epoch rewards exist
            cursor.execute("SELECT COUNT(*) FROM epoch_rewards;")
            rewards_count = cursor.fetchone()[0]
            checks.append(('epoch_rewards_exist', rewards_count > 0))

    except Exception as e:
        logging.error(f"Data verification failed: {e}")
        return False, []

    all_passed = all(check[1] for check in checks)
    return all_passed, checks

def compare_with_live_db(backup_path, live_db_path):
    """Compare backup row counts with live database."""
    tables = ['balances', 'miner_attest_recent', 'headers', 'ledger', 'epoch_rewards']

    backup_counts = get_table_counts(backup_path, tables)
    live_counts = get_table_counts(live_db_path, tables)

    if not backup_counts or not live_counts:
        return False, {}

    comparison = {}
    acceptable_lag = True

    for table in tables:
        backup_count = backup_counts.get(table, 0)
        live_count = live_counts.get(table, 0)
        diff = live_count - backup_count

        # Allow some lag but not too much
        max_acceptable_diff = max(100, live_count * 0.05)  # 5% or 100 rows

        if diff > max_acceptable_diff:
            acceptable_lag = False

        comparison[table] = {
            'backup': backup_count,
            'live': live_count,
            'diff': diff,
            'acceptable': diff <= max_acceptable_diff
        }

    return acceptable_lag, comparison

def run_verification():
    """Main verification routine."""
    logging.info("Starting backup verification process")

    # Find latest backup
    backup_file = find_latest_backup()
    if not backup_file:
        logging.error("No backup files found")
        return False

    logging.info(f"Found backup file: {backup_file}")
    backup_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(backup_file))
    logging.info(f"Backup age: {backup_age}")

    # Create temporary copy
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        temp_backup_path = temp_file.name

    try:
        shutil.copy2(backup_file, temp_backup_path)
        logging.info(f"Created temporary copy: {temp_backup_path}")

        # Run integrity check
        logging.info("Running integrity check...")
        if not verify_backup_integrity(temp_backup_path):
            logging.error("FAIL: Backup integrity check failed")
            return False
        logging.info("PASS: Backup integrity check")

        # Verify required tables exist
        required_tables = ['balances', 'miner_attest_recent', 'headers', 'ledger', 'epoch_rewards']
        logging.info("Checking table existence...")
        if not verify_table_existence(temp_backup_path, required_tables):
            logging.error("FAIL: Required tables missing")
            return False
        logging.info("PASS: All required tables present")

        # Verify data presence
        logging.info("Verifying data presence...")
        data_ok, data_checks = verify_data_presence(temp_backup_path)
        for check_name, passed in data_checks:
            status = "PASS" if passed else "FAIL"
            logging.info(f"{status}: {check_name}")

        if not data_ok:
            logging.error("FAIL: Data verification failed")
            return False

        # Compare with live database
        if os.path.exists(DB_PATH):
            logging.info("Comparing with live database...")
            counts_ok, comparison = compare_with_live_db(temp_backup_path, DB_PATH)

            for table, data in comparison.items():
                status = "PASS" if data['acceptable'] else "FAIL"
                logging.info(f"{status}: {table} - backup:{data['backup']} live:{data['live']} diff:{data['diff']}")

            if not counts_ok:
                logging.warning("WARNING: Backup appears to be significantly behind live database")
        else:
            logging.warning("Live database not found, skipping comparison")

        logging.info("PASS: Backup verification completed successfully")
        return True

    except Exception as e:
        logging.error(f"Verification failed with exception: {e}")
        return False
    finally:
        # Cleanup temporary file
        try:
            os.unlink(temp_backup_path)
        except:
            pass

if __name__ == "__main__":
    success = run_verification()

    if success:
        print("Backup verification: PASS")
        sys.exit(0)
    else:
        print("Backup verification: FAIL")
        sys.exit(1)
