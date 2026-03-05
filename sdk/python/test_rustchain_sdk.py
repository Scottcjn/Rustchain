"""
RustChain SDK Tests
"""

import pytest
from rustchain_sdk import RustChainClient, APIError


# Test configuration
TEST_NODE_URL = "https://50.28.86.131"


class TestRustChainClient:
    """Test cases for RustChain SDK"""
    
    @pytest.fixture
    def client(self):
        """Create client for testing"""
        return RustChainClient(TEST_NODE_URL)
    
    def test_health(self, client):
        """Test health endpoint"""
        health = client.health()
        assert health is not None
        assert "ok" in health
        assert "version" in health
        assert health["ok"] is True
    
    def test_get_miners(self, client):
        """Test get_miners endpoint"""
        miners = client.get_miners()
        assert miners is not None
        assert isinstance(miners, list)
        # Should have at least one miner
        assert len(miners) > 0
    
    def test_get_epoch(self, client):
        """Test get_epoch endpoint"""
        epoch = client.get_epoch()
        assert epoch is not None
        assert "epoch" in epoch
        assert "blocks_per_epoch" in epoch
        assert "epoch_pot" in epoch
    
    def test_check_eligibility(self, client):
        """Test check_eligibility endpoint"""
        eligibility = client.check_eligibility("test-miner")
        assert eligibility is not None
        assert "eligible" in eligibility
        assert "slot" in eligibility
    
    def test_invalid_endpoint(self, client):
        """Test invalid endpoint handling"""
        with pytest.raises(APIError):
            client._get("/invalid/endpoint")
    
    def test_client_configuration(self):
        """Test client configuration"""
        client = RustChainClient(
            base_url=TEST_NODE_URL,
            verify_ssl=False,
            timeout=30,
            retry_count=3
        )
        assert client.base_url == TEST_NODE_URL
        assert client.verify_ssl is False
        assert client.timeout == 30
        assert client.retry_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
