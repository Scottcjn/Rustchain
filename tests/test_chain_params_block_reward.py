# SPDX-License-Identifier: MIT

from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CHAIN_PARAMS_PATH = REPO_ROOT / "rips" / "rustchain-core" / "config" / "chain_params.py"


def load_chain_params():
    spec = importlib.util.spec_from_file_location("chain_params_under_test", CHAIN_PARAMS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_block_reward_rejects_negative_height():
    chain_params = load_chain_params()

    with pytest.raises(ValueError, match="Block height cannot be negative: -1"):
        chain_params.calculate_block_reward(-1)


def test_block_reward_rejects_negative_height_large():
    chain_params = load_chain_params()

    with pytest.raises(ValueError, match="Block height cannot be negative: -210000"):
        chain_params.calculate_block_reward(-210_000)


def test_block_reward_is_fixed_no_halving():
    # RIP-0004: emission is fixed at 1.5 RTC/epoch, no halving, at every height.
    chain_params = load_chain_params()

    assert chain_params.calculate_block_reward(0) == Decimal("1.5")
    assert chain_params.calculate_block_reward(210_000) == Decimal("1.5")
    assert chain_params.calculate_block_reward(10_000_000) == Decimal("1.5")
