# SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, render_template_string, jsonify, make_response
import sqlite3
import os
import html
import re
import json
from urllib.parse import unquote

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(32).hex())

DB_PATH = 'rustchain.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS test_payments (
            id INTEGER PRIMARY KEY,
            amount TEXT,
            recipient TEXT,
            memo TEXT,
            origin TEXT,
            user_agent TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Widget Security Test Suite</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .test-section { border: 1px solid #ccc; margin: 20px 0; padding: 15px; }
            .vulnerable { background-color: #fee; }
            .secure { background-color: #efe; }
            button { padding: 10px; margin: 5px; }
            iframe { border: 1px solid #999; }
        </style>
    </head>
    <body>
        <h1>Payment Widget Security Test Suite</h1>
        
        <div class="test-section vulnerable">
            <h3>XSS Test 1: Script in Amount Parameter</h3>
            <iframe src="/widget?amount=<script>alert('XSS in amount')</script>&recipient=test" width="400" height="200"></iframe>
        </div>
        
        <div class="test-section vulnerable">
            <h3>XSS Test 2: Script in Memo Field</h3>
            <iframe src="/widget?amount=100&recipient=test&memo=<img src=x onerror=alert('XSS in memo')>" width="400" height="200"></iframe>
        </div>
        
        <div class="test-section vulnerable">
            <h3>XSS Test 3: JavaScript URL in Recipient</h3>
            <iframe src="/widget?amount=100&recipient=javascript:alert('XSS in recipient')" width="400" height="200"></iframe>
        </div>
        
        <div class="test-section vulnerable">
            <h3>Clickjacking Test: Hidden Widget</h3>
            <div style="position:relative;">
                <button onclick="alert('You clicked the wrong button!')">Click me for prize!</button>
                <iframe src="/widget?amount=1000&recipient=attacker_wallet" 
                        style="position:absolute; top:0; left:0; opacity:0.1; z-index:2;" 
                        width="200" height="50"></iframe>
            </div>
        </div>
        
        <div class="test-section vulnerable">
            <h3>CSRF Test: Auto-submitting Form</h3>
            <form id="csrf-test" action="/process_payment" method="post" target="csrf-frame">
                <input type="hidden" name="amount" value="500">
                <input type="hidden" name="recipient" value="evil_wallet_123">
                <input type="hidden" name="memo" value="CSRF Attack">
            </form>
            <iframe name="csrf-frame" width="400" height="100"></iframe>
            <script>document.getElementById('csrf-test').submit();</script>
        </div>
        
        <div class="test-section vulnerable">
            <h3>Amount Overflow Tests</h3>
            <iframe src="/widget?amount=999999999999999999999&recipient=test" width="400" height="150"></iframe>
            <iframe src="/widget?amount=-100&recipient=test" width="400" height="150"></iframe>
            <iframe src="/widget?amount=1.00000000001&recipient=test" width="400" height="150"></iframe>
        </div>
        
        <div class="test-section vulnerable">
            <h3>Address Injection Test</h3>
            <iframe src="/widget?amount=100&recipient=normal_address%3Cscript%3Ealert('injected')%3C/script%3E" width="400" height="200"></iframe>
        </div>
        
        <div class="test-section">
            <h3>Test Results</h3>
            <button onclick="loadTestResults()">Load Test Results</button>
            <div id="results"></div>
        </div>
        
        <script>
        function loadTestResults() {
            fetch('/test_results')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('results').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                });
        }
        </script>
    </body>
    </html>
    ''')

@app.route('/widget')
def widget():
    amount = request.args.get('amount', '0')
    recipient = request.args.get('recipient', '')
    memo = request.args.get('memo', '')
    origin = request.headers.get('Origin', 'unknown')
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO test_payments (amount, recipient, memo, origin, user_agent) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (amount, recipient, memo, origin, request.headers.get('User-Agent', '')))
    
    widget_html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Widget</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 10px; background: #f5f5f5; }}
            .widget {{ background: white; padding: 15px; border-radius: 5px; }}
            .amount {{ font-size: 18px; font-weight: bold; color: #007cba; }}
            .recipient {{ color: #666; font-size: 12px; word-break: break-all; }}
            .memo {{ font-style: italic; color: #888; }}
            button {{ background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 3px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="widget">
            <h4>RTC Payment Widget</h4>
            <div class="amount">Amount: {amount} RTC</div>
            <div class="recipient">To: {recipient}</div>
            <div class="memo">Memo: {memo}</div>
            <button onclick="processPayment()">Pay Now</button>
            <div id="status"></div>
        </div>
        
        <script>
        function processPayment() {{
            fetch('/process_payment', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    amount: '{amount}',
                    recipient: '{recipient}',
                    memo: '{memo}'
                }})
            }})
            .then(response => response.json())
            .then(data => {{
                document.getElementById('status').innerHTML = data.message;
            }})
            .catch(error => {{
                document.getElementById('status').innerHTML = 'Error: ' + error;
            }});
        }}
        </script>
    </body>
    </html>
    '''
    
    response = make_response(widget_html)
    response.headers.pop('X-Frame-Options', None)
    return response

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if request.content_type == 'application/json':
        data = request.get_json()
        amount = data.get('amount', '0')
        recipient = data.get('recipient', '')
        memo = data.get('memo', '')
    else:
        amount = request.form.get('amount', '0')
        recipient = request.form.get('recipient', '')
        memo = request.form.get('memo', '')
    
    origin = request.headers.get('Origin', 'unknown')
    referer = request.headers.get('Referer', 'unknown')
    
    try:
        amount_float = float(amount)
        if amount_float < 0:
            return jsonify({'status': 'error', 'message': 'Negative amounts detected but processed anyway!'})
        elif amount_float > 1000000:
            return jsonify({'status': 'error', 'message': 'Amount overflow detected but processed anyway!'})
    except:
        pass
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO test_payments (amount, recipient, memo, origin, user_agent) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (amount, recipient, memo, f"{origin}|{referer}", request.headers.get('User-Agent', '')))
    
    return jsonify({
        'status': 'success',
        'message': f'Payment of {amount} RTC to {recipient} processed! Memo: {memo}',
        'transaction_id': 'fake_tx_' + str(abs(hash(amount + recipient + memo)))[:8]
    })

@app.route('/test_results')
def test_results():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT * FROM test_payments ORDER BY timestamp DESC LIMIT 20')
        payments = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    return jsonify({
        'total_tests': len(payments),
        'recent_payments': payments,
        'vulnerabilities_detected': {
            'xss_attempts': len([p for p in payments if '<script>' in str(p) or 'javascript:' in str(p) or 'onerror=' in str(p)]),
            'negative_amounts': len([p for p in payments if p['amount'].startswith('-')]),
            'overflow_amounts': len([p for p in payments if len(p['amount']) > 10]),
            'csrf_attempts': len([p for p in payments if 'CSRF' in p['memo']]),
            'injection_attempts': len([p for p in payments if '%3C' in p['recipient'] or '%3E' in p['recipient']])
        }
    })

@app.route('/admin/payments')
def admin_payments():
    auth_header = request.headers.get('Authorization', '')
    if auth_header != 'Bearer admin_token_123':
        return render_template_string('''
        <h1>Admin Login Required</h1>
        <form method="post" action="/admin/login">
            <input type="password" name="password" placeholder="Admin password">
            <button type="submit">Login</button>
        </form>
        ''')
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT * FROM test_payments ORDER BY timestamp DESC')
        payments = cursor.fetchall()
    
    return render_template_string('''
    <h1>Admin Payment Dashboard</h1>
    <table border="1" cellpadding="5">
        <tr><th>ID</th><th>Amount</th><th>Recipient</th><th>Memo</th><th>Origin</th><th>Timestamp</th></tr>
        {% for payment in payments %}
        <tr>
            <td>{{ payment[0] }}</td>
            <td>{{ payment[1] }}</td>
            <td>{{ payment[2] }}</td>
            <td>{{ payment[3] }}</td>
            <td>{{ payment[4] }}</td>
            <td>{{ payment[6] }}</td>
        </tr>
        {% endfor %}
    </table>
    ''', payments=payments)

@app.route('/admin/login', methods=['POST'])
def admin_login():
    password = request.form.get('password', '')
    if password == os.getenv('ADMIN_PASSWORD', 'changeme') and password != '':
        return jsonify({'token': 'admin_token_123', 'message': 'Login successful'})
    return jsonify({'error': 'Invalid credentials'})

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)