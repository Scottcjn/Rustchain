# SPDX-License-Identifier: MIT
"""Cross-model double-spend regression (bounty #2819).

After UTXO migration a wallet has both an account balance and a migrated UTXO
box mirroring the same funds. Confirming an account-model pending transfer must
reconcile the mirror so the same funds cannot also move through the UTXO path.

These tests pin the *synthesis* fix (provenance-based discriminator):
  * the sender's migrated MIRROR box is consumed on confirm (no double-spend);
  * an independently-earned (non-mirror) box is LEFT ALONE (no over-spend);
  * both invariants hold with UTXO_DUAL_WRITE off and on.
"""

import hashlib
import importlib.util
import json
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


def _load_node_module(db_path: str, dual_write: str = "0"):
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
    os.environ["UTXO_DUAL_WRITE"] = dual_write
    if str(NODE_DIR) not in sys.path:
        sys.path.insert(0, str(NODE_DIR))

    spec = importlib.util.spec_from_file_location(
        f"rustchain_pending_confirm_xmodel_{dual_write}",
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
                "SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)
            ).fetchone()
            return (row[0] if row else 0) / ACCOUNT_UNIT
        if {"miner_pk", "balance_rtc"}.issubset(cols):
            row = conn.execute(
                "SELECT balance_rtc FROM balances WHERE miner_pk = ?", (wallet,)
            ).fetchone()
            return float(row[0] if row else 0)
        raise AssertionError(f"unsupported balances schema: {sorted(cols)}")


def _seed_box(db_path: str, wallet: str, rtc_amount: int, *, mirror: bool, tag: str) -> str:
    """Seed an unspent UTXO box for `wallet`.

    mirror=True records it in account_mirror_boxes (simulating genesis
    migration); mirror=False is an independently-earned box with no provenance.
    """
    from utxo_db import UNIT, UtxoDB, address_to_proposition, compute_box_id

    utxo = UtxoDB(db_path)
    utxo.init_tables()
    value = rtc_amount * UNIT
    prop = address_to_proposition(wallet)
    tx_id = hashlib.sha256(f"seed:{tag}:{wallet}:{rtc_amount}".encode()).hexdigest()
    box_id = compute_box_id(value, prop, 1, tx_id, 0)
    utxo.add_box({
        "box_id": box_id,
        "value_nrtc": value,
        "proposition": prop,
        "owner_address": wallet,
        "creation_height": 1,
        "transaction_id": tx_id,
        "output_index": 0,
        "tokens_json": "[]",
        "registers_json": json.dumps({"R4": "genesis"}) if mirror else "[]",
    })
    if mirror:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS account_mirror_boxes (
                       box_id TEXT PRIMARY KEY, account_wallet TEXT NOT NULL,
                       value_nrtc INTEGER NOT NULL, created_epoch INTEGER NOT NULL)"""
            )
            conn.execute(
                "INSERT OR REPLACE INTO account_mirror_boxes "
                "(box_id, account_wallet, value_nrtc, created_epoch) VALUES (?,?,?,?)",
                (box_id, wallet, value, 1),
            )
    return box_id


def _insert_pending_and_confirm(mod, db_path, sender, recipient, amount_rtc):
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO pending_ledger
               (ts, epoch, from_miner, to_miner, amount_i64, reason,
                status, created_at, confirms_at, tx_hash)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (now - 10, 1, sender, recipient, amount_rtc * ACCOUNT_UNIT,
             "signed_transfer:xmodel-regression", now - 10, now - 1,
             f"acct-confirm-{sender}-{recipient}"),
        )
    return mod.app.test_client().post(
        "/pending/confirm", json={"limit": 5}, headers={"X-Admin-Key": ADMIN_KEY}
    )


class _Base(unittest.TestCase):
    DUAL_WRITE = "0"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_env = {k: os.environ.get(k) for k in
                         ("RUSTCHAIN_DB_PATH", "RC_ADMIN_KEY", "UTXO_DUAL_WRITE")}
        self.db_path = os.path.join(self._tmp.name, "node.db")
        self.mod = _load_node_module(self.db_path, self.DUAL_WRITE)

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def _unspent(self, wallet):
        from utxo_db import UtxoDB
        return UtxoDB(self.db_path).get_unspent_for_address(wallet)

    def test_confirm_consumes_migrated_mirror_box(self):
        """The migrated mirror box must not survive an account confirm."""
        from utxo_db import UNIT
        _seed_account_balance(self.db_path, "alice", 100)
        _seed_account_balance(self.db_path, "bob", 0)
        _seed_box(self.db_path, "alice", 100, mirror=True, tag="mirror")

        resp = _insert_pending_and_confirm(self.mod, self.db_path, "alice", "bob", 100)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["confirmed_count"], 1)

        self.assertEqual(_account_balance_rtc(self.db_path, "alice"), 0)
        self.assertEqual(_account_balance_rtc(self.db_path, "bob"), 100)
        # Alice's mirror box is consumed → no double-spend path remains.
        self.assertEqual(self._unspent("alice"), [],
                         "migrated mirror box left spendable after account confirm")
        # The moved funds are mirrored onto Bob (dual-model stays consistent).
        self.assertEqual(sum(b["value_nrtc"] for b in self._unspent("bob")), 100 * UNIT)

    def test_confirm_leaves_independently_earned_box(self):
        """An earned (non-mirror) box must NOT be burned by an account confirm."""
        _seed_account_balance(self.db_path, "alice", 100)
        _seed_account_balance(self.db_path, "bob", 0)
        _seed_box(self.db_path, "alice", 100, mirror=True, tag="mirror")
        earned = _seed_box(self.db_path, "alice", 40, mirror=False, tag="earned")

        resp = _insert_pending_and_confirm(self.mod, self.db_path, "alice", "bob", 100)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))

        alice_unspent = {b["box_id"] for b in self._unspent("alice")}
        self.assertIn(earned, alice_unspent,
                      "account confirm wrongly burned an independently-earned UTXO")

    def test_partial_transfer_returns_mirror_change(self):
        """A partial transfer consumes the mirror box but returns change."""
        from utxo_db import UNIT
        _seed_account_balance(self.db_path, "alice", 100)
        _seed_account_balance(self.db_path, "bob", 0)
        _seed_box(self.db_path, "alice", 100, mirror=True, tag="mirror")

        resp = _insert_pending_and_confirm(self.mod, self.db_path, "alice", "bob", 30)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))

        # Alice keeps 70 RTC of mirror change; Bob receives 30.
        self.assertEqual(sum(b["value_nrtc"] for b in self._unspent("alice")), 70 * UNIT)
        self.assertEqual(sum(b["value_nrtc"] for b in self._unspent("bob")), 30 * UNIT)

    def test_backfill_adopts_pre_provenance_genesis_box(self):
        """A genesis box created before provenance tracking must be adopted by
        the confirm-time backfill and consumed — no lingering double-spend
        window on DBs migrated before this fix."""
        from utxo_db import UNIT, UtxoDB, address_to_proposition, compute_box_id
        _seed_account_balance(self.db_path, "alice", 100)
        _seed_account_balance(self.db_path, "bob", 0)
        # Genesis-marked box with NO account_mirror_boxes row (pre-fix state).
        utxo = UtxoDB(self.db_path)
        utxo.init_tables()
        value = 100 * UNIT
        prop = address_to_proposition("alice")
        tx_id = hashlib.sha256(b"premig:alice").hexdigest()
        box_id = compute_box_id(value, prop, 1, tx_id, 0)
        utxo.add_box({
            "box_id": box_id, "value_nrtc": value, "proposition": prop,
            "owner_address": "alice", "creation_height": 1,
            "transaction_id": tx_id, "output_index": 0, "tokens_json": "[]",
            "registers_json": json.dumps({"R4": "genesis"}),
        })

        resp = _insert_pending_and_confirm(self.mod, self.db_path, "alice", "bob", 100)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(self._unspent("alice"), [],
                         "pre-provenance genesis box not adopted+consumed by backfill")


class TestDualWriteOff(_Base):
    DUAL_WRITE = "0"


class TestDualWriteOn(_Base):
    DUAL_WRITE = "1"


if __name__ == "__main__":
    unittest.main()
