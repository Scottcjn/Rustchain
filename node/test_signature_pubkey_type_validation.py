#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression tests for issues #6123, #6125, #6127:
Validate that non-string signature/public_key fields return 400
instead of crashing with AttributeError/ValueError.

Bug class: endpoints coerce signature/public_key with str() or .strip()/.lower()
before type-checking, allowing non-string JSON values (lists, bools, ints)
to reach address_from_pubkey() or string methods and raise unhandled exceptions.

Fix: Reject non-string signature and public_key values with structured 400
responses before any coercion or string method calls. Also wrap
address_from_pubkey() in try/except to catch malformed hex.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


class TestEpochEnrollSignatureValidation(unittest.TestCase):
    """#6123: /epoch/enroll crashes on non-string signature/public_key fields."""

    def setUp(self):
        os.environ.setdefault("RUSTCHAIN_DB", "/tmp/test_6123_regression.db")
        import rustchain_v2_integrated_v2.2.1_rip200 as app_module
        self.app = app_module.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_enroll_bool_signature_returns_400(self):
        """signature=True should return 400, not AttributeError."""
        rv = self.client.post("/epoch/enroll", json={
            "miner_pubkey": "test-miner",
            "miner_id": "test-miner",
            "signature": True,
            "public_key": "0" * 64,
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")

    def test_enroll_list_public_key_returns_400(self):
        """public_key=["not","hex"] should return 400, not crash."""
        rv = self.client.post("/epoch/enroll", json={
            "miner_pubkey": "test-miner",
            "miner_id": "test-miner",
            "signature": "ab" * 32,
            "public_key": ["not", "hex"],
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")

    def test_enroll_int_signature_returns_400(self):
        """signature=12345 should return 400."""
        rv = self.client.post("/epoch/enroll", json={
            "miner_pubkey": "test-miner",
            "miner_id": "test-miner",
            "signature": 12345,
            "public_key": "0" * 64,
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")


class TestGovernanceVoteSignatureValidation(unittest.TestCase):
    """#6125: /governance/vote crashes on non-string public_key."""

    def setUp(self):
        import rustchain_v2_integrated_v2.2.1_rip200 as app_module
        self.app = app_module.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_vote_list_public_key_returns_400(self):
        """public_key=["not","hex"] should return 400, not ValueError."""
        rv = self.client.post("/governance/vote", json={
            "proposal_id": 1,
            "wallet": "RTC-test",
            "vote": "yes",
            "nonce": "n-1",
            "signature": "ab" * 32,
            "public_key": ["not", "hex"],
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")

    def test_vote_bool_signature_returns_400(self):
        """signature=True should return 400, not AttributeError."""
        rv = self.client.post("/governance/vote", json={
            "proposal_id": 1,
            "wallet": "RTC-test",
            "vote": "yes",
            "nonce": "n-1",
            "signature": True,
            "public_key": "ab" * 16,
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")

    def test_vote_invalid_hex_public_key_returns_400(self):
        """Malformed hex public_key should return 400, not ValueError."""
        rv = self.client.post("/governance/vote", json={
            "proposal_id": 1,
            "wallet": "RTC-test",
            "vote": "yes",
            "nonce": "n-1",
            "signature": "ab" * 32,
            "public_key": "zzzzzzzzzzzzzzzz",
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")


class TestWalletTransferSignedValidation(unittest.TestCase):
    """#6127: /wallet/transfer/signed crashes on non-string public_key."""

    def setUp(self):
        import rustchain_v2_integrated_v2.2.1_rip200 as app_module
        self.app = app_module.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_transfer_list_public_key_returns_400(self):
        """public_key=["not","hex"] should return 400, not ValueError."""
        rv = self.client.post("/wallet/transfer/signed", json={
            "from_address": "RTC" + "a" * 40,
            "to_address": "RTC" + "b" * 40,
            "amount_rtc": 1.0,
            "nonce": 1733420000000,
            "signature": "ab" * 32,
            "public_key": ["not", "hex"],
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")

    def test_transfer_bool_signature_returns_400(self):
        """signature=True should return 400, not crash."""
        rv = self.client.post("/wallet/transfer/signed", json={
            "from_address": "RTC" + "a" * 40,
            "to_address": "RTC" + "b" * 40,
            "amount_rtc": 1.0,
            "nonce": 1733420000000,
            "signature": True,
            "public_key": "ab" * 16,
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")

    def test_transfer_invalid_hex_public_key_returns_400(self):
        """Malformed hex public_key should return 400, not ValueError."""
        rv = self.client.post("/wallet/transfer/signed", json={
            "from_address": "RTC" + "a" * 40,
            "to_address": "RTC" + "b" * 40,
            "amount_rtc": 1.0,
            "nonce": 1733420000000,
            "signature": "ab" * 32,
            "public_key": "zzzzzzzzzzzzzzzz",
        })
        self.assertIn(rv.status_code, (400, 422),
                      f"Expected 400-class, got {rv.status_code}: {rv.data[:200]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
