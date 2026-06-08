"""T3.1 regression: finalize_epoch must audit-ledger every reward credit.

finalize_epoch (the auto block-path settlement) credited `balances` with NO `ledger`
row, while settle_epoch_rip200 and the transfer/bonus paths DO. Block-path rewards were
therefore invisible to audit/reconstruction and broke any ledger<->balance
reconciliation. This adds a schema-tolerant single-sided reward row inside the same
BEGIN IMMEDIATE that credits the balance (commit/rollback together).
"""
import importlib.util
import os
import sqlite3
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class LedgerRewardHelperTest(unittest.TestCase):
    """Unit-level: the schema-tolerant _ledger_reward_row helper."""
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ.setdefault("RUSTCHAIN_DB_PATH", os.path.join(cls._tmp.name, "t31h.db"))
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ.setdefault("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1")
        spec = importlib.util.spec_from_file_location("rcnode_t31h_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_shape_a_canonical(self):
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, "
                  "epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
        cols = self.mod._table_columns(c, "ledger")
        self.mod._ledger_reward_row(c, cols, 42, "g4-115", 108_000_000, "epoch_42_reward")
        row = c.execute("SELECT epoch, miner_id, delta_i64, reason FROM ledger").fetchone()
        self.assertEqual(row, (42, "g4-115", 108_000_000, "epoch_42_reward"))

    def test_legacy_shape_b_not_supported_skips(self):
        """Only the canonical shape is supported (matching settle_epoch_rip200, which has
        no fallback). A legacy double-entry ledger is skipped, not written with a
        synthetic mint source."""
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE ledger (from_miner TEXT, to_miner TEXT, amount_i64 INTEGER, memo TEXT, ts INTEGER)")
        cols = self.mod._table_columns(c, "ledger")
        wrote = self.mod._ledger_reward_row(c, cols, 42, "g4-115", 108_000_000, "epoch_42_reward")
        self.assertFalse(wrote)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0], 0)

    def test_unknown_schema_skips_gracefully(self):
        """An unrecognized ledger schema must NOT raise (raising would halt reward
        settlement on a non-canonical node). It logs + skips and returns False;
        the caller still credits the balance."""
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE ledger (something_else TEXT)")
        cols = self.mod._table_columns(c, "ledger")
        wrote = self.mod._ledger_reward_row(c, cols, 42, "g4-115", 1, "epoch_42_reward")
        self.assertFalse(wrote)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0], 0)

    def test_partial_shape_a_missing_ts_skips(self):
        """A drifted shape-A table missing `ts` must NOT be selected then fail on the
        INSERT — the all-columns guard sends it to the skip path."""
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE ledger (epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
        cols = self.mod._table_columns(c, "ledger")
        wrote = self.mod._ledger_reward_row(c, cols, 42, "g4-115", 1, "epoch_42_reward")
        self.assertFalse(wrote)


class FinalizeEpochLedgerTest(unittest.TestCase):
    """End-to-end: finalize_epoch credits balances AND ledgers them, reconcilably."""
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._db = os.path.join(cls._tmp.name, "t31e.db")
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        spec = importlib.util.spec_from_file_location("rcnode_t31e_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.init_db()
        # init_db creates the LEGACY balances(miner_pk, balance_rtc) shape, but the live
        # node (and finalize_epoch) run on the migrated (miner_id, amount_i64) shape.
        # Recreate it to match production so this test exercises the real code path.
        with sqlite3.connect(cls._db) as c:
            c.execute("DROP TABLE IF EXISTS balances")
            c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, "
                      "amount_i64 INTEGER NOT NULL DEFAULT 0 CHECK(amount_i64>=0), "
                      "balance_rtc REAL DEFAULT 0)")
            c.commit()

    def _seed_epoch(self, epoch, miners):
        with sqlite3.connect(self._db) as c:
            for pk, w in miners:
                c.execute("INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                          (epoch, pk, w))
                c.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)", (pk,))
            c.commit()

    def test_finalize_writes_reconcilable_ledger_rows(self):
        epoch = 5005
        miners = [("g4-powerbook-115", self.mod.epoch_weight_to_units(2.5)),
                  ("g5-selena-179", self.mod.epoch_weight_to_units(2.0))]
        self._seed_epoch(epoch, miners)

        self.mod.finalize_epoch(epoch, per_block_rtc=1.5, prev_block_hash=b"")

        with sqlite3.connect(self._db) as c:
            # every credited miner has a ledger row for this epoch
            led = dict(c.execute(
                "SELECT miner_id, SUM(delta_i64) FROM ledger WHERE reason = ? GROUP BY miner_id",
                (f"epoch_{epoch}_reward",)).fetchall())
            bals = dict(c.execute(
                "SELECT miner_id, amount_i64 FROM balances WHERE miner_id IN (?, ?)",
                (miners[0][0], miners[1][0])).fetchall())
            settled = c.execute("SELECT settled FROM epoch_state WHERE epoch = ?", (epoch,)).fetchone()[0]

        self.assertEqual(settled, 1)
        self.assertTrue(led, "finalize_epoch wrote no reward ledger rows (the T3.1 gap)")
        # RECONCILIATION: each miner's ledgered reward == its balance credit
        for pk, _w in miners:
            self.assertGreater(bals[pk], 0)
            self.assertEqual(led.get(pk), bals[pk],
                             f"ledger delta != balance credit for {pk} (unreconciled)")
        # and the ledger total equals the total credited
        self.assertEqual(sum(led.values()), sum(bals.values()))

    def test_replay_does_not_double_ledger(self):
        epoch = 5006
        miners = [("dual-g4-125", self.mod.epoch_weight_to_units(2.5))]
        self._seed_epoch(epoch, miners)
        self.mod.finalize_epoch(epoch, per_block_rtc=1.5, prev_block_hash=b"")
        with sqlite3.connect(self._db) as c:
            n1 = c.execute("SELECT COUNT(*) FROM ledger WHERE reason = ?", (f"epoch_{epoch}_reward",)).fetchone()[0]
            bal1 = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'dual-g4-125'").fetchone()[0]
        # second finalize must be a no-op (epoch already settled)
        self.mod.finalize_epoch(epoch, per_block_rtc=1.5, prev_block_hash=b"")
        with sqlite3.connect(self._db) as c:
            n2 = c.execute("SELECT COUNT(*) FROM ledger WHERE reason = ?", (f"epoch_{epoch}_reward",)).fetchone()[0]
            bal2 = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'dual-g4-125'").fetchone()[0]
        self.assertEqual(n1, n2, "replay created duplicate ledger rows")
        self.assertEqual(bal1, bal2, "replay double-credited the balance")


    def test_no_phantom_ledger_when_balance_row_absent(self):
        """Codex #18: a miner enrolled WITHOUT a balance row — the UPDATE hits 0 rows
        (no credit) — must NOT get a ledger row (no ledger≠balance phantom)."""
        epoch = 5007
        pk = "ghost-no-balance-row"
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                      (epoch, pk, self.mod.epoch_weight_to_units(2.5)))
            # deliberately NO balances row for pk
            c.commit()
        self.mod.finalize_epoch(epoch, per_block_rtc=1.5, prev_block_hash=b"")
        with sqlite3.connect(self._db) as c:
            led = c.execute("SELECT COUNT(*) FROM ledger WHERE reason = ?",
                            (f"epoch_{epoch}_reward",)).fetchone()[0]
            bal = c.execute("SELECT COUNT(*) FROM balances WHERE miner_id = ?", (pk,)).fetchone()[0]
        self.assertEqual(bal, 0, "no balance row should have been created")
        self.assertEqual(led, 0, "phantom ledger row written for an uncredited miner")


    def test_ledger_failure_one_miner_does_not_block_others(self):
        """SAVEPOINT isolation: if the ledger INSERT fails for ONE miner mid-loop, the
        epoch must still settle, EVERY miner (including the failing one) must still be
        credited, and the non-failing miners must still get their audit rows. A bare
        try/except would risk poisoning the transaction for the rest of the loop."""
        epoch = 5008
        w = self.mod.epoch_weight_to_units(2.5)
        miners = [("led-ok-1", w), ("led-boom", w), ("led-ok-2", w)]
        self._seed_epoch(epoch, miners)

        orig = self.mod._ledger_reward_row

        def _selective(c, cols, ep, mid, amt, reason):
            if mid == "led-boom":
                raise sqlite3.OperationalError("injected ledger failure for one miner")
            return orig(c, cols, ep, mid, amt, reason)

        self.mod._ledger_reward_row = _selective
        try:
            self.mod.finalize_epoch(epoch, per_block_rtc=1.5, prev_block_hash=b"")
        finally:
            self.mod._ledger_reward_row = orig

        with sqlite3.connect(self._db) as c:
            settled = c.execute("SELECT settled FROM epoch_state WHERE epoch = ?", (epoch,)).fetchone()[0]
            bals = {pk: c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (pk,)).fetchone()[0]
                    for pk, _ in miners}
            led = {r[0] for r in c.execute(
                "SELECT miner_id FROM ledger WHERE reason = ?", (f"epoch_{epoch}_reward",)).fetchall()}

        self.assertEqual(settled, 1, "epoch left unsettled by a single ledger failure")
        for pk, _ in miners:
            self.assertGreater(bals[pk], 0, f"{pk} was not credited (transaction poisoned)")
        # non-failing miners got audit rows; the failing one was rolled back but still credited
        self.assertIn("led-ok-1", led)
        self.assertIn("led-ok-2", led)
        self.assertNotIn("led-boom", led)


if __name__ == "__main__":
    unittest.main()
