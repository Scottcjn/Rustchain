// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
import hashlib
import os
import secrets
from datetime import datetime
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import mnemonic

app = Flask(__name__)
DB_PATH = 'browser_extension_demo.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY,
                address TEXT UNIQUE,
                encrypted_keystore TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                from_address TEXT,
                to_address TEXT,
                amount REAL,
                signature TEXT,
                txhash TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

def generate_seed_phrase():
    mnemo = mnemonic.Mnemonic("english")
    return mnemo.generate(strength=256)

def seed_to_keypair(seed_phrase, passphrase=""):
    mnemo = mnemonic.Mnemonic("english")
    seed = mnemo.to_seed(seed_phrase, passphrase)
    private_key = Ed25519PrivateKey.from_private_bytes(seed[:32])
    public_key = private_key.public_key()
    return private_key, public_key

def keypair_to_address(public_key):
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return hashlib.sha256(public_bytes).hexdigest()[:40]

def encrypt_keystore(private_key, password):
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)[:32]
    iv = os.urandom(12)
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(private_bytes) + encryptor.finalize()
    
    keystore = {
        'salt': base64.b64encode(salt).decode(),
        'iv': base64.b64encode(iv).decode(),
        'ciphertext': base64.b64encode(ciphertext).decode(),
        'tag': base64.b64encode(encryptor.tag).decode()
    }
    return json.dumps(keystore)

def decrypt_keystore(encrypted_keystore, password):
    keystore = json.loads(encrypted_keystore)
    salt = base64.b64decode(keystore['salt'])
    iv = base64.b64decode(keystore['iv'])
    ciphertext = base64.b64decode(keystore['ciphertext'])
    tag = base64.b64decode(keystore['tag'])
    
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)[:32]
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    private_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    
    return Ed25519PrivateKey.from_private_bytes(private_bytes)

@app.route('/')
def home():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Wallet Extension Demo</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #1a1a1a; color: #fff; }
            .container { max-width: 800px; margin: 0 auto; }
            .section { background: #2d2d2d; padding: 20px; margin: 20px 0; border-radius: 8px; }
            input, textarea, button { padding: 10px; margin: 5px; border: none; border-radius: 4px; }
            input, textarea { background: #3d3d3d; color: #fff; width: 300px; }
            button { background: #ff6b35; color: white; cursor: pointer; font-weight: bold; }
            button:hover { background: #e55a2b; }
            .response { background: #1e3a1e; padding: 15px; margin: 10px 0; border-radius: 4px; font-family: monospace; }
            .error { background: #3a1e1e; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🦀 RustChain Wallet Extension Demo</h1>
            <p>Local testing environment for browser extension APIs</p>
            
            <div class="section">
                <h3>Create New Wallet</h3>
                <input type="password" id="createPassword" placeholder="Wallet password">
                <button onclick="createWallet()">Generate Wallet</button>
                <div id="createResponse" class="response" style="display:none;"></div>
            </div>
            
            <div class="section">
                <h3>Import Wallet</h3>
                <textarea id="seedPhrase" placeholder="Enter 24-word seed phrase"></textarea><br>
                <input type="password" id="importPassword" placeholder="Wallet password">
                <button onclick="importWallet()">Import Wallet</button>
                <div id="importResponse" class="response" style="display:none;"></div>
            </div>
            
            <div class="section">
                <h3>Get Balance</h3>
                <input type="text" id="balanceAddress" placeholder="Wallet address">
                <button onclick="getBalance()">Check Balance</button>
                <div id="balanceResponse" class="response" style="display:none;"></div>
            </div>
            
            <div class="section">
                <h3>Sign Transaction</h3>
                <input type="text" id="fromAddress" placeholder="From address"><br>
                <input type="text" id="toAddress" placeholder="To address"><br>
                <input type="number" id="amount" placeholder="Amount" step="0.01"><br>
                <input type="password" id="signPassword" placeholder="Wallet password">
                <button onclick="signTransaction()">Sign Transaction</button>
                <div id="signResponse" class="response" style="display:none;"></div>
            </div>
        </div>
        
        <script>
            async function apiCall(endpoint, data) {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                return await response.json();
            }
            
            async function createWallet() {
                const password = document.getElementById('createPassword').value;
                const result = await apiCall('/api/create-wallet', {password});
                const div = document.getElementById('createResponse');
                div.style.display = 'block';
                div.className = result.success ? 'response' : 'response error';
                div.textContent = JSON.stringify(result, null, 2);
            }
            
            async function importWallet() {
                const seedPhrase = document.getElementById('seedPhrase').value;
                const password = document.getElementById('importPassword').value;
                const result = await apiCall('/api/import-wallet', {seedPhrase, password});
                const div = document.getElementById('importResponse');
                div.style.display = 'block';
                div.className = result.success ? 'response' : 'response error';
                div.textContent = JSON.stringify(result, null, 2);
            }
            
            async function getBalance() {
                const address = document.getElementById('balanceAddress').value;
                const result = await apiCall('/api/get-balance', {address});
                const div = document.getElementById('balanceResponse');
                div.style.display = 'block';
                div.className = result.success ? 'response' : 'response error';
                div.textContent = JSON.stringify(result, null, 2);
            }
            
            async function signTransaction() {
                const fromAddress = document.getElementById('fromAddress').value;
                const toAddress = document.getElementById('toAddress').value;
                const amount = parseFloat(document.getElementById('amount').value);
                const password = document.getElementById('signPassword').value;
                
                const result = await apiCall('/api/sign-transaction', {
                    fromAddress, toAddress, amount, password
                });
                const div = document.getElementById('signResponse');
                div.style.display = 'block';
                div.className = result.success ? 'response' : 'response error';
                div.textContent = JSON.stringify(result, null, 2);
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/api/create-wallet', methods=['POST'])
def create_wallet():
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        if not password:
            return jsonify({'success': False, 'error': 'Password required'})
        
        seed_phrase = generate_seed_phrase()
        private_key, public_key = seed_to_keypair(seed_phrase)
        address = keypair_to_address(public_key)
        encrypted_keystore = encrypt_keystore(private_key, password)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('INSERT INTO wallets (address, encrypted_keystore) VALUES (?, ?)', 
                        (address, encrypted_keystore))
        
        return jsonify({
            'success': True,
            'address': address,
            'seedPhrase': seed_phrase,
            'message': 'Wallet created successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/import-wallet', methods=['POST'])
def import_wallet():
    try:
        data = request.get_json()
        seed_phrase = data.get('seedPhrase', '').strip()
        password = data.get('password', '')
        
        if not seed_phrase or not password:
            return jsonify({'success': False, 'error': 'Seed phrase and password required'})
        
        mnemo = mnemonic.Mnemonic("english")
        if not mnemo.check(seed_phrase):
            return jsonify({'success': False, 'error': 'Invalid seed phrase'})
        
        private_key, public_key = seed_to_keypair(seed_phrase)
        address = keypair_to_address(public_key)
        encrypted_keystore = encrypt_keystore(private_key, password)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('INSERT OR REPLACE INTO wallets (address, encrypted_keystore) VALUES (?, ?)', 
                        (address, encrypted_keystore))
        
        return jsonify({
            'success': True,
            'address': address,
            'message': 'Wallet imported successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-balance', methods=['POST'])
def get_balance():
    try:
        data = request.get_json()
        address = data.get('address', '')
        
        if not address:
            return jsonify({'success': False, 'error': 'Address required'})
        
        # Simulate balance (in real implementation would query blockchain)
        balance = hash(address) % 1000 / 10.0
        
        return jsonify({
            'success': True,
            'address': address,
            'balance': balance,
            'unit': 'RTC'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sign-transaction', methods=['POST'])
def sign_transaction():
    try:
        data = request.get_json()
        from_address = data.get('fromAddress', '')
        to_address = data.get('toAddress', '')
        amount = data.get('amount', 0)
        password = data.get('password', '')
        
        if not all([from_address, to_address, amount, password]):
            return jsonify({'success': False, 'error': 'All fields required'})
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('SELECT encrypted_keystore FROM wallets WHERE address = ?', (from_address,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'success': False, 'error': 'Wallet not found'})
            
            private_key = decrypt_keystore(row[0], password)
            
            # Create transaction data to sign
            tx_data = f"{from_address}{to_address}{amount}{datetime.now().isoformat()}"
            signature = private_key.sign(tx_data.encode())
            signature_hex = signature.hex()
            
            # Generate transaction hash
            txhash = hashlib.sha256(tx_data.encode()).hexdigest()
            
            # Store transaction
            conn.execute('''
                INSERT INTO transactions (from_address, to_address, amount, signature, txhash) 
                VALUES (?, ?, ?, ?, ?)
            ''', (from_address, to_address, amount, signature_hex, txhash))
        
        return jsonify({
            'success': True,
            'txhash': txhash,
            'signature': signature_hex,
            'message': 'Transaction signed successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/list-wallets', methods=['GET'])
def list_wallets():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('SELECT address, created_at FROM wallets ORDER BY created_at DESC')
            wallets = [{'address': row[0], 'created_at': row[1]} for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'wallets': wallets
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/transaction-history', methods=['POST'])
def transaction_history():
    try:
        data = request.get_json()
        address = data.get('address', '')
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT from_address, to_address, amount, txhash, timestamp 
                FROM transactions 
                WHERE from_address = ? OR to_address = ? 
                ORDER BY timestamp DESC
            ''', (address, address))
            
            transactions = []
            for row in cursor.fetchall():
                transactions.append({
                    'from': row[0],
                    'to': row[1],
                    'amount': row[2],
                    'txhash': row[3],
                    'timestamp': row[4]
                })
        
        return jsonify({
            'success': True,
            'transactions': transactions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    init_db()
    print("🦀 RustChain Wallet Extension Demo Server")
    print("🌐 http://localhost:5000")
    app.run(debug=True, port=5000)