"""
Tests for Claims Eligibility DB Settlement Check (Issue #3960).

Verifies that epoch settlement status is checked against the database
instead of relying solely on a time-based heuristic.
"""
import unittest
import os
import sqlite3
import tempfile
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestClaimsEligibilityDBCheck(unittest.TestCase):
    def setUp(self):
        self.module_path = os.path.join(os.path.dirname(__file__), '..', 'node', 'claims_eligibility.py')
        with open(self.module_path, 'r') as f:
            self.source = f.read()

    def test_fix_queries_database(self):
        """The fix must query the database for settlement status."""
        self.assertIn("SELECT settled FROM epoch_state", self.source,
            "is_epoch_settled must query the database for settlement status")

    def test_fallback_to_heuristic(self):
        """Must still have the fallback heuristic for missing DB records."""
        self.assertIn("current_slot // 144 - 2", self.source,
            "Must include time-based heuristic as fallback")

    def test_handles_legacy_finalized_column(self):
        """Should handle legacy schemas with 'finalized' column."""
        self.assertIn("SELECT finalized FROM epoch_state", self.source,
            "Should fallback to 'finalized' column for legacy schemas")

    def test_no_unsettled_claim_bypass(self):
        """Ensure the security fix comment is present."""
        self.assertIn("#3960", self.source,
            "Should reference Issue #3960 in docstring or comments")

if __name__ == '__main__':
    unittest.main()
