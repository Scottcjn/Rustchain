# SPDX-License-Identifier: MIT
"""Tests for EIP-1559-compatible fee market helpers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fee_market import (
    calculate_effective_priority_fee,
    calculate_eip1559_fee_breakdown,
    calculate_next_base_fee,
    legacy_fee_breakdown,
)


class TestFeeMarket(unittest.TestCase):
    def test_base_fee_unchanged_at_target_gas(self):
        self.assertEqual(calculate_next_base_fee(1_000, 15_000_000), 1_000)

    def test_base_fee_increases_when_parent_block_is_above_target(self):
        self.assertEqual(calculate_next_base_fee(1_000, 30_000_000), 1_125)

    def test_base_fee_decreases_when_parent_block_is_below_target(self):
        self.assertEqual(calculate_next_base_fee(1_000, 7_500_000), 938)

    def test_base_fee_increase_is_at_least_one_when_congested(self):
        self.assertEqual(calculate_next_base_fee(1, 15_000_001), 2)

    def test_effective_priority_fee_is_capped_by_max_fee_minus_base_fee(self):
        self.assertEqual(
            calculate_effective_priority_fee(
                max_fee_per_gas_nrtc=120,
                max_priority_fee_per_gas_nrtc=50,
                base_fee_per_gas_nrtc=100,
            ),
            20,
        )

    def test_fee_breakdown_splits_burn_and_tip(self):
        breakdown = calculate_eip1559_fee_breakdown(
            gas_limit=21_000,
            max_fee_per_gas_nrtc=150,
            max_priority_fee_per_gas_nrtc=10,
            base_fee_per_gas_nrtc=100,
        )

        self.assertEqual(breakdown.burned_fee_nrtc, 2_100_000)
        self.assertEqual(breakdown.priority_tip_nrtc, 210_000)
        self.assertEqual(breakdown.total_fee_nrtc, 2_310_000)

    def test_fee_breakdown_rejects_max_fee_below_base_fee(self):
        with self.assertRaisesRegex(ValueError, "below base_fee"):
            calculate_eip1559_fee_breakdown(
                gas_limit=21_000,
                max_fee_per_gas_nrtc=99,
                max_priority_fee_per_gas_nrtc=1,
                base_fee_per_gas_nrtc=100,
            )

    def test_legacy_fixed_fee_remains_backward_compatible(self):
        breakdown = legacy_fee_breakdown(5_000)

        self.assertEqual(breakdown.burned_fee_nrtc, 0)
        self.assertEqual(breakdown.priority_tip_nrtc, 5_000)
        self.assertEqual(breakdown.total_fee_nrtc, 5_000)

    def test_legacy_fee_can_be_split_once_base_fee_is_known(self):
        breakdown = legacy_fee_breakdown(
            5_000,
            gas_limit=10,
            base_fee_per_gas_nrtc=100,
        )

        self.assertEqual(breakdown.burned_fee_nrtc, 1_000)
        self.assertEqual(breakdown.priority_tip_nrtc, 4_000)
        self.assertEqual(breakdown.total_fee_nrtc, 5_000)


if __name__ == "__main__":
    unittest.main()
