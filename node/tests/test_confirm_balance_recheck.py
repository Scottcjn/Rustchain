"""
Test: confirm_transaction() must re-check sender balance before deduction.

Regression test for negative-balance minting: if a sender's balance drops
between submit_transaction() and confirm_transaction() (e.g. due to another
confirmed tx in the same block, or direct DB mutation), confirm_transaction()
must reject the confirmation rather than creating a negative balance.
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

# Mock rustchain_crypto so we can import rustchain_tx_handler without the real lib
mock = types.ModuleType("rustchain_crypto")


class FakeSignedTransaction:
    def __init__(self, from_addr, to_addr, amount_urtc, nonce=1, tx_hash=None):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount_urtc = amount_urtc
        self.nonce = nonce
        self.timestamp = 1234567890
        self.memo = "test"
        self.signature = "sig"
        self.public_key = "00"
        self.tx_hash = tx_hash or f"tx-{amount_urtc}-{nonce}"

    def verify(self):
        return True


class FakeEd25519Signer:
    pass


def blake2b256_hex(x):
    return "00" * 32


def address_from_public_key(b: bytes) -> str:
    return "addr-from-pub"


mock.SignedTransaction = FakeSignedTransaction
mock.Ed25519Signer = FakeEd25519Signer
mock.blake2b256_hex = blake2b256_hex
mock.address_from_public_key = address_from_public_key
sys.modules["rustchain_crypto"] = mock

import rustchain_tx_handler as txh


class TestConfirmBalanceRecheck(unittest.TestCase):
    """confirm_transaction() must not allow negative sender balances."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        # Pre-create balances table with OLD schema (no CHECK constraint) so
        # the TransactionPool migration can detect and upgrade it.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS balances "
                "(wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL, wallet_nonce INTEGER DEFAULT 0)"
            )
            conn.execute(
                "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                ("addr-sender", 1_000_000, 0),
            )
            conn.execute(
                "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                ("addr-receiver", 0, 0),
            )
        # Now create the pool — migration should add CHECK constraint
        self.pool = txh.TransactionPool(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def _insert_pending(self, tx_hash, from_addr, to_addr, amount_urtc, nonce=1):
        """Helper: insert a pending transaction directly into DB."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO pending_transactions
                   (tx_hash, from_addr, to_addr, amount_urtc, nonce,
                    timestamp, memo, signature, public_key, created_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (
                    tx_hash,
                    from_addr,
                    to_addr,
                    amount_urtc,
                    nonce,
                    1234567890,
                    "test",
                    "sig",
                    "00",
                    1234567890,
                ),
            )

    def test_confirm_rejects_when_balance_insufficient(self):
        """If sender balance is drained before confirm, confirmation must fail."""
        # Insert a pending tx for 500_000 (sender has 1_000_000 — should pass normally)
        self._insert_pending("tx-normal", "addr-sender", "addr-receiver", 500_000)

        # Drain sender's balance to 100_000 (less than the pending tx amount)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE balances SET balance_urtc = ? WHERE wallet = ?",
                (100_000, "addr-sender"),
            )

        # Confirm should FAIL — balance re-check catches insufficient funds
        result = self.pool.confirm_transaction("tx-normal", 100, "blockhash")
        self.assertFalse(result)

        # Sender balance should be unchanged
        balance = self.pool.get_balance("addr-sender")
        self.assertEqual(balance, 100_000)

    def test_confirm_succeeds_when_balance_sufficient(self):
        """Normal confirmation path still works."""
        self._insert_pending("tx-ok", "addr-sender", "addr-receiver", 500_000)

        result = self.pool.confirm_transaction("tx-ok", 100, "blockhash")
        self.assertTrue(result)

        # Balances should be updated correctly
        self.assertEqual(self.pool.get_balance("addr-sender"), 500_000)
        self.assertEqual(self.pool.get_balance("addr-receiver"), 500_000)

    def test_confirm_rejects_exact_balance(self):
        """Confirming for exactly the sender's balance should succeed (balance goes to 0)."""
        self._insert_pending("tx-exact", "addr-sender", "addr-receiver", 1_000_000)

        result = self.pool.confirm_transaction("tx-exact", 100, "blockhash")
        self.assertTrue(result)
        self.assertEqual(self.pool.get_balance("addr-sender"), 0)

    def test_confirm_rejects_unknown_sender(self):
        """If sender has no balance row at all, confirm must fail."""
        self._insert_pending("tx-ghost", "addr-unknown", "addr-receiver", 100)

        result = self.pool.confirm_transaction("tx-ghost", 100, "blockhash")
        self.assertFalse(result)

    def test_check_constraint_prevents_negative_balance(self):
        """The CHECK(balance_urtc >= 0) constraint should reject negative inserts."""
        # After migration, the balances table should have the CHECK constraint.
        # Try to directly insert a negative balance — should fail.
        with sqlite3.connect(self.db_path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                    ("addr-negative", -1, 0),
                )


if __name__ == "__main__":
    unittest.main()
