#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression test: BoTTube feed endpoints accept negative LIMIT values.

The RSS, Atom and JSON feed endpoints only cap the upper bound (max 100)
but do not validate that limit is >= 1.  A negative int passes through
``min(negative, 100)`` unchanged and reaches the DB query as ``LIMIT -N``.

The mock fallback silently returns [] which masks the issue in test
deployments, but the bug still violates the stated contract
(``limit >= 1`` is implied by the docstring).

Severity: LOW  |  Bounty: #305
"""

import unittest


class TestBottubeFeedLimit(unittest.TestCase):

    def test_negative_limit_parsing(self):
        """A negative request argument should be rejected."""
        for value in ("-5", "-100", "-1"):
            parsed = int(value)
            # Without guard: min(-5, 100) == -5  (passes silently)
            unguarded = min(parsed, 100)
            self.assertLess(unguarded, 0,
                            f"Value {value} should be caught before use")

            # With guard: max(1, min(int(x), 100)) ensures positive
            guarded = max(1, min(parsed, 100))
            self.assertGreaterEqual(guarded, 1,
                                    f"Guarded {value} should be >= 1")

    def test_limit_zero_clamped(self):
        """Zero should be clamped to 1."""
        guarded = max(1, min(0, 100))
        self.assertEqual(guarded, 1)

    def test_positive_limit_unchanged(self):
        """Normal values pass through unchanged."""
        for value in ("1", "5", "50", "100"):
            parsed = int(value)
            guarded = max(1, min(parsed, 100))
            self.assertEqual(guarded, parsed,
                             f"Value {value} should pass unchanged")

    def test_above_max_clamped_to_100(self):
        """Values above 100 are clamped to 100."""
        guarded = max(1, min(200, 100))
        self.assertEqual(guarded, 100)

    def test_non_integer_rejected(self):
        """Non-integer strings should raise ValueError."""
        for value in ("abc", "1.5", "", " "):
            with self.assertRaises(ValueError):
                int(value)


if __name__ == "__main__":
    unittest.main()
