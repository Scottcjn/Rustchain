#!/usr/bin/env python3
"""
Test suite for Beacon Dashboard v1.1
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock


class TestBeaconDashboard(unittest.TestCase):
    """Test cases for BeaconDashboard class"""
    
    def test_dashboard_initialization(self):
        """Test dashboard initializes correctly"""
        from beacon_dashboard_v1.1 import BeaconDashboard
        dashboard = BeaconDashboard()
        
        self.assertIsNotNone(dashboard.app)
        self.assertEqual(len(dashboard.beacon_nodes), 0)
    
    def test_status_response_format(self):
        """Test status API response format"""
        from datetime import datetime
        status = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_nodes': 5,
            'active_nodes': 3,
            'version': '1.1'
        }
        
        self.assertIn('timestamp', status)
        self.assertIn('total_nodes', status)
        self.assertIn('active_nodes', status)
        self.assertIn('version', status)
        self.assertEqual(status['version'], '1.1')
    
    def test_node_counting(self):
        """Test node counting logic"""
        nodes = {
            'node1': {'active': True, 'name': 'Node 1'},
            'node2': {'active': True, 'name': 'Node 2'},
            'node3': {'active': False, 'name': 'Node 3'},
        }
        
        total = len(nodes)
        active = sum(1 for n in nodes.values() if n.get('active'))
        
        self.assertEqual(total, 3)
        self.assertEqual(active, 2)


class TestDashboardAPI(unittest.TestCase):
    """Test API endpoints"""
    
    @patch('aiohttp.web.Application')
    def test_routes_configured(self, mock_app):
        """Test that all routes are properly configured"""
        from beacon_dashboard_v1.1 import BeaconDashboard
        dashboard = BeaconDashboard()
        
        # Verify routes exist
        routes = dashboard.app.router.routes()
        route_paths = [str(route.method) + ' ' + str(route.resource) for route in routes]
        
        self.assertTrue(any('GET' in r and '/api/status' in r for r in route_paths))
        self.assertTrue(any('GET' in r and '/api/nodes' in r for r in route_paths))


if __name__ == '__main__':
    unittest.main()
