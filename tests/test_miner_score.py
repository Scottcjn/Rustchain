# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "miner_score.py"
spec = importlib.util.spec_from_file_location("miner_score", MODULE_PATH)
miner_score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(miner_score)


def test_score_handles_list_payload_and_assigns_grades(monkeypatch, capsys):
    miners = [
        {
            "miner_id": "miner-s-tier-long-id",
            "blocks_mined": 1000,
            "antiquity_multiplier": 1.0,
            "uptime": 100,
        },
        {
            "miner_id": "miner-c-tier",
            "blocks_mined": 100,
            "antiquity_multiplier": 1.0,
            "uptime": 40,
        },
    ]
    monkeypatch.setattr(miner_score, "api", lambda path: miners)

    miner_score.score()

    output = capsys.readouterr().out
    assert "miner-s-tier-lo" in output
    assert "Score: 550" in output
    assert "Grade: S" in output
    assert "miner-c-tier" in output
    assert "Score: 70" in output
    assert "Grade: C" in output


def test_score_handles_dict_payload_filters_by_id_and_fallback_fields(monkeypatch, capsys):
    payload = {
        "miners": [
            {"id": "skip-me", "total_blocks": 999, "multiplier": 9, "uptime_pct": 99},
            {"id": "target", "total_blocks": 220, "multiplier": 2, "uptime_pct": 80},
        ]
    }
    monkeypatch.setattr(miner_score, "api", lambda path: payload)

    miner_score.score("target")

    output = capsys.readouterr().out
    assert "target" in output
    assert "Score: 260" in output
    assert "Grade: A" in output
    assert "skip-me" not in output


def test_score_defaults_missing_metrics_and_ids(monkeypatch, capsys):
    monkeypatch.setattr(miner_score, "api", lambda path: {"miners": [{}]})

    miner_score.score()

    output = capsys.readouterr().out
    assert "?" in output
    assert "Score: 25" in output
    assert "Grade: D" in output
    assert "blocks:0 mult:1.0 uptime:50%" in output


def test_score_handles_empty_or_failed_api_payload(monkeypatch, capsys):
    monkeypatch.setattr(miner_score, "api", lambda path: {})

    miner_score.score()

    assert capsys.readouterr().out == ""
