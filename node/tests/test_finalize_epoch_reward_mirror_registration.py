# SPDX-License-Identifier: MIT
"""End-to-end: under UTXO dual-write, finalize_epoch registers ITS OWN reward
boxes as account-mirror provenance, and only those.

Reward batches mint at height epoch*EPOCH_SLOTS + batch_index, which is in the
same number space as /utxo/transfer's current_slot() heights. A height-only
match would tag an unrelated user's transfer box at that height as a mirror,
locking it (every spend -> 409 ACCOUNT_MIRROR_BOX_NOT_SPENDABLE).
"""
import importlib.util
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "rustchain_v2_integrated_v2.2.1_rip200.py"


class FinalizeEpochRewardMirrorRegistrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved_env = {k: os.environ.get(k) for k in
                          ("RUSTCHAIN_DB_PATH", "RC_ADMIN_KEY", "RUSTCHAIN_DISABLE_P2P_AUTO_START")}
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._db = os.path.join(cls._tmp.name, "dwmirror.db")
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        spec = importlib.util.spec_from_file_location("rcnode_dwmirror_test", MODULE_PATH)
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
        for k, v in cls._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls._tmp.cleanup()

    def test_only_this_epochs_reward_boxes_become_mirrors(self):
        epoch = 6201
        height = epoch * self.mod.EPOCH_SLOTS  # batch 0's mint height
        miners = [("mir-a", 3), ("mir-b", 5)]
        with sqlite3.connect(self._db) as c:
            for pk, w in miners:
                c.execute("INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                          (epoch, pk, self.mod.epoch_weight_to_units(w)))
                c.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)", (pk,))
            # A user's ordinary transfer output that happens to share the height.
            now = int(time.time())
            c.execute("INSERT INTO utxo_transactions (tx_id, tx_type, inputs_json, outputs_json, "
                      "timestamp, block_height) VALUES ('user-transfer-tx', 'transfer', '[]', '[]', ?, ?)",
                      (now, height))
            c.execute("INSERT INTO utxo_boxes (box_id, value_nrtc, proposition, owner_address, "
                      "creation_height, transaction_id, output_index, created_at) "
                      "VALUES ('user-box', 5000000, 'p', 'RTC' || ?, ?, 'user-transfer-tx', 0, ?)",
                      ("ab" * 20, height, now))
            c.commit()

        self.mod.finalize_epoch(epoch, per_block_rtc=self.mod.PER_BLOCK_RTC, prev_block_hash=b"")

        ratio = self.mod.UTXO_UNIT // self.mod.ACCOUNT_UNIT
        with sqlite3.connect(self._db) as c:
            mirrors = {r[0]: (r[1], r[2]) for r in c.execute(
                "SELECT box_id, account_wallet, value_nrtc FROM account_mirror_boxes")}
            self.assertNotIn("user-box", mirrors,
                             "a user's transfer box at the reward height was tagged as a mirror (locked)")
            for pk, _ in miners:
                credit = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (pk,)).fetchone()[0]
                rows = [v for (w, v) in mirrors.values() if w == pk]
                self.assertEqual(len(rows), 1, f"{pk}: reward box not registered as mirror")
                self.assertEqual(rows[0], credit * ratio, f"{pk}: mirror value != account credit")


if __name__ == "__main__":
    unittest.main()
