// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import hashlib
import json
import time
from datetime import datetime
import os

app = Flask(__name__)

DB_PATH = 'otc_bridge.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS otc_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                seller_address TEXT,
                rtc_amount REAL,
                price_per_rtc REAL,
                currency TEXT,
                total_value REAL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS otc_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                order_id TEXT,
                buyer_address TEXT,
                seller_address TEXT,
                rtc_amount REAL,
                escrow_address TEXT,
                payment_txid TEXT,
                rtc_txid TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                settled_at TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES otc_orders (order_id)
            )
        ''')

def generate_order_id():
    timestamp = str(int(time.time()))
    hash_obj = hashlib.sha256(timestamp.encode())
    return hash_obj.hexdigest()[:12]

def generate_trade_id():
    timestamp = str(int(time.time()))
    hash_obj = hashlib.sha256((timestamp + "trade").encode())
    return hash_obj.hexdigest()[:16]

@app.route('/')
def otc_bridge():
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RTC OTC Bridge</title>
        <style>
            body { font-family: Arial; margin: 20px; background: #1a1a1a; color: #fff; }
            .container { max-width: 1200px; margin: 0 auto; }
            .section { background: #2a2a2a; padding: 20px; margin: 20px 0; border-radius: 8px; }
            .order-form { background: #333; padding: 15px; border-radius: 5px; margin: 10px 0; }
            .order-list { background: #333; padding: 15px; border-radius: 5px; }
            input, select, button { padding: 8px; margin: 5px; background: #444; color: #fff; border: 1px solid #666; }
            button { background: #007bff; cursor: pointer; }
            button:hover { background: #0056b3; }
            .order-item { background: #444; margin: 10px 0; padding: 15px; border-radius: 5px; }
            .status-active { color: #28a745; }
            .status-filled { color: #6c757d; }
            .status-cancelled { color: #dc3545; }
            .trade-actions { margin-top: 10px; }
            .trade-actions button { margin-right: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>RTC OTC Bridge</h1>
            <p>Decentralized RTC trading with manual escrow settlement</p>

            <div class="section">
                <h2>Create Sell Order</h2>
                <div class="order-form">
                    <input type="text" id="sellerAddress" placeholder="Your RTC Address" style="width: 300px;">
                    <input type="number" id="rtcAmount" placeholder="RTC Amount" step="0.001">
                    <input type="number" id="pricePerRtc" placeholder="Price per RTC" step="0.0001">
                    <select id="currency">
                        <option value="ETH">ETH</option>
                        <option value="ERG">ERG</option>
                        <option value="USDC">USDC</option>
                    </select>
                    <button onclick="createOrder()">List RTC for Sale</button>
                </div>
            </div>

            <div class="section">
                <h2>Active Orders</h2>
                <div id="ordersList" class="order-list">
                    Loading orders...
                </div>
                <button onclick="refreshOrders()">Refresh Orders</button>
            </div>

            <div class="section">
                <h2>Trade Management</h2>
                <div id="tradesList" class="order-list">
                    <h3>Your Active Trades</h3>
                    <input type="text" id="tradeAddress" placeholder="Your Address" style="width: 300px;">
                    <button onclick="loadTrades()">Load My Trades</button>
                    <div id="tradesContent"></div>
                </div>
            </div>
        </div>

        <script>
            function createOrder() {
                const data = {
                    seller_address: document.getElementById('sellerAddress').value,
                    rtc_amount: parseFloat(document.getElementById('rtcAmount').value),
                    price_per_rtc: parseFloat(document.getElementById('pricePerRtc').value),
                    currency: document.getElementById('currency').value
                };

                if (!data.seller_address || !data.rtc_amount || !data.price_per_rtc) {
                    alert('Please fill all fields');
                    return;
                }

                fetch('/create_order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        alert('Order created: ' + result.order_id);
                        refreshOrders();
                        clearForm();
                    } else {
                        alert('Error: ' + result.error);
                    }
                });
            }

            function clearForm() {
                document.getElementById('sellerAddress').value = '';
                document.getElementById('rtcAmount').value = '';
                document.getElementById('pricePerRtc').value = '';
            }

            function refreshOrders() {
                fetch('/get_orders')
                .then(response => response.json())
                .then(orders => {
                    const ordersList = document.getElementById('ordersList');
                    if (orders.length === 0) {
                        ordersList.innerHTML = '<p>No active orders</p>';
                        return;
                    }

                    let html = '';
                    orders.forEach(order => {
                        const totalValue = order.rtc_amount * order.price_per_rtc;
                        html += `
                            <div class="order-item">
                                <strong>Order ${order.order_id}</strong>
                                <span class="status-${order.status}">[${order.status.toUpperCase()}]</span><br>
                                Selling: ${order.rtc_amount} RTC<br>
                                Price: ${order.price_per_rtc} ${order.currency} per RTC<br>
                                Total: ${totalValue.toFixed(6)} ${order.currency}<br>
                                Seller: ${order.seller_address}<br>
                                <small>Created: ${order.created_at}</small><br>
                                ${order.status === 'active' ?
                                    `<div class="trade-actions">
                                        <button onclick="buyOrder('${order.order_id}')">Buy This RTC</button>
                                    </div>` : ''
                                }
                            </div>
                        `;
                    });
                    ordersList.innerHTML = html;
                });
            }

            function buyOrder(orderId) {
                const buyerAddress = prompt('Enter your address for receiving RTC:');
                if (!buyerAddress) return;

                fetch('/create_trade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        order_id: orderId,
                        buyer_address: buyerAddress
                    })
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        alert(`Trade created: ${result.trade_id}\\nEscrow Address: ${result.escrow_address}\\nSend payment to escrow and notify seller.`);
                        refreshOrders();
                    } else {
                        alert('Error: ' + result.error);
                    }
                });
            }

            function loadTrades() {
                const address = document.getElementById('tradeAddress').value;
                if (!address) {
                    alert('Enter your address');
                    return;
                }

                fetch(`/get_trades?address=${encodeURIComponent(address)}`)
                .then(response => response.json())
                .then(trades => {
                    const tradesContent = document.getElementById('tradesContent');
                    if (trades.length === 0) {
                        tradesContent.innerHTML = '<p>No trades found</p>';
                        return;
                    }

                    let html = '';
                    trades.forEach(trade => {
                        html += `
                            <div class="order-item">
                                <strong>Trade ${trade.trade_id}</strong>
                                <span class="status-${trade.status}">[${trade.status.toUpperCase()}]</span><br>
                                Amount: ${trade.rtc_amount} RTC<br>
                                Buyer: ${trade.buyer_address}<br>
                                Seller: ${trade.seller_address}<br>
                                Escrow: ${trade.escrow_address}<br>
                                ${trade.payment_txid ? `Payment TX: ${trade.payment_txid}<br>` : ''}
                                ${trade.rtc_txid ? `RTC TX: ${trade.rtc_txid}<br>` : ''}
                                <small>Created: ${trade.created_at}</small><br>
                                ${trade.status === 'pending' && !trade.payment_txid ?
                                    `<div class="trade-actions">
                                        <button onclick="markPaymentSent('${trade.trade_id}')">Mark Payment Sent</button>
                                    </div>` : ''
                                }
                                ${trade.status === 'payment_sent' ?
                                    `<div class="trade-actions">
                                        <button onclick="confirmPayment('${trade.trade_id}')">Confirm Payment Received</button>
                                        <button onclick="markRtcSent('${trade.trade_id}')">Mark RTC Sent</button>
                                    </div>` : ''
                                }
                                ${trade.status === 'rtc_sent' ?
                                    `<div class="trade-actions">
                                        <button onclick="completeTrade('${trade.trade_id}')">Confirm RTC Received</button>
                                    </div>` : ''
                                }
                            </div>
                        `;
                    });
                    tradesContent.innerHTML = html;
                });
            }

            function markPaymentSent(tradeId) {
                const txid = prompt('Enter payment transaction ID:');
                if (!txid) return;

                updateTradeStatus(tradeId, 'payment_sent', { payment_txid: txid });
            }

            function confirmPayment(tradeId) {
                if (confirm('Confirm you received the payment?')) {
                    updateTradeStatus(tradeId, 'payment_confirmed');
                }
            }

            function markRtcSent(tradeId) {
                const txid = prompt('Enter RTC transaction ID:');
                if (!txid) return;

                updateTradeStatus(tradeId, 'rtc_sent', { rtc_txid: txid });
            }

            function completeTrade(tradeId) {
                if (confirm('Confirm you received the RTC?')) {
                    updateTradeStatus(tradeId, 'completed');
                }
            }

            function updateTradeStatus(tradeId, status, data = {}) {
                fetch('/update_trade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trade_id: tradeId,
                        status: status,
                        ...data
                    })
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        alert('Trade updated successfully');
                        loadTrades();
                    } else {
                        alert('Error: ' + result.error);
                    }
                });
            }

            // Load orders on page load
            refreshOrders();
        </script>
    </body>
    </html>
    '''
    return render_template_string(html_template)

@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        order_id = generate_order_id()

        seller_address = data.get('seller_address', '').strip()
        rtc_amount = float(data.get('rtc_amount', 0))
        price_per_rtc = float(data.get('price_per_rtc', 0))
        currency = data.get('currency', 'ETH')

        if not seller_address or rtc_amount <= 0 or price_per_rtc <= 0:
            return jsonify({'success': False, 'error': 'Invalid order parameters'})

        total_value = rtc_amount * price_per_rtc

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO otc_orders
                (order_id, seller_address, rtc_amount, price_per_rtc, currency, total_value)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (order_id, seller_address, rtc_amount, price_per_rtc, currency, total_value))
            conn.commit()

        return jsonify({
            'success': True,
            'order_id': order_id,
            'total_value': total_value
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_orders')
def get_orders():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT order_id, seller_address, rtc_amount, price_per_rtc,
                       currency, total_value, status, created_at
                FROM otc_orders
                WHERE status = 'active'
                ORDER BY created_at DESC
            ''')

            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'order_id': row[0],
                    'seller_address': row[1],
                    'rtc_amount': row[2],
                    'price_per_rtc': row[3],
                    'currency': row[4],
                    'total_value': row[5],
                    'status': row[6],
                    'created_at': row[7]
                })

        return jsonify(orders)

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/create_trade', methods=['POST'])
def create_trade():
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        buyer_address = data.get('buyer_address', '').strip()

        if not order_id or not buyer_address:
            return jsonify({'success': False, 'error': 'Missing order ID or buyer address'})

        with sqlite3.connect(DB_PATH) as conn:
            # Check if order exists and is active
            cursor = conn.execute('''
                SELECT seller_address, rtc_amount, status
                FROM otc_orders
                WHERE order_id = ? AND status = 'active'
            ''', (order_id,))

            order_row = cursor.fetchone()
            if not order_row:
                return jsonify({'success': False, 'error': 'Order not found or not active'})

            seller_address, rtc_amount, status = order_row

            # Generate escrow address (simple hash for demo)
            escrow_data = f"{order_id}{buyer_address}{seller_address}"
            escrow_address = hashlib.sha256(escrow_data.encode()).hexdigest()[:20]

            trade_id = generate_trade_id()

            # Create trade record
            conn.execute('''
                INSERT INTO otc_trades
                (trade_id, order_id, buyer_address, seller_address, rtc_amount, escrow_address)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (trade_id, order_id, buyer_address, seller_address, rtc_amount, escrow_address))

            # Mark order as in_trade
            conn.execute('''
                UPDATE otc_orders
                SET status = 'in_trade', updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?
            ''', (order_id,))

            conn.commit()

        return jsonify({
            'success': True,
            'trade_id': trade_id,
            'escrow_address': escrow_address,
            'rtc_amount': rtc_amount
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_trades')
def get_trades():
    try:
        address = request.args.get('address', '').strip()
        if not address:
            return jsonify([])

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT trade_id, order_id, buyer_address, seller_address,
                       rtc_amount, escrow_address, payment_txid, rtc_txid,
                       status, created_at, settled_at
                FROM otc_trades
                WHERE buyer_address = ? OR seller_address = ?
                ORDER BY created_at DESC
            ''', (address, address))

            trades = []
            for row in cursor.fetchall():
                trades.append({
                    'trade_id': row[0],
                    'order_id': row[1],
                    'buyer_address': row[2],
                    'seller_address': row[3],
                    'rtc_amount': row[4],
                    'escrow_address': row[5],
                    'payment_txid': row[6],
                    'rtc_txid': row[7],
                    'status': row[8],
                    'created_at': row[9],
                    'settled_at': row[10]
                })

        return jsonify(trades)

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/update_trade', methods=['POST'])
def update_trade():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        status = data.get('status')
        payment_txid = data.get('payment_txid')
        rtc_txid = data.get('rtc_txid')

        if not trade_id or not status:
            return jsonify({'success': False, 'error': 'Missing trade ID or status'})

        with sqlite3.connect(DB_PATH) as conn:
            update_fields = ['status = ?']
            params = [status]

            if payment_txid:
                update_fields.append('payment_txid = ?')
                params.append(payment_txid)

            if rtc_txid:
                update_fields.append('rtc_txid = ?')
                params.append(rtc_txid)

            if status == 'completed':
                update_fields.append('settled_at = CURRENT_TIMESTAMP')

                # Update order status to filled
                cursor = conn.execute('SELECT order_id FROM otc_trades WHERE trade_id = ?', (trade_id,))
                order_row = cursor.fetchone()
                if order_row:
                    conn.execute('UPDATE otc_orders SET status = ? WHERE order_id = ?',
                               ('filled', order_row[0]))

            params.append(trade_id)
            query = f'UPDATE otc_trades SET {", ".join(update_fields)} WHERE trade_id = ?'

            conn.execute(query, params)
            conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stats')
def api_stats():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Order stats
            cursor = conn.execute('SELECT COUNT(*), SUM(rtc_amount) FROM otc_orders WHERE status = "active"')
            active_orders, total_rtc = cursor.fetchone()

            # Trade stats
            cursor = conn.execute('SELECT COUNT(*) FROM otc_trades WHERE status = "completed"')
            completed_trades = cursor.fetchone()[0]

            cursor = conn.execute('SELECT SUM(rtc_amount) FROM otc_trades WHERE status = "completed"')
            traded_volume = cursor.fetchone()[0] or 0

        return jsonify({
            'active_orders': active_orders or 0,
            'total_rtc_listed': total_rtc or 0,
            'completed_trades': completed_trades,
            'traded_volume': traded_volume
        })

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()

    app.run(host='0.0.0.0', port=5007, debug=True)
