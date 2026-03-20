# SPDX-License-Identifier: MIT

import json
import os
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock, mock_open
import pytest
from pathlib import Path

# Import the actual wallet CLI module
from rustchain_wallet_cli import RustChainWallet, WalletError


def mock_http_response(data, status_code=200, ok=True):
    """Create a mock HTTP response object."""
    response = MagicMock()
    response.status_code = status_code
    response.ok = ok
    response.json.return_value = data
    response.text = json.dumps(data) if isinstance(data, dict) else str(data)
    return response


class TestWalletCLI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.wallet_path = os.path.join(self.temp_dir, "test_wallet.json")
        self.keystore_path = os.path.join(self.temp_dir, "keystore.json")

        # Override wallet directory for testing
        self.original_wallet_dir = Path.home() / ".rustchain" / "wallets"
        self.test_wallet_dir = Path(self.temp_dir) / "wallets"

        # Patch WALLET_DIR and DB_PATH
        self.wallet_dir_patcher = patch('rustchain_wallet_cli.WALLET_DIR', self.test_wallet_dir)
        self.db_path_patcher = patch('rustchain_wallet_cli.DB_PATH', self.test_wallet_dir / "wallet.db")

        self.wallet_dir_patcher.start()
        self.db_path_patcher.start()

    def tearDown(self):
        self.wallet_dir_patcher.stop()
        self.db_path_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_wallet_initialization(self):
        """Test wallet initialization creates proper directory structure."""
        wallet = RustChainWallet()
        self.assertTrue(self.test_wallet_dir.exists())
        self.assertTrue((self.test_wallet_dir / "wallet.db").exists())

    @patch('rustchain_wallet_cli.requests.get')
    def test_get_balance_success(self, mock_get):
        """Test successful balance retrieval."""
        mock_get.return_value = mock_http_response({'balance': 100.5})

        wallet = RustChainWallet()
        balance = wallet.get_balance("test_address")

        self.assertEqual(balance, 100.5)
        mock_get.assert_called_once()

    @patch('rustchain_wallet_cli.requests.get')
    def test_get_balance_network_error(self, mock_get):
        """Test balance retrieval with network error."""
        mock_get.side_effect = Exception("Network error")

        wallet = RustChainWallet()

        with self.assertRaises(WalletError):
            wallet.get_balance("test_address")

    def test_create_wallet_with_password(self):
        """Test wallet creation with password protection."""
        wallet = RustChainWallet()

        with patch('rustchain_wallet_cli.getpass.getpass', return_value='testpassword'):
            result = wallet.create_wallet('test_wallet')

        self.assertIsInstance(result, dict)
        self.assertIn('address', result)
        self.assertIn('mnemonic', result)

        # Verify wallet was saved to database
        wallets = wallet.list_wallets()
        self.assertIn('test_wallet', wallets)

    def test_list_empty_wallets(self):
        """Test listing wallets when none exist."""
        wallet = RustChainWallet()
        wallets = wallet.list_wallets()
        self.assertEqual(wallets, [])

    @patch('rustchain_wallet_cli.requests.post')
    def test_send_transaction_success(self, mock_post):
        """Test successful transaction sending."""
        mock_post.return_value = mock_http_response({'tx_hash': 'abc123', 'success': True})

        wallet = RustChainWallet()

        # Create a test wallet first
        with patch('rustchain_wallet_cli.getpass.getpass', return_value='testpassword'):
            wallet.create_wallet('test_wallet')

        with patch('rustchain_wallet_cli.getpass.getpass', return_value='testpassword'):
            result = wallet.send_transaction('test_wallet', 'recipient_address', 10.0)

        self.assertIsInstance(result, dict)
        self.assertIn('tx_hash', result)
        mock_post.assert_called_once()

    def test_invalid_wallet_name_handling(self):
        """Test handling of invalid wallet names."""
        wallet = RustChainWallet()

        with self.assertRaises(WalletError):
            wallet.get_wallet_info('nonexistent_wallet')

    def test_mnemonic_generation(self):
        """Test that mnemonic generation works properly."""
        wallet = RustChainWallet()

        with patch('rustchain_wallet_cli.getpass.getpass', return_value='testpassword'):
            result = wallet.create_wallet('mnemonic_test')

        mnemonic_words = result['mnemonic'].split()
        self.assertEqual(len(mnemonic_words), 12)  # Standard 12-word mnemonic

        # All words should be valid (no empty strings)
        for word in mnemonic_words:
            self.assertTrue(len(word) > 0)


if __name__ == '__main__':
    unittest.main()
