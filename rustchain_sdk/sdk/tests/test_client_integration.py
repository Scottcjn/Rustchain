"""
Integration tests for RustChain Client (against live node)

These tests require network access to https://rustchain.org
"""

import pytest
from rustchain import RustChainClient
from rustchain.exceptions import ConnectionError


# Test against live RustChain node
LIVE_NODE_URL = "https://rustchain.org"


@pytest.mark.integration
class TestLiveAPI:
    """Test against live RustChain API"""

    @pytest.fixture
    def client(self):
        """Create client for live testing"""
        client = RustChainClient(LIVE_NODE_URL, verify_ssl=False, timeout=10)
        yield client
        client.close()

    def test_health_live(self, client):
        """Test health endpoint against live node"""
        health = client.health()
        assert health is not None
        assert isinstance(health, dict)
        assert "ok" in health
        assert "uptime_s" in health
        assert "version" in health
        assert health["ok"] is True

    def test_epoch_live(self, client):
        """Test epoch endpoint against live node"""
        epoch = client.epoch()
        assert epoch is not None
        assert isinstance(epoch, dict)
        assert "epoch" in epoch
        assert "slot" in epoch
        assert "blocks_per_epoch" in epoch
        assert "enrolled_miners" in epoch
        assert epoch["epoch"] >= 0
        assert epoch["slot"] >= 0
        assert epoch["blocks_per_epoch"] > 0

    def test_miners_live(self, client):
        """Test miners endpoint against live node"""
        miners = client.miners()
        assert miners is not None
        assert isinstance(miners, list)
        assert len(miners) >= 0

        if len(miners) > 0:
            # Check first miner structure
            miner = miners[0]
            assert "miner" in miner
            assert "antiquity_multiplier" in miner
            assert "hardware_type" in miner
            assert miner["antiquity_multiplier"] >= 1.0

    @pytest.mark.skipif(True, reason="Requires valid wallet address")
    def test_balance_live(self, client):
        """Test balance endpoint against live node"""
        # This test requires a valid wallet address
        # Skip by default, uncomment with real wallet to test
        balance = client.balance("valid_wallet_address")
        assert balance is not None
        assert isinstance(balance, dict)
        assert "balance" in balance
        assert balance["balance"] >= 0

    def test_connection_error_invalid_url(self):
        """Test connection error with invalid URL"""
        with pytest.raises(ConnectionError):
            client = RustChainClient("https://invalid-url-that-does-not-exist.com")
            client.health()
            client.close()

    def test_connection_error_timeout(self):
        """Test connection error with timeout"""
        with pytest.raises(ConnectionError):
            client = RustChainClient("https://rustchain.org", timeout=0.001)
            client.health()
            client.close()


@pytest.mark.integration
class TestLiveAPIConvenience:
    """Convenience tests for live API"""

    @pytest.fixture
    def client(self):
        """Create client for live testing"""
        client = RustChainClient(LIVE_NODE_URL, verify_ssl=False, timeout=10)
        yield client
        client.close()

    def test_get_network_stats(self, client):
        """Test getting comprehensive network stats"""
        health = client.health()
        epoch = client.epoch()
        miners = client.miners()

        assert health["ok"] is True
        assert epoch["epoch"] >= 0
        assert isinstance(miners, list)

        # Print stats for manual verification
        print(f"\nNetwork Stats:")
        print(f"  Version: {health['version']}")
        print(f"  Uptime: {health['uptime_s']}s")
        print(f"  Current Epoch: {epoch['epoch']}")
        print(f"  Current Slot: {epoch['slot']}")
        print(f"  Enrolled Miners: {epoch['enrolled_miners']}")
        print(f"  Total Miners: {len(miners)}")
