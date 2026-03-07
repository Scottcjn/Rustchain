"""
Tests for wallet network error handling.

Tests verify that:
1. Network errors are properly classified (unreachable vs timeout vs API error)
2. Retry logic works with exponential backoff
3. User-facing diagnostics are clear and actionable
"""

import pytest
import socket
from unittest.mock import patch, MagicMock
from typing import Tuple, Optional, Dict, Any

# Import the wallet module functions
import sys
from pathlib import Path
wallet_dir = Path(__file__).parent.parent
sys.path.insert(0, str(wallet_dir))


class TestNetworkConnectivity:
    """Tests for _check_network_connectivity function."""

    def test_successful_connection(self):
        """Test when network is reachable."""
        from coinbase_wallet import _check_network_connectivity
        
        with patch('socket.gethostbyname', return_value='127.0.0.1'):
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 0
                mock_socket.return_value = mock_sock
                
                is_reachable, error = _check_network_connectivity("https://example.com")
                
                assert is_reachable is True
                assert error == ""

    def test_dns_resolution_failure(self):
        """Test when DNS resolution fails."""
        from coinbase_wallet import _check_network_connectivity
        
        with patch('socket.gethostbyname', side_effect=socket.gaierror("Name or service not known")):
            is_reachable, error = _check_network_connectivity("https://nonexistent.invalid")
            
            assert is_reachable is False
            assert "DNS resolution failed" in error

    def test_connection_refused(self):
        """Test when TCP connection fails."""
        from coinbase_wallet import _check_network_connectivity
        
        with patch('socket.gethostbyname', return_value='127.0.0.1'):
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 111  # Connection refused
                mock_socket.return_value = mock_sock
                
                is_reachable, error = _check_network_connectivity("https://localhost:9999")
                
                assert is_reachable is False
                assert "Cannot connect" in error


class TestFetchWithRetry:
    """Tests for _fetch_with_retry function."""

    def test_successful_fetch(self):
        """Test successful JSON fetch."""
        from coinbase_wallet import _fetch_with_retry
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"balance": 100.0}
        mock_response.raise_for_status.return_value = None
        
        with patch('requests.get', return_value=mock_response):
            data, error = _fetch_with_retry("https://example.com/api")
            
            assert error is None
            assert data == {"balance": 100.0}

    def test_connection_error_with_network_unreachable(self):
        """Test connection error when network is truly unreachable."""
        from coinbase_wallet import _fetch_with_retry
        from requests.exceptions import ConnectionError
        
        # Use proper ConnectionError exception type
        with patch('requests.get', side_effect=ConnectionError("Connection refused")):
            with patch('coinbase_wallet._check_network_connectivity', 
                      return_value=(False, "DNS resolution failed")):
                data, error = _fetch_with_retry("https://example.com/api", max_retries=1)
                
                assert data is None
                assert "Network unreachable" in error

    def test_transient_error_with_retry_success(self):
        """Test that transient errors are retried and eventually succeed."""
        from coinbase_wallet import _fetch_with_retry
        
        call_count = [0]
        
        def mock_get(url, timeout, verify):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Transient error")
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"success": True}
            mock_resp.raise_for_status.return_value = None
            return mock_resp
        
        with patch('requests.get', side_effect=mock_get):
            with patch('coinbase_wallet._check_network_connectivity', 
                      return_value=(True, "")):
                data, error = _fetch_with_retry("https://example.com/api", max_retries=3)
                
                assert error is None
                assert data == {"success": True}
                assert call_count[0] == 3  # Failed twice, succeeded on third

    def test_timeout_after_max_retries(self):
        """Test timeout error after max retries."""
        from coinbase_wallet import _fetch_with_retry
        from requests.exceptions import Timeout
        
        with patch('requests.get', side_effect=Timeout("Request timed out")):
            data, error = _fetch_with_retry("https://example.com/api", max_retries=2, timeout=5)
            
            assert data is None
            assert "timeout" in error.lower()

    def test_http_error_classification(self):
        """Test HTTP error is properly classified."""
        from coinbase_wallet import _fetch_with_retry
        from requests.exceptions import HTTPError
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = HTTPError(response=mock_response)
        
        with patch('requests.get', side_effect=http_error):
            data, error = _fetch_with_retry("https://example.com/api", max_retries=1)
            
            assert data is None
            assert "API error" in error
            assert "404" in error


class TestGetWalletBalance:
    """Tests for _get_wallet_balance_from_node function."""

    def test_successful_balance_fetch(self):
        """Test successful balance fetch."""
        from coinbase_wallet import _get_wallet_balance_from_node
        
        with patch('coinbase_wallet._fetch_with_retry', 
                  return_value=({"balance": 42.5}, None)):
            balance, error = _get_wallet_balance_from_node("0x1234567890")
            
            assert error is None
            assert balance == 42.5

    def test_balance_with_alternative_field(self):
        """Test balance extraction from alternative field names."""
        from coinbase_wallet import _get_wallet_balance_from_node
        
        # Test amount_rtc field
        with patch('coinbase_wallet._fetch_with_retry', 
                  return_value=({"amount_rtc": 100.0}, None)):
            balance, error = _get_wallet_balance_from_node("0x1234567890")
            assert balance == 100.0
        
        # Test amount field
        with patch('coinbase_wallet._fetch_with_retry', 
                  return_value=({"amount": 50.0}, None)):
            balance, error = _get_wallet_balance_from_node("0x1234567890")
            assert balance == 50.0

    def test_balance_fetch_failure(self):
        """Test balance fetch failure propagates error."""
        from coinbase_wallet import _get_wallet_balance_from_node
        
        with patch('coinbase_wallet._fetch_with_retry', 
                  return_value=(None, "Network unreachable")):
            balance, error = _get_wallet_balance_from_node("0x1234567890")
            
            assert balance is None
            assert error == "Network unreachable"

    def test_invalid_balance_format(self):
        """Test handling of invalid balance format."""
        from coinbase_wallet import _get_wallet_balance_from_node
        
        with patch('coinbase_wallet._fetch_with_retry', 
                  return_value=({"balance": "not_a_number"}, None)):
            balance, error = _get_wallet_balance_from_node("0x1234567890")
            
            assert balance is None
            assert "Invalid balance format" in error


class TestCoinbaseShow:
    """Tests for coinbase_show function."""

    def test_show_with_no_wallet(self):
        """Test show when no wallet exists."""
        from coinbase_wallet import coinbase_show
        import io
        from contextlib import redirect_stdout
        
        with patch('coinbase_wallet._load_coinbase_wallet', return_value=None):
            f = io.StringIO()
            with redirect_stdout(f):
                coinbase_show(MagicMock())
            
            output = f.getvalue()
            assert "No Coinbase wallet found" in output

    def test_show_with_wallet_and_balance(self):
        """Test show with wallet and successful balance fetch."""
        from coinbase_wallet import coinbase_show
        import io
        from contextlib import redirect_stdout
        
        mock_wallet = {
            "address": "0x1234567890abcdef",
            "network": "Base",
            "created": "2024-01-01T00:00:00Z",
            "method": "agentkit"
        }
        
        with patch('coinbase_wallet._load_coinbase_wallet', return_value=mock_wallet):
            with patch('coinbase_wallet._get_wallet_balance_from_node', 
                      return_value=(100.5, None)):
                f = io.StringIO()
                with redirect_stdout(f):
                    coinbase_show(MagicMock())
                
                output = f.getvalue()
                assert "Coinbase Base Wallet" in output
                assert "0x1234567890abcdef" in output
                assert "100.50000000" in output

    def test_show_with_wallet_but_network_error(self):
        """Test show with wallet but network error."""
        from coinbase_wallet import coinbase_show
        import io
        from contextlib import redirect_stdout
        
        mock_wallet = {
            "address": "0x1234567890abcdef",
            "network": "Base",
        }
        
        with patch('coinbase_wallet._load_coinbase_wallet', return_value=mock_wallet):
            with patch('coinbase_wallet._get_wallet_balance_from_node', 
                      return_value=(None, "Network unreachable")):
                with patch('coinbase_wallet._check_network_connectivity', 
                          return_value=(False, "DNS failed")):
                    f = io.StringIO()
                    with redirect_stdout(f):
                        coinbase_show(MagicMock())
                    
                    output = f.getvalue()
                    assert "Coinbase Base Wallet" in output
                    assert "Unable to fetch" in output
                    assert "Network unreachable" in output
                    assert "Troubleshooting" in output


class TestRetryBackoff:
    """Tests for exponential backoff in retry logic."""

    def test_exponential_backoff_timing(self):
        """Test that retry delays follow exponential backoff."""
        from coinbase_wallet import (
            _fetch_with_retry, 
            INITIAL_RETRY_DELAY, 
            MAX_RETRY_DELAY
        )
        
        call_times = []
        
        def mock_get(url, timeout, verify):
            call_times.append(__import__('time').time())
            raise Exception("Always fails")
        
        with patch('requests.get', side_effect=mock_get):
            with patch('coinbase_wallet._check_network_connectivity', 
                      return_value=(True, "")):
                # Use very short delays for testing
                with patch('coinbase_wallet.INITIAL_RETRY_DELAY', 0.01):
                    with patch('coinbase_wallet.MAX_RETRY_DELAY', 0.1):
                        _fetch_with_retry("https://example.com", max_retries=3)
        
        # Verify we have 3 call times
        assert len(call_times) == 3
        
        # Verify delays increase (approximately exponential)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        
        # Second delay should be roughly 2x the first (with some tolerance)
        assert delay2 > delay1 * 1.5  # Allow for timing variance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
