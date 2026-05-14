# SPDX-License-Identifier: MIT

import hashlib
import json
from datetime import datetime, timezone

import pytest

from tools import validator_core_with_badge as validator_badge
from tools.validator_core_with_badge import simulate_entropy_score


class FixedDatetime:
    @classmethod
    def utcnow(cls):
        return datetime(2026, 5, 13, 6, 30, 0)


def test_simulate_entropy_score_uses_current_utc_year_by_default():
    cpu_model = "Pentium III"
    bios_date = "1998-12-01"
    current_year = datetime.now(timezone.utc).year
    expected_age_weight = max(0, current_year - 1998)
    expected_score = round((expected_age_weight * 0.25) + (len(cpu_model) * 0.05), 2)

    assert simulate_entropy_score(cpu_model, bios_date) == expected_score


def test_simulate_entropy_score_can_cover_2026_age_weight():
    score = simulate_entropy_score("Pentium III", "1998-12-01", current_year=2026)

    assert score == 7.55


def test_simulate_entropy_score_clamps_future_bios_age():
    score = simulate_entropy_score("486", "2030-01-01", current_year=2026)

    assert score == 0.15


def test_simulate_entropy_score_rejects_invalid_date():
    with pytest.raises(ValueError):
        simulate_entropy_score("Pentium III", "not-a-date")


def test_generate_validator_entry_writes_current_year_proof_and_badge(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(validator_badge, "datetime", FixedDatetime)

    validator_badge.generate_validator_entry()

    proof = json.loads((tmp_path / "proof_of_antiquity.json").read_text())
    rewards = json.loads((tmp_path / "relic_rewards.json").read_text())
    expected_fingerprint = hashlib.sha256(b"Pentium III_1998-12-01").hexdigest()

    assert proof["wallet"] == "example-wallet-123"
    assert proof["bios_timestamp"] == "1998-12-01"
    assert proof["cpu_model"] == "Pentium III"
    assert proof["entropy_score"] == 7.55
    assert proof["score_composite"] == 13.22
    assert proof["bios_fingerprint"] == expected_fingerprint
    assert proof["timestamp"] == "2026-05-13T06:30:00Z"
    assert proof["rarity_bonus"] == 1.02
    assert rewards["badges"][0]["nft_id"] == "badge_defrag_001"
    assert rewards["badges"][0]["emotional_resonance"]["timestamp"] == (
        "2026-05-13T06:30:00Z"
    )
    assert "proof_of_antiquity.json created" in capsys.readouterr().out


def test_generate_validator_entry_skips_badge_when_entropy_is_low(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(validator_badge, "datetime", FixedDatetime)
    monkeypatch.setattr(validator_badge, "simulate_entropy_score", lambda _cpu, _bios: 2.99)

    validator_badge.generate_validator_entry()

    proof = json.loads((tmp_path / "proof_of_antiquity.json").read_text())
    assert proof["entropy_score"] == 2.99
    assert proof["score_composite"] == 8.66
    assert not (tmp_path / "relic_rewards.json").exists()
