"""
websocket_feed.py — RustChain WebSocket Real-Time Event Feed
Bounty #748: RustChain WebSocket Real-Time Feed

Integration (add to your Flask app):
    from websocket_feed import ws_bp, socketio, start_event_poller
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")
    app.register_blueprint(ws_bp)
    start_event_poller()

Standalone:
    python3 websocket_feed.py --port 5001 --node https://rustchain.org

Connect with:
    wscat -c ws://localhost:5001/ws/feed
    # or use Socket.IO client

Author: noxventures_rtc
Wallet: noxventures_rtc
"""

import time
import threading
import json
import os
import urllib.request
from flask import Blueprint
from node.tls_config import get_ssl_context

try:
    from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room
    HAVE_SOCKETIO = True
except ImportError:
    HAVE_SOCKETIO = False
    # Fallback: pure WebSocket via websockets library
    try:
        import websockets
        import asyncio
        HAVE_WS = True
    except ImportError:
        HAVE_WS = False

# ─── Config ─────────────────────────────────────────────────────────────────── #
NODE_URL     = os.environ.get("RUSTCHAIN_NODE_URL", "https://rustchain.org")
POLL_INTERVAL = int(os.environ.get("WS_POLL_INTERVAL", "5"))   # seconds between polls
HEARTBEAT_S  = 30    # ping/pong interval
MAX_QUEUE    = 100   # max buffered events per client (backpressure)

CTX = get_ssl_context()

# ─── Event Bus ──────────────────────────────────────────────────────────────── #
class EventBus:
    """Thread-safe event bus that tracks state and emits diffs."""

    def __init__(self):
        self._lock         = threading.Lock()
        self._handlers     = []          # (handler_fn, filter_set)
        self._last_epoch   = None
        self._last_slot    = None
        self._last_miners  = {}          # wallet -> last_attest_ts
        self._last_txns    = set()       # seen transfer IDs

    def subscribe(self, handler, event_types=None):
        """Register a callback for events. event_types=None means all."""
        with self._lock:
            self._handlers.append((handler, event_types))
        return handler

    def unsubscribe(self, handler):
        with self._lock:
            self._handlers = [(h, f) for h, f in self._handlers if h != handler]

    def emit(self, event_type: str, data: dict):
        event = {"type": event_type, "data": data, "ts": time.time()}
        with self._lock:
            handlers = list(self._handlers)
        for handler, filt in handlers:
            if filt is None or event_type in filt:
                try:
                    handler(event)
                except Exception:
                    pass

    def process_health(self, health: dict):
        pass  # Could emit node_status events here

    def process_epoch(self, epoch_data: dict):
        epoch = epoch_data.get("epoch")
        slot  = epoch_data.get("slot", epoch_data.get("epoch_slot"))

        with self._lock:
            last_epoch = self._last_epoch
            last_slot  = self._last_slot

        if slot is not None and slot != last_slot:
            self.emit("new_block", {
                "slot": slot,
                "epoch": epoch,
                "timestamp": int(time.time()),
            })
            with self._lock:
                self._last_slot = slot

        if epoch is not None and epoch != last_epoch and last_epoch is not None:
            self.emit("epoch_settlement", {
                "epoch": last_epoch,
                "new_epoch": epoch,
                "timestamp": int(time.time()),
                "total_rtc": epoch_data.get("pot_rtc", epoch_data.get("reward_pot", 0)),
                "miners": epoch_data.get("enrolled_miners", epoch_data.get("miners_enrolled", 0)),
            })
            with self._lock:
                self._last_epoch = epoch
        elif epoch is not None and last_epoch is None:
            with self._lock:
                self._last_epoch = epoch

    def process_miners(self, miners: list):
        new_attests = {}
        for m in miners:
            wallet = m.get("wallet_name", m.get("wallet", ""))
            ts     = m.get("last_attestation_time", m.get("last_attest", 0))
            arch   = m.get("hardware_type", m.get("arch", "unknown"))
            mult   = m.get("multiplier", m.get("rtc_multiplier", 1.0))
            if wallet:
                new_attests[wallet] = (ts, arch, mult)

        with self._lock:
            last_miners = self._last_miners

        for wallet, (ts, arch, mult) in new_attests.items():
            prev_ts = last_miners.get(wallet, (None,))[0]
            if ts and ts != prev_ts:
                self.emit("attestation", {
                    "miner": wallet,
                    "arch": arch,
                    "multiplier": mult,
                    "timestamp": ts,
                })

        with self._lock:
            self._last_miners = new_attests


# ─── Poller ─────────────────────────────────────────────────────────────────── #
bus = EventBus()

def _fetch(path):
    url = f"{NODE_URL.rstrip('/')}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-ws/1.0"})
        with urllib.request.urlopen(req, timeout=8, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _poll_loop():
    while True:
        try:
            epoch_data = _fetch("/epoch")
            if epoch_data:
                bus.process_epoch(epoch_data)

            miners_data = _fetch("/api/miners")
            if miners_data:
                miners = miners_data if isinstance(miners_data, list) else miners_data.get("miners", [])
                bus.process_miners(miners)

        except Exception:
            pass

        time.sleep(POLL_INTERVAL)


def start_event_poller():
    """Start background polling thread. Call once at app startup."""
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()


# ─── Flask-SocketIO Blueprint ─────────────────────────────────────────────────── #
ws_bp = Blueprint("ws", __name__)

if HAVE_SOCKETIO:
    socketio = SocketIO(cors_allowed_origins="*", async_mode="threading",
                        ping_timeout=HEARTBEAT_S, ping_interval=HEARTBEAT_S,
                        max_http_buffer_size=1024 * 64)

    # Track subscriptions per session
    _subscriptions = {}  # sid -> set of event types (None = all)

    @socketio.on("connect", namespace="/ws/feed")
    def on_connect():
        sid = socketio.server.get_environ(None, namespace="/ws/feed")
        _subscriptions[sid] = None  # subscribe to all by default
        # Register bus handler for this client
        def handler(event):
            try:
                socketio.emit("event", event, namespace="/ws/feed", to=sid)
            except Exception:
                pass
        _subscriptions[sid] = handler
        bus.subscribe(handler)
        emit("connected", {"status": "ok", "node": NODE_URL, "heartbeat_s": HEARTBEAT_S})

    @socketio.on("disconnect", namespace="/ws/feed")
    def on_disconnect():
        sid = socketio.server.get_environ(None, namespace="/ws/feed")
        handler = _subscriptions.pop(sid, None)
        if handler and callable(handler):
            bus.unsubscribe(handler)

    @socketio.on("subscribe", namespace="/ws/feed")
    def on_subscribe(data):
        """Client can filter by event type: {'types': ['attestation', 'new_block']}"""
        types = data.get("types") if isinstance(data, dict) else None
        sid = socketio.server.get_environ(None, namespace="/ws/feed")
        old_handler = _subscriptions.pop(sid, None)
        if old_handler and callable(old_handler):
            bus.unsubscribe(old_handler)

        filt = set(types) if types else None

        def handler(event):
            try:
                socketio.emit("event", event, namespace="/ws/feed", to=sid)
            except Exception:
                pass

        _subscriptions[sid] = handler
        bus.subscribe(handler, filt)
        emit("subscribed", {"types": list(filt) if filt else "all"})

    @socketio.on("ping", namespace="/ws/feed")
    def on_ping():
        emit("pong", {"ts": time.time()})

    @ws_bp.route("/ws/feed/status")
    def ws_status():
        from flask import jsonify
        return jsonify({
            "connected_clients": len(_subscriptions),
            "node_url": NODE_URL,
            "poll_interval_s": POLL_INTERVAL,
            "heartbeat_s": HEARTBEAT_S,
        })


# ─── Standalone mode ─────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import argparse
    from flask import Flask

    parser = argparse.ArgumentParser(description="RustChain WebSocket Real-Time Feed")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--node", default=NODE_URL)
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL)
    args = parser.parse_args()

    NODE_URL      = args.node
    POLL_INTERVAL = args.interval

    app = Flask(__name__)

    if HAVE_SOCKETIO:
        socketio.init_app(app)
        app.register_blueprint(ws_bp)
        start_event_poller()

        print("RustChain WebSocket Real-Time Feed")
        print(f"  Node:    {NODE_URL}")
        print(f"  Port:    {args.port}")
        print(f"  Poll:    {POLL_INTERVAL}s")
        print(f"  Connect: ws://localhost:{args.port}/ws/feed")
        print()
        print("  Events emitted:")
        print("    new_block        — every new slot detected")
        print("    epoch_settlement — when epoch advances")
        print("    attestation      — when miner attests")
        print()
        print("  Subscribe to specific events:")
        print('    socket.emit("subscribe", {"types": ["attestation"]})')
        print()

        socketio.run(app, host=args.host, port=args.port, debug=False)
    else:
        print("flask-socketio not installed. Run: pip install flask-socketio")
        print("Starting demo event bus (no WebSocket)...")
        start_event_poller()

        def demo_handler(event):
            print(f"[EVENT] {event['type']}: {json.dumps(event['data'])[:80]}")

        bus.subscribe(demo_handler)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
