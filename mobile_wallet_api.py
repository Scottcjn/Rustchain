# SPDX-License-Identifier: MIT

import sqlite3
import json
import qrcode
import io
import base64
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import hashlib
import secrets
import os

app = Flask(__name__)

DB_PATH = 'rustchain.db'

def init_wallet_db():
    """Initialize wallet database tables"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                private_key TEXT NOT NULL,
                label TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE NOT NULL,
                address TEXT NOT NULL,
                amount REAL NOT NULL,
                tx_type TEXT NOT NULL,
                block_height INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmations INTEGER DEFAULT 0,
                fee REAL DEFAULT 0.0,
                memo TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_balance (
                address TEXT PRIMARY KEY,
                confirmed_balance REAL DEFAULT 0.0,
                unconfirmed_balance REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()

def generate_wallet_address():
    """Generate a new wallet address with private key"""
    private_key = secrets.token_hex(32)

    # Simple address generation using hash
    addr_hash = hashlib.sha256(private_key.encode()).hexdigest()[:32]
    address = f"RTC{addr_hash}"

    return address, private_key

def get_wallet_balance(address):
    """Get wallet balance for specific address"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT confirmed_balance, unconfirmed_balance FROM wallet_balance WHERE address = ?',
            (address,)
        )
        result = cursor.fetchone()

        if result:
            return {
                'confirmed': result[0],
                'unconfirmed': result[1],
                'total': result[0] + result[1]
            }
        return {'confirmed': 0.0, 'unconfirmed': 0.0, 'total': 0.0}

def validate_rtc_address(address):
    """Validate RTC address format"""
    if not address or not isinstance(address, str):
        return False
    return address.startswith('RTC') and len(address) == 35

@app.route('/')
def mobile_wallet_dashboard():
    """Mobile wallet API dashboard"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Rustchain Mobile Wallet API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
            .container { max-width: 800px; margin: 0 auto; }
            .endpoint { background: #2d2d2d; padding: 15px; margin: 10px 0; border-radius: 8px; }
            .method { color: #4CAF50; font-weight: bold; }
            .path { color: #2196F3; font-family: monospace; }
            .desc { color: #ccc; margin-top: 5px; }
            h1 { color: #FF6B35; text-align: center; }
            h2 { color: #4CAF50; border-bottom: 2px solid #4CAF50; padding-bottom: 5px; }
            .status { background: #4CAF50; color: white; padding: 5px 10px; border-radius: 4px; display: inline-block; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🦀 Rustchain Mobile Wallet API</h1>
            <div class="status">API Status: Active</div>

            <h2>Available Endpoints</h2>

            <div class="endpoint">
                <span class="method">GET</span> <span class="path">/api/balance/{address}</span>
                <div class="desc">Get wallet balance for specified RTC address</div>
            </div>

            <div class="endpoint">
                <span class="method">GET</span> <span class="path">/api/transactions/{address}</span>
                <div class="desc">Get transaction history for specified address</div>
            </div>

            <div class="endpoint">
                <span class="method">POST</span> <span class="path">/api/generate-address</span>
                <div class="desc">Generate new wallet address</div>
            </div>

            <div class="endpoint">
                <span class="method">GET</span> <span class="path">/api/qr/{address}</span>
                <div class="desc">Generate QR code for receive address</div>
            </div>

            <div class="endpoint">
                <span class="method">GET</span> <span class="path">/api/wallet/addresses</span>
                <div class="desc">List all wallet addresses</div>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/api/balance/<address>')
def get_balance(address):
    """Get balance for wallet address"""
    try:
        if not validate_rtc_address(address):
            return jsonify({
                'success': False,
                'error': 'Invalid RTC address format'
            }), 400

        balance = get_wallet_balance(address)

        return jsonify({
            'success': True,
            'address': address,
            'balance': balance,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to fetch balance: {str(e)}'
        }), 500

@app.route('/api/transactions/<address>')
def get_transactions(address):
    """Get transaction history for address"""
    try:
        if not validate_rtc_address(address):
            return jsonify({
                'success': False,
                'error': 'Invalid RTC address format'
            }), 400

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tx_hash, amount, tx_type, block_height, timestamp,
                       confirmations, fee, memo
                FROM wallet_transactions
                WHERE address = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (address, limit, offset))

            rows = cursor.fetchall()

            transactions = []
            for row in rows:
                transactions.append({
                    'tx_hash': row[0],
                    'amount': row[1],
                    'type': row[2],
                    'block_height': row[3],
                    'timestamp': row[4],
                    'confirmations': row[5],
                    'fee': row[6],
                    'memo': row[7]
                })

        return jsonify({
            'success': True,
            'address': address,
            'transactions': transactions,
            'count': len(transactions),
            'limit': limit,
            'offset': offset
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to fetch transactions: {str(e)}'
        }), 500

@app.route('/api/generate-address', methods=['POST'])
def create_address():
    """Generate new wallet address"""
    try:
        data = request.get_json() or {}
        label = data.get('label', 'Mobile Wallet')

        address, private_key = generate_wallet_address()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO wallet_addresses (address, private_key, label)
                VALUES (?, ?, ?)
            ''', (address, private_key, label))

            # Initialize balance entry
            cursor.execute('''
                INSERT OR REPLACE INTO wallet_balance (address, confirmed_balance, unconfirmed_balance)
                VALUES (?, 0.0, 0.0)
            ''', (address,))

            conn.commit()

        return jsonify({
            'success': True,
            'address': address,
            'label': label,
            'created_at': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to generate address: {str(e)}'
        }), 500

@app.route('/api/qr/<address>')
def generate_qr_code(address):
    """Generate QR code for receive address"""
    try:
        if not validate_rtc_address(address):
            return jsonify({
                'success': False,
                'error': 'Invalid RTC address format'
            }), 400

        # Check if address exists in wallet
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT address FROM wallet_addresses WHERE address = ?', (address,))
            if not cursor.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Address not found in wallet'
                }), 404

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        qr_data = f"rustchain:{address}"
        qr.add_data(qr_data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()

        return jsonify({
            'success': True,
            'address': address,
            'qr_code': f'data:image/png;base64,{img_str}',
            'qr_data': qr_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to generate QR code: {str(e)}'
        }), 500

@app.route('/api/wallet/addresses')
def list_addresses():
    """List all wallet addresses"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.address, a.label, a.created_at, a.is_active,
                       COALESCE(b.confirmed_balance, 0.0) as balance
                FROM wallet_addresses a
                LEFT JOIN wallet_balance b ON a.address = b.address
                WHERE a.is_active = 1
                ORDER BY a.created_at DESC
            ''')

            rows = cursor.fetchall()

            addresses = []
            for row in rows:
                addresses.append({
                    'address': row[0],
                    'label': row[1],
                    'created_at': row[2],
                    'is_active': bool(row[3]),
                    'balance': row[4]
                })

        return jsonify({
            'success': True,
            'addresses': addresses,
            'count': len(addresses)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to list addresses: {str(e)}'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'API endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    init_wallet_db()
    app.run(debug=True, host='0.0.0.0', port=5001)
