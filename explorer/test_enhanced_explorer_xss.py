import unittest
from pathlib import Path


class TestEnhancedExplorerXss(unittest.TestCase):
    def setUp(self):
        self.html = Path("enhanced-explorer.html").read_text()

    def test_transaction_identity_fields_are_escaped(self):
        self.assertIn("${esc(tx.hash || tx.tx_hash || 'N/A')}", self.html)
        self.assertIn("${esc(tx.from || 'N/A')}", self.html)
        self.assertIn("${esc(tx.to || 'N/A')}", self.html)

        self.assertNotIn("${tx.hash || tx.tx_hash || 'N/A'}</code>", self.html)
        self.assertNotIn("${tx.from || 'N/A'}</code>", self.html)
        self.assertNotIn("${tx.to || 'N/A'}</code>", self.html)


if __name__ == "__main__":
    unittest.main()
