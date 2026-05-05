#!/usr/bin/env python3
"""
Migration Script for Machine Passport Ledger (Issue #2309)

This script initializes the machine passport schema for existing RustChain nodes.
Run this once to add machine passport support to your node.

Usage:
    python migrate_machine_passport.py [--db-path PATH] [--dry-run]
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from machine_passport import init_machine_passport_schema


def get_default_db_path():
    """Get default database path from environment or use default."""
    return os.environ.get('PASSPORT_DB_PATH', 'machine_passports.db')


def check_existing_schema(db_path: str) -> dict:
    """Check what tables already exist."""
    result = {
        'exists': os.path.exists(db_path),
        'tables': [],
        'machine_passports': False,
        'passport_repair_log': False,
        'passport_attestation_history': False,
        'passport_benchmark_signatures': False,
        'passport_lineage_notes': False,
    }
    
    if not result['exists']:
        return result
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        result['tables'] = [row[0] for row in cursor.fetchall()]
        
        result['machine_passports'] = 'machine_passports' in result['tables']
        result['passport_repair_log'] = 'passport_repair_log' in result['tables']
        result['passport_attestation_history'] = 'passport_attestation_history' in result['tables']
        result['passport_benchmark_signatures'] = 'passport_benchmark_signatures' in result['tables']
        result['passport_lineage_notes'] = 'passport_lineage_notes' in result['tables']
        
        conn.close()
    except Exception as e:
        result['error'] = "Migration schema check failed"
    
    return result


def migrate(db_path: str, dry_run: bool = False) -> bool:
    """
    Run the migration.
    
    Args:
        db_path: Path to the database file
        dry_run: If True, only show what would be done
        
    Returns:
        True if successful, False otherwise
    """
    print(f"🔍 Checking database: {db_path}")
    
    status = check_existing_schema(db_path)
    
    if status['error']:
        print(f"❌ Error checking database: {status['error']}")
        return False
    
    if not status['exists']:
        print(f"ℹ️  Database does not exist yet. Will be created.")
    else:
        print(f"✓ Database exists with {len(status['tables'])} tables")
    
    # Check what needs to be created
    tables_to_create = []
    if not status['machine_passports']:
        tables_to_create.append('machine_passports')
    if not status['passport_repair_log']:
        tables_to_create.append('passport_repair_log')
    if not status['passport_attestation_history']:
        tables_to_create.append('passport_attestation_history')
    if not status['passport_benchmark_signatures']:
        tables_to_create.append('passport_benchmark_signatures')
    if not status['passport_lineage_notes']:
        tables_to_create.append('passport_lineage_notes')
    
    if not tables_to_create:
        print(f"✅ All machine passport tables already exist. No migration needed.")
        return True
    
    print(f"📋 Tables to create: {', '.join(tables_to_create)}")
    
    if dry_run:
        print(f"🛑 Dry run mode - no changes made")
        return True
    
    # Run migration
    print(f"🚀 Running migration...")
    
    try:
        conn = sqlite3.connect(db_path)
        init_machine_passport_schema(conn)
        conn.close()
        
        print(f"✅ Migration completed successfully!")
        print(f"✓ Created {len(tables_to_create)} table(s)")
        
        # Verify
        status_after = check_existing_schema(db_path)
        all_created = all([
            status_after['machine_passports'],
            status_after['passport_repair_log'],
            status_after['passport_attestation_history'],
            status_after['passport_benchmark_signatures'],
            status_after['passport_lineage_notes'],
        ])
        
        if all_created:
            print(f"✓ All tables verified")
            return True
        else:
            print(f"⚠️  Some tables may not have been created correctly")
            return False
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Migrate database to support Machine Passport Ledger'
    )
    parser.add_argument(
        '--db-path',
        default=None,
        help='Database path (default: PASSPORT_DB_PATH env var or machine_passports.db)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    db_path = args.db_path or get_default_db_path()
    
    print("="*70)
    print("Machine Passport Ledger Migration")
    print("Issue #2309 — Give Every Relic a Biography")
    print("="*70)
    print()
    
    success = migrate(db_path, dry_run=args.dry_run)
    
    print()
    print("="*70)
    if success:
        print("✅ Migration completed successfully!")
        print()
        print("Next steps:")
        print("1. Start your RustChain node")
        print("2. Access the web viewer at: http://localhost:5000/passport/")
        print("3. Create your first passport:")
        print("   python machine_passport.py --action create \\")
        print("     --machine-id <hardware_id> \\")
        print("     --name \"Your Machine Name\" \\")
        print("     --owner <your_miner_id>")
        sys.exit(0)
    else:
        print("❌ Migration failed!")
        print()
        print("Check the error messages above and try again.")
        print("For support, see: bounties/issue-2309/README.md")
        sys.exit(1)


if __name__ == '__main__':
    main()
