# SPDX-License-Identifier: MIT
"""Regressions for validator release-year heuristics."""

import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "rips"
    / "rustchain-core"
    / "validator"
    / "setup_validator.py"
)


def _load_module():
    chain_params = types.ModuleType("config.chain_params")
    chain_params.CHAIN_ID = "test-chain"
    chain_params.NETWORK_NAME = "test-network"
    chain_params.HARDWARE_TIERS = {
        "ancient": 3.5,
        "sacred": 3.0,
        "vintage": 2.5,
        "classic": 2.0,
        "retro": 1.5,
        "modern": 1.0,
        "recent": 0.5,
    }
    chain_params.ANCIENT_THRESHOLD = 30
    chain_params.SACRED_THRESHOLD = 25
    chain_params.VINTAGE_THRESHOLD = 20
    chain_params.CLASSIC_THRESHOLD = 15
    chain_params.RETRO_THRESHOLD = 10
    chain_params.MODERN_THRESHOLD = 5

    entropy = types.ModuleType("validator.entropy")
    entropy.HardwareEntropyCollector = object
    entropy.SoftwareEntropyCollector = object
    entropy.EntropyProfile = object
    entropy.ValidatorIdentityManager = object

    sys.modules["config"] = types.ModuleType("config")
    sys.modules["config.chain_params"] = chain_params
    sys.modules["validator"] = types.ModuleType("validator")
    sys.modules["validator.entropy"] = entropy

    spec = importlib.util.spec_from_file_location("setup_validator", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["setup_validator"] = module
    spec.loader.exec_module(module)
    return module


def test_unknown_cpu_defaults_to_current_year_not_free_antiquity():
    module = _load_module()

    assert module.estimate_release_year("FakeCPU-X9999", "UnknownVendor") == module.CURRENT_YEAR


def test_known_cpu_release_years_are_preserved():
    module = _load_module()

    assert module.estimate_release_year("Intel Core i7-14700K", "GenuineIntel") == 2024
    assert module.estimate_release_year("PowerMac3,6 PowerPC G4", "Apple") == 2003
