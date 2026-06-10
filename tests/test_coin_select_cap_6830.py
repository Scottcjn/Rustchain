# SPDX-License-Identifier: MIT
"""
Regression test for #6830: coin_select() largest-first fallback
still returns >20 inputs on equal-value UTXOs.

When all UTXOs have the same value and the target requires more
than 20 of them, both smallest-first and largest-first produce
identical input counts (>20). The fix adds a cap at 20: take
the 20 largest UTXOs and return them if they cover the target,
otherwise fail with an empty result.
"""
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from utxo_db import coin_select

UNIT = 1_000_000  # 1 nRTC = 1e-6 RTC


class TestCoinSelectCap6830(unittest.TestCase):
    """Verify coin_select caps at 20 inputs when UTXOs are equal-value."""

    def _box(self, value_nrtc, idx=0):
        return {
            'box_id': f'box_{idx}_{value_nrtc}',
            'value_nrtc': value_nrtc,
        }

    def test_equal_value_utxos_capped_at_20(self):
        """25 equal-value UTXOs, target needs 21 — should cap at 20."""
        utxos = [self._box(1 * UNIT, i) for i in range(25)]
        # Target = 21 * UNIT, need 21 inputs of 1 UNIT each
        selected, change = coin_select(utxos, 21 * UNIT)
        # 20 biggest = 20 * UNIT, which is < 21 * UNIT target → insufficient
        self.assertEqual(selected, [])
        self.assertEqual(change, 0)

    def test_equal_value_utxos_covers_target(self):
        """25 equal-value UTXOs, target needs exactly 20 — should succeed."""
        utxos = [self._box(1 * UNIT, i) for i in range(25)]
        selected, change = coin_select(utxos, 20 * UNIT)
        # 20 biggest = 20 * UNIT, exactly covers the target
        self.assertEqual(len(selected), 20)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertEqual(total, 20 * UNIT)
        self.assertEqual(change, 0)

    def test_equal_value_utxos_covers_with_extra(self):
        """25 UTXOs of 2 UNIT, target 30 UNIT — 15 needed, no cap hit."""
        utxos = [self._box(2 * UNIT, i) for i in range(25)]
        selected, change = coin_select(utxos, 30 * UNIT)
        # Need 15 of 25, well under 20 cap
        self.assertEqual(len(selected), 15)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertGreaterEqual(total, 30 * UNIT)

    def test_mixed_values_largest_first_under_20(self):
        """Mixed values where largest-first uses <20 inputs — normal path."""
        utxos = [self._box(v, i) for i, v in enumerate(
            [1 * UNIT] * 30 + [50 * UNIT] * 2
        )]
        # Target = 60, largest first: 50+50=100 or 50+50 = 100 → 2 inputs
        selected, change = coin_select(utxos, 60 * UNIT)
        self.assertLessEqual(len(selected), 20)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertGreaterEqual(total, 60 * UNIT)

    def test_cap_20_with_mixed_equal_utxos(self):
        """22 UTXOs of 1 UNIT + 1 UTXO of 100 UNIT, target 119 UNIT."""
        utxos = [self._box(100 * UNIT, 0)] + [self._box(1 * UNIT, i+1) for i in range(22)]
        selected, change = coin_select(utxos, 119 * UNIT)
        # Smallest first: 22 * 1 + then 100 = 122 (23 inputs, >20)
        # Largest first: 100 + 19*1 = 119 (20 inputs, exactly 20)
        self.assertLessEqual(len(selected), 20)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertGreaterEqual(total, 119 * UNIT)

    def test_original_repro_from_issue(self):
        """Exact reproduction from #6830: 25 equal-value UTXOs, target 21."""
        utxos = [{'value_nrtc': 1} for _ in range(25)]
        selected, change = coin_select(utxos, 21)
        # 20 inputs of value 1 = 20, which is < 21 target
        self.assertEqual(selected, [])
        self.assertEqual(change, 0)

    def test_cap_20_large_equal_utxos(self):
        """30 UTXOs of 5 UNIT each, target 80 UNIT (needs 16)."""
        utxos = [self._box(5 * UNIT, i) for i in range(30)]
        selected, change = coin_select(utxos, 80 * UNIT)
        # Need 16 of 30, under 20 cap
        self.assertEqual(len(selected), 16)
        total = sum(u['value_nrtc'] for u in selected)
        self.assertEqual(total, 80 * UNIT)


if __name__ == '__main__':
    unittest.main()
