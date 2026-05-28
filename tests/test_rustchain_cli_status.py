# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "cli" / "rustchain_cli.py"
spec = importlib.util.spec_from_file_location("rustchain_cli", MODULE_PATH)
rustchain_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rustchain_cli)


def test_status_text_handles_partial_health_payload(monkeypatch, capsys):
    monkeypatch.setattr(
        rustchain_cli,
        "fetch_api",
        lambda endpoint: {
            "ok": True,
            "version": "2.2.1",
            "uptime_s": None,
            "db_rw": True,
            "tip_age_slots": None,
            "backup_age_hours": None,
        },
    )

    rustchain_cli.cmd_status(SimpleNamespace(json=False))

    out = capsys.readouterr().out
    assert "Status:" in out
    assert "Uptime:      N/A" in out
    assert "Tip Age:     N/A" in out
    assert "Backup Age:  N/A" in out
