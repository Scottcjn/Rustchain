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


def test_block_reward_rejects_negative_halving_boundary():
    chain_params = load_chain_params()

    with pytest.raises(ValueError, match="Block height cannot be negative: -210000"):
        chain_params.calculate_block_reward(-chain_params.HALVING_INTERVAL_BLOCKS)


def test_block_reward_keeps_genesis_and_halving_outputs():
    chain_params = load_chain_params()

    assert chain_params.calculate_block_reward(0) == Decimal("1.5")
    assert chain_params.calculate_block_reward(chain_params.HALVING_INTERVAL_BLOCKS) == Decimal("0.75")
    assert chain_params.calculate_block_reward(
        chain_params.HALVING_INTERVAL_BLOCKS * chain_params.HALVING_COUNT
    ) == Decimal("0.09375")
