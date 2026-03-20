// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
import tempfile
import os
import json
import sqlite3
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wallet_cli import WalletCLI, generate_keypair, create_keystore, unlock_keystore


class TestWalletCLI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.keystore_path = os.path.join(self.temp_dir, 'test_keystore.json')
        self.wallet_db = os.path.join(self.temp_dir, 'test_wallet.db')
        self.test_password = 'test_password_123'

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_keypair(self):
        private_key, public_key = generate_keypair()
        self.assertIsInstance(private_key, str)
        self.assertIsInstance(public_key, str)
        self.assertEqual(len(private_key), 64)  # 32 bytes hex
        self.assertEqual(len(public_key), 64)   # 32 bytes hex

    def test_create_keystore(self):
        private_key, public_key = generate_keypair()
        create_keystore(self.keystore_path, private_key, public_key, self.test_password)

        self.assertTrue(os.path.exists(self.keystore_path))

        with open(self.keystore_path, 'r') as f:
            keystore_data = json.load(f)

        self.assertIn('address', keystore_data)
        self.assertIn('crypto', keystore_data)
        self.assertIn('ciphertext', keystore_data['crypto'])
        self.assertIn('salt', keystore_data['crypto'])
        self.assertIn('iv', keystore_data['crypto'])

    def test_unlock_keystore_success(self):
        private_key, public_key = generate_keypair()
        create_keystore(self.keystore_path, private_key, public_key, self.test_password)

        unlocked_key = unlock_keystore(self.keystore_path, self.test_password)
        self.assertEqual(unlocked_key, private_key)

    def test_unlock_keystore_wrong_password(self):
        private_key, public_key = generate_keypair()
        create_keystore(self.keystore_path, private_key, public_key, self.test_password)

        with self.assertRaises(ValueError):
            unlock_keystore(self.keystore_path, 'wrong_password')

    def test_wallet_cli_init(self):
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        self.assertEqual(cli.keystore_path, self.keystore_path)
        self.assertEqual(cli.wallet_db, self.wallet_db)
        self.assertIsNone(cli.private_key)

    @patch('getpass.getpass')
    def test_create_wallet_command(self, mock_getpass):
        mock_getpass.return_value = self.test_password

        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        result = cli.create_wallet()

        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.keystore_path))

    @patch('getpass.getpass')
    def test_unlock_wallet_command(self, mock_getpass):
        mock_getpass.return_value = self.test_password

        # First create wallet
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        cli.create_wallet()

        # Then unlock it
        result = cli.unlock_wallet()
        self.assertTrue(result)
        self.assertIsNotNone(cli.private_key)

    def test_get_balance_unlocked_wallet(self):
        # Create and unlock wallet first
        private_key, public_key = generate_keypair()
        create_keystore(self.keystore_path, private_key, public_key, self.test_password)

        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        cli.private_key = private_key

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {'balance': '1000.50', 'address': cli.get_address()}
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            balance = cli.get_balance()
            self.assertEqual(balance, '1000.50')

    def test_get_balance_locked_wallet(self):
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        balance = cli.get_balance()
        self.assertIsNone(balance)

    def test_send_transaction_unlocked(self):
        private_key, public_key = generate_keypair()
        create_keystore(self.keystore_path, private_key, public_key, self.test_password)

        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        cli.private_key = private_key

        to_address = "1234567890abcdef"
        amount = "100.0"

        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {'success': True, 'tx_id': 'abc123'}
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = cli.send_transaction(to_address, amount)
            self.assertTrue(result)

    def test_send_transaction_locked(self):
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        result = cli.send_transaction("1234567890abcdef", "100.0")
        self.assertFalse(result)

    def test_get_transaction_history(self):
        private_key, public_key = generate_keypair()
        create_keystore(self.keystore_path, private_key, public_key, self.test_password)

        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        cli.private_key = private_key

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'transactions': [
                    {'tx_id': 'abc123', 'amount': '50.0', 'type': 'sent'},
                    {'tx_id': 'def456', 'amount': '25.5', 'type': 'received'}
                ]
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            history = cli.get_transaction_history()
            self.assertEqual(len(history), 2)

    def test_database_operations(self):
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)
        cli._init_database()

        # Test storing transaction
        tx_data = {
            'tx_id': 'test123',
            'amount': '100.0',
            'to_address': 'recipient123',
            'status': 'pending'
        }
        cli._store_transaction(tx_data)

        # Verify transaction stored
        with sqlite3.connect(self.wallet_db) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM transactions WHERE tx_id = ?', ('test123',))
            result = cursor.fetchone()

        self.assertIsNotNone(result)
        self.assertEqual(result[1], '100.0')

    def test_validate_address_format(self):
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)

        # Valid hex address
        valid_addr = "1234567890abcdef1234567890abcdef12345678"
        self.assertTrue(cli._validate_address(valid_addr))

        # Invalid characters
        invalid_addr = "1234567890ghijkl"
        self.assertFalse(cli._validate_address(invalid_addr))

        # Empty address
        self.assertFalse(cli._validate_address(""))

    def test_validate_amount_format(self):
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)

        # Valid amounts
        self.assertTrue(cli._validate_amount("100.0"))
        self.assertTrue(cli._validate_amount("0.001"))
        self.assertTrue(cli._validate_amount("1000"))

        # Invalid amounts
        self.assertFalse(cli._validate_amount("abc"))
        self.assertFalse(cli._validate_amount("-100"))
        self.assertFalse(cli._validate_amount("0"))

    def test_command_parsing(self):
        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)

        # Test create command
        with patch.object(cli, 'create_wallet') as mock_create:
            mock_create.return_value = True
            cli.parse_command(['create'])
            mock_create.assert_called_once()

        # Test balance command
        with patch.object(cli, 'get_balance') as mock_balance:
            mock_balance.return_value = '100.0'
            cli.parse_command(['balance'])
            mock_balance.assert_called_once()

        # Test send command
        with patch.object(cli, 'send_transaction') as mock_send:
            mock_send.return_value = True
            cli.parse_command(['send', 'addr123', '50.0'])
            mock_send.assert_called_once_with('addr123', '50.0')

    def test_keystore_backup_restore(self):
        private_key, public_key = generate_keypair()
        create_keystore(self.keystore_path, private_key, public_key, self.test_password)

        backup_path = os.path.join(self.temp_dir, 'backup.json')

        cli = WalletCLI(keystore_path=self.keystore_path, wallet_db=self.wallet_db)

        # Backup keystore
        result = cli.backup_keystore(backup_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(backup_path))

        # Restore from backup
        new_keystore = os.path.join(self.temp_dir, 'restored.json')
        result = cli.restore_keystore(backup_path, new_keystore)
        self.assertTrue(result)

        # Verify restored keystore works
        restored_key = unlock_keystore(new_keystore, self.test_password)
        self.assertEqual(restored_key, private_key)


if __name__ == '__main__':
    unittest.main()
