#!/usr/bin/env python3
"""
RustChain Explorer - Real-time WebSocket Server
Issue #2295: Block Explorer Real-time WebSocket Feed

Features:
- WebSocket server endpoint for real-time updates
- Live block feed (new blocks appear without refresh)
- Live attestation feed (new miner attestations stream in)
- Connection status tracking
- Auto-reconnect support via WebSocket protocol
- Nginx proxy compatible

Standalone usage:
    python3 explorer_websocket_server.py --port 8080 --node https://50.28.86.131

Integration:
    from explorer_websocket_server import socketio, app, start_explorer_poller
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")
    start_explorer_poller()

Author: RustChain Team
Bounty: #2295 - Block Explorer Real-time WebSocket Feed
"""

import os
import json
import time
import threading
import ssl
import urllib.request
from flask import Flask, Blueprint, jsonify, request
from datetime import datetime

try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    HAVE_SOCKETIO = True
except ImportError:
    HAVE_SOCKETIO = False
    print("Warning: flask-socketio not installed. Run: pip install flask-socketio")

# ─── Configuration ─────────────────────────────────────────────────────────── #
EXPLORER_PORT = int(os.environ.get('EXPLORER_PORT', 8080))
NODE_URL = os.environ.get('RUSTCHAIN_NODE_URL', os.environ.get('RUSTCHAIN_API_BASE', 'https://50.28.86.131'))
API_TIMEOUT = float(os.environ.get('API_TIMEOUT', '8'))
POLL_INTERVAL = float(os.environ.get('POLL_INTERVAL', '5'))  # seconds between polls
HEARTBEAT_S = 30  # ping/pong interval for connection health
MAX_QUEUE = 100  # max buffered events per client (backpressure)

# SSL context for HTTPS node connections
CTX = ssl._create_unverified_context()

# ─── Explorer State ─────────────────────────────────────────────────────────── #
class ExplorerState:
    """Thread-safe state tracker for explorer data with change detection."""

    def __init__(self):
        self._lock = threading.Lock()
        self.blocks = []
        self.transactions = []
        self.miners = {}  # wallet -> last_attest_ts for change detection
        self.epoch = None
        self.slot = None
        self.health = {}
        self.last_update = None
        self.metrics = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'polls_executed': 0,
            'blocks_broadcast': 0,
            'attestations_broadcast': 0
        }
        self._handlers = []  # (handler_fn, event_types) for event bus pattern

    def subscribe(self, handler, event_types=None):
        """Register a callback for events. event_types=None means all."""
        with self._lock:
            self._handlers.append((handler, set(event_types) if event_types else None))
        return handler

    def unsubscribe(self, handler):
        """Unregister a callback."""
        with self._lock:
            self._handlers = [(h, f) for h, f in self._handlers if h != handler]

    def emit(self, event_type: str, data: dict):
        """Emit event to all registered handlers."""
        event = {"type": event_type, "data": data, "ts": time.time()}
        with self._lock:
            handlers = list(self._handlers)
        for handler, filt in handlers:
            if filt is None or event_type in filt:
                try:
                    handler(event)
                except Exception as e:
                    print(f"[EventBus] Handler error: {e}")

    def process_blocks(self, blocks: list):
        """Process blocks list, detect new blocks, emit events."""
        if not blocks:
            return

        with self._lock:
            old_top = self.blocks[0]['height'] if self.blocks else 0

        # Sort by height descending
        sorted_blocks = sorted(blocks, key=lambda b: b.get('height', 0), reverse=True)
        new_blocks = []

        for block in sorted_blocks[:10]:  # Keep top 10
            height = block.get('height', 0)
            if height > old_top:
                new_blocks.append(block)

        if new_blocks:
            # Emit newest block first
            for block in sorted(new_blocks, key=lambda b: b.get('height', 0), reverse=True):
                self.emit("new_block", {
                    "height": block.get('height'),
                    "hash": block.get('hash'),
                    "timestamp": block.get('timestamp', int(time.time())),
                    "miners_count": block.get('miners_count', 0),
                    "reward": block.get('reward', 0)
                })
                with self._lock:
                    self.metrics['blocks_broadcast'] += 1

        with self._lock:
            self.blocks = sorted_blocks[:50]  # Keep last 50 blocks

    def process_epoch(self, epoch_data: dict):
        """Process epoch data, detect epoch/slot changes, emit events."""
        if not epoch_data:
            return

        epoch = epoch_data.get('epoch')
        slot = epoch_data.get('slot', epoch_data.get('epoch_slot'))

        with self._lock:
            old_epoch = self.epoch
            old_slot = self.slot

        # Detect new slot (block)
        if slot is not None and slot != old_slot:
            self.emit("new_block", {
                "slot": slot,
                "epoch": epoch,
                "timestamp": int(time.time()),
            })

        # Detect epoch settlement
        if epoch is not None and old_epoch is not None and epoch != old_epoch:
            self.emit("epoch_settlement", {
                "epoch": old_epoch,
                "new_epoch": epoch,
                "timestamp": int(time.time()),
                "total_rtc": epoch_data.get('pot_rtc', epoch_data.get('reward_pot', epoch_data.get('pot', 0))),
                "miners": epoch_data.get('enrolled_miners', epoch_data.get('miners_enrolled', 0)),
            })

        with self._lock:
            self.epoch = epoch
            self.slot = slot
            self.epoch_data = epoch_data

    def process_miners(self, miners: list):
        """Process miners list, detect new attestations, emit events."""
        if not miners:
            return

        new_attestations = {}
        for m in miners:
            wallet = m.get("wallet_name", m.get("wallet", m.get("wallet_address", "")))
            ts = m.get("last_attestation_time", m.get("last_attest", m.get("last_seen", 0)))
            arch = m.get("hardware_type", m.get("arch", m.get("architecture", "unknown")))
            mult = m.get("multiplier", m.get("rtc_multiplier", m.get("antiquity_multiplier", 1.0)))
            miner_id = m.get("miner_id", m.get("id", wallet))
            if wallet:
                new_attestations[wallet] = (ts, arch, mult, miner_id)

        with self._lock:
            old_miners = self.miners.copy()

        # Detect new attestations (only if we have previous state)
        if old_miners:  # Only emit if we have seen miners before
            for wallet, (ts, arch, mult, miner_id) in new_attestations.items():
                prev_ts = old_miners.get(wallet, (None,))[0]
                if ts and ts != prev_ts:
                    self.emit("attestation", {
                        "miner": wallet,
                        "miner_id": miner_id,
                        "arch": arch,
                        "multiplier": mult,
                        "timestamp": ts,
                    })
                    with self._lock:
                        self.metrics['attestations_broadcast'] += 1

        with self._lock:
            self.miners = new_attestations
            self.miners_list = miners[:100]  # Keep last 100 miners

    def process_health(self, health: dict):
        """Process health data, emit on status change."""
        if not health:
            return

        with self._lock:
            old_status = self.health.get('ok') if self.health else None

        new_status = health.get('ok', health.get('status') == 'ok')

        if old_status is not None and new_status != old_status:
            self.emit("node_status", {
                "online": new_status,
                "status": "online" if new_status else "offline",
                "timestamp": int(time.time())
            })

        with self._lock:
            self.health = health


# Global state instance
state = ExplorerState()


# ─── API Fetching ──────────────────────────────────────────────────────────── #
def _fetch(path, node_url=NODE_URL):
    """Fetch JSON from node API endpoint."""
    url = f"{node_url.rstrip('/')}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-explorer-ws/1.0"})
        with urllib.request.urlopen(req, timeout=API_TIMEOUT, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[Fetch] Error fetching {url}: {e}")
        return None


def _poll_loop():
    """Background polling loop for upstream API."""
    global state

    while True:
        try:
            # Fetch epoch data (includes slot info)
            epoch_data = _fetch("/epoch")
            if epoch_data:
                state.process_epoch(epoch_data)

            # Fetch blocks
            blocks_data = _fetch("/blocks")
            if blocks_data:
                blocks = blocks_data if isinstance(blocks_data, list) else blocks_data.get('blocks', [])
                state.process_blocks(blocks)

            # Fetch miners
            miners_data = _fetch("/api/miners")
            if miners_data:
                miners = miners_data if isinstance(miners_data, list) else miners_data.get('miners', [])
                state.process_miners(miners)

            # Fetch health
            health_data = _fetch("/health")
            if health_data:
                state.process_health(health_data)

            with state._lock:
                state.last_update = time.time()
                state.metrics['polls_executed'] += 1

        except Exception as e:
            print(f"[Poller] Error: {e}")

        time.sleep(POLL_INTERVAL)


def start_explorer_poller():
    """Start background polling thread. Call once at app startup."""
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    print(f"[Poller] Started background polling (interval={POLL_INTERVAL}s, node={NODE_URL})")


# ─── Flask App ──────────────────────────────────────────────────────────────── #
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

# ─── Flask Blueprint ────────────────────────────────────────────────────────── #
ws_bp = Blueprint("explorer_ws", __name__)

if HAVE_SOCKETIO:
    socketio = SocketIO(
        cors_allowed_origins="*",
        async_mode="threading",
        ping_timeout=HEARTBEAT_S,
        ping_interval=HEARTBEAT_S,
        max_http_buffer_size=1024 * 64
    )

    # Track client subscriptions
    _client_handlers = {}  # sid -> handler function

    @socketio.on("connect", namespace="/ws/explorer")
    def on_connect():
        """Handle client connection."""
        sid = request.sid if hasattr(request, 'sid') else "unknown"

        with state._lock:
            state.metrics['total_connections'] += 1
            state.metrics['active_connections'] += 1
            total = state.metrics['total_connections']
            active = state.metrics['active_connections']

        print(f"[WebSocket] Client connected. Active: {active}, Total: {total}")

        # Register event handler for this client
        def handler(event):
            try:
                emit("event", event, namespace="/ws/explorer", to=sid)
            except Exception as e:
                print(f"[WebSocket] Emit error: {e}")

        _client_handlers[sid] = handler
        state.subscribe(handler)

        # Send connection confirmation with current state summary
        with state._lock:
            emit("connected", {
                "status": "ok",
                "node": NODE_URL,
                "heartbeat_s": HEARTBEAT_S,
                "state": {
                    "blocks_count": len(state.blocks),
                    "miners_count": len(state.miners),
                    "epoch": state.epoch,
                    "slot": state.slot
                },
                "metrics": state.metrics.copy()
            })

    @socketio.on("disconnect", namespace="/ws/explorer")
    def on_disconnect():
        """Handle client disconnection."""
        sid = request.sid if hasattr(request, 'sid') else "unknown"

        handler = _client_handlers.pop(sid, None)
        if handler and callable(handler):
            state.unsubscribe(handler)

        with state._lock:
            state.metrics['active_connections'] -= 1
            active = state.metrics['active_connections']

        print(f"[WebSocket] Client disconnected. Active: {active}")

    @socketio.on("subscribe", namespace="/ws/explorer")
    def on_subscribe(data):
        """Client can filter by event type: {'types': ['attestation', 'new_block']}"""
        sid = request.sid if hasattr(request, 'sid') else "unknown"
        types = data.get("types") if isinstance(data, dict) else None

        # Remove old handler
        old_handler = _client_handlers.pop(sid, None)
        if old_handler and callable(old_handler):
            state.unsubscribe(old_handler)

        filt = set(types) if types else None

        def handler(event):
            try:
                emit("event", event, namespace="/ws/explorer", to=sid)
            except Exception as e:
                print(f"[WebSocket] Emit error: {e}")

        _client_handlers[sid] = handler
        state.subscribe(handler, filt)

        emit("subscribed", {"types": list(filt) if filt else "all"})
        print(f"[WebSocket] Client {sid} subscribed to: {filt or 'all'}")

    @socketio.on("ping", namespace="/ws/explorer")
    def on_ping():
        """Handle heartbeat ping."""
        emit("pong", {"ts": time.time()})

    @socketio.on("request_state", namespace="/ws/explorer")
    def on_request_state():
        """Send current state to requesting client."""
        with state._lock:
            emit("state", {
                "blocks": state.blocks[:50],
                "miners": state.miners_list[:100] if hasattr(state, 'miners_list') else [],
                "epoch": state.epoch_data if hasattr(state, 'epoch_data') else {},
                "health": state.health,
                "last_update": state.last_update,
                "metrics": state.metrics.copy()
            })

    @ws_bp.route("/ws/explorer/status")
    def ws_status():
        """Get WebSocket server status."""
        with state._lock:
            return jsonify({
                "connected_clients": state.metrics['active_connections'],
                "total_connections": state.metrics['total_connections'],
                "node_url": NODE_URL,
                "poll_interval_s": POLL_INTERVAL,
                "heartbeat_s": HEARTBEAT_S,
                "metrics": state.metrics.copy()
            })

else:
    # Fallback when SocketIO not available
    socketio = None

    @ws_bp.route("/ws/explorer/status")
    def ws_status_fallback():
        return jsonify({
            "error": "WebSocket not available",
            "message": "flask-socketio not installed",
            "connected_clients": 0
        })


# ─── HTTP API Endpoints ─────────────────────────────────────────────────────── #
@app.route("/api/explorer/dashboard")
def dashboard_data():
    """Get current dashboard data (HTTP polling fallback)."""
    with state._lock:
        return jsonify({
            "blocks": state.blocks[:50],
            "miners": state.miners_list[:100] if hasattr(state, 'miners_list') else [],
            "epoch": state.epoch_data if hasattr(state, 'epoch_data') else {},
            "health": state.health,
            "last_update": state.last_update,
            "metrics": state.metrics.copy()
        })


@app.route("/api/explorer/metrics")
def metrics_endpoint():
    """Get server metrics."""
    with state._lock:
        return jsonify({
            "active_connections": state.metrics['active_connections'],
            "total_connections": state.metrics['total_connections'],
            "messages_sent": state.metrics['messages_sent'],
            "polls_executed": state.metrics['polls_executed'],
            "blocks_broadcast": state.metrics['blocks_broadcast'],
            "attestations_broadcast": state.metrics['attestations_broadcast'],
            "last_poll": state.last_update,
            "uptime": time.time()
        })


@app.route("/api/explorer/blocks")
def get_blocks():
    """Get recent blocks."""
    limit = request.args.get("limit", 50, type=int)
    with state._lock:
        return jsonify(state.blocks[:limit])


@app.route("/api/explorer/miners")
def get_miners():
    """Get active miners."""
    with state._lock:
        return jsonify(state.miners_list[:100] if hasattr(state, 'miners_list') else [])


@app.route("/api/explorer/epoch")
def get_epoch():
    """Get current epoch."""
    with state._lock:
        return jsonify(state.epoch_data if hasattr(state, 'epoch_data') else {})


@app.route("/health")
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "active_connections": state.metrics['active_connections'] if HAVE_SOCKETIO else 0,
        "polls_executed": state.metrics['polls_executed']
    })


# Register blueprint
app.register_blueprint(ws_bp)


# ─── Standalone Mode ────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Explorer WebSocket Server")
    parser.add_argument("--port", type=int, default=EXPLORER_PORT, help="Server port")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--node", default=NODE_URL, help="RustChain node URL")
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL, help="Poll interval (seconds)")
    args = parser.parse_args()

    NODE_URL = args.node
    POLL_INTERVAL = args.interval

    if HAVE_SOCKETIO:
        socketio.init_app(app)
        start_explorer_poller()

        print(f"""
╔══════════════════════════════════════════════════════════╗
║     RustChain Explorer - Real-time WebSocket Server      ║
║                  Issue #2295 Implementation               ║
╠══════════════════════════════════════════════════════════╣
║  HTTP: http://localhost:{args.port}                            ║
║  WebSocket: ws://localhost:{args.port}/ws/explorer             ║
║  Node: {NODE_URL}                    ║
║  Poll Interval: {POLL_INTERVAL}s                               ║
║  Heartbeat: {HEARTBEAT_S}s                                     ║
║                                                          ║
║  Features:                                               ║
║  ✓ Live block feed (new blocks without refresh)          ║
║  ✓ Live attestation feed (miner attestations stream)     ║
║  ✓ Connection status indicator                           ║
║  ✓ Auto-reconnect on disconnect                          ║
║  ✓ Nginx proxy compatible                                ║
║                                                          ║
║  Events emitted:                                         ║
║    - new_block        (every new slot/block detected)    ║
║    - epoch_settlement (when epoch advances)              ║
║    - attestation      (when miner attests)               ║
║    - node_status      (when node status changes)         ║
║                                                          ║
║  Connect with:                                           ║
║    wscat -c ws://localhost:{args.port}/ws/explorer             ║
║    or use Socket.IO client: io('ws://localhost:{args.port}')    ║
╚══════════════════════════════════════════════════════════╝

        Press Ctrl+C to stop
        """)

        socketio.run(app, host=args.host, port=args.port, debug=False)
    else:
        print("flask-socketio not installed. Run: pip install flask-socketio")
        print("Starting demo event bus (no WebSocket)...")
        start_explorer_poller()

        def demo_handler(event):
            print(f"[EVENT] {event['type']}: {json.dumps(event['data'])[:80]}")

        state.subscribe(demo_handler)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
