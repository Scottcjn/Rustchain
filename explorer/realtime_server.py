#!/usr/bin/env python3
"""
RustChain Explorer - Real-time WebSocket Server
Provides live data streaming for dashboard updates
Flask-SocketIO based implementation
"""

import os
import json
import time
import threading
import requests
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room

# Configuration
EXPLORER_PORT = int(os.environ.get('EXPLORER_PORT', 8080))
API_BASE = os.environ.get('RUSTCHAIN_API_BASE', 'https://rustchain.org').rstrip('/')
API_TIMEOUT = float(os.environ.get('API_TIMEOUT', '8'))
POLL_INTERVAL = float(os.environ.get('POLL_INTERVAL', '5'))  # seconds

# Flask app with SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# State tracking
class ExplorerState:
    def __init__(self):
        self.blocks = []
        self.transactions = []
        self.miners = []
        self.epoch = {}
        self.health = {}
        self.last_update = None
        self.metrics = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'polls_executed': 0
        }
        self._lock = threading.Lock()

state = ExplorerState()


def fetch_api(endpoint):
    """Fetch data from RustChain API"""
    try:
        url = f"{API_BASE}{endpoint}"
        response = requests.get(url, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e)}


def poll_upstream():
    """Poll upstream API and broadcast changes"""
    global state
    
    while True:
        try:
            # Fetch all data
            new_blocks = fetch_api('/blocks') or []
            new_txs = fetch_api('/api/transactions') or []
            new_miners = fetch_api('/api/miners') or []
            new_epoch = fetch_api('/epoch') or {}
            new_health = fetch_api('/health') or {}
            
            with state._lock:
                # Detect new blocks
                if new_blocks and (not state.blocks or new_blocks[0].get('height', 0) > state.blocks[0].get('height', 0)):
                    for block in new_blocks[:5]:  # Send up to 5 new blocks
                        socketio.emit('block', block, namespace='/')
                        state.metrics['messages_sent'] += 1
                
                # Detect new transactions
                if new_txs and len(new_txs) > len(state.transactions):
                    for tx in new_txs[:10]:  # Send up to 10 new transactions
                        socketio.emit('transaction', tx, namespace='/')
                        state.metrics['messages_sent'] += 1
                
                # Detect miner updates
                if new_miners != state.miners:
                    socketio.emit('miner_update', {'miners': new_miners}, namespace='/')
                    state.metrics['messages_sent'] += 1
                
                # Detect epoch updates
                if new_epoch != state.epoch:
                    socketio.emit('epoch_update', new_epoch, namespace='/')
                    state.metrics['messages_sent'] += 1
                
                # Detect health updates
                if new_health != state.health:
                    socketio.emit('health', new_health, namespace='/')
                    state.metrics['messages_sent'] += 1
                
                # Update state
                state.blocks = new_blocks
                state.transactions = new_txs
                state.miners = new_miners
                state.epoch = new_epoch
                state.health = new_health
                state.last_update = time.time()
                state.metrics['polls_executed'] += 1
            
            time.sleep(POLL_INTERVAL)
            
        except Exception as e:
            print(f"[Poller] Error: {e}")
            time.sleep(POLL_INTERVAL)


# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    with state._lock:
        state.metrics['total_connections'] += 1
        state.metrics['active_connections'] += 1
    
    print(f"[WebSocket] Client connected. Total: {state.metrics['total_connections']}")
    
    # Send current state to new client
    emit('connected', {
        'timestamp': time.time(),
        'state': {
            'blocks_count': len(state.blocks),
            'transactions_count': len(state.transactions),
            'miners_count': len(state.miners),
            'epoch': state.epoch,
            'health': state.health
        }
    })
    
    # Send initial metrics
    emit('metrics', state.metrics)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    with state._lock:
        state.metrics['active_connections'] -= 1
    
    print(f"[WebSocket] Client disconnected. Active: {state.metrics['active_connections']}")


@socketio.on('ping')
def handle_ping():
    """Handle heartbeat ping"""
    emit('pong', {'timestamp': time.time()})


@socketio.on('subscribe')
def handle_subscribe(data):
    """Subscribe to specific event types"""
    room = data.get('room', 'all')
    join_room(room)
    print(f"[WebSocket] Client subscribed to room: {room}")


@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    """Unsubscribe from specific event types"""
    room = data.get('room', 'all')
    leave_room(room)
    print(f"[WebSocket] Client unsubscribed from room: {room}")


@socketio.on('request_state')
def handle_request_state():
    """Send current state to requesting client"""
    with state._lock:
        emit('state', {
            'blocks': state.blocks[:50],
            'transactions': state.transactions[:100],
            'miners': state.miners,
            'epoch': state.epoch,
            'health': state.health,
            'last_update': state.last_update
        })


# HTTP routes
@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template('dashboard.html')


@app.route('/api/dashboard')
def dashboard_data():
    """Get current dashboard data"""
    with state._lock:
        return jsonify({
            'blocks': state.blocks[:50],
            'transactions': state.transactions[:100],
            'miners': state.miners,
            'epoch': state.epoch,
            'health': state.health,
            'last_update': state.last_update,
            'metrics': state.metrics
        })


@app.route('/api/metrics')
def metrics():
    """Get server metrics"""
    with state._lock:
        return jsonify({
            'active_connections': state.metrics['active_connections'],
            'total_connections': state.metrics['total_connections'],
            'messages_sent': state.metrics['messages_sent'],
            'polls_executed': state.metrics['polls_executed'],
            'last_poll': state.last_update,
            'uptime': time.time() - app.config.get('start_time', time.time())
        })


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': time.time(),
        'active_connections': state.metrics['active_connections'],
        'polls_executed': state.metrics['polls_executed']
    })


@app.route('/api/blocks')
def get_blocks():
    """Get recent blocks"""
    limit = request.args.get('limit', 50, type=int)
    with state._lock:
        return jsonify(state.blocks[:limit])


@app.route('/api/transactions')
def get_transactions():
    """Get recent transactions"""
    limit = request.args.get('limit', 100, type=int)
    with state._lock:
        return jsonify(state.transactions[:limit])


@app.route('/api/miners')
def get_miners():
    """Get active miners"""
    with state._lock:
        return jsonify(state.miners)


@app.route('/api/epoch')
def get_epoch():
    """Get current epoch"""
    with state._lock:
        return jsonify(state.epoch)


def run_poller():
    """Run the upstream poller in background thread"""
    poller_thread = threading.Thread(target=poll_upstream, daemon=True)
    poller_thread.start()
    print("[Poller] Started background polling thread")


def main():
    """Start the explorer server"""
    app.config['start_time'] = time.time()
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║        RustChain Explorer - Real-time Server             ║
╠══════════════════════════════════════════════════════════╣
║  HTTP: http://localhost:{EXPLORER_PORT}                        ║
║  WebSocket: ws://localhost:{EXPLORER_PORT}                     ║
║  API Base: {API_BASE}                    ║
║  Poll Interval: {POLL_INTERVAL}s                               ║
║                                                          ║
║  Features:                                               ║
║  - Real-time block updates                               ║
║  - Live transaction feed                                 ║
║  - Miner status streaming                                ║
║  - Epoch progress tracking                               ║
║  - Health monitoring                                     ║
╚══════════════════════════════════════════════════════════╝

    Press Ctrl+C to stop
    """)
    
    # Start background poller
    run_poller()
    
    # Run Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=EXPLORER_PORT, debug=False)


if __name__ == '__main__':
    main()
