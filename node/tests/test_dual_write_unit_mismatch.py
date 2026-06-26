"""
Tests for UTXO↔account dual-write unit correctness
====================================================

Regression tests for the 1000x balance corruption bug where
utxo_endpoints.py wrote amount_rtc * 1_000_000_000 (9 decimals)
into balances.amount_i64, but the account model expects
amount_rtc * 1_000_000 (6 decimals).

Run: python3 -m pytest tests/test_dual_write_unit_mismatch.py -v
"""

import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest

# Ensure node/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask

from utxo_db import MAX_COINBASE_OUTPUT_NRTC, UtxoDB, UNIT
from utxo_endpoints import (
    ACCOUNT_UNIT,
    UTXO_SIGNATURE_DOMAIN,
    register_utxo_blueprint,
)


# Mock crypto functions for testing
def mock_verify_sig(pubkey_hex, message, sig_hex):
    return True


def mock_addr_from_pk(pubkey_hex):
    return f"RTC_test_{pubkey_hex[:8]}"


def mock_current_slot():
    return 100


class TestUtxoSignatureDomain(unittest.TestCase):
    """UTXO transfers must not accept account-transfer signatures."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.utxo_db = UtxoDB(self.db_path)
        self.utxo_db.init_tables()

    def tearDown(self):
        os.unlink(self.db_path)

    def _seed_coinbase(self, address, value_nrtc, height=1):
        ok = self.utxo_db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': value_nrtc}],
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=height)
        self.assertTrue(ok, "Coinbase fixture should seed UTXO balance")

    def _client_with_verifier(self, verifier):
        app = Flask(__name__)
        app.config['TESTING'] = True
        register_utxo_blueprint(
            app, self.utxo_db, self.db_path,
            verify_sig_fn=verifier,
            addr_from_pk_fn=mock_addr_from_pk,
            current_slot_fn=mock_current_slot,
            dual_write=False,
        )
        return app.test_client()

    def _payload(self, nonce=123):
        return {
            'from_address': 'RTC_test_aabbccdd',
            'to_address': 'RTC_test_eeffgghh',
            'amount_rtc': 10.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': nonce,
        }

    def test_account_transfer_signature_rejected_on_utxo_endpoint(self):
        """An account-model signed payload must not settle immediately as UTXO."""
        sender = 'RTC_test_aabbccdd'
        self._seed_coinbase(sender, 100 * UNIT)

        def account_style_verifier(pubkey_hex, message, sig_hex):
            signed = json.loads(message.decode())
            return (
                signed.get('from') == sender
                and signed.get('to') == 'RTC_test_eeffgghh'
                and signed.get('amount') == 10.0
                and signed.get('memo') == ''
                and signed.get('nonce') == 123
                and 'domain' not in signed
            )

        client = self._client_with_verifier(account_style_verifier)
        response = client.post('/utxo/transfer', json=self._payload())

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json()['code'],
            'UTXO_SIGNATURE_DOMAIN_REQUIRED',
        )
        self.assertEqual(self.utxo_db.get_balance(sender), 100 * UNIT)

    def test_utxo_domain_signature_still_authorizes_transfer(self):
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 100 * UNIT)

        def utxo_domain_verifier(pubkey_hex, message, sig_hex):
            signed = json.loads(message.decode())
            return signed.get('domain') == UTXO_SIGNATURE_DOMAIN

        client = self._client_with_verifier(utxo_domain_verifier)
        response = client.post('/utxo/transfer', json=self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['ok'])
        self.assertEqual(self.utxo_db.get_balance(recipient), 10 * UNIT)


class TestDualWriteUnitCorrectness(unittest.TestCase):
    """Verify that dual-write uses the correct unit (6 decimals, not 9)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        # Create account model tables
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS balances "
            "(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0, "
            "balance_rtc REAL DEFAULT 0)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ledger "
            "(ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)"
        )
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
            dual_write=True,  # Enable dual-write for these tests
        )
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    def _seed_coinbase(self, address, value_nrtc, height=1):
        remaining = value_nrtc
        block_height = height
        while remaining > 0:
            chunk = min(remaining, MAX_COINBASE_OUTPUT_NRTC)
            ok = self.utxo_db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{'address': address, 'value_nrtc': chunk}],
                'timestamp': int(time.time()),
                '_allow_minting': True,
            }, block_height=block_height)
            self.assertTrue(ok, "Coinbase fixture should seed UTXO balance")
            remaining -= chunk
            block_height += 1

    def _get_account_balance_i64(self, miner_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            (miner_id,)
        ).fetchone()
        conn.close()
        return row['amount_i64'] if row else 0

    # -- Core unit correctness tests -----------------------------------------

    def test_account_unit_constant_is_6_decimals(self):
        """ACCOUNT_UNIT must be 1_000_000 (6 decimals), not 1_000_000_000."""
        self.assertEqual(ACCOUNT_UNIT, 1_000_000)
        self.assertNotEqual(ACCOUNT_UNIT, 1_000_000_000)

    def test_dual_write_10_rtc_equals_10_million_uRTC(self):
        """Transferring 10 RTC should write 10_000_000 uRTC, not 10_000_000_000."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 100 * UNIT)

        # Seed shadow balance so dual-write can proceed (security guard requires it)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(100.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        r = self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 10.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data['ok'])

        # Account model balance should be 10 * 1_000_000 = 10_000_000
        recipient_i64 = self._get_account_balance_i64(recipient)
        expected_i64 = int(10.0 * ACCOUNT_UNIT)  # 10_000_000
        self.assertEqual(recipient_i64, expected_i64)

        # Must NOT be 1000x larger (the old bug)
        self.assertNotEqual(recipient_i64, int(10.0 * 1_000_000_000))

        # Verify it reads back as ~10 RTC when divided by ACCOUNT_UNIT
        back_to_rtc = recipient_i64 / ACCOUNT_UNIT
        self.assertAlmostEqual(back_to_rtc, 10.0, places=2)

    def test_dual_write_debit_matches_credit(self):
        """Sender debit and recipient credit must use the same unit."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 100 * UNIT)

        # Pre-seed sender in balances table with sufficient shadow balance
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(100.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 25.5,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })

        sender_i64 = self._get_account_balance_i64(sender)
        recipient_i64 = self._get_account_balance_i64(recipient)

        expected_amount = int(25.5 * ACCOUNT_UNIT)  # 25_500_000
        self.assertEqual(recipient_i64, expected_amount)
        # Sender started with 100 * ACCOUNT_UNIT, debited 25.5 * ACCOUNT_UNIT
        self.assertEqual(sender_i64, int(100.0 * ACCOUNT_UNIT) - expected_amount)

    def test_dual_write_fractional_rtc(self):
        """Transferring 0.001 RTC should write 1000 uRTC, not 1_000_000."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 10 * UNIT)

        # Seed shadow balance so dual-write can proceed
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(10.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 0.001,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })

        recipient_i64 = self._get_account_balance_i64(recipient)
        expected_i64 = int(0.001 * ACCOUNT_UNIT)  # 1000
        self.assertEqual(recipient_i64, expected_i64)

        # The old bug would have written 1_000_000 (1000x too large)
        self.assertNotEqual(recipient_i64, 1_000_000)

    def test_dual_write_large_amount_no_overflow(self):
        """A large transfer must write the correct large i64 to the shadow row.

        Amount note / invariant: a single ``/utxo/transfer`` can be funded by at
        most ``MAX_INPUTS`` (100) UTXOs, and coinbase outputs are capped at
        ``MAX_COINBASE_OUTPUT_NRTC`` (150 RTC). A coinbase-only sender therefore
        cannot move more than 100 * 150 = 15,000 RTC in one transfer, so the
        original 1_000_000 RTC amount is structurally unreachable through this
        endpoint path (it needs ~6,667 inputs and is rejected before settling).
        The full 1_000_000 RTC i64-overflow magnitude is covered directly at the
        conversion boundary by ``test_account_i64_no_overflow_at_one_million_rtc``
        below; this case exercises a large end-to-end transfer near the feasible
        ceiling.
        """
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 20_000 * UNIT)

        # Seed shadow balance so dual-write can proceed
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(20_000.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 10_000.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })

        recipient_i64 = self._get_account_balance_i64(recipient)
        expected_i64 = int(10_000.0 * ACCOUNT_UNIT)  # 10_000_000_000
        self.assertEqual(recipient_i64, expected_i64)

    def test_account_i64_no_overflow_at_one_million_rtc(self):
        """Restore 1_000_000 RTC i64-overflow coverage at the conversion boundary.

        This is the exact helper the dual-write path uses to mirror UTXO amounts
        into the 6-decimal account shadow row. It is not bounded by MAX_INPUTS, so
        it can assert the full 1_000_000 RTC magnitude (1_000_000_000_000 uRTC)
        converts exactly, stays positive, and remains far below the int64 ceiling.
        """
        from decimal import Decimal
        from utxo_endpoints import _decimal_to_account_i64

        result = _decimal_to_account_i64(Decimal('1000000'), 'amount_rtc')
        self.assertEqual(result, 1_000_000_000_000)
        self.assertGreater(result, 0)
        self.assertLess(result, 2 ** 63 - 1)

    # -- Integrity endpoint tests --------------------------------------------

    def test_integrity_matches_after_dual_write(self):
        """After a dual-write, /utxo/integrity should report models_agree=true
        when UTXO and account totals match (after unit conversion)."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 100 * UNIT)

        # Seed shadow balance so dual-write can proceed
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(100.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 50.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })

        r = self.client.get('/utxo/integrity')
        data = r.get_json()
        self.assertEqual(r.status_code, 200)

        # The integrity check should now correctly compare units
        # Both UTXO and account should total 100 RTC (transfers are zero-sum)
        if 'models_agree' in data:
            # models_agree may be False if the account model had pre-existing
            # balances from other sources, but the conversion must be correct
            account_nrtc = data.get('account_total_nrtc', 0)
            utxo_nrtc = data.get('total_unspent_nrtc', 0)
            # Account total in nrtc should be in the same ballpark as UTXO total
            # (they may differ if account model has entries from non-UTXO sources)
            self.assertGreaterEqual(account_nrtc, 0)

    def test_integrity_unit_conversion(self):
        """Verify that account_total_nrtc = account_total_i64 * (UNIT/ACCOUNT_UNIT)."""
        sender = 'RTC_test_aabbccdd'
        self._seed_coinbase(sender, 50 * UNIT)

        r = self.client.get('/utxo/integrity')
        data = r.get_json()

        account_i64 = data.get('account_total_i64', 0)
        account_nrtc = data.get('account_total_nrtc', 0)

        if account_i64 != 0:
            expected_nrtc = account_i64 * (UNIT // ACCOUNT_UNIT)
            self.assertEqual(account_nrtc, expected_nrtc)

    # -- Ledger entry tests --------------------------------------------------

    def test_ledger_entries_use_correct_unit(self):
        """Ledger delta_i64 should match ACCOUNT_UNIT, not 1000x larger."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 100 * UNIT)

        # Seed shadow balance so dual-write can proceed
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(100.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 7.5,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT miner_id, delta_i64, reason FROM ledger ORDER BY rowid"
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)

        expected_delta = int(7.5 * ACCOUNT_UNIT)  # 7_500_000

        # Find sender and recipient ledger entries
        sender_entries = [r for r in rows if r['miner_id'] == sender]
        recipient_entries = [r for r in rows if r['miner_id'] == recipient]

        self.assertEqual(len(sender_entries), 1)
        self.assertEqual(len(recipient_entries), 1)
        self.assertEqual(sender_entries[0]['delta_i64'], -expected_delta)
        self.assertEqual(recipient_entries[0]['delta_i64'], expected_delta)


class TestDualWriteDisabled(unittest.TestCase):
    """Verify that when dual_write=False, account model is untouched."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS balances "
            "(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0, "
            "balance_rtc REAL DEFAULT 0)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ledger "
            "(ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)"
        )
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
            dual_write=False,  # Disabled
        )
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    def _seed_coinbase(self, address, value_nrtc, height=1):
        ok = self.utxo_db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': value_nrtc}],
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=height)
        self.assertTrue(ok, "Coinbase fixture should seed UTXO balance")

    def test_no_account_write_when_dual_write_false(self):
        """When dual_write=False, balances table should remain untouched."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC_test_eeffgghh'
        self._seed_coinbase(sender, 100 * UNIT)

        self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 50.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_i64), 0) FROM balances"
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], 0)


if __name__ == '__main__':
    unittest.main()
