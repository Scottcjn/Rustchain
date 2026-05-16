#!/usr/bin/env python3
"""
RustChain WebSocket Feed Module
Real-time WebSocket push for Block Explorer
Issue #2295 - 75 RTC Bounty

Features:
- WebSocket server endpoint on RustChain node
- Live block feed (new blocks without refresh)
- Live attestation feed (miner attestations stream)
- Connection status indicator
- Auto-reconnect support
- Works with nginx proxy config

Tech Stack:
- Backend: Python (Flask-SocketIO)
- Compatible with static HTML frontend
"""

import os
import json
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque

try:
    from flask import Flask, request, jsonify
    from flask_socketio import SocketIO, emit, join_room, leave_room
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    print("[WARNING] Flask-SocketIO not installed. WebSocket features disabled.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WS_PORT = int(os.environ.get('WEBSOCKET_PORT', 8765))
API_BASE = os.environ.get('RUSTCHAIN_API_BASE', 'http://localhost:8088')
POLL_INTERVAL = float(os.environ.get('WS_POLL_INTERVAL', '3'))
MAX_EVENTS = int(os.environ.get('WS_MAX_EVENTS', '100'))
JSON_RPC_VERSION = '2.0'
MINING_STATS_SUBSCRIPTION = 'mining_stats'


@dataclass
class BlockEvent:
    """Block event data structure"""
    height: int
    hash: str
    timestamp: float
    miners_count: int
    reward: float
    epoch: int
    slot: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttestationEvent:
    """Attestation event data structure"""
    miner_id: str
    device_arch: str
    multiplier: float
    timestamp: float
    epoch: int
    weight: float
    ticket_id: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EpochSettlementEvent:
    """Epoch settlement event (bonus feature)"""
    epoch: int
    total_blocks: int
    total_reward: float
    miners_count: int
    timestamp: float

    def to_dict(self) -> Dict:
        return asdict(self)


class WebSocketFeed:
    """
    WebSocket Feed Manager for RustChain Block Explorer
    
    Manages real-time data streaming to connected clients.
    Thread-safe event broadcasting with room-based subscriptions.
    """

    def __init__(self, app: Optional[Flask] = None):
        self.socketio: Optional[SocketIO] = None
        self.app: Optional[Flask] = None
        
        # Event history for replay
        self.block_history: deque = deque(maxlen=MAX_EVENTS)
        self.attestation_history: deque = deque(maxlen=MAX_EVENTS)
        self.settlement_history: deque = deque(maxlen=10)
        self.started_at = time.time()
        
        # State
        self.state: Dict[str, Any] = {
            'blocks': [],
            'transactions': [],
            'miners': [],
            'epoch': {},
            'health': {},
            'last_update': None
        }
        
        # Metrics
        self.metrics: Dict[str, int] = {
            'total_connections': 0,
            'active_connections': 0,
            'blocks_sent': 0,
            'attestations_sent': 0,
            'settlements_sent': 0
        }
        self.json_rpc_subscriptions: Dict[str, Dict[str, Any]] = {}
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        # Poller thread
        self._poller_running = False
        self._poller_thread: Optional[threading.Thread] = None
        
        # Callbacks for data fetching
        self._fetch_blocks = None
        self._fetch_miners = None
        self._fetch_epoch = None
        self._fetch_health = None
        
        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize WebSocket with Flask app"""
        if not SOCKETIO_AVAILABLE:
            logger.warning("Flask-SocketIO not available. WebSocket disabled.")
            return
        
        self.app = app
        self.socketio = SocketIO(
            app, 
            cors_allowed_origins="*",
            async_mode='threading',
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=10 * 1024 * 1024
        )
        
        self._register_events()
        logger.info("[WebSocket] Initialized with Flask app")

    def _register_events(self):
        """Register SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection"""
            with self._lock:
                self.metrics['total_connections'] += 1
                self.metrics['active_connections'] += 1
            
            client_id = request.sid if request else 'unknown'
            logger.info(f"[WebSocket] Client connected: {client_id}")
            
            # Send welcome message with current state
            emit('connected', {
                'timestamp': time.time(),
                'server_time': datetime.utcnow().isoformat(),
                'state': {
                    'blocks_count': len(self.state.get('blocks', [])),
                    'miners_count': len(self.state.get('miners', [])),
                    'epoch': self.state.get('epoch', {}),
                    'last_update': self.state.get('last_update')
                }
            })
            
            # Send connection status indicator data
            emit('connection_status', {
                'status': 'connected',
                'server_version': '2.2.1-ws',
                'ping_interval': 25
            })
            
            # Send recent events for catch-up
            if self.block_history:
                emit('block_history', [b.to_dict() for b in list(self.block_history)[-10:]])
            if self.attestation_history:
                emit('attestation_history', [a.to_dict() for a in list(self.attestation_history)[-10:]])

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            with self._lock:
                self.metrics['active_connections'] = max(0, self.metrics['active_connections'] - 1)
            
            client_id = request.sid if request else 'unknown'
            logger.info(f"[WebSocket] Client disconnected: {client_id}")

        @self.socketio.on('ping')
        def handle_ping():
            """Handle heartbeat ping from client"""
            emit('pong', {
                'timestamp': time.time(),
                'server_time': datetime.utcnow().isoformat()
            })

        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            """Subscribe to specific event channels"""
            room = data.get('room', 'all')
            join_room(room)
            logger.info(f"[WebSocket] Client subscribed to room: {room}")
            emit('subscribed', {'room': room})

        @self.socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            """Unsubscribe from event channels"""
            room = data.get('room', 'all')
            leave_room(room)
            logger.info(f"[WebSocket] Client unsubscribed from room: {room}")

        @self.socketio.on('request_state')
        def handle_request_state():
            """Send current state to client"""
            with self._lock:
                emit('state', {
                    'blocks': self.state.get('blocks', [])[:50],
                    'miners': self.state.get('miners', []),
                    'epoch': self.state.get('epoch', {}),
                    'health': self.state.get('health', {}),
                    'last_update': self.state.get('last_update')
                })

        @self.socketio.on('request_metrics')
        def handle_request_metrics():
            """Send server metrics to client"""
            with self._lock:
                emit('metrics', dict(self.metrics))

        @self.socketio.on('json_rpc')
        def handle_json_rpc(data):
            """Handle JSON-RPC requests over the existing WebSocket channel."""
            client_id = request.sid if request else None
            response = self.handle_json_rpc_message(data, client_id=client_id)
            emit('json_rpc', response)
            if isinstance(response, dict) and response.get('result'):
                emit('json_rpc', self.build_mining_stats_notification(response['result']))

    def set_fetch_callbacks(self, fetch_blocks=None, fetch_miners=None, 
                            fetch_epoch=None, fetch_health=None):
        """Set custom callbacks for data fetching"""
        self._fetch_blocks = fetch_blocks
        self._fetch_miners = fetch_miners
        self._fetch_epoch = fetch_epoch
        self._fetch_health = fetch_health

    def broadcast_block(self, block: BlockEvent):
        """Broadcast new block to all connected clients"""
        if not self.socketio:
            return
        
        with self._lock:
            self.block_history.append(block)
            self.metrics['blocks_sent'] += 1
        
        self.socketio.emit('block', block.to_dict(), namespace='/')
        logger.info(f"[WebSocket] Broadcasted block #{block.height}")
        self.broadcast_mining_stats()

    def broadcast_attestation(self, attestation: AttestationEvent):
        """Broadcast new attestation to all connected clients"""
        if not self.socketio:
            return
        
        with self._lock:
            self.attestation_history.append(attestation)
            self.metrics['attestations_sent'] += 1
        
        self.socketio.emit('attestation', attestation.to_dict(), namespace='/')
        logger.info(f"[WebSocket] Broadcasted attestation from {attestation.miner_id[:16]}...")

    def broadcast_epoch_settlement(self, settlement: EpochSettlementEvent):
        """Broadcast epoch settlement event (bonus feature)"""
        if not self.socketio:
            return
        
        with self._lock:
            self.settlement_history.append(settlement)
            self.metrics['settlements_sent'] += 1
        
        self.socketio.emit('epoch_settlement', settlement.to_dict(), namespace='/')
        logger.info(f"[WebSocket] Broadcasted epoch #{settlement.epoch} settlement")

    def broadcast_miner_update(self, miners: List[Dict]):
        """Broadcast miner list update"""
        if not self.socketio:
            return
        
        with self._lock:
            self.state['miners'] = miners
            self.state['last_update'] = time.time()
        
        self.socketio.emit('miner_update', {'miners': miners}, namespace='/')
        self.broadcast_mining_stats()

    def broadcast_epoch_update(self, epoch: Dict):
        """Broadcast epoch update"""
        if not self.socketio:
            return
        
        with self._lock:
            self.state['epoch'] = epoch
            self.state['last_update'] = time.time()
        
        self.socketio.emit('epoch_update', epoch, namespace='/')
        self.broadcast_mining_stats()

    def broadcast_health_update(self, health: Dict):
        """Broadcast health status update"""
        if not self.socketio:
            return
        
        with self._lock:
            self.state['health'] = health
            self.state['last_update'] = time.time()
        
        self.socketio.emit('health', health, namespace='/')
        self.broadcast_mining_stats()

    def update_state(self, key: str, value: Any):
        """Update internal state"""
        with self._lock:
            self.state[key] = value
            self.state['last_update'] = time.time()

    def get_state(self) -> Dict:
        """Get current state"""
        with self._lock:
            return dict(self.state)

    def get_metrics(self) -> Dict:
        """Get current metrics"""
        with self._lock:
            return dict(self.metrics)

    def handle_json_rpc_message(self, message: Dict, client_id: Optional[str] = None) -> Dict:
        """Handle JSON-RPC subscription requests for mining stats."""
        if not isinstance(message, dict):
            return self._json_rpc_error(None, -32600, "Invalid Request")

        request_id = message.get('id')
        if message.get('method') != 'eth_subscribe':
            return self._json_rpc_error(request_id, -32601, "Method not found")

        params = message.get('params') or []
        if not isinstance(params, list) or not params or params[0] != MINING_STATS_SUBSCRIPTION:
            return self._json_rpc_error(request_id, -32602, "Expected params ['mining_stats', options]")

        subscription_id = self._create_json_rpc_subscription(MINING_STATS_SUBSCRIPTION, client_id)
        return {
            'jsonrpc': JSON_RPC_VERSION,
            'id': request_id,
            'result': subscription_id
        }

    def _create_json_rpc_subscription(self, channel: str, client_id: Optional[str]) -> str:
        with self._lock:
            subscription_id = f"{channel}:{client_id or 'anonymous'}:{len(self.json_rpc_subscriptions) + 1}"
            self.json_rpc_subscriptions[subscription_id] = {
                'channel': channel,
                'client_id': client_id,
                'created_at': time.time()
            }
        return subscription_id

    def build_mining_stats_notification(self, subscription_id: str, stats: Optional[Dict] = None) -> Dict:
        """Build an Ethereum-style eth_subscription notification."""
        return {
            'jsonrpc': JSON_RPC_VERSION,
            'method': 'eth_subscription',
            'params': {
                'subscription': subscription_id,
                'result': stats or self.get_mining_stats()
            }
        }

    def get_mining_stats(self) -> Dict:
        """Return the compact stats payload expected by JSON-RPC subscribers."""
        with self._lock:
            miners = list(self.state.get('miners') or [])
            blocks = list(self.state.get('blocks') or [])
            transactions = list(self.state.get('transactions') or [])
            health = dict(self.state.get('health') or {})
            metrics = dict(self.metrics)
            started_at = self.started_at

        hashrate = self._sum_hashrate(miners)
        if hashrate == 0:
            hashrate = self._to_float(health.get('hashrate', health.get('hash_rate', 0)))

        blocks_found = self._to_int(
            health.get('blocks_found', health.get('block_count', len(blocks) or metrics.get('blocks_sent', 0)))
        )
        pending_tx = self._to_int(
            health.get('pending_tx', health.get('pending_transactions', len(transactions)))
        )

        return {
            'hashrate': hashrate,
            'blocks_found': blocks_found,
            'pending_tx': pending_tx,
            'peers': self._peer_count(health),
            'uptime_s': max(0, int(time.time() - started_at))
        }

    def broadcast_mining_stats(self) -> Dict:
        """Broadcast mining stats through plain SocketIO and JSON-RPC streams."""
        stats = self.get_mining_stats()
        if not self.socketio:
            return stats

        self.socketio.emit('mining_stats', stats, namespace='/')
        with self._lock:
            subscriptions = list(self.json_rpc_subscriptions.items())

        for subscription_id, subscription in subscriptions:
            notification = self.build_mining_stats_notification(subscription_id, stats)
            client_id = subscription.get('client_id')
            if client_id:
                self.socketio.emit('json_rpc', notification, to=client_id, namespace='/')
            else:
                self.socketio.emit('json_rpc', notification, namespace='/')

        return stats

    def _json_rpc_error(self, request_id: Any, code: int, message: str) -> Dict:
        return {
            'jsonrpc': JSON_RPC_VERSION,
            'id': request_id,
            'error': {
                'code': code,
                'message': message
            }
        }

    def _sum_hashrate(self, miners: List[Dict]) -> float:
        total = 0.0
        for miner in miners:
            if not isinstance(miner, dict):
                continue
            for key in ('hashrate', 'hash_rate', 'hashrate_hs', 'hashrate_hps'):
                if key in miner:
                    total += self._to_float(miner.get(key))
                    break
        return total

    def _peer_count(self, health: Dict) -> int:
        peers = health.get('peers', health.get('peer_count', health.get('connected_peers', 0)))
        if isinstance(peers, list):
            return len(peers)
        return self._to_int(peers)

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _to_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def run(self, host: str = '0.0.0.0', port: int = None, **kwargs):
        """Run the WebSocket server"""
        if not self.socketio:
            logger.error("WebSocket not initialized. Call init_app() first.")
            return
        
        port = port or WS_PORT
        logger.info(f"[WebSocket] Starting server on {host}:{port}")
        self.socketio.run(self.app, host=host, port=port, **kwargs)


# Global instance
ws_feed = WebSocketFeed()


def init_websocket(app: Flask) -> WebSocketFeed:
    """Initialize WebSocket feed with Flask app"""
    ws_feed.init_app(app)
    return ws_feed


def get_ws_feed() -> WebSocketFeed:
    """Get the global WebSocket feed instance"""
    return ws_feed


# Convenience functions for integration
def broadcast_block(height: int, hash: str, timestamp: float, 
                    miners_count: int, reward: float, 
                    epoch: int, slot: int):
    """Broadcast a new block event"""
    block = BlockEvent(
        height=height,
        hash=hash,
        timestamp=timestamp,
        miners_count=miners_count,
        reward=reward,
        epoch=epoch,
        slot=slot
    )
    ws_feed.broadcast_block(block)


def broadcast_attestation(miner_id: str, device_arch: str, multiplier: float,
                         epoch: int, weight: float, ticket_id: str):
    """Broadcast a new attestation event"""
    attestation = AttestationEvent(
        miner_id=miner_id,
        device_arch=device_arch,
        multiplier=multiplier,
        timestamp=time.time(),
        epoch=epoch,
        weight=weight,
        ticket_id=ticket_id
    )
    ws_feed.broadcast_attestation(attestation)


def broadcast_epoch_settlement(epoch: int, total_blocks: int, 
                               total_reward: float, miners_count: int):
    """Broadcast an epoch settlement event"""
    settlement = EpochSettlementEvent(
        epoch=epoch,
        total_blocks=total_blocks,
        total_reward=total_reward,
        miners_count=miners_count,
        timestamp=time.time()
    )
    ws_feed.broadcast_epoch_settlement(settlement)


if __name__ == '__main__':
    # Standalone WebSocket server for testing
    from flask import Flask
    
    app = Flask(__name__)
    ws = WebSocketFeed(app)
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     RustChain WebSocket Feed Server                      ║
╠══════════════════════════════════════════════════════════╣
║  WebSocket: ws://localhost:{WS_PORT}                        ║
║  Features:                                               ║
║  - Real-time block updates                               ║
║  - Live attestation feed                                 ║
║  - Epoch settlement notifications                        ║
║  - Connection status indicator                           ║
║  - Auto-reconnect support                                ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    ws.run()
