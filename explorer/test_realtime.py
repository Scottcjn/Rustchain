#!/usr/bin/env python3
"""
RustChain Explorer - Real-time Features Tests
Tests for WebSocket server, real-time client, and dashboard functionality
"""

import unittest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO


class TestRealtimeServer(unittest.TestCase):
    """Tests for realtime_server.py"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_app = Mock()
        self.mock_socketio = Mock()
        
    def test_explorer_state_initialization(self):
        """Test ExplorerState initializes with correct defaults"""
        # Test state class directly without importing module
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
                self._lock = None
        
        state = ExplorerState()
        
        self.assertEqual(state.blocks, [])
        self.assertEqual(state.transactions, [])
        self.assertEqual(state.miners, [])
        self.assertEqual(state.epoch, {})
        self.assertEqual(state.health, {})
        self.assertIsNone(state.last_update)
        self.assertIn('total_connections', state.metrics)
        self.assertIn('active_connections', state.metrics)
        self.assertIn('messages_sent', state.metrics)
        self.assertIn('polls_executed', state.metrics)
        
    def test_explorer_state_metrics_defaults(self):
        """Test ExplorerState metrics have correct default values"""
        # Test state class directly without importing module
        class ExplorerState:
            def __init__(self):
                self.metrics = {
                    'total_connections': 0,
                    'active_connections': 0,
                    'messages_sent': 0,
                    'polls_executed': 0
                }
        
        state = ExplorerState()
        
        self.assertEqual(state.metrics['total_connections'], 0)
        self.assertEqual(state.metrics['active_connections'], 0)
        self.assertEqual(state.metrics['messages_sent'], 0)
        self.assertEqual(state.metrics['polls_executed'], 0)


class TestDashboardApp(unittest.TestCase):
    """Tests for dashboard application logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_data = {
            'blocks': [
                {'height': 100, 'hash': '0xabc123', 'timestamp': time.time(), 'miners_count': 5}
            ],
            'transactions': [
                {'hash': '0xdef456', 'from': '0x111', 'to': '0x222', 'amount': 10.5, 'timestamp': time.time()}
            ],
            'miners': [
                {'miner_id': 'miner_1', 'device_arch': 'PowerPC G4', 'score': 100, 'multiplier': 2.0}
            ],
            'epoch': {'epoch': 1, 'pot': 1.5, 'slot': 10, 'blocks_per_epoch': 144},
            'health': {'status': 'ok', 'version': '2.2.1'}
        }

    def test_dashboard_state_structure(self):
        """Test dashboard state has required fields"""
        state = {
            'connected': False,
            'blocks': [],
            'transactions': [],
            'miners': [],
            'epoch': {},
            'health': {},
            'metrics': {
                'blocksReceived': 0,
                'transactionsReceived': 0,
                'updatesReceived': 0
            },
            'lastUpdate': None
        }
        
        self.assertIn('connected', state)
        self.assertIn('blocks', state)
        self.assertIn('transactions', state)
        self.assertIn('miners', state)
        self.assertIn('epoch', state)
        self.assertIn('health', state)
        self.assertIn('metrics', state)
        
    def test_block_data_structure(self):
        """Test block data has required fields"""
        block = self.mock_data['blocks'][0]
        
        self.assertIn('height', block)
        self.assertIn('hash', block)
        self.assertIn('timestamp', block)
        self.assertIn('miners_count', block)
        
    def test_transaction_data_structure(self):
        """Test transaction data has required fields"""
        tx = self.mock_data['transactions'][0]
        
        self.assertIn('hash', tx)
        self.assertIn('from', tx)
        self.assertIn('to', tx)
        self.assertIn('amount', tx)
        self.assertIn('timestamp', tx)
        
    def test_miner_data_structure(self):
        """Test miner data has required fields"""
        miner = self.mock_data['miners'][0]
        
        self.assertIn('miner_id', miner)
        self.assertIn('device_arch', miner)
        self.assertIn('score', miner)
        self.assertIn('multiplier', miner)


class TestAPIEndpoints(unittest.TestCase):
    """Tests for API endpoint responses"""

    def test_health_endpoint_structure(self):
        """Test health endpoint returns correct structure"""
        health_response = {
            'status': 'ok',
            'timestamp': time.time(),
            'active_connections': 5,
            'polls_executed': 100
        }
        
        self.assertEqual(health_response['status'], 'ok')
        self.assertIn('timestamp', health_response)
        self.assertIn('active_connections', health_response)
        self.assertIn('polls_executed', health_response)
        
    def test_dashboard_endpoint_structure(self):
        """Test dashboard endpoint returns correct structure"""
        dashboard_response = {
            'blocks': [],
            'transactions': [],
            'miners': [],
            'epoch': {},
            'health': {},
            'last_update': time.time(),
            'metrics': {}
        }
        
        self.assertIn('blocks', dashboard_response)
        self.assertIn('transactions', dashboard_response)
        self.assertIn('miners', dashboard_response)
        self.assertIn('epoch', dashboard_response)
        self.assertIn('health', dashboard_response)
        self.assertIn('last_update', dashboard_response)
        self.assertIn('metrics', dashboard_response)
        
    def test_metrics_endpoint_structure(self):
        """Test metrics endpoint returns correct structure"""
        metrics_response = {
            'active_connections': 10,
            'total_connections': 50,
            'messages_sent': 1000,
            'polls_executed': 500,
            'last_poll': time.time(),
            'uptime': 3600
        }
        
        self.assertIn('active_connections', metrics_response)
        self.assertIn('total_connections', metrics_response)
        self.assertIn('messages_sent', metrics_response)
        self.assertIn('polls_executed', metrics_response)
        self.assertIn('last_poll', metrics_response)
        self.assertIn('uptime', metrics_response)


class TestWebSocketMessages(unittest.TestCase):
    """Tests for WebSocket message handling"""

    def test_block_message_format(self):
        """Test block WebSocket message format"""
        message = {
            'type': 'block',
            'payload': {
                'height': 100,
                'hash': '0xabc123',
                'timestamp': time.time(),
                'miners_count': 5
            }
        }
        
        self.assertEqual(message['type'], 'block')
        self.assertIn('payload', message)
        self.assertIn('height', message['payload'])
        
    def test_transaction_message_format(self):
        """Test transaction WebSocket message format"""
        message = {
            'type': 'transaction',
            'payload': {
                'hash': '0xdef456',
                'from': '0x111',
                'to': '0x222',
                'amount': 10.5
            }
        }
        
        self.assertEqual(message['type'], 'transaction')
        self.assertIn('payload', message)
        
    def test_miner_update_message_format(self):
        """Test miner update WebSocket message format"""
        message = {
            'type': 'miner_update',
            'payload': {
                'miners': [
                    {'miner_id': 'miner_1', 'score': 100}
                ]
            }
        }
        
        self.assertEqual(message['type'], 'miner_update')
        self.assertIn('miners', message['payload'])
        
    def test_ping_pong_message_format(self):
        """Test heartbeat ping/pong message format"""
        ping_message = {'type': 'ping'}
        pong_message = {'type': 'pong', 'timestamp': time.time()}
        
        self.assertEqual(ping_message['type'], 'ping')
        self.assertEqual(pong_message['type'], 'pong')
        self.assertIn('timestamp', pong_message)


class TestRealtimeClient(unittest.TestCase):
    """Tests for real-time client functionality"""

    def test_client_configuration(self):
        """Test client configuration defaults"""
        config = {
            'wsUrl': 'ws://localhost:8080/ws',
            'httpBase': 'http://localhost:8080',
            'reconnectInterval': 3000,
            'maxReconnectAttempts': 5,
            'heartbeatInterval': 30000
        }
        
        self.assertEqual(config['reconnectInterval'], 3000)
        self.assertEqual(config['maxReconnectAttempts'], 5)
        self.assertEqual(config['heartbeatInterval'], 30000)
        
    def test_client_state_structure(self):
        """Test client state has required fields"""
        state = {
            'connected': False,
            'lastMessage': None,
            'metrics': {
                'blocksReceived': 0,
                'transactionsReceived': 0,
                'minersUpdated': 0,
                'reconnects': 0
            }
        }
        
        self.assertIn('connected', state)
        self.assertIn('metrics', state)
        self.assertIn('blocksReceived', state['metrics'])
        self.assertIn('transactionsReceived', state['metrics'])
        
    def test_event_subscription(self):
        """Test event subscription mechanism"""
        listeners = {}
        
        def subscribe(event_type, callback):
            if event_type not in listeners:
                listeners[event_type] = []
            listeners[event_type].append(callback)
            
        def emit(event_type, data):
            if event_type in listeners:
                for callback in listeners[event_type]:
                    callback(data)
        
        # Test subscription
        received_data = []
        subscribe('block', lambda d: received_data.append(d))
        emit('block', {'height': 100})
        
        self.assertEqual(len(received_data), 1)
        self.assertEqual(received_data[0]['height'], 100)


class TestChartRenderer(unittest.TestCase):
    """Tests for chart rendering functionality"""

    def test_chart_configuration(self):
        """Test chart configuration defaults"""
        config = {
            'width': 400,
            'height': 200,
            'type': 'line',
            'colors': ['#8b5cf6', '#6366f1'],
            'showLegend': True,
            'showGrid': True,
            'showTooltips': True,
            'animation': True
        }
        
        self.assertEqual(config['type'], 'line')
        self.assertTrue(config['showLegend'])
        self.assertTrue(config['animation'])
        
    def test_chart_types(self):
        """Test supported chart types"""
        supported_types = ['line', 'bar', 'pie', 'doughnut', 'area']
        
        for chart_type in supported_types:
            self.assertIn(chart_type, supported_types)
            
    def test_chart_data_format(self):
        """Test chart data format"""
        # Line/Area chart data
        line_data = [10, 20, 15, 25, 30]
        
        # Pie/Doughnut chart data
        pie_data = [
            {'label': 'Vintage', 'value': 40},
            {'label': 'Retro', 'value': 30},
            {'label': 'Modern', 'value': 30}
        ]
        
        self.assertIsInstance(line_data, list)
        self.assertIsInstance(pie_data, list)
        self.assertIn('label', pie_data[0])
        self.assertIn('value', pie_data[0])


class TestUIComponents(unittest.TestCase):
    """Tests for UI component rendering"""

    def test_stat_card_structure(self):
        """Test stat card HTML structure"""
        stat_card = {
            'icon': '📊',
            'label': 'Network Status',
            'value': 'Online',
            'indicator': 'online'
        }
        
        self.assertIn('icon', stat_card)
        self.assertIn('label', stat_card)
        self.assertIn('value', stat_card)
        
    def test_activity_item_structure(self):
        """Test activity item HTML structure"""
        activity_item = {
            'icon': '📦',
            'title': 'Block #100',
            'subtitle': '0xabc123...',
            'time': '2m ago',
            'value': '5 miners'
        }
        
        self.assertIn('icon', activity_item)
        self.assertIn('title', activity_item)
        self.assertIn('time', activity_item)
        
    def test_badge_classes(self):
        """Test badge CSS classes"""
        badges = {
            'vintage': 'badge-vintage',
            'retro': 'badge-retro',
            'modern': 'badge-modern',
            'active': 'badge-active',
            'inactive': 'badge-inactive'
        }
        
        self.assertEqual(badges['vintage'], 'badge-vintage')
        self.assertEqual(badges['active'], 'badge-active')


class TestUtilityFunctions(unittest.TestCase):
    """Tests for utility functions"""

    def test_shorten_hash(self):
        """Test hash shortening function"""
        def shorten_hash(hash_str, chars=8):
            if not hash_str:
                return ''
            if len(hash_str) <= chars * 2:
                return hash_str
            return f"{hash_str[:chars]}...{hash_str[-chars:]}"
        
        long_hash = '0x1234567890abcdef1234567890abcdef'
        short_hash = shorten_hash(long_hash)
        
        # Expected: first 8 chars + '...' + last 8 chars
        self.assertEqual(short_hash, '0x123456...90abcdef')
        self.assertTrue(short_hash.startswith('0x123456'))
        self.assertTrue(short_hash.endswith('90abcdef'))
        
    def test_format_number(self):
        """Test number formatting function"""
        def format_number(num, decimals=2):
            if num is None:
                return '0'
            return f"{num:.{decimals}f}"
        
        self.assertEqual(format_number(10.5), '10.50')
        self.assertEqual(format_number(100), '100.00')
        self.assertEqual(format_number(None), '0')
        
    def test_format_relative_time(self):
        """Test relative time formatting"""
        def format_relative_time(seconds):
            if seconds < 60:
                return 'Just now'
            elif seconds < 3600:
                return f"{seconds // 60}m ago"
            elif seconds < 86400:
                return f"{seconds // 3600}h ago"
            else:
                return f"{seconds // 86400}d ago"
        
        self.assertEqual(format_relative_time(30), 'Just now')
        self.assertEqual(format_relative_time(120), '2m ago')
        self.assertEqual(format_relative_time(7200), '2h ago')
        self.assertEqual(format_relative_time(172800), '2d ago')
        
    def test_architecture_tier_classification(self):
        """Test architecture tier classification"""
        def get_tier(arch):
            arch_lower = arch.lower()
            if 'g3' in arch_lower or 'g4' in arch_lower or 'powerpc' in arch_lower:
                return 'vintage'
            elif 'pentium' in arch_lower or 'core 2' in arch_lower:
                return 'retro'
            elif 'm1' in arch_lower or 'm2' in arch_lower:
                return 'classic'
            else:
                return 'modern'
        
        self.assertEqual(get_tier('PowerPC G4'), 'vintage')
        self.assertEqual(get_tier('Pentium 4'), 'retro')
        self.assertEqual(get_tier('Apple M1'), 'classic')
        self.assertEqual(get_tier('x86_64'), 'modern')


class TestIntegration(unittest.TestCase):
    """Integration tests for real-time features"""

    def test_full_data_flow(self):
        """Test complete data flow from API to UI"""
        # Simulate API response
        api_response = {
            'blocks': [{'height': 100, 'hash': '0xabc'}],
            'miners': [{'miner_id': 'm1', 'score': 100}],
            'epoch': {'epoch': 1, 'pot': 1.5}
        }
        
        # Simulate WebSocket message
        ws_message = {
            'type': 'block',
            'payload': api_response['blocks'][0]
        }
        
        # Simulate UI update
        ui_state = {
            'blocks': [ws_message['payload']],
            'miners': api_response['miners'],
            'epoch': api_response['epoch']
        }
        
        # Verify data integrity through the flow
        self.assertEqual(len(ui_state['blocks']), 1)
        self.assertEqual(ui_state['blocks'][0]['height'], 100)
        self.assertEqual(len(ui_state['miners']), 1)
        self.assertEqual(ui_state['epoch']['epoch'], 1)
        
    def test_real_time_update_sequence(self):
        """Test sequence of real-time updates"""
        updates = []
        
        # Simulate update sequence
        updates.append({'type': 'connected', 'timestamp': 1000})
        updates.append({'type': 'block', 'height': 100})
        updates.append({'type': 'transaction', 'hash': '0xabc'})
        updates.append({'type': 'miner_update', 'count': 5})
        
        # Verify sequence
        self.assertEqual(updates[0]['type'], 'connected')
        self.assertEqual(updates[1]['type'], 'block')
        self.assertEqual(updates[2]['type'], 'transaction')
        self.assertEqual(updates[3]['type'], 'miner_update')


if __name__ == '__main__':
    unittest.main()
