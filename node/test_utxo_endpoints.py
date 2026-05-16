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
from decimal import Decimal

from flask import Flask

import utxo_endpoints
from utxo_db import (
    UtxoDB, UNIT, address_to_proposition, compute_box_id,
)
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
            '_allow_minting': True,
        }, block_height=height)

    def _seed_existing_box(self, address, value_nrtc, height=1):
        tx_id = '22' * 32
        prop = address_to_proposition(address)
        box_id = compute_box_id(value_nrtc, prop, height, tx_id, 0)
        self.utxo_db.add_box({
            'box_id': box_id,
            'value_nrtc': value_nrtc,
            'proposition': prop,
            'owner_address': address,
            'creation_height': height,
            'transaction_id': tx_id,
            'output_index': 0,
        })
        return box_id

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

    def test_transfer_rejects_non_object_json_body(self):
        for payload in ([{'from_address': 'alice'}], ['bad'], 'bad'):
            r = self.client.post('/utxo/transfer', json=payload)
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.get_json()['error'], 'JSON object body required')

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

    def test_transfer_float_precision(self):
        """0.1 RTC must convert to exactly 10_000_000 nanoRTC.

        Without Decimal: int(0.1 * 100_000_000) = 9_999_999 (truncation)
        With Decimal:    int(Decimal('0.1') * 100_000_000) = 10_000_000
        (bounty #2819 MED-3)
        """
        self._seed_coinbase('RTC_test_aabbccdd', 100 * UNIT)

        r = self.client.post('/utxo/transfer', json={
            'from_address': 'RTC_test_aabbccdd',
            'to_address': 'bob',
            'amount_rtc': 0.1,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(data['ok'])

        # Bob must have exactly 0.1 RTC = 10_000_000 nanoRTC
        bob_bal = self.utxo_db.get_balance('bob')
        self.assertEqual(bob_bal, 10_000_000,
                         f"Expected 10_000_000 nanoRTC, got {bob_bal} "
                         f"(float truncation bug)")

    def test_transfer_preserves_three_nanortc_amount(self):
        """Issue #4671: 0.00000003 RTC must transfer exactly 3 nanoRTC."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'bob'
        self._seed_coinbase(sender, UNIT)

        r = self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 0.00000003,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        data = r.get_json()

        self.assertEqual(r.status_code, 200, data)
        self.assertTrue(data['ok'])
        self.assertEqual(self.utxo_db.get_balance(recipient), 3)
        self.assertEqual(self.utxo_db.get_balance(sender), UNIT - 3)

    def test_transfer_rejects_decimal_amount_not_preserved_by_signed_float(self):
        """The signed float amount must match the ledger nanoRTC amount.

        Decimal parsing is exact, but the legacy signed payload serializes
        amount as a JSON float. These two inputs produce the same signed float
        while differing by 5 nanoRTC in ledger math.
        """
        base_amount = Decimal('1000000000.0')
        mutated_amount = Decimal('1000000000.00000005')
        self.assertEqual(float(base_amount), float(mutated_amount))

        sender = 'RTC_test_aabbccdd'
        recipient = 'bob'
        self._seed_existing_box(sender, int(mutated_amount * UNIT))

        signed_message = json.dumps({
            'from': sender,
            'to': recipient,
            'amount': float(base_amount),
            'fee': 0.0,
            'memo': '',
            'nonce': 424242,
        }, sort_keys=True, separators=(',', ':')).encode()

        old_verify = utxo_endpoints._verify_sig_fn

        def verify_base_amount(pubkey_hex, message, sig_hex):
            return sig_hex == 'valid-for-base' and message == signed_message

        try:
            utxo_endpoints._verify_sig_fn = verify_base_amount
            r = self.client.post('/utxo/transfer', json={
                'from_address': sender,
                'to_address': recipient,
                'amount_rtc': str(mutated_amount),
                'fee_rtc': '0',
                'public_key': 'aabbccdd' * 8,
                'signature': 'valid-for-base',
                'nonce': 424242,
            })
        finally:
            utxo_endpoints._verify_sig_fn = old_verify

        self.assertEqual(r.status_code, 400)
        self.assertIn('signed payload', r.get_json()['error'])
        self.assertEqual(self.utxo_db.get_balance(recipient), 0)

    def test_legacy_signature_rejects_nonzero_fee(self):
        """Legacy signatures omit fee_rtc, so they cannot authorize fees."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'bob'
        self._seed_coinbase(sender, 100 * UNIT)

        signed_message = json.dumps({
            'from': sender,
            'to': recipient,
            'amount': 10.0,
            'memo': '',
            'nonce': 515151,
        }, sort_keys=True, separators=(',', ':')).encode()

        old_verify = utxo_endpoints._verify_sig_fn

        def verify_legacy_only(pubkey_hex, message, sig_hex):
            return sig_hex == 'legacy-sig' and message == signed_message

        try:
            utxo_endpoints._verify_sig_fn = verify_legacy_only
            r = self.client.post('/utxo/transfer', json={
                'from_address': sender,
                'to_address': recipient,
                'amount_rtc': 10.0,
                'fee_rtc': 1.0,
                'public_key': 'aabbccdd' * 8,
                'signature': 'legacy-sig',
                'nonce': 515151,
            })
        finally:
            utxo_endpoints._verify_sig_fn = old_verify

        self.assertEqual(r.status_code, 401)
        self.assertEqual(
            r.get_json()['code'],
            'LEGACY_SIGNATURE_FEE_UNBOUND',
        )
        self.assertEqual(self.utxo_db.get_balance(sender), 100 * UNIT)
        self.assertEqual(self.utxo_db.get_balance(recipient), 0)

    def test_dual_write_rejects_non_string_memo_before_utxo_commit(self):
        """Non-string memo must not commit UTXO state then break shadow writes."""
        import sqlite3

        sender = 'RTC_test_aabbccdd'
        recipient = 'bob'
        self._seed_coinbase(sender, 100 * UNIT)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                (sender, 100_000_000),
            )
            conn.execute(
                """CREATE TABLE ledger (
                   ts INTEGER, epoch INTEGER, miner_id TEXT,
                   delta_i64 INTEGER, reason TEXT
                )"""
            )
            conn.commit()
        finally:
            conn.close()

        dual_app = Flask(__name__ + '_dual_write')
        dual_app.config['TESTING'] = True
        register_utxo_blueprint(
            dual_app, self.utxo_db, self.db_path,
            verify_sig_fn=mock_verify_sig,
            addr_from_pk_fn=mock_addr_from_pk,
            current_slot_fn=mock_current_slot,
            dual_write=True,
        )
        client = dual_app.test_client()

        for nonce, bad_memo in (
            (616161, {'not': 'a string'}),
            (616162, None),
            (616163, ['not', 'a', 'string']),
        ):
            with self.subTest(memo=bad_memo):
                r = client.post('/utxo/transfer', json={
                    'from_address': sender,
                    'to_address': recipient,
                    'amount_rtc': 10.0,
                    'public_key': 'aabbccdd' * 8,
                    'signature': 'sig' * 22,
                    'nonce': nonce,
                    'memo': bad_memo,
                })

                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.get_json()['error'], 'memo must be a string')
                self.assertEqual(self.utxo_db.get_balance(sender), 100 * UNIT)
                self.assertEqual(self.utxo_db.get_balance(recipient), 0)

                conn = sqlite3.connect(self.db_path)
                try:
                    balances = dict(conn.execute(
                        "SELECT miner_id, amount_i64 FROM balances"
                    ).fetchall())
                    ledger_count = conn.execute(
                        "SELECT COUNT(*) FROM ledger"
                    ).fetchone()[0]
                finally:
                    conn.close()

                self.assertEqual(balances[sender], 100_000_000)
                self.assertNotIn(recipient, balances)
                self.assertEqual(ledger_count, 0)


if __name__ == '__main__':
    unittest.main()
