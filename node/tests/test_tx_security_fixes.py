"""
Tests for security fixes #2017, #2018, #2019.

TX-001: Double-spend via concurrent pending submissions (TOCTOU)
TX-002: Balance underflow on concurrent transaction confirmation
TX-003: Pending pool DoS via mass submissions
"""

import os
import sqlite3
import sys
import tempfile
import threading
import types
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

mock = types.ModuleType("rustchain_crypto")
class SignedTransaction: pass
class Ed25519Signer: pass
def blake2b256_hex(x): return "00" * 32
def address_from_public_key(b: bytes) -> str: return "addr-from-pub"
mock.SignedTransaction = SignedTransaction
mock.Ed25519Signer = Ed25519Signer
mock.blake2b256_hex = blake2b256_hex
mock.address_from_public_key = address_from_public_key
sys.modules["rustchain_crypto"] = mock

import rustchain_tx_handler as txh


class FakeTx:
    def __init__(self, amount_urtc, nonce=1, tx_hash=None, from_addr="addr-from-pub"):
        self.from_addr = from_addr
        self.to_addr = "addr-target"
        self.amount_urtc = amount_urtc
        self.nonce = nonce
        self.timestamp = 1234567890
        self.memo = "test"
        self.signature = "sig"
        self.public_key = "00"
        self.tx_hash = tx_hash or f"tx-{from_addr}-{nonce}-{amount_urtc}"

    def verify(self):
        return True


class TxSecurityTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        # Create balances table BEFORE pool init so schema/triggers work
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS balances "
                "(wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL, wallet_nonce INTEGER DEFAULT 0)"
            )
        self.pool = txh.TransactionPool(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def seed_balance(self, address, amount_urtc, nonce=0):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                (address, amount_urtc, nonce)
            )


class TestDoubleSpendConcurrent(TxSecurityTestBase):
    """TX-001 (#2017): Concurrent submissions with same nonce must not both succeed."""

    def test_double_spend_concurrent(self):
        self.seed_balance("addr-from-pub", 10_000_000_000)  # 100 RTC

        results = []
        barrier = threading.Barrier(2)

        def submit(tx):
            barrier.wait()
            ok, msg = self.pool.submit_transaction(tx)
            results.append((ok, msg))

        tx_a = FakeTx(5_000_000_000, nonce=1, tx_hash="tx-a")
        tx_b = FakeTx(5_000_000_000, nonce=1, tx_hash="tx-b")

        t1 = threading.Thread(target=submit, args=(tx_a,))
        t2 = threading.Thread(target=submit, args=(tx_b,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0]]
        self.assertEqual(len(successes), 1, f"Expected exactly 1 success, got {len(successes)}: {results}")


class TestConfirmRejectsInsufficientBalance(TxSecurityTestBase):
    """TX-002 (#2018): Confirming a tx when balance is insufficient must fail."""

    def test_confirm_rejects_insufficient_balance(self):
        # Balance allows both txs to be submitted (available balance check
        # accounts for pending amounts), but after confirming tx1 the actual
        # balance is too low to confirm tx2.
        self.seed_balance("addr-from-pub", 5_000_000_000)  # 50 RTC

        tx1 = FakeTx(3_000_000_000, nonce=1, tx_hash="tx-confirm-1")
        tx2 = FakeTx(2_000_000_000, nonce=2, tx_hash="tx-confirm-2")

        ok1, _ = self.pool.submit_transaction(tx1)
        self.assertTrue(ok1)
        ok2, _ = self.pool.submit_transaction(tx2)
        self.assertTrue(ok2)

        # Confirm first - should succeed
        result1 = self.pool.confirm_transaction("tx-confirm-1", 100, "block100")
        self.assertTrue(result1)

        # Now manually lower balance to simulate concurrent deduction
        # (balance is now 2B after tx1; set to 1B to ensure tx2 fails)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE balances SET balance_urtc = ? WHERE wallet = ?",
                (1_000_000_000, "addr-from-pub")
            )

        # Confirm second - should fail (balance 1B < 2B needed)
        result2 = self.pool.confirm_transaction("tx-confirm-2", 101, "block101")
        self.assertFalse(result2)


class TestPendingLimitPerAddress(TxSecurityTestBase):
    """TX-003 (#2019): Per-address pending limit must be enforced."""

    def test_pending_limit_per_address(self):
        self.seed_balance("addr-from-pub", 100_000_000_000_000)  # huge balance

        max_pending = txh.MAX_PENDING_PER_ADDRESS

        # Submit up to the limit
        for i in range(1, max_pending + 1):
            tx = FakeTx(txh.MIN_TX_AMOUNT_URTC, nonce=i, tx_hash=f"tx-limit-{i}")
            ok, msg = self.pool.submit_transaction(tx)
            self.assertTrue(ok, f"TX {i} should succeed: {msg}")

        # One more should be rejected
        tx_over = FakeTx(txh.MIN_TX_AMOUNT_URTC, nonce=max_pending + 1, tx_hash=f"tx-limit-over")
        ok, msg = self.pool.submit_transaction(tx_over)
        self.assertFalse(ok)
        self.assertIn("Pending limit exceeded", msg)


class TestMinimumTxAmount(TxSecurityTestBase):
    """TX-003 (#2019): Transactions below MIN_TX_AMOUNT_URTC must be rejected."""

    def test_minimum_tx_amount(self):
        self.seed_balance("addr-from-pub", 100_000_000_000)

        tx = FakeTx(txh.MIN_TX_AMOUNT_URTC - 1, nonce=1, tx_hash="tx-tiny")
        ok, msg = self.pool.submit_transaction(tx)
        self.assertFalse(ok)
        self.assertIn("amount", msg.lower())

    def test_exact_minimum_succeeds(self):
        self.seed_balance("addr-from-pub", 100_000_000_000)

        tx = FakeTx(txh.MIN_TX_AMOUNT_URTC, nonce=1, tx_hash="tx-min")
        ok, msg = self.pool.submit_transaction(tx)
        self.assertTrue(ok, f"Exact minimum should succeed: {msg}")


class TestBalanceCannotGoNegative(TxSecurityTestBase):
    """TX-002 (#2018): CHECK constraint prevents negative balance."""

    def test_balance_cannot_go_negative(self):
        self.seed_balance("addr-from-pub", 1_000_000_000)  # 10 RTC

        # Try to force a negative balance via raw SQL (simulates the bug)
        with self.assertRaises(sqlite3.IntegrityError):
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                # The CHECK constraint should prevent this
                conn.execute(
                    "UPDATE balances SET balance_urtc = -1 WHERE wallet = ?",
                    ("addr-from-pub",)
                )


if __name__ == "__main__":
    unittest.main()
