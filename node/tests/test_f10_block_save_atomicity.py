"""
F10: Block save / transaction confirmation must be atomic.

Tests that save_block + confirm_transaction share a single DB connection
so that a crash or failure cannot partially confirm transactions.
"""

import os
import sqlite3
import sys
import tempfile
import types
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

# Stub rustchain_crypto module
mock = types.ModuleType("rustchain_crypto")


class SignedTransaction:
    def __init__(
        self,
        from_addr="",
        to_addr="",
        amount_urtc=0,
        nonce=0,
        timestamp=0,
        memo="",
        signature="",
        public_key="",
        tx_hash="",
    ):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount_urtc = amount_urtc
        self.nonce = nonce
        self.timestamp = timestamp
        self.memo = memo
        self.signature = signature
        self.public_key = public_key
        self.tx_hash = tx_hash

    def verify(self):
        return True


class Ed25519Signer:
    pass


def blake2b256_hex(x):
    return "00" * 32


def address_from_public_key(b):
    return "addr-from-pub"


mock.SignedTransaction = SignedTransaction
mock.Ed25519Signer = Ed25519Signer
mock.blake2b256_hex = blake2b256_hex
mock.address_from_public_key = address_from_public_key
sys.modules["rustchain_crypto"] = mock

import rustchain_tx_handler as txh


class TestConfirmTransactionAtomicity(unittest.TestCase):
    """Test that confirm_transaction can share a connection with save_block."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        # Create the balances table BEFORE TransactionPool init so
        # _ensure_schema can find it and apply migrations.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS balances "
                "(wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL, "
                "wallet_nonce INTEGER DEFAULT 0)"
            )
        self.pool = txh.TransactionPool(self.db_path)
        # Seed balances
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)", ("alice", 10_000, 0)
            )
            conn.execute("INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)", ("bob", 0, 0))

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def _seed_pending(self, tx_hash, from_addr, to_addr, amount, nonce):
        """Insert a pending transaction directly into the DB."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO pending_transactions "
                "(tx_hash, from_addr, to_addr, amount_urtc, nonce, timestamp, "
                "memo, signature, public_key, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (tx_hash, from_addr, to_addr, amount, nonce, 1000, "", "sig", "pk", 1000),
            )

    def test_confirm_with_shared_connection_succeeds(self):
        """When a shared connection is passed, confirmation succeeds and
        changes are visible on that connection."""
        self._seed_pending("tx1", "alice", "bob", 1_000, 1)

        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE")
        ok = self.pool.confirm_transaction("tx1", 1, "hash1", conn=conn)
        self.assertTrue(ok)

        # Verify changes are visible on the same connection (before commit)
        row = conn.execute("SELECT balance_urtc FROM balances WHERE wallet = ?", ("bob",)).fetchone()
        self.assertEqual(row[0], 1_000)

        conn.commit()
        conn.close()

        # Verify persisted after commit
        with sqlite3.connect(self.db_path) as conn2:
            row = conn2.execute("SELECT balance_urtc FROM balances WHERE wallet = ?", ("bob",)).fetchone()
            self.assertEqual(row[0], 1_000)
            # Pending should be gone
            row2 = conn2.execute("SELECT COUNT(*) FROM pending_transactions WHERE tx_hash = ?", ("tx1",)).fetchone()
            self.assertEqual(row2[0], 0)

    def test_confirm_rollback_on_shared_connection(self):
        """If confirm_transaction is called on a shared connection but the
        caller rolls back, all changes are reverted."""
        self._seed_pending("tx2", "alice", "bob", 2_000, 1)

        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE")
        ok = self.pool.confirm_transaction("tx2", 1, "hash2", conn=conn)
        self.assertTrue(ok)

        # Rollback instead of commit
        conn.rollback()
        conn.close()

        # State should be unchanged
        with sqlite3.connect(self.db_path) as conn2:
            row = conn2.execute("SELECT balance_urtc FROM balances WHERE wallet = ?", ("bob",)).fetchone()
            self.assertEqual(row[0], 0)  # bob still has 0
            # Pending should still exist
            row2 = conn2.execute("SELECT COUNT(*) FROM pending_transactions WHERE tx_hash = ?", ("tx2",)).fetchone()
            self.assertEqual(row2[0], 1)

    def test_confirm_fails_insufficient_balance_shared_conn(self):
        """Confirm fails when balance is insufficient, even on shared conn."""
        self._seed_pending("tx3", "alice", "bob", 99_999, 1)

        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE")
        ok = self.pool.confirm_transaction("tx3", 1, "hash3", conn=conn)
        self.assertFalse(ok)

        conn.commit()
        conn.close()

        # Nothing should have changed
        with sqlite3.connect(self.db_path) as conn2:
            row = conn2.execute("SELECT balance_urtc FROM balances WHERE wallet = ?", ("alice",)).fetchone()
            self.assertEqual(row[0], 10_000)
            row2 = conn2.execute("SELECT COUNT(*) FROM pending_transactions WHERE tx_hash = ?", ("tx3",)).fetchone()
            self.assertEqual(row2[0], 1)

    def test_standalone_confirm_still_works(self):
        """Legacy standalone confirm (no shared conn) still works."""
        self._seed_pending("tx4", "alice", "bob", 500, 1)

        ok = self.pool.confirm_transaction("tx4", 1, "hash4")
        self.assertTrue(ok)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT balance_urtc FROM balances WHERE wallet = ?", ("bob",)).fetchone()
            self.assertEqual(row[0], 500)

    def test_multi_tx_atomic_on_shared_conn(self):
        """Multiple confirmations on the same shared connection are atomic:
        if the caller rolls back, none are applied."""
        self._seed_pending("txA", "alice", "bob", 1_000, 1)
        self._seed_pending("txB", "alice", "bob", 2_000, 2)

        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE")
        ok_a = self.pool.confirm_transaction("txA", 1, "hashA", conn=conn)
        ok_b = self.pool.confirm_transaction("txB", 1, "hashB", conn=conn)
        self.assertTrue(ok_a)
        self.assertTrue(ok_b)

        # Rollback everything
        conn.rollback()
        conn.close()

        with sqlite3.connect(self.db_path) as conn2:
            row = conn2.execute("SELECT balance_urtc FROM balances WHERE wallet = ?", ("bob",)).fetchone()
            self.assertEqual(row[0], 0)


if __name__ == "__main__":
    unittest.main()
