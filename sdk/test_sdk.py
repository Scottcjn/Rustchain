import unittest
from unittest.mock import patch, MagicMock
from rustchain_sdk import RustChainClient, APIError, AuthenticationError
from rustchain_sdk.models import HealthStatus

class TestRustChainClient(unittest.TestCase):
    def setUp(self):
        self.client = RustChainClient(base_url="https://mock-node", verify_ssl=False)

    @patch('requests.Session.request')
    def test_health_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "backup_age_hours": 6.75,
            "db_rw": True,
            "ok": True,
            "tip_age_slots": 0,
            "uptime_s": 18728,
            "version": "2.2.1-rip200"
        }
        mock_request.return_value = mock_response

        status = self.client.health()
        self.assertTrue(status.ok)
        self.assertEqual(status.version, "2.2.1-rip200")
        self.assertEqual(status.uptime_s, 18728)

    @patch('requests.Session.request')
    def test_balance_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "amount_i64": 118357193,
            "amount_rtc": 118.357193,
            "miner_id": "test_miner"
        }
        mock_request.return_value = mock_response

        balance = self.client.balance("test_miner")
        self.assertEqual(balance.amount_rtc, 118.357193)
        self.assertEqual(balance.miner_id, "test_miner")

    @patch('requests.Session.request')
    def test_invalid_signature_error(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"success": False, "error": "INVALID_SIGNATURE"}
        mock_request.return_value = mock_response
        
        # We need to trigger raise_for_status for the catch block to work in _request
        from requests.exceptions import HTTPError
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)

        with self.assertRaises(AuthenticationError):
            self.client.balance("test_miner")

if __name__ == '__main__':
    unittest.main()
