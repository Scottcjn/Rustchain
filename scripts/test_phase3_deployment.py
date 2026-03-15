#!/usr/bin/env python3
"""
Unit Tests for Phase 3 Deployment
==================================

Tests for spectrum_pool_manager.py and deploy_phase3.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from spectrum_pool_manager import (
    SpectrumAPI,
    SpectrumPoolManager,
    PoolInfo,
    LiquidityPosition,
    PoolCreationConfig,
    MIN_LIQUIDITY
)


class TestPoolInfo:
    """Tests for PoolInfo dataclass"""
    
    def test_pool_info_creation(self):
        """Test basic pool info creation"""
        pool = PoolInfo(
            pool_id="pool_123",
            base_token_id="token_base",
            quote_token_id="token_quote",
            base_token_name="RTC",
            quote_token_name="ERG",
            base_reserve=1000 * 10**9,
            quote_reserve=67 * 10**9,
            lp_token_id="lp_123",
            lp_token_supply=1000000,
            fee=0.003,
            price=0.067
        )
        
        assert pool.pool_id == "pool_123"
        assert pool.base_token_name == "RTC"
        assert pool.quote_token_name == "ERG"
        assert pool.price == 0.067
        assert pool.fee == 0.003


class TestPoolCreationConfig:
    """Tests for PoolCreationConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = PoolCreationConfig(
            base_token_id="rtc_token",
            quote_token_id="erg_token",
            base_amount=1000 * 10**9,
            quote_amount=67 * 10**9
        )
        
        assert config.fee_tier == 0.003  # Default 0.3%
        assert config.start_price is None
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = PoolCreationConfig(
            base_token_id="rtc_token",
            quote_token_id="erg_token",
            base_amount=1000 * 10**9,
            quote_amount=67 * 10**9,
            fee_tier=0.0025,
            start_price=0.067
        )
        
        assert config.fee_tier == 0.0025
        assert config.start_price == 0.067


class TestSpectrumAPI:
    """Tests for SpectrumAPI class"""
    
    @patch('spectrum_pool_manager.requests.Session')
    def test_health_check_success(self, mock_session):
        """Test successful health check"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.return_value.get.return_value = mock_response
        
        api = SpectrumAPI("api_key", testnet=False)
        healthy = api.health_check()
        
        assert healthy is True
    
    @patch('spectrum_pool_manager.requests.Session')
    def test_health_check_failure(self, mock_session):
        """Test failed health check"""
        mock_session.return_value.get.side_effect = Exception("Connection failed")
        
        api = SpectrumAPI("api_key", testnet=False)
        healthy = api.health_check()
        
        assert healthy is False
    
    @patch('spectrum_pool_manager.requests.Session')
    def test_get_pools(self, mock_session):
        """Test getting pools list"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "pool_1",
                    "baseToken": {"id": "token1", "name": "Token1"},
                    "quoteToken": {"id": "token2", "name": "Token2"},
                    "baseReserve": "1000000000000",
                    "quoteReserve": "67000000000",
                    "lpToken": {"id": "lp_1"},
                    "lpTokenSupply": "1000000",
                    "fee": "0.003",
                    "price": "0.067"
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_session.return_value.get.return_value = mock_response
        
        api = SpectrumAPI("api_key")
        pools = api.get_pools(limit=100)
        
        assert len(pools) == 1
        assert pools[0].pool_id == "pool_1"
        assert pools[0].price == 0.067


class TestSpectrumPoolManager:
    """Tests for SpectrumPoolManager class"""
    
    @patch('spectrum_pool_manager.SpectrumAPI')
    def test_check_api_health(self, mock_api_class):
        """Test API health check"""
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.health_check.return_value = True
        
        manager = SpectrumPoolManager(
            api_key="api_key",
            node_host="http://localhost:9053",
            wallet_address="test_addr"
        )
        
        healthy = manager.check_api_health()
        assert healthy is True
    
    @patch('spectrum_pool_manager.SpectrumAPI')
    def test_pool_exists(self, mock_api_class):
        """Test pool existence check"""
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        
        # Mock existing pool
        mock_pool = PoolInfo(
            pool_id="existing_pool",
            base_token_id="rtc_token",
            quote_token_id="erg_token",
            base_token_name="RTC",
            quote_token_name="ERG",
            base_reserve=1000 * 10**9,
            quote_reserve=67 * 10**9,
            lp_token_id="lp_token",
            lp_token_supply=1000000,
            fee=0.003,
            price=0.067
        )
        mock_api.get_pool_by_tokens.return_value = mock_pool
        
        manager = SpectrumPoolManager(
            api_key="api_key",
            node_host="http://localhost:9053",
            wallet_address="test_addr"
        )
        
        exists = manager.rtc_erg_pool_exists("rtc_token")
        assert exists is True
        assert manager.rtc_erg_pool is not None
        assert manager.rtc_erg_pool.pool_id == "existing_pool"
    
    @patch('spectrum_pool_manager.SpectrumAPI')
    def test_create_pool(self, mock_api_class):
        """Test pool creation"""
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.create_pool.return_value = "new_pool_123"
        mock_api.get_pool_by_tokens.return_value = None  # Pool doesn't exist
        
        manager = SpectrumPoolManager(
            api_key="api_key",
            node_host="http://localhost:9053",
            wallet_address="test_addr"
        )
        
        pool_id = manager.create_rtc_erg_pool(
            rtc_token_id="rtc_token",
            initial_rtc=1000 * 10**9,
            initial_erg=67 * 10**9
        )
        
        assert pool_id == "new_pool_123"
        assert manager.rtc_erg_pool is not None
        assert manager.rtc_erg_pool.base_reserve == 1000 * 10**9
    
    @patch('spectrum_pool_manager.SpectrumAPI')
    def test_add_liquidity(self, mock_api_class):
        """Test adding liquidity"""
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.add_liquidity.return_value = 500000  # LP tokens received
        mock_api.calculate_optimal_deposit.return_value = (1000 * 10**9, 67 * 10**9)
        mock_api.get_pool_by_id.return_value = PoolInfo(
            pool_id="pool_123",
            base_token_id="rtc",
            quote_token_id="erg",
            base_token_name="RTC",
            quote_token_name="ERG",
            base_reserve=1000 * 10**9,
            quote_reserve=67 * 10**9,
            lp_token_id="lp",
            lp_token_supply=1000000,
            fee=0.003,
            price=0.067
        )
        
        manager = SpectrumPoolManager(
            api_key="api_key",
            node_host="http://localhost:9053",
            wallet_address="test_addr"
        )
        
        lp_tokens = manager.add_liquidity_to_pool(
            pool_id="pool_123",
            rtc_amount=1000 * 10**9,
            erg_amount=67 * 10**9
        )
        
        assert lp_tokens == 500000
        assert "pool_123" in manager.positions
    
    @patch('spectrum_pool_manager.SpectrumAPI')
    def test_get_pool_stats(self, mock_api_class):
        """Test pool statistics retrieval"""
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.get_pool_by_id.return_value = PoolInfo(
            pool_id="pool_123",
            base_token_id="rtc",
            quote_token_id="erg",
            base_token_name="RTC",
            quote_token_name="ERG",
            base_reserve=1000 * 10**9,
            quote_reserve=67 * 10**9,
            lp_token_id="lp",
            lp_token_supply=1000000,
            fee=0.003,
            price=0.067
        )
        
        manager = SpectrumPoolManager(
            api_key="api_key",
            node_host="http://localhost:9053",
            wallet_address="test_addr"
        )
        
        stats = manager.get_pool_stats("pool_123")
        
        assert stats["pool_id"] == "pool_123"
        assert stats["price"] == 0.067
        assert stats["base_reserve"] == 1000.0
        assert stats["quote_reserve"] == 67.0
        assert "tvl_usd" in stats
        assert "apy_percent" in stats
    
    @patch('spectrum_pool_manager.SpectrumAPI')
    def test_get_user_positions(self, mock_api_class):
        """Test getting user positions"""
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        
        manager = SpectrumPoolManager(
            api_key="api_key",
            node_host="http://localhost:9053",
            wallet_address="test_addr"
        )
        
        # Add mock position
        position = LiquidityPosition(
            pool_id="pool_123",
            lp_tokens=500000,
            base_share=0.5,
            quote_share=0.5,
            base_amount=1000 * 10**9,
            quote_amount=67 * 10**9
        )
        manager.positions["pool_123"] = position
        
        positions = manager.get_user_positions()
        
        assert len(positions) == 1
        assert positions[0].pool_id == "pool_123"
        assert positions[0].lp_tokens == 500000
    
    @patch('spectrum_pool_manager.SpectrumAPI')
    def test_get_total_value_locked(self, mock_api_class):
        """Test TVL calculation"""
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        
        manager = SpectrumPoolManager(
            api_key="api_key",
            node_host="http://localhost:9053",
            wallet_address="test_addr"
        )
        
        # Add mock positions
        manager.positions["pool_1"] = LiquidityPosition(
            pool_id="pool_1",
            lp_tokens=500000,
            base_share=0.5,
            quote_share=0.5,
            base_amount=1000 * 10**9,
            quote_amount=67 * 10**9
        )
        
        manager.positions["pool_2"] = LiquidityPosition(
            pool_id="pool_2",
            lp_tokens=300000,
            base_share=0.3,
            quote_share=0.3,
            base_amount=500 * 10**9,
            quote_amount=33.5 * 10**9
        )
        
        tvl = manager.get_total_value_locked()
        
        assert tvl["rtc"] == 1500.0  # 1000 + 500
        assert tvl["erg"] == 100.5  # 67 + 33.5


class TestLiquidityPosition:
    """Tests for LiquidityPosition dataclass"""
    
    def test_position_creation(self):
        """Test position creation"""
        position = LiquidityPosition(
            pool_id="pool_123",
            lp_tokens=500000,
            base_share=0.5,
            quote_share=0.5,
            base_amount=1000 * 10**9,
            quote_amount=67 * 10**9
        )
        
        assert position.pool_id == "pool_123"
        assert position.lp_tokens == 500000
        assert position.base_share == 0.5
        assert position.fees_earned == 0  # Default
    
    def test_position_with_fees(self):
        """Test position with earned fees"""
        position = LiquidityPosition(
            pool_id="pool_123",
            lp_tokens=500000,
            base_share=0.5,
            quote_share=0.5,
            base_amount=1000 * 10**9,
            quote_amount=67 * 10**9,
            fees_earned=1000000
        )
        
        assert position.fees_earned == 1000000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
