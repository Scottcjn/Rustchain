"""
Pytest configuration and fixtures for SPL deployment tests.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_token_config():
    """Sample token configuration for testing."""
    from spl_deployment import TokenConfig
    
    return TokenConfig(
        name="Test wRTC",
        symbol="TwRTC",
        decimals=9,
        description="Test wrapped RustChain token"
    )


@pytest.fixture
def sample_multisig_config():
    """Sample multi-sig configuration for testing."""
    from spl_deployment import MultiSigConfig
    
    return MultiSigConfig(
        signers=[
            "Signer1PubKey12345678901234567890123",
            "Signer2PubKey12345678901234567890123",
            "Signer3PubKey12345678901234567890123",
            "Signer4PubKey12345678901234567890123",
            "Signer5PubKey12345678901234567890123"
        ],
        threshold=3
    )


@pytest.fixture
def sample_escrow_config():
    """Sample escrow configuration for testing."""
    from spl_deployment import BridgeEscrowConfig
    
    return BridgeEscrowConfig(
        escrow_authority="BridgeProgramPDA",
        mint_address="MintAddress123",
        daily_mint_cap=100_000_000_000_000,
        per_tx_limit=10_000_000_000_000
    )


@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary config file."""
    import json
    
    config_data = {
        "token": {
            "name": "Temp Test Token",
            "symbol": "TTT",
            "decimals": 9
        },
        "multisig": {
            "signers": ["Signer1", "Signer2", "Signer3"],
            "threshold": 2
        }
    }
    
    config_file = tmp_path / "test-config.json"
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    return config_file


@pytest.fixture
def mock_spl_deployment():
    """Mock SPL deployment for testing."""
    from unittest.mock import Mock
    
    mock = Mock()
    mock.mint_address = "MockMintAddress123"
    mock.token_client = Mock()
    
    return mock
