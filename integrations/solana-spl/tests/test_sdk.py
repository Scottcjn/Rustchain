"""
Tests for wRTC SDK

Run with:
    pytest tests/test_sdk.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sdk import (
    WRtcToken,
    WRtcBridge,
    WRtcSDK,
    TokenInfo,
    BridgeQuote,
    get_token_info,
    get_bridge_quote,
)


class TestWRtcToken:
    """Test WRtcToken class."""
    
    def test_initialization_mainnet(self):
        """Test token initialization for mainnet."""
        token = WRtcToken(network="mainnet")
        
        assert token.network == "mainnet"
        assert "mainnet" in token.rpc_url
        assert token.mint_address == "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    
    def test_initialization_devnet(self):
        """Test token initialization for devnet."""
        token = WRtcToken(network="devnet")
        
        assert token.network == "devnet"
        assert "devnet" in token.rpc_url
    
    def test_get_token_info(self):
        """Test getting token info."""
        token = WRtcToken(network="mainnet")
        info = token.get_token_info()
        
        assert isinstance(info, TokenInfo)
        assert info.name == "Wrapped RustChain"
        assert info.symbol == "wRTC"
        assert info.decimals == 9
    
    def test_to_ui_amount(self):
        """Test conversion to UI amount."""
        token = WRtcToken(network="mainnet")
        
        # 1 wRTC = 10^9 smallest units
        amount = 1_000_000_000
        ui_amount = token.to_ui_amount(amount)
        
        assert ui_amount == 1.0
    
    def test_from_ui_amount(self):
        """Test conversion from UI amount."""
        token = WRtcToken(network="mainnet")
        
        ui_amount = 1.0
        amount = token.from_ui_amount(ui_amount)
        
        assert amount == 1_000_000_000
    
    def test_round_trip_conversion(self):
        """Test round-trip conversion."""
        token = WRtcToken(network="mainnet")
        
        ui_amount = 123.456
        amount = token.from_ui_amount(ui_amount)
        back_to_ui = token.to_ui_amount(amount)
        
        assert abs(back_to_ui - ui_amount) < 0.001


class TestWRtcBridge:
    """Test WRtcBridge class."""
    
    @pytest.fixture
    def bridge(self):
        """Create bridge instance."""
        token = WRtcToken(network="mainnet")
        return WRtcBridge(token)
    
    def test_initialization(self, bridge):
        """Test bridge initialization."""
        assert bridge.bridge_fee_bps == 30  # 0.3%
        assert bridge.min_bridge_amount == 10
        assert bridge.max_bridge_amount == 10000
    
    def test_get_bridge_quote(self, bridge):
        """Test getting bridge quote."""
        amount = 1000 * 10**9  # 1000 wRTC
        quote = bridge.get_bridge_quote(amount, "wRTC", "RTC")
        
        assert isinstance(quote, BridgeQuote)
        assert quote.from_amount == amount
        assert quote.expected_to_amount < amount  # Fee deducted
        assert quote.fee > 0
        assert quote.min_receive <= quote.expected_to_amount
    
    def test_bridge_fee_calculation(self, bridge):
        """Test bridge fee calculation."""
        amount = 10000 * 10**9  # 10k wRTC
        quote = bridge.get_bridge_quote(amount, "wRTC", "RTC")
        
        # Fee should be 0.3% (30 bps)
        expected_fee = (amount * 30) // 10000
        assert quote.fee == expected_fee
    
    def test_slippage_setting(self, bridge):
        """Test slippage configuration."""
        amount = 1000 * 10**9
        
        # Default slippage (50 bps = 0.5%)
        quote1 = bridge.get_bridge_quote(amount, "wRTC", "RTC")
        assert quote1.slippage_bps == 50
        
        # Custom slippage (100 bps = 1%)
        quote2 = bridge.get_bridge_quote(amount, "wRTC", "RTC", slippage_bps=100)
        assert quote2.slippage_bps == 100
        assert quote2.min_receive < quote1.min_receive  # Higher slippage = lower min
    
    def test_initiate_bridge(self, bridge):
        """Test initiating bridge transaction."""
        amount = 100 * 10**9
        tx = bridge.initiate_bridge(amount, "wRTC", "RustChainAddress")
        
        assert tx.status == "pending"
        assert tx.from_amount == amount
        assert tx.to_amount < amount  # Fee deducted


class TestWRtcSDK:
    """Test complete WRtcSDK class."""
    
    def test_initialization(self):
        """Test SDK initialization."""
        sdk = WRtcSDK(network="mainnet")
        
        assert sdk.network == "mainnet"
        assert sdk.token is not None
        assert sdk.bridge is not None
    
    def test_get_sdk_info(self):
        """Test getting SDK info."""
        sdk = WRtcSDK(network="mainnet")
        info = sdk.get_sdk_info()
        
        assert info["version"] == "1.0.0"
        assert info["network"] == "mainnet"
        assert "mint_address" in info
        assert "features" in info
        assert "limits" in info
    
    def test_sdk_features(self):
        """Test SDK features list."""
        sdk = WRtcSDK(network="mainnet")
        info = sdk.get_sdk_info()
        
        expected_features = [
            "token_info",
            "balance_query",
            "bridge_quotes",
            "bridge_status"
        ]
        
        for feature in expected_features:
            assert feature in info["features"]


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_get_token_info(self):
        """Test get_token_info function."""
        info = get_token_info(network="mainnet")
        
        assert isinstance(info, TokenInfo)
        assert info.symbol == "wRTC"
    
    def test_get_bridge_quote(self):
        """Test get_bridge_quote function."""
        quote = get_bridge_quote(1000, "wRTC", "RTC", network="mainnet")
        
        assert isinstance(quote, BridgeQuote)
        assert quote.from_token == "wRTC"
        assert quote.to_token == "RTC"


class TestEdgeCases:
    """Test edge cases."""
    
    def test_zero_amount_quote(self):
        """Test quote with zero amount."""
        token = WRtcToken(network="mainnet")
        bridge = WRtcBridge(token)
        
        quote = bridge.get_bridge_quote(0, "wRTC", "RTC")
        assert quote.from_amount == 0
        assert quote.expected_to_amount == 0
        assert quote.fee == 0
    
    def test_very_small_amount(self):
        """Test quote with very small amount."""
        token = WRtcToken(network="mainnet")
        bridge = WRtcBridge(token)
        
        amount = 1  # 1 smallest unit
        quote = bridge.get_bridge_quote(amount, "wRTC", "RTC")
        
        assert quote.from_amount == 1
        # Fee might round to 0 for very small amounts
        assert quote.fee >= 0
    
    def test_maximum_bridge_amount(self):
        """Test quote at maximum bridge amount."""
        token = WRtcToken(network="mainnet")
        bridge = WRtcBridge(token)
        
        amount = bridge.max_bridge_amount * 10**9
        quote = bridge.get_bridge_quote(amount, "wRTC", "RTC")
        
        assert quote.from_amount == amount
        assert quote.expected_to_amount > 0
    
    def test_invalid_network(self):
        """Test handling of invalid network."""
        # Should default to mainnet behavior
        token = WRtcToken(network="invalid")
        info = token.get_token_info()
        
        assert info is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
