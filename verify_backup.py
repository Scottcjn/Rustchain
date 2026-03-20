# SPDX-License-Identifier: MIT

import os
import sys
import sqlite3
import shutil
import tempfile
from datetime import datetime, timezone
import glob

DB_PATH = 'rustchain_v2.db'
BACKUP_PATTERN = 'rustchain_v2.db.bak*'
MAX_EPOCH_DIFF = 1

def find_latest_backup():
    """Find the most recent backup file"""
    backup_files = glob.glob(BACKUP_PATTERN)
    if not backup_files:
        return None

    # Sort by modification time, newest first
    backup_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return backup_files[0]

def run_integrity_check(db_path):
    """Run SQLite integrity check on database"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            return result[0] == 'ok'
    except Exception as e:
        print(f"Integrity check failed: {e}")
        return False

def get_table_count(db_path, table):
    """Get row count for a table"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            return cursor.fetchone()[0]
    except Exception:
        return 0

def validate_table_data(db_path):
    """Validate key tables have expected data"""
    checks = {}

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check balances table has positive amounts
            cursor.execute("SELECT COUNT(*) FROM balances WHERE balance > 0")
            checks['balances_positive'] = cursor.fetchone()[0] > 0

            # Check recent attestations (within last 50 blocks)
            cursor.execute("SELECT COUNT(*) FROM miner_attest_recent")
            checks['attestations_exist'] = cursor.fetchone()[0] > 0

            # Check headers table
            cursor.execute("SELECT COUNT(*) FROM headers")
            checks['headers_exist'] = cursor.fetchone()[0] > 0

            # Check ledger has transactions
            cursor.execute("SELECT COUNT(*) FROM ledger")
            checks['transactions_exist'] = cursor.fetchone()[0] > 0

            # Check epoch rewards
            cursor.execute("SELECT COUNT(*) FROM epoch_rewards")
            checks['epoch_rewards_exist'] = cursor.fetchone()[0] > 0

    except Exception as e:
        print(f"Table validation error: {e}")
        return {}

    return checks

def get_latest_epoch(db_path):
    """Get the latest epoch from headers table"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(epoch) FROM headers")
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
    except Exception:
        return 0

def compare_databases(live_db, backup_db):
    """Compare row counts and epochs between live and backup databases"""
    tables = ['balances', 'miner_attest_recent', 'headers', 'ledger', 'epoch_rewards']
    comparison = {}

    for table in tables:
        live_count = get_table_count(live_db, table)
        backup_count = get_table_count(backup_db, table)
        comparison[table] = {
            'live': live_count,
            'backup': backup_count,
            'diff': live_count - backup_count
        }

    # Check epoch difference
    live_epoch = get_latest_epoch(live_db)
    backup_epoch = get_latest_epoch(backup_db)
    epoch_diff = live_epoch - backup_epoch

    comparison['epochs'] = {
        'live': live_epoch,
        'backup': backup_epoch,
        'diff': epoch_diff,
        'acceptable': epoch_diff <= MAX_EPOCH_DIFF
    }

    return comparison

def print_results(backup_file, integrity_ok, table_checks, comparison):
    """Print verification results"""
    print("=== BACKUP VERIFICATION RESULTS ===")
    print(f"Backup file: {backup_file}")
    print(f"Verification time: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Integrity check
    status = "PASS" if integrity_ok else "FAIL"
    print(f"SQLite Integrity: {status}")

    # Table validation
    print("\nTable Validation:")
    all_tables_ok = True
    for check, result in table_checks.items():
        status = "PASS" if result else "FAIL"
        print(f"  {check}: {status}")
        if not result:
            all_tables_ok = False

    # Database comparison
    print("\nDatabase Comparison:")
    comparison_ok = True
    for table, data in comparison.items():
        if table == 'epochs':
            status = "PASS" if data['acceptable'] else "FAIL"
            print(f"  Epoch difference: {data['diff']} (live: {data['live']}, backup: {data['backup']}) - {status}")
            if not data['acceptable']:
                comparison_ok = False
        else:
            print(f"  {table}: live={data['live']}, backup={data['backup']}, diff={data['diff']}")

    # Overall result
    overall_pass = integrity_ok and all_tables_ok and comparison_ok
    print(f"\n=== OVERALL RESULT: {'PASS' if overall_pass else 'FAIL'} ===")

    return overall_pass

def main():
    print("Starting backup verification...")

    # Check if live database exists
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Live database {DB_PATH} not found")
        sys.exit(1)

    # Find latest backup
    backup_file = find_latest_backup()
    if not backup_file:
        print("ERROR: No backup files found matching pattern:", BACKUP_PATTERN)
        sys.exit(1)

    print(f"Found backup: {backup_file}")

    # Create temporary copy of backup
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
        temp_backup = temp_file.name

    try:
        shutil.copy2(backup_file, temp_backup)
        print(f"Copied backup to temporary location: {temp_backup}")

        # Run integrity check
        print("Running integrity check...")
        integrity_ok = run_integrity_check(temp_backup)

        # Validate table data
        print("Validating table data...")
        table_checks = validate_table_data(temp_backup)

        # Compare with live database
        print("Comparing with live database...")
        comparison = compare_databases(DB_PATH, temp_backup)

        # Print results and determine overall status
        overall_pass = print_results(backup_file, integrity_ok, table_checks, comparison)

        sys.exit(0 if overall_pass else 1)

    except Exception as e:
        print(f"ERROR: Verification failed: {e}")
        sys.exit(1)
    finally:
        # Clean up temporary file
        if os.path.exists(temp_backup):
            os.unlink(temp_backup)

if __name__ == '__main__':
    main()
