# SPDX-License-Identifier: MIT

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest


CHAIN_PARAMS_PATH = (
    Path(__file__).resolve().parents[1]
    / "rips"
    / "rustchain-core"
    / "config"
    / "chain_params.py"
)


def load_chain_params():
    spec = importlib.util.spec_from_file_location("chain_params_under_test", CHAIN_PARAMS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_calculate_block_reward_rejects_negative_heights():
    chain_params = load_chain_params()

    with pytest.raises(ValueError, match="Block height cannot be negative: -1"):
        chain_params.calculate_block_reward(-1)

    with pytest.raises(ValueError, match="Block height cannot be negative: -210000"):
        chain_params.calculate_block_reward(-210000)


def test_calculate_block_reward_preserves_halving_schedule():
    chain_params = load_chain_params()

    assert chain_params.calculate_block_reward(0) == Decimal("1.5")
    assert (
        chain_params.calculate_block_reward(chain_params.HALVING_INTERVAL_BLOCKS - 1)
        == Decimal("1.5")
    )
    assert (
        chain_params.calculate_block_reward(chain_params.HALVING_INTERVAL_BLOCKS)
        == Decimal("0.75")
    )
    assert (
        chain_params.calculate_block_reward(chain_params.HALVING_INTERVAL_BLOCKS * 2)
        == Decimal("0.375")
    )
    assert (
        chain_params.calculate_block_reward(chain_params.HALVING_INTERVAL_BLOCKS * 4)
        == Decimal("0.09375")
    )
    assert (
        chain_params.calculate_block_reward(chain_params.HALVING_INTERVAL_BLOCKS * 5)
        == Decimal("0.09375")
    )
