# SPDX-License-Identifier: MIT

import unittest
from pathlib import Path


class TestEnhancedExplorerXss(unittest.TestCase):
    def setUp(self):
        self.html = Path(__file__).with_name("enhanced-explorer.html").read_text(
            encoding="utf-8"
        )

    def test_transaction_identity_fields_are_escaped(self):
        self.assertIn("${esc(tx.hash || tx.tx_hash || 'N/A')}", self.html)
        self.assertIn("${esc(tx.from || 'N/A')}", self.html)
        self.assertIn("${esc(tx.to || 'N/A')}", self.html)

        self.assertNotIn("${tx.hash || tx.tx_hash || 'N/A'}</code>", self.html)
        self.assertNotIn("${tx.from || 'N/A'}</code>", self.html)
        self.assertNotIn("${tx.to || 'N/A'}</code>", self.html)

    def test_api_numeric_fields_are_formatted_safely(self):
        self.assertIn("function safeNumber(value, fallback = 0)", self.html)
        self.assertIn("function formatNumber(value, decimals)", self.html)
        self.assertIn(
            "${esc(formatNumber(miner.earnings || miner.total_earned, 2))} RTC",
            self.html,
        )
        self.assertIn(
            "${formatNumber(safeNumber(tx.amount) / 1000000, 2)} RTC",
            self.html,
        )
        self.assertIn(
            "${formatNumber(safeNumber(tx.fee) / 1000000, 4)} RTC",
            self.html,
        )
        self.assertNotIn(
            "(miner.earnings || miner.total_earned || 0).toFixed(2)",
            self.html,
        )
        self.assertNotIn("(tx.amount / 1000000 || 0).toFixed(2)", self.html)
        self.assertNotIn("(tx.fee / 1000000 || 0).toFixed(4)", self.html)


if __name__ == "__main__":
    unittest.main()
