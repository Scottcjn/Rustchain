#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for bounty #2819:
1. Under UTXO_DUAL_WRITE=1, /utxo/transfer must register the receiver's output
   (output_index=0) in account_mirror_boxes without poisoning the sender's
   own non-mirror change output (output_index=1), so the sender can execute
   subsequent transfers from their change.
2. /utxo/transfer must reject self-transfers (from_address == to_address) so a
   sender cannot convert their own non-mirror UTXOs into locked mirror boxes.
3. mempool_add() must not inject a synthetic 'timestamp' into tx_data_json when
    the caller omitted 'timestamp', allowing _mempool_claim_matches_tx() to
   match when apply_transaction() is called in a later second.
"""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

NODE_DIR = os.path.abspath(os.path.dirname(__file__))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

try:
    from flask import Flask
except ImportError:
    flask_mod = types.ModuleType("flask")
    class _Req:
        args = {}
        headers = {}
        _json = None
        def get_json(self, silent=False):
            return self._json
    request = _Req()
    class _Resp:
        def __init__(self, data, status=200):
            self._data = data
            self.status_code = status
        def get_json(self):
            return self._data
    def jsonify(obj):
        return obj
    class Blueprint:
        def __init__(self, name, import_name, url_prefix=""):
            self.routes = {}
        def route(self, path, methods=("GET",)):
            def dec(fn):
                self.routes[path] = fn
                return fn
            return dec
    class Flask:
        def __init__(self, name):
            self.config = {}
            self.bp = None
        def register_blueprint(self, bp):
            self.bp = bp
        def test_client(self):
            app = self
            class _Client:
                def post(self, path, json=None):
                    request._json = json
                    fn = app.bp.routes["/transfer"]
                    res = fn()
                    if isinstance(res, tuple):
                        return _Resp(res[0], res[1])
                    return _Resp(res, 200)
                def get(self, path):
                    fn = app.bp.routes[path.replace("/utxo", "")]
                    res = fn()
                    if isinstance(res, tuple):
                        return _Resp(res[0], res[1])
                    return _Resp(res, 200)
            return _Client()
    flask_mod.Blueprint = Blueprint
    flask_mod.Flask = Flask
    flask_mod.request = request
    flask_mod.jsonify = jsonify
    sys.modules["flask"] = flask_mod

import utxo_db
import utxo_endpoints
from utxo_db import UtxoDB, UNIT
from utxo_endpoints import register_utxo_blueprint

SENDER = "RTC" + "a" * 40
RECIPIENT = "RTC" + "b" * 40


class TestBounty2819DualWriteChangeAndMempoolTimestamp(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
            conn.execute("CREATE TABLE ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
            conn.commit()
        self.utxo_db = UtxoDB(self.db_path)
        self.utxo_db.init_tables()
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        register_utxo_blueprint(
            self.app, self.utxo_db, self.db_path,
            verify_sig_fn=lambda pk, msg, sig: True,
            addr_from_pk_fn=lambda pk: SENDER,
            current_slot_fn=lambda: 42,
            dual_write=True,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _seed(self, address, rtc):
        self.utxo_db.apply_transaction({
            "tx_type": "mining_reward", "inputs": [],
            "outputs": [{"address": address, "value_nrtc": rtc * UNIT}],
            "timestamp": int(time.time()), "_allow_minting": True,
        }, block_height=1)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                (address, rtc * utxo_endpoints.ACCOUNT_UNIT),
            )
            conn.commit()

    def test_dual_write_sender_change_remains_spendable_on_second_transfer(self):
        self._seed(SENDER, 100)
        r1 = self.client.post("/utxo/transfer", json={
            "from_address": SENDER, "to_address": RECIPIENT,
            "amount_rtc": 10.0, "public_key": "aa" * 32, "signature": "bb" * 64, "nonce": 1,
        })
        self.assertEqual(r1.status_code, 200, r1.get_json())
        self.assertEqual(r1.get_json()["change_rtc"], 90.0)

        r2 = self.client.post("/utxo/transfer", json={
            "from_address": SENDER, "to_address": RECIPIENT,
            "amount_rtc": 15.0, "public_key": "aa" * 32, "signature": "bb" * 64, "nonce": 2,
        })
        self.assertEqual(r2.status_code, 200, r2.get_json())
        self.assertEqual(r2.get_json()["change_rtc"], 75.0)
        self.assertEqual(self.utxo_db.get_balance(SENDER), 75 * UNIT)
        self.assertEqual(self.utxo_db.get_balance(RECIPIENT), 25 * UNIT)

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT b.owner_address, b.output_index, m.box_id
                   FROM utxo_boxes AS b
                   LEFT JOIN account_mirror_boxes AS m ON m.box_id = b.box_id
                   WHERE b.owner_address IN (?, ?)
                   ORDER BY b.created_at, b.output_index""",
                (SENDER, RECIPIENT),
            ).fetchall()
        recipient_outputs = [r for r in rows if r[0] == RECIPIENT and r[1] == 0]
        sender_change = [r for r in rows if r[0] == SENDER and r[1] == 1]
        self.assertEqual(len(recipient_outputs), 2)
        self.assertTrue(all(r[2] is not None for r in recipient_outputs))
        self.assertEqual(len(sender_change), 2)
        self.assertTrue(all(r[2] is None for r in sender_change))

    def test_self_transfer_is_rejected(self):
        self._seed(SENDER, 100)
        r = self.client.post("/utxo/transfer", json={
            "from_address": SENDER, "to_address": SENDER,
            "amount_rtc": 10.0, "public_key": "aa" * 32, "signature": "bb" * 64, "nonce": 1,
        })
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertEqual(r.get_json().get("code"), "SELF_TRANSFER_NOT_ALLOWED")

    def test_mempool_pins_server_timestamp_and_rejects_missing_or_mismatched_apply(self):
        self._seed(SENDER, 50)
        box_id = self.utxo_db.get_unspent_for_address(SENDER)[0]["box_id"]
        admission_time = 1_700_000_000
        fee_nrtc = 1
        outputs = [{
            "address": RECIPIENT,
            "value_nrtc": 50 * UNIT - fee_nrtc,
            "tokens_json": "[]",
            "registers_json": "{}",
        }]
        identity = {
            "tx_type": "transfer",
            "inputs": [box_id],
            "data_inputs": [],
            "outputs": outputs,
            "fee_nrtc": fee_nrtc,
            "timestamp": admission_time,
            "block_height": 2,
        }
        canonical_tx_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        tx_without_timestamp = {
            "tx_id": canonical_tx_id,
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "test-fixture-proof"}],
            "outputs": outputs,
            "fee_nrtc": fee_nrtc,
        }

        with patch.object(utxo_db.time, "time", return_value=admission_time):
            self.assertTrue(self.utxo_db.mempool_add(tx_without_timestamp))

        with sqlite3.connect(self.db_path) as conn:
            raw = conn.execute(
                "SELECT tx_data_json FROM utxo_mempool WHERE tx_id = ?",
                (canonical_tx_id,),
            ).fetchone()[0]
        pinned_tx = json.loads(raw)
        self.assertEqual(pinned_tx["timestamp"], admission_time)

        # A later node clock must not silently substitute a new timestamp.
        with patch.object(utxo_db.time, "time", return_value=admission_time + 100):
            self.assertFalse(
                self.utxo_db.apply_transaction(tx_without_timestamp, block_height=2),
                "applying the original timestamp-less request must fail closed",
            )
            self.assertTrue(
                self.utxo_db.apply_transaction(pinned_tx, block_height=2),
                "the exact server-pinned mempool payload must apply",
            )

        with sqlite3.connect(self.db_path) as conn:
            applied = conn.execute(
                "SELECT timestamp FROM utxo_transactions WHERE tx_id = ?",
                (canonical_tx_id,),
            ).fetchone()
        self.assertIsNotNone(applied)
        self.assertEqual(applied[0], admission_time)
        self.assertEqual(self.utxo_db.get_balance(RECIPIENT), 50 * UNIT - fee_nrtc)



if __name__ == "__main__":
    unittest.main()
