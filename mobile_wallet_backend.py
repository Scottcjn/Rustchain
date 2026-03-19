// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import hashlib
import json
import time
from flask import Flask, request, jsonify, render_template_string
import threading
import os
import base64
import secrets

app = Flask(__name__)
DB_PATH = 'rustchain.db'

class MobileWalletBackend:
    def __init__(self):
        self.init_wallet_db()
        
    def init_wallet_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS wallet_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE,
                private_key TEXT,
                public_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            conn.execute('''CREATE TABLE IF NOT EXISTS mobile_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                device_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()
    
    def generate_address(self):
        private_key = secrets.token_hex(32)
        public_key = hashlib.sha256(private_key.encode()).hexdigest()
        address = 'RTC' + hashlib.sha256(public_key.encode()).hexdigest()[:34]
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO wallet_addresses (address, private_key, public_key) VALUES (?, ?, ?)",
                (address, private_key, public_key)
            )
            conn.commit()
        
        return {
            'address': address,
            'private_key': private_key,
            'public_key': public_key
        }
    
    def get_balance(self, address):
        balance = 0.0
        
        with sqlite3.connect(DB_PATH) as conn:
            # Incoming transactions
            cursor = conn.execute(
                "SELECT SUM(amount) FROM transactions WHERE to_address = ? AND status = 'confirmed'",
                (address,)
            )
            incoming = cursor.fetchone()[0] or 0
            
            # Outgoing transactions
            cursor = conn.execute(
                "SELECT SUM(amount) FROM transactions WHERE from_address = ? AND status = 'confirmed'",
                (address,)
            )
            outgoing = cursor.fetchone()[0] or 0
            
            balance = float(incoming) - float(outgoing)
        
        return max(0.0, balance)
    
    def get_transaction_history(self, address, limit=50):
        transactions = []
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT id, from_address, to_address, amount, fee, timestamp, status, block_hash
                FROM transactions 
                WHERE from_address = ? OR to_address = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (address, address, limit))
            
            for row in cursor.fetchall():
                tx_id, from_addr, to_addr, amount, fee, timestamp, status, block_hash = row
                
                tx_type = 'sent' if from_addr == address else 'received'
                
                transactions.append({
                    'id': tx_id,
                    'type': tx_type,
                    'from_address': from_addr,
                    'to_address': to_addr,
                    'amount': float(amount),
                    'fee': float(fee) if fee else 0.0,
                    'timestamp': timestamp,
                    'status': status,
                    'block_hash': block_hash,
                    'confirmations': self.get_confirmations(block_hash) if block_hash else 0
                })
        
        return transactions
    
    def get_confirmations(self, block_hash):
        if not block_hash:
            return 0
            
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM blocks WHERE id > (SELECT id FROM blocks WHERE hash = ?)", (block_hash,))
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def validate_address(self, address):
        if not address or not isinstance(address, str):
            return False
        if not address.startswith('RTC'):
            return False
        if len(address) != 37:  # RTC + 34 chars
            return False
        return True
    
    def create_transaction(self, from_address, to_address, amount, fee=0.001):
        if not self.validate_address(from_address) or not self.validate_address(to_address):
            return {'error': 'Invalid address format'}
        
        balance = self.get_balance(from_address)
        total_needed = float(amount) + float(fee)
        
        if balance < total_needed:
            return {'error': 'Insufficient balance'}
        
        # Get private key for signing
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT private_key FROM wallet_addresses WHERE address = ?", (from_address,))
            key_row = cursor.fetchone()
            if not key_row:
                return {'error': 'Private key not found'}
        
        # Create transaction hash
        tx_data = f"{from_address}{to_address}{amount}{fee}{time.time()}"
        tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()
        
        # Insert pending transaction
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO transactions (hash, from_address, to_address, amount, fee, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (tx_hash, from_address, to_address, amount, fee, time.time(), 'pending'))
            conn.commit()
        
        return {
            'transaction_hash': tx_hash,
            'status': 'pending',
            'amount': float(amount),
            'fee': float(fee)
        }

wallet_backend = MobileWalletBackend()

@app.route('/api/wallet/generate_address', methods=['POST'])
def api_generate_address():
    try:
        result = wallet_backend.generate_address()
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/balance/<address>', methods=['GET'])
def api_get_balance(address):
    try:
        if not wallet_backend.validate_address(address):
            return jsonify({'success': False, 'error': 'Invalid address'}), 400
        
        balance = wallet_backend.get_balance(address)
        return jsonify({'success': True, 'balance': balance})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/history/<address>', methods=['GET'])
def api_get_history(address):
    try:
        if not wallet_backend.validate_address(address):
            return jsonify({'success': False, 'error': 'Invalid address'}), 400
        
        limit = request.args.get('limit', 50, type=int)
        transactions = wallet_backend.get_transaction_history(address, limit)
        return jsonify({'success': True, 'transactions': transactions})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/send', methods=['POST'])
def api_send_transaction():
    try:
        data = request.get_json()
        from_address = data.get('from_address')
        to_address = data.get('to_address')
        amount = data.get('amount')
        fee = data.get('fee', 0.001)
        
        if not all([from_address, to_address, amount]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        result = wallet_backend.create_transaction(from_address, to_address, amount, fee)
        
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/validate_address/<address>', methods=['GET'])
def api_validate_address(address):
    try:
        is_valid = wallet_backend.validate_address(address)
        return jsonify({'success': True, 'valid': is_valid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/mobile_wallet_dashboard')
def mobile_wallet_dashboard():
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Mobile Wallet Backend</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
            .button { background: #007bff; color: white; padding: 8px 16px; border: none; cursor: pointer; }
            .input { padding: 8px; margin: 5px; width: 300px; }
            .result { margin-top: 10px; padding: 10px; background: #f8f9fa; }
            .error { background: #f8d7da; color: #721c24; }
            .success { background: #d4edda; color: #155724; }
        </style>
    </head>
    <body>
        <h1>RustChain Mobile Wallet Backend</h1>
        
        <div class="section">
            <h3>Generate New Address</h3>
            <button class="button" onclick="generateAddress()">Generate Address</button>
            <div id="newAddress" class="result" style="display:none;"></div>
        </div>
        
        <div class="section">
            <h3>Check Balance</h3>
            <input type="text" id="balanceAddress" class="input" placeholder="Enter RTC address">
            <button class="button" onclick="checkBalance()">Check Balance</button>
            <div id="balanceResult" class="result" style="display:none;"></div>
        </div>
        
        <div class="section">
            <h3>Transaction History</h3>
            <input type="text" id="historyAddress" class="input" placeholder="Enter RTC address">
            <button class="button" onclick="getHistory()">Get History</button>
            <div id="historyResult" class="result" style="display:none;"></div>
        </div>
        
        <div class="section">
            <h3>Send Transaction</h3>
            <input type="text" id="fromAddr" class="input" placeholder="From address"><br>
            <input type="text" id="toAddr" class="input" placeholder="To address"><br>
            <input type="number" id="amount" class="input" placeholder="Amount" step="0.000001"><br>
            <input type="number" id="fee" class="input" placeholder="Fee (optional)" value="0.001" step="0.000001"><br>
            <button class="button" onclick="sendTransaction()">Send</button>
            <div id="sendResult" class="result" style="display:none;"></div>
        </div>
        
        <script>
        async function generateAddress() {
            try {
                const response = await fetch('/api/wallet/generate_address', {method: 'POST'});
                const data = await response.json();
                const div = document.getElementById('newAddress');
                if (data.success) {
                    div.className = 'result success';
                    div.innerHTML = '<strong>New Address Generated:</strong><br>' +
                        'Address: ' + data.data.address + '<br>' +
                        'Private Key: ' + data.data.private_key + '<br>' +
                        '<small>Keep your private key safe!</small>';
                } else {
                    div.className = 'result error';
                    div.innerHTML = 'Error: ' + data.error;
                }
                div.style.display = 'block';
            } catch (e) {
                console.error(e);
            }
        }
        
        async function checkBalance() {
            const address = document.getElementById('balanceAddress').value;
            if (!address) return;
            
            try {
                const response = await fetch('/api/wallet/balance/' + address);
                const data = await response.json();
                const div = document.getElementById('balanceResult');
                if (data.success) {
                    div.className = 'result success';
                    div.innerHTML = 'Balance: ' + data.balance + ' RTC';
                } else {
                    div.className = 'result error';
                    div.innerHTML = 'Error: ' + data.error;
                }
                div.style.display = 'block';
            } catch (e) {
                console.error(e);
            }
        }
        
        async function getHistory() {
            const address = document.getElementById('historyAddress').value;
            if (!address) return;
            
            try {
                const response = await fetch('/api/wallet/history/' + address);
                const data = await response.json();
                const div = document.getElementById('historyResult');
                if (data.success) {
                    div.className = 'result success';
                    if (data.transactions.length === 0) {
                        div.innerHTML = 'No transactions found';
                    } else {
                        let html = '<strong>Transaction History:</strong><br>';
                        data.transactions.forEach(tx => {
                            html += '<div style="border-bottom:1px solid #ccc; padding:5px;">' +
                                'Type: ' + tx.type + '<br>' +
                                'Amount: ' + tx.amount + ' RTC<br>' +
                                'Status: ' + tx.status + '<br>' +
                                'Hash: ' + (tx.id || 'N/A') + '<br>' +
                                '</div>';
                        });
                        div.innerHTML = html;
                    }
                } else {
                    div.className = 'result error';
                    div.innerHTML = 'Error: ' + data.error;
                }
                div.style.display = 'block';
            } catch (e) {
                console.error(e);
            }
        }
        
        async function sendTransaction() {
            const fromAddr = document.getElementById('fromAddr').value;
            const toAddr = document.getElementById('toAddr').value;
            const amount = document.getElementById('amount').value;
            const fee = document.getElementById('fee').value;
            
            if (!fromAddr || !toAddr || !amount) {
                alert('Please fill required fields');
                return;
            }
            
            try {
                const response = await fetch('/api/wallet/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        from_address: fromAddr,
                        to_address: toAddr,
                        amount: parseFloat(amount),
                        fee: parseFloat(fee)
                    })
                });
                const data = await response.json();
                const div = document.getElementById('sendResult');
                if (data.success) {
                    div.className = 'result success';
                    div.innerHTML = 'Transaction created successfully!<br>' +
                        'Hash: ' + data.data.transaction_hash + '<br>' +
                        'Status: ' + data.data.status;
                } else {
                    div.className = 'result error';
                    div.innerHTML = 'Error: ' + data.error;
                }
                div.style.display = 'block';
            } catch (e) {
                console.error(e);
            }
        }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html_template)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)