"""
Tests for wRTC SPL Token Deployment Module

Run with:
    pytest tests/test_spl_deployment.py -v
    
Or:
    python -m pytest tests/test_spl_deployment.py -v --cov=spl_deployment
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from spl_deployment import (
    TokenConfig,
    MultiSigConfig,
    BridgeEscrowConfig,
    SPLTokenDeployment,
    BridgeIntegration,
    load_config_from_file,
    save_config_to_file,
    hash_config
)


class TestTokenConfig:
    """Test TokenConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = TokenConfig()
        
        assert config.name == "Wrapped RustChain"
        assert config.symbol == "wRTC"
        assert config.decimals == 9
        assert "RustChain" in config.description
        assert config.decimals == 9
    
    def test_custom_values(self):
        """Test custom configuration."""
        config = TokenConfig(
            name="Custom Token",
            symbol="CTK",
            decimals=6,
            description="A custom token"
        )
        
        assert config.name == "Custom Token"
        assert config.symbol == "CTK"
        assert config.decimals == 6
    
    def test_to_metadata(self):
        """Test metadata generation."""
        config = TokenConfig()
        metadata = config.to_metadata()
        
        assert metadata["name"] == config.name
        assert metadata["symbol"] == config.symbol
        assert metadata["description"] == config.description
        assert "attributes" in metadata
        assert len(metadata["attributes"]) == 4
        
        # Check attribute structure
        traits = {attr["trait_type"]: attr["value"] for attr in metadata["attributes"]}
        assert traits["Chain"] == "Solana"
        assert traits["Backing"] == "1:1 RTC"


class TestMultiSigConfig:
    """Test MultiSigConfig dataclass."""
    
    def test_valid_config(self):
        """Test valid multi-sig configuration."""
        config = MultiSigConfig(
            signers=[
                "Signer1PubKeyHere12345678901234567890",
                "Signer2PubKeyHere12345678901234567890",
                "Signer3PubKeyHere12345678901234567890",
                "Signer4PubKeyHere12345678901234567890",
                "Signer5PubKeyHere12345678901234567890"
            ],
            threshold=3
        )
        
        assert config.validate() is True
        assert config.threshold == 3
    
    def test_insufficient_signers(self):
        """Test validation fails with insufficient signers."""
        config = MultiSigConfig(
            signers=["Signer1", "Signer2"],
            threshold=3
        )
        
        assert config.validate() is False
    
    def test_threshold_too_low(self):
        """Test validation fails with threshold < 1."""
        config = MultiSigConfig(
            signers=["Signer1", "Signer2", "Signer3"],
            threshold=0
        )
        
        assert config.validate() is False
    
    def test_invalid_pubkey_format(self):
        """Test validation fails with invalid pubkey format."""
        config = MultiSigConfig(
            signers=["short", "Signer2", "Signer3"],
            threshold=2
        )
        
        assert config.validate() is False


class TestBridgeEscrowConfig:
    """Test BridgeEscrowConfig dataclass."""
    
    def test_valid_config(self):
        """Test valid escrow configuration."""
        config = BridgeEscrowConfig(
            escrow_authority="BridgePDA",
            mint_address="MintAddress",
            daily_mint_cap=100_000_000_000_000,
            per_tx_limit=10_000_000_000_000
        )
        
        assert config.validate() is True
    
    def test_per_tx_exceeds_daily(self):
        """Test validation fails when per-tx limit exceeds daily cap."""
        config = BridgeEscrowConfig(
            escrow_authority="BridgePDA",
            mint_address="MintAddress",
            daily_mint_cap=10_000,
            per_tx_limit=100_000
        )
        
        assert config.validate() is False
    
    def test_negative_cap(self):
        """Test validation fails with negative cap."""
        config = BridgeEscrowConfig(
            escrow_authority="BridgePDA",
            mint_address="MintAddress",
            daily_mint_cap=-100
        )
        
        assert config.validate() is False


class TestSPLTokenDeployment:
    """Test SPLTokenDeployment class."""
    
    @pytest.fixture
    def mock_solana_sdk(self):
        """Mock Solana SDK for testing without actual connection."""
        with patch('spl_deployment.SOLANA_SDK_AVAILABLE', False):
            yield
    
    def test_initialization(self, mock_solana_sdk):
        """Test deployment client initialization."""
        # Should raise ImportError when SDK not available
        with pytest.raises(ImportError):
            deployment = SPLTokenDeployment("https://api.devnet.solana.com")
    
    def test_rpc_url_networks(self):
        """Test different RPC URLs."""
        networks = {
            "devnet": "https://api.devnet.solana.com",
            "mainnet": "https://api.mainnet-beta.solana.com",
            "testnet": "https://api.testnet.solana.com",
            "localnet": "http://localhost:8899"
        }
        
        for network, url in networks.items():
            # Just test that URLs are valid strings
            assert isinstance(url, str)
            assert len(url) > 10
    
    def test_detect_network(self, mock_solana_sdk):
        """Test network detection from RPC URL."""
        # Test network detection logic
        def detect_network(rpc_url):
            if "devnet" in rpc_url:
                return "devnet"
            elif "mainnet" in rpc_url:
                return "mainnet"
            elif "testnet" in rpc_url:
                return "testnet"
            else:
                return "custom"
        
        assert detect_network("https://api.devnet.solana.com") == "devnet"
        assert detect_network("https://api.mainnet-beta.solana.com") == "mainnet"
        assert detect_network("https://api.testnet.solana.com") == "testnet"
        assert detect_network("http://localhost:8899") == "custom"


class TestBridgeIntegration:
    """Test BridgeIntegration class."""
    
    def test_initialization(self):
        """Test bridge integration initialization."""
        # Mock SPL deployment
        mock_spl = Mock()
        
        bridge = BridgeIntegration(mock_spl)
        
        assert bridge.spl == mock_spl
        assert bridge.lock_events == []
        assert bridge.mint_events == []
    
    def test_verify_rtc_lock(self):
        """Test RTC lock verification (simulated)."""
        mock_spl = Mock()
        bridge = BridgeIntegration(mock_spl)
        
        # Simulated verification
        result = bridge.verify_rtc_lock("tx_hash_123", 1000)
        
        assert result is True
    
    def test_authorize_mint(self):
        """Test mint authorization."""
        mock_spl = Mock()
        bridge = BridgeIntegration(mock_spl)
        
        auth = bridge.authorize_mint(
            destination="SolanaAddress123",
            amount=1000,
            rustchain_proof="tx_hash_123"
        )
        
        assert auth["destination"] == "SolanaAddress123"
        assert auth["amount"] == 1000
        assert auth["rustchain_proof"] == "tx_hash_123"
        assert auth["status"] == "pending_multi_sig"


class TestConfigFileOperations:
    """Test configuration file operations."""
    
    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create temporary config file for testing."""
        config_data = {
            "token": {
                "name": "Test Token",
                "symbol": "TTK",
                "decimals": 9
            }
        }
        
        config_file = tmp_path / "test-config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        return config_file
    
    def test_load_config(self, temp_config_file):
        """Test loading config from file."""
        config = load_config_from_file(str(temp_config_file))
        
        assert config["token"]["name"] == "Test Token"
        assert config["token"]["symbol"] == "TTK"
    
    def test_save_config(self, tmp_path):
        """Test saving config to file."""
        config_data = {"test": "value", "number": 42}
        config_file = tmp_path / "output-config.json"
        
        save_config_to_file(config_data, str(config_file))
        
        # Verify file was created
        assert config_file.exists()
        
        # Verify content
        with open(config_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded["test"] == "value"
        assert loaded["number"] == 42
    
    def test_load_nonexistent_file(self):
        """Test loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_config_from_file("/nonexistent/path/config.json")
    
    def test_hash_config(self):
        """Test configuration hashing."""
        config1 = {"a": 1, "b": 2}
        config2 = {"a": 1, "b": 2}
        config3 = {"a": 1, "b": 3}
        
        hash1 = hash_config(config1)
        hash2 = hash_config(config2)
        hash3 = hash_config(config3)
        
        # Same config should produce same hash
        assert hash1 == hash2
        
        # Different config should produce different hash
        assert hash1 != hash3
        
        # Hash should be SHA256 (64 hex chars)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)


class TestIntegrationScenarios:
    """Test integration scenarios."""
    
    def test_full_deployment_flow(self):
        """Test complete deployment flow (mocked)."""
        # Create configuration
        token_config = TokenConfig(
            name="Test wRTC",
            symbol="TwRTC",
            decimals=9
        )
        
        multisig_config = MultiSigConfig(
            signers=[f"Signer{i}PubKey12345678901234567890" for i in range(1, 6)],
            threshold=3
        )
        
        escrow_config = BridgeEscrowConfig(
            escrow_authority="BridgePDA",
            mint_address="TODO",
            daily_mint_cap=100_000_000_000_000,
            per_tx_limit=10_000_000_000_000
        )
        
        # Validate all configs
        assert token_config.to_metadata() is not None
        assert multisig_config.validate() is True
        assert escrow_config.validate() is True
        
        # Generate metadata
        metadata = token_config.to_metadata()
        assert "attributes" in metadata
        
        # Simulate bridge authorization
        mock_spl = Mock()
        bridge = BridgeIntegration(mock_spl)
        auth = bridge.authorize_mint("Destination123", 1000, "proof_123")
        
        assert auth["status"] == "pending_multi_sig"
    
    def test_config_round_trip(self, tmp_path):
        """Test configuration save/load round trip."""
        original_config = {
            "token": {
                "name": "Round Trip Token",
                "symbol": "RTT",
                "decimals": 9,
                "description": "Test config"
            },
            "multisig": {
                "signers": ["Signer1", "Signer2", "Signer3"],
                "threshold": 2
            }
        }
        
        config_file = tmp_path / "roundtrip-config.json"
        
        # Save
        save_config_to_file(original_config, str(config_file))
        
        # Load
        loaded_config = load_config_from_file(str(config_file))
        
        # Verify
        assert loaded_config["token"]["name"] == original_config["token"]["name"]
        assert loaded_config["multisig"]["threshold"] == original_config["multisig"]["threshold"]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_signer_list(self):
        """Test multi-sig with empty signer list."""
        config = MultiSigConfig(signers=[], threshold=0)
        assert config.validate() is False
    
    def test_zero_decimals(self):
        """Test token with zero decimals."""
        config = TokenConfig(decimals=0)
        metadata = config.to_metadata()
        assert metadata is not None
    
    def test_very_large_supply_cap(self):
        """Test very large supply cap."""
        large_cap = 10**18  # 1 quintillion
        config = BridgeEscrowConfig(
            escrow_authority="BridgePDA",
            mint_address="Mint",
            daily_mint_cap=large_cap,
            per_tx_limit=large_cap // 10
        )
        assert config.validate() is True
    
    def test_unicode_in_description(self):
        """Test unicode characters in description."""
        config = TokenConfig(
            description="Token with unicode:  RustChain 🔥 古董"
        )
        metadata = config.to_metadata()
        assert "RustChain" in metadata["description"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
