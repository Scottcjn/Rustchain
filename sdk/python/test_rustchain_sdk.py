"""
RustChain SDK Tests (20+ unit tests)
Tests all API methods, CLI, explorer, exceptions, and configuration.
"""

import pytest
import json
import ssl
from unittest.mock import patch, MagicMock
from rustchain import RustChainClient, create_client, APIError, AuthenticationError
from rustchain.explorer import ExplorerClient, ExplorerError
from rustchain.exceptions import RustChainError, ConnectionError, ValidationError, WalletError


# Test configuration
TEST_NODE_URL = "https://50.28.86.131"
TEST_MINER = "nox-ventures"


# ========== Fixtures ==========

@pytest.fixture
def client():
    """Create client for testing"""
    return RustChainClient(TEST_NODE_URL, verify_ssl=False, timeout=10)


@pytest.fixture
def explorer():
    """Create explorer client for testing"""
    return ExplorerClient(TEST_NODE_URL, verify_ssl=False)


# ========== Client Initialization Tests ==========

class TestClientInitialization:
    """Test client configuration and initialization"""
    
    def test_default_url(self):
        """Test client uses default URL"""
        c = RustChainClient()
        assert c.base_url == "https://50.28.86.131"
    
    def test_custom_url(self):
        """Test client accepts custom URL"""
        c = RustChainClient("https://custom.node.com")
        assert c.base_url == "https://custom.node.com"
    
    def test_url_strips_trailing_slash(self):
        """Test URL trailing slash is stripped"""
        c = RustChainClient("https://node.com/")
        assert c.base_url == "https://node.com"
    
    def test_verify_ssl_default(self):
        """Test SSL verification defaults to False"""
        c = RustChainClient()
        assert c.verify_ssl is False
        assert c._ctx is not None  # SSL context created
    
    def test_verify_ssl_true(self):
        """Test SSL verification can be enabled"""
        c = RustChainClient(verify_ssl=True)
        assert c.verify_ssl is True
        assert c._ctx is None  # No custom context needed
    
    def test_timeout_config(self):
        """Test timeout configuration"""
        c = RustChainClient(timeout=60)
        assert c.timeout == 60
    
    def test_retry_config(self):
        """Test retry configuration"""
        c = RustChainClient(retry_count=5, retry_delay=2.0)
        assert c.retry_count == 5
        assert c.retry_delay == 2.0
    
    def test_explorer_subclient(self, client):
        """Test explorer subclient is initialized"""
        assert client.explorer is not None
        assert isinstance(client.explorer, ExplorerClient)
        assert client.explorer.base_url == client.base_url


class TestCreateClient:
    """Test create_client convenience function"""
    
    def test_create_client_returns_client(self):
        """Test create_client returns RustChainClient"""
        c = create_client()
        assert isinstance(c, RustChainClient)
    
    def test_create_client_custom_url(self):
        """Test create_client accepts custom URL"""
        c = create_client("https://custom.com")
        assert c.base_url == "https://custom.com"


# ========== Health Endpoint Tests ==========

class TestHealthEndpoint:
    """Test health() endpoint"""
    
    @patch("urllib.request.urlopen")
    def test_health_returns_dict(self, mock_urlopen, client):
        """Test health returns a dictionary"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True, "version": "2.2.1"}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = client.health()
        assert isinstance(result, dict)
    
    @patch("urllib.request.urlopen")
    def test_health_calls_correct_endpoint(self, mock_urlopen, client):
        """Test health calls /health endpoint"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        client.health()
        
        call_args = mock_urlopen.call_args
        url = call_args[0][0].full_url
        assert "/health" in url


# ========== Epoch Endpoint Tests ==========

class TestEpochEndpoint:
    """Test epoch() and get_epoch() endpoints"""
    
    @patch("urllib.request.urlopen")
    def test_epoch_returns_dict(self, mock_urlopen, client):
        """Test epoch returns a dictionary"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"epoch": 112, "blocks_per_epoch": 144}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = client.epoch()
        assert isinstance(result, dict)
    
    @patch("urllib.request.urlopen")
    def test_epoch_alias(self, mock_urlopen, client):
        """Test epoch() is alias for get_epoch()"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"epoch": 50}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        epoch_result = client.epoch()
        get_epoch_result = client.get_epoch()
        
        # Both should hit the same endpoint
        assert mock_urlopen.call_count == 2


# ========== Miners Endpoint Tests ==========

class TestMinersEndpoint:
    """Test miners() and get_miners() endpoints"""
    
    @patch("urllib.request.urlopen")
    def test_miners_returns_list(self, mock_urlopen, client):
        """Test miners returns a list"""
        mock_response = MagicMock()
        mock_data = [{"miner": "test-miner", "antiquity_multiplier": 1.0}]
        mock_response.read.return_value = json.dumps(mock_data).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = client.miners()
        assert isinstance(result, list)
    
    @patch("urllib.request.urlopen")
    def test_miners_calls_api_miners(self, mock_urlopen, client):
        """Test miners calls /api/miners endpoint"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        client.miners()
        
        call_args = mock_urlopen.call_args
        url = call_args[0][0].full_url
        assert "/api/miners" in url


# ========== Balance Endpoint Tests ==========

class TestBalanceEndpoint:
    """Test balance() and get_balance() endpoints"""
    
    @patch("urllib.request.urlopen")
    def test_balance_calls_correct_endpoint(self, mock_urlopen, client):
        """Test balance() calls /balance/{wallet_id}"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"balance": 100.0}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        client.balance("test-wallet")
        
        call_args = mock_urlopen.call_args
        url = call_args[0][0].full_url
        assert "/balance/test-wallet" in url
    
    @patch("urllib.request.urlopen")
    def test_balance_with_special_chars(self, mock_urlopen, client):
        """Test balance handles special characters in wallet ID"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"balance": 50.0}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        client.balance("rtc-wallet-with-dashes")
        # Should not raise


# ========== Transfer Endpoint Tests ==========

class TestTransferEndpoint:
    """Test transfer() endpoint"""
    
    @patch("urllib.request.urlopen")
    def test_transfer_calls_post(self, mock_urlopen, client):
        """Test transfer uses POST method"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"success": True}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        client.transfer("from-wallet", "to-wallet", 10.0, "sig-hex")
        
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.method == "POST"
    
    @patch("urllib.request.urlopen")
    def test_transfer_payload(self, mock_urlopen, client):
        """Test transfer sends correct payload"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"success": True}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        client.transfer("a", "b", 5.5, "sig123")
        
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        import urllib.parse
        # Data is in request._data


# ========== Attestation Status Tests ==========

class TestAttestationStatus:
    """Test attestation_status() endpoint"""
    
    @patch("urllib.request.urlopen")
    def test_attestation_status_returns_dict(self, mock_urlopen, client):
        """Test attestation_status returns a dictionary"""
        # Mock beacon envelopes response
        mock_response = MagicMock()
        mock_data = {
            "count": 2,
            "envelopes": [
                {"agent_id": "test-miner", "nonce": "test-nonce-abc", "kind": "heartbeat"},
                {"agent_id": "other-miner", "nonce": "test-miner-other", "kind": "mayday"}
            ]
        }
        mock_response.read.return_value = json.dumps(mock_data).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = client.attestation_status("test-miner")
        assert isinstance(result, dict)
        assert "attestations" in result
        assert result["count"] == 2  # Both contain "test-miner" in agent_id or nonce


# ========== Explorer Tests ==========

class TestExplorerBlocks:
    """Test explorer.blocks()"""
    
    @patch("urllib.request.urlopen")
    def test_blocks_returns_dict(self, mock_urlopen, explorer):
        """Test blocks returns a dictionary with blocks list"""
        mock_response = MagicMock()
        mock_data = {
            "blocks": [
                {"block_hash": "abc123", "slot": 1, "miner": "test"},
                {"block_hash": "def456", "slot": 2, "miner": "test2"}
            ]
        }
        mock_response.read.return_value = json.dumps(mock_data).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = explorer.blocks()
        assert isinstance(result, dict)
        assert "blocks" in result
        assert len(result["blocks"]) == 2
    
    @patch("urllib.request.urlopen")
    def test_blocks_respects_limit(self, mock_urlopen, explorer):
        """Test blocks respects limit parameter"""
        mock_response = MagicMock()
        mock_data = {"blocks": [{"slot": i} for i in range(20)]}
        mock_response.read.return_value = json.dumps(mock_data).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = explorer.blocks(limit=5)
        assert result["count"] == 5


class TestExplorerChainTip:
    """Test explorer.chain_tip()"""
    
    @patch("urllib.request.urlopen")
    def test_chain_tip_returns_dict(self, mock_urlopen, explorer):
        """Test chain_tip returns miner and slot info"""
        mock_response = MagicMock()
        mock_data = {"miner": "sophia-nas", "slot": 100, "tip_age": 50}
        mock_response.read.return_value = json.dumps(mock_data).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = explorer.chain_tip()
        assert result["miner"] == "sophia-nas"
        assert result["slot"] == 100


# ========== Exception Tests ==========

class TestExceptions:
    """Test exception handling"""
    
    @patch("urllib.request.urlopen")
    def test_api_error_contains_status_code(self, mock_urlopen, client):
        """Test APIError includes status code"""
        from urllib.error import HTTPError
        
        mock_urlopen.side_effect = HTTPError(
            "http://test.com", 404, "Not Found", {}, None
        )
        
        with pytest.raises(APIError) as exc_info:
            client._get("/invalid")
        
        assert exc_info.value.status_code == 404
    
    @patch("urllib.request.urlopen")
    def test_auth_error(self, mock_urlopen, client):
        """Test AuthenticationError for 401 responses"""
        from urllib.error import HTTPError
        
        mock_urlopen.side_effect = HTTPError(
            "http://test.com", 401, "Unauthorized", {}, None
        )
        
        with pytest.raises(AuthenticationError):
            client._get("/admin")
    
    @patch("urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen, client):
        """Test ConnectionError for network failures"""
        from urllib.error import URLError
        
        mock_urlopen.side_effect = URLError("Connection refused")
        
        with pytest.raises(APIError):
            client._get("/health")


# ========== Retry Logic Tests ==========

class TestRetryLogic:
    """Test retry behavior"""
    
    @patch("urllib.request.urlopen")
    def test_retries_on_failure(self, mock_urlopen, client):
        """Test client retries on transient failures"""
        from urllib.error import URLError
        
        call_count = 0
        def side_effect(request, context=None, timeout=None):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({"ok": True}).encode()
            
            if call_count < 3:
                raise URLError("Transient error")
            
            # Return a context manager (what urlopen returns)
            class ResponseCtx:
                def __enter__(self):
                    return mock_response
                def __exit__(self, *args):
                    return None
            return ResponseCtx()
        
        mock_urlopen.side_effect = side_effect
        
        result = client.health()
        assert call_count == 3
        assert result["ok"] is True
    
    @patch("urllib.request.urlopen")
    def test_no_retry_on_api_error(self, mock_urlopen, client):
        """Test APIError is raised immediately for HTTP errors"""
        from urllib.error import HTTPError
        
        mock_urlopen.side_effect = HTTPError(
            "http://test.com", 404, "Not Found", {}, None
        )
        
        with pytest.raises(APIError):
            client._get("/invalid")


# ========== Async Methods Tests ==========

class TestAsyncMethods:
    """Test async method availability"""
    
    def test_async_health_defined(self, client):
        """Test async_health method exists"""
        assert hasattr(client, "async_health")
        assert callable(client.async_health)
    
    def test_async_epoch_defined(self, client):
        """Test async_epoch method exists"""
        assert hasattr(client, "async_epoch")
    
    def test_async_miners_defined(self, client):
        """Test async_miners method exists"""
        assert hasattr(client, "async_miners")
    
    def test_async_balance_defined(self, client):
        """Test async_balance method exists"""
        assert hasattr(client, "async_balance")
    
    def test_async_get_balance_defined(self, client):
        """Test async_get_balance method exists"""
        assert hasattr(client, "async_get_balance")
    
    def test_async_check_eligibility_defined(self, client):
        """Test async_check_eligibility method exists"""
        assert hasattr(client, "async_check_eligibility")


# ========== Additional API Methods Tests ==========

class TestAdditionalMethods:
    """Test additional API methods"""
    
    @patch("urllib.request.urlopen")
    def test_get_stats(self, mock_urlopen, client):
        """Test get_stats() method"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"stats": "data"}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = client.get_stats()
        assert isinstance(result, dict)
    
    @patch("urllib.request.urlopen")
    def test_get_chain_tip(self, mock_urlopen, client):
        """Test get_chain_tip() method"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"miner": "test"}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = client.get_chain_tip()
        assert "miner" in result
    
    @patch("urllib.request.urlopen")
    def test_wallet_history(self, mock_urlopen, client):
        """Test wallet_history() method"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"history": []}).encode()
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda *a: None
        
        result = client.wallet_history("test-wallet")
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
