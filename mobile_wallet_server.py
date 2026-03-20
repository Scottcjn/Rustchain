// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import logging
import os
import re

DB_PATH = 'blockchain.db'
MOBILE_PORT = 5001

app = Flask(__name__)
CORS(app, origins=['*'])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_mobile_db():
    """Initialize database tables for mobile wallet"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_sessions (
                session_id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                device_info TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mobile_transactions (
                tx_id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                amount REAL NOT NULL,
                tx_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                block_hash TEXT,
                recipient TEXT,
                sender TEXT
            )
        ''')

        conn.commit()

def validate_wallet_address(address):
    """Validate wallet address format"""
    if not address or len(address) < 26 or len(address) > 35:
        return False
    return bool(re.match(r'^[A-Za-z0-9]+$', address))

def get_wallet_balance(wallet_address):
    """Get current balance for wallet"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as balance
            FROM transactions
            WHERE recipient = ? AND status = 'confirmed'
        ''', (wallet_address,))

        received = cursor.fetchone()[0] or 0

        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as spent
            FROM transactions
            WHERE sender = ? AND status = 'confirmed'
        ''', (wallet_address,))

        spent = cursor.fetchone()[0] or 0

        return max(0, received - spent)

def get_transaction_history(wallet_address, limit=50, offset=0):
    """Get transaction history for wallet"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT tx_hash, sender, recipient, amount, timestamp, status, block_hash
            FROM transactions
            WHERE sender = ? OR recipient = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        ''', (wallet_address, wallet_address, limit, offset))

        transactions = []
        for row in cursor.fetchall():
            tx_hash, sender, recipient, amount, timestamp, status, block_hash = row
            tx_type = 'sent' if sender == wallet_address else 'received'

            transactions.append({
                'tx_hash': tx_hash,
                'type': tx_type,
                'amount': amount,
                'timestamp': timestamp,
                'status': status,
                'sender': sender,
                'recipient': recipient,
                'block_hash': block_hash
            })

        return transactions

@app.route('/api/mobile/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'mobile_wallet_api'
    })

@app.route('/api/mobile/wallet/balance/<wallet_address>', methods=['GET'])
def get_balance(wallet_address):
    """Get wallet balance"""
    try:
        if not validate_wallet_address(wallet_address):
            return jsonify({'error': 'Invalid wallet address format'}), 400

        balance = get_wallet_balance(wallet_address)

        return jsonify({
            'wallet_address': wallet_address,
            'balance': balance,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting balance: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/mobile/wallet/history/<wallet_address>', methods=['GET'])
def get_history(wallet_address):
    """Get transaction history"""
    try:
        if not validate_wallet_address(wallet_address):
            return jsonify({'error': 'Invalid wallet address format'}), 400

        limit = min(int(request.args.get('limit', 20)), 100)
        offset = int(request.args.get('offset', 0))

        transactions = get_transaction_history(wallet_address, limit, offset)

        return jsonify({
            'wallet_address': wallet_address,
            'transactions': transactions,
            'limit': limit,
            'offset': offset,
            'timestamp': datetime.utcnow().isoformat()
        })

    except ValueError:
        return jsonify({'error': 'Invalid limit or offset parameter'}), 400
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/mobile/wallet/qr/<wallet_address>', methods=['GET'])
def generate_qr_data(wallet_address):
    """Generate QR code data for receiving payments"""
    try:
        if not validate_wallet_address(wallet_address):
            return jsonify({'error': 'Invalid wallet address format'}), 400

        amount = request.args.get('amount', '')
        memo = request.args.get('memo', '')

        qr_data = {
            'address': wallet_address,
            'protocol': 'rustchain'
        }

        if amount:
            try:
                qr_data['amount'] = float(amount)
            except ValueError:
                return jsonify({'error': 'Invalid amount format'}), 400

        if memo:
            qr_data['memo'] = memo[:100]

        qr_string = f"rustchain:{wallet_address}"
        if amount or memo:
            params = []
            if amount:
                params.append(f"amount={amount}")
            if memo:
                params.append(f"memo={memo}")
            qr_string += "?" + "&".join(params)

        return jsonify({
            'qr_data': qr_data,
            'qr_string': qr_string,
            'wallet_address': wallet_address,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error generating QR data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/mobile/wallet/send', methods=['POST'])
def send_transaction():
    """Create new transaction"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        sender = data.get('sender')
        recipient = data.get('recipient')
        amount = data.get('amount')

        if not all([sender, recipient, amount]):
            return jsonify({'error': 'Missing required fields: sender, recipient, amount'}), 400

        if not validate_wallet_address(sender) or not validate_wallet_address(recipient):
            return jsonify({'error': 'Invalid wallet address format'}), 400

        try:
            amount = float(amount)
            if amount <= 0:
                return jsonify({'error': 'Amount must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid amount format'}), 400

        sender_balance = get_wallet_balance(sender)
        if sender_balance < amount:
            return jsonify({'error': 'Insufficient balance'}), 400

        tx_hash = hashlib.sha256(f"{sender}{recipient}{amount}{time.time()}".encode()).hexdigest()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO mobile_transactions
                (tx_id, wallet_address, amount, tx_type, recipient, sender)
                VALUES (?, ?, ?, 'send', ?, ?)
            ''', (tx_hash, sender, amount, recipient, sender))
            conn.commit()

        return jsonify({
            'tx_hash': tx_hash,
            'status': 'pending',
            'message': 'Transaction submitted successfully',
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error sending transaction: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/mobile/wallet/session', methods=['POST'])
def create_session():
    """Create wallet session for mobile app"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        wallet_address = data.get('wallet_address')
        device_info = data.get('device_info', '')

        if not validate_wallet_address(wallet_address):
            return jsonify({'error': 'Invalid wallet address format'}), 400

        session_id = hashlib.sha256(f"{wallet_address}{time.time()}".encode()).hexdigest()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO wallet_sessions
                (session_id, wallet_address, device_info)
                VALUES (?, ?, ?)
            ''', (session_id, wallet_address, device_info))
            conn.commit()

        return jsonify({
            'session_id': session_id,
            'wallet_address': wallet_address,
            'expires_in': 86400,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/mobile/dashboard')
def mobile_dashboard():
    """Simple web dashboard for testing mobile API"""
    dashboard_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Mobile Wallet API</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 600px; margin: 0 auto; }
            .endpoint { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            .method { color: #007bff; font-weight: bold; }
            .url { background: #f8f9fa; padding: 5px; border-radius: 3px; font-family: monospace; }
            input, button { margin: 5px 0; padding: 8px; }
            button { background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; }
            .result { background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>RustChain Mobile Wallet API</h1>
            <p>Backend API for mobile wallet applications</p>

            <div class="endpoint">
                <h3><span class="method">GET</span> Balance Check</h3>
                <div class="url">/api/mobile/wallet/balance/{wallet_address}</div>
                <input type="text" id="balanceAddr" placeholder="Wallet address" style="width: 300px;">
                <button onclick="checkBalance()">Check Balance</button>
                <div id="balanceResult" class="result" style="display:none;"></div>
            </div>

            <div class="endpoint">
                <h3><span class="method">GET</span> Transaction History</h3>
                <div class="url">/api/mobile/wallet/history/{wallet_address}</div>
                <input type="text" id="historyAddr" placeholder="Wallet address" style="width: 300px;">
                <input type="number" id="historyLimit" placeholder="Limit (default: 20)" style="width: 150px;">
                <button onclick="getHistory()">Get History</button>
                <div id="historyResult" class="result" style="display:none;"></div>
            </div>

            <div class="endpoint">
                <h3><span class="method">GET</span> QR Code Data</h3>
                <div class="url">/api/mobile/wallet/qr/{wallet_address}</div>
                <input type="text" id="qrAddr" placeholder="Wallet address" style="width: 300px;"><br>
                <input type="number" id="qrAmount" placeholder="Amount (optional)" style="width: 150px;">
                <input type="text" id="qrMemo" placeholder="Memo (optional)" style="width: 200px;">
                <button onclick="generateQR()">Generate QR</button>
                <div id="qrResult" class="result" style="display:none;"></div>
            </div>

            <div class="endpoint">
                <h3>API Endpoints</h3>
                <ul>
                    <li><strong>Health:</strong> GET /api/mobile/health</li>
                    <li><strong>Balance:</strong> GET /api/mobile/wallet/balance/{address}</li>
                    <li><strong>History:</strong> GET /api/mobile/wallet/history/{address}</li>
                    <li><strong>QR Data:</strong> GET /api/mobile/wallet/qr/{address}</li>
                    <li><strong>Send TX:</strong> POST /api/mobile/wallet/send</li>
                    <li><strong>Session:</strong> POST /api/mobile/wallet/session</li>
                </ul>
            </div>
        </div>

        <script>
            async function checkBalance() {
                const addr = document.getElementById('balanceAddr').value;
                if (!addr) return;

                try {
                    const response = await fetch(`/api/mobile/wallet/balance/${addr}`);
                    const data = await response.json();
                    document.getElementById('balanceResult').innerHTML = JSON.stringify(data, null, 2);
                    document.getElementById('balanceResult').style.display = 'block';
                } catch (e) {
                    document.getElementById('balanceResult').innerHTML = 'Error: ' + e.message;
                    document.getElementById('balanceResult').style.display = 'block';
                }
            }

            async function getHistory() {
                const addr = document.getElementById('historyAddr').value;
                const limit = document.getElementById('historyLimit').value || 20;
                if (!addr) return;

                try {
                    const response = await fetch(`/api/mobile/wallet/history/${addr}?limit=${limit}`);
                    const data = await response.json();
                    document.getElementById('historyResult').innerHTML = JSON.stringify(data, null, 2);
                    document.getElementById('historyResult').style.display = 'block';
                } catch (e) {
                    document.getElementById('historyResult').innerHTML = 'Error: ' + e.message;
                    document.getElementById('historyResult').style.display = 'block';
                }
            }

            async function generateQR() {
                const addr = document.getElementById('qrAddr').value;
                const amount = document.getElementById('qrAmount').value;
                const memo = document.getElementById('qrMemo').value;
                if (!addr) return;

                let url = `/api/mobile/wallet/qr/${addr}`;
                const params = new URLSearchParams();
                if (amount) params.append('amount', amount);
                if (memo) params.append('memo', memo);
                if (params.toString()) url += '?' + params.toString();

                try {
                    const response = await fetch(url);
                    const data = await response.json();
                    document.getElementById('qrResult').innerHTML = JSON.stringify(data, null, 2);
                    document.getElementById('qrResult').style.display = 'block';
                } catch (e) {
                    document.getElementById('qrResult').innerHTML = 'Error: ' + e.message;
                    document.getElementById('qrResult').style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(dashboard_html)

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    init_mobile_db()
    logger.info(f"Starting Mobile Wallet API server on port {MOBILE_PORT}")
    logger.info("Dashboard available at: http://localhost:5001/mobile/dashboard")
    app.run(host='0.0.0.0', port=MOBILE_PORT, debug=True)
