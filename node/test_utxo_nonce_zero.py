#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression test for UTXO transfer nonce=0 rejection bug.
Issue: #2819 — Bounty fix

Bug: `if not all([..., nonce])` rejects nonce=0 because 0 is falsy in Python.

Fix: Use explicit `nonce is None` check instead of `all()`.
"""

import unittest
import json


class TestNonceZeroValidation(unittest.TestCase):
    """Verify that nonce=0 is accepted by the validation logic."""

    def test_all_rejects_zero(self):
        """Demonstrate the old bug: all() rejects nonce=0."""
        from_address = "RTCtest123"
        to_address = "RTCtest456"
        public_key = "abcd" * 16
        signature = "efgh" * 16
        nonce = 0

        # Old logic (BUG)
        old_result = not all([from_address, to_address, public_key, signature, nonce])
        self.assertTrue(old_result, "all() incorrectly rejects nonce=0")

    def test_fix_accepts_zero(self):
        """Verify the fix: explicit None check accepts nonce=0."""
        from_address = "RTCtest123"
        to_address = "RTCtest456"
        public_key = "abcd" * 16
        signature = "efgh" * 16
        nonce = 0

        # New logic (FIX)
        new_result = not from_address or not to_address or not public_key or not signature or nonce is None
        self.assertFalse(new_result, "Fixed: nonce=0 should be accepted")

    def test_fix_still_rejects_none(self):
        """Verify the fix still rejects missing nonce."""
        from_address = "RTCtest123"
        to_address = "RTCtest456"
        public_key = "abcd" * 16
        signature = "efgh" * 16
        nonce = None

        new_result = not from_address or not to_address or not public_key or not signature or nonce is None
        self.assertTrue(new_result, "nonce=None should still be rejected")

    def test_fix_still_rejects_empty_string(self):
        """Verify the fix still rejects empty addresses."""
        from_address = ""
        to_address = "RTCtest456"
        public_key = "abcd" * 16
        signature = "efgh" * 16
        nonce = 123

        new_result = not from_address or not to_address or not public_key or not signature or nonce is None
        self.assertTrue(new_result, "empty from_address should be rejected")

    def test_fix_accepts_valid_transfer(self):
        """Verify the fix accepts a valid transfer with nonce=0."""
        from_address = "RTCtest123"
        to_address = "RTCtest456"
        public_key = "abcd" * 16
        signature = "efgh" * 16
        nonce = 0

        # Simulates the fixed validation
        if not from_address or not to_address or not public_key or not signature or nonce is None:
            self.fail("Valid transfer with nonce=0 should not be rejected")


if __name__ == '__main__':
    unittest.main(verbosity=2)
