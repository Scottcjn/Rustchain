import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from rustchain.client import RustChainClient, AsyncRustChainClient
from rustchain.models import NodeHealth, MinerInfo

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
        # Fix: make .get() an AsyncMock or set side_effect to async function
        mock_client.get = AsyncMock(return_value=mock_response)
        
        client = AsyncRustChainClient()
        health = await client.get_health()
        
        self.assertTrue(health.ok)
        self.assertEqual(health.version, "1.0")

    @patch('httpx.AsyncClient')
    async def test_check_eligibility(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"miner": "miner1", "claim_id": "c1", "hardware_type": "cpu"},
            {"miner": "miner2", "claim_id": "c2", "hardware_type": "gpu"}
        ]
        mock_client.get = AsyncMock(return_value=mock_response)

        client = AsyncRustChainClient()
        
        # Test eligible
        is_eligible = await client.check_eligibility("miner1")
        self.assertTrue(is_eligible)
        
        # Test not eligible
        is_eligible = await client.check_eligibility("miner3")
        self.assertFalse(is_eligible)

if __name__ == '__main__':
    unittest.main()
