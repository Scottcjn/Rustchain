// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import hashlib
import json
import time
import os
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

DB_PATH = "rustchain.db"

class MobileWalletBridge:
    """Mobile wallet bridge for RustChain operations"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_wallet_tables()

    def init_wallet_tables(self):
        """Initialize wallet-specific database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Wallet addresses table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallet_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE NOT NULL,
                    private_key TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    label TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')

            # Transaction cache for mobile performance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mobile_tx_cache (
                    tx_hash TEXT PRIMARY KEY,
                    from_address TEXT,
                    to_address TEXT,
                    amount REAL,
                    timestamp TIMESTAMP,
                    block_height INTEGER,
                    status TEXT DEFAULT 'confirmed'
                )
            ''')

            conn.commit()

    def generate_address(self, label: str = None) -> Dict:
        """Generate a new wallet address"""
        try:
            # Generate keypair using simple hash-based approach
            private_key = hashlib.sha256(os.urandom(32)).hexdigest()
            public_key = hashlib.sha256(private_key.encode()).hexdigest()
            address = f"RC{hashlib.sha256(public_key.encode()).hexdigest()[:32]}"

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO wallet_addresses (address, private_key, public_key, label)
                    VALUES (?, ?, ?, ?)
                ''', (address, private_key, public_key, label))
                conn.commit()

            return {
                'success': True,
                'address': address,
                'public_key': public_key,
                'label': label
            }

        except Exception as e:
            logger.error(f"Address generation failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_balance(self, address: str) -> Dict:
        """Get balance for a specific address"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Calculate balance from transactions
                cursor.execute('''
                    SELECT
                        COALESCE(SUM(CASE WHEN to_address = ? THEN amount ELSE 0 END), 0) as received,
                        COALESCE(SUM(CASE WHEN from_address = ? THEN amount ELSE 0 END), 0) as sent
                    FROM transactions
                    WHERE to_address = ? OR from_address = ?
                ''', (address, address, address, address))

                result = cursor.fetchone()
                received = result[0] if result[0] else 0.0
                sent = result[1] if result[1] else 0.0
                balance = received - sent

                return {
                    'success': True,
                    'balance': balance,
                    'received': received,
                    'sent': sent
                }

        except Exception as e:
            logger.error(f"Balance calculation failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_transaction_history(self, address: str, limit: int = 50) -> Dict:
        """Get transaction history for an address"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT tx_hash, from_address, to_address, amount, timestamp,
                           CASE WHEN to_address = ? THEN 'incoming' ELSE 'outgoing' END as type
                    FROM transactions
                    WHERE from_address = ? OR to_address = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (address, address, address, limit))

                transactions = []
                for row in cursor.fetchall():
                    transactions.append({
                        'hash': row[0],
                        'from': row[1],
                        'to': row[2],
                        'amount': row[3],
                        'timestamp': row[4],
                        'type': row[5]
                    })

                return {
                    'success': True,
                    'transactions': transactions,
                    'count': len(transactions)
                }

        except Exception as e:
            logger.error(f"Transaction history failed: {e}")
            return {'success': False, 'error': str(e)}

    def create_transaction(self, from_address: str, to_address: str, amount: float) -> Dict:
        """Create a new transaction"""
        try:
            # Validate balance
            balance_result = self.get_balance(from_address)
            if not balance_result['success']:
                return balance_result

            if balance_result['balance'] < amount:
                return {'success': False, 'error': 'Insufficient balance'}

            # Generate transaction
            tx_data = {
                'from': from_address,
                'to': to_address,
                'amount': amount,
                'timestamp': time.time()
            }

            tx_hash = hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions (tx_hash, from_address, to_address, amount, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (tx_hash, from_address, to_address, amount, tx_data['timestamp']))

                # Cache for mobile
                cursor.execute('''
                    INSERT OR REPLACE INTO mobile_tx_cache
                    (tx_hash, from_address, to_address, amount, timestamp, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                ''', (tx_hash, from_address, to_address, amount, tx_data['timestamp']))

                conn.commit()

            return {
                'success': True,
                'tx_hash': tx_hash,
                'from': from_address,
                'to': to_address,
                'amount': amount
            }

        except Exception as e:
            logger.error(f"Transaction creation failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_wallet_addresses(self) -> Dict:
        """Get all wallet addresses"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT address, label, created_at, is_active
                    FROM wallet_addresses
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')

                addresses = []
                for row in cursor.fetchall():
                    addr_data = {
                        'address': row[0],
                        'label': row[1],
                        'created_at': row[2],
                        'is_active': bool(row[3])
                    }

                    # Add balance info
                    balance_info = self.get_balance(row[0])
                    if balance_info['success']:
                        addr_data['balance'] = balance_info['balance']

                    addresses.append(addr_data)

                return {
                    'success': True,
                    'addresses': addresses,
                    'count': len(addresses)
                }

        except Exception as e:
            logger.error(f"Get addresses failed: {e}")
            return {'success': False, 'error': str(e)}

    def validate_address(self, address: str) -> Dict:
        """Validate if an address is properly formatted"""
        try:
            if not address or len(address) < 10:
                return {'success': False, 'valid': False, 'error': 'Address too short'}

            if not address.startswith('RC'):
                return {'success': False, 'valid': False, 'error': 'Invalid address prefix'}

            # Check if address exists in our wallet
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM wallet_addresses WHERE address = ?', (address,))
                is_own = cursor.fetchone() is not None

            return {
                'success': True,
                'valid': True,
                'is_own_address': is_own
            }

        except Exception as e:
            logger.error(f"Address validation failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_blockchain_info(self) -> Dict:
        """Get basic blockchain information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get block count
                cursor.execute('SELECT COUNT(*) FROM blocks')
                block_count = cursor.fetchone()[0]

                # Get transaction count
                cursor.execute('SELECT COUNT(*) FROM transactions')
                tx_count = cursor.fetchone()[0]

                # Get latest block
                cursor.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT 1')
                latest_block = cursor.fetchone()

                return {
                    'success': True,
                    'block_count': block_count,
                    'transaction_count': tx_count,
                    'latest_block_height': latest_block[1] if latest_block else 0,
                    'latest_block_hash': latest_block[0] if latest_block else None
                }

        except Exception as e:
            logger.error(f"Blockchain info failed: {e}")
            return {'success': False, 'error': str(e)}

    def generate_qr_data(self, address: str, amount: float = None, label: str = None) -> Dict:
        """Generate QR code data for receiving payments"""
        try:
            qr_data = {'address': address}

            if amount:
                qr_data['amount'] = amount
            if label:
                qr_data['label'] = label

            qr_string = f"rustchain:{address}"
            if amount or label:
                params = []
                if amount:
                    params.append(f"amount={amount}")
                if label:
                    params.append(f"label={label}")
                qr_string += "?" + "&".join(params)

            return {
                'success': True,
                'qr_data': qr_data,
                'qr_string': qr_string
            }

        except Exception as e:
            logger.error(f"QR generation failed: {e}")
            return {'success': False, 'error': str(e)}
