# SPDX-License-Identifier: MIT
"""Tests for get_time_aged_multiplier penalty preservation (#7892).

Sub-1.0 multipliers (anti-farm penalties like ARM SBC = 0.0005x) must
be returned as-is, not inflated to 1.0.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rip_200_round_robin_1cpu1vote import get_time_aged_multiplier


def test_arm_sbc_penalty_preserved():
    """ARM SBC (0.0005x) must NOT be inflated to 1.0."""
    result = get_time_aged_multiplier("aarch64", 0)
    assert result == 0.0005, f"Expected 0.0005, got {result}"


def test_modern_amd_penalty_preserved():
    """modern_amd (0.8x) must NOT be inflated to 1.0."""
    result = get_time_aged_multiplier("modern_amd", 0)
    assert result == 0.8, f"Expected 0.8, got {result}"


def test_apple_silicon_penalty_preserved():
    """apple_silicon (0.8x) must NOT be inflated to 1.0."""
    result = get_time_aged_multiplier("apple_silicon", 0)
    assert result == 0.8, f"Expected 0.8, got {result}"


def test_baseline_returns_1():
    """Unknown arch defaults to 1.0 and should return 1.0."""
    result = get_time_aged_multiplier("unknown_arch_xyz", 5)
    assert result == 1.0


def test_vintage_multiplier_still_decays():
    """Vintage hardware (>1.0) should still get decay applied."""
    # PowerPC G4 = 2.5x at year 0
    result = get_time_aged_multiplier("g4", 0)
    assert result == 2.5  # full multiplier at year 0

    # At year 10, decay should bring it close to 1.0
    result_year10 = get_time_aged_multiplier("g4", 10)
    assert result_year10 < 2.5
    assert result_year10 >= 1.0  # never drops below baseline


def test_penalty_does_not_change_with_chain_age():
    """Penalty multipliers should not change regardless of chain age."""
    year0 = get_time_aged_multiplier("armv7", 0)
    year5 = get_time_aged_multiplier("armv7", 5)
    year10 = get_time_aged_multiplier("armv7", 10)
    assert year0 == year5 == year10 == 0.0005
