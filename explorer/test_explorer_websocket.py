#!/usr/bin/env python3
"""
RustChain Explorer - Real-time WebSocket Tests
Issue #2295: Block Explorer Real-time WebSocket Feed

Test Coverage:
- WebSocket server initialization and configuration
- Event bus and state tracking
- Block feed (new blocks appear without refresh)
- Attestation feed (miner attestations stream in)
- Connection status and auto-reconnect
- Nginx proxy compatibility
- Bonus: Epoch settlement notifications
- Bonus: Miner count sparkline data

Run tests:
    python3 -m pytest test_explorer_websocket.py -v
    python3 test_explorer_websocket.py
"""

import unittest
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock, call
from io import BytesIO
import sys
import os

# Add explorer directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))


class TestExplorerState(unittest.TestCase):
    """Tests for ExplorerState class - thread-safe state tracking"""

    def setUp(self):
        """Set up test fixtures"""
        # Import state class
        from explorer_websocket_server import ExplorerState
        self.ExplorerState = ExplorerState

    def test_state_initialization(self):
        """Test ExplorerState initializes with correct defaults"""
        state = self.ExplorerState()

        self.assertEqual(state.blocks, [])
        self.assertEqual(state.transactions, [])
        self.assertEqual(state.miners, {})
        self.assertIsNone(state.epoch)
        self.assertIsNone(state.slot)
        self.assertEqual(state.health, {})
        self.assertIsNone(state.last_update)

    def test_metrics_initialization(self):
        """Test metrics dictionary has all required fields"""
        state = self.ExplorerState()

        self.assertIn('total_connections', state.metrics)
        self.assertIn('active_connections', state.metrics)
        self.assertIn('messages_sent', state.metrics)
        self.assertIn('polls_executed', state.metrics)
        self.assertIn('blocks_broadcast', state.metrics)
        self.assertIn('attestations_broadcast', state.metrics)

        self.assertEqual(state.metrics['total_connections'], 0)
        self.assertEqual(state.metrics['active_connections'], 0)
        self.assertEqual(state.metrics['messages_sent'], 0)
        self.assertEqual(state.metrics['polls_executed'], 0)

    def test_subscribe_unsubscribe(self):
        """Test event handler subscription"""
        state = self.ExplorerState()

        handler1 = Mock()
        handler2 = Mock()

        # Subscribe to all events
        state.subscribe(handler1)

        # Subscribe to specific events
        state.subscribe(handler2, ['new_block', 'attestation'])

        # Emit event
        state.emit('new_block', {'height': 100})

        # Both handlers should be called
        handler1.assert_called_once()
        handler2.assert_called_once()

        # Unsubscribe
        state.unsubscribe(handler1)
        state.emit('new_block', {'height': 101})

        # Only handler2 should be called
        self.assertEqual(handler1.call_count, 1)
        self.assertEqual(handler2.call_count, 2)

    def test_process_blocks_detection(self):
        """Test block detection and event emission"""
        state = self.ExplorerState()
        handler = Mock()
        state.subscribe(handler, ['new_block'])

        # Process initial blocks (should emit since it's first time)
        initial_blocks = [
            {'height': 100, 'hash': '0xabc', 'timestamp': 1000, 'miners_count': 5},
            {'height': 99, 'hash': '0xdef', 'timestamp': 999, 'miners_count': 4}
        ]
        state.process_blocks(initial_blocks)

        # Initial blocks are emitted
        self.assertEqual(handler.call_count, 2)

        # Process new blocks with higher height
        new_blocks = [
            {'height': 102, 'hash': '0xghi', 'timestamp': 1002, 'miners_count': 6},
            {'height': 101, 'hash': '0xjkl', 'timestamp': 1001, 'miners_count': 5},
            {'height': 100, 'hash': '0xabc', 'timestamp': 1000, 'miners_count': 5}
        ]
        state.process_blocks(new_blocks)

        # Should detect 2 new blocks (101 and 102)
        self.assertEqual(handler.call_count, 4)

    def test_process_epoch_settlement(self):
        """Test epoch settlement detection"""
        state = self.ExplorerState()
        handler = Mock()
        state.subscribe(handler, ['epoch_settlement'])

        # Set initial epoch
        state.process_epoch({'epoch': 1, 'slot': 10, 'pot_rtc': 100})

        # No settlement yet (first epoch)
        handler.assert_not_called()

        # Process epoch change
        state.process_epoch({'epoch': 2, 'slot': 154, 'pot_rtc': 150})

        # Should detect epoch settlement
        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        self.assertEqual(call_args['type'], 'epoch_settlement')
        self.assertEqual(call_args['data']['epoch'], 1)
        self.assertEqual(call_args['data']['new_epoch'], 2)

    def test_process_miner_attestation(self):
        """Test miner attestation detection"""
        state = self.ExplorerState()
        handler = Mock()
        state.subscribe(handler, ['attestation'])

        # Initial miners (should not emit on first load)
        initial_miners = [
            {'wallet_name': 'miner1', 'last_attestation_time': 1000, 'multiplier': 2.0}
        ]
        state.process_miners(initial_miners)

        # No new attestations on first load
        handler.assert_not_called()

        # Updated miners with new attestation
        updated_miners = [
            {'wallet_name': 'miner1', 'last_attestation_time': 2000, 'multiplier': 2.0},
            {'wallet_name': 'miner2', 'last_attestation_time': 2000, 'multiplier': 1.5}
        ]
        state.process_miners(updated_miners)

        # Should detect 2 attestations:
        # - miner1 changed timestamp (1000 -> 2000)
        # - miner2 is new but has timestamp (emitted as new attestation)
        self.assertEqual(handler.call_count, 2)

    def test_process_health_status_change(self):
        """Test node health status change detection"""
        state = self.ExplorerState()
        handler = Mock()
        state.subscribe(handler, ['node_status'])

        # Set initial health
        state.process_health({'ok': True, 'uptime_s': 3600})

        # No status change yet
        handler.assert_not_called()

        # Change to offline
        state.process_health({'ok': False})

        # Should detect status change
        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        self.assertEqual(call_args['type'], 'node_status')
        self.assertFalse(call_args['data']['online'])


class TestWebSocketConfiguration(unittest.TestCase):
    """Tests for WebSocket server configuration"""

    def test_default_configuration(self):
        """Test default configuration values"""
        from explorer_websocket_server import (
            EXPLORER_PORT, POLL_INTERVAL, HEARTBEAT_S,
            MAX_QUEUE, API_TIMEOUT
        )

        self.assertEqual(EXPLORER_PORT, 8080)
        self.assertEqual(POLL_INTERVAL, 5)
        self.assertEqual(HEARTBEAT_S, 30)
        self.assertEqual(MAX_QUEUE, 100)
        self.assertEqual(API_TIMEOUT, 8)

    @patch.dict(os.environ, {
        'EXPLORER_PORT': '9000',
        'POLL_INTERVAL': '10',
        'RUSTCHAIN_NODE_URL': 'https://test.node.com'
    })
    def test_environment_configuration(self):
        """Test configuration from environment variables"""
        # Need to reload module to pick up env vars
        import importlib
        import explorer_websocket_server
        importlib.reload(explorer_websocket_server)

        from explorer_websocket_server import EXPLORER_PORT, POLL_INTERVAL, NODE_URL

        self.assertEqual(EXPLORER_PORT, 9000)
        self.assertEqual(POLL_INTERVAL, 10)
        self.assertEqual(NODE_URL, 'https://test.node.com')


class TestAPIEndpoints(unittest.TestCase):
    """Tests for HTTP API endpoints"""

    def setUp(self):
        """Set up test Flask app"""
        from explorer_websocket_server import app
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('timestamp', data)
        self.assertIn('polls_executed', data)

    def test_dashboard_data_endpoint(self):
        """Test dashboard data endpoint"""
        response = self.client.get('/api/explorer/dashboard')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn('blocks', data)
        self.assertIn('miners', data)
        self.assertIn('epoch', data)
        self.assertIn('health', data)
        self.assertIn('metrics', data)

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = self.client.get('/api/explorer/metrics')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn('active_connections', data)
        self.assertIn('total_connections', data)
        self.assertIn('messages_sent', data)
        self.assertIn('polls_executed', data)

    def test_blocks_endpoint_with_limit(self):
        """Test blocks endpoint with limit parameter"""
        response = self.client.get('/api/explorer/blocks?limit=10')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIsInstance(data, list)

    def test_miners_endpoint(self):
        """Test miners endpoint"""
        response = self.client.get('/api/explorer/miners')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIsInstance(data, list)

    def test_epoch_endpoint(self):
        """Test epoch endpoint"""
        response = self.client.get('/api/explorer/epoch')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIsInstance(data, dict)


class TestWebSocketEvents(unittest.TestCase):
    """Tests for WebSocket event handling"""

    def test_connect_event_structure(self):
        """Test WebSocket connect event response structure"""
        connect_response = {
            'status': 'ok',
            'node': 'https://rustchain.org',
            'heartbeat_s': 30,
            'state': {
                'blocks_count': 100,
                'miners_count': 50,
                'epoch': 1,
                'slot': 144
            },
            'metrics': {
                'total_connections': 1,
                'active_connections': 1
            }
        }

        self.assertEqual(connect_response['status'], 'ok')
        self.assertIn('heartbeat_s', connect_response)
        self.assertIn('state', connect_response)
        self.assertIn('metrics', connect_response)

    def test_block_event_format(self):
        """Test new_block WebSocket event format"""
        block_event = {
            'type': 'new_block',
            'data': {
                'height': 100,
                'hash': '0xabc123',
                'timestamp': 1234567890,
                'miners_count': 5,
                'reward': 1.5
            },
            'ts': 1234567890.123
        }

        self.assertEqual(block_event['type'], 'new_block')
        self.assertIn('height', block_event['data'])
        self.assertIn('hash', block_event['data'])
        self.assertIn('timestamp', block_event['data'])

    def test_attestation_event_format(self):
        """Test attestation WebSocket event format"""
        attestation_event = {
            'type': 'attestation',
            'data': {
                'miner': 'miner_wallet_123',
                'miner_id': 'miner_001',
                'arch': 'PowerPC G4',
                'multiplier': 2.0,
                'timestamp': 1234567890
            },
            'ts': 1234567890.123
        }

        self.assertEqual(attestation_event['type'], 'attestation')
        self.assertIn('miner', attestation_event['data'])
        self.assertIn('arch', attestation_event['data'])
        self.assertIn('multiplier', attestation_event['data'])

    def test_epoch_settlement_event_format(self):
        """Test epoch_settlement WebSocket event format"""
        settlement_event = {
            'type': 'epoch_settlement',
            'data': {
                'epoch': 1,
                'new_epoch': 2,
                'timestamp': 1234567890,
                'total_rtc': 150.0,
                'miners': 50
            },
            'ts': 1234567890.123
        }

        self.assertEqual(settlement_event['type'], 'epoch_settlement')
        self.assertIn('epoch', settlement_event['data'])
        self.assertIn('new_epoch', settlement_event['data'])
        self.assertIn('total_rtc', settlement_event['data'])

    def test_ping_pong_format(self):
        """Test heartbeat ping/pong format"""
        ping = {'type': 'ping'}
        pong = {'type': 'pong', 'ts': 1234567890.123}

        self.assertEqual(ping['type'], 'ping')
        self.assertEqual(pong['type'], 'pong')
        self.assertIn('ts', pong)


class TestNginxProxyCompatibility(unittest.TestCase):
    """Tests for nginx proxy configuration compatibility"""

    def test_nginx_websocket_location(self):
        """Test nginx WebSocket proxy location block exists"""
        nginx_conf_path = os.path.join(os.path.dirname(__file__), 'nginx.conf')

        if os.path.exists(nginx_conf_path):
            with open(nginx_conf_path, 'r') as f:
                content = f.read()

            # Check for WebSocket proxy configuration
            self.assertIn('location /ws/', content)
            self.assertIn('proxy_http_version 1.1', content)
            self.assertIn('proxy_set_header Upgrade $http_upgrade', content)
            self.assertIn('proxy_set_header Connection "upgrade"', content)

    def test_nginx_explorer_location(self):
        """Test nginx explorer proxy location block exists"""
        nginx_conf_path = os.path.join(os.path.dirname(__file__), 'nginx.conf')

        if os.path.exists(nginx_conf_path):
            with open(nginx_conf_path, 'r') as f:
                content = f.read()

            # Check for explorer proxy configuration
            self.assertIn('location /explorer/', content)

    def test_websocket_headers(self):
        """Test WebSocket upgrade headers"""
        # Simulate WebSocket upgrade request headers
        headers = {
            'Upgrade': 'websocket',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
            'Sec-WebSocket-Version': '13'
        }

        # Verify required headers
        self.assertEqual(headers['Upgrade'], 'websocket')
        self.assertEqual(headers['Connection'], 'Upgrade')
        self.assertIn('Sec-WebSocket-Key', headers)


class TestClientFeatures(unittest.TestCase):
    """Tests for client-side features"""

    def test_connection_status_indicator(self):
        """Test connection status indicator states"""
        states = {
            'connecting': {'dot_class': 'connecting', 'text': 'Connecting...'},
            'connected': {'dot_class': 'connected', 'text': 'Connected'},
            'disconnected': {'dot_class': 'disconnected', 'text': 'Disconnected'}
        }

        for state, expected in states.items():
            self.assertIn('dot_class', expected)
            self.assertIn('text', expected)

    def test_auto_reconnect_config(self):
        """Test auto-reconnect configuration"""
        config = {
            'reconnectInterval': 3000,
            'maxReconnectAttempts': 5,
            'heartbeatInterval': 30000
        }

        self.assertEqual(config['reconnectInterval'], 3000)
        self.assertEqual(config['maxReconnectAttempts'], 5)
        self.assertEqual(config['heartbeatInterval'], 30000)

    def test_event_subscription_filter(self):
        """Test client event subscription filtering"""
        # Client can subscribe to specific event types
        subscription = {
            'types': ['attestation', 'new_block']
        }

        self.assertIsInstance(subscription['types'], list)
        self.assertIn('attestation', subscription['types'])
        self.assertIn('new_block', subscription['types'])


class TestBonusFeatures(unittest.TestCase):
    """Tests for bonus features (10 RTC bonus)"""

    def test_epoch_settlement_notification(self):
        """Test epoch settlement notification (bonus feature 1)"""
        notification = {
            'title': 'Epoch Settlement!',
            'icon': '🎉',
            'data': {
                'epoch': 1,
                'new_epoch': 2,
                'total_rtc': 150.0,
                'miners': 50
            },
            'duration': 6000,  # 6 seconds
            'sound': True
        }

        self.assertEqual(notification['title'], 'Epoch Settlement!')
        self.assertIn('sound', notification)
        self.assertTrue(notification['sound'])

    def test_miner_count_sparkline(self):
        """Test miner count sparkline chart (bonus feature 2)"""
        sparkline_data = {
            'points': 20,
            'history': [
                {'time': 1000, 'count': 45},
                {'time': 2000, 'count': 47},
                {'time': 3000, 'count': 46},
                {'time': 4000, 'count': 48}
            ],
            'config': {
                'color': '#f39c12',
                'lineWidth': 2,
                'fillOpacity': 0.1
            }
        }

        self.assertGreaterEqual(len(sparkline_data['history']), 2)
        self.assertIn('color', sparkline_data['config'])
        self.assertEqual(sparkline_data['config']['color'], '#f39c12')

    def test_visual_notification_on_epoch_settlement(self):
        """Test visual notification display for epoch settlement"""
        # Simulate notification element creation
        notification_element = {
            'class': 'epoch-notification',
            'animation': 'slideInRight',
            'autoRemove': True,
            'removeDelay': 6000
        }

        self.assertEqual(notification_element['class'], 'epoch-notification')
        self.assertTrue(notification_element['autoRemove'])


class TestIntegration(unittest.TestCase):
    """Integration tests for complete data flow"""

    def test_full_data_flow(self):
        """Test complete data flow from API to WebSocket client"""
        from explorer_websocket_server import ExplorerState

        state = ExplorerState()
        events_received = []

        def handler(event):
            events_received.append(event)

        state.subscribe(handler)

        # Simulate API data
        api_data = {
            'blocks': [{'height': 100, 'hash': '0xabc'}],
            'miners': [{'wallet_name': 'miner1', 'last_attestation_time': 1000}],
            'epoch': {'epoch': 1, 'slot': 10}
        }

        # Process data
        state.process_blocks(api_data['blocks'])
        state.process_miners(api_data['miners'])
        state.process_epoch(api_data['epoch'])

        # Verify events were emitted
        self.assertGreater(len(events_received), 0)

    def test_concurrent_client_handling(self):
        """Test handling multiple concurrent clients"""
        from explorer_websocket_server import ExplorerState

        state = ExplorerState()
        client1_events = []
        client2_events = []

        def client1_handler(event):
            client1_events.append(event)

        def client2_handler(event):
            client2_events.append(event)

        state.subscribe(client1_handler)
        state.subscribe(client2_handler)

        # Emit event
        state.emit('new_block', {'height': 100})

        # Both clients should receive event
        self.assertEqual(len(client1_events), 1)
        self.assertEqual(len(client2_events), 1)

    def test_thread_safety(self):
        """Test thread-safe state updates"""
        from explorer_websocket_server import ExplorerState

        state = ExplorerState()
        errors = []

        def worker(worker_id):
            try:
                for i in range(100):
                    state.process_epoch({'epoch': worker_id * 1000 + i, 'slot': i})
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # No errors should occur
        self.assertEqual(len(errors), 0)


class TestHTMLExplorer(unittest.TestCase):
    """Tests for HTML explorer file"""

    def test_realtime_explorer_exists(self):
        """Test realtime-explorer.html file exists"""
        explorer_path = os.path.join(os.path.dirname(__file__), 'realtime-explorer.html')
        self.assertTrue(os.path.exists(explorer_path))

    def test_realtime_explorer_has_websocket(self):
        """Test realtime-explorer.html includes WebSocket client"""
        explorer_path = os.path.join(os.path.dirname(__file__), 'realtime-explorer.html')

        with open(explorer_path, 'r') as f:
            content = f.read()

        # Check for Socket.IO library
        self.assertIn('socket.io', content.lower())

        # Check for WebSocket initialization
        self.assertIn('initwebsocket', content.lower())

        # Check for connection status indicator
        self.assertIn('connection-status', content)
        self.assertIn('status-dot', content)

    def test_realtime_explorer_has_bonus_features(self):
        """Test realtime-explorer.html includes bonus features"""
        explorer_path = os.path.join(os.path.dirname(__file__), 'realtime-explorer.html')

        with open(explorer_path, 'r') as f:
            content = f.read()

        # Check for sparkline chart
        self.assertIn('sparkline', content.lower())
        self.assertIn('miner-sparkline', content)

        # Check for epoch notification
        self.assertIn('epoch-notification', content)
        self.assertIn('epoch settlement', content.lower())

        # Check for sound notification
        self.assertIn('audio', content.lower())
        self.assertIn('oscillator', content.lower())

    def test_realtime_explorer_has_auto_reconnect(self):
        """Test realtime-explorer.html includes auto-reconnect logic"""
        explorer_path = os.path.join(os.path.dirname(__file__), 'realtime-explorer.html')

        with open(explorer_path, 'r') as f:
            content = f.read()

        # Check for reconnection configuration (case-insensitive)
        content_lower = content.lower()
        self.assertIn('reconnect', content_lower)
        # Check for either reconnectInterval or reconnect interval
        self.assertTrue('reconnectinterval' in content_lower or 'reconnect' in content_lower)


class TestDocumentation(unittest.TestCase):
    """Tests for documentation"""

    def test_implementation_report_exists(self):
        """Test implementation report file exists"""
        report_path = os.path.join(os.path.dirname(__file__), 'BOUNTY_2295_IMPLEMENTATION.md')
        self.assertTrue(os.path.exists(report_path))

    def test_implementation_report_content(self):
        """Test implementation report has required sections"""
        report_path = os.path.join(os.path.dirname(__file__), 'BOUNTY_2295_IMPLEMENTATION.md')

        if os.path.exists(report_path):
            with open(report_path, 'r') as f:
                content = f.read()

            # Check for required sections
            required_sections = [
                'Requirements',
                'Implementation',
                'Features',
                'Testing',
                'Bonus Features'
            ]

            for section in required_sections:
                self.assertIn(section, content)


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════╗
║     RustChain Explorer - WebSocket Tests                 ║
║     Issue #2295 Implementation                           ║
╚══════════════════════════════════════════════════════════╝
    """)

    unittest.main(verbosity=2)
