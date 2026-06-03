# SPDX-License-Identifier: MIT
"""Regression tests for RustChain chain parameter helpers."""

import importlib.util
from decimal import Decimal
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "rips" / "rustchain-core" / "config" / "chain_params.py"
spec = importlib.util.spec_from_file_location("chain_params", MODULE_PATH)
chain_params = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(chain_params)


def test_get_tier_for_age_covers_boundary_values():
    assert chain_params.get_tier_for_age(0) == "recent"
    assert chain_params.get_tier_for_age(4) == "recent"
    assert chain_params.get_tier_for_age(5) == "modern"
    assert chain_params.get_tier_for_age(9) == "modern"
    assert chain_params.get_tier_for_age(10) == "retro"
    assert chain_params.get_tier_for_age(14) == "retro"
    assert chain_params.get_tier_for_age(15) == "classic"
    assert chain_params.get_tier_for_age(19) == "classic"
    assert chain_params.get_tier_for_age(20) == "vintage"
    assert chain_params.get_tier_for_age(24) == "vintage"
    assert chain_params.get_tier_for_age(25) == "sacred"
    assert chain_params.get_tier_for_age(29) == "sacred"
    assert chain_params.get_tier_for_age(30) == "ancient"
    assert chain_params.get_tier_for_age(999) == "ancient"


def test_get_tier_for_age_defaults_out_of_range_to_recent():
    assert chain_params.get_tier_for_age(-1) == "recent"
    assert chain_params.get_tier_for_age(1000) == "recent"


def test_get_multiplier_for_tier_returns_configured_and_fallback_values():
    assert chain_params.get_multiplier_for_tier("ancient") == 3.5
    assert chain_params.get_multiplier_for_tier("vintage") == 2.5
    assert chain_params.get_multiplier_for_tier("recent") == 0.5
    assert chain_params.get_multiplier_for_tier("unknown") == 0.5


def test_calculate_block_reward_halving_boundaries_and_tail_emission():
    interval = chain_params.HALVING_INTERVAL_BLOCKS
    assert chain_params.calculate_block_reward(0) == Decimal("1.5")
    assert chain_params.calculate_block_reward(interval - 1) == Decimal("1.5")
    assert chain_params.calculate_block_reward(interval) == Decimal("0.75")
    assert chain_params.calculate_block_reward(interval * 2) == Decimal("0.375")
    assert chain_params.calculate_block_reward(interval * 4) == Decimal("0.09375")
    assert chain_params.calculate_block_reward(interval * 5) == Decimal("0.09375")
