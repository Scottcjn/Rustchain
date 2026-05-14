# SPDX-License-Identifier: MIT
import importlib.util
import json
from datetime import datetime
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "quantum_flux_validator.py"
spec = importlib.util.spec_from_file_location("quantum_flux_validator", MODULE_PATH)
quantum_flux_validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quantum_flux_validator)


class FixedDatetime:
    @classmethod
    def utcnow(cls):
        return datetime(2026, 5, 13, 6, 30, 0)


def test_detect_network_flux_sleeps_with_random_delay_and_returns_choice(monkeypatch):
    calls = []
    monkeypatch.setattr(quantum_flux_validator.random, "randint", lambda start, end: 3)
    monkeypatch.setattr(quantum_flux_validator.time, "sleep", lambda seconds: calls.append(seconds))
    monkeypatch.setattr(quantum_flux_validator.random, "choice", lambda options: options[0])

    assert quantum_flux_validator.detect_network_flux() is True
    assert calls == [3]


def test_award_quantum_flux_badge_writes_badge_when_flux_detected(tmp_path, monkeypatch, capsys):
    relics_dir = tmp_path / "relics"
    relics_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(quantum_flux_validator, "detect_network_flux", lambda: True)

    quantum_flux_validator.award_quantum_flux_badge()

    payload = json.loads((relics_dir / "badge_quantum_flux_validator.json").read_text())
    badge = payload["badges"][0]
    assert badge["nft_id"] == "badge_quantum_flux_validator"
    assert badge["soulbound"] is True
    assert badge["emotional_resonance"]["timestamp"].endswith("Z")
    assert "Quantum Flux detected" in capsys.readouterr().out


def test_award_quantum_flux_badge_does_not_write_when_no_flux(tmp_path, monkeypatch, capsys):
    relics_dir = tmp_path / "relics"
    relics_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(quantum_flux_validator, "detect_network_flux", lambda: False)

    quantum_flux_validator.award_quantum_flux_badge()

    assert not (relics_dir / "badge_quantum_flux_validator.json").exists()
    assert "No network anomaly detected" in capsys.readouterr().out


def test_detect_network_flux_can_return_false(monkeypatch):
    monkeypatch.setattr(quantum_flux_validator.random, "randint", lambda start, end: 2)
    monkeypatch.setattr(quantum_flux_validator.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(quantum_flux_validator.random, "choice", lambda options: options[1])

    assert quantum_flux_validator.detect_network_flux() is False


def test_award_quantum_flux_badge_uses_current_utc_timestamp(tmp_path, monkeypatch):
    relics_dir = tmp_path / "relics"
    relics_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(quantum_flux_validator, "datetime", FixedDatetime)
    monkeypatch.setattr(quantum_flux_validator, "detect_network_flux", lambda: True)

    quantum_flux_validator.award_quantum_flux_badge()

    payload = json.loads((relics_dir / "badge_quantum_flux_validator.json").read_text())
    badge = payload["badges"][0]
    assert badge["title"] == "Quantum Flux Validator"
    assert badge["rarity"] == "Mythic"
    assert badge["emotional_resonance"]["timestamp"] == "2026-05-13T06:30:00Z"
