# SPDX-License-Identifier: MIT
"""settle_epoch_rip200 is the path production actually settles with (cron ->
POST /rewards/settle -> settle_epoch). Under UTXO_DUAL_WRITE it must mint a
reward box mirroring each account credit; before this fix it minted nothing, so
the account model grew by the epoch pot every epoch while the UTXO side stood
still (#2819, same class as the finalize_epoch precision split)."""
import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

NODE = str(Path(__file__).resolve().parents[1])
if NODE not in sys.path:
    sys.path.insert(0, NODE)


class Rip200SettlementDualWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = os.path.join(self.tmp.name, "settle.db")
        os.environ["UTXO_DUAL_WRITE"] = "1"
        import rewards_implementation_rip200 as rip
        self.rip = importlib.reload(rip)          # picks up UTXO_DUAL_WRITE
        from utxo_db import UtxoDB
        UtxoDB(self.db).init_tables()
        with sqlite3.connect(self.db) as c:
            c.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)")
            c.execute("CREATE TABLE IF NOT EXISTS epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER)")
            c.commit()

    def tearDown(self):
        os.environ.pop("UTXO_DUAL_WRITE", None)
        importlib.reload(self.rip)
        self.tmp.cleanup()

    def _mint(self, rewards, epoch=7001):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("BEGIN IMMEDIATE")
            for miner, urtc in rewards.items():
                conn.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?,?) "
                             "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                             (miner, urtc, urtc))
                conn.execute("INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?,?,?)",
                             (epoch, miner, urtc))
            res = self.rip._dual_write_mint_rewards(conn, epoch, self.db)
            conn.commit()
            return res
        finally:
            conn.close()

    def test_each_credit_gets_an_exactly_matching_mirror_box(self):
        rewards = {"RTC" + "a" * 40: 16777395, "dual-g4-125": 7522569}
        res = self._mint(rewards)
        self.assertEqual(res["minted_boxes"], 2)
        with sqlite3.connect(self.db) as c:
            for miner, urtc in rewards.items():
                box = c.execute("SELECT COALESCE(SUM(value_nrtc),0) FROM utxo_boxes "
                                "WHERE owner_address=? AND spent_at IS NULL", (miner,)).fetchone()[0]
                self.assertEqual(box, urtc * 100, f"{miner}: box != credit x100")
                mirrored = c.execute("SELECT COUNT(*) FROM account_mirror_boxes m JOIN utxo_boxes b "
                                     "ON b.box_id=m.box_id WHERE b.owner_address=?", (miner,)).fetchone()[0]
                self.assertEqual(mirrored, 1, f"{miner}: reward box not registered as a mirror")
            unmirrored = c.execute("SELECT COUNT(*) FROM utxo_boxes WHERE spent_at IS NULL AND box_id "
                                   "NOT IN (SELECT box_id FROM account_mirror_boxes)").fetchone()[0]
            self.assertEqual(unmirrored, 0)

    def test_sub_dust_share_is_skipped_not_minted(self):
        res = self._mint({"tiny-miner": 5})      # 5 uRTC = 500 nRTC < 1000 dust
        self.assertEqual(res["minted_boxes"], 0)
        self.assertEqual(res["skipped_dust_nrtc"], 500)

    def test_does_nothing_when_dual_write_is_off(self):
        os.environ["UTXO_DUAL_WRITE"] = "0"
        rip = importlib.reload(self.rip)
        conn = sqlite3.connect(self.db)
        try:
            res = rip._dual_write_mint_rewards(conn, 7002, self.db)
        finally:
            conn.close()
        self.assertEqual(res["minted_boxes"], 0)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM utxo_boxes").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
