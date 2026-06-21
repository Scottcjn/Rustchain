# SPDX-License-Identifier: MIT

import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"
ADMIN_KEY = "0123456789abcdef0123456789abcdef"
ACCOUNT_UNIT = 1_000_000


def _load_node_module(db_path: str):
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
    os.environ["UTXO_DUAL_WRITE"] = "0"
    if str(NODE_DIR) not in sys.path:
        sys.path.insert(0, str(NODE_DIR))

    spec = importlib.util.spec_from_file_location(
        "rustchain_pending_confirm_cross_model_test",
        MODULE_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.send_sophiacheck_alert = lambda *args, **kwargs: None
    mod.init_db()
    return mod


def _seed_account_balance(db_path: str, wallet: str, rtc_amount: int) -> None:
    with sqlite3.connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(balances)")}
        if {"miner_id", "amount_i64"}.issubset(cols):
            conn.execute(
                "INSERT OR REPLACE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                (wallet, rtc_amount * ACCOUNT_UNIT),
            )
            return
        if {"miner_pk", "balance_rtc"}.issubset(cols):
            conn.execute(
                "INSERT OR REPLACE INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
                (wallet, float(rtc_amount)),
            )
            return
        raise AssertionError(f"unsupported balances schema: {sorted(cols)}")


def _account_balance_rtc(db_path: str, wallet: str) -> float:
    with sqlite3.connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(balances)")}
        if {"miner_id", "amount_i64"}.issubset(cols):
            row = conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (wallet,),
            ).fetchone()
            return (row[0] if row else 0) / ACCOUNT_UNIT
        if {"miner_pk", "balance_rtc"}.issubset(cols):
            row = conn.execute(
                "SELECT balance_rtc FROM balances WHERE miner_pk = ?",
                (wallet,),
            ).fetchone()
            return float(row[0] if row else 0)
        raise AssertionError(f"unsupported balances schema: {sorted(cols)}")


class TestPendingConfirmUtxoOwnership(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_env = {
            "RUSTCHAIN_DB_PATH": os.environ.get("RUSTCHAIN_DB_PATH"),
            "RC_ADMIN_KEY": os.environ.get("RC_ADMIN_KEY"),
            "UTXO_DUAL_WRITE": os.environ.get("UTXO_DUAL_WRITE"),
        }
        self.db_path = os.path.join(self._tmp.name, "node.db")
        self.mod = _load_node_module(self.db_path)

    def tearDown(self):
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def _seed_pending_transfer(self, sender, recipient, amount_rtc, *, tx_hash):
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, reason,
                 status, created_at, confirms_at, tx_hash)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    now - 10,
                    1,
                    sender,
                    recipient,
                    amount_rtc * ACCOUNT_UNIT,
                    "signed_transfer:cross-model-regression",
                    now - 10,
                    now - 1,
                    tx_hash,
                ),
            )

    def _confirm_ready_pending(self):
        return self.mod.app.test_client().post(
            "/pending/confirm",
            json={"limit": 1},
            headers={"X-Admin-Key": ADMIN_KEY},
        )

    def test_pending_confirm_consumes_or_moves_matching_migrated_utxo(self):
        """Account confirmation must not leave the sender's migrated UTXO spendable."""
        from utxo_db import UNIT, UtxoDB

        sender = "alice"
        account_recipient = "bob"
        utxo_recipient = "carol"
        amount_rtc = 100

        _seed_account_balance(self.db_path, sender, amount_rtc)
        _seed_account_balance(self.db_path, account_recipient, 0)

        utxo = UtxoDB(self.db_path)
        utxo.init_tables()
        self.assertTrue(
            utxo.apply_transaction(
                {
                    "tx_type": "mining_reward",
                    "_allow_minting": True,
                    "inputs": [],
                    "outputs": [
                        {"address": sender, "value_nrtc": amount_rtc * UNIT},
                    ],
                    "fee_nrtc": 0,
                    "timestamp": 1,
                },
                block_height=1,
            )
        )
        self.assertEqual(utxo.get_balance(sender), amount_rtc * UNIT)

        self._seed_pending_transfer(
            sender,
            account_recipient,
            amount_rtc,
            tx_hash="acct-confirm-cross-model",
        )
        response = self._confirm_ready_pending()
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["confirmed_count"], 1)
        self.assertEqual(_account_balance_rtc(self.db_path, sender), 0)
        self.assertEqual(_account_balance_rtc(self.db_path, account_recipient), amount_rtc)

        stale_sender_boxes = utxo.get_unspent_for_address(sender)
        stale_spend_ok = False
        if stale_sender_boxes:
            stale_spend_ok = utxo.apply_transaction(
                {
                    "tx_type": "transfer",
                    "inputs": [
                        {
                            "box_id": stale_sender_boxes[0]["box_id"],
                            "spending_proof": "already-authorized-account-transfer",
                        }
                    ],
                    "outputs": [
                        {"address": utxo_recipient, "value_nrtc": amount_rtc * UNIT},
                    ],
                    "fee_nrtc": 0,
                    "timestamp": 2,
                },
                block_height=2,
            )

        self.assertFalse(
            stale_sender_boxes or stale_spend_ok,
            (
                "confirmed account-model transfer left sender's migrated UTXO "
                f"spendable; stale_box_count={len(stale_sender_boxes)}, "
                f"stale_spend_ok={stale_spend_ok}"
            ),
        )

    def test_pending_confirm_preserves_utxo_change_for_partial_mirror(self):
        """Partial account confirmations must mirror recipient output and sender change."""
        from utxo_db import UNIT, UtxoDB

        sender = "alice"
        recipient = "bob"
        account_rtc = 100
        transfer_rtc = 40

        _seed_account_balance(self.db_path, sender, account_rtc)
        _seed_account_balance(self.db_path, recipient, 0)

        utxo = UtxoDB(self.db_path)
        utxo.init_tables()
        self.assertTrue(
            utxo.apply_transaction(
                {
                    "tx_type": "mining_reward",
                    "_allow_minting": True,
                    "inputs": [],
                    "outputs": [{"address": sender, "value_nrtc": account_rtc * UNIT}],
                    "fee_nrtc": 0,
                    "timestamp": 1,
                },
                block_height=1,
            )
        )

        self._seed_pending_transfer(sender, recipient, transfer_rtc, tx_hash="partial-mirror")
        response = self._confirm_ready_pending()

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["confirmed_count"], 1)
        self.assertEqual(_account_balance_rtc(self.db_path, sender), account_rtc - transfer_rtc)
        self.assertEqual(_account_balance_rtc(self.db_path, recipient), transfer_rtc)
        self.assertEqual(utxo.get_balance(sender), (account_rtc - transfer_rtc) * UNIT)
        self.assertEqual(utxo.get_balance(recipient), transfer_rtc * UNIT)

    def test_pending_confirm_rolls_back_when_migrated_utxo_cannot_cover_amount(self):
        """Do not debit the account model if migrated UTXO state cannot mirror it."""
        from utxo_db import UNIT, UtxoDB

        sender = "alice"
        recipient = "bob"
        account_rtc = 100
        utxo_rtc = 50

        _seed_account_balance(self.db_path, sender, account_rtc)
        _seed_account_balance(self.db_path, recipient, 0)

        utxo = UtxoDB(self.db_path)
        utxo.init_tables()
        self.assertTrue(
            utxo.apply_transaction(
                {
                    "tx_type": "mining_reward",
                    "_allow_minting": True,
                    "inputs": [],
                    "outputs": [{"address": sender, "value_nrtc": utxo_rtc * UNIT}],
                    "fee_nrtc": 0,
                    "timestamp": 1,
                },
                block_height=1,
            )
        )

        self._seed_pending_transfer(sender, recipient, account_rtc, tx_hash="insufficient-utxo")
        response = self._confirm_ready_pending()
        body = response.get_json()

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(body["confirmed_count"], 0)
        self.assertEqual(body["errors"], [{"id": 1, "error": "internal_error"}])
        self.assertEqual(_account_balance_rtc(self.db_path, sender), account_rtc)
        self.assertEqual(_account_balance_rtc(self.db_path, recipient), 0)
        self.assertEqual(utxo.get_balance(sender), utxo_rtc * UNIT)
        self.assertEqual(utxo.get_balance(recipient), 0)

        with sqlite3.connect(self.db_path) as conn:
            status = conn.execute("SELECT status FROM pending_ledger WHERE id = 1").fetchone()[0]
        self.assertEqual(status, "pending")


if __name__ == "__main__":
    unittest.main()
