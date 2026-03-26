#!/usr/bin/env python3
"""
Tests for RustChain Multi-Node Health Dashboard
Issue #2300
"""
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from server import (
    NODES,
    NodeStatus,
    init_database,
    record_health,
    record_incident,
    check_node_health,
    detect_status_change,
    cleanup_old_data,
    HISTORY_RETENTION_HOURS
)


class TestNodeStatus(unittest.TestCase):
    """Test NodeStatus dataclass"""
    
    def test_node_status_creation(self):
        """Test creating a NodeStatus instance"""
        status = NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test Location',
            status='up',
            response_time_ms=150.5,
            version='1.0.0',
            uptime_s=3600,
            active_miners=10,
            current_epoch=100,
            timestamp=datetime.now()
        )
        
        self.assertEqual(status.node_id, 'node1')
        self.assertEqual(status.name, 'Test Node')
        self.assertEqual(status.status, 'up')
        self.assertEqual(status.response_time_ms, 150.5)
        self.assertEqual(status.uptime_s, 3600)
        self.assertEqual(status.active_miners, 10)
        self.assertEqual(status.current_epoch, 100)
    
    def test_node_status_with_error(self):
        """Test NodeStatus with error field"""
        status = NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test Location',
            status='down',
            response_time_ms=0,
            version='unknown',
            uptime_s=0,
            active_miners=0,
            current_epoch=0,
            timestamp=datetime.now(),
            error='Connection timeout'
        )
        
        self.assertEqual(status.status, 'down')
        self.assertEqual(status.error, 'Connection timeout')


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        os.environ['DB_PATH'] = self.test_db.name
        
        # Monkey-patch DB_PATH
        import server
        self.original_db_path = server.DB_PATH
        server.DB_PATH = Path(self.test_db.name)
        
        init_database()
    
    def tearDown(self):
        """Clean up test database"""
        import server
        server.DB_PATH = self.original_db_path
        try:
            os.unlink(self.test_db.name)
        except:
            pass
    
    def test_init_database(self):
        """Test database initialization"""
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn('health_history', tables)
        self.assertIn('incidents', tables)
        
        conn.close()
    
    def test_record_health(self):
        """Test recording health status"""
        status = NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test Location',
            status='up',
            response_time_ms=150.5,
            version='1.0.0',
            uptime_s=3600,
            active_miners=10,
            current_epoch=100,
            timestamp=datetime.now()
        )
        
        record_health(status)
        
        # Verify record was inserted
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM health_history")
        count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 1)
    
    def test_record_incident(self):
        """Test recording an incident"""
        record_incident('node1', 'node_down', 'Test incident')
        
        # Verify incident was inserted
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM incidents")
        count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 1)
    
    def test_cleanup_old_data(self):
        """Test cleanup of old data"""
        # Insert old record
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        old_time = (datetime.now() - timedelta(hours=HISTORY_RETENTION_HOURS + 1)).isoformat()
        cursor.execute('''
            INSERT INTO health_history (node_id, timestamp, status)
            VALUES (?, ?, ?)
        ''', ('node1', old_time, 'up'))
        conn.commit()
        conn.close()
        
        # Run cleanup
        cleanup_old_data()
        
        # Verify old record was deleted
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM health_history WHERE timestamp < ?", (old_time,))
        count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 0)


class TestHealthCheck(unittest.TestCase):
    """Test health check functionality"""
    
    @patch('server.requests.get')
    def test_check_node_health_success(self, mock_get):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'version': '1.0.0',
            'uptime_s': 3600,
            'active_miners': 10,
            'epoch': 100,
            'ok': True
        }
        mock_get.return_value = mock_response
        
        node_config = NODES[0]
        status = check_node_health(node_config)
        
        self.assertEqual(status.status, 'up')
        self.assertEqual(status.version, '1.0.0')
        self.assertEqual(status.uptime_s, 3600)
        self.assertEqual(status.active_miners, 10)
        self.assertEqual(status.current_epoch, 100)
        self.assertIsNone(status.error)
    
    @patch('server.requests.get')
    def test_check_node_health_http_error(self, mock_get):
        """Test health check with HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        node_config = NODES[0]
        status = check_node_health(node_config)
        
        self.assertEqual(status.status, 'down')
        self.assertEqual(status.error, 'HTTP 500')
    
    @patch('server.requests.get')
    def test_check_node_health_timeout(self, mock_get):
        """Test health check with timeout"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        node_config = NODES[0]
        status = check_node_health(node_config)
        
        self.assertEqual(status.status, 'down')
        self.assertEqual(status.error, 'Timeout')
    
    @patch('server.requests.get')
    def test_check_node_health_connection_error(self, mock_get):
        """Test health check with connection error"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        node_config = NODES[0]
        status = check_node_health(node_config)
        
        self.assertEqual(status.status, 'down')
        self.assertEqual(status.error, 'Connection Error')
    
    @patch('server.requests.get')
    def test_check_node_health_measures_response_time(self, mock_get):
        """Test that health check measures response time"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'version': '1.0.0',
            'uptime_s': 3600,
            'active_miners': 10,
            'epoch': 100,
            'ok': True
        }
        mock_get.return_value = mock_response
        
        node_config = NODES[0]
        status = check_node_health(node_config)
        
        # Response time should be positive
        self.assertGreater(status.response_time_ms, 0)


class TestIncidentDetection(unittest.TestCase):
    """Test incident detection logic"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        
        import server
        self.original_db_path = server.DB_PATH
        server.DB_PATH = Path(self.test_db.name)
        server.incident_log.clear()
        self.server_module = server
        
        init_database()
    
    def tearDown(self):
        """Clean up"""
        import server
        server.DB_PATH = self.original_db_path
        try:
            os.unlink(self.test_db.name)
        except:
            pass
    
    def test_detect_node_down_incident(self):
        """Test detection of node going down"""
        old_status = {'status': 'up'}
        new_status = NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test Location',
            status='down',
            response_time_ms=0,
            version='unknown',
            uptime_s=0,
            active_miners=0,
            current_epoch=0,
            timestamp=datetime.now(),
            error='Connection failed'
        )
        
        detect_status_change(old_status, new_status)
        
        # Check incident was logged
        self.assertEqual(len(self.server_module.incident_log), 1)
        self.assertEqual(self.server_module.incident_log[0]['incident_type'], 'node_down')
    
    def test_detect_node_recovery_incident(self):
        """Test detection of node recovery"""
        old_status = {'status': 'down'}
        new_status = NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test Location',
            status='up',
            response_time_ms=150,
            version='1.0.0',
            uptime_s=3600,
            active_miners=10,
            current_epoch=100,
            timestamp=datetime.now()
        )
        
        detect_status_change(old_status, new_status)
        
        # Check incident was logged
        self.assertEqual(len(self.server_module.incident_log), 1)
        self.assertEqual(self.server_module.incident_log[0]['incident_type'], 'node_recovery')
    
    def test_no_incident_on_same_status(self):
        """Test that no incident is logged when status doesn't change"""
        old_status = {'status': 'up'}
        new_status = NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test Location',
            status='up',
            response_time_ms=150,
            version='1.0.0',
            uptime_s=3600,
            active_miners=10,
            current_epoch=100,
            timestamp=datetime.now()
        )
        
        detect_status_change(old_status, new_status)
        
        # No incident should be logged
        self.assertEqual(len(self.server_module.incident_log), 0)
    
    def test_no_incident_on_none_old_status(self):
        """Test that no incident is logged when old status is None"""
        old_status = None
        new_status = NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test Location',
            status='up',
            response_time_ms=150,
            version='1.0.0',
            uptime_s=3600,
            active_miners=10,
            current_epoch=100,
            timestamp=datetime.now()
        )
        
        detect_status_change(old_status, new_status)
        
        # No incident should be logged on first check
        self.assertEqual(len(self.server_module.incident_log), 0)


class TestNodeConfiguration(unittest.TestCase):
    """Test node configuration"""
    
    def test_all_nodes_configured(self):
        """Test that all 4 nodes from issue #2300 are configured"""
        self.assertEqual(len(NODES), 4)
    
    def test_node_endpoints(self):
        """Test node endpoints match issue #2300"""
        expected_endpoints = [
            'https://50.28.86.131/health',
            'https://50.28.86.153/health',
            'http://76.8.228.245:8099/health',
            'http://38.76.217.189:8099/health'
        ]
        
        actual_endpoints = [node['endpoint'] for node in NODES]
        self.assertEqual(actual_endpoints, expected_endpoints)
    
    def test_node_locations(self):
        """Test node locations match issue #2300"""
        expected_locations = [
            'LiquidWeb US',
            'LiquidWeb US',
            'Ryan\'s Proxmox',
            'Hong Kong'
        ]
        
        actual_locations = [node['location'] for node in NODES]
        self.assertEqual(actual_locations, expected_locations)
    
    def test_nodes_have_coordinates(self):
        """Test that all nodes have geographic coordinates for map"""
        for node in NODES:
            self.assertIn('lat', node)
            self.assertIn('lng', node)
            self.assertIsInstance(node['lat'], (int, float))
            self.assertIsInstance(node['lng'], (int, float))


class TestFlaskAPI(unittest.TestCase):
    """Test Flask API endpoints"""
    
    def setUp(self):
        """Set up test client"""
        import server
        self.app = server.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Set up test database
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.original_db_path = server.DB_PATH
        server.DB_PATH = Path(self.test_db.name)
        init_database()
        
        # Clear and set up test data
        server.current_status.clear()
        server.incident_log.clear()
        self.server_module = server
    
    def tearDown(self):
        """Clean up"""
        import server
        server.DB_PATH = self.original_db_path
        try:
            os.unlink(self.test_db.name)
        except:
            pass
    
    def test_dashboard_route(self):
        """Test dashboard page loads"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'RustChain Network Status', response.data)
    
    def test_api_status_endpoint(self):
        """Test API status endpoint"""
        # Set up test data
        self.server_module.current_status = {
            'node1': {
                'node_id': 'node1',
                'name': 'Node 1',
                'status': 'up',
                'response_time_ms': 150,
                'version': '1.0.0',
                'uptime_s': 3600,
                'active_miners': 10,
                'current_epoch': 100,
                'timestamp': datetime.now().isoformat(),
                'error': None,
                'location': 'Test',
                'endpoint': 'http://test.com',
                'lat': 0,
                'lng': 0
            }
        }
        
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('nodes', data)
        self.assertIn('total_nodes', data)
        self.assertIn('nodes_up', data)
        self.assertIn('nodes_down', data)
    
    def test_api_history_endpoint(self):
        """Test API history endpoint"""
        # Insert test data
        record_health(NodeStatus(
            node_id='node1',
            name='Test Node',
            endpoint='http://test.com/health',
            location='Test',
            status='up',
            response_time_ms=150,
            version='1.0.0',
            uptime_s=3600,
            active_miners=10,
            current_epoch=100,
            timestamp=datetime.now()
        ))
        
        response = self.client.get('/api/history/node1')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['node_id'], 'node1')
        self.assertIn('history', data)
        self.assertGreater(len(data['history']), 0)
    
    def test_api_incidents_endpoint(self):
        """Test API incidents endpoint"""
        # Insert test data
        record_incident('node1', 'node_down', 'Test incident')
        
        response = self.client.get('/api/incidents')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('incidents', data)
        self.assertGreater(len(data['incidents']), 0)
    
    def test_rss_feed_endpoint(self):
        """Test RSS/Atom feed endpoint"""
        # Insert test data with explicit id
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO incidents (node_id, incident_type, timestamp, details)
            VALUES (?, ?, ?, ?)
        ''', ('node1', 'node_down', datetime.now().isoformat(), 'Test incident'))
        conn.commit()
        conn.close()
        
        response = self.client.get('/feed/incidents.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'application/atom+xml', response.headers['Content-Type'].encode())
        self.assertIn(b'<feed', response.data)
        self.assertIn(b'Node Down: Node 1', response.data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
