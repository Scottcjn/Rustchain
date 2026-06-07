"""T2.2 regression: withdrawal balance ops must be schema-tolerant.

The withdrawal money path used to read/write balances hardcoded to
(miner_pk, balance_rtc). On the live (miner_id, amount_i64) schema that read
empty -> every withdrawal falsely rejected (functional DoS). These tests exercise
the shared helpers across all three known schemas:
  A:  (miner_pk, balance_rtc)            [legacy]
  B:  (miner_id, amount_i64)             [current canonical]
  AB: (miner_id, amount_i64, miner_pk, balance_rtc)  [live, post-migration]
"""
import importlib.util
import os
import sqlite3
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
U = 1_000_000  # ACCOUNT_UNIT micro-RTC


def _schema_A(c):
    c.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)")


def _schema_B(c):
    c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0 CHECK(amount_i64>=0))")


def _schema_AB(c):
    c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0 CHECK(amount_i64>=0), miner_pk TEXT, balance_rtc REAL DEFAULT 0)")


def _seed(c, cols, wallet, rtc):
    """Seed a wallet with `rtc` RTC in whichever columns the schema has."""
    if "amount_i64" in cols and "balance_rtc" in cols:
        c.execute("INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?,?,?)", (wallet, int(rtc * U), rtc))
    elif "amount_i64" in cols:
        c.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?,?)", (wallet, int(rtc * U)))
    else:
        c.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES (?,?)", (wallet, rtc))


class WithdrawalBalanceSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ.setdefault("RUSTCHAIN_DB_PATH", os.path.join(cls._tmp.name, "w.db"))
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        spec = importlib.util.spec_from_file_location("rcnode_withdrawal_schema_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        assert cls.mod.ACCOUNT_UNIT == U

    def _fresh(self, schema_fn):
        c = sqlite3.connect(":memory:")
        schema_fn(c)
        return c, self.mod._balance_columns(c)

    def test_read_identical_across_schemas(self):
        for fn in (_schema_A, _schema_B, _schema_AB):
            c, cols = self._fresh(fn)
            _seed(c, cols, "miner-x", 5.0)
            self.assertEqual(self.mod._balance_i64_for_wallet(c, "miner-x"), 5 * U,
                             f"read mismatch on schema {sorted(cols)}")
            c.close()

    def test_debit_succeeds_on_each_schema(self):
        for fn in (_schema_A, _schema_B, _schema_AB):
            c, cols = self._fresh(fn)
            _seed(c, cols, "miner-x", 5.0)
            # withdraw 2 + 0.01 fee = 2.01 RTC
            need = int(round(2.01 * U))
            self.assertEqual(self.mod._debit_wallet_atomic(c, "miner-x", need, cols), 1,
                             f"debit should succeed on schema {sorted(cols)} (pre-fix: failed on B)")
            self.assertEqual(self.mod._balance_i64_for_wallet(c, "miner-x"), 5 * U - need)
            c.close()

    def test_overdraw_rejected_no_negative(self):
        for fn in (_schema_A, _schema_B, _schema_AB):
            c, cols = self._fresh(fn)
            _seed(c, cols, "miner-x", 1.0)
            self.assertEqual(self.mod._debit_wallet_atomic(c, "miner-x", int(5 * U), cols), 0,
                             f"overdraw must be rejected on schema {sorted(cols)}")
            self.assertEqual(self.mod._balance_i64_for_wallet(c, "miner-x"), 1 * U)  # unchanged
            c.close()

    def test_fee_credit_to_founder_community(self):
        for fn in (_schema_A, _schema_B, _schema_AB):
            c, cols = self._fresh(fn)
            fee = int(round(0.01 * U))
            self.mod._apply_wallet_balance_delta(c, "founder_community", fee, cols)
            self.assertEqual(self.mod._balance_i64_for_wallet(c, "founder_community"), fee,
                             f"fee credit failed on schema {sorted(cols)}")
            c.close()

    def test_AB_dual_column_consistency_after_debit(self):
        c, cols = self._fresh(_schema_AB)
        _seed(c, cols, "miner-x", 5.0)
        self.mod._debit_wallet_atomic(c, "miner-x", int(round(2.01 * U)), cols)
        row = c.execute("SELECT amount_i64, balance_rtc FROM balances WHERE miner_id='miner-x'").fetchone()
        self.assertEqual(row[0], 5 * U - int(round(2.01 * U)))
        self.assertAlmostEqual(row[1], row[0] / 1_000_000.0, places=6)  # both columns agree
        c.close()

    def test_legacy_float_debit_consistent_with_i64_check(self):
        """On a legacy balance_rtc schema, any balance the outer i64 check deems
        affordable must also pass the inner debit guard — they now share the integer
        micro-RTC basis, so no float round-trip mismatch can spuriously reject."""
        c, cols = self._fresh(_schema_A)
        c.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)", ("miner-x", 2.01))
        need_i64 = int(round(2.01 * U))
        self.assertGreaterEqual(self.mod._balance_i64_for_wallet(c, "miner-x"), need_i64)  # outer says affordable
        self.assertEqual(self.mod._debit_wallet_atomic(c, "miner-x", need_i64, cols), 1)   # inner agrees
        self.assertEqual(self.mod._balance_i64_for_wallet(c, "miner-x"), 0)
        c.close()

    def test_fleet_named_wallets_work(self):
        """Vintage NAMED wallets are keyed by identity string, unaffected by the fix."""
        for fn in (_schema_A, _schema_B):
            c, cols = self._fresh(fn)
            for w in ("g4-powerbook-115", "power8-s824-sophia", "founder_community"):
                _seed(c, cols, w, 3.0)
                self.assertEqual(self.mod._balance_i64_for_wallet(c, w), 3 * U)
                self.assertEqual(self.mod._debit_wallet_atomic(c, w, int(1 * U), cols), 1)
                self.assertEqual(self.mod._balance_i64_for_wallet(c, w), 2 * U)
            c.close()


if __name__ == "__main__":
    unittest.main()
