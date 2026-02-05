"""Tests for RustChain SDK."""
import pytest
from rustchain_sdk import RustChainClient, Miner, EpochInfo, Balance


# Integration tests (require network access)
class TestRustChainClientIntegration:
    """Integration tests against live RustChain node."""
    
    @pytest.fixture
    def client(self):
        """Create a client for testing."""
        return RustChainClient()
    
    def test_health(self, client):
        """Test health endpoint."""
        health = client.health()
        assert "ok" in health
        assert "version" in health
        assert health["ok"] is True
    
    def test_get_epoch(self, client):
        """Test epoch endpoint."""
        epoch = client.get_epoch()
        assert isinstance(epoch, EpochInfo)
        assert epoch.epoch >= 0
        assert epoch.slot >= 0
        assert epoch.blocks_per_epoch > 0
        assert epoch.epoch_pot > 0
    
    def test_get_miners(self, client):
        """Test miners endpoint."""
        miners = client.get_miners()
        assert isinstance(miners, list)
        # Network should have at least some miners
        if miners:
            miner = miners[0]
            assert isinstance(miner, Miner)
            assert miner.miner_id
            assert miner.antiquity_multiplier >= 1.0
    
    def test_get_balance_nonexistent(self, client):
        """Test balance for non-existent wallet."""
        balance = client.get_balance("nonexistent-wallet-12345")
        assert isinstance(balance, Balance)
        assert balance.amount_rtc == 0.0


class TestRustChainClientUnit:
    """Unit tests (no network required)."""
    
    def test_client_init_defaults(self):
        """Test client initialization with defaults."""
        client = RustChainClient()
        assert client.base_url == "https://50.28.86.131"
        assert client.verify_ssl is False
        assert client.timeout == 30.0
        assert client.max_retries == 3
    
    def test_client_init_custom(self):
        """Test client initialization with custom values."""
        client = RustChainClient(
            base_url="https://custom.node:8080/",
            verify_ssl=True,
            timeout=60.0,
            max_retries=5,
        )
        assert client.base_url == "https://custom.node:8080"  # Trailing slash stripped
        assert client.verify_ssl is True
        assert client.timeout == 60.0
        assert client.max_retries == 5
    
    def test_context_manager(self):
        """Test client as context manager."""
        with RustChainClient() as client:
            assert client is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
