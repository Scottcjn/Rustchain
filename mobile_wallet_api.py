// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sqlite3
import json
import hashlib
import time
from flask import Flask, jsonify, request
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)

# Database configuration
DB_PATH = os.environ.get('BLOCKCHAIN_DB_PATH', 'blockchain.db')

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_wallet_tables():
    """Initialize wallet-related tables if they don't exist"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                private_key TEXT,
                public_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE NOT NULL,
                from_address TEXT,
                to_address TEXT,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                block_height INTEGER,
                confirmations INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending'
            )
        ''')

        conn.commit()

@app.route('/api/wallet/balance/<address>', methods=['GET'])
def get_balance(address):
    """Get balance for a specific address"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Calculate balance from transactions
            cursor.execute('''
                SELECT
                    COALESCE(SUM(CASE WHEN to_address = ? THEN amount ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN from_address = ? THEN amount + fee ELSE 0 END), 0) as balance
                FROM transactions
                WHERE (to_address = ? OR from_address = ?) AND status = 'confirmed'
            ''', (address, address, address, address))

            result = cursor.fetchone()
            balance = result[0] if result else 0

            return jsonify({
                'success': True,
                'address': address,
                'balance': balance,
                'currency': 'RTC'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/transactions/<address>', methods=['GET'])
def get_transaction_history(address):
    """Get transaction history for an address"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT tx_hash, from_address, to_address, amount, fee,
                       timestamp, block_height, confirmations, status
                FROM transactions
                WHERE from_address = ? OR to_address = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (address, address, limit, offset))

            transactions = []
            for row in cursor.fetchall():
                tx_hash, from_addr, to_addr, amount, fee, timestamp, block_height, confirmations, status = row

                # Determine transaction type
                tx_type = 'received' if to_addr == address else 'sent'

                transactions.append({
                    'tx_hash': tx_hash,
                    'type': tx_type,
                    'from_address': from_addr,
                    'to_address': to_addr,
                    'amount': amount,
                    'fee': fee,
                    'timestamp': timestamp,
                    'block_height': block_height,
                    'confirmations': confirmations,
                    'status': status
                })

            # Get total count for pagination
            cursor.execute('''
                SELECT COUNT(*) FROM transactions
                WHERE from_address = ? OR to_address = ?
            ''', (address, address))
            total_count = cursor.fetchone()[0]

            return jsonify({
                'success': True,
                'transactions': transactions,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_count,
                    'has_more': (offset + limit) < total_count
                }
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/generate-address', methods=['POST'])
def generate_receive_address():
    """Generate a new receive address"""
    try:
        # Simple address generation (in real implementation, use proper crypto)
        timestamp = str(int(time.time()))
        seed = request.json.get('seed', timestamp)

        # Generate address hash
        address_hash = hashlib.sha256(seed.encode()).hexdigest()[:32]
        address = f"RTC{address_hash}"

        # Generate keys (simplified)
        private_key = hashlib.sha256(f"priv_{seed}".encode()).hexdigest()
        public_key = hashlib.sha256(f"pub_{seed}".encode()).hexdigest()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO addresses (address, private_key, public_key)
                VALUES (?, ?, ?)
            ''', (address, private_key, public_key))
            conn.commit()

        return jsonify({
            'success': True,
            'address': address,
            'public_key': public_key
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/qr-code/<address>', methods=['GET'])
def generate_qr_code(address):
    """Generate QR code for receive address"""
    try:
        amount = request.args.get('amount', '')
        label = request.args.get('label', '')

        # Create payment URI
        uri = f"rustchain:{address}"
        if amount:
            uri += f"?amount={amount}"
        if label:
            separator = '&' if amount else '?'
            uri += f"{separator}label={label}"

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        return jsonify({
            'success': True,
            'address': address,
            'qr_code': f"data:image/png;base64,{qr_base64}",
            'uri': uri
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/broadcast', methods=['POST'])
def broadcast_transaction():
    """Broadcast a new transaction"""
    try:
        data = request.json
        from_address = data.get('from_address')
        to_address = data.get('to_address')
        amount = float(data.get('amount'))
        fee = float(data.get('fee', 0.001))
        private_key = data.get('private_key')

        if not all([from_address, to_address, amount, private_key]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Verify private key belongs to from_address
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT address FROM addresses
                WHERE address = ? AND private_key = ?
            ''', (from_address, private_key))

            if not cursor.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Invalid private key for address'
                }), 401

        # Check balance
        cursor.execute('''
            SELECT
                COALESCE(SUM(CASE WHEN to_address = ? THEN amount ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN from_address = ? THEN amount + fee ELSE 0 END), 0) as balance
            FROM transactions
            WHERE (to_address = ? OR from_address = ?) AND status = 'confirmed'
        ''', (from_address, from_address, from_address, from_address))

        current_balance = cursor.fetchone()[0]
        if current_balance < (amount + fee):
            return jsonify({
                'success': False,
                'error': 'Insufficient balance'
            }), 400

        # Generate transaction hash
        tx_data = f"{from_address}{to_address}{amount}{fee}{time.time()}"
        tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()

        # Insert transaction
        cursor.execute('''
            INSERT INTO transactions (tx_hash, from_address, to_address, amount, fee, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (tx_hash, from_address, to_address, amount, fee))

        conn.commit()

        return jsonify({
            'success': True,
            'tx_hash': tx_hash,
            'status': 'pending',
            'message': 'Transaction broadcasted successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/addresses', methods=['GET'])
def list_addresses():
    """List all wallet addresses"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT address, public_key, created_at FROM addresses
                ORDER BY created_at DESC
            ''')

            addresses = []
            for row in cursor.fetchall():
                address, public_key, created_at = row
                addresses.append({
                    'address': address,
                    'public_key': public_key,
                    'created_at': created_at
                })

            return jsonify({
                'success': True,
                'addresses': addresses
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/transaction/<tx_hash>', methods=['GET'])
def get_transaction_details(tx_hash):
    """Get detailed transaction information"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tx_hash, from_address, to_address, amount, fee,
                       timestamp, block_height, confirmations, status
                FROM transactions
                WHERE tx_hash = ?
            ''', (tx_hash,))

            row = cursor.fetchone()
            if not row:
                return jsonify({
                    'success': False,
                    'error': 'Transaction not found'
                }), 404

            tx_hash, from_addr, to_addr, amount, fee, timestamp, block_height, confirmations, status = row

            return jsonify({
                'success': True,
                'transaction': {
                    'tx_hash': tx_hash,
                    'from_address': from_addr,
                    'to_address': to_addr,
                    'amount': amount,
                    'fee': fee,
                    'timestamp': timestamp,
                    'block_height': block_height,
                    'confirmations': confirmations,
                    'status': status
                }
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    init_wallet_tables()
    app.run(host='0.0.0.0', port=5000, debug=True)
