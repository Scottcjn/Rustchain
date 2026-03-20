// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
import sqlite3
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
import sys
sys.path.append('.')

from otc_bridge import OTCBridge, app

class TestOTCBridge(unittest.TestCase):

    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False)
        self.test_db.close()
        self.db_path = self.test_db.name

        self.bridge = OTCBridge(self.db_path)
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['DB_PATH'] = self.db_path
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_database_initialization(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        expected_tables = ['orders', 'transactions', 'escrows']
        for table in expected_tables:
            self.assertIn(table, tables)

    def test_create_sell_order(self):
        order_id = self.bridge.create_order(
            order_type='sell',
            rtc_amount=100.0,
            price_per_rtc=0.10,
            payment_currency='ETH',
            seller_address='0x123...abc',
            contact_info='seller@test.com'
        )

        self.assertIsNotNone(order_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()

        self.assertEqual(order[1], 'sell')
        self.assertEqual(order[2], 100.0)
        self.assertEqual(order[3], 0.10)
        self.assertEqual(order[4], 'ETH')
        self.assertEqual(order[7], 'open')

    def test_create_buy_order(self):
        order_id = self.bridge.create_order(
            order_type='buy',
            rtc_amount=50.0,
            price_per_rtc=0.12,
            payment_currency='USDC',
            buyer_address='0x456...def',
            contact_info='buyer@test.com'
        )

        self.assertIsNotNone(order_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()

        self.assertEqual(order[1], 'buy')
        self.assertEqual(order[2], 50.0)
        self.assertEqual(order[6], '0x456...def')

    def test_get_orders(self):
        self.bridge.create_order('sell', 100.0, 0.10, 'ETH', 'addr1', 'test1@test.com')
        self.bridge.create_order('buy', 75.0, 0.11, 'USDC', 'addr2', 'test2@test.com')

        all_orders = self.bridge.get_orders()
        sell_orders = self.bridge.get_orders(order_type='sell')
        buy_orders = self.bridge.get_orders(order_type='buy')

        self.assertEqual(len(all_orders), 2)
        self.assertEqual(len(sell_orders), 1)
        self.assertEqual(len(buy_orders), 1)

    def test_order_matching(self):
        sell_order_id = self.bridge.create_order(
            'sell', 100.0, 0.10, 'ETH', 'seller_addr', 'seller@test.com'
        )

        matches = self.bridge.find_matching_orders(
            order_type='buy',
            rtc_amount=50.0,
            max_price=0.11,
            payment_currency='ETH'
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['id'], sell_order_id)

    def test_no_matching_orders(self):
        self.bridge.create_order(
            'sell', 100.0, 0.15, 'ETH', 'seller_addr', 'seller@test.com'
        )

        matches = self.bridge.find_matching_orders(
            order_type='buy',
            rtc_amount=50.0,
            max_price=0.10,
            payment_currency='ETH'
        )

        self.assertEqual(len(matches), 0)

    def test_create_escrow(self):
        sell_order_id = self.bridge.create_order(
            'sell', 100.0, 0.10, 'ETH', 'seller_addr', 'seller@test.com'
        )

        escrow_id = self.bridge.create_escrow(
            seller_order_id=sell_order_id,
            buyer_address='buyer_addr',
            rtc_amount=50.0,
            payment_amount=5.0,
            payment_currency='ETH'
        )

        self.assertIsNotNone(escrow_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM escrows WHERE id = ?", (escrow_id,))
            escrow = cursor.fetchone()

        self.assertEqual(escrow[1], sell_order_id)
        self.assertEqual(escrow[2], 'buyer_addr')
        self.assertEqual(escrow[3], 50.0)
        self.assertEqual(escrow[4], 5.0)
        self.assertEqual(escrow[6], 'pending')

    def test_update_order_status(self):
        order_id = self.bridge.create_order(
            'sell', 100.0, 0.10, 'ETH', 'seller_addr', 'seller@test.com'
        )

        success = self.bridge.update_order_status(order_id, 'filled')
        self.assertTrue(success)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
            status = cursor.fetchone()[0]

        self.assertEqual(status, 'filled')

    def test_update_escrow_status(self):
        sell_order_id = self.bridge.create_order(
            'sell', 100.0, 0.10, 'ETH', 'seller_addr', 'seller@test.com'
        )

        escrow_id = self.bridge.create_escrow(
            sell_order_id, 'buyer_addr', 50.0, 5.0, 'ETH'
        )

        success = self.bridge.update_escrow_status(escrow_id, 'completed')
        self.assertTrue(success)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM escrows WHERE id = ?", (escrow_id,))
            status = cursor.fetchone()[0]

        self.assertEqual(status, 'completed')

    def test_api_create_order(self):
        order_data = {
            'order_type': 'sell',
            'rtc_amount': 200.0,
            'price_per_rtc': 0.08,
            'payment_currency': 'ETH',
            'seller_address': '0x789...ghi',
            'contact_info': 'api_seller@test.com'
        }

        response = self.client.post(
            '/api/orders',
            data=json.dumps(order_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 201)
        data = json.loads(response.get_data(as_text=True))
        self.assertIn('order_id', data)
        self.assertEqual(data['status'], 'created')

    def test_api_get_orders(self):
        self.bridge.create_order(
            'sell', 150.0, 0.09, 'USDC', 'addr1', 'test1@test.com'
        )
        self.bridge.create_order(
            'buy', 100.0, 0.11, 'ETH', 'addr2', 'test2@test.com'
        )

        response = self.client.get('/api/orders')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data), 2)

    def test_api_find_matches(self):
        self.bridge.create_order(
            'sell', 100.0, 0.10, 'ETH', 'seller_addr', 'seller@test.com'
        )

        match_data = {
            'order_type': 'buy',
            'rtc_amount': 50.0,
            'max_price': 0.12,
            'payment_currency': 'ETH'
        }

        response = self.client.post(
            '/api/matches',
            data=json.dumps(match_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data), 1)

    def test_api_create_escrow(self):
        sell_order_id = self.bridge.create_order(
            'sell', 100.0, 0.10, 'ETH', 'seller_addr', 'seller@test.com'
        )

        escrow_data = {
            'seller_order_id': sell_order_id,
            'buyer_address': 'buyer_addr',
            'rtc_amount': 75.0,
            'payment_amount': 7.5,
            'payment_currency': 'ETH'
        }

        response = self.client.post(
            '/api/escrow',
            data=json.dumps(escrow_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 201)
        data = json.loads(response.get_data(as_text=True))
        self.assertIn('escrow_id', data)

    def test_api_invalid_order_data(self):
        invalid_data = {
            'order_type': 'invalid',
            'rtc_amount': -10.0
        }

        response = self.client.post(
            '/api/orders',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)

    def test_api_missing_required_fields(self):
        incomplete_data = {
            'order_type': 'sell',
            'rtc_amount': 100.0
        }

        response = self.client.post(
            '/api/orders',
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)

    def test_database_transaction_rollback(self):
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = sqlite3.Error("Database error")
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value.__enter__.return_value = mock_conn

            bridge = OTCBridge(':memory:')
            order_id = bridge.create_order(
                'sell', 100.0, 0.10, 'ETH', 'addr', 'test@test.com'
            )

            self.assertIsNone(order_id)

    def test_order_validation(self):
        invalid_orders = [
            ('invalid_type', 100.0, 0.10, 'ETH', 'addr', 'test@test.com'),
            ('sell', -100.0, 0.10, 'ETH', 'addr', 'test@test.com'),
            ('sell', 100.0, -0.10, 'ETH', 'addr', 'test@test.com'),
            ('sell', 100.0, 0.10, '', 'addr', 'test@test.com'),
        ]

        for order_params in invalid_orders:
            order_id = self.bridge.create_order(*order_params)
            self.assertIsNone(order_id)

    def test_get_order_statistics(self):
        self.bridge.create_order('sell', 100.0, 0.10, 'ETH', 'addr1', 'test1')
        self.bridge.create_order('sell', 200.0, 0.12, 'USDC', 'addr2', 'test2')
        self.bridge.create_order('buy', 150.0, 0.11, 'ETH', 'addr3', 'test3')

        stats = self.bridge.get_order_statistics()

        self.assertEqual(stats['total_orders'], 3)
        self.assertEqual(stats['sell_orders'], 2)
        self.assertEqual(stats['buy_orders'], 1)
        self.assertEqual(stats['total_rtc_for_sale'], 300.0)
        self.assertEqual(stats['total_rtc_wanted'], 150.0)

if __name__ == '__main__':
    unittest.main()
