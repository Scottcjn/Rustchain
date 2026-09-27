"""
Tests for RustChain Python SDK Wallet address generation and signing.
"""

import hashlib
import unittest
from rustchain_sdk.wallet import RustChainWallet


class TestWalletAddressDerivation(unittest.TestCase):
    def test_address_matches_node_derivation(self):
        """
        Verify that Python SDK wallet address matches node address_from_pubkey derivation:
        Node derivation rule: "RTC" + SHA256(pubkey).hexdigest()[:40]
        """
        wallet = RustChainWallet.create()
        pubkey_bytes = bytes.fromhex(wallet.public_key_hex)
        expected_node_address = "RTC" + hashlib.sha256(pubkey_bytes).hexdigest()[:40]

        self.assertEqual(
            wallet.address,
            expected_node_address,
            f"SDK address {wallet.address} does not match node expected derivation {expected_node_address}"
        )
        self.assertEqual(len(wallet.address), 43)  # 'RTC' (3) + 40 hex chars = 43 chars
        self.assertTrue(wallet.address.startswith("RTC"))

    def test_rfc8032_known_vector_address(self):
        pubkey = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        expected_address = "RTC" + hashlib.sha256(pubkey).hexdigest()[:40]
        self.assertEqual(expected_address, "RTC21fe31dfa154a261626bf854046fd2271b7bed4b")


if __name__ == "__main__":
    unittest.main()
