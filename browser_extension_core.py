// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import hashlib
import secrets
import hmac
import json
import os
from datetime import datetime
import base64

app = Flask(__name__)

DB_PATH = 'rustchain.db'

def init_extension_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS extension_wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id TEXT UNIQUE NOT NULL,
            encrypted_private_key TEXT NOT NULL,
            public_key TEXT NOT NULL,
            address TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS extension_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id TEXT NOT NULL,
            tx_hash TEXT NOT NULL,
            amount REAL NOT NULL,
            recipient TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()

def generate_keypair():
    private_key = secrets.token_hex(32)
    public_key = hashlib.sha256(private_key.encode()).hexdigest()
    address = 'RC' + hashlib.sha256(public_key.encode()).hexdigest()[:40]
    return private_key, public_key, address

def encrypt_private_key(private_key, password):
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    encrypted = bytes(a ^ b for a, b in zip(private_key.encode(), key[:len(private_key)]))
    return base64.b64encode(salt + encrypted).decode()

def decrypt_private_key(encrypted_key, password):
    data = base64.b64decode(encrypted_key)
    salt = data[:16]
    encrypted = data[16:]
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    private_key = bytes(a ^ b for a, b in zip(encrypted, key[:len(encrypted)]))
    return private_key.decode()

def get_wallet_balance(address):
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE recipient = ?',
            (address,)
        ).fetchone()
        received = result[0] if result else 0
        
        result = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE sender = ?',
            (address,)
        ).fetchone()
        sent = result[0] if result else 0
        
        return received - sent

def sign_transaction(private_key, tx_data):
    message = f"{tx_data['sender']}{tx_data['recipient']}{tx_data['amount']}{tx_data['timestamp']}"
    signature = hmac.new(private_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return signature

@app.route('/api/wallet/create', methods=['POST'])
def create_wallet():
    data = request.get_json()
    password = data.get('password')
    
    if not password:
        return jsonify({'error': 'Password required'}), 400
    
    private_key, public_key, address = generate_keypair()
    encrypted_key = encrypt_private_key(private_key, password)
    wallet_id = secrets.token_hex(16)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO extension_wallets (wallet_id, encrypted_private_key, public_key, address) VALUES (?, ?, ?, ?)',
            (wallet_id, encrypted_key, public_key, address)
        )
        conn.commit()
    
    return jsonify({
        'wallet_id': wallet_id,
        'address': address,
        'public_key': public_key
    })

@app.route('/api/wallet/import', methods=['POST'])
def import_wallet():
    data = request.get_json()
    private_key = data.get('private_key')
    password = data.get('password')
    
    if not private_key or not password:
        return jsonify({'error': 'Private key and password required'}), 400
    
    public_key = hashlib.sha256(private_key.encode()).hexdigest()
    address = 'RC' + hashlib.sha256(public_key.encode()).hexdigest()[:40]
    encrypted_key = encrypt_private_key(private_key, password)
    wallet_id = secrets.token_hex(16)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO extension_wallets (wallet_id, encrypted_private_key, public_key, address) VALUES (?, ?, ?, ?)',
            (wallet_id, encrypted_key, public_key, address)
        )
        conn.commit()
    
    return jsonify({
        'wallet_id': wallet_id,
        'address': address,
        'public_key': public_key
    })

@app.route('/api/wallet/<wallet_id>/balance', methods=['GET'])
def get_balance(wallet_id):
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute(
            'SELECT address FROM extension_wallets WHERE wallet_id = ?',
            (wallet_id,)
        ).fetchone()
        
        if not result:
            return jsonify({'error': 'Wallet not found'}), 404
        
        address = result[0]
        balance = get_wallet_balance(address)
        
        return jsonify({'balance': balance, 'address': address})

@app.route('/api/wallet/<wallet_id>/sign', methods=['POST'])
def sign_tx(wallet_id):
    data = request.get_json()
    password = data.get('password')
    tx_data = data.get('transaction')
    
    if not password or not tx_data:
        return jsonify({'error': 'Password and transaction data required'}), 400
    
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute(
            'SELECT encrypted_private_key, address FROM extension_wallets WHERE wallet_id = ?',
            (wallet_id,)
        ).fetchone()
        
        if not result:
            return jsonify({'error': 'Wallet not found'}), 404
        
        encrypted_key, address = result
        
        try:
            private_key = decrypt_private_key(encrypted_key, password)
        except:
            return jsonify({'error': 'Invalid password'}), 401
        
        tx_data['sender'] = address
        tx_data['timestamp'] = datetime.now().isoformat()
        signature = sign_transaction(private_key, tx_data)
        
        tx_hash = hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest()
        
        conn.execute(
            'INSERT INTO extension_transactions (wallet_id, tx_hash, amount, recipient) VALUES (?, ?, ?, ?)',
            (wallet_id, tx_hash, tx_data['amount'], tx_data['recipient'])
        )
        conn.commit()
        
        return jsonify({
            'signature': signature,
            'tx_hash': tx_hash,
            'transaction': tx_data
        })

@app.route('/api/wallet/<wallet_id>/transactions', methods=['GET'])
def get_transactions(wallet_id):
    with sqlite3.connect(DB_PATH) as conn:
        results = conn.execute(
            'SELECT tx_hash, amount, recipient, status, created_at FROM extension_transactions WHERE wallet_id = ? ORDER BY created_at DESC',
            (wallet_id,)
        ).fetchall()
        
        transactions = []
        for row in results:
            transactions.append({
                'tx_hash': row[0],
                'amount': row[1],
                'recipient': row[2],
                'status': row[3],
                'created_at': row[4]
            })
        
        return jsonify({'transactions': transactions})

@app.route('/extension')
def extension_interface():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Wallet Extension</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; max-width: 400px; margin: 0 auto; }
            .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            input, button { margin: 5px 0; padding: 8px; width: 100%; box-sizing: border-box; }
            button { background: #007cba; color: white; border: none; cursor: pointer; }
            button:hover { background: #005a8b; }
            .result { background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 3px; font-family: monospace; font-size: 12px; }
        </style>
    </head>
    <body>
        <h2>RustChain Wallet Extension</h2>
        
        <div class="section">
            <h3>Create Wallet</h3>
            <input type="password" id="createPassword" placeholder="Password">
            <button onclick="createWallet()">Create Wallet</button>
            <div id="createResult" class="result"></div>
        </div>
        
        <div class="section">
            <h3>Import Wallet</h3>
            <input type="text" id="importPrivateKey" placeholder="Private Key">
            <input type="password" id="importPassword" placeholder="Password">
            <button onclick="importWallet()">Import Wallet</button>
            <div id="importResult" class="result"></div>
        </div>
        
        <div class="section">
            <h3>Check Balance</h3>
            <input type="text" id="walletId" placeholder="Wallet ID">
            <button onclick="checkBalance()">Check Balance</button>
            <div id="balanceResult" class="result"></div>
        </div>
        
        <div class="section">
            <h3>Sign Transaction</h3>
            <input type="text" id="signWalletId" placeholder="Wallet ID">
            <input type="password" id="signPassword" placeholder="Password">
            <input type="text" id="recipient" placeholder="Recipient Address">
            <input type="number" id="amount" placeholder="Amount">
            <button onclick="signTransaction()">Sign Transaction</button>
            <div id="signResult" class="result"></div>
        </div>
        
        <script>
            async function createWallet() {
                const password = document.getElementById('createPassword').value;
                const response = await fetch('/api/wallet/create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({password})
                });
                const result = await response.json();
                document.getElementById('createResult').innerText = JSON.stringify(result, null, 2);
            }
            
            async function importWallet() {
                const private_key = document.getElementById('importPrivateKey').value;
                const password = document.getElementById('importPassword').value;
                const response = await fetch('/api/wallet/import', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({private_key, password})
                });
                const result = await response.json();
                document.getElementById('importResult').innerText = JSON.stringify(result, null, 2);
            }
            
            async function checkBalance() {
                const walletId = document.getElementById('walletId').value;
                const response = await fetch(`/api/wallet/${walletId}/balance`);
                const result = await response.json();
                document.getElementById('balanceResult').innerText = JSON.stringify(result, null, 2);
            }
            
            async function signTransaction() {
                const walletId = document.getElementById('signWalletId').value;
                const password = document.getElementById('signPassword').value;
                const recipient = document.getElementById('recipient').value;
                const amount = parseFloat(document.getElementById('amount').value);
                
                const response = await fetch(`/api/wallet/${walletId}/sign`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        password,
                        transaction: {recipient, amount}
                    })
                });
                const result = await response.json();
                document.getElementById('signResult').innerText = JSON.stringify(result, null, 2);
            }
        </script>
    </body>
    </html>
    ''')

if __name__ == '__main__':
    init_extension_db()
    app.run(debug=True, port=5003)