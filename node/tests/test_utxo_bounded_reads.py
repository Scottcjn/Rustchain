"""
Tests for FIX(#13975): bound the per-address public read path.

Covers the new helpers on `UtxoDB` and the public routes:
  * `/utxo/balance/<address>` must use a scalar `COUNT(*)` so its cost
    is independent of the box count.
  * `/utxo/boxes/<address>` must require a `?limit=` and `?offset=`,
    clamp `limit` to `MAX_BOXES_PER_PAGE`, and surface `has_more` +
    `next_offset` so callers can page a fragmented address.
  * `UtxoDB.get_unspent_for_address` (the internal full-read helper
    used by coin selection) must still work for normal wallets, but
    must refuse to silently materialize more than `MAX_BOXES_INTERNAL`
    rows in one call.

Run: python3 -m pytest test_utxo_bounded_reads.py -v
"""

import json
import os
import sqlite3
import tempfile
import time
import unittest
from decimal import Decimal

from flask import Flask

import utxo_endpoints
from utxo_db import (
    DUST_THRESHOLD,
    UNIT,
    UtxoDB,
    address_to_proposition,
    compute_box_id,
)
from utxo_endpoints import register_utxo_blueprint


def _mock_verify_sig(pubkey_hex, message, sig_hex):
    return True


def _mock_addr_from_pk(pubkey_hex):
    return f"RTC_test_{pubkey_hex[:8]}"


def _mock_current_slot():
    return 100


def _seed_coinbase(db, address, value_nrtc, height=1):
    return db.apply_transaction({
        'tx_type': 'mining_reward',
        'inputs': [],
        'outputs': [{'address': address, 'value_nrtc': value_nrtc}],
        'timestamp': int(time.time()),
        '_allow_minting': True,
    }, block_height=height)


def _seed_existing_box(db, address, value_nrtc, height=1, tx_id=None, output_index=0):
    if tx_id is None:
        # Use a unique hex tx_id per box so the (transaction_id, output_index)
        # unique index does not collide when we seed many boxes in one test,
        # and so `compute_box_id` (which calls bytes.fromhex on it) succeeds.
        unique = f"{int(time.time() * 1_000_000):x}{height:x}{output_index:x}"
        tx_id = unique.ljust(64, '0')[:64]
    prop = address_to_proposition(address)
    box_id = compute_box_id(value_nrtc, prop, height, tx_id, output_index)
    db.add_box({
        'box_id': box_id,
        'value_nrtc': value_nrtc,
        'proposition': prop,
        'owner_address': address,
        'creation_height': height,
        'transaction_id': tx_id,
        'output_index': output_index,
    })
    return box_id


class TestUtxoDBCountForAddress(unittest.TestCase):
    """`get_unspent_count_for_address` is a cheap scalar COUNT(*)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_count_empty(self):
        self.assertEqual(self.db.get_unspent_count_for_address('nobody'), 0)

    def test_count_matches_coinbase(self):
        _seed_coinbase(self.db, 'alice', 100 * UNIT)
        _seed_coinbase(self.db, 'alice', 30 * UNIT, height=2)
        self.assertEqual(self.db.get_unspent_count_for_address('alice'), 2)

    def test_count_excludes_spent(self):
        # A 0-value transfer spends one box, so the count drops by 1.
        box_id = _seed_existing_box(self.db, 'alice', 50 * UNIT)
        _seed_existing_box(self.db, 'alice', 50 * UNIT, height=2)
        self.assertEqual(self.db.get_unspent_count_for_address('alice'), 2)
        # Mark the first box spent directly
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE utxo_boxes SET spent_at = ?, spent_by_tx = ? WHERE box_id = ?",
            (int(time.time()), '00' * 32, box_id),
        )
        conn.commit()
        conn.close()
        self.assertEqual(self.db.get_unspent_count_for_address('alice'), 1)


class TestUtxoDBPagedRead(unittest.TestCase):
    """`get_unspent_for_address_paged` is bounded and stable."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_paged_basic(self):
        for i in range(5):
            _seed_coinbase(self.db, 'bob', (i + 1) * UNIT, height=i + 1)
        page, has_more = self.db.get_unspent_for_address_paged(
            'bob', limit=3, offset=0
        )
        self.assertEqual(len(page), 3)
        self.assertTrue(has_more)
        # Ordered by value ASC, so the first 3 are 1, 2, 3 RTC
        self.assertEqual([p['value_nrtc'] for p in page], [UNIT, 2 * UNIT, 3 * UNIT])

    def test_paged_exact_last_page(self):
        for i in range(5):
            _seed_coinbase(self.db, 'bob', (i + 1) * UNIT, height=i + 1)
        page, has_more = self.db.get_unspent_for_address_paged(
            'bob', limit=10, offset=0
        )
        self.assertEqual(len(page), 5)
        self.assertFalse(has_more)

    def test_paged_offset_skips(self):
        for i in range(5):
            _seed_coinbase(self.db, 'bob', (i + 1) * UNIT, height=i + 1)
        page, has_more = self.db.get_unspent_for_address_paged(
            'bob', limit=2, offset=2
        )
        self.assertEqual([p['value_nrtc'] for p in page], [3 * UNIT, 4 * UNIT])
        self.assertTrue(has_more)

    def test_paged_clamps_oversize_limit(self):
        # Caller asks for more than the hard cap; helper clamps to MAX_BOXES_PER_PAGE.
        page, has_more = self.db.get_unspent_for_address_paged(
            'bob', limit=10_000, offset=0
        )
        self.assertLessEqual(len(page), UtxoDB.MAX_BOXES_PER_PAGE)

    def test_paged_rejects_negative(self):
        with self.assertRaises(ValueError):
            self.db.get_unspent_for_address_paged('bob', limit=-1, offset=0)
        with self.assertRaises(ValueError):
            self.db.get_unspent_for_address_paged('bob', limit=1, offset=-1)

    def test_paged_empty_address(self):
        page, has_more = self.db.get_unspent_for_address_paged(
            'nobody', limit=50, offset=0
        )
        self.assertEqual(page, [])
        self.assertFalse(has_more)


class TestUtxoDBInternalCap(unittest.TestCase):
    """`get_unspent_for_address` (the internal full read) is bounded."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_internal_read_normal_wallet(self):
        for i in range(3):
            _seed_coinbase(self.db, 'alice', (i + 1) * UNIT, height=i + 1)
        # 3 boxes is well below MAX_BOXES_INTERNAL, so this must succeed.
        boxes = self.db.get_unspent_for_address('alice')
        self.assertEqual(len(boxes), 3)

    def test_internal_read_refuses_fragmented(self):
        # Bypass the public endpoint and seed `MAX_BOXES_INTERNAL + 1` rows
        # directly via add_box so the coin-selection internal helper is
        # exercised in the fragmented regime without us having to mine
        # 50k blocks. We temporarily shrink the cap to a small number so
        # the test stays fast.
        original_cap = UtxoDB.MAX_BOXES_INTERNAL
        UtxoDB.MAX_BOXES_INTERNAL = 5  # pyright: ignore[reportAttributeAccessIssue]
        try:
            for i in range(UtxoDB.MAX_BOXES_INTERNAL + 1):
                _seed_existing_box(
                    self.db, 'fragmented', DUST_THRESHOLD,
                    height=1, output_index=i,
                )
            with self.assertRaises(ValueError) as ctx:
                self.db.get_unspent_for_address('fragmented')
            self.assertIn("more than", str(ctx.exception))
        finally:
            UtxoDB.MAX_BOXES_INTERNAL = original_cap


class TestUtxoEndpointsBounded(unittest.TestCase):
    """Public routes must use the bounded helpers and reject bad paging."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
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
            verify_sig_fn=_mock_verify_sig,
            addr_from_pk_fn=_mock_addr_from_pk,
            current_slot_fn=_mock_current_slot,
            dual_write=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_balance_does_not_materialize_rows(self):
        # Seed 5 boxes and verify the balance route returns the count
        # correctly while using the scalar COUNT(*) path.
        for i in range(5):
            _seed_coinbase(self.utxo_db, 'alice', (i + 1) * UNIT, height=i + 1)
        r = self.client.get('/utxo/balance/alice')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data['balance_nrtc'], sum((i + 1) * UNIT for i in range(5)))
        self.assertEqual(data['utxo_count'], 5)

    def test_boxes_default_page(self):
        for i in range(5):
            _seed_coinbase(self.utxo_db, 'alice', (i + 1) * UNIT, height=i + 1)
        r = self.client.get('/utxo/boxes/alice')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        # Default page size is 50, so all 5 fit and has_more is False.
        self.assertEqual(data['count'], 5)
        self.assertEqual(data['limit'], 50)
        self.assertEqual(data['offset'], 0)
        self.assertFalse(data['has_more'])
        self.assertIsNone(data['next_offset'])
        self.assertFalse(data['truncated'])

    def test_boxes_paging(self):
        for i in range(5):
            _seed_coinbase(self.utxo_db, 'alice', (i + 1) * UNIT, height=i + 1)
        # Page 1: limit=2, offset=0 -> 2 boxes, has_more=True
        r = self.client.get('/utxo/boxes/alice?limit=2&offset=0')
        data = r.get_json()
        self.assertEqual(data['count'], 2)
        self.assertTrue(data['has_more'])
        self.assertTrue(data['truncated'])
        self.assertEqual(data['next_offset'], 2)

        # Page 2: limit=2, offset=2 -> 2 boxes, has_more=True
        r = self.client.get('/utxo/boxes/alice?limit=2&offset=2')
        data = r.get_json()
        self.assertEqual(data['count'], 2)
        self.assertTrue(data['has_more'])
        self.assertEqual(data['next_offset'], 4)

        # Page 3: limit=2, offset=4 -> 1 box, has_more=False
        r = self.client.get('/utxo/boxes/alice?limit=2&offset=4')
        data = r.get_json()
        self.assertEqual(data['count'], 1)
        self.assertFalse(data['has_more'])
        self.assertFalse(data['truncated'])
        self.assertIsNone(data['next_offset'])

    def test_boxes_clamps_oversize_limit(self):
        r = self.client.get('/utxo/boxes/alice?limit=10000')
        data = r.get_json()
        # Server silently clamps to MAX_BOXES_PER_PAGE = 200.
        self.assertEqual(data['limit'], 200)

    def test_boxes_rejects_bad_paging(self):
        r = self.client.get('/utxo/boxes/alice?limit=abc')
        self.assertEqual(r.status_code, 400)
        r = self.client.get('/utxo/boxes/alice?offset=-1')
        self.assertEqual(r.status_code, 400)
        r = self.client.get('/utxo/boxes/alice?limit=0')
        self.assertEqual(r.status_code, 400)


if __name__ == '__main__':
    unittest.main()
