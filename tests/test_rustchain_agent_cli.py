# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def rustchain_agent_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "sdk" / "rustchain_agent_cli.py"
    spec = importlib.util.spec_from_file_location("rustchain_agent_cli", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_list_jobs_unwraps_live_agent_jobs_envelope(
    rustchain_agent_cli_module, monkeypatch
):
    def fake_get(url, timeout, verify):
        assert url == "https://node.example/agent/jobs"
        assert timeout == 10
        assert verify is False
        return FakeResponse(
            {
                "ok": True,
                "jobs": [
                    {"job_id": "job-code", "title": "Code task", "category": "code"},
                    {
                        "job_id": "job-writing",
                        "title": "Writing task",
                        "category": "writing",
                    },
                ],
            }
        )

    monkeypatch.setattr(rustchain_agent_cli_module.requests, "get", fake_get)

    cli = rustchain_agent_cli_module.RustChainAgentCLI()
    cli.base_url = "https://node.example"

    assert cli.list_jobs(category="code") == [
        {"job_id": "job-code", "title": "Code task", "category": "code"}
    ]


def test_agent_cli_defaults_to_live_agent_node(rustchain_agent_cli_module):
    cli = rustchain_agent_cli_module.RustChainAgentCLI()

    assert cli.base_url == "https://50.28.86.131"
    assert cli.verify_ssl is False


def test_agent_cli_allows_env_node_and_ssl_override(
    rustchain_agent_cli_module, monkeypatch
):
    monkeypatch.setenv("RUSTCHAIN_AGENT_API", "https://agent.example")
    monkeypatch.setenv("RUSTCHAIN_AGENT_VERIFY_SSL", "true")

    cli = rustchain_agent_cli_module.RustChainAgentCLI()

    assert cli.base_url == "https://agent.example"
    assert cli.verify_ssl is True


def test_mutating_agent_requests_use_ssl_mode(rustchain_agent_cli_module, monkeypatch):
    calls = []

    def fake_post(url, json, timeout, verify):
        assert timeout == 10
        assert verify is False
        calls.append((url, json))
        return FakeResponse({"ok": True, "job_id": "job-1"})

    monkeypatch.setattr(rustchain_agent_cli_module.requests, "post", fake_post)

    cli = rustchain_agent_cli_module.RustChainAgentCLI(wallet="worker-wallet")
    cli.base_url = "https://node.example"

    assert cli.post_job("Title", "Description", "code", 5, ["cli"]) == {
        "ok": True,
        "job_id": "job-1",
    }
    assert cli.claim_job("job-1") == {"ok": True, "job_id": "job-1"}
    assert cli.deliver_job("job-1", "https://example.com/pr", "Done") == {
        "ok": True,
        "job_id": "job-1",
    }
    assert calls == [
        (
            "https://node.example/agent/jobs",
            {
                "poster_wallet": "worker-wallet",
                "title": "Title",
                "description": "Description",
                "category": "code",
                "reward_rtc": 5,
                "tags": ["cli"],
            },
        ),
        (
            "https://node.example/agent/jobs/job-1/claim",
            {"worker_wallet": "worker-wallet"},
        ),
        (
            "https://node.example/agent/jobs/job-1/deliver",
            {
                "worker_wallet": "worker-wallet",
                "deliverable_url": "https://example.com/pr",
                "result_summary": "Done",
            },
        ),
    ]


def test_get_job_unwraps_live_agent_job_envelope(rustchain_agent_cli_module, monkeypatch):
    def fake_get(url, timeout, verify):
        assert url == "https://node.example/agent/jobs/job-1"
        assert timeout == 10
        assert verify is False
        return FakeResponse(
            {
                "ok": True,
                "job": {
                    "job_id": "job-1",
                    "title": "Ship a fix",
                    "reward_rtc": 5,
                },
            }
        )

    monkeypatch.setattr(rustchain_agent_cli_module.requests, "get", fake_get)

    cli = rustchain_agent_cli_module.RustChainAgentCLI()
    cli.base_url = "https://node.example"

    assert cli.get_job("job-1") == {
        "job_id": "job-1",
        "title": "Ship a fix",
        "reward_rtc": 5,
    }


def test_get_stats_unwraps_live_agent_stats_envelope(
    rustchain_agent_cli_module, monkeypatch
):
    def fake_get(url, timeout, verify):
        assert url == "https://node.example/agent/stats"
        assert timeout == 10
        assert verify is False
        return FakeResponse(
            {
                "ok": True,
                "stats": {
                    "total_jobs": 4,
                    "open_jobs": 2,
                    "completed_jobs": 1,
                    "total_rtc_volume": 7.5,
                    "active_agents": 3,
                },
            }
        )

    monkeypatch.setattr(rustchain_agent_cli_module.requests, "get", fake_get)

    cli = rustchain_agent_cli_module.RustChainAgentCLI()
    cli.base_url = "https://node.example"

    assert cli.get_stats() == {
        "total_jobs": 4,
        "open_jobs": 2,
        "completed_jobs": 1,
        "total_rtc_volume": 7.5,
        "active_agents": 3,
    }


def test_cmd_list_prints_live_job_id(rustchain_agent_cli_module, monkeypatch, capsys):
    class FakeCLI:
        def __init__(self, wallet):
            assert wallet == "agent-wallet"

        def list_jobs(self, category):
            assert category is None
            return [
                {
                    "job_id": "job-live-123",
                    "title": "Fix live CLI rows",
                    "category": "code",
                    "reward_rtc": 5,
                }
            ]

    monkeypatch.setattr(rustchain_agent_cli_module, "RustChainAgentCLI", FakeCLI)

    rustchain_agent_cli_module.cmd_list(
        SimpleNamespace(wallet="agent-wallet", category=None)
    )

    output = capsys.readouterr().out
    assert "job-live-123" in output
    assert "Fix live CLI rows" in output


def test_cmd_post_prints_live_job_id(rustchain_agent_cli_module, monkeypatch, capsys):
    class FakeCLI:
        def __init__(self, wallet):
            assert wallet == "poster-wallet"

        def post_job(self, title, description, category, reward, tags):
            assert title == "Fix live CLI rows"
            assert description == "Long enough live CLI task description"
            assert category == "code"
            assert reward == 5
            assert tags == ["cli", "agent"]
            return {"ok": True, "job_id": "job-posted-123", "status": "open"}

    monkeypatch.setattr(rustchain_agent_cli_module, "RustChainAgentCLI", FakeCLI)

    rustchain_agent_cli_module.cmd_post(
        SimpleNamespace(
            wallet="poster-wallet",
            title="Fix live CLI rows",
            description="Long enough live CLI task description",
            category="code",
            reward=5,
            tags="cli,agent",
        )
    )

    output = capsys.readouterr().out
    assert "Job ID: job-posted-123" in output
    assert "Title: Fix live CLI rows" in output


def test_cmd_stats_prints_live_total_rtc_volume(
    rustchain_agent_cli_module, monkeypatch, capsys
):
    class FakeCLI:
        def __init__(self, wallet):
            assert wallet == "agent-wallet"

        def get_stats(self):
            return {
                "total_jobs": 4,
                "open_jobs": 2,
                "completed_jobs": 1,
                "total_rtc_volume": 7.5,
                "active_agents": 3,
            }

    monkeypatch.setattr(rustchain_agent_cli_module, "RustChainAgentCLI", FakeCLI)

    rustchain_agent_cli_module.cmd_stats(SimpleNamespace(wallet="agent-wallet"))

    output = capsys.readouterr().out
    assert "Total Volume:   7.5 RTC" in output
