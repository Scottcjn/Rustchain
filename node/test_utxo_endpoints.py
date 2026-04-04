"""
Tests for utxo_endpoints.py — UTXO Transaction Engine
======================================================

Run: python3 -m pytest test_utxo_endpoints.py -v
"""

import json
import os
import tempfile
import time
import unittest

from flask import Flask

from utxo_db import UtxoDB, UNIT
from utxo_endpoints import register_utxo_blueprint


# Mock crypto functions for testing
def mock_verify_sig(pubkey_hex, message, sig_hex):
    """Accept any signature in test mode."""
    return True


def mock_addr_from_pk(pubkey_hex):
    """Deterministic test address from pubkey."""
    return f"RTC_test_{pubkey_hex[:8]}"


def mock_current_slot():
    return 100


class TestUtxoEndpoints(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        # Create account model table for integrity checks
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
        conn.commit()
        conn.close()

        self.utxo_db = UtxoDB(self.db_path)
        self.utxo_db.init_tables()

        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        register_utxo_blueprint(
            self.app, self.utxo_db, self.db_path,
            verify_sig_fn=mock_verify_sig,
            addr_from_pk_fn=mock_addr_from_pk,
            current_slot_fn=mock_current_slot,
            dual_write=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    def _seed_coinbase(self, address, value_nrtc, height=1):
        return self.utxo_db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': value_nrtc}],
            'timestamp': int(time.time()),
        }, block_height=height)

    # -- read endpoints ------------------------------------------------------

    def test_balance_empty(self):
        r = self.client.get('/utxo/balance/nobody')
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(data['balance_nrtc'], 0)
        self.assertEqual(data['utxo_count'], 0)

    def test_balance_after_coinbase(self):
        self._seed_coinbase('alice', 100 * UNIT)
        r = self.client.get('/utxo/balance/alice')
        data = r.get_json()
        self.assertEqual(data['balance_nrtc'], 100 * UNIT)
        self.assertEqual(data['balance_rtc'], 100.0)
        self.assertEqual(data['utxo_count'], 1)

    def test_boxes_endpoint(self):
        self._seed_coinbase('bob', 50 * UNIT, height=1)
        self._seed_coinbase('bob', 30 * UNIT, height=2)
        r = self.client.get('/utxo/boxes/bob')
        data = r.get_json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['boxes']), 2)
        values = sorted(b['value_nrtc'] for b in data['boxes'])
        self.assertEqual(values, [30 * UNIT, 50 * UNIT])

    def test_box_not_found(self):
        r = self.client.get('/utxo/box/deadbeef' * 8)
        self.assertEqual(r.status_code, 404)

    def test_box_found(self):
        self._seed_coinbase('charlie', 75 * UNIT)
        boxes = self.utxo_db.get_unspent_for_address('charlie')
        box_id = boxes[0]['box_id']
        r = self.client.get(f'/utxo/box/{box_id}')
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(data['value_nrtc'], 75 * UNIT)
        self.assertFalse(data['spent'])

    def test_state_root(self):
        r = self.client.get('/utxo/state_root')
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertIn('state_root', data)
        self.assertEqual(len(data['state_root']), 64)

    def test_integrity_empty(self):
        r = self.client.get('/utxo/integrity')
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(data['ok'])

    def test_stats(self):
        self._seed_coinbase('alice', 100 * UNIT)
        r = self.client.get('/utxo/stats')
        data = r.get_json()
        self.assertEqual(data['unspent_boxes'], 1)
        self.assertEqual(data['total_value_nrtc'], 100 * UNIT)
        self.assertEqual(data['total_transactions'], 1)

    def test_mempool_empty(self):
        r = self.client.get('/utxo/mempool')
        data = r.get_json()
        self.assertEqual(data['count'], 0)

    # -- transfer endpoint ---------------------------------------------------

    def test_transfer_success(self):
        self._seed_coinbase('RTC_test_aabbccdd', 100 * UNIT)

        r = self.client.post('/utxo/transfer', json={
            'from_address': 'RTC_test_aabbccdd',
            'to_address': 'bob',
            'amount_rtc': 60.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(data['ok'])
        self.assertEqual(data['amount_rtc'], 60.0)
        self.assertEqual(data['model'], 'utxo')
        self.assertEqual(data['inputs_consumed'], 1)
        self.assertGreaterEqual(data['outputs_created'], 1)

        # Check balances
        self.assertEqual(self.utxo_db.get_balance('bob'), 60 * UNIT)
        sender_bal = self.utxo_db.get_balance('RTC_test_aabbccdd')
        self.assertEqual(sender_bal, 40 * UNIT)

    def test_transfer_insufficient(self):
        self._seed_coinbase('RTC_test_aabbccdd', 50 * UNIT)

        r = self.client.post('/utxo/transfer', json={
            'from_address': 'RTC_test_aabbccdd',
            'to_address': 'bob',
            'amount_rtc': 100.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertIn('Insufficient', data['error'])

    def test_transfer_missing_fields(self):
        r = self.client.post('/utxo/transfer', json={
            'from_address': 'alice',
            'to_address': 'bob',
        })
        self.assertEqual(r.status_code, 400)

    def test_transfer_zero_amount(self):
        r = self.client.post('/utxo/transfer', json={
            'from_address': 'RTC_test_aabbccdd',
            'to_address': 'bob',
            'amount_rtc': 0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': 123,
        })
        self.assertEqual(r.status_code, 400)

    def test_transfer_pubkey_mismatch(self):
        r = self.client.post('/utxo/transfer', json={
            'from_address': 'wrong_address',
            'to_address': 'bob',
            'amount_rtc': 10.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': 123,
        })
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertIn('does not match', data['error'])

    def test_transfer_with_fee(self):
        self._seed_coinbase('RTC_test_aabbccdd', 100 * UNIT)

        r = self.client.post('/utxo/transfer', json={
            'from_address': 'RTC_test_aabbccdd',
            'to_address': 'bob',
            'amount_rtc': 90.0,
            'fee_rtc': 1.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(data['ok'])
        # 100 - 90 - 1 fee = 9 change
        self.assertEqual(data['change_rtc'], 9.0)


if __name__ == '__main__':
    unittest.main()
