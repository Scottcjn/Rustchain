# SPDX-License-Identifier: MIT

import agent_sdk_demo


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_client_strips_trailing_slash_and_posts_job_defaults(monkeypatch):
    calls = []

    def fake_post(url, json):
        calls.append((url, json))
        return FakeResponse({"job_id": "job-1"})

    monkeypatch.setattr(agent_sdk_demo.requests, "post", fake_post)

    client = agent_sdk_demo.AgentEconomyClient("http://node.local/")
    result = client.post_job("Docs", "Write docs", 3.5)

    assert result == {"job_id": "job-1"}
    assert calls == [
        (
            "http://node.local/api/agent_economy/jobs",
            {
                "title": "Docs",
                "description": "Write docs",
                "reward": 3.5,
                "category": "general",
                "requirements": {},
            },
        )
    ]


def test_get_jobs_includes_status_and_optional_category(monkeypatch):
    calls = []

    def fake_get(url, params=None):
        calls.append((url, params))
        return FakeResponse({"jobs": []})

    monkeypatch.setattr(agent_sdk_demo.requests, "get", fake_get)

    client = agent_sdk_demo.AgentEconomyClient("http://node.local")
    assert client.get_jobs(status="completed", category="writing") == {"jobs": []}

    assert calls == [
        (
            "http://node.local/api/agent_economy/jobs",
            {"status": "completed", "category": "writing"},
        )
    ]


def test_claim_deliver_and_review_use_expected_payloads(monkeypatch):
    calls = []

    def fake_post(url, json):
        calls.append((url, json))
        return FakeResponse({"ok": True})

    monkeypatch.setattr(agent_sdk_demo.requests, "post", fake_post)

    client = agent_sdk_demo.AgentEconomyClient("http://node.local")

    assert client.claim_job("job-1", "agent-a") == {"ok": True}
    assert client.deliver_work("job-1", "https://example.com/pr", "done") == {"ok": True}
    assert client.review_work("job-1", accept=False, feedback="needs tests") == {"ok": True}

    assert calls == [
        (
            "http://node.local/api/agent_economy/jobs/job-1/claim",
            {"agent_id": "agent-a"},
        ),
        (
            "http://node.local/api/agent_economy/jobs/job-1/deliver",
            {"deliverable_url": "https://example.com/pr", "summary": "done"},
        ),
        (
            "http://node.local/api/agent_economy/jobs/job-1/review",
            {"accept": False, "feedback": "needs tests"},
        ),
    ]


def test_reputation_and_stats_read_from_expected_endpoints(monkeypatch):
    calls = []

    def fake_get(url, params=None):
        calls.append((url, params))
        return FakeResponse({"url": url})

    monkeypatch.setattr(agent_sdk_demo.requests, "get", fake_get)

    client = agent_sdk_demo.AgentEconomyClient("http://node.local")
    reputation = client.get_reputation("agent-a")
    stats = client.get_marketplace_stats()

    assert reputation == {
        "url": "http://node.local/api/agent_economy/agents/agent-a/reputation"
    }
    assert stats == {"url": "http://node.local/api/agent_economy/stats"}
    assert calls == [
        ("http://node.local/api/agent_economy/agents/agent-a/reputation", None),
        ("http://node.local/api/agent_economy/stats", None),
    ]
