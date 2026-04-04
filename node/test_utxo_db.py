"""
Tests for utxo_db.py — RustChain UTXO Database Layer
=====================================================

Run:  python3 -m pytest test_utxo_db.py -v
  or: python3 test_utxo_db.py
"""

import os
import tempfile
import time
import unittest

from utxo_db import (
    UtxoDB, coin_select, compute_box_id, address_to_proposition,
    proposition_to_address, UNIT, DUST_THRESHOLD,
)


class TestUtxoDB(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    # -- helpers -------------------------------------------------------------

    def _apply_coinbase(self, address: str, value_nrtc: int,
                        block_height: int = 1) -> bool:
        return self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': value_nrtc}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=block_height)

    # -- box operations ------------------------------------------------------

    def test_coinbase_creates_box(self):
        ok = self._apply_coinbase('alice', 150 * UNIT)
        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('alice'), 150 * UNIT)
        self.assertEqual(self.db.count_unspent(), 1)

    def test_multiple_coinbases(self):
        self._apply_coinbase('alice', 100 * UNIT, block_height=1)
        self._apply_coinbase('alice', 50 * UNIT, block_height=2)
        self.assertEqual(self.db.get_balance('alice'), 150 * UNIT)
        self.assertEqual(self.db.count_unspent(), 2)

    def test_balance_zero_for_unknown(self):
        self.assertEqual(self.db.get_balance('nobody'), 0)

    def test_get_unspent_for_address(self):
        self._apply_coinbase('bob', 10 * UNIT, block_height=1)
        self._apply_coinbase('bob', 20 * UNIT, block_height=2)
        boxes = self.db.get_unspent_for_address('bob')
        self.assertEqual(len(boxes), 2)
        values = sorted(b['value_nrtc'] for b in boxes)
        self.assertEqual(values, [10 * UNIT, 20 * UNIT])

    # -- transfers -----------------------------------------------------------

    def test_transfer(self):
        self._apply_coinbase('alice', 100 * UNIT)
        alice_boxes = self.db.get_unspent_for_address('alice')
        self.assertEqual(len(alice_boxes), 1)

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [
                {'address': 'bob', 'value_nrtc': 60 * UNIT},
                {'address': 'alice', 'value_nrtc': 40 * UNIT},  # change
            ],
            'fee_nrtc': 0,
        }, block_height=10)

        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('alice'), 40 * UNIT)
        self.assertEqual(self.db.get_balance('bob'), 60 * UNIT)
        self.assertEqual(self.db.count_unspent(), 2)

    def test_transfer_insufficient_funds(self):
        self._apply_coinbase('alice', 50 * UNIT)
        alice_boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 60 * UNIT}],
            'fee_nrtc': 0,
        }, block_height=10)

        self.assertFalse(ok)
        # Balance unchanged
        self.assertEqual(self.db.get_balance('alice'), 50 * UNIT)

    def test_transfer_with_fee(self):
        self._apply_coinbase('alice', 100 * UNIT)
        alice_boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [
                {'address': 'bob', 'value_nrtc': 90 * UNIT},
                {'address': 'alice', 'value_nrtc': 9 * UNIT},
            ],
            'fee_nrtc': 1 * UNIT,
        }, block_height=10)

        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('bob'), 90 * UNIT)
        self.assertEqual(self.db.get_balance('alice'), 9 * UNIT)

    def test_fee_exceeds_conservation(self):
        """Outputs + fee > inputs should fail."""
        self._apply_coinbase('alice', 100 * UNIT)
        alice_boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 1,
        }, block_height=10)

        self.assertFalse(ok)

    # -- double-spend --------------------------------------------------------

    def test_double_spend_rejected(self):
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # First spend succeeds
        ok1 = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
        }, block_height=10)
        self.assertTrue(ok1)

        # Second spend of same box fails
        ok2 = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'eve', 'value_nrtc': 100 * UNIT}],
        }, block_height=11)
        self.assertFalse(ok2)
        self.assertEqual(self.db.get_balance('bob'), 100 * UNIT)
        self.assertEqual(self.db.get_balance('eve'), 0)

    def test_nonexistent_input_rejected(self):
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': 'deadbeef' * 8, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
        }, block_height=10)
        self.assertFalse(ok)

    # -- state root ----------------------------------------------------------

    def test_empty_state_root(self):
        root = self.db.compute_state_root()
        self.assertEqual(len(root), 64)  # hex SHA256

    def test_state_root_deterministic(self):
        self._apply_coinbase('alice', 100 * UNIT)
        self._apply_coinbase('bob', 50 * UNIT)
        root1 = self.db.compute_state_root()
        root2 = self.db.compute_state_root()
        self.assertEqual(root1, root2)

    def test_state_root_changes_after_spend(self):
        self._apply_coinbase('alice', 100 * UNIT)
        root_before = self.db.compute_state_root()

        boxes = self.db.get_unspent_for_address('alice')
        self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id'], 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
        }, block_height=10)

        root_after = self.db.compute_state_root()
        self.assertNotEqual(root_before, root_after)

    # -- integrity -----------------------------------------------------------

    def test_integrity_ok(self):
        self._apply_coinbase('alice', 100 * UNIT)
        self._apply_coinbase('bob', 50 * UNIT)
        result = self.db.integrity_check(expected_total=150 * UNIT)
        self.assertTrue(result['ok'])
        self.assertTrue(result['models_agree'])
        self.assertEqual(result['total_unspent_nrtc'], 150 * UNIT)
        self.assertEqual(result['total_unspent_boxes'], 2)

    def test_integrity_mismatch(self):
        self._apply_coinbase('alice', 100 * UNIT)
        result = self.db.integrity_check(expected_total=200 * UNIT)
        self.assertFalse(result['ok'])
        self.assertFalse(result['models_agree'])

    # -- mempool -------------------------------------------------------------

    def test_mempool_add_and_remove(self):
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'aaaa' * 16,
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }
        ok = self.db.mempool_add(tx)
        self.assertTrue(ok)

        # Same input in mempool = double-spend
        tx2 = {
            'tx_id': 'bbbb' * 16,
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'eve', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }
        ok2 = self.db.mempool_add(tx2)
        self.assertFalse(ok2)

        # Check double-spend flag
        self.assertTrue(
            self.db.mempool_check_double_spend(boxes[0]['box_id'])
        )

        # Remove first TX
        self.db.mempool_remove('aaaa' * 16)
        self.assertFalse(
            self.db.mempool_check_double_spend(boxes[0]['box_id'])
        )

    def test_mempool_block_candidates(self):
        self._apply_coinbase('alice', 100 * UNIT, block_height=1)
        self._apply_coinbase('alice', 200 * UNIT, block_height=2)
        boxes = self.db.get_unspent_for_address('alice')

        # Add two txs with different fees
        self.db.mempool_add({
            'tx_id': 'low_' * 16,
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 1000,
        })
        self.db.mempool_add({
            'tx_id': 'high' * 16,
            'inputs': [{'box_id': boxes[1]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 200 * UNIT}],
            'fee_nrtc': 5000,
        })

        candidates = self.db.mempool_get_block_candidates(max_count=10)
        self.assertEqual(len(candidates), 2)
        # Highest fee first
        self.assertEqual(candidates[0]['tx_id'], 'high' * 16)

    def test_mempool_nonexistent_input_rejected(self):
        tx = {
            'tx_id': 'cccc' * 16,
            'inputs': [{'box_id': 'deadbeef' * 8}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }
        ok = self.db.mempool_add(tx)
        self.assertFalse(ok)

    # -- proposition encoding ------------------------------------------------

    def test_proposition_roundtrip(self):
        addr = 'RTCa1b2c3d4e5'
        prop = address_to_proposition(addr)
        recovered = proposition_to_address(prop)
        self.assertEqual(recovered, addr)

    # -- bounty #2819: empty-input minting vulnerability ---------------------

    def test_empty_inputs_rejected_for_transfer(self):
        """A normal transfer with empty inputs must be rejected.
        This prevents minting funds from nothing (bounty #2819)."""
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [],
            'outputs': [{'address': 'attacker', 'value_nrtc': 1_000_000 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=10)
        self.assertFalse(ok)
        self.assertEqual(self.db.get_balance('attacker'), 0)

    def test_empty_inputs_rejected_for_unknown_tx_type(self):
        """Any non-minting tx_type with empty inputs must be rejected."""
        ok = self.db.apply_transaction({
            'tx_type': 'some_random_type',
            'inputs': [],
            'outputs': [{'address': 'attacker', 'value_nrtc': 500 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=10)
        self.assertFalse(ok)

    def test_mining_reward_empty_inputs_allowed(self):
        """Legitimate mining_reward transactions MUST still work with empty inputs."""
        ok = self._apply_coinbase('alice', 100 * UNIT)
        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('alice'), 100 * UNIT)

    def test_mempool_empty_inputs_rejected_for_transfer(self):
        """Mempool must also reject non-minting txs with empty inputs."""
        tx = {
            'tx_id': 'ffff' * 16,
            'tx_type': 'transfer',
            'inputs': [],
            'outputs': [{'address': 'attacker', 'value_nrtc': 999 * UNIT}],
            'fee_nrtc': 0,
        }
        ok = self.db.mempool_add(tx)
        self.assertFalse(ok)


class TestCoinSelect(unittest.TestCase):

    def _box(self, value_nrtc: int) -> dict:
        return {'box_id': f'box_{value_nrtc}', 'value_nrtc': value_nrtc}

    def test_exact_match(self):
        utxos = [self._box(100 * UNIT)]
        selected, change = coin_select(utxos, 100 * UNIT)
        self.assertEqual(len(selected), 1)
        self.assertEqual(change, 0)

    def test_change_returned(self):
        utxos = [self._box(100 * UNIT)]
        selected, change = coin_select(utxos, 60 * UNIT)
        self.assertEqual(len(selected), 1)
        self.assertEqual(change, 40 * UNIT)

    def test_insufficient_funds(self):
        utxos = [self._box(50 * UNIT)]
        selected, change = coin_select(utxos, 100 * UNIT)
        self.assertEqual(selected, [])

    def test_smallest_first(self):
        utxos = [self._box(50 * UNIT), self._box(10 * UNIT),
                 self._box(30 * UNIT)]
        selected, change = coin_select(utxos, 35 * UNIT)
        # Should pick 10 + 30 = 40 (smallest-first)
        values = sorted(s['value_nrtc'] for s in selected)
        self.assertEqual(values, [10 * UNIT, 30 * UNIT])
        self.assertEqual(change, 5 * UNIT)

    def test_dust_absorbed(self):
        utxos = [self._box(100 * UNIT + 500)]  # 500 nrtc over target
        selected, change = coin_select(utxos, 100 * UNIT)
        # 500 < DUST_THRESHOLD (1000), absorbed into fee
        self.assertEqual(change, 0)

    def test_empty_utxos(self):
        selected, change = coin_select([], 100 * UNIT)
        self.assertEqual(selected, [])

    def test_zero_target(self):
        selected, change = coin_select([self._box(100)], 0)
        self.assertEqual(selected, [])

    def test_many_small_utxos_switches_to_largest(self):
        # 25 UTXOs of 10 each, target 200 — smallest-first would use 20+
        utxos = [self._box(10 * UNIT) for _ in range(25)]
        # Add one big one
        utxos.append(self._box(200 * UNIT))
        selected, change = coin_select(utxos, 200 * UNIT)
        # Should switch to largest-first and pick the 200 UNIT box
        self.assertLessEqual(len(selected), 20)


class TestMultiInputTransfer(unittest.TestCase):
    """Test transfers that consume multiple UTXOs."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_consolidation(self):
        """Multiple small boxes consolidated into one transfer."""
        for i in range(5):
            self.db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{'address': 'miner', 'value_nrtc': 10 * UNIT}],
                'timestamp': int(time.time()) + i,
            }, block_height=i + 1)

        self.assertEqual(self.db.get_balance('miner'), 50 * UNIT)
        boxes = self.db.get_unspent_for_address('miner')
        self.assertEqual(len(boxes), 5)

        # Spend all 5 to send 45, keep 5 change
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': b['box_id'], 'spending_proof': 'sig'}
                       for b in boxes],
            'outputs': [
                {'address': 'recipient', 'value_nrtc': 45 * UNIT},
                {'address': 'miner', 'value_nrtc': 5 * UNIT},
            ],
            'fee_nrtc': 0,
        }, block_height=10)

        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('recipient'), 45 * UNIT)
        self.assertEqual(self.db.get_balance('miner'), 5 * UNIT)
        # 5 spent + 2 new = 2 unspent
        self.assertEqual(self.db.count_unspent(), 2)

    def test_transaction_recorded(self):
        """Verify utxo_transactions table is populated."""
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
        }, block_height=1)

        conn = self.db._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM utxo_transactions"
            ).fetchone()
            self.assertEqual(row['n'], 1)

            tx = conn.execute(
                "SELECT * FROM utxo_transactions"
            ).fetchone()
            self.assertEqual(tx['tx_type'], 'mining_reward')
            self.assertEqual(tx['block_height'], 1)
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
