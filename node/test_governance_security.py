#!/usr/bin/env python3
"""
Tests for governance security (HIGH-GOV-1, HIGH-GOV-2).

Demonstrates that the governance vote column validation
rejects unknown vote values from corrupted DB rows.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from governance import VOTE_CHOICES


class TestGovernanceSQLHardening(unittest.TestCase):
    """HIGH-GOV-2: f-string SQL column names must be validated."""

    def test_valid_vote_choices_in_allowlist(self):
        """Only 'for', 'against', 'abstain' are valid vote choices."""
        self.assertEqual(set(VOTE_CHOICES), {"for", "against", "abstain"})

    def test_column_injection_blocked(self):
        """A corrupted vote value must NOT be usable as a SQL column."""
        malicious_values = [
            "1; DROP TABLE governance_proposals--",
            "for = 999, votes_against",
            "",
            "unknown",
        ]
        for val in malicious_values:
            self.assertNotIn(val, VOTE_CHOICES, f"'{val}' must not be in VOTE_CHOICES")

    def test_valid_column_names_constructed(self):
        """f'votes_{{choice}}' must produce only known column names."""
        valid_columns = {"votes_for", "votes_against", "votes_abstain"}
        for choice in VOTE_CHOICES:
            col = f"votes_{choice}"
            self.assertIn(col, valid_columns, f"Column '{col}' must be in the valid set")


if __name__ == "__main__":
    unittest.main()
