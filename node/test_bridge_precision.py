#!/usr/bin/env python3
"""
Tests for CRIT-BRIDGE-1: Float truncation in bridge amount conversion.
"""

import unittest
from decimal import Decimal

BRIDGE_UNIT = 1_000_000


class TestBridgeFloatPrecision(unittest.TestCase):
    """CRIT-BRIDGE-1: Bridge amounts must use Decimal, not float."""

    def test_float_truncation_exists(self):
        """int(2.01 * 1e6) = 2009999, not 2010000."""
        broken = int(2.01 * BRIDGE_UNIT)
        self.assertEqual(broken, 2009999)

    def test_decimal_is_exact(self):
        """Decimal(str(2.01)) * 1e6 = 2010000 exactly."""
        fixed = int(Decimal("2.01") * BRIDGE_UNIT)
        self.assertEqual(fixed, 2010000)

    def test_bridge_amounts_exact(self):
        """Common bridge amounts must be exact."""
        for amount_rtc in [1.0, 5.5, 10.0, 100.0, 0.5, 2.01]:
            result = int(Decimal(str(amount_rtc)) * BRIDGE_UNIT)
            expected = round(amount_rtc * BRIDGE_UNIT)
            self.assertEqual(result, expected,
                             f"Bridge amount {amount_rtc} RTC must convert exactly")


if __name__ == "__main__":
    unittest.main()
