# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest


@pytest.fixture()
def agent_economy_cli_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "agent_economy_cli"
        / "rustchain_ae.py"
    )
    spec = importlib.util.spec_from_file_location("rustchain_ae", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return self.payload


def test_api_get_builds_url_and_parses_json(agent_economy_cli_module, monkeypatch):
    calls = []

    def fake_urlopen(request, context, timeout):
        calls.append((request, context, timeout))
        return FakeResponse(b'{"jobs": [{"id": "job-1"}]}')

    monkeypatch.setattr(agent_economy_cli_module, "BASE_URL", "https://node.example")
    monkeypatch.setattr(agent_economy_cli_module.urllib.request, "urlopen", fake_urlopen)

    result = agent_economy_cli_module.api_get("/agent/jobs?status=open")

    assert result == {"jobs": [{"id": "job-1"}]}
    request, context, timeout = calls[0]
    assert request.full_url == "https://node.example/agent/jobs?status=open"
    assert context is agent_economy_cli_module.SSL_CTX
    assert timeout == 15


def test_api_post_sends_json_and_parses_success(agent_economy_cli_module, monkeypatch):
    calls = []

    def fake_urlopen(request, context, timeout):
        calls.append((request, context, timeout))
        return FakeResponse(b'{"claimed": true}')

    monkeypatch.setattr(agent_economy_cli_module, "BASE_URL", "https://node.example")
    monkeypatch.setattr(agent_economy_cli_module.urllib.request, "urlopen", fake_urlopen)

    result = agent_economy_cli_module.api_post(
        "/agent/jobs/job-1/claim",
        {"agent_id": "wallet-1", "proposal": "I can ship it"},
    )

    assert result == {"claimed": True}
    request, context, timeout = calls[0]
    assert request.full_url == "https://node.example/agent/jobs/job-1/claim"
    assert request.get_method() == "POST"
    assert request.data == b'{"agent_id": "wallet-1", "proposal": "I can ship it"}'
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["content-type"] == "application/json"
    assert context is agent_economy_cli_module.SSL_CTX
    assert timeout == 15


def test_api_post_parses_http_error_body(agent_economy_cli_module, monkeypatch):
    def fake_urlopen(_request, context, timeout):
        assert context is agent_economy_cli_module.SSL_CTX
        assert timeout == 15
        raise HTTPError(
            "https://node.example/agent/jobs/job-1/claim",
            400,
            "Bad Request",
            {},
            BytesIO(b'{"error": "already claimed"}'),
        )

    monkeypatch.setattr(agent_economy_cli_module.urllib.request, "urlopen", fake_urlopen)

    assert agent_economy_cli_module.api_post("/agent/jobs/job-1/claim", {}) == {
        "error": "already claimed"
    }


def test_cmd_list_formats_dict_response_and_empty_response(
    agent_economy_cli_module,
    monkeypatch,
    capsys,
):
    responses = iter(
        [
            {
                "jobs": [
                    {
                        "id": "job-12345678901234567890",
                        "reward_rtc": 2.5,
                        "title": "Build an agent economy demo that is long",
                    }
                ]
            },
            [],
        ]
    )
    paths = []

    def fake_api_get(path):
        paths.append(path)
        return next(responses)

    monkeypatch.setattr(agent_economy_cli_module, "api_get", fake_api_get)

    agent_economy_cli_module.cmd_list(SimpleNamespace(status="claimed"))
    agent_economy_cli_module.cmd_list(SimpleNamespace(status=None))

    output = capsys.readouterr().out
    assert paths == ["/agent/jobs?status=claimed", "/agent/jobs?status=open"]
    assert "ID" in output
    assert "Reward" in output
    assert "job-12345678901234" in output
    assert "2.5 RTC" in output
    assert "Build an agent economy demo that is long"[:40] in output
    assert "1 job(s) found." in output
    assert "No jobs found." in output


def test_command_payloads_are_sent_and_printed(
    agent_economy_cli_module,
    monkeypatch,
    capsys,
):
    calls = []

    def fake_api_post(path, payload):
        calls.append((path, payload))
        return {"ok": True, "path": path}

    monkeypatch.setattr(agent_economy_cli_module, "api_post", fake_api_post)

    agent_economy_cli_module.cmd_claim(
        SimpleNamespace(
            job_id="job-1",
            wallet="wallet-1",
            proposal="I will add tests",
        )
    )
    agent_economy_cli_module.cmd_deliver(
        SimpleNamespace(
            job_id="job-2",
            url="https://github.com/example/pr/1",
            summary="Tests added",
        )
    )
    agent_economy_cli_module.cmd_post(
        SimpleNamespace(
            title="New job",
            description="Write a verifier",
            reward=3.0,
            deadline=48,
            wallet="poster-wallet",
            skills="python,pytest",
        )
    )

    assert calls == [
        (
            "/agent/jobs/job-1/claim",
            {"agent_id": "wallet-1", "proposal": "I will add tests"},
        ),
        (
            "/agent/jobs/job-2/deliver",
            {
                "deliverable_url": "https://github.com/example/pr/1",
                "result_summary": "Tests added",
            },
        ),
        (
            "/agent/jobs",
            {
                "title": "New job",
                "description": "Write a verifier",
                "reward_rtc": 3.0,
                "deadline_hours": 48,
                "poster_wallet": "poster-wallet",
                "required_skills": ["python", "pytest"],
            },
        ),
    ]
    output = capsys.readouterr().out
    assert '"ok": true' in output
    assert '"/agent/jobs/job-1/claim"' in output
    assert '"/agent/jobs/job-2/deliver"' in output
    assert '"/agent/jobs"' in output


def test_read_commands_print_json_or_errors(
    agent_economy_cli_module,
    monkeypatch,
    capsys,
):
    responses = {
        "/agent/jobs/job-1": {"id": "job-1", "title": "Demo"},
        "/agent/reputation/wallet-1": {"score": 9},
        "/agent/stats": {"open_jobs": 3},
    }
    paths = []

    def fake_api_get(path):
        paths.append(path)
        if path == "/agent/stats":
            raise RuntimeError("node offline")
        return responses[path]

    monkeypatch.setattr(agent_economy_cli_module, "api_get", fake_api_get)

    agent_economy_cli_module.cmd_show(SimpleNamespace(job_id="job-1"))
    agent_economy_cli_module.cmd_reputation(SimpleNamespace(wallet="wallet-1"))
    agent_economy_cli_module.cmd_stats(SimpleNamespace())

    assert paths == [
        "/agent/jobs/job-1",
        "/agent/reputation/wallet-1",
        "/agent/stats",
    ]
    output = capsys.readouterr().out
    assert '"title": "Demo"' in output
    assert '"score": 9' in output
    assert "Error: node offline" in output
