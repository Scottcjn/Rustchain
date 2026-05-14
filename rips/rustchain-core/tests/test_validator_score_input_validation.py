import importlib.util
import sys
import types
from pathlib import Path


def _load_score_module():
    root = Path(__file__).resolve().parents[1]
    package = "rustchain_core_under_test"

    for name, path in (
        (package, root),
        (f"{package}.config", root / "config"),
        (f"{package}.validator", root / "validator"),
    ):
        module = sys.modules.get(name)
        if module is None:
            module = types.ModuleType(name)
            module.__path__ = [str(path)]
            sys.modules[name] = module

    module_name = f"{package}.validator.score"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        root / "validator" / "score.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


score = _load_score_module()


def test_unknown_hardware_claim_fails_closed():
    valid, message = score.validate_hardware_claim("QuantumCPU-9000", 1992)

    assert valid is False
    assert "Unknown hardware" in message


def test_impossible_release_year_gets_no_antiquity_score():
    valid, message = score.validate_hardware_claim("486DX2", 0)

    assert valid is False
    assert "Invalid release year" in message
    assert score.calculate_antiquity_score(0, 365) == 0.0


def test_negative_uptime_does_not_crash_and_scores_zero():
    assert score.calculate_antiquity_score(1992, -1) == 0.0


def test_known_hardware_still_validates_and_scores():
    valid, message = score.validate_hardware_claim("IBM 486DX2", 1992)

    assert valid is True
    assert "Hardware validated" in message
    assert score.calculate_antiquity_score(1992, 365) > 0


def test_validator_rejects_invalid_uptime_without_exception():
    validator = score.HardwareValidator()
    hardware = score.HardwareInfo("486DX2", 1992, -1)

    result = validator.validate_miner("RTC-test-wallet", hardware)

    assert result["eligible"] is False
    assert "below minimum" in result["errors"][0]
