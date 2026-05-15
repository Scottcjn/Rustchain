from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "integrations"))

from bottube_onboarding import example


def test_validate_metadata_file_reports_missing_file(capsys) -> None:
    result = example.validate_metadata_file("/tmp/does-not-exist-upload-metadata.json")

    assert result == 1
    assert "Error: File not found" in capsys.readouterr().out


def test_validate_metadata_file_accepts_valid_upload_metadata(tmp_path, capsys) -> None:
    metadata_file = tmp_path / "metadata.json"
    metadata_file.write_text(
        json.dumps(
            {
                "title": "My First AI Agent Tutorial",
                "description": "A practical walkthrough for creating a first useful agent video.",
                "duration_seconds": 180,
                "file_size_mb": 45.5,
                "format": "mp4",
                "has_thumbnail": True,
                "tags": ["ai", "tutorial", "agent", "automation"],
                "rights_confirmed": True,
            }
        ),
        encoding="utf-8",
    )

    result = example.validate_metadata_file(str(metadata_file))

    output = capsys.readouterr().out
    assert result == 0
    assert "Upload Validation Result" in output
    assert "Valid:" in output
    assert "Checklist Progress:" in output


def test_check_agent_state_prints_empty_state_guidance(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOTTUBE_STATE_DIR", str(tmp_path))

    example.check_agent_state("agent-new")

    output = capsys.readouterr().out
    assert "Agent: agent-new" in output
    assert "Video Count: 0" in output
    assert "Is New Agent: Yes" in output
    assert "Checklist Progress:" in output
    assert "Remaining Required Items:" in output
    assert "agent-new" in output


def test_main_dispatches_demo_agent_validate_and_help(monkeypatch, capsys) -> None:
    calls: list[tuple] = []

    monkeypatch.setattr(example, "demo_onboarding_flow", lambda agent_id: calls.append(("demo", agent_id)))
    monkeypatch.setattr(example, "check_agent_state", lambda agent_id: calls.append(("agent", agent_id)))
    monkeypatch.setattr(example, "validate_metadata_file", lambda path: calls.append(("validate", path)) or 7)

    assert example.main(["--demo"]) == 0
    assert example.main(["--agent", "agent-123"]) == 0
    assert example.main(["--validate", "metadata.json"]) == 7
    assert example.main([]) == 0

    assert calls == [
        ("demo", "demo_agent_001"),
        ("agent", "agent-123"),
        ("validate", "metadata.json"),
    ]
    assert "BoTTube Onboarding Example" in capsys.readouterr().out
