# SPDX-License-Identifier: MIT
"""The welcome bonus must move on the UTXO side too, not only in the account model.

Production, node1, 2026-09-20 -- the first day dual-write ran for real. Epoch 291
settled cleanly (credited nRTC == minted nRTC), yet /utxo/integrity reported
``ok: false`` with one wallet violating ``mirror <= balance``:

    founder_community  balance 2,028,714,224,800 nRTC
                       mirror  2,028,764,224,800 nRTC
                       excess     50,000,000 nRTC  == exactly 0.5 RTC

That day founder_community made 14 ``transfer_out`` payouts (55.20 RTC) and one
``welcome_bonus:0.5_rtc`` debit. The transfers reconciled because they go through
/pending/confirm, which calls _settle_account_transfer_in_utxo. The bonus writes
``balances`` directly, so it never reached that reconciler -- the payer's mirrored
boxes stayed unspent while its balance dropped.

mirror > balance is the double-spend condition from bounty #2819: the same funds
counted in both models. It grows by one bonus every time a new miner first attests.
"""
import importlib.util
import os
import sqlite3
import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"

SOURCE = "founder_community"
MINER = "brand-new-g4-miner"
EPOCH = 291                       # the epoch this was found in
BONUS_URTC = 500_000              # 0.5 RTC, the production bonus
NRTC_PER_URTC = 100
SOURCE_START_URTC = 20_000_000    # 20 RTC in the payer


def _load_node(db_path, tag):
    for p in (str(PROJECT_ROOT), str(NODE_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from tests import mock_crypto

    sys.modules["rustchain_crypto"] = mock_crypto
    os.environ["DB_PATH"] = str(db_path)
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
    spec = importlib.util.spec_from_file_location(f"integrated_node_welcome_mirror_{tag}", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.DB_PATH = str(db_path)
    module.UTXO_DUAL_WRITE = True
    return module


def _mirror_nrtc(conn, wallet):
    return int(conn.execute(
        "SELECT COALESCE(SUM(b.value_nrtc), 0) FROM utxo_boxes b "
        "JOIN account_mirror_boxes m ON m.box_id = b.box_id "
        "WHERE m.account_wallet = ? AND b.spent_at IS NULL",
        (wallet,),
    ).fetchone()[0])


def _balance_nrtc(conn, wallet):
    row = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)).fetchone()
    return int(row[0]) * NRTC_PER_URTC if row and row[0] is not None else 0


class WelcomeBonusMirrorTest(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Path(self.tmp.name)
        self.node = _load_node(self.db, str(int(time.time() * 1000)))

        sys.path.insert(0, str(NODE_DIR))
        from utxo_db import UtxoDB

        UtxoDB(str(self.db)).init_tables()

        now = int(time.time())
        with sqlite3.connect(self.db) as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS balances (
                    miner_id TEXT PRIMARY KEY, miner_pk TEXT,
                    amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,
                    epoch INTEGER, miner_id TEXT NOT NULL,
                    delta_i64 INTEGER NOT NULL, reason TEXT);
                CREATE TABLE IF NOT EXISTS account_mirror_boxes (
                    box_id TEXT PRIMARY KEY, account_wallet TEXT NOT NULL,
                    value_nrtc INTEGER NOT NULL, created_epoch INTEGER);
                """
            )
            c.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                      (SOURCE, SOURCE_START_URTC))
            # The payer is fully mirrored, exactly as genesis leaves it.
            c.execute(
                "INSERT INTO utxo_transactions (tx_id, tx_type, inputs_json, outputs_json, timestamp, block_height) "
                "VALUES ('genesistx', 'genesis', '[]', '[]', ?, 0)", (now,))
            c.execute(
                "INSERT INTO utxo_boxes (box_id, value_nrtc, proposition, owner_address, "
                "creation_height, transaction_id, output_index, created_at) "
                "VALUES ('genesisbox', ?, 'p', ?, 0, 'genesistx', 0, ?)",
                (SOURCE_START_URTC * NRTC_PER_URTC, SOURCE, now))
            c.execute(
                "INSERT INTO account_mirror_boxes (box_id, account_wallet, value_nrtc, created_epoch) "
                "VALUES ('genesisbox', ?, ?, 0)", (SOURCE, SOURCE_START_URTC * NRTC_PER_URTC))
            c.commit()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def _pay_bonus(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self.node._write_welcome_bonus(
                conn, MINER, BONUS_URTC,
                self.node._table_columns(conn, "ledger"),
                self.node._table_columns(conn, "balances"),
            )
            conn.commit()

    def test_payer_mirror_never_exceeds_its_balance(self):
        """The production failure, reduced: pay one bonus, check the invariant."""
        self._pay_bonus()
        with sqlite3.connect(self.db) as c:
            mirror, balance = _mirror_nrtc(c, SOURCE), _balance_nrtc(c, SOURCE)
        self.assertLessEqual(
            mirror, balance,
            f"{SOURCE} mirror exceeds balance by {mirror - balance} nRTC -- "
            "the bounty #2819 double-spend condition",
        )
        # Pre-fix this was exactly the bonus: 50,000,000 nRTC.
        self.assertEqual(mirror - balance, 0)

    def test_bonus_is_mirrored_onto_the_recipient(self):
        self._pay_bonus()
        with sqlite3.connect(self.db) as c:
            self.assertEqual(_balance_nrtc(c, MINER), BONUS_URTC * NRTC_PER_URTC)
            self.assertEqual(_mirror_nrtc(c, MINER), BONUS_URTC * NRTC_PER_URTC)
            self.assertLessEqual(_mirror_nrtc(c, MINER), _balance_nrtc(c, MINER))

    def test_total_mirrored_value_is_conserved(self):
        """A bonus moves value; it must not create or destroy mirrored nRTC."""
        with sqlite3.connect(self.db) as c:
            before = int(c.execute(
                "SELECT COALESCE(SUM(b.value_nrtc),0) FROM utxo_boxes b "
                "JOIN account_mirror_boxes m ON m.box_id=b.box_id WHERE b.spent_at IS NULL"
            ).fetchone()[0])
        self._pay_bonus()
        with sqlite3.connect(self.db) as c:
            after = int(c.execute(
                "SELECT COALESCE(SUM(b.value_nrtc),0) FROM utxo_boxes b "
                "JOIN account_mirror_boxes m ON m.box_id=b.box_id WHERE b.spent_at IS NULL"
            ).fetchone()[0])
        self.assertEqual(before, after)

    def test_repeated_bonuses_do_not_accumulate_drift(self):
        """The real risk: the gap widened by one bonus per new miner."""
        for i in range(5):
            with sqlite3.connect(self.db) as conn:
                conn.execute("BEGIN IMMEDIATE")
                self.node._write_welcome_bonus(
                    conn, f"miner-{i}", BONUS_URTC,
                    self.node._table_columns(conn, "ledger"),
                    self.node._table_columns(conn, "balances"),
                )
                conn.commit()
        with sqlite3.connect(self.db) as c:
            self.assertEqual(_mirror_nrtc(c, SOURCE) - _balance_nrtc(c, SOURCE), 0)
            for i in range(5):
                w = f"miner-{i}"
                self.assertLessEqual(_mirror_nrtc(c, w), _balance_nrtc(c, w))

    def test_account_side_still_correct(self):
        """The mirror sync must not disturb the balances/ledger it reconciles."""
        self._pay_bonus()
        with sqlite3.connect(self.db) as c:
            self.assertEqual(
                int(c.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (SOURCE,)).fetchone()[0]),
                SOURCE_START_URTC - BONUS_URTC)
            self.assertEqual(
                int(c.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (MINER,)).fetchone()[0]),
                BONUS_URTC)
            self.assertEqual(
                int(c.execute("SELECT COUNT(*) FROM ledger WHERE reason LIKE 'welcome_bonus:%'").fetchone()[0]), 2)

    def test_non_mirrored_payer_is_tolerated(self):
        """A pure-account payer has nothing to reconcile; the bonus must still pay."""
        with sqlite3.connect(self.db) as c:
            c.execute("DELETE FROM account_mirror_boxes")
            c.execute("UPDATE utxo_boxes SET spent_at = 1 WHERE box_id='genesisbox'")
            c.commit()
        self._pay_bonus()
        with sqlite3.connect(self.db) as c:
            self.assertEqual(
                int(c.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (MINER,)).fetchone()[0]),
                BONUS_URTC)


if __name__ == "__main__":
    unittest.main()
