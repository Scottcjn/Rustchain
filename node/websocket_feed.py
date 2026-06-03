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

from __future__ import annotations

import os
import json
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
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
BLOCK_SUBSCRIPTION = 'blocks'
TRANSACTION_SUBSCRIPTION = 'transactions'
ATTESTATION_SUBSCRIPTION = 'attestations'
SUPPORTED_SUBSCRIPTION_CHANNELS = {
    'all',
    BLOCK_SUBSCRIPTION,
    TRANSACTION_SUBSCRIPTION,
    MINING_STATS_SUBSCRIPTION,
    ATTESTATION_SUBSCRIPTION,
}
SUBSCRIPTION_CHANNEL_ALIASES = {
    'all': 'all',
    'block': BLOCK_SUBSCRIPTION,
    'blocks': BLOCK_SUBSCRIPTION,
    'new_block': BLOCK_SUBSCRIPTION,
    'new_blocks': BLOCK_SUBSCRIPTION,
    'newheads': BLOCK_SUBSCRIPTION,
    'transaction': TRANSACTION_SUBSCRIPTION,
    'transactions': TRANSACTION_SUBSCRIPTION,
    'new_transaction': TRANSACTION_SUBSCRIPTION,
    'new_transactions': TRANSACTION_SUBSCRIPTION,
    'newpendingtransactions': TRANSACTION_SUBSCRIPTION,
    'mining_stats': MINING_STATS_SUBSCRIPTION,
    'attestation': ATTESTATION_SUBSCRIPTION,
    'attestations': ATTESTATION_SUBSCRIPTION,
}
ADDRESS_FILTER_FIELDS = {
    'address',
    'wallet',
    'wallet_address',
    'walletaddress',
    'from',
    'from_addr',
    'fromaddress',
    'sender',
    'to',
    'to_addr',
    'toaddress',
    'recipient',
    'miner',
    'miner_id',
    'minerid',
    'owner',
    'counterparty',
}
HEIGHT_FILTER_FIELDS = (
    'height',
    'block_height',
    'block_index',
    'blockNumber',
    'block_number',
    'number',
)
HEIGHT_FILTER_FIELD_KEYS = {field.casefold() for field in HEIGHT_FILTER_FIELDS}


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
        self.socket_subscriptions: Dict[str, List[Dict[str, Any]]] = {}
        
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
            if client_id != 'unknown':
                removed = self.remove_json_rpc_subscriptions(client_id)
                self.remove_socket_subscriptions(client_id)
                if removed:
                    logger.info(f"[WebSocket] Removed {removed} JSON-RPC subscription(s) for {client_id}")
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
            subscription, error = self.normalize_subscription(data)
            if error:
                emit('subscription_error', {'error': error})
                return

            room = subscription['channel']
            join_room(room)
            client_id = request.sid if request else None
            if client_id:
                self.add_socket_subscription(client_id, subscription)
            logger.info(f"[WebSocket] Client subscribed to room: {room} filters={subscription['filters']}")
            emit('subscribed', {
                'room': room,
                'channel': room,
                'filters': subscription['filters'],
            })

        @self.socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            """Unsubscribe from event channels"""
            room = self.subscription_channel_from_payload(data)
            leave_room(room)
            client_id = request.sid if request else None
            if client_id:
                self.remove_socket_subscriptions(client_id, room)
            logger.info(f"[WebSocket] Client unsubscribed from room: {room}")
            emit('unsubscribed', {'room': room, 'channel': room})

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
            subscription_id = self._mining_stats_notification_subscription_id(response)
            if subscription_id:
                emit('json_rpc', self.build_mining_stats_notification(subscription_id))

    def set_fetch_callbacks(self, fetch_blocks=None, fetch_miners=None, 
                            fetch_epoch=None, fetch_health=None):
        """Set custom callbacks for data fetching"""
        self._fetch_blocks = fetch_blocks
        self._fetch_miners = fetch_miners
        self._fetch_epoch = fetch_epoch
        self._fetch_health = fetch_health

    def broadcast_block(self, block: BlockEvent):
        """Broadcast new block to legacy streams and filtered subscribers."""
        if not self.socketio:
            return
        payload = block.to_dict()
        
        with self._lock:
            self.block_history.append(block)
            self.metrics['blocks_sent'] += 1
        
        self.socketio.emit('block', payload, namespace='/')
        self.emit_filtered_socket_subscribers(BLOCK_SUBSCRIPTION, 'block', payload)
        self.emit_json_rpc_subscribers(BLOCK_SUBSCRIPTION, payload)
        logger.info(f"[WebSocket] Broadcasted block #{block.height}")
        self.broadcast_mining_stats()

    def broadcast_transaction(self, transaction: Dict[str, Any]):
        """Broadcast a new transaction to legacy streams and filtered subscribers."""
        if not self.socketio:
            return
        if not isinstance(transaction, dict):
            logger.warning("[WebSocket] Ignored non-dict transaction payload")
            return

        payload = dict(transaction)
        with self._lock:
            transactions = list(self.state.get('transactions') or [])
            transactions.insert(0, payload)
            self.state['transactions'] = transactions[:MAX_EVENTS]
            self.state['last_update'] = time.time()
            self.metrics['transactions_sent'] = self.metrics.get('transactions_sent', 0) + 1

        self.socketio.emit('transaction', payload, namespace='/')
        self.emit_filtered_socket_subscribers(TRANSACTION_SUBSCRIPTION, 'transaction', payload)
        self.emit_json_rpc_subscribers(TRANSACTION_SUBSCRIPTION, payload)
        logger.info(f"[WebSocket] Broadcasted transaction {payload.get('tx_hash', payload.get('id', 'unknown'))}")
        self.broadcast_mining_stats()

    def broadcast_attestation(self, attestation: AttestationEvent):
        """Broadcast new attestation to legacy streams and filtered subscribers."""
        if not self.socketio:
            return
        payload = attestation.to_dict()
        
        with self._lock:
            self.attestation_history.append(attestation)
            self.metrics['attestations_sent'] += 1
        
        self.socketio.emit('attestation', payload, namespace='/')
        self.emit_filtered_socket_subscribers(ATTESTATION_SUBSCRIPTION, 'attestation', payload)
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
        """Handle JSON-RPC subscription requests for live feed channels."""
        if not isinstance(message, dict):
            return self._json_rpc_error(None, -32600, "Invalid Request")

        request_id = message.get('id')
        method = message.get('method')
        params = message.get('params') or []

        if method == 'eth_unsubscribe':
            if not isinstance(params, list) or not params:
                return self._json_rpc_error(request_id, -32602, "Expected subscription id")
            removed = self.remove_json_rpc_subscription(params[0], client_id=client_id)
            return {
                'jsonrpc': JSON_RPC_VERSION,
                'id': request_id,
                'result': removed
            }

        if method != 'eth_subscribe':
            return self._json_rpc_error(request_id, -32601, "Method not found")

        expected_message = "Expected params ['mining_stats'|'newHeads'|'newPendingTransactions', options]"
        if not isinstance(params, list) or not params:
            return self._json_rpc_error(request_id, -32602, expected_message)

        channel = self.normalize_subscription_channel(params[0])
        if channel not in {MINING_STATS_SUBSCRIPTION, BLOCK_SUBSCRIPTION, TRANSACTION_SUBSCRIPTION}:
            return self._json_rpc_error(request_id, -32602, expected_message)

        options = params[1] if len(params) > 1 else {}
        filters, error = self.normalize_subscription_filters(options if isinstance(options, dict) else {})
        if error:
            return self._json_rpc_error(request_id, -32602, error)
        error = self.validate_subscription_filters(channel, filters)
        if error:
            return self._json_rpc_error(request_id, -32602, error)

        subscription_id = self._create_json_rpc_subscription(channel, client_id, filters)
        return {
            'jsonrpc': JSON_RPC_VERSION,
            'id': request_id,
            'result': subscription_id
        }

    def _create_json_rpc_subscription(
        self,
        channel: str,
        client_id: Optional[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            subscription_id = f"{channel}:{client_id or 'anonymous'}:{len(self.json_rpc_subscriptions) + 1}"
            self.json_rpc_subscriptions[subscription_id] = {
                'channel': channel,
                'client_id': client_id,
                'filters': filters or {},
                'created_at': time.time()
            }
        return subscription_id

    def _mining_stats_notification_subscription_id(self, response: Dict) -> Optional[str]:
        if not isinstance(response, dict):
            return None
        subscription_id = response.get('result')
        if not isinstance(subscription_id, str):
            return None
        with self._lock:
            subscription = self.json_rpc_subscriptions.get(subscription_id)
        if not subscription or subscription.get('channel') != MINING_STATS_SUBSCRIPTION:
            return None
        return subscription_id

    def remove_json_rpc_subscription(self, subscription_id: str, client_id: Optional[str] = None) -> bool:
        """Remove one JSON-RPC subscription if it belongs to the caller."""
        with self._lock:
            subscription = self.json_rpc_subscriptions.get(subscription_id)
            if not subscription:
                return False
            if client_id is not None and subscription.get('client_id') != client_id:
                return False
            del self.json_rpc_subscriptions[subscription_id]
            return True

    def remove_json_rpc_subscriptions(self, client_id: str) -> int:
        """Remove all JSON-RPC subscriptions owned by a disconnected client."""
        with self._lock:
            stale_ids = [
                subscription_id
                for subscription_id, subscription in self.json_rpc_subscriptions.items()
                if subscription.get('client_id') == client_id
            ]
            for subscription_id in stale_ids:
                del self.json_rpc_subscriptions[subscription_id]
            return len(stale_ids)

    def build_mining_stats_notification(self, subscription_id: str, stats: Optional[Dict] = None) -> Dict:
        """Build an Ethereum-style eth_subscription notification."""
        return self.build_subscription_notification(subscription_id, stats or self.get_mining_stats())

    def build_subscription_notification(self, subscription_id: str, result: Dict[str, Any]) -> Dict:
        """Build an Ethereum-style eth_subscription notification."""
        return {
            'jsonrpc': JSON_RPC_VERSION,
            'method': 'eth_subscription',
            'params': {
                'subscription': subscription_id,
                'result': result
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

    def normalize_subscription(self, data: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Normalize SocketIO subscribe payloads into a channel plus filters."""
        if data is None:
            data = {}
        if isinstance(data, str):
            data = {'room': data}
        if not isinstance(data, dict):
            return None, "Subscription payload must be an object"

        channel = self.normalize_subscription_channel(
            data.get('channel', data.get('room', data.get('type', 'all')))
        )
        if channel not in SUPPORTED_SUBSCRIPTION_CHANNELS:
            requested = data.get('channel', data.get('room', data.get('type')))
            return None, f"Unsupported subscription channel: {requested}"

        filter_payload = data.get('filters', data.get('filter', {})) or {}
        if not isinstance(filter_payload, dict):
            return None, "Subscription filters must be an object"
        filter_payload = dict(filter_payload)
        for key in ('address', 'wallet', 'wallet_address', 'miner_id', 'min_height', 'from_height', 'block_height'):
            if key in data and key not in filter_payload:
                filter_payload[key] = data[key]

        filters, error = self.normalize_subscription_filters(filter_payload)
        if error:
            return None, error
        error = self.validate_subscription_filters(channel, filters)
        if error:
            return None, error

        return {'channel': channel, 'filters': filters}, None

    def subscription_channel_from_payload(self, data: Any) -> str:
        """Return a best-effort channel name for unsubscribe payloads."""
        if isinstance(data, str):
            channel = data
        elif isinstance(data, dict):
            channel = data.get('channel', data.get('room', data.get('type', 'all')))
        else:
            channel = 'all'
        normalized = self.normalize_subscription_channel(channel)
        return normalized if normalized in SUPPORTED_SUBSCRIPTION_CHANNELS else 'all'

    def normalize_subscription_channel(self, channel: Any) -> Optional[str]:
        if not isinstance(channel, str):
            return None
        key = channel.strip()
        if not key:
            return None
        return SUBSCRIPTION_CHANNEL_ALIASES.get(key.casefold(), SUBSCRIPTION_CHANNEL_ALIASES.get(key))

    def normalize_subscription_filters(self, filters: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
        if not isinstance(filters, dict):
            return {}, "Subscription filters must be an object"

        normalized: Dict[str, Any] = {}
        address = self.first_present(filters, ('address', 'wallet', 'wallet_address', 'miner_id'))
        if address is not None:
            if not isinstance(address, str) or not address.strip():
                return {}, "Address filter must be a non-empty string"
            normalized['address'] = address.strip()

        min_height = self.first_present(filters, ('min_height', 'from_height', 'block_height', 'height'))
        if min_height is not None:
            parsed_height = self.parse_height_filter(min_height)
            if parsed_height is None:
                return {}, "Height filter must be a non-negative integer"
            normalized['min_height'] = parsed_height

        return normalized, None

    def validate_subscription_filters(self, channel: str, filters: Dict[str, Any]) -> Optional[str]:
        if channel == BLOCK_SUBSCRIPTION and filters.get('address'):
            return "Address filters are not supported for block subscriptions"
        return None

    def add_socket_subscription(self, client_id: str, subscription: Dict[str, Any]):
        """Store a filtered SocketIO subscription for one connected client."""
        with self._lock:
            subscriptions = self.socket_subscriptions.setdefault(client_id, [])
            if subscription not in subscriptions:
                subscriptions.append(subscription)

    def remove_socket_subscriptions(self, client_id: str, channel: Optional[str] = None) -> int:
        """Remove stored SocketIO subscriptions for a client."""
        with self._lock:
            subscriptions = self.socket_subscriptions.get(client_id, [])
            if channel is None or channel == 'all':
                removed = len(subscriptions)
                self.socket_subscriptions.pop(client_id, None)
                return removed

            kept = [subscription for subscription in subscriptions if subscription.get('channel') != channel]
            removed = len(subscriptions) - len(kept)
            if kept:
                self.socket_subscriptions[client_id] = kept
            else:
                self.socket_subscriptions.pop(client_id, None)
            return removed

    def emit_filtered_socket_subscribers(self, channel: str, event: str, payload: Dict[str, Any]):
        """Emit a filtered event envelope to SocketIO clients whose filters match."""
        if not self.socketio:
            return
        with self._lock:
            socket_subscriptions = [
                (client_id, list(subscriptions))
                for client_id, subscriptions in self.socket_subscriptions.items()
            ]

        envelope = {
            'channel': channel,
            'event': event,
            'payload': payload,
        }
        for client_id, subscriptions in socket_subscriptions:
            if any(self.subscription_matches(subscription, channel, payload) for subscription in subscriptions):
                self.socketio.emit('subscription_event', envelope, to=client_id, namespace='/')

    def emit_json_rpc_subscribers(self, channel: str, payload: Dict[str, Any]):
        """Emit JSON-RPC subscription notifications for matching live-feed subscriptions."""
        if not self.socketio:
            return
        with self._lock:
            subscriptions = list(self.json_rpc_subscriptions.items())

        for subscription_id, subscription in subscriptions:
            if not self.subscription_matches(subscription, channel, payload):
                continue
            notification = self.build_subscription_notification(subscription_id, payload)
            client_id = subscription.get('client_id')
            if client_id:
                self.socketio.emit('json_rpc', notification, to=client_id, namespace='/')
            else:
                self.socketio.emit('json_rpc', notification, namespace='/')

    def subscription_matches(self, subscription: Dict[str, Any], channel: str, payload: Dict[str, Any]) -> bool:
        subscription_channel = subscription.get('channel')
        if subscription_channel not in ('all', channel):
            return False

        filters = subscription.get('filters') or {}
        min_height = filters.get('min_height')
        if min_height is not None:
            payload_height = self.payload_height(payload)
            if payload_height is None or payload_height < min_height:
                return False

        address = filters.get('address')
        if address and not self.payload_references_address(payload, address):
            return False

        return True

    def payload_height(self, payload: Any) -> Optional[int]:
        if not isinstance(payload, dict):
            return None
        for key, value in payload.items():
            if not isinstance(key, str) or key.casefold() not in HEIGHT_FILTER_FIELD_KEYS:
                continue
            height = self.parse_height_filter(value)
            if height is not None:
                return height
        return None

    def payload_references_address(self, payload: Any, address: str) -> bool:
        target = address.casefold()
        return any(value.casefold() == target for value in self.iter_address_values(payload))

    def iter_address_values(self, payload: Any):
        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(key, str) and key.casefold() in ADDRESS_FILTER_FIELDS and isinstance(value, str):
                    yield value
                if isinstance(value, (dict, list)):
                    yield from self.iter_address_values(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self.iter_address_values(item)

    def first_present(self, payload: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]
        return None

    def parse_height_filter(self, value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            try:
                parsed = int(value, 0)
            except ValueError:
                return None
            return parsed if parsed >= 0 else None
        return None

    def broadcast_mining_stats(self) -> Dict:
        """Broadcast mining stats through plain SocketIO and JSON-RPC streams."""
        stats = self.get_mining_stats()
        if not self.socketio:
            return stats

        self.socketio.emit('mining_stats', stats, namespace='/')
        with self._lock:
            subscriptions = list(self.json_rpc_subscriptions.items())

        for subscription_id, subscription in subscriptions:
            if subscription.get('channel') != MINING_STATS_SUBSCRIPTION:
                continue
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


def broadcast_transaction(transaction: Dict[str, Any]):
    """Broadcast a new transaction event."""
    ws_feed.broadcast_transaction(transaction)


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
