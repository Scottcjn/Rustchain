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

    def test_pending_confirm_consumes_or_moves_matching_migrated_utxo(self):
        """Account confirmation must not leave the sender's migrated UTXO spendable."""
        from utxo_db import UNIT, UtxoDB

        sender = "alice"
        account_recipient = "bob"
        utxo_recipient = "carol"
        amount_rtc = 100
        amount_i64 = amount_rtc * ACCOUNT_UNIT

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
                    account_recipient,
                    amount_i64,
                    "signed_transfer:cross-model-regression",
                    now - 10,
                    now - 1,
                    "acct-confirm-cross-model",
                ),
            )

        response = self.mod.app.test_client().post(
            "/pending/confirm",
            json={"limit": 1},
            headers={"X-Admin-Key": ADMIN_KEY},
        )
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


if __name__ == "__main__":
    unittest.main()
