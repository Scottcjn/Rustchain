# SPDX-License-Identifier: MIT
"""End-to-end: under UTXO dual-write, finalize_epoch must mint UTXO reward boxes
that EXACTLY mirror the account-model credit.

#2819 (favoritegrandson-tech): the account credit truncated the share to 6
decimals (uRTC) while the UTXO mint truncated the same Decimal to 8 decimals
(nRTC), so each reward box could be up to 99 nRTC larger than the credit and
/utxo/integrity reported the models disagreeing after every settlement with
fractional shares. Separately, a miner with no balance row got no account
credit (no-phantom invariant) but still received a UTXO mint.
"""
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "rustchain_v2_integrated_v2.2.1_rip200.py"


class FinalizeEpochDualWritePrecisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved_env = {k: os.environ.get(k) for k in
                          ("RUSTCHAIN_DB_PATH", "RC_ADMIN_KEY", "RUSTCHAIN_DISABLE_P2P_AUTO_START")}
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._db = os.path.join(cls._tmp.name, "dwprec.db")
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        spec = importlib.util.spec_from_file_location("rcnode_dwprec_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.init_db()
        with sqlite3.connect(cls._db) as c:  # production (miner_id, amount_i64) shape
            c.execute("DROP TABLE IF EXISTS balances")
            c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, "
                      "amount_i64 INTEGER NOT NULL DEFAULT 0 CHECK(amount_i64>=0), "
                      "balance_rtc REAL DEFAULT 0)")
            c.commit()
        from utxo_db import UtxoDB
        UtxoDB(cls._db).init_tables()
        cls._orig_dual_write = cls.mod.UTXO_DUAL_WRITE
        cls.mod.UTXO_DUAL_WRITE = True

    @classmethod
    def tearDownClass(cls):
        cls.mod.UTXO_DUAL_WRITE = cls._orig_dual_write
        # Don't leak this suite's env into later tests in the same process.
        for k, v in cls._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls._tmp.cleanup()

    def _enroll(self, epoch, pk, weight, with_balance_row=True):
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                      (epoch, pk, weight))
            if with_balance_row:
                c.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)", (pk,))
            c.commit()

    def _utxo_total(self, c, owner):
        return c.execute("SELECT COALESCE(SUM(value_nrtc), 0) FROM utxo_boxes "
                         "WHERE owner_address = ? AND spent_at IS NULL", (owner,)).fetchone()[0]

    def test_reward_box_equals_account_credit_exactly(self):
        epoch = 6101
        # Co-prime weights => shares with non-terminating decimals, where 6dp and
        # 8dp truncation of the same Decimal disagree.
        miners = [("prec-a", 7), ("prec-b", 11), ("prec-c", 13)]
        for pk, w in miners:
            self._enroll(epoch, pk, self.mod.epoch_weight_to_units(w))

        self.mod.finalize_epoch(epoch, per_block_rtc=self.mod.PER_BLOCK_RTC, prev_block_hash=b"")

        ratio = self.mod.UTXO_UNIT // self.mod.ACCOUNT_UNIT
        with sqlite3.connect(self._db) as c:
            self.assertEqual(c.execute("SELECT settled FROM epoch_state WHERE epoch = ?",
                                       (epoch,)).fetchone()[0], 1)
            for pk, _ in miners:
                credit = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?",
                                   (pk,)).fetchone()[0]
                self.assertGreater(credit, 0)
                self.assertEqual(self._utxo_total(c, pk), credit * ratio,
                                 f"{pk}: UTXO reward != account credit (models disagree)")

    def test_no_utxo_mint_for_miner_without_balance_row(self):
        epoch = 6102
        self._enroll(epoch, "prec-credited", self.mod.epoch_weight_to_units(2.0))
        self._enroll(epoch, "prec-ghost", self.mod.epoch_weight_to_units(2.0), with_balance_row=False)

        self.mod.finalize_epoch(epoch, per_block_rtc=self.mod.PER_BLOCK_RTC, prev_block_hash=b"")

        with sqlite3.connect(self._db) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM balances WHERE miner_id = 'prec-ghost'")
                             .fetchone()[0], 0, "no-phantom: no balance row may be created")
            self.assertEqual(self._utxo_total(c, "prec-ghost"), 0,
                             "UTXO minted for a miner the account model never credited")
            # The ghost still dilutes total_weight (its share is burned in both
            # models); the credited miner must still mirror its credit exactly.
            credit = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'prec-credited'").fetchone()[0]
            self.assertGreater(credit, 0)
            self.assertEqual(self._utxo_total(c, "prec-credited"),
                             credit * (self.mod.UTXO_UNIT // self.mod.ACCOUNT_UNIT))


if __name__ == "__main__":
    unittest.main()
