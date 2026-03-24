#!/usr/bin/env python3
"""
RustChain Transaction Handler - Mainnet Security
=================================================

Phase 1 Implementation:
- Signed transaction validation
- Replay protection via nonces
- Balance checking with proper locking
- Transaction pool management

All transactions MUST be signed with Ed25519.
"""

import sqlite3
import time
import threading
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from contextlib import contextmanager

from rustchain_crypto import (
    SignedTransaction,
    Ed25519Signer,
    blake2b256_hex,
    address_from_public_key
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [TX] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE SCHEMA UPGRADES
# =============================================================================

SCHEMA_UPGRADE_SQL = """
-- Upgrade balances table to include nonce
ALTER TABLE balances ADD COLUMN wallet_nonce INTEGER DEFAULT 0;

-- Create pending transactions table
CREATE TABLE IF NOT EXISTS pending_transactions (
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
);

-- Create transaction history table
CREATE TABLE IF NOT EXISTS transaction_history (
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
);

-- Create wallet public key registry
CREATE TABLE IF NOT EXISTS wallet_pubkeys (
    address TEXT PRIMARY KEY,
    public_key TEXT NOT NULL,
    registered_at INTEGER NOT NULL
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_pending_from ON pending_transactions(from_addr);
CREATE INDEX IF NOT EXISTS idx_pending_nonce ON pending_transactions(from_addr, nonce);
CREATE INDEX IF NOT EXISTS idx_history_from ON transaction_history(from_addr);
CREATE INDEX IF NOT EXISTS idx_history_to ON transaction_history(to_addr);
CREATE INDEX IF NOT EXISTS idx_history_block ON transaction_history(block_height);
"""


# =============================================================================
# TRANSACTION POOL
# =============================================================================

class TransactionPool:
    """
    Manages pending transactions with proper validation.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure database schema is up to date"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if wallet_nonce column exists
            cursor.execute("PRAGMA table_info(balances)")
            columns = [col[1] for col in cursor.fetchall()]

            if "wallet_nonce" not in columns:
                try:
                    cursor.execute("ALTER TABLE balances ADD COLUMN wallet_nonce INTEGER DEFAULT 0")
                    logger.info("Added wallet_nonce column to balances table")
                except sqlite3.OperationalError:
                    pass  # Column might already exist

            # Create other tables
            for statement in SCHEMA_UPGRADE_SQL.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('ALTER'):
                    try:
                        cursor.execute(statement)
                    except sqlite3.OperationalError as e:
                        if "already exists" not in str(e):
                            logger.warning(f"Schema statement failed: {e}")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper locking"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_wallet_nonce(self, address: str) -> int:
        """Get current nonce for a wallet"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT wallet_nonce FROM balances WHERE wallet = ?",
                (address,)
            )
            result = cursor.fetchone()
            return result["wallet_nonce"] if result else 0

    def get_balance(self, address: str) -> int:
        """Get current balance for a wallet (in uRTC)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT balance_urtc FROM balances WHERE wallet = ?",
                (address,)
            )
            result = cursor.fetchone()
            return result["balance_urtc"] if result else 0

    def get_pending_amount(self, address: str) -> int:
        """Get total pending outgoing amount for address"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT COALESCE(SUM(amount_urtc), 0) as pending
                   FROM pending_transactions
                   WHERE from_addr = ? AND status = 'pending'""",
                (address,)
            )
            result = cursor.fetchone()
            return result["pending"] if result else 0

    def get_available_balance(self, address: str) -> int:
        """Get available balance (total - pending)"""
        balance = self.get_balance(address)
        pending = self.get_pending_amount(address)
        return max(0, balance - pending)

    def register_public_key(self, address: str, public_key: str) -> bool:
        """Register a wallet's public key"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Verify address derives from public key
            derived_addr = address_from_public_key(bytes.fromhex(public_key))
            if derived_addr != address:
                logger.warning(f"Address mismatch: {address} != {derived_addr}")
                return False

            try:
                cursor.execute(
                    """INSERT OR REPLACE INTO wallet_pubkeys
                       (address, public_key, registered_at)
                       VALUES (?, ?, ?)""",
                    (address, public_key, int(time.time()))
                )
                return True
            except Exception as e:
                logger.error(f"Failed to register public key: {e}")
                return False

    def get_public_key(self, address: str) -> Optional[str]:
        """Get registered public key for address"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT public_key FROM wallet_pubkeys WHERE address = ?",
                (address,)
            )
            result = cursor.fetchone()
            return result["public_key"] if result else None

    def validate_transaction(self, tx: SignedTransaction) -> Tuple[bool, str]:
        """
        Validate a signed transaction.

        Checks:
        1. Signature validity
        2. Public key matches from_addr
        3. Nonce is correct (replay protection)
        4. Sufficient balance
        5. No duplicate in pool
        """
        # 1. Verify signature
        if not tx.verify():
            return False, "Invalid signature"

        # 2. Verify public key matches address
        derived_addr = address_from_public_key(bytes.fromhex(tx.public_key))
        if derived_addr != tx.from_addr:
            return False, f"Public key does not match from_addr"

        # 3. Check nonce
        expected_nonce = self.get_wallet_nonce(tx.from_addr) + 1
        pending_nonces = self._get_pending_nonces(tx.from_addr)

        # Account for pending transactions
        while expected_nonce in pending_nonces:
            expected_nonce += 1

        if tx.nonce != expected_nonce:
            return False, f"Invalid nonce: expected {expected_nonce}, got {tx.nonce}"

        # 4. Validate amount and check balance
        if tx.amount_urtc <= 0:
            return False, "Invalid amount: must be > 0"

        available = self.get_available_balance(tx.from_addr)
        if tx.amount_urtc > available:
            return False, f"Insufficient balance: have {available}, need {tx.amount_urtc}"

        # 5. Check for duplicate
        if self._tx_exists(tx.tx_hash):
            return False, "Transaction already exists"

        return True, ""

    def _get_pending_nonces(self, address: str) -> set:
        """Get set of pending nonces for address"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT nonce FROM pending_transactions WHERE from_addr = ? AND status = 'pending'",
                (address,)
            )
            return {row["nonce"] for row in cursor.fetchall()}

    def _tx_exists(self, tx_hash: str) -> bool:
        """Check if transaction already exists"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check pending
            cursor.execute(
                "SELECT 1 FROM pending_transactions WHERE tx_hash = ?",
                (tx_hash,)
            )
            if cursor.fetchone():
                return True

            # Check history
            cursor.execute(
                "SELECT 1 FROM transaction_history WHERE tx_hash = ?",
                (tx_hash,)
            )
            return cursor.fetchone() is not None

    def submit_transaction(self, tx: SignedTransaction) -> Tuple[bool, str]:
        """
        Submit a signed transaction to the pool.

        Returns (success, error_or_tx_hash)
        """
        # Validate
        is_valid, error = self.validate_transaction(tx)
        if not is_valid:
            return False, error

        # Register public key if not already registered
        self.register_public_key(tx.from_addr, tx.public_key)

        # Add to pending pool
        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """INSERT INTO pending_transactions
                       (tx_hash, from_addr, to_addr, amount_urtc, nonce,
                        timestamp, memo, signature, public_key, created_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (
                        tx.tx_hash,
                        tx.from_addr,
                        tx.to_addr,
                        tx.amount_urtc,
                        tx.nonce,
                        tx.timestamp,
                        tx.memo,
                        tx.signature,
                        tx.public_key,
                        int(time.time())
                    )
                )

                logger.info(f"TX accepted: {tx.tx_hash[:16]}... "
                           f"{tx.from_addr[:16]}... -> {tx.to_addr[:16]}... "
                           f"amount={tx.amount_urtc}")

                return True, tx.tx_hash

            except sqlite3.IntegrityError as e:
                return False, f"Transaction already exists: {e}"

    def get_pending_transactions(self, limit: int = 100) -> List[SignedTransaction]:
        """Get pending transactions ordered by nonce"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM pending_transactions
                   WHERE status = 'pending'
                   ORDER BY nonce ASC
                   LIMIT ?""",
                (limit,)
            )

            return [
                SignedTransaction(
                    from_addr=row["from_addr"],
                    to_addr=row["to_addr"],
                    amount_urtc=row["amount_urtc"],
                    nonce=row["nonce"],
                    timestamp=row["timestamp"],
                    memo=row["memo"],
                    signature=row["signature"],
                    public_key=row["public_key"],
                    tx_hash=row["tx_hash"]
                )
                for row in cursor.fetchall()
            ]

    def confirm_transaction(
        self,
        tx_hash: str,
        block_height: int,
        block_hash: str
    ) -> bool:
        """
        Confirm a transaction (move from pending to history).
        Also updates balances and nonces.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get pending transaction
            cursor.execute(
                "SELECT * FROM pending_transactions WHERE tx_hash = ?",
                (tx_hash,)
            )
            row = cursor.fetchone()

            if not row:
                logger.warning(f"Transaction not found in pending: {tx_hash}")
                return False

            try:
                # Move to history
                cursor.execute(
                    """INSERT INTO transaction_history
                       (tx_hash, from_addr, to_addr, amount_urtc, nonce,
                        timestamp, memo, signature, public_key,
                        block_height, block_hash, confirmed_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')""",
                    (
                        row["tx_hash"],
                        row["from_addr"],
                        row["to_addr"],
                        row["amount_urtc"],
                        row["nonce"],
                        row["timestamp"],
                        row["memo"],
                        row["signature"],
                        row["public_key"],
                        block_height,
                        block_hash,
                        int(time.time())
                    )
                )

                # Update sender balance and nonce
                cursor.execute(
                    """UPDATE balances
                       SET balance_urtc = balance_urtc - ?,
                           wallet_nonce = ?
                       WHERE wallet = ?""",
                    (row["amount_urtc"], row["nonce"], row["from_addr"])
                )

                # Update receiver balance (create if not exists)
                cursor.execute(
                    """INSERT INTO balances (wallet, balance_urtc, wallet_nonce)
                       VALUES (?, ?, 0)
                       ON CONFLICT(wallet) DO UPDATE SET
                       balance_urtc = balance_urtc + ?""",
                    (row["to_addr"], row["amount_urtc"], row["amount_urtc"])
                )

                # Remove from pending
                cursor.execute(
                    "DELETE FROM pending_transactions WHERE tx_hash = ?",
                    (tx_hash,)
                )

                logger.info(f"TX confirmed: {tx_hash[:16]}... in block {block_height}")
                return True

            except Exception as e:
                logger.error(f"Failed to confirm transaction: {e}")
                return False

    def reject_transaction(self, tx_hash: str, reason: str = "") -> bool:
        """Reject a pending transaction"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE pending_transactions
                   SET status = 'rejected'
                   WHERE tx_hash = ?""",
                (tx_hash,)
            )

            if cursor.rowcount > 0:
                logger.info(f"TX rejected: {tx_hash[:16]}... reason: {reason}")
                return True
            return False

    def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        """Remove transactions older than max_age"""
        cutoff = int(time.time()) - max_age_seconds

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """DELETE FROM pending_transactions
                   WHERE status = 'pending' AND created_at < ?""",
                (cutoff,)
            )
            count = cursor.rowcount

            if count > 0:
                logger.info(f"Cleaned up {count} expired pending transactions")

            return count

    def get_transaction_status(self, tx_hash: str) -> Dict:
        """Get transaction status"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check pending
            cursor.execute(
                "SELECT *, 'pending' as location FROM pending_transactions WHERE tx_hash = ?",
                (tx_hash,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

            # Check history
            cursor.execute(
                "SELECT *, 'history' as location FROM transaction_history WHERE tx_hash = ?",
                (tx_hash,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

            return {"status": "not_found"}


# =============================================================================
# TRANSACTION API ENDPOINTS
# =============================================================================

def create_tx_api_routes(app, tx_pool: TransactionPool):
    """
    Create Flask routes for transaction API.

    Endpoints:
    - POST /tx/submit - Submit signed transaction
    - GET /tx/status/<hash> - Get transaction status
    - GET /tx/pending - List pending transactions
    - GET /wallet/<addr>/balance - Get wallet balance
    - GET /wallet/<addr>/nonce - Get wallet nonce
    - GET /wallet/<addr>/history - Get transaction history
    """
    from flask import request, jsonify

    @app.route('/tx/submit', methods=['POST'])
    def submit_transaction():
        """Submit a signed transaction"""
        try:
            data = request.get_json()

            if not data:
                return jsonify({"error": "No JSON data provided"}), 400

            # Create transaction object
            tx = SignedTransaction.from_dict(data)

            # Compute hash if not provided
            if not tx.tx_hash:
                tx.tx_hash = tx.compute_hash()

            # Submit to pool
            success, result = tx_pool.submit_transaction(tx)

            if success:
                return jsonify({
                    "success": True,
                    "tx_hash": result,
                    "status": "pending"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": result
                }), 400

        except Exception as e:
            logger.error(f"Error submitting transaction: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/tx/status/<tx_hash>', methods=['GET'])
    def get_tx_status(tx_hash: str):
        """Get transaction status"""
        try:
            status = tx_pool.get_transaction_status(tx_hash)
            return jsonify(status)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/tx/pending', methods=['GET'])
    def list_pending():
        """List pending transactions"""
        try:
            limit = request.args.get('limit', 100, type=int)
            pending = tx_pool.get_pending_transactions(limit)
            return jsonify({
                "count": len(pending),
                "transactions": [tx.to_dict() for tx in pending]
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/wallet/<address>/balance', methods=['GET'])
    def get_wallet_balance(address: str):
        """Get wallet balance"""
        try:
            balance = tx_pool.get_balance(address)
            available = tx_pool.get_available_balance(address)
            pending = tx_pool.get_pending_amount(address)

            return jsonify({
                "address": address,
                "balance_urtc": balance,
                "available_urtc": available,
                "pending_urtc": pending,
                "balance_rtc": balance / 100_000_000,
                "available_rtc": available / 100_000_000
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/wallet/<address>/nonce', methods=['GET'])
    def get_wallet_nonce(address: str):
        """Get wallet nonce (for transaction construction)"""
        try:
            nonce = tx_pool.get_wallet_nonce(address)
            pending_nonces = tx_pool._get_pending_nonces(address)

            # Next nonce to use
            next_nonce = nonce + 1
            while next_nonce in pending_nonces:
                next_nonce += 1

            return jsonify({
                "address": address,
                "confirmed_nonce": nonce,
                "next_nonce": next_nonce,
                "pending_nonces": sorted(pending_nonces)
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/wallet/<address>/history', methods=['GET'])
    def get_wallet_history(address: str):
        """Get transaction history for wallet"""
        try:
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)

            with sqlite3.connect(tx_pool.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    """SELECT * FROM transaction_history
                       WHERE from_addr = ? OR to_addr = ?
                       ORDER BY confirmed_at DESC
                       LIMIT ? OFFSET ?""",
                    (address, address, limit, offset)
                )

                transactions = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                "address": address,
                "count": len(transactions),
                "transactions": transactions
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import tempfile
    import os

    print("=" * 70)
    print("RustChain Transaction Handler - Test Suite")
    print("=" * 70)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        # Initialize pool
        pool = TransactionPool(db_path)

        # Create test wallet
        print("\n=== Creating Test Wallets ===")
        from rustchain_crypto import generate_wallet_keypair

        addr1, pub1, priv1 = generate_wallet_keypair()
        addr2, pub2, priv2 = generate_wallet_keypair()

        print(f"Wallet 1: {addr1}")
        print(f"Wallet 2: {addr2}")

        # Seed balance for wallet 1
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                (addr1, 1000_000_000, 0)  # 10 RTC
            )

        print(f"\nSeeded Wallet 1 with 10 RTC")

        # Check balance
        print(f"\n=== Balance Check ===")
        balance = pool.get_balance(addr1)
        nonce = pool.get_wallet_nonce(addr1)
        print(f"Wallet 1 balance: {balance / 100_000_000} RTC, nonce: {nonce}")

        # Create and sign transaction
        print("\n=== Creating Transaction ===")
        signer = Ed25519Signer(bytes.fromhex(priv1))

        tx = SignedTransaction(
            from_addr=addr1,
            to_addr=addr2,
            amount_urtc=100_000_000,  # 1 RTC
            nonce=1,
            timestamp=int(time.time() * 1000),
            memo="Test transfer"
        )
        tx.sign(signer)

        print(f"TX Hash: {tx.tx_hash}")
        print(f"Signature: {tx.signature[:32]}...")

        # Submit transaction
        print("\n=== Submitting Transaction ===")
        success, result = pool.submit_transaction(tx)
        print(f"Success: {success}")
        print(f"Result: {result}")

        # Check pending
        print("\n=== Pending Transactions ===")
        pending = pool.get_pending_transactions()
        print(f"Count: {len(pending)}")
        for p in pending:
            print(f"  {p.tx_hash[:16]}... {p.amount_urtc} uRTC")

        # Check available balance
        print("\n=== Available Balance ===")
        available = pool.get_available_balance(addr1)
        print(f"Available: {available / 100_000_000} RTC")

        # Try duplicate (should fail)
        print("\n=== Duplicate Test ===")
        success, result = pool.submit_transaction(tx)
        print(f"Duplicate result: {success}, {result}")

        # Try invalid nonce
        print("\n=== Invalid Nonce Test ===")
        tx2 = SignedTransaction(
            from_addr=addr1,
            to_addr=addr2,
            amount_urtc=50_000_000,
            nonce=5,  # Wrong nonce
            timestamp=int(time.time() * 1000)
        )
        tx2.sign(signer)
        success, result = pool.validate_transaction(tx2)
        print(f"Invalid nonce result: {success}, {result}")

        # Confirm transaction
        print("\n=== Confirming Transaction ===")
        pool.confirm_transaction(tx.tx_hash, 100, "blockhash123")

        # Check balances after confirmation
        print("\n=== Post-Confirmation Balances ===")
        bal1 = pool.get_balance(addr1)
        bal2 = pool.get_balance(addr2)
        nonce1 = pool.get_wallet_nonce(addr1)

        print(f"Wallet 1: {bal1 / 100_000_000} RTC, nonce: {nonce1}")
        print(f"Wallet 2: {bal2 / 100_000_000} RTC")

        print("\n" + "=" * 70)
        print("All tests passed!")
        print("=" * 70)

    finally:
        # Cleanup
        os.unlink(db_path)
