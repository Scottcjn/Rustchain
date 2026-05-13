#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Consensus math regression checks for chain parameters.
"""

import importlib.util
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAIN_PARAMS_PATH = os.path.join(
    PROJECT_ROOT, "rips", "rustchain-core", "config", "chain_params.py"
)


def _load_chain_params():
    """Load chain_params module from file path with a stable import name."""
    spec = importlib.util.spec_from_file_location("chain_params_test_target", CHAIN_PARAMS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load chain_params test target module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["chain_params_test_target"] = module
    spec.loader.exec_module(module)
    return module


class TestChainParams(unittest.TestCase):
    """Edge-case regression tests for reward and math constants."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(CHAIN_PARAMS_PATH):
            raise FileNotFoundError(f"Missing chain params file: {CHAIN_PARAMS_PATH}")
        cls.chain_params = _load_chain_params()

    def test_calculate_block_reward_rejects_negative_height(self):
        """Negative heights should be rejected instead of producing inflated reward."""
        with self.assertRaises(ValueError):
            self.chain_params.calculate_block_reward(-1)

        with self.assertRaises(ValueError):
            self.chain_params.calculate_block_reward(-210000)

    def test_calculate_block_reward_matches_base_reward_at_genesis(self):
        """height=0 remains at the configured base reward."""
        self.assertEqual(
            self.chain_params.calculate_block_reward(0),
            self.chain_params.BLOCK_REWARD,
        )


if __name__ == "__main__":
    unittest.main()
