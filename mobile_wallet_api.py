// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import sqlite3
import json
import qrcode
import io
import base64
import hashlib
import time
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=['*'])

DB_PATH = 'rustchain.db'
BLOCKS_DB = 'blocks.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS wallets (
            address TEXT PRIMARY KEY,
            private_key TEXT,
            public_key TEXT,
            balance REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
            tx_id TEXT PRIMARY KEY,
            from_address TEXT,
            to_address TEXT,
            amount REAL,
            fee REAL DEFAULT 0.001,
            timestamp TIMESTAMP,
            block_height INTEGER,
            status TEXT DEFAULT 'pending'
        )''')

def get_wallet_balance(address):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT balance FROM wallets WHERE address = ?', (address,))
        result = cursor.fetchone()
        return result[0] if result else 0.0

def get_wallet_transactions(address, limit=50):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT tx_id, from_address, to_address, amount, fee, timestamp, block_height, status 
            FROM transactions 
            WHERE from_address = ? OR to_address = ? 
            ORDER BY timestamp DESC LIMIT ?
        ''', (address, address, limit))
        
        transactions = []
        for row in cursor.fetchall():
            tx_type = 'sent' if row[1] == address else 'received'
            transactions.append({
                'tx_id': row[0],
                'from_address': row[1],
                'to_address': row[2],
                'amount': row[3],
                'fee': row[4],
                'timestamp': row[5],
                'block_height': row[6],
                'status': row[7],
                'type': tx_type
            })
        return transactions

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    img_b64 = base64.b64encode(img_io.getvalue()).decode()
    return f"data:image/png;base64,{img_b64}"

@app.route('/api/wallet/<address>/balance', methods=['GET'])
def get_balance(address):
    try:
        balance = get_wallet_balance(address)
        return jsonify({
            'success': True,
            'address': address,
            'balance': balance
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/<address>/transactions', methods=['GET'])
def get_transactions(address):
    try:
        limit = int(request.args.get('limit', 50))
        transactions = get_wallet_transactions(address, limit)
        return jsonify({
            'success': True,
            'address': address,
            'transactions': transactions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/<address>/qr', methods=['GET'])
def generate_receive_qr(address):
    try:
        amount = request.args.get('amount', '')
        memo = request.args.get('memo', '')
        
        qr_data = f"rustchain:{address}"
        if amount:
            qr_data += f"?amount={amount}"
        if memo:
            separator = "&" if amount else "?"
            qr_data += f"{separator}memo={memo}"
        
        qr_image = generate_qr_code(qr_data)
        
        return jsonify({
            'success': True,
            'address': address,
            'qr_data': qr_data,
            'qr_image': qr_image
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/send', methods=['POST'])
def send_transaction():
    try:
        data = request.json
        from_address = data.get('from_address')
        to_address = data.get('to_address')
        amount = float(data.get('amount'))
        fee = float(data.get('fee', 0.001))
        
        if not all([from_address, to_address, amount]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        sender_balance = get_wallet_balance(from_address)
        if sender_balance < amount + fee:
            return jsonify({'success': False, 'error': 'Insufficient balance'}), 400
        
        tx_id = hashlib.sha256(f"{from_address}{to_address}{amount}{time.time()}".encode()).hexdigest()
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO transactions (tx_id, from_address, to_address, amount, fee, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (tx_id, from_address, to_address, amount, fee, timestamp, 'pending'))
            
            conn.execute('UPDATE wallets SET balance = balance - ? WHERE address = ?', 
                        (amount + fee, from_address))
            conn.execute('UPDATE wallets SET balance = balance + ? WHERE address = ?', 
                        (amount, to_address))
        
        return jsonify({
            'success': True,
            'tx_id': tx_id,
            'message': 'Transaction submitted'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/create', methods=['POST'])
def create_wallet():
    try:
        import secrets
        private_key = secrets.token_hex(32)
        public_key = hashlib.sha256(private_key.encode()).hexdigest()
        address = f"RTC{public_key[:32]}"
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO wallets (address, private_key, public_key, balance)
                VALUES (?, ?, ?, ?)
            ''', (address, private_key, public_key, 0.0))
        
        return jsonify({
            'success': True,
            'address': address,
            'private_key': private_key,
            'public_key': public_key
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/info', methods=['GET'])
def get_network_info():
    try:
        with sqlite3.connect(BLOCKS_DB) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM blocks')
            block_count = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT height FROM blocks ORDER BY height DESC LIMIT 1')
            latest_block = cursor.fetchone()
            latest_height = latest_block[0] if latest_block else 0
        
        return jsonify({
            'success': True,
            'block_count': block_count,
            'latest_height': latest_height,
            'network': 'Rustchain'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def index():
    return render_template_string('''
    <h1>Rustchain Mobile Wallet API</h1>
    <p>Available endpoints:</p>
    <ul>
        <li>GET /api/wallet/{address}/balance - Get wallet balance</li>
        <li>GET /api/wallet/{address}/transactions - Get transaction history</li>
        <li>GET /api/wallet/{address}/qr - Generate QR code for receiving</li>
        <li>POST /api/wallet/send - Send transaction</li>
        <li>POST /api/wallet/create - Create new wallet</li>
        <li>GET /api/network/info - Get network information</li>
    </ul>
    ''')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)