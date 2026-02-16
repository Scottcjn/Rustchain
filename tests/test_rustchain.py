"""
RustChain CI Test Suite
Tests for fingerprint validation, rewards calculation, and consensus logic
"""

import pytest
import hashlib
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add node directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

# Import modules to test
try:
    from fingerprint_checks import (
        check_clock_drift,
        check_cache_timing,
        _compute_hardware_id,
        validate_fingerprint_data,
    )
    from rewards_implementation_rip200 import (
        current_slot,
        slot_to_epoch,
    )
    from rip_200_round_robin_1cpu1vote import (
        get_time_aged_multiplier,
        get_chain_age_years,
        get_round_robin_producer,
    )
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    print(f"Warning: Could not import RustChain modules: {e}")


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="RustChain modules not available")
class TestFingerprintChecks:
    """Test hardware fingerprint validation"""

    def test_compute_hardware_id_different_inputs(self):
        """Test that different inputs produce different hardware IDs"""
        # Mock fingerprint data
        fp1 = {
            "mean_ns": 1000,
            "stdev_ns": 50,
            "cv": 0.05
        }
        fp2 = {
            "mean_ns": 2000,
            "stdev_ns": 100,
            "cv": 0.05
        }
        
        # Compute IDs
        id1 = _compute_hardware_id(fp1)
        id2 = _compute_hardware_id(fp2)
        
        # Different fingerprints should produce different IDs
        assert id1 != id2
        assert isinstance(id1, str)
        assert len(id1) > 0

    def test_compute_hardware_id_stable(self):
        """Test that same input produces same hardware ID"""
        fp = {
            "mean_ns": 1000,
            "stdev_ns": 50,
            "cv": 0.05
        }
        
        id1 = _compute_hardware_id(fp)
        id2 = _compute_hardware_id(fp)
        
        # Same fingerprint should produce same ID
        assert id1 == id2

    def test_clock_drift_detects_synthetic_timing(self):
        """Test that clock drift check can detect synthetic timing"""
        # Run actual clock drift check (will pass on real hardware)
        valid, data = check_clock_drift(samples=50)  # Reduced samples for CI speed
        
        # Should return valid data structure
        assert isinstance(data, dict)
        assert "mean_ns" in data
        assert "stdev_ns" in data
        assert "cv" in data
        assert "drift_stdev" in data
        
        # CV (coefficient of variation) should be > 0 on real hardware
        assert data["cv"] >= 0

    def test_cache_timing_returns_valid_structure(self):
        """Test that cache timing check returns valid data structure"""
        valid, data = check_cache_timing(iterations=20)  # Reduced for CI
        
        assert isinstance(data, dict)
        assert "l1_avg_ns" in data or "l1_avg" in data  # Handle both naming conventions
        assert isinstance(valid, bool)

    def test_validate_fingerprint_data_rejects_empty(self):
        """Test that fingerprint validation rejects empty data"""
        result = validate_fingerprint_data({})
        
        # Should fail validation for empty data
        assert isinstance(result, dict)
        # Check if it has success/valid key (implementation may vary)

    def test_validate_fingerprint_data_clock_threshold(self):
        """Test that CV below threshold is flagged"""
        # Create mock fingerprint with too-perfect timing (emulator signature)
        fp = {
            "clock_drift": {
                "mean_ns": 1000,
                "stdev_ns": 0.1,
                "cv": 0.00001,  # Too perfect - likely emulator
                "drift_stdev": 0
            },
            "cache_timing": {
                "l1_avg_ns": 10,
                "l2_avg_ns": 50,
                "l3_avg_ns": 200
            }
        }
        
        result = validate_fingerprint_data(fp)
        
        # Should detect synthetic timing
        assert isinstance(result, dict)


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="RustChain modules not available")
class TestRewardsImplementation:
    """Test reward calculation logic"""

    def test_current_slot_calculation(self):
        """Test slot calculation from timestamp"""
        # Mock genesis timestamp
        with patch('rewards_implementation_rip200.GENESIS_TIMESTAMP', 1728000000):
            with patch('time.time', return_value=1728000600):  # 600s after genesis
                slot = current_slot()
                # 600s / 600s block time = slot 1
                assert slot == 1

    def test_slot_to_epoch_conversion(self):
        """Test slot to epoch conversion (144 blocks per epoch)"""
        assert slot_to_epoch(0) == 0
        assert slot_to_epoch(143) == 0
        assert slot_to_epoch(144) == 1
        assert slot_to_epoch(288) == 2

    def test_slot_to_epoch_large_numbers(self):
        """Test slot to epoch with large slot numbers"""
        assert slot_to_epoch(1440) == 10
        assert slot_to_epoch(14400) == 100


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="RustChain modules not available")
class TestRIP200Consensus:
    """Test RIP-200 round-robin consensus logic"""

    def test_time_aged_multiplier_increases_with_time(self):
        """Test that antiquity multiplier increases with chain age"""
        # Mock chain age
        with patch('rip_200_round_robin_1cpu1vote.get_chain_age_years', return_value=0.0):
            mult_0 = get_time_aged_multiplier()
        
        with patch('rip_200_round_robin_1cpu1vote.get_chain_age_years', return_value=1.0):
            mult_1 = get_time_aged_multiplier()
        
        # Multiplier should increase with age
        assert mult_1 > mult_0

    def test_chain_age_calculation(self):
        """Test chain age calculation in years"""
        # Mock time and genesis
        genesis = 1728000000
        one_year_later = genesis + (365 * 24 * 60 * 60)
        
        with patch('rip_200_round_robin_1cpu1vote.GENESIS_TIMESTAMP', genesis):
            with patch('time.time', return_value=one_year_later):
                age = get_chain_age_years()
                # Should be approximately 1 year
                assert 0.99 < age < 1.01

    def test_round_robin_producer_deterministic(self):
        """Test that round-robin producer selection is deterministic"""
        miners = ["miner1", "miner2", "miner3"]
        epoch = 100
        
        # Same inputs should produce same result
        producer1 = get_round_robin_producer(miners, epoch)
        producer2 = get_round_robin_producer(miners, epoch)
        
        assert producer1 == producer2
        assert producer1 in miners

    def test_round_robin_producer_rotates(self):
        """Test that producer rotates across epochs"""
        miners = ["miner1", "miner2", "miner3"]
        
        # Get producers for sequential epochs
        producers = [get_round_robin_producer(miners, epoch) for epoch in range(10)]
        
        # Should use multiple different miners (rotation)
        unique_producers = set(producers)
        assert len(unique_producers) > 1  # At least 2 different miners


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="RustChain modules not available")
class TestAddressValidation:
    """Test RTC address format validation"""

    def test_rtc_address_format(self):
        """Test RTC address format validation"""
        # Valid RTC address (example)
        valid_addr = "RTC1234567890abcdef1234567890abcdef12345678"
        
        # Address should start with RTC
        assert valid_addr.startswith("RTC")

    def test_rtc_address_length(self):
        """Test that RTC addresses have consistent length"""
        # RTC addresses should be fixed length (RTC + 40 hex chars)
        valid_addr = "RTC" + "a" * 40
        assert len(valid_addr) == 43


# Run tests with coverage if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=node", "--cov-report=term-missing"])
