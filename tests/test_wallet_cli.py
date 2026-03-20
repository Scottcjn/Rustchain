# SPDX-License-Identifier: MIT

import json
import os
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock, mock_open
import pytest

import wallet_cli


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

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_wallet_creates_valid_keys(self):
        """Test wallet generation creates proper key pair."""
        private_key, public_key, address = wallet_cli.generate_wallet()

        self.assertEqual(len(private_key), 64)  # 32 bytes hex
        self.assertEqual(len(public_key), 128)  # 64 bytes hex
        self.assertEqual(len(address), 42)  # 20 bytes hex with 0x prefix
        self.assertTrue(address.startswith("0x"))

        # Keys should be valid hex
        int(private_key, 16)
        int(public_key, 16)
        int(address[2:], 16)

    def test_save_and_load_wallet(self):
        """Test saving wallet to file and loading it back."""
        private_key = "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
        public_key = "04" + "1234" * 31
        address = "0x1234567890123456789012345678901234567890"

        wallet_cli.save_wallet(self.wallet_path, private_key, public_key, address)
        self.assertTrue(os.path.exists(self.wallet_path))

        loaded_private, loaded_public, loaded_address = wallet_cli.load_wallet(self.wallet_path)
        self.assertEqual(loaded_private, private_key)
        self.assertEqual(loaded_public, public_key)
        self.assertEqual(loaded_address, address)

    @patch('wallet_cli.requests.get')
    def test_check_balance_success(self, mock_get):
        """Test balance checking with successful API response."""
        mock_response = mock_http_response({
            "miner_id": "0x1234567890123456789012345678901234567890",
            "amount_rtc": 125.75,
            "status": "active"
        })
        mock_get.return_value = mock_response

        address = "0x1234567890123456789012345678901234567890"
        balance = wallet_cli.check_balance(address)

        self.assertEqual(balance, 125.75)
        mock_get.assert_called_once()
        expected_url = f"{wallet_cli.NODE_URL}/api/balance/{address}"
        mock_get.assert_called_with(expected_url, timeout=10)

    @patch('wallet_cli.requests.get')
    def test_check_balance_api_error(self, mock_get):
        """Test balance checking with API error response."""
        mock_response = mock_http_response({"error": "Address not found"}, status_code=404, ok=False)
        mock_get.return_value = mock_response

        address = "0xinvalidaddress"
        balance = wallet_cli.check_balance(address)

        self.assertEqual(balance, 0)

    @patch('wallet_cli.requests.get')
    def test_check_balance_network_error(self, mock_get):
        """Test balance checking with network connection error."""
        mock_get.side_effect = Exception("Connection timeout")

        address = "0x1234567890123456789012345678901234567890"
        balance = wallet_cli.check_balance(address)

        self.assertEqual(balance, 0)

    def test_encrypt_decrypt_keystore(self):
        """Test keystore encryption and decryption."""
        private_key = "deadbeefcafebabe1234567890abcdef1234567890abcdef1234567890abcdef"
        password = "super_secret_password123"

        # Encrypt private key to keystore
        keystore_data = wallet_cli.encrypt_keystore(private_key, password)
        self.assertIn("ciphertext", keystore_data)
        self.assertIn("salt", keystore_data)
        self.assertIn("iv", keystore_data)

        # Save and load keystore
        with open(self.keystore_path, 'w') as f:
            json.dump(keystore_data, f)

        # Decrypt keystore back to private key
        decrypted_key = wallet_cli.decrypt_keystore(self.keystore_path, password)
        self.assertEqual(decrypted_key, private_key)

    def test_decrypt_keystore_wrong_password(self):
        """Test keystore decryption with incorrect password."""
        private_key = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        correct_password = "correct_password"
        wrong_password = "wrong_password"

        keystore_data = wallet_cli.encrypt_keystore(private_key, correct_password)
        with open(self.keystore_path, 'w') as f:
            json.dump(keystore_data, f)

        with self.assertRaises(ValueError):
            wallet_cli.decrypt_keystore(self.keystore_path, wrong_password)

    @patch('wallet_cli.requests.post')
    def test_send_transaction_success(self, mock_post):
        """Test successful transaction sending."""
        mock_response = mock_http_response({
            "transaction_hash": "0xabcdef1234567890",
            "status": "pending",
            "fee": 0.001
        })
        mock_post.return_value = mock_response

        from_address = "0x1111111111111111111111111111111111111111"
        to_address = "0x2222222222222222222222222222222222222222"
        amount = 50.5
        private_key = "1234567890abcdef" * 4

        tx_hash = wallet_cli.send_transaction(from_address, to_address, amount, private_key)

        self.assertEqual(tx_hash, "0xabcdef1234567890")
        mock_post.assert_called_once()

    def test_parse_command_line_args(self):
        """Test command line argument parsing."""
        # Test create command
        args = wallet_cli.parse_args(['create', '--output', '/tmp/wallet.json'])
        self.assertEqual(args.command, 'create')
        self.assertEqual(args.output, '/tmp/wallet.json')

        # Test balance command
        args = wallet_cli.parse_args(['balance', '0x1234567890123456789012345678901234567890'])
        self.assertEqual(args.command, 'balance')
        self.assertEqual(args.address, '0x1234567890123456789012345678901234567890')

        # Test import command
        args = wallet_cli.parse_args(['import', '--keystore', '/tmp/keystore.json', '--password', 'secret'])
        self.assertEqual(args.command, 'import')
        self.assertEqual(args.keystore, '/tmp/keystore.json')
        self.assertEqual(args.password, 'secret')

    def test_import_private_key_validation(self):
        """Test importing wallet with private key validation."""
        # Valid private key
        valid_key = "1234567890abcdef" * 4
        self.assertTrue(wallet_cli.is_valid_private_key(valid_key))

        # Invalid length
        short_key = "1234567890abcdef"
        self.assertFalse(wallet_cli.is_valid_private_key(short_key))

        # Invalid characters
        invalid_key = "gggg567890abcdef" * 4
        self.assertFalse(wallet_cli.is_valid_private_key(invalid_key))

    @patch('wallet_cli.getpass.getpass')
    def test_secure_password_input(self, mock_getpass):
        """Test secure password input handling."""
        mock_getpass.return_value = "test_password123"

        password = wallet_cli.get_secure_password("Enter password: ")
        self.assertEqual(password, "test_password123")
        mock_getpass.assert_called_once_with("Enter password: ")

    def test_wallet_file_format_validation(self):
        """Test wallet file format validation."""
        # Create invalid wallet file
        invalid_data = {"invalid": "format"}
        with open(self.wallet_path, 'w') as f:
            json.dump(invalid_data, f)

        with self.assertRaises(ValueError):
            wallet_cli.load_wallet(self.wallet_path)

        # Create valid wallet file
        valid_data = {
            "private_key": "1234567890abcdef" * 4,
            "public_key": "04" + "abcd" * 31,
            "address": "0x1234567890123456789012345678901234567890"
        }
        with open(self.wallet_path, 'w') as f:
            json.dump(valid_data, f)

        # Should load without error
        private_key, public_key, address = wallet_cli.load_wallet(self.wallet_path)
        self.assertEqual(private_key, valid_data["private_key"])


if __name__ == '__main__':
    unittest.main()
