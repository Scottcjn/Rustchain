#!/usr/bin/env python3
"""
Tests for CRIT-TX-1: Float precision loss in RTC → µRTC conversion.

Demonstrates that Decimal-based conversion produces exact results where
float multiplication truncates.
"""

import unittest
from decimal import Decimal

# The production UNIT for the account model (1 RTC = 1,000,000 µRTC)
UNIT = 1_000_000


class TestRTCFloatPrecision(unittest.TestCase):
    """CRIT-TX-1: int(amount_rtc * UNIT) truncates for non-round amounts."""

    def test_float_truncation_demonstrated(self):
        """Show the bug: int(2.01 * 1_000_000) = 2009999 instead of 2010000."""
        broken = int(2.01 * UNIT)
        self.assertEqual(broken, 2009999, "Float truncation produces 2009999")

    def test_decimal_conversion_exact(self):
        """Decimal conversion produces exact results."""
        for amount_rtc in [0.1, 0.3, 0.7, 0.01, 0.001, 1.23, 9.999999]:
            result = int(Decimal(str(amount_rtc)) * UNIT)
            expected = round(amount_rtc * UNIT)
            self.assertEqual(result, expected, f"Decimal conversion of {amount_rtc} RTC should be exact")

    def test_problematic_amounts(self):
        """2.01 RTC truncates: int(2.01 * 1e6) = 2009999 instead of 2010000."""
        amount_rtc = 2.01
        expected = 2_010_000

        float_result = int(amount_rtc * UNIT)
        decimal_result = int(Decimal(str(amount_rtc)) * UNIT)

        # Float is wrong
        self.assertEqual(float_result, 2_009_999, "Float truncation produces 2009999")
        # Decimal is correct
        self.assertEqual(decimal_result, expected, "Decimal conversion produces exact 2010000")

    def test_integer_amounts_unaffected(self):
        """Integer RTC amounts are not affected by the fix."""
        for amount_rtc in [1, 5, 10, 100, 1500]:
            float_result = int(amount_rtc * UNIT)
            decimal_result = int(Decimal(str(amount_rtc)) * UNIT)
            self.assertEqual(float_result, decimal_result, f"Integer amount {amount_rtc} should be same either way")


if __name__ == "__main__":
    unittest.main()
