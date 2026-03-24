#!/usr/bin/env python3
"""
RustChain Testnet to Mainnet Migration Script
==============================================

Phase 6 Implementation:
- Testnet state snapshot
- Database schema migration
- Premine initialization
- Genesis block creation
- Validation and verification

Run this script ONCE to migrate from testnet to mainnet.
"""

import os
import sys
import json
import sqlite3
import shutil
import time
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

# Import mainnet modules
from rustchain_crypto import blake2b256_hex, canonical_json, generate_wallet_keypair
from rustchain_genesis_premine import PremineManager, TOTAL_PREMINE_RTC, FOUNDER_ALLOCATIONS
from rustchain_tx_handler import TransactionPool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MIGRATE] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# MIGRATION CONFIGURATION
# =============================================================================

MIGRATION_VERSION = "2.3.0-mainnet"
GENESIS_TIMESTAMP = 1728000000  # Oct 4, 2024 00:00:00 UTC (same as testnet)

# Paths
TESTNET_DB_PATH = os.environ.get("TESTNET_DB", "/root/rustchain/rustchain_v2.db")
MAINNET_DB_PATH = os.environ.get("MAINNET_DB", "/root/rustchain/rustchain_mainnet.db")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/root/rustchain/backups")

# Migration flags
PRESERVE_ATTESTATION_HISTORY = True
PRESERVE_MINER_STATS = True
RESET_BALANCES = True  # Reset to premine only


# =============================================================================
# MIGRATION STEPS
# =============================================================================

class RustChainMigration:
    """
    Handles testnet -> mainnet migration.
    """

    def __init__(
        self,
        testnet_db: str = TESTNET_DB_PATH,
        mainnet_db: str = MAINNET_DB_PATH,
        backup_dir: str = BACKUP_DIR
    ):
        self.testnet_db = testnet_db
        self.mainnet_db = mainnet_db
        self.backup_dir = backup_dir
        self.migration_log = []
        self.errors = []

    def log(self, message: str, level: str = "INFO"):
        """Log migration step"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        self.migration_log.append(entry)

        if level == "ERROR":
            logger.error(message)
            self.errors.append(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

    def pre_flight_checks(self) -> bool:
        """Run pre-migration validation"""
        self.log("=" * 60)
        self.log("PRE-FLIGHT CHECKS")
        self.log("=" * 60)

        # Check testnet DB exists
        if not os.path.exists(self.testnet_db):
            self.log(f"Testnet DB not found: {self.testnet_db}", "ERROR")
            return False
        self.log(f"Testnet DB found: {self.testnet_db}")

        # Check mainnet DB doesn't exist (prevent accidental overwrite)
        if os.path.exists(self.mainnet_db):
            self.log(f"Mainnet DB already exists: {self.mainnet_db}", "WARNING")
            self.log("Will create backup before overwriting")

        # Check backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
        self.log(f"Backup directory: {self.backup_dir}")

        # Verify testnet DB integrity
        try:
            with sqlite3.connect(self.testnet_db) as conn:
                cursor = conn.cursor()

                # Check tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                self.log(f"Testnet tables: {tables}")

                # Check miner attestations
                if "miner_attest_recent" in tables:
                    cursor.execute("SELECT COUNT(*) FROM miner_attest_recent")
                    count = cursor.fetchone()[0]
                    self.log(f"Active attestations: {count}")

                # Check balances
                if "balances" in tables:
                    cursor.execute("SELECT COUNT(*), SUM(balance_urtc) FROM balances")
                    row = cursor.fetchone()
                    self.log(f"Testnet wallets: {row[0]}, Total balance: {(row[1] or 0) / 100_000_000:.2f} RTC")

        except Exception as e:
            self.log(f"Failed to verify testnet DB: {e}", "ERROR")
            return False

        self.log("Pre-flight checks PASSED")
        return True

    def create_backup(self) -> str:
        """Create timestamped backup of testnet DB"""
        self.log("Creating backup...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"testnet_backup_{timestamp}.db")

        shutil.copy2(self.testnet_db, backup_path)
        self.log(f"Backup created: {backup_path}")

        # Also backup mainnet if it exists
        if os.path.exists(self.mainnet_db):
            mainnet_backup = os.path.join(self.backup_dir, f"mainnet_backup_{timestamp}.db")
            shutil.copy2(self.mainnet_db, mainnet_backup)
            self.log(f"Mainnet backup created: {mainnet_backup}")

        return backup_path

    def create_mainnet_schema(self):
        """Create mainnet database with upgraded schema"""
        self.log("Creating mainnet database schema...")

        # Remove existing if present
        if os.path.exists(self.mainnet_db):
            os.remove(self.mainnet_db)

        with sqlite3.connect(self.mainnet_db) as conn:
            cursor = conn.cursor()

            # Core tables
            cursor.execute("""
                CREATE TABLE balances (
                    wallet TEXT PRIMARY KEY,
                    balance_urtc INTEGER DEFAULT 0,
                    wallet_nonce INTEGER DEFAULT 0,
                    created_at INTEGER,
                    updated_at INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE blocks (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT UNIQUE NOT NULL,
                    prev_hash TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    merkle_root TEXT NOT NULL,
                    state_root TEXT NOT NULL,
                    attestations_hash TEXT NOT NULL,
                    producer TEXT NOT NULL,
                    producer_sig TEXT NOT NULL,
                    tx_count INTEGER NOT NULL,
                    attestation_count INTEGER NOT NULL,
                    body_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    device_arch TEXT,
                    device_family TEXT,
                    device_model TEXT,
                    device_year INTEGER,
                    ts_ok INTEGER,
                    last_block_produced INTEGER,
                    total_blocks_produced INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE miner_attest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner TEXT NOT NULL,
                    device_arch TEXT,
                    device_family TEXT,
                    ts_ok INTEGER NOT NULL,
                    block_height INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE pending_transactions (
                    tx_hash TEXT PRIMARY KEY,
                    from_addr TEXT NOT NULL,
                    to_addr TEXT NOT NULL,
                    amount_urtc INTEGER NOT NULL,
                    nonce INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    memo TEXT DEFAULT '',
                    signature TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)

            cursor.execute("""
                CREATE TABLE transaction_history (
                    tx_hash TEXT PRIMARY KEY,
                    from_addr TEXT NOT NULL,
                    to_addr TEXT NOT NULL,
                    amount_urtc INTEGER NOT NULL,
                    nonce INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    memo TEXT DEFAULT '',
                    signature TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    block_height INTEGER,
                    block_hash TEXT,
                    confirmed_at INTEGER,
                    status TEXT DEFAULT 'confirmed'
                )
            """)

            cursor.execute("""
                CREATE TABLE wallet_pubkeys (
                    address TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    registered_at INTEGER NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE premine_allocations (
                    allocation_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    public_key TEXT,
                    total_urtc INTEGER NOT NULL,
                    vesting_months INTEGER NOT NULL,
                    cliff_months INTEGER NOT NULL,
                    claimed_urtc INTEGER DEFAULT 0,
                    role TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE vesting_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    allocation_id TEXT NOT NULL,
                    amount_urtc INTEGER NOT NULL,
                    claimed_at INTEGER NOT NULL,
                    tx_hash TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE ergo_anchors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rustchain_height INTEGER NOT NULL,
                    rustchain_hash TEXT NOT NULL,
                    commitment_hash TEXT NOT NULL,
                    ergo_tx_id TEXT NOT NULL,
                    ergo_height INTEGER,
                    confirmations INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE chain_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX idx_tx_pending_from ON pending_transactions(from_addr)")
            cursor.execute("CREATE INDEX idx_tx_history_from ON transaction_history(from_addr)")
            cursor.execute("CREATE INDEX idx_tx_history_to ON transaction_history(to_addr)")
            cursor.execute("CREATE INDEX idx_tx_history_block ON transaction_history(block_height)")
            cursor.execute("CREATE INDEX idx_attest_history_miner ON miner_attest_history(miner)")
            cursor.execute("CREATE INDEX idx_blocks_hash ON blocks(block_hash)")

            # Insert metadata
            cursor.execute("""
                INSERT INTO chain_metadata (key, value, updated_at) VALUES
                ('version', ?, ?),
                ('genesis_timestamp', ?, ?),
                ('network', 'mainnet', ?),
                ('migration_date', ?, ?)
            """, (
                MIGRATION_VERSION, int(time.time()),
                str(GENESIS_TIMESTAMP), int(time.time()),
                int(time.time()),
                datetime.now().isoformat(), int(time.time())
            ))

            conn.commit()

        self.log("Mainnet schema created successfully")

    def migrate_attestation_history(self):
        """Migrate attestation history from testnet"""
        if not PRESERVE_ATTESTATION_HISTORY:
            self.log("Skipping attestation history migration (disabled)")
            return

        self.log("Migrating attestation history...")

        try:
            with sqlite3.connect(self.testnet_db) as testnet_conn:
                testnet_conn.row_factory = sqlite3.Row
                cursor = testnet_conn.cursor()

                # Get attestation history
                cursor.execute("""
                    SELECT miner, device_arch, device_family, ts_ok
                    FROM miner_attest_recent
                """)
                attestations = cursor.fetchall()

            with sqlite3.connect(self.mainnet_db) as mainnet_conn:
                cursor = mainnet_conn.cursor()

                for att in attestations:
                    cursor.execute("""
                        INSERT INTO miner_attest_recent
                        (miner, device_arch, device_family, ts_ok)
                        VALUES (?, ?, ?, ?)
                    """, (att["miner"], att["device_arch"], att["device_family"], att["ts_ok"]))

                mainnet_conn.commit()

            self.log(f"Migrated {len(attestations)} attestation records")

        except Exception as e:
            self.log(f"Attestation migration failed: {e}", "ERROR")

    def initialize_premine(self, wallet_addresses: Dict[str, str] = None) -> Dict:
        """Initialize premine allocations"""
        self.log("Initializing premine allocations...")

        manager = PremineManager(self.mainnet_db, GENESIS_TIMESTAMP)
        result = manager.initialize_premine(wallet_addresses)

        self.log(f"Total premine: {TOTAL_PREMINE_RTC:,} RTC")
        self.log(f"Allocations created: {len(result['allocations'])}")

        for alloc in result['allocations']:
            self.log(f"  {alloc['name']}: {alloc['amount_rtc']:,} RTC -> {alloc['wallet'][:20]}...")

        return result

    def create_genesis_block(self) -> Dict:
        """Create genesis block"""
        self.log("Creating genesis block...")

        # Genesis block data
        genesis = {
            "height": 0,
            "block_hash": "0" * 64,  # Will be computed
            "prev_hash": "0" * 64,
            "timestamp": GENESIS_TIMESTAMP * 1000,
            "merkle_root": "0" * 64,
            "state_root": "0" * 64,
            "attestations_hash": "0" * 64,
            "producer": "genesis",
            "producer_sig": "0" * 128,
            "tx_count": 0,
            "attestation_count": 0,
            "body_json": json.dumps({
                "transactions": [],
                "attestations": [],
                "premine": {
                    "total_rtc": TOTAL_PREMINE_RTC,
                    "allocations": list(FOUNDER_ALLOCATIONS.keys())
                }
            })
        }

        # Compute genesis hash
        genesis_data = canonical_json({
            "height": genesis["height"],
            "prev_hash": genesis["prev_hash"],
            "timestamp": genesis["timestamp"],
            "merkle_root": genesis["merkle_root"],
            "producer": genesis["producer"]
        })
        genesis["block_hash"] = blake2b256_hex(genesis_data)

        with sqlite3.connect(self.mainnet_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO blocks
                (height, block_hash, prev_hash, timestamp, merkle_root, state_root,
                 attestations_hash, producer, producer_sig, tx_count, attestation_count,
                 body_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                genesis["height"],
                genesis["block_hash"],
                genesis["prev_hash"],
                genesis["timestamp"],
                genesis["merkle_root"],
                genesis["state_root"],
                genesis["attestations_hash"],
                genesis["producer"],
                genesis["producer_sig"],
                genesis["tx_count"],
                genesis["attestation_count"],
                genesis["body_json"],
                int(time.time())
            ))
            conn.commit()

        self.log(f"Genesis block created: {genesis['block_hash'][:16]}...")
        return genesis

    def verify_migration(self) -> bool:
        """Verify migration was successful"""
        self.log("=" * 60)
        self.log("VERIFICATION")
        self.log("=" * 60)

        try:
            with sqlite3.connect(self.mainnet_db) as conn:
                cursor = conn.cursor()

                # Check genesis block
                cursor.execute("SELECT block_hash FROM blocks WHERE height = 0")
                genesis = cursor.fetchone()
                if not genesis:
                    self.log("Genesis block not found", "ERROR")
                    return False
                self.log(f"Genesis block: {genesis[0][:16]}...")

                # Check premine
                cursor.execute("SELECT COUNT(*), SUM(total_urtc) FROM premine_allocations")
                premine = cursor.fetchone()
                expected_premine = TOTAL_PREMINE_RTC * 100_000_000
                if premine[1] != expected_premine:
                    self.log(f"Premine mismatch: {premine[1]} != {expected_premine}", "ERROR")
                    return False
                self.log(f"Premine allocations: {premine[0]}, Total: {premine[1] / 100_000_000:,.0f} RTC")

                # Check balances
                cursor.execute("SELECT COUNT(*), SUM(balance_urtc) FROM balances")
                balances = cursor.fetchone()
                self.log(f"Wallet count: {balances[0]}, Total balance: {(balances[1] or 0) / 100_000_000:,.2f} RTC")

                # Check chain metadata
                cursor.execute("SELECT key, value FROM chain_metadata")
                metadata = dict(cursor.fetchall())
                self.log(f"Chain version: {metadata.get('version', 'unknown')}")
                self.log(f"Network: {metadata.get('network', 'unknown')}")

        except Exception as e:
            self.log(f"Verification failed: {e}", "ERROR")
            return False

        if self.errors:
            self.log(f"Migration completed with {len(self.errors)} errors", "WARNING")
            return False

        self.log("Verification PASSED")
        return True

    def run(self, wallet_addresses: Dict[str, str] = None) -> Dict:
        """
        Run full migration process.

        Args:
            wallet_addresses: Optional dict mapping allocation_id to existing wallet addresses.
                            If not provided, new wallets will be generated.

        Returns:
            Migration result including any generated wallets
        """
        self.log("=" * 60)
        self.log("RUSTCHAIN TESTNET -> MAINNET MIGRATION")
        self.log(f"Version: {MIGRATION_VERSION}")
        self.log(f"Started: {datetime.now().isoformat()}")
        self.log("=" * 60)

        result = {
            "success": False,
            "version": MIGRATION_VERSION,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "backup_path": None,
            "genesis_hash": None,
            "premine": None,
            "errors": []
        }

        try:
            # Step 1: Pre-flight checks
            if not self.pre_flight_checks():
                result["errors"] = self.errors
                return result

            # Step 2: Backup
            result["backup_path"] = self.create_backup()

            # Step 3: Create mainnet schema
            self.create_mainnet_schema()

            # Step 4: Migrate attestation history
            self.migrate_attestation_history()

            # Step 5: Initialize premine
            premine_result = self.initialize_premine(wallet_addresses)
            result["premine"] = premine_result

            # Step 6: Create genesis block
            genesis = self.create_genesis_block()
            result["genesis_hash"] = genesis["block_hash"]

            # Step 7: Verify
            if self.verify_migration():
                result["success"] = True
                self.log("=" * 60)
                self.log("MIGRATION COMPLETED SUCCESSFULLY")
                self.log("=" * 60)
            else:
                result["errors"] = self.errors

        except Exception as e:
            self.log(f"Migration failed: {e}", "ERROR")
            result["errors"] = self.errors + [str(e)]

        result["completed_at"] = datetime.now().isoformat()
        result["log"] = self.migration_log

        # Save migration log
        log_path = os.path.join(self.backup_dir, f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(log_path, 'w') as f:
            json.dump(result, f, indent=2)
        self.log(f"Migration log saved: {log_path}")

        return result


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Testnet -> Mainnet Migration")
    parser.add_argument("--testnet-db", default=TESTNET_DB_PATH, help="Testnet database path")
    parser.add_argument("--mainnet-db", default=MAINNET_DB_PATH, help="Mainnet database path")
    parser.add_argument("--backup-dir", default=BACKUP_DIR, help="Backup directory")
    parser.add_argument("--wallets-file", help="JSON file with existing wallet addresses")
    parser.add_argument("--dry-run", action="store_true", help="Run validation only")

    args = parser.parse_args()

    # Load wallet addresses if provided
    wallet_addresses = None
    if args.wallets_file and os.path.exists(args.wallets_file):
        with open(args.wallets_file) as f:
            wallet_addresses = json.load(f)
        print(f"Loaded {len(wallet_addresses)} wallet addresses")

    # Create migration instance
    migration = RustChainMigration(
        testnet_db=args.testnet_db,
        mainnet_db=args.mainnet_db,
        backup_dir=args.backup_dir
    )

    if args.dry_run:
        print("DRY RUN - Validation only")
        success = migration.pre_flight_checks()
        sys.exit(0 if success else 1)

    # Run migration
    result = migration.run(wallet_addresses)

    # Print summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"Success: {result['success']}")
    print(f"Genesis Hash: {result.get('genesis_hash', 'N/A')}")
    print(f"Backup: {result.get('backup_path', 'N/A')}")

    if result.get('premine', {}).get('generated_wallets'):
        print("\nGENERATED WALLETS (SAVE THESE SECURELY!):")
        for alloc_id, wallet in result['premine']['generated_wallets'].items():
            print(f"\n{alloc_id}:")
            print(f"  Address: {wallet['address']}")
            print(f"  Private Key: {wallet['private_key']}")

    if result.get('errors'):
        print(f"\nErrors: {len(result['errors'])}")
        for err in result['errors']:
            print(f"  - {err}")

    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()
