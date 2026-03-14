"""
Unit tests for network utility functions in rustchain_wallet_secure.py

Tests the network connectivity checking and retry logic that was added
to improve error handling and user experience when nodes are unreachable.

Bounty #1589: Add unit tests for untested functions
"""

import unittest
from unittest.mock import patch, MagicMock
import socket
from requests.exceptions import ConnectionError, Timeout, HTTPError

# Import the functions we're testing
import sys
from pathlib import Path
wallet_dir = Path(__file__).parent.parent / "wallet"
sys.path.insert(0, str(wallet_dir))

from rustchain_wallet_secure import SecureFounderWallet


class TestNetworkConnectivity(unittest.TestCase):
    """Test network connectivity checking function."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a minimal SecureFounderWallet instance for testing
        # We don't need the full GUI, just the network methods
        self.wallet = MagicMock(spec=SecureFounderWallet)
        self.wallet._check_network_connectivity = SecureFounderWallet._check_network_connectivity.__get__(
            self.wallet, SecureFounderWallet
        )

    @patch('socket.gethostbyname')
    @patch('socket.socket')
    def test_check_network_connectivity_success(self, mock_socket_class, mock_gethostbyname):
        """Test successful network connectivity check."""
        # Mock DNS resolution
        mock_gethostbyname.return_value = "1.2.3.4"
        
        # Mock successful TCP connection
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0  # Success
        mock_socket_class.return_value = mock_sock
        
        is_reachable, error = self.wallet._check_network_connectivity("https://rustchain.org")
        
        self.assertTrue(is_reachable)
        self.assertEqual(error, "")
        mock_gethostbyname.assert_called_once_with("rustchain.org")
        mock_sock.connect_ex.assert_called_once_with(("rustchain.org", 443))

    @patch('socket.gethostbyname')
    def test_check_network_connectivity_dns_failure(self, mock_gethostbyname):
        """Test network check when DNS resolution fails."""
        mock_gethostbyname.side_effect = socket.gaierror("Name or service not known")
        
        is_reachable, error = self.wallet._check_network_connectivity("https://rustchain.org")
        
        self.assertFalse(is_reachable)
        self.assertIn("DNS resolution failed", error)
        self.assertIn("rustchain.org", error)

    @patch('socket.gethostbyname')
    @patch('socket.socket')
    def test_check_network_connectivity_connection_refused(self, mock_socket_class, mock_gethostbyname):
        """Test network check when connection is refused."""
        mock_gethostbyname.return_value = "1.2.3.4"
        
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # Connection refused
        mock_socket_class.return_value = mock_sock
        
        is_reachable, error = self.wallet._check_network_connectivity("https://rustchain.org")
        
        self.assertFalse(is_reachable)
        self.assertIn("Cannot connect", error)
        self.assertIn("rustchain.org:443", error)
        self.assertIn("111", error)

    @patch('socket.gethostbyname')
    @patch('socket.socket')
    def test_check_network_connectivity_http_port(self, mock_socket_class, mock_gethostbyname):
        """Test network check uses correct port for HTTP."""
        mock_gethostbyname.return_value = "1.2.3.4"
        
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_sock
        
        is_reachable, error = self.wallet._check_network_connectivity("http://example.com")
        
        self.assertTrue(is_reachable)
        # Should use port 80 for HTTP
        mock_sock.connect_ex.assert_called_once_with(("example.com", 80))


class TestFetchWithRetry(unittest.TestCase):
    """Test fetch with retry logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.wallet = MagicMock(spec=SecureFounderWallet)
        self.wallet._fetch_with_retry = SecureFounderWallet._fetch_with_retry.__get__(
            self.wallet, SecureFounderWallet
        )
        self.wallet._check_network_connectivity = MagicMock(return_value=(True, ""))

    @patch('requests.get')
    def test_fetch_with_retry_success_first_attempt(self, mock_get):
        """Test successful fetch on first attempt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"balance": 100.5}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        data, error = self.wallet._fetch_with_retry("https://rustchain.org/wallet/balance")
        
        self.assertIsNotNone(data)
        self.assertIsNone(error)
        self.assertEqual(data["balance"], 100.5)
        mock_get.assert_called_once()

    @patch('requests.get')
    @patch('time.sleep')
    def test_fetch_with_retry_success_after_retry(self, mock_sleep, mock_get):
        """Test successful fetch after one retry."""
        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.json.return_value = {"balance": 100.5}
        mock_response.raise_for_status = MagicMock()
        
        mock_get.side_effect = [
            ConnectionError("Connection failed"),
            mock_response
        ]
        
        data, error = self.wallet._fetch_with_retry("https://rustchain.org/wallet/balance", max_retries=2)
        
        self.assertIsNotNone(data)
        self.assertIsNone(error)
        self.assertEqual(data["balance"], 100.5)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()  # Should sleep between retries

    @patch('requests.get')
    @patch('time.sleep')
    def test_fetch_with_retry_all_attempts_fail(self, mock_sleep, mock_get):
        """Test when all retry attempts fail."""
        mock_get.side_effect = ConnectionError("Connection failed")
        self.wallet._check_network_connectivity.return_value = (False, "Network unreachable")
        
        data, error = self.wallet._fetch_with_retry("https://rustchain.org/wallet/balance", max_retries=3)
        
        self.assertIsNone(data)
        self.assertIsNotNone(error)
        self.assertIn("Network unreachable", error)

    @patch('requests.get')
    def test_fetch_with_retry_timeout(self, mock_get):
        """Test timeout handling."""
        mock_get.side_effect = Timeout("Request timeout")
        
        data, error = self.wallet._fetch_with_retry("https://rustchain.org/wallet/balance", max_retries=1)
        
        self.assertIsNone(data)
        self.assertIsNotNone(error)
        self.assertIn("timeout", error.lower())

    @patch('requests.get')
    def test_fetch_with_retry_http_error(self, mock_get):
        """Test HTTP error handling (e.g., 404, 500)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = HTTPError()
        http_error.response = mock_response
        mock_get.side_effect = http_error
        
        data, error = self.wallet._fetch_with_retry("https://rustchain.org/wallet/balance")
        
        self.assertIsNone(data)
        self.assertIsNotNone(error)
        self.assertIn("API error", error)
        self.assertIn("404", error)

    @patch('requests.post')
    def test_fetch_with_retry_post_method(self, mock_post):
        """Test POST request with retry."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        post_data = {"from": "RTC123", "to": "RTC456", "amount": 10.0}
        data, error = self.wallet._fetch_with_retry(
            "https://rustchain.org/wallet/transfer",
            method="POST",
            data=post_data
        )
        
        self.assertIsNotNone(data)
        self.assertIsNone(error)
        self.assertTrue(data["ok"])
        mock_post.assert_called_once()

    @patch('requests.get')
    @patch('time.sleep')
    def test_fetch_with_retry_exponential_backoff(self, mock_sleep, mock_get):
        """Test exponential backoff between retries."""
        mock_get.side_effect = ConnectionError("Connection failed")
        self.wallet._check_network_connectivity.return_value = (False, "Network unreachable")
        
        # Use custom initial delay for testing
        data, error = self.wallet._fetch_with_retry(
            "https://rustchain.org/wallet/balance",
            max_retries=3
        )
        
        # Should have called sleep twice (between 3 attempts)
        self.assertEqual(mock_sleep.call_count, 2)
        
        # Verify exponential backoff (delays should increase)
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertGreater(delays[1], delays[0])


if __name__ == "__main__":
    unittest.main()
