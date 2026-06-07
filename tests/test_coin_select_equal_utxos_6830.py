# SPDX-License-Identifier: MIT
"""Regression tests for issue #6830:
coin_select() largest-first fallback should cap at 20 inputs
and still cover the target when unequal UTXOs allow it.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from utxo_db import coin_select


class TestCoinSelectEqualValueEdgeCase(unittest.TestCase):
    """25 equal-value UTXOs of 1 nRTC, target 21 nRTC.

    Before the fix: largest-first picks 21 UTXOs -> exceeds 20 -> returns []
    After the fix:  top 20 largest (all 1 nRTC) sum to 20 < 21 -> returns [] correctly
    """

    def test_equal_value_cannot_cover_target_over_20(self):
        utxos = [{'value_nrtc': 1} for _ in range(25)]
        selected, change = coin_select(utxos, 21)
        self.assertEqual(selected, [])
        self.assertEqual(change, 0)

    def test_equal_value_can_cover_target_at_20(self):
        """Target of 20 nRTC with 25 equal 1-nRTC UTXOs should work."""
        utxos = [{'value_nrtc': 1} for _ in range(25)]
        selected, change = coin_select(utxos, 20)
        self.assertEqual(len(selected), 20)
        self.assertEqual(change, 0)

    def test_unequal_value_capped_fallback(self):
        """Mixed UTXOs where smallest-first picks >20 but top 20 largest cover the target."""
        utxos = [{'value_nrtc': 1} for _ in range(15)]
        utxos += [{'value_nrtc': 5} for _ in range(10)]
        selected, change = coin_select(utxos, 30)
        self.assertLessEqual(len(selected), 20)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertGreaterEqual(total, 30)

    def test_unequal_capped_at_20(self):
        """Large UTXOs + many small ones where large alone cover target."""
        utxos = [{'value_nrtc': 10} for _ in range(5)]
        utxos += [{'value_nrtc': 1} for _ in range(25)]
        selected, change = coin_select(utxos, 30)
        self.assertLessEqual(len(selected), 20)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertGreaterEqual(total, 30)

    def test_normal_case_under_20(self):
        """Normal case where selection stays under 20 inputs."""
        utxos = [{'value_nrtc': 5} for _ in range(5)]
        selected, change = coin_select(utxos, 12)
        self.assertGreater(len(selected), 0)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertGreaterEqual(total, 12)

    def test_insufficient_funds(self):
        """Target exceeds total available funds."""
        utxos = [{'value_nrtc': 1} for _ in range(5)]
        selected, change = coin_select(utxos, 100)
        self.assertEqual(selected, [])
        self.assertEqual(change, 0)

    def test_large_equal_capped_fallback(self):
        """25 UTXOs of 3 nRTC each, target 60.
        Top 20 = 60 nRTC exactly, should succeed with 20 inputs."""
        utxos = [{'value_nrtc': 3} for _ in range(25)]
        selected, change = coin_select(utxos, 60)
        self.assertEqual(len(selected), 20)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertEqual(total, 60)
        self.assertEqual(change, 0)


if __name__ == '__main__':
    unittest.main()
