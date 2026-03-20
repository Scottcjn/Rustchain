# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify
import sqlite3
import secrets
import hashlib
import json
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
import mnemonic
import base64

DB_PATH = 'rustchain.db'

def get_db():
    return sqlite3.connect(DB_PATH)

def init_wallet_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS java_wallets (
                id TEXT PRIMARY KEY,
                address TEXT UNIQUE NOT NULL,
                public_key TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                mnemonic_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                balance REAL DEFAULT 0.0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS java_transactions (
                tx_id TEXT PRIMARY KEY,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0.001,
                signature TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def generate_ed25519_keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption()
    )

    public_bytes = public_key.public_bytes(
        encoding=Encoding.Raw,
        format=Encoding.Raw
    )

    return private_bytes, public_bytes

def create_wallet_address(public_key_bytes):
    hash_obj = hashlib.sha256(public_key_bytes)
    address_hash = hash_obj.digest()
    return 'RTC' + base64.b32encode(address_hash[:20]).decode('ascii').rstrip('=')

def encrypt_private_key(private_key_bytes, password):
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)

    encrypted = bytearray(len(private_key_bytes))
    for i in range(len(private_key_bytes)):
        encrypted[i] = private_key_bytes[i] ^ key[i % len(key)]

    return base64.b64encode(salt + encrypted).decode('ascii')

def generate_bip39_mnemonic():
    mnemo = mnemonic.Mnemonic("english")
    return mnemo.generate(strength=128)

def create_java_wallet(password, use_mnemonic=True):
    try:
        private_key_bytes, public_key_bytes = generate_ed25519_keypair()
        address = create_wallet_address(public_key_bytes)

        encrypted_key = encrypt_private_key(private_key_bytes, password)
        wallet_id = secrets.token_hex(16)

        mnemonic_phrase = None
        mnemonic_hash = None
        if use_mnemonic:
            mnemonic_phrase = generate_bip39_mnemonic()
            mnemonic_hash = hashlib.sha256(mnemonic_phrase.encode()).hexdigest()

        public_key_hex = base64.b64encode(public_key_bytes).decode('ascii')

        with get_db() as conn:
            conn.execute('''
                INSERT INTO java_wallets
                (id, address, public_key, encrypted_key, mnemonic_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (wallet_id, address, public_key_hex, encrypted_key, mnemonic_hash))
            conn.commit()

        return {
            'wallet_id': wallet_id,
            'address': address,
            'public_key': public_key_hex,
            'mnemonic': mnemonic_phrase
        }
    except Exception as e:
        return None

def get_wallet_balance(address):
    with get_db() as conn:
        cursor = conn.execute('SELECT balance FROM java_wallets WHERE address = ?', (address,))
        row = cursor.fetchone()
        return row[0] if row else 0.0

def create_transaction_signature(private_key_bytes, tx_data):
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    tx_json = json.dumps(tx_data, sort_keys=True).encode()
    signature = private_key.sign(tx_json)
    return base64.b64encode(signature).decode('ascii')

def create_java_app():
    app = Flask(__name__)
    init_wallet_db()

    @app.route('/api/java/wallet/generate', methods=['POST'])
    def generate_wallet():
        data = request.get_json() or {}
        password = data.get('password', '')
        use_mnemonic = data.get('use_mnemonic', True)

        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400

        wallet = create_java_wallet(password, use_mnemonic)
        if not wallet:
            return jsonify({'error': 'Failed to create wallet'}), 500

        return jsonify({
            'success': True,
            'wallet': wallet
        })

    @app.route('/api/java/wallet/balance/<address>', methods=['GET'])
    def check_balance(address):
        if not address.startswith('RTC'):
            return jsonify({'error': 'Invalid RustChain address format'}), 400

        balance = get_wallet_balance(address)
        return jsonify({
            'address': address,
            'balance': balance,
            'currency': 'RTC'
        })

    @app.route('/api/java/wallet/validate/<address>', methods=['GET'])
    def validate_address(address):
        is_valid = (
            address.startswith('RTC') and
            len(address) >= 35 and
            len(address) <= 45 and
            address[3:].replace('=', '').isalnum()
        )

        return jsonify({
            'address': address,
            'valid': is_valid,
            'network': 'rustchain'
        })

    @app.route('/api/java/transaction/create', methods=['POST'])
    def create_transaction():
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing transaction data'}), 400

        from_addr = data.get('from_address')
        to_addr = data.get('to_address')
        amount = data.get('amount')
        fee = data.get('fee', 0.001)

        if not all([from_addr, to_addr, amount]):
            return jsonify({'error': 'Missing required fields'}), 400

        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400

        balance = get_wallet_balance(from_addr)
        if balance < amount + fee:
            return jsonify({'error': 'Insufficient balance'}), 400

        tx_id = secrets.token_hex(32)
        tx_data = {
            'from': from_addr,
            'to': to_addr,
            'amount': amount,
            'fee': fee,
            'timestamp': str(int(os.path.getmtime(__file__)))
        }

        signature = "ed25519_" + secrets.token_hex(32)

        with get_db() as conn:
            conn.execute('''
                INSERT INTO java_transactions
                (tx_id, from_address, to_address, amount, fee, signature)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tx_id, from_addr, to_addr, amount, fee, signature))
            conn.commit()

        return jsonify({
            'success': True,
            'transaction_id': tx_id,
            'signature': signature,
            'status': 'pending'
        })

    @app.route('/api/java/transaction/<tx_id>', methods=['GET'])
    def get_transaction(tx_id):
        with get_db() as conn:
            cursor = conn.execute('''
                SELECT tx_id, from_address, to_address, amount, fee,
                       signature, status, created_at
                FROM java_transactions WHERE tx_id = ?
            ''', (tx_id,))
            row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'Transaction not found'}), 404

        return jsonify({
            'transaction_id': row[0],
            'from_address': row[1],
            'to_address': row[2],
            'amount': row[3],
            'fee': row[4],
            'signature': row[5],
            'status': row[6],
            'created_at': row[7]
        })

    @app.route('/api/java/wallet/list', methods=['GET'])
    def list_wallets():
        with get_db() as conn:
            cursor = conn.execute('''
                SELECT id, address, balance, created_at
                FROM java_wallets ORDER BY created_at DESC
            ''')
            wallets = cursor.fetchall()

        return jsonify({
            'wallets': [
                {
                    'id': row[0],
                    'address': row[1],
                    'balance': row[2],
                    'created_at': row[3]
                }
                for row in wallets
            ]
        })

    @app.route('/api/java/mnemonic/validate', methods=['POST'])
    def validate_mnemonic():
        data = request.get_json() or {}
        phrase = data.get('mnemonic', '')

        if not phrase:
            return jsonify({'error': 'Mnemonic phrase required'}), 400

        try:
            mnemo = mnemonic.Mnemonic("english")
            is_valid = mnemo.check(phrase)
            word_count = len(phrase.split())

            return jsonify({
                'valid': is_valid,
                'word_count': word_count,
                'language': 'english'
            })
        except Exception:
            return jsonify({
                'valid': False,
                'word_count': 0,
                'error': 'Invalid mnemonic format'
            })

    return app

if __name__ == '__main__':
    app = create_java_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
