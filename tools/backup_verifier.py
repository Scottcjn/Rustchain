#!/usr/bin/env python3
"""
RustChain Backup Verification Script

Verifies the integrity of RustChain SQLite database backups.
Ensures backups are valid before relying on them for disaster recovery.

Usage:
    python3 backup_verifier.py [--backup-dir PATH] [--live-db PATH]

Exit codes:
    0 = PASS
    1 = FAIL

Cron example:
    0 6 * * * /root/Rustchain/tools/backup_verifier.py >> /var/log/backup_verify.log 2>&1
"""

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Key tables that must exist and have data
REQUIRED_TABLES = [
    "balances",
    "miner_attest_recent",
    "headers",
    "ledger",
    "epoch_rewards",
]

# Default paths
DEFAULT_BACKUP_DIR = os.path.expanduser("~/.rustchain/backups")
DEFAULT_LIVE_DB = os.path.expanduser("~/.rustchain/rustchain_v2.db")


def find_latest_backup(backup_dir: str) -> Optional[Path]:
    """Find the most recent backup file in the backup directory."""
    backup_path = Path(backup_dir)
    
    if not backup_path.exists():
        return None
    
    # Look for common backup file patterns
    backup_patterns = [
        "rustchain_v2.db.bak",
        "rustchain_v2_*.db",
        "*.db.bak",
    ]
    
    backups = []
    for pattern in backup_patterns:
        backups.extend(backup_path.glob(pattern))
    
    if not backups:
        return None
    
    # Sort by modification time, most recent first
    backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return backups[0]


def verify_backup_integrity(backup_file: Path) -> Tuple[bool, str]:
    """Run SQLite integrity check on the backup file."""
    try:
        conn = sqlite3.connect(str(backup_file))
        cursor = conn.cursor()
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        
        conn.close()
        
        if result[0] == "ok":
            return True, "PASS"
        else:
            return False, result[0]
    except Exception as e:
        return False, str(e)


def get_table_row_counts(db_path: Path) -> Dict[str, int]:
    """Get row counts for all required tables."""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        counts = {}
        for table in REQUIRED_TABLES:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                counts[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                counts[table] = -1  # Table doesn't exist
        
        conn.close()
        return counts
    except Exception:
        return {table: -1 for table in REQUIRED_TABLES}


def verify_backup(
    backup_file: Path,
    live_db_path: Optional[Path] = None,
    copy_to_temp: bool = True
) -> Tuple[bool, str, Dict]:
    """
    Verify a backup file.
    
    Returns: (success, message, details)
    """
    details = {
        "backup_file": str(backup_file),
        "timestamp": datetime.now().isoformat(),
        "integrity": "N/A",
        "tables": {},
        "row_comparison": {},
        "result": "FAIL",
    }
    
    # Copy to temp location for non-destructive testing
    if copy_to_temp:
        temp_dir = tempfile.mkdtemp()
        temp_backup = Path(temp_dir) / backup_file.name
        shutil.copy2(backup_file, temp_backup)
        test_db = temp_backup
    else:
        test_db = backup_file
    
    try:
        # Step 1: Integrity check
        integrity_pass, integrity_msg = verify_backup_integrity(test_db)
        details["integrity"] = integrity_msg
        
        if not integrity_pass:
            return False, f"Integrity check failed: {integrity_msg}", details
        
        # Step 2: Check tables exist and have data
        table_counts = get_table_row_counts(test_db)
        details["tables"] = table_counts
        
        missing_tables = []
        empty_tables = []
        
        for table in REQUIRED_TABLES:
            count = table_counts.get(table, -1)
            if count < 0:
                missing_tables.append(table)
            elif count == 0:
                empty_tables.append(table)
        
        if missing_tables:
            return False, f"Missing tables: {', '.join(missing_tables)}", details
        
        if empty_tables:
            return False, f"Empty tables: {', '.join(empty_tables)}", details
        
        # Step 3: Compare with live DB if available
        if live_db_path and live_db_path.exists():
            live_counts = get_table_row_counts(live_db_path)
            details["row_comparison"] = {
                table: {
                    "backup": table_counts.get(table, 0),
                    "live": live_counts.get(table, 0),
                }
                for table in REQUIRED_TABLES
            }
            
            # Check if backup is not more than 1 epoch behind (allowing some tolerance)
            for table in REQUIRED_TABLES:
                backup_count = table_counts.get(table, 0)
                live_count = live_counts.get(table, 0)
                
                if live_count > 0 and backup_count < live_count * 0.9:
                    # More than 10% behind might indicate stale backup
                    details["row_comparison"][table]["status"] = "WARNING"
                else:
                    details["row_comparison"][table]["status"] = "OK"
        
        details["result"] = "PASS"
        return True, "All checks passed", details
        
    finally:
        # Clean up temp file
        if copy_to_temp and test_db.exists():
            try:
                os.remove(test_db)
                os.rmdir(os.path.dirname(test_db))
            except Exception:
                pass


def print_report(success: bool, message: str, details: Dict):
    """Print a formatted report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"[{timestamp}] Backup: {details['backup_file']}")
    print(f"[{timestamp}] Integrity: {details['integrity']}")
    
    for table, count in details.get("tables", {}).items():
        status = "✅" if count > 0 else "❌"
        print(f"[{timestamp}] {table}: {count} rows {status}")
    
    if details.get("row_comparison"):
        for table, comp in details["row_comparison"].items():
            backup_rows = comp.get("backup", "N/A")
            live_rows = comp.get("live", "N/A")
            status = comp.get("status", "")
            status_icon = "⚠️ " if status == "WARNING" else ""
            print(f"[{timestamp}] {table}: {backup_rows} rows (live: {live_rows}) {status_icon}")
    
    result = "PASS" if success else "FAIL"
    print(f"[{timestamp}] RESULT: {result}")
    
    if not success:
        print(f"[{timestamp}] ERROR: {message}")


def main():
    parser = argparse.ArgumentParser(
        description="Verify RustChain database backup integrity"
    )
    parser.add_argument(
        "--backup-dir",
        default=DEFAULT_BACKUP_DIR,
        help=f"Directory containing backups (default: {DEFAULT_BACKUP_DIR})"
    )
    parser.add_argument(
        "--live-db",
        default=DEFAULT_LIVE_DB,
        help=f"Path to live database for comparison (default: {DEFAULT_LIVE_DB})"
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Don't copy to temp location (not recommended)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output final result"
    )
    
    args = parser.parse_args()
    
    # Find latest backup
    backup_file = find_latest_backup(args.backup_dir)
    
    if not backup_file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ERROR: No backup files found in {args.backup_dir}")
        sys.exit(1)
    
    # Get live DB path
    live_db = Path(args.live_db) if args.live_db else None
    
    # Verify backup
    success, message, details = verify_backup(
        backup_file,
        live_db_path=live_db,
        copy_to_temp=not args.no_copy
    )
    
    # Print report
    if not args.quiet:
        print_report(success, message, details)
    else:
        result = "PASS" if success else "FAIL"
        print(result)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
