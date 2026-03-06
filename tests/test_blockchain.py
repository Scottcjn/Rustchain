import pytest
import time
from unittest.mock import patch
import sys
from pathlib import Path

# Modules are pre-loaded in conftest.py
rewards_mod = sys.modules["rewards_mod"]
rr_mod = sys.modules["rr_mod"]

GENESIS_TS = rewards_mod.GENESIS_TIMESTAMP
BLOCK_TIME = rewards_mod.BLOCK_TIME

def test_current_slot_calculation():
    """Verify that current_slot calculates the correct slot based on time."""
    # Mock current time to be exactly 10 blocks after genesis
    mock_now = GENESIS_TS + (BLOCK_TIME * 10) + 30 # 10.05 blocks in

    with patch('time.time', return_value=mock_now):
        slot = rewards_mod.current_slot()
        assert slot == 10

def test_current_slot_at_genesis():
    """Verify slot is 0 at genesis timestamp."""
    with patch('time.time', return_value=GENESIS_TS):
        slot = rewards_mod.current_slot()
        assert slot == 0

def test_multiplier_no_decay():
    """Verify multiplier at year 0 (no decay)."""
    # G4 base multiplier is 2.5
    multiplier = rr_mod.get_time_aged_multiplier("g4", 0.0)
    assert multiplier == 2.5

def test_multiplier_with_decay():
    """Verify multiplier after some years of decay."""
    # G4 base = 2.5, bonus = 1.5
    # Decay rate = 0.15 per year
    # After 2 years: bonus = 1.5 * (1 - 0.15 * 2) = 1.5 * 0.7 = 1.05
    # Total = 1.0 + 1.05 = 2.05
    multiplier = rr_mod.get_time_aged_multiplier("g4", 2.0)
    assert pytest.approx(multiplier) == 2.05

def test_multiplier_floor():
    """Verify multiplier does not drop below 1.0."""
    # After 10 years: bonus = 1.5 * (1 - 0.15 * 10) = 1.5 * (1 - 1.5) = -0.75 -> 0
    multiplier = rr_mod.get_time_aged_multiplier("g4", 10.0)
    assert multiplier == 1.0

def test_multiplier_modern_hardware():
    """Verify modern hardware stays at 1.0x even with decay."""
    multiplier = rr_mod.get_time_aged_multiplier("modern_x86", 0.0)
    assert multiplier == 1.0

    multiplier = rr_mod.get_time_aged_multiplier("modern_x86", 5.0)
    assert multiplier == 1.0

def test_chain_age_calculation():
    """Verify slot to years conversion."""
    # 1 year = 365.25 * 24 * 3600 seconds
    # BLOCK_TIME = 600
    # Slots in a year = (365.25 * 24 * 3600) / 600
    slots_per_year = (365.25 * 24 * 3600) / 600

    age = rr_mod.get_chain_age_years(int(slots_per_year))
    assert pytest.approx(age) == 1.0
