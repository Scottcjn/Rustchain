import unittest
from unittest.mock import MagicMock, patch
from rustchain.client import RustChainClient, AsyncRustChainClient
from rustchain.models import NodeHealth

class TestRustChainClient(unittest.TestCase):
    @patch('httpx.Client')
    def test_get_health(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.json.return_value = {
            "ok": True, "version": "1.0", "uptime_s": 100, 
            "db_rw": True, "backup_age_hours": 1.0, "tip_age_slots": 0
        }
        
        client = RustChainClient()
        health = client.get_health()
        
        self.assertTrue(health.ok)
        self.assertEqual(health.version, "1.0")

class TestAsyncRustChainClient(unittest.IsolatedAsyncioTestCase):
    @patch('httpx.AsyncClient')
    async def test_get_health(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True, "version": "1.0", "uptime_s": 100, 
            "db_rw": True, "backup_age_hours": 1.0, "tip_age_slots": 0
        }
        mock_client.get.return_value = mock_response
        
        client = AsyncRustChainClient()
        health = await client.get_health()
        
        self.assertTrue(health.ok)
        self.assertEqual(health.version, "1.0")

if __name__ == '__main__':
    unittest.main()
