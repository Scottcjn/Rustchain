"""
Tests for UTXO dual-write shadow-balance guard
===============================================

Regression tests for the negative-balance minting vulnerability in the
UTXO→account-model dual-write bridge.  Even when units are correct (#2095)
and confirm_transaction re-checks balances (#2094), the dual-write path
in utxo_endpoints.py had no balance guard on the shadow-ledger debit.

When the account-model balance diverges from the UTXO balance (via non-UTXO
writes, prior dual-write failures, admin ops, or races), the dual-write
UPDATE silently drives amount_i64 negative — minting funds in the shadow
ledger.

Run: python3 -m pytest tests/test_dual_write_shadow_balance.py -v
"""

import os
import sqlite3
import sys
import tempfile
import time
import unittest

# Ensure node/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask

from utxo_db import UtxoDB, UNIT
from utxo_endpoints import register_utxo_blueprint, ACCOUNT_UNIT


# Mock crypto functions for testing
def mock_verify_sig(pubkey_hex, message, sig_hex):
    return True


def mock_addr_from_pk(pubkey_hex):
    return f"RTC_test_{pubkey_hex[:8]}"


def mock_current_slot():
    return 100


class TestDualWriteShadowBalanceGuard(unittest.TestCase):
    """Dual-write must not drive the shadow ledger negative."""

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
            dual_write=True,
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

    def _unspent_utxo_nrtc(self, address):
        """Unspent UTXO value for an address — proves the UTXO side rolled back."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(value_nrtc), 0) FROM utxo_boxes "
                "WHERE owner_address = ? AND spent_at IS NULL", (address,)).fetchone()
            return row[0]
        finally:
            conn.close()

    def _get_account_balance_i64(self, miner_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            (miner_id,)
        ).fetchone()
        conn.close()
        return row['amount_i64'] if row else 0

    # -- Core guard tests ----------------------------------------------------

    def test_dual_write_refused_when_shadow_balance_insufficient(self):
        """If sender shadow balance < transfer amount, dual-write must be
        skipped (not drive amount_i64 negative)."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC' + 'e' * 40  # canonical form; recipients are format-checked since #2819

        # Seed UTXO with 100 RTC
        self._seed_coinbase(sender, 100 * UNIT)

        # But shadow ledger only has 5 RTC (diverged via non-UTXO writes)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(5.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        # Try to transfer 10 RTC — UTXO has enough, shadow does not
        r = self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 10.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        data = r.get_json()
        # #7928 made this FAIL CLOSED. Letting the UTXO spend through while
        # skipping the account write is exactly the success-path divergence the
        # dual-write model exists to prevent (/utxo/integrity would then report
        # the models disagreeing while the endpoint returned ok=True).
        self.assertEqual(r.status_code, 409, data)
        self.assertEqual(data['code'], 'DUAL_WRITE_SHADOW_BALANCE')
        self.assertEqual(data['shadow_balance_i64'], int(5.0 * ACCOUNT_UNIT))

        # Nothing moved in either model.
        self.assertEqual(self._get_account_balance_i64(sender), int(5.0 * ACCOUNT_UNIT))
        self.assertEqual(self._get_account_balance_i64(recipient), 0)
        self.assertEqual(self._unspent_utxo_nrtc(sender), 100 * UNIT,
                         "UTXO side must be rolled back too")

    def test_dual_write_refused_when_sender_missing_from_shadow(self):
        """A sender with no balances row cannot back the spend: the transfer is
        refused and the UTXO side rolled back (not silently half-applied)."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC' + 'e' * 40  # canonical form; recipients are format-checked since #2819

        self._seed_coinbase(sender, 100 * UNIT)

        # Do NOT insert sender into balances — shadow balance = 0

        r = self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 10.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        data = r.get_json()
        # Fail closed (#7928): a sender with no account row cannot back the
        # spend, so the UTXO application is rolled back rather than creating
        # value that exists only in the UTXO model.
        self.assertEqual(r.status_code, 409, data)
        self.assertEqual(data['code'], 'DUAL_WRITE_SHADOW_BALANCE')
        self.assertEqual(data['shadow_balance_i64'], 0)

        self.assertEqual(self._get_account_balance_i64(sender), 0)
        self.assertEqual(self._get_account_balance_i64(recipient), 0)
        self.assertEqual(self._unspent_utxo_nrtc(sender), 100 * UNIT,
                         "UTXO side must be rolled back too")

    def test_dual_write_succeeds_when_shadow_sufficient(self):
        """Normal dual-write path still works when shadow balance is enough."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC' + 'e' * 40  # canonical form; recipients are format-checked since #2819

        self._seed_coinbase(sender, 100 * UNIT)

        # Seed shadow ledger with matching balance
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
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(data['ok'])

        sender_i64 = self._get_account_balance_i64(sender)
        recipient_i64 = self._get_account_balance_i64(recipient)

        self.assertEqual(sender_i64, int(90.0 * ACCOUNT_UNIT))
        self.assertEqual(recipient_i64, int(10.0 * ACCOUNT_UNIT))

    def test_dual_write_exact_balance_goes_to_zero(self):
        """Transferring exactly the shadow balance should succeed (goes to 0)."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC' + 'e' * 40  # canonical form; recipients are format-checked since #2819

        # Consistent dual-write state: the sender's UTXO value equals its account
        # balance. (With 100 RTC of UTXO against a 10 RTC account, the 90 RTC
        # change output is registered as an account mirror and the
        # MIRROR_EXCEEDS_BALANCE guard correctly fails closed.)
        self._seed_coinbase(sender, 10 * UNIT)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(10.0 * ACCOUNT_UNIT)),
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
        data = r.get_json()
        self.assertTrue(data['ok'])

        sender_i64 = self._get_account_balance_i64(sender)
        self.assertEqual(sender_i64, 0)

    def test_no_leder_entries_when_dual_write_skipped(self):
        """When dual-write is skipped due to insufficient shadow balance,
        no ledger entries should be created."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC' + 'e' * 40  # canonical form; recipients are format-checked since #2819

        self._seed_coinbase(sender, 100 * UNIT)

        # Shadow has only 5 RTC, trying to send 10
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (sender, int(5.0 * ACCOUNT_UNIT)),
        )
        conn.commit()
        conn.close()

        self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 10.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM ledger WHERE miner_id IN (?, ?)",
            (sender, recipient),
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 0)


class TestDualWriteShadowBalanceGuardDisabled(unittest.TestCase):
    """Verify guard doesn't affect dual_write=False path."""

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
            dual_write=False,
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

    def test_utxo_succeeds_when_dual_write_disabled(self):
        """UTXO transfer succeeds regardless of shadow balance when
        dual_write=False."""
        sender = 'RTC_test_aabbccdd'
        recipient = 'RTC' + 'e' * 40  # canonical form; recipients are format-checked since #2819
        self._seed_coinbase(sender, 100 * UNIT)

        r = self.client.post('/utxo/transfer', json={
            'from_address': sender,
            'to_address': recipient,
            'amount_rtc': 50.0,
            'public_key': 'aabbccdd' * 8,
            'signature': 'sig' * 22,
            'nonce': int(time.time() * 1000),
        })
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(data['ok'])

        # UTXO balance updated correctly
        self.assertEqual(self.utxo_db.get_balance(sender), 50 * UNIT)
        self.assertEqual(self.utxo_db.get_balance(recipient), 50 * UNIT)


if __name__ == '__main__':
    unittest.main()


class TestTransferRecipientFormat(unittest.TestCase):
    """#2819 (reported by @antoleod): a non-canonical to_address must be rejected
    before signature verification or any state mutation, or the RTC lands in a
    box no wallet key can ever spend."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
        conn.commit(); conn.close()
        self.utxo_db = UtxoDB(self.db_path); self.utxo_db.init_tables()
        self.app = Flask(__name__); self.app.config['TESTING'] = True
        register_utxo_blueprint(self.app, self.utxo_db, self.db_path,
                                verify_sig_fn=mock_verify_sig, addr_from_pk_fn=mock_addr_from_pk,
                                current_slot_fn=mock_current_slot, dual_write=False)
        self.client = self.app.test_client()

    def tearDown(self):
        try: os.unlink(self.db_path)
        except OSError: pass

    def _post(self, to_address):
        pk = 'aa' * 32
        return self.client.post('/utxo/transfer', json={
            'from_address': mock_addr_from_pk(pk), 'to_address': to_address,
            'amount_rtc': '0.1', 'fee_rtc': '0', 'nonce': 1,
            'public_key': pk, 'signature': 'bb' * 64,
        })

    def test_rejects_arbitrary_string_recipient(self):
        for bad in ('not-a-wallet', 'RTC' + 'g' * 40, 'RTC' + 'a' * 39, 'rtc' + 'a' * 40, 'bcn_something'):
            resp = self._post(bad)
            self.assertEqual(resp.status_code, 400, bad)
            self.assertEqual(resp.get_json()['error'], 'invalid_to_address_format', bad)
        self.assertEqual(self.utxo_db.get_balance('not-a-wallet') if hasattr(self.utxo_db, 'get_balance') else 0, 0)

    def test_rejects_non_canonical_case_recipient(self):
        """#2819 (Ondrej Nad): derivation yields lower-case hex, and ownership is
        matched case-sensitively, so an upper/mixed-case recipient would create a
        box no key can ever spend. It must be rejected before any state change."""
        canonical = 'RTC' + 'abcdef0123' * 4
        for bad in ('RTC' + 'Abcdef0123' * 4, 'RTC' + 'ABCDEF0123' * 4,
                    canonical[:-1] + 'F'):
            resp = self._post(bad)
            self.assertEqual(resp.status_code, 400, bad)
            self.assertEqual(resp.get_json()['error'], 'invalid_to_address_format', bad)
        resp = self._post(canonical)
        self.assertNotEqual((resp.get_json() or {}).get('error'), 'invalid_to_address_format')

    def test_canonical_recipient_passes_format_check(self):
        resp = self._post('RTC' + 'c' * 40)
        # Anything but the format error: the request proceeds to the normal path.
        self.assertNotEqual((resp.get_json() or {}).get('error'), 'invalid_to_address_format')
