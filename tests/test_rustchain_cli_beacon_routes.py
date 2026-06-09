# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "cli" / "rustchain_cli.py"
spec = importlib.util.spec_from_file_location("rustchain_cli", MODULE_PATH)
rustchain_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rustchain_cli)


def test_agent_list_uses_live_beacon_agents_endpoint(monkeypatch, capsys):
    seen = []

    def fake_fetch(endpoint):
        seen.append(endpoint)
        assert endpoint == "/beacon/api/agents"
        return [{"agent_id": "bcn_alpha", "name": "Alpha", "status": "active"}]

    monkeypatch.setattr(rustchain_cli, "fetch_api", fake_fetch)

    rustchain_cli.cmd_agent(SimpleNamespace(action="list", json=True, dry_run=False))

    assert seen == ["/beacon/api/agents"]
    data = json.loads(capsys.readouterr().out)
    assert data[0]["agent_id"] == "bcn_alpha"
    assert data[0]["type"] == "agent"


def test_agent_info_filters_beacon_list_and_merges_reputation(monkeypatch, capsys):
    seen = []

    def fake_fetch(endpoint):
        seen.append(endpoint)
        if endpoint == "/beacon/api/agents":
            return [
                {"agent_id": "bcn_alpha", "name": "Alpha"},
                {"agent_id": "bcn_beta", "name": "Beta", "provider_name": "Beacon"},
            ]
        if endpoint == "/beacon/api/reputation/bcn_beta":
            return {
                "agent_id": "bcn_beta",
                "score": 42.5,
                "total_rtc_earned": 7.25,
                "bounties_completed": 3,
            }
        raise AssertionError(endpoint)

    monkeypatch.setattr(rustchain_cli, "fetch_api", fake_fetch)

    rustchain_cli.cmd_agent(SimpleNamespace(action="info", agent_id="bcn_beta", json=True, dry_run=False))

    assert seen == ["/beacon/api/agents", "/beacon/api/reputation/bcn_beta"]
    data = json.loads(capsys.readouterr().out)
    assert data["agent_id"] == "bcn_beta"
    assert data["reputation_score"] == 42.5
    assert data["total_earnings_rtc"] == 7.25
    assert data["tasks_completed"] == 3


def test_bounty_list_uses_live_beacon_bounties_endpoint(monkeypatch, capsys):
    seen = []

    def fake_fetch(endpoint):
        seen.append(endpoint)
        assert endpoint == "/beacon/api/bounties"
        return [{"id": "bounty_1", "title": "Fix it", "reward_rtc": 5, "state": "open"}]

    monkeypatch.setattr(rustchain_cli, "fetch_api", fake_fetch)

    rustchain_cli.cmd_bounty(SimpleNamespace(action="list", status=None, json=True, dry_run=False))

    assert seen == ["/beacon/api/bounties"]
    data = json.loads(capsys.readouterr().out)
    assert data[0]["id"] == "bounty_1"
    assert data[0]["status"] == "open"


def test_bounty_info_filters_beacon_bounty_list(monkeypatch, capsys):
    def fake_fetch(endpoint):
        assert endpoint == "/beacon/api/bounties"
        return [
            {"id": "bounty_1", "title": "One", "reward_rtc": 1, "state": "open"},
            {"id": "bounty_2", "title": "Two", "reward_rtc": 2, "state": "completed"},
        ]

    monkeypatch.setattr(rustchain_cli, "fetch_api", fake_fetch)

    rustchain_cli.cmd_bounty(SimpleNamespace(action="info", bounty_id="bounty_2", json=True, dry_run=False))

    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "bounty_2"
    assert data["status"] == "completed"
    assert data["category"] == "general"


def test_missing_agent_raises_api_error(monkeypatch):
    monkeypatch.setattr(rustchain_cli, "fetch_api", lambda endpoint: [])

    with pytest.raises(rustchain_cli.RustChainAPIError, match="Agent not found"):
        rustchain_cli.cmd_agent(SimpleNamespace(action="info", agent_id="bcn_missing", json=True, dry_run=False))
