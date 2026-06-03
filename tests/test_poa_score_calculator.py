import importlib.util
import sys
import types
from pathlib import Path


def load_score_calculator():
    for name in list(sys.modules):
        if name == "poa_validator" or name.startswith("poa_validator."):
            sys.modules.pop(name)

    module_path = (
        Path(__file__).resolve().parents[1]
        / "rustchain-poa"
        / "validator"
        / "score_calculator.py"
    )
    package = types.ModuleType("poa_validator")
    package.__path__ = [str(module_path.parent)]
    sys.modules["poa_validator"] = package

    spec = importlib.util.spec_from_file_location(
        "poa_validator.score_calculator",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_calculate_score_adds_marker_and_identifier_bonuses(monkeypatch):
    module = load_score_calculator()
    emulation = {"likely_emulated": False, "flags": [], "score": 0}
    markers = {
        "hardware_uuid": "12345678901",
        "cpu_id": "cpu-123",
    }
    monkeypatch.setattr(module, "detect_emulation", lambda: emulation)
    monkeypatch.setattr(
        module,
        "detect_unique_hardware_signature",
        lambda: ("sig-123", markers),
    )

    score, signature, detected_emulation, detected_markers = module.calculate_score()

    assert score == 1200
    assert signature == "sig-123"
    assert detected_emulation is emulation
    assert detected_markers is markers


def test_calculate_score_applies_emulation_penalty_and_caps_marker_bonus(monkeypatch):
    module = load_score_calculator()
    emulation = {"likely_emulated": True, "flags": ["vm"], "score": 50}
    markers = {f"marker_{index}": f"value_{index}" for index in range(20)}
    monkeypatch.setattr(module, "detect_emulation", lambda: emulation)
    monkeypatch.setattr(
        module,
        "detect_unique_hardware_signature",
        lambda: ("sig-emulated", markers),
    )

    score, signature, detected_emulation, detected_markers = module.calculate_score()

    assert score == 700
    assert signature == "sig-emulated"
    assert detected_emulation is emulation
    assert detected_markers is markers


def test_calculate_score_requires_long_hardware_uuid_for_uuid_bonus(monkeypatch):
    module = load_score_calculator()
    emulation = {"likely_emulated": False, "flags": [], "score": 0}
    markers = {
        "hardware_uuid": "short",
        "cpu_id": "cpu-123",
    }
    monkeypatch.setattr(module, "detect_emulation", lambda: emulation)
    monkeypatch.setattr(
        module,
        "detect_unique_hardware_signature",
        lambda: ("sig-short-uuid", markers),
    )

    score, signature, detected_emulation, detected_markers = module.calculate_score()

    assert score == 1150
    assert signature == "sig-short-uuid"
    assert detected_emulation is emulation
    assert detected_markers is markers
