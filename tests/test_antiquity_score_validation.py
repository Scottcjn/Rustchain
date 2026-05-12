# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT / "rips" / "rustchain-core"
PYTHON_ROOT = ROOT / "rips" / "python" / "rustchain"


def _namespace_package(name: str, path: Path):
    package = sys.modules.get(name)
    if package is None:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    return package


def _core_module(module_name: str):
    _namespace_package("rustchain_core", CORE_ROOT)
    if str(CORE_ROOT) not in sys.path:
        sys.path.insert(0, str(CORE_ROOT))
    return importlib.import_module(f"rustchain_core.{module_name}")


def _setup_validator_module():
    if str(CORE_ROOT) not in sys.path:
        sys.path.insert(0, str(CORE_ROOT))
    chain_params = importlib.import_module("config.chain_params")
    chain_params.NETWORK_NAME = getattr(chain_params, "NETWORK_NAME", "testnet")
    chain_params.ANCIENT_THRESHOLD = getattr(chain_params, "ANCIENT_THRESHOLD", 30)
    chain_params.SACRED_THRESHOLD = getattr(chain_params, "SACRED_THRESHOLD", 25)
    chain_params.VINTAGE_THRESHOLD = getattr(chain_params, "VINTAGE_THRESHOLD", 20)
    chain_params.CLASSIC_THRESHOLD = getattr(chain_params, "CLASSIC_THRESHOLD", 15)
    chain_params.RETRO_THRESHOLD = getattr(chain_params, "RETRO_THRESHOLD", 10)
    chain_params.MODERN_THRESHOLD = getattr(chain_params, "MODERN_THRESHOLD", 5)
    return _core_module("validator.setup_validator")


def _python_module(module_name: str):
    _namespace_package("rustchain_pkg", PYTHON_ROOT)
    return importlib.import_module(f"rustchain_pkg.{module_name}")


SCORE_FUNCTIONS = [
    (
        "validator.score.calculate_antiquity_score",
        _core_module("validator.score").calculate_antiquity_score,
    ),
    (
        "consensus.poa.compute_antiquity_score",
        _core_module("consensus.poa").compute_antiquity_score,
    ),
    (
        "validator.setup_validator.calculate_antiquity_score",
        _setup_validator_module().calculate_antiquity_score,
    ),
    (
        "python.proof_of_antiquity.calculate_antiquity_score",
        _python_module("proof_of_antiquity").calculate_antiquity_score,
    ),
]


@pytest.mark.parametrize("name,score_func", SCORE_FUNCTIONS, ids=[name for name, _ in SCORE_FUNCTIONS])
@pytest.mark.parametrize("release_year", [0, 1969, 3000, True, 1992.5, "1992"])
def test_antiquity_scores_reject_invalid_release_years(name, score_func, release_year):
    with pytest.raises(ValueError, match="release_year"):
        score_func(release_year, 365)


@pytest.mark.parametrize("name,score_func", SCORE_FUNCTIONS, ids=[name for name, _ in SCORE_FUNCTIONS])
@pytest.mark.parametrize("uptime_days", [-1, True, 1.5, "365"])
def test_antiquity_scores_reject_invalid_uptime(name, score_func, uptime_days):
    with pytest.raises(ValueError, match="uptime_days"):
        score_func(1992, uptime_days)


@pytest.mark.parametrize("name,score_func", SCORE_FUNCTIONS, ids=[name for name, _ in SCORE_FUNCTIONS])
def test_antiquity_scores_preserve_valid_hardware_scoring(name, score_func):
    assert score_func(1992, 276) > 0


def test_validator_rejects_unknown_hardware_claims():
    score_module = _core_module("validator.score")

    valid, message = score_module.validate_hardware_claim("QuantumCPU-9000", 1970)

    assert valid is False
    assert "Unknown hardware" in message


def test_validator_rejects_impossible_claimed_years_before_model_lookup():
    score_module = _core_module("validator.score")

    valid, message = score_module.validate_hardware_claim("486DX2", 0)

    assert valid is False
    assert "Release year" in message


def test_validator_accepts_known_hardware_with_matching_year():
    score_module = _core_module("validator.score")

    valid, message = score_module.validate_hardware_claim("486DX2", 1992)

    assert valid is True
    assert "Hardware validated" in message
