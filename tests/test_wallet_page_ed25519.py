# SPDX-License-Identifier: MIT
"""Regression checks for the native Ed25519 web wallet implementation."""

import unittest
from pathlib import Path


WALLET_PAGE = Path(__file__).parents[1] / "site" / "wallet.html"


class WalletPageEd25519Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WALLET_PAGE.read_text(encoding="utf-8")

    def test_wallet_page_generates_ed25519_keys(self) -> None:
        self.assertIn("name: 'Ed25519'", self.source)
        self.assertIn("exportKey('jwk'", self.source)
        self.assertIn("curve: 'Ed25519'", self.source)
        self.assertNotIn("ECDSA", self.source)
        self.assertNotIn("P-256", self.source)

    def test_wallet_page_uses_raw_ed25519_public_key_for_address(self) -> None:
        self.assertIn("const pubKeyHex = base64UrlToHex(publicJwk.x);", self.source)
        self.assertIn("crypto.subtle.digest('SHA-256', addressKeyBytes)", self.source)
        self.assertIn("'RTC' + hashHex.substring(0, 40)", self.source)


if __name__ == "__main__":
    unittest.main()
