"""
Test suite for wallet balance error handling (Rustchain#7889).

Tests verify that all error paths in coinbase_show produce:
1. Clear error messages on stderr
2. Distinct non-zero exit codes (2=network, 3=invalid response)
3. No silent failures or misleading success
"""

import pytest
import sys
import json
from unittest.mock import patch, MagicMock
from io import StringIO

# Import the module under test
sys.path.insert(0, ".")
from coinbase_wallet import (
    coinbase_show,
    _fetch_with_retry,
    _get_wallet_balance_from_node,
)


class TestFetchWithRetry:
    """Test _fetch_with_retry error handling."""

    def test_network_error_returns_error_message(self):
        """Network error should return None and error message."""
        with patch("coinbase_wallet.requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            payload, error = _fetch_with_retry("http://invalid.local/api")
            assert payload is None
            assert error is not None
            assert "Network unreachable" in error or "failed" in error.lower()

    def test_http_error_returns_status_code(self):
        """HTTP error (e.g., 500) should return error with status."""
        with patch("coinbase_wallet.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
            mock_get.return_value = mock_resp

            payload, error = _fetch_with_retry("http://localhost/api")
            assert payload is None
            assert error is not None


class TestGetWalletBalance:
    """Test _get_wallet_balance_from_node error handling."""

    def test_network_error(self):
        """Network error should propagate."""
        with patch("coinbase_wallet._fetch_with_retry") as mock_fetch:
            mock_fetch.return_value = (None, "Network unreachable: DNS resolution failed")
            balance, error = _get_wallet_balance_from_node("0xtest")
            assert balance is None
            assert "Network unreachable" in error

    def test_invalid_balance_format(self):
        """Invalid balance data should produce error."""
        with patch("coinbase_wallet._fetch_with_retry") as mock_fetch:
            mock_fetch.return_value = ({"wrong_field": "value"}, None)
            balance, error = _get_wallet_balance_from_node("0xtest")
            assert balance is None
            assert "Invalid balance format" in error

    def test_balance_not_float_convertible(self):
        """Non-numeric balance should produce error."""
        with patch("coinbase_wallet._fetch_with_retry") as mock_fetch:
            mock_fetch.return_value = ({"balance": "not_a_number"}, None)
            balance, error = _get_wallet_balance_from_node("0xtest")
            assert balance is None
            assert "Invalid balance format" in error

    def test_successful_balance_fetch(self):
        """Successful balance fetch should return float."""
        with patch("coinbase_wallet._fetch_with_retry") as mock_fetch:
            mock_fetch.return_value = ({"balance": 42.5}, None)
            balance, error = _get_wallet_balance_from_node("0xtest")
            assert balance == 42.5
            assert error is None

    def test_alternative_field_names(self):
        """Alternative field names (amount_rtc, amount) should work."""
        with patch("coinbase_wallet._fetch_with_retry") as mock_fetch:
            mock_fetch.return_value = ({"amount_rtc": 99.99}, None)
            balance, error = _get_wallet_balance_from_node("0xtest")
            assert balance == 99.99
            assert error is None


class TestCoinbaseShowExitCodes:
    """Test that coinbase_show exits with correct codes."""

    def test_no_wallet_found_exits_1(self):
        """No wallet file should exit(1)."""
        mock_args = MagicMock()
        with patch("coinbase_wallet._load_coinbase_wallet") as mock_load:
            mock_load.return_value = None
            with pytest.raises(SystemExit) as exc_info:
                coinbase_show(mock_args)
            assert exc_info.value.code == 1

    def test_network_error_exits_2(self):
        """Network error should exit(2)."""
        mock_args = MagicMock()
        mock_wallet = {"address": "0xtest"}
        with patch("coinbase_wallet._load_coinbase_wallet") as mock_load:
            mock_load.return_value = mock_wallet
            with patch("coinbase_wallet._get_wallet_balance_from_node") as mock_balance:
                mock_balance.return_value = (None, "Network unreachable: DNS resolution failed for rustchain.org")
                with pytest.raises(SystemExit) as exc_info:
                    coinbase_show(mock_args)
                assert exc_info.value.code == 2

    def test_invalid_response_exits_3(self):
        """Invalid balance response should exit(3)."""
        mock_args = MagicMock()
        mock_wallet = {"address": "0xtest"}
        with patch("coinbase_wallet._load_coinbase_wallet") as mock_load:
            mock_load.return_value = mock_wallet
            with patch("coinbase_wallet._get_wallet_balance_from_node") as mock_balance:
                mock_balance.return_value = (None, "Invalid balance format")
                with pytest.raises(SystemExit) as exc_info:
                    coinbase_show(mock_args)
                assert exc_info.value.code == 3

    def test_success_exits_0(self):
        """Successful balance fetch should exit(0)."""
        mock_args = MagicMock()
        mock_wallet = {"address": "0xtest"}
        with patch("coinbase_wallet._load_coinbase_wallet") as mock_load:
            mock_load.return_value = mock_wallet
            with patch("coinbase_wallet._get_wallet_balance_from_node") as mock_balance:
                mock_balance.return_value = (123.456, None)
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc_info:
                        coinbase_show(mock_args)
                    assert exc_info.value.code == 0


class TestErrorMessagesOnStderr:
    """Test that errors go to stderr, not stdout."""

    def test_network_error_to_stderr(self):
        """Network errors should print to stderr."""
        mock_args = MagicMock()
        mock_wallet = {"address": "0xtest"}
        with patch("coinbase_wallet._load_coinbase_wallet") as mock_load:
            mock_load.return_value = mock_wallet
            with patch("coinbase_wallet._get_wallet_balance_from_node") as mock_balance:
                mock_balance.return_value = (None, "Network unreachable: Connection refused")
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with pytest.raises(SystemExit):
                        coinbase_show(mock_args)
                    stderr_output = mock_stderr.getvalue()
                    assert "Error" in stderr_output or "unreachable" in stderr_output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
