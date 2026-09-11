#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression test for the danaher-j #2819 RECEIVER-provenance double-spend.

Under UTXO_DUAL_WRITE=1, `balances` (account) is the primary ledger and UTXO
boxes are its shadow; `account_mirror_boxes` records which boxes back account
value, with the invariant `mirror <= balance`. A /utxo/transfer credits the
receiver's account balance AND creates a spendable UTXO output box for the
receiver. If that output is NOT registered as account-mirror provenance, the
same value is spendable via BOTH models (UTXO + account) = double spend.

Fix: the dual-write path registers the transfer's output boxes into
account_mirror_boxes, so the unconditional mirror-input exclusion blocks
re-spending them via the UTXO path (value must move via the account path).
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

from flask import Flask

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

import utxo_endpoints
from utxo_db import UtxoDB, UNIT
from utxo_endpoints import (
    register_utxo_blueprint,
    _selected_account_mirror_boxes,
    _spendable_utxo_candidates,
)


def _mock_verify_sig(pubkey_hex, message, sig_hex):
    return True


def _mock_addr_from_pk(pubkey_hex):
    return 'RTC_test_aabbccdd'


def _mock_current_slot():
    return 42


class TestDualWriteReceiverProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
        conn.commit()
        conn.close()

        self.utxo_db = UtxoDB(self.db_path)
        self.utxo_db.init_tables()

        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        register_utxo_blueprint(
            self.app, self.utxo_db, self.db_path,
            verify_sig_fn=_mock_verify_sig,
            addr_from_pk_fn=_mock_addr_from_pk,
            current_slot_fn=_mock_current_slot,
            dual_write=True,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _seed(self, address, rtc):
        """Give `address` both a spendable UTXO box and a matching account balance
        (a fully-migrated wallet: mirror == balance is maintained elsewhere; here
        the seeded box is independent UTXO, i.e. NOT yet a mirror)."""
        self.utxo_db.apply_transaction({
            'tx_type': 'mining_reward', 'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': rtc * UNIT}],
            'timestamp': int(time.time()), '_allow_minting': True,
        }, block_height=1)
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                     (address, rtc * utxo_endpoints.ACCOUNT_UNIT))
        conn.commit()
        conn.close()

    def _transfer(self, sender, recipient, amount_rtc, nonce):
        return self.client.post('/utxo/transfer', json={
            'from_address': sender, 'to_address': recipient,
            'amount_rtc': amount_rtc, 'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22, 'nonce': nonce, 'memo': 'x',
        })

    def test_receiver_output_is_registered_as_mirror(self):
        sender, recipient = 'RTC_test_aabbccdd', 'bob'
        self._seed(sender, 100)

        r = self._transfer(sender, recipient, 10.0, 700001)
        self.assertEqual(r.status_code, 200, r.get_json())

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Receiver account credited (the single spendable form).
            bal = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (recipient,)).fetchone()
            self.assertIsNotNone(bal)
            self.assertEqual(bal['amount_i64'], 10 * utxo_endpoints.ACCOUNT_UNIT)

            # Receiver's NEW output box must now be account-mirror provenance.
            recv_boxes = conn.execute(
                "SELECT box_id, value_nrtc FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL",
                (recipient,),
            ).fetchall()
            self.assertEqual(len(recv_boxes), 1)
            mirror = conn.execute(
                "SELECT box_id FROM account_mirror_boxes WHERE account_wallet=?", (recipient,)
            ).fetchall()
            mirror_ids = {m['box_id'] for m in mirror}
            self.assertIn(recv_boxes[0]['box_id'], mirror_ids,
                          "receiver output box was NOT registered as account-mirror (danaher #2819 residual)")

            # Therefore it is excluded from UTXO coin-selection (cannot be UTXO-spent).
            excluded = _selected_account_mirror_boxes(conn, [dict(box_id=recv_boxes[0]['box_id'])])
            self.assertEqual(excluded, [recv_boxes[0]['box_id']])
        finally:
            conn.close()

    def test_receiver_box_is_not_utxo_spendable(self):
        """The value the receiver got is spendable via the ACCOUNT path only: its
        UTXO output box is now mirror-tagged, so UTXO coin-selection excludes it
        entirely — the receiver cannot re-spend it through /utxo/transfer, which
        is exactly what closes the double-spend."""
        sender, recipient = 'RTC_test_aabbccdd', 'bob'
        self._seed(sender, 100)
        self.assertEqual(self._transfer(sender, recipient, 10.0, 700001).status_code, 200)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            recv_boxes = [dict(r) for r in conn.execute(
                "SELECT * FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL",
                (recipient,),
            ).fetchall()]
            self.assertEqual(len(recv_boxes), 1)
            spendable, mirrored = _spendable_utxo_candidates(conn, recv_boxes)
            self.assertEqual(spendable, [], "receiver box is UTXO-spendable — double-spend open")
            self.assertEqual(mirrored, [recv_boxes[0]['box_id']])
        finally:
            conn.close()

    def test_invariant_holds_after_transfer(self):
        sender, recipient = 'RTC_test_aabbccdd', 'bob'
        self._seed(sender, 100)
        self.assertEqual(self._transfer(sender, recipient, 10.0, 700001).status_code, 200)

        conn = sqlite3.connect(self.db_path)
        try:
            nrtc_per_account = UNIT // utxo_endpoints.ACCOUNT_UNIT
            for w in (sender, recipient):
                mirror = conn.execute(
                    "SELECT COALESCE(SUM(b.value_nrtc),0) FROM utxo_boxes b "
                    "JOIN account_mirror_boxes m ON m.box_id=b.box_id "
                    "WHERE m.account_wallet=? AND b.spent_at IS NULL", (w,)).fetchone()[0]
                brow = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (w,)).fetchone()
                bal_nrtc = (brow[0] if brow else 0) * nrtc_per_account
                self.assertLessEqual(int(mirror), bal_nrtc, f"mirror>balance for {w} (double-spend condition)")
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
