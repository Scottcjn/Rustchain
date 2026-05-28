# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path

from rich.console import Console


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "tui-dashboard" / "dashboard.py"
spec = importlib.util.spec_from_file_location("tui_dashboard", MODULE_PATH)
tui_dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui_dashboard)


def test_refresh_uses_paginated_miners_total_and_rows(monkeypatch):
    responses = {
        "https://node.example/health": {"ok": True},
        "https://node.example/epoch": {"epoch": 7},
        "https://node.example/api/miners": {
            "miners": [{"miner": "alice"}, {"miner_id": "bob"}],
            "pagination": {"total": 42, "limit": 2, "offset": 0, "count": 2},
        },
        "https://node.example/headers/tip": {},
    }

    monkeypatch.setattr(tui_dashboard, "fetch_json", lambda url, timeout=8: responses.get(url))
    data = tui_dashboard.RustChainData("https://node.example")
    data._fetch_price = lambda: {}

    data.refresh()

    assert data.miners == [{"miner": "alice"}, {"miner_id": "bob"}]
    assert data.miner_total == 42


def test_miners_panel_title_uses_api_total_and_miner_fallback():
    data = tui_dashboard.RustChainData("https://node.example")
    data.miners = [
        {"miner": "alice", "device_arch": "G4"},
        {"miner_id": "bob", "device_arch": "SPARC"},
    ]
    data.miner_total = 42

    panel = tui_dashboard.build_miners_panel(data)

    assert "42 total" in str(panel.title)
    console = Console(record=True, width=100)
    console.print(panel)
    rendered = console.export_text()
    assert "alice" in rendered
    assert "bob" in rendered
