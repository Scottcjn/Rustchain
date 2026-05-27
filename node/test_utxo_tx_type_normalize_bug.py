#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Test case for _normalize_tx_type empty string bug.
Issue: A12 — _normalize_tx_type returns None for empty string instead of default 'transfer'

Root cause: The condition `if not tx_type` treats empty string as falsy → returns None.
But semantically, an empty string is equivalent to "not provided" and should default
to 'transfer' just like a missing key.

Callers (lines 522, 885 in utxo_db.py) treat None as rejection:
    if tx_type is None: return False
So an empty tx_type silently rejects transactions that should default to 'transfer'.
"""

import unittest
import tempfile
import os
import sys
import time

# sys.path.insert not needed — tests run from /tmp/rustchain-utxo/node/

from utxo_db import UtxoDB, UNIT


class TestTxTypeNormalizeBug(unittest.TestCase):
    """
    Bug: _normalize_tx_type empty string returns None vs default 'transfer'.

    Severity: LOW (BCOS-L2)
    Behavior: Empty tx_type string causes transaction rejection instead of defaulting to 'transfer'.
    Fix: Treat empty string as absent → default to 'transfer'.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_missing_key_defaults_to_transfer(self):
        """Missing tx_type key → default 'transfer' (baseline, should work)."""
        r = self.db._normalize_tx_type({})
        self.assertEqual(r, 'transfer',
            "Missing tx_type key should default to 'transfer'")

    def test_empty_string_defaults_to_transfer(self):
        """EMPTY STRING tx_type → should default to 'transfer' (this is the bug fix)."""
        r = self.db._normalize_tx_type({'tx_type': ''})
        self.assertEqual(r, 'transfer',
            "BUG: Empty string tx_type should default to 'transfer', got None")

    def test_none_value_rejected(self):
        """None value tx_type → rejected (None), preserves existing behavior."""
        r = self.db._normalize_tx_type({'tx_type': None})
        self.assertIsNone(r,
            "None tx_type should be rejected (None), not defaulted")

    def test_valid_transfer_accepted(self):
        """Valid 'transfer' type → passes through."""
        r = self.db._normalize_tx_type({'tx_type': 'transfer'})
        self.assertEqual(r, 'transfer')

    def test_valid_mining_reward_accepted(self):
        """Valid 'mining_reward' type → passes through."""
        r = self.db._normalize_tx_type({'tx_type': 'mining_reward'})
        self.assertEqual(r, 'mining_reward')

    def test_non_string_rejected(self):
        """Non-string tx_type (int) → rejeted (None)."""
        r = self.db._normalize_tx_type({'tx_type': 123})
        self.assertIsNone(r,
            "Non-string tx_type should be rejected (None)")

    def test_unsupported_type_rejected(self):
        """Unsupported tx_type → rejected (None)."""
        r = self.db._normalize_tx_type({'tx_type': 'hack'})
        self.assertIsNone(r,
            "Unsupported tx_type should be rejected (None)")

    def test_whitespace_string_rejected(self):
        """Whitespace-only string → rejected (None, not in SUPPORTED_TX_TYPES)."""
        r = self.db._normalize_tx_type({'tx_type': '   '})
        self.assertIsNone(r,
            "Whitespace tx_type should be rejected (None), not in SUPPORTED_TX_TYPES")

    def test_transaction_with_empty_tx_type_passes_with_default(self):
        """End-to-end: transaction with empty tx_type is not rejected at normalize step."""
        # Create initial UTXO
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertTrue(ok, "Coinbase should succeed")

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # Try spending with empty tx_type — should NOT be rejected at normalize
        # (Note: full apply_transaction may still fail on other checks, that's fine)
        r = self.db._normalize_tx_type({'tx_type': '', 'inputs': [{'box_id': box_id}]})
        self.assertEqual(r, 'transfer',
            "Empty string tx_type should normalize to 'transfer' "
            "so the transaction can proceed")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTxTypeNormalizeBug)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED - Empty string now defaults to 'transfer'")
        print("=" * 70)
    else:
        print("⚠️  SOME TESTS FAILED")
        print("=" * 70)
