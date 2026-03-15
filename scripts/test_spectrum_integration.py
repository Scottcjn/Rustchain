#!/usr/bin/env python3
"""
Test Spectrum DEX Integration
==============================

Basic tests for Spectrum integration modules.

Usage:
    python scripts/test_spectrum_integration.py
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.spectrum.client import (
    SpectrumClient,
    PoolInfo,
    PriceQuote,
    erg_to_nanoerg,
    nanoerg_to_erg
)
from integrations.spectrum.oracle import SpectrumPriceOracle
from integrations.spectrum.liquidity import LiquidityPoolManager


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""
    
    def test_erg_to_nanoerg(self):
        """Test ERG to nanoERG conversion"""
        self.assertEqual(erg_to_nanoerg(1.0), 1_000_000_000)
        self.assertEqual(erg_to_nanoerg(0.5), 500_000_000)
        self.assertEqual(erg_to_nanoerg(0.001), 1_000_000)
    
    def test_nanoerg_to_erg(self):
        """Test nanoERG to ERG conversion"""
        self.assertEqual(nanoerg_to_erg(1_000_000_000), 1.0)
        self.assertEqual(nanoerg_to_erg(500_000_000), 0.5)
        self.assertEqual(nanoerg_to_erg(1_000_000), 0.001)
    
    def test_conversion_roundtrip(self):
        """Test roundtrip conversion"""
        erg_value = 123.456
        nanoerg = erg_to_nanoerg(erg_value)
        back_to_erg = nanoerg_to_erg(nanoerg)
        self.assertAlmostEqual(back_to_erg, erg_value, places=6)


class TestPoolInfo(unittest.TestCase):
    """Test PoolInfo dataclass"""
    
    def test_price_calculation(self):
        """Test price calculation from reserves"""
        pool = PoolInfo(
            id="test_pool",
            base_token_id="rtc_id",
            base_token_name="RTC",
            quote_token_id="erg_id",
            quote_token_name="ERG",
            base_reserve=1_000_000,
            quote_reserve=67_000,
            lp_token_id="lp_id",
            lp_token_supply=100_000,
            fee=0.3
        )
        
        # Price should be quote/base
        expected_price = 67_000 / 1_000_000
        self.assertAlmostEqual(pool.price, expected_price, places=6)
    
    def test_price_zero_reserve(self):
        """Test price with zero reserve"""
        pool = PoolInfo(
            id="test_pool",
            base_token_id="rtc_id",
            base_token_name="RTC",
            quote_token_id="erg_id",
            quote_token_name="ERG",
            base_reserve=0,
            quote_reserve=67_000,
            lp_token_id="lp_id",
            lp_token_supply=100_000,
            fee=0.3
        )
        
        self.assertEqual(pool.price, 0.0)


class TestSpectrumClient(unittest.TestCase):
    """Test SpectrumClient"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = SpectrumClient()
    
    @patch('integrations.spectrum.client.requests.Session.request')
    def test_health_check_success(self, mock_request):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        result = self.client.health_check()
        self.assertTrue(result)
    
    @patch('integrations.spectrum.client.requests.Session.request')
    def test_health_check_failure(self, mock_request):
        """Test failed health check"""
        mock_request.side_effect = Exception("Connection error")
        
        result = self.client.health_check()
        self.assertFalse(result)
    
    @patch('integrations.spectrum.client.requests.Session.request')
    def test_get_pools(self, mock_request):
        """Test getting pools"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "pool1",
                    "base_token": {"id": "rtc", "name": "RTC"},
                    "quote_token": {"id": "erg", "name": "ERG"},
                    "base_reserve": "1000000",
                    "quote_reserve": "67000",
                    "lp_token_id": "lp1",
                    "lp_token_supply": "100000",
                    "fee": 0.3
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        pools = self.client.get_pools(limit=10)
        self.assertEqual(len(pools), 1)
        self.assertEqual(pools[0].id, "pool1")


class TestPriceOracle(unittest.TestCase):
    """Test SpectrumPriceOracle"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.oracle = SpectrumPriceOracle()
    
    @patch.object(SpectrumPriceOracle, '_fetch_price')
    def test_get_price_cached(self, mock_fetch):
        """Test price retrieval with cache"""
        from integrations.spectrum.oracle import PriceData
        import time
        
        # First call - should fetch
        mock_fetch.return_value = PriceData(
            price=0.067,
            timestamp=int(time.time()),
            volume_24h=0,
            price_change_24h=0
        )
        
        price1 = self.oracle.get_price()
        self.assertEqual(price1, 0.067)
        
        # Second call - should use cache
        price2 = self.oracle.get_price()
        self.assertEqual(price2, 0.067)
        
        # Fetch should only be called once
        mock_fetch.assert_called_once()
    
    def test_get_status(self):
        """Test oracle status"""
        status = self.oracle.get_status()
        
        self.assertIsInstance(status.healthy, bool)
        self.assertIsInstance(status.last_update, int)
        self.assertIsInstance(status.cache_age, int)


class TestLiquidityManager(unittest.TestCase):
    """Test LiquidityPoolManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = LiquidityPoolManager()
    
    def test_calculate_optimal_deposit(self):
        """Test optimal deposit calculation"""
        # Mock pool
        mock_pool = Mock()
        mock_pool.price = 0.067
        
        rtc_amount = 1_000_000
        rtc, erg = self.manager.calculate_optimal_deposit(rtc_amount, mock_pool)
        
        self.assertEqual(rtc, rtc_amount)
        self.assertEqual(erg, int(rtc_amount * 0.067))


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestUtilityFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestPoolInfo))
    suite.addTests(loader.loadTestsFromTestCase(TestSpectrumClient))
    suite.addTests(loader.loadTestsFromTestCase(TestPriceOracle))
    suite.addTests(loader.loadTestsFromTestCase(TestLiquidityManager))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
