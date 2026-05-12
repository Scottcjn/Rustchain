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
    proposition_to_address, UNIT, DUST_THRESHOLD, MAX_COINBASE_OUTPUT_NRTC,
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
            '_allow_minting': True,
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

    def test_transfer_missing_input_box_id_rejected(self):
        """Malformed inputs should fail validation instead of raising."""
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{}],
            'outputs': [{'address': 'bob', 'value_nrtc': 1 * UNIT}],
            'fee_nrtc': 0,
        }, block_height=10)

        self.assertFalse(ok)

    def test_transfer_missing_output_address_rejected(self):
        """Malformed outputs should fail validation instead of raising."""
        self._apply_coinbase('alice', 100 * UNIT)
        alice_boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [{'value_nrtc': 99 * UNIT}],
            'fee_nrtc': 1 * UNIT,
        }, block_height=10)

        self.assertFalse(ok)
        self.assertEqual(self.db.get_balance('alice'), 100 * UNIT)

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

    def test_transfer_tx_id_commits_to_outputs(self):
        """Different transfer outputs must not share the same tx_id.

        Previously transfer tx_id was derived from inputs + timestamp only.
        Two nodes could apply materially different transactions with the same
        input and timestamp, record the same tx_id, but produce different UTXO
        sets and state roots.
        """
        def apply_variant(recipient: str) -> tuple:
            tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            tmp.close()
            db = UtxoDB(tmp.name)
            try:
                db.init_tables()
                ok = db.apply_transaction({
                    'tx_type': 'mining_reward',
                    'inputs': [],
                    'outputs': [{'address': 'alice',
                                 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': 1234567890,
                    '_allow_minting': True,
                }, block_height=1)
                self.assertTrue(ok)

                box = db.get_unspent_for_address('alice')[0]
                ok = db.apply_transaction({
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': box['box_id'],
                                'spending_proof': 'sig'}],
                    'outputs': [{'address': recipient,
                                 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': 2222222222,
                }, block_height=10)
                self.assertTrue(ok)

                conn = db._conn()
                try:
                    row = conn.execute(
                        """SELECT tx_id FROM utxo_transactions
                           WHERE tx_type = 'transfer'"""
                    ).fetchone()
                    return row['tx_id'], db.compute_state_root()
                finally:
                    conn.close()
            finally:
                os.unlink(tmp.name)

        bob_tx_id, bob_root = apply_variant('bob')
        eve_tx_id, eve_root = apply_variant('eve')

        self.assertNotEqual(bob_root, eve_root)
        self.assertNotEqual(bob_tx_id, eve_tx_id)

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

    def test_negative_fee_rejected(self):
        """Negative fee should fail — allows minting via weakened conservation."""
        self._apply_coinbase('alice', 100 * UNIT)
        alice_boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 1100 * UNIT}],
            'fee_nrtc': -1000 * UNIT,  # negative fee bypasses conservation
        }, block_height=10)

        self.assertFalse(ok)
        # Balances unchanged
        self.assertEqual(self.db.get_balance('alice'), 100 * UNIT)
        self.assertEqual(self.db.get_balance('bob'), 0)

    def test_fractional_fee_rejected(self):
        """fee_nrtc must be an integer nanoRTC amount.

        A fractional fee can pass conservation by pairing it with a one-nanoRTC
        output reduction, but SQLite stores the fee in an INTEGER column and
        truncates it. That silently destroys value without recording the fee.
        """
        self._apply_coinbase('alice', 100 * UNIT)
        alice_boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT - 1}],
            'fee_nrtc': 0.5,
        }, block_height=10)

        self.assertFalse(ok)
        # Balances unchanged
        self.assertEqual(self.db.get_balance('alice'), 100 * UNIT)
        self.assertEqual(self.db.get_balance('bob'), 0)

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

    def test_spend_box_double_spend_raises(self):
        """spend_box() must raise ValueError on double-spend, not silently
        return the box dict (bounty #2819 HIGH-1 TOCTOU fix)."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # First spend succeeds
        result = self.db.spend_box(box_id, 'tx_first')
        self.assertIsNotNone(result)

        # Second spend must raise, not return silently
        with self.assertRaises(ValueError):
            self.db.spend_box(box_id, 'tx_second')

    def test_spend_box_nonexistent_returns_none(self):
        """spend_box() on a nonexistent box_id returns None."""
        result = self.db.spend_box('deadbeef' * 8, 'tx_whatever')
        self.assertIsNone(result)

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

    def test_state_root_odd_count_unique(self):
        """Odd-count UTXO sets must produce unique roots.

        The old Merkle construction duplicated the last hash when the count
        was odd, creating second-preimage ambiguity: sets [A,B,C] and
        [A,B,C,C] could produce the same root. The domain-separated padding
        and count-binding fix eliminates this (bounty #2819 MED-2).
        """
        # Create 3 boxes (odd count)
        self._apply_coinbase('alice', 10 * UNIT, block_height=1)
        self._apply_coinbase('bob',   20 * UNIT, block_height=2)
        self._apply_coinbase('carol', 30 * UNIT, block_height=3)
        root_3 = self.db.compute_state_root()
        self.assertEqual(len(root_3), 64)

        # Create a 4th box — root must change
        self._apply_coinbase('dave', 40 * UNIT, block_height=4)
        root_4 = self.db.compute_state_root()
        self.assertNotEqual(root_3, root_4)

        # Create a 5th box (odd again) — root must change again
        self._apply_coinbase('eve', 50 * UNIT, block_height=5)
        root_5 = self.db.compute_state_root()
        self.assertNotEqual(root_4, root_5)
        self.assertNotEqual(root_3, root_5)

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

    def test_mempool_rejects_user_supplied_mining_reward(self):
        """Public mempool must not admit minting transactions.

        apply_transaction() requires _allow_minting=True for mining rewards;
        mempool_add() is a public admission boundary and should reject this
        class entirely so invalid mint candidates cannot occupy the mempool or
        be returned to block producers.
        """
        ok = self.db.mempool_add({
            'tx_id': 'evil_mint_1',
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'attacker', 'value_nrtc': 999999999 * UNIT}],
            'fee_nrtc': 0,
        })
        self.assertFalse(ok)
        self.assertEqual(self.db.mempool_get_block_candidates(), [])

    def test_mempool_block_candidates(self):
        self._apply_coinbase('alice', 100 * UNIT, block_height=1)
        self._apply_coinbase('alice', 120 * UNIT, block_height=2)
        boxes = self.db.get_unspent_for_address('alice')

        # Add two txs with different fees (outputs + fee <= inputs)
        self.db.mempool_add({
            'tx_id': 'low_' * 16,
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT - 1000}],
            'fee_nrtc': 1000,
        })
        self.db.mempool_add({
            'tx_id': 'high' * 16,
            'inputs': [{'box_id': boxes[1]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 120 * UNIT - 5000}],
            'fee_nrtc': 5000,
        })

        candidates = self.db.mempool_get_block_candidates(max_count=10)
        self.assertEqual(len(candidates), 2)
        # Highest fee first
        self.assertEqual(candidates[0]['tx_id'], 'high' * 16)

    def test_mempool_block_candidates_ignore_expired_transactions(self):
        self._apply_coinbase('alice', 100 * UNIT, block_height=1)
        box = self.db.get_unspent_for_address('alice')[0]
        tx_id = 'expired' * 8

        self.assertTrue(self.db.mempool_add({
            'tx_id': tx_id,
            'inputs': [{'box_id': box['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT - 1000}],
            'fee_nrtc': 1000,
        }))

        conn = self.db._conn()
        try:
            conn.execute(
                "UPDATE utxo_mempool SET expires_at = ? WHERE tx_id = ?",
                (int(time.time()) - 1, tx_id),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertTrue(self.db.mempool_add({
            'tx_id': 'replacement' * 6,
            'inputs': [{'box_id': box['box_id']}],
            'outputs': [{'address': 'carol', 'value_nrtc': 100 * UNIT - 2000}],
            'fee_nrtc': 2000,
        }))

        candidates = self.db.mempool_get_block_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['tx_id'], 'replacement' * 6)

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

    # -- bounty #2819 LOW: validation gaps & edge cases ----------------------

    def test_duplicate_input_rejected(self):
        """Same box_id listed twice in inputs must be rejected.
        Without explicit dedup, input_total is inflated 2x (LOW-2)."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [
                {'box_id': box_id, 'spending_proof': 'sig'},
                {'box_id': box_id, 'spending_proof': 'sig'},  # duplicate
            ],
            'outputs': [{'address': 'attacker', 'value_nrtc': 200 * UNIT}],
            'fee_nrtc': 0,
        }, block_height=10)
        self.assertFalse(ok)
        self.assertEqual(self.db.get_balance('alice'), 100 * UNIT)
        self.assertEqual(self.db.get_balance('attacker'), 0)

    def test_self_transfer(self):
        """Self-transfer (from == to) must work correctly."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }, block_height=10)
        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('alice'), 100 * UNIT)

    def test_spending_proof_accepted_without_verification(self):
        """The UTXO layer accepts any spending_proof without verification.
        Signature verification is the endpoint layer's responsibility.
        This test documents the behavior so future changes don't
        accidentally rely on it (LOW-3)."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        # Bogus spending_proof is accepted at the UTXO layer
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id'],
                         'spending_proof': 'TOTALLY_BOGUS'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }, block_height=10)
        self.assertTrue(ok, "UTXO layer should accept any spending_proof "
                            "(verification is endpoint's job)")

    def test_mining_reward_at_cap_allowed(self):
        """Mining reward exactly at MAX_COINBASE_OUTPUT_NRTC must succeed."""
        ok = self._apply_coinbase('miner', MAX_COINBASE_OUTPUT_NRTC)
        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('miner'), MAX_COINBASE_OUTPUT_NRTC)

    def test_mining_reward_over_cap_rejected(self):
        """Mining reward exceeding MAX_COINBASE_OUTPUT_NRTC must be rejected.
        Without this, any caller that passes tx_type='mining_reward' can
        mint unlimited funds (bounty #2819 HIGH-2)."""
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'attacker',
                         'value_nrtc': MAX_COINBASE_OUTPUT_NRTC + 1}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=10)
        self.assertFalse(ok)
        self.assertEqual(self.db.get_balance('attacker'), 0)

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

    # -- mempool conservation-of-value (DoS prevention) ----------------------

    def test_mempool_rejects_outputs_exceed_inputs(self):
        """Mempool must reject tx where outputs > inputs (conservation violation).
        Prevents UTXO locking DoS — invalid tx would lock boxes until expiry."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'cons' * 16,
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 1_000_000 * UNIT}],
            'fee_nrtc': 0,
        }
        ok = self.db.mempool_add(tx)
        self.assertFalse(ok)
        # Box should NOT be locked — still available for legitimate tx
        self.assertFalse(
            self.db.mempool_check_double_spend(boxes[0]['box_id'])
        )

    def test_mempool_rejects_negative_fee(self):
        """Mempool must reject negative fee (minting via weakened conservation)."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'nfee' * 16,
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': -50 * UNIT,
        }
        ok = self.db.mempool_add(tx)
        self.assertFalse(ok)
        # Box should NOT be locked
        self.assertFalse(
            self.db.mempool_check_double_spend(boxes[0]['box_id'])
        )

    def test_mempool_rejects_fractional_fee(self):
        """Mempool must reject non-integer fee_nrtc values.

        Otherwise a transaction can lock inputs with fee accounting that will
        diverge when persisted to SQLite's INTEGER fee column.
        """
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'ffee' * 16,
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT - 1}],
            'fee_nrtc': 0.5,
        }
        ok = self.db.mempool_add(tx)
        self.assertFalse(ok)
        # Box should NOT be locked
        self.assertFalse(
            self.db.mempool_check_double_spend(boxes[0]['box_id'])
        )

    def test_mempool_rejects_input_missing_box_id(self):
        """Mempool should reject malformed inputs before admission."""
        tx = {
            'tx_id': 'missingbox' * 8,
            'tx_type': 'transfer',
            'inputs': [{}],
            'outputs': [{'address': 'bob', 'value_nrtc': 1 * UNIT}],
            'fee_nrtc': 0,
        }

        self.assertFalse(self.db.mempool_add(tx))

    def test_mempool_rejects_output_missing_address(self):
        """Mempool must reject outputs that apply_transaction cannot create.

        A positive-valued output without an address passes the current mempool
        value checks, claims the input box, and later raises KeyError in
        apply_transaction() when block construction tries to materialize it.
        """
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'addr' * 16,
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'value_nrtc': 99 * UNIT}],
            'fee_nrtc': 1 * UNIT,
        }
        ok = self.db.mempool_add(tx)
        self.assertFalse(ok)
        # Box should NOT be locked by a transaction that cannot be applied.
        self.assertFalse(
            self.db.mempool_check_double_spend(boxes[0]['box_id'])
        )

    def test_mempool_accepts_valid_tx(self):
        """Mempool should accept a well-formed tx with valid conservation."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'good' * 16,
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [
                {'address': 'bob', 'value_nrtc': 90 * UNIT},
                {'address': 'alice', 'value_nrtc': 9 * UNIT},
            ],
            'fee_nrtc': 1 * UNIT,
        }
        ok = self.db.mempool_add(tx)
        self.assertTrue(ok)
        # Box should be locked
        self.assertTrue(
            self.db.mempool_check_double_spend(boxes[0]['box_id'])
        )

    def test_mempool_accepts_exact_input_output(self):
        """Mempool should accept tx where outputs == inputs (no fee, no change)."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'xact' * 16,
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }
        ok = self.db.mempool_add(tx)
        self.assertTrue(ok)

    def test_mempool_rejects_fee_exceeding_surplus(self):
        """Mempool must reject tx where outputs + fee > inputs."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        tx = {
            'tx_id': 'hife' * 16,
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id']}],
            'outputs': [{'address': 'bob', 'value_nrtc': 99 * UNIT}],
            'fee_nrtc': 2 * UNIT,  # 99 + 2 = 101 > 100
        }
        ok = self.db.mempool_add(tx)
        self.assertFalse(ok)

    # -- bounty #2819: negative / zero value outputs -------------------------

    def test_negative_value_output_rejected(self):
        """Negative value_nrtc on an output bypasses conservation law.

        Attack: 100 RTC input → [+200 RTC, -100 RTC] outputs.
        output_total = 200 + (-100) = 100 <= input_total = 100, PASSES.
        Attacker mints 100 RTC from nothing.
        """
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [
                {'address': 'attacker', 'value_nrtc': 200 * UNIT},
                {'address': 'burn',     'value_nrtc': -100 * UNIT},
            ],
            'fee_nrtc': 0,
        }, block_height=10)

        self.assertFalse(ok)
        # Balance must be unchanged
        self.assertEqual(self.db.get_balance('alice'), 100 * UNIT)
        self.assertEqual(self.db.get_balance('attacker'), 0)

    def test_zero_value_output_rejected(self):
        """Zero-value outputs are meaningless dust that bloats the UTXO set."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [
                {'address': 'bob',  'value_nrtc': 100 * UNIT},
                {'address': 'dust', 'value_nrtc': 0},
            ],
            'fee_nrtc': 0,
        }, block_height=10)

        self.assertFalse(ok)

    def test_float_value_nrtc_rejected(self):
        """value_nrtc must be an integer; floats cause silent truncation."""
        self._apply_coinbase('alice', 100 * UNIT)
        boxes = self.db.get_unspent_for_address('alice')

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': boxes[0]['box_id'],
                         'spending_proof': 'sig'}],
            'outputs': [
                {'address': 'bob', 'value_nrtc': 99.5 * UNIT},
            ],
            'fee_nrtc': 0,
        }, block_height=10)
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
                '_allow_minting': True,
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
            '_allow_minting': True,
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
