# SPDX-License-Identifier: MIT

import asyncio
import inspect

import agent_sdk_demo


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []
        self.responses = [
            {"job_id": "job-1"},
            {"jobs": []},
            {"ok": True},
            {"ok": True},
            {"ok": True},
            {"stats": {"total_jobs": 1}},
            {"reputation": None},
        ]
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse(self.responses.pop(0))

    async def close(self):
        self.closed = True


def run(coro):
    return asyncio.run(coro)


def test_client_methods_are_async():
    for method_name in (
        "post_job",
        "get_jobs",
        "claim_job",
        "deliver_work",
        "accept_delivery",
        "get_marketplace_stats",
        "get_reputation",
    ):
        method = getattr(agent_sdk_demo.AgentEconomyClient, method_name)
        assert inspect.iscoroutinefunction(method), method_name


def test_async_client_uses_live_rip302_routes_and_payloads():
    session = FakeSession()
    client = agent_sdk_demo.AgentEconomyClient("http://node.local/", session=session)

    async def exercise_client():
        assert await client.post_job(
            "Write docs",
            "Write complete API docs for the live RIP-302 routes",
            3.5,
            poster_wallet="poster-1",
            category="code",
            ttl_seconds=7200,
            tags=["docs", "api"],
        ) == {"job_id": "job-1"}
        assert await client.get_jobs(status="delivered", category="code", limit=25) == {
            "jobs": []
        }
        assert await client.claim_job("job-1", "worker-1") == {"ok": True}
        assert await client.deliver_work(
            "job-1",
            "worker-1",
            deliverable_url="https://github.com/example/pr/1",
            result_summary="Implemented with tests",
        ) == {"ok": True}
        assert await client.accept_delivery("job-1", "poster-1", rating=5) == {
            "ok": True
        }
        assert await client.get_marketplace_stats() == {"stats": {"total_jobs": 1}}
        assert await client.get_reputation("worker-1") == {"reputation": None}

    run(exercise_client())

    assert session.calls == [
        (
            "POST",
            "http://node.local/agent/jobs",
            {
                "json": {
                    "poster_wallet": "poster-1",
                    "title": "Write docs",
                    "description": "Write complete API docs for the live RIP-302 routes",
                    "reward_rtc": 3.5,
                    "category": "code",
                    "ttl_seconds": 7200,
                    "tags": ["docs", "api"],
                }
            },
        ),
        (
            "GET",
            "http://node.local/agent/jobs",
            {
                "params": {
                    "status": "delivered",
                    "limit": 25,
                    "offset": 0,
                    "min_reward": 0,
                    "category": "code",
                }
            },
        ),
        (
            "POST",
            "http://node.local/agent/jobs/job-1/claim",
            {"json": {"worker_wallet": "worker-1"}},
        ),
        (
            "POST",
            "http://node.local/agent/jobs/job-1/deliver",
            {
                "json": {
                    "worker_wallet": "worker-1",
                    "deliverable_url": "https://github.com/example/pr/1",
                    "result_summary": "Implemented with tests",
                }
            },
        ),
        (
            "POST",
            "http://node.local/agent/jobs/job-1/accept",
            {"json": {"poster_wallet": "poster-1", "rating": 5}},
        ),
        ("GET", "http://node.local/agent/stats", {}),
        ("GET", "http://node.local/agent/reputation/worker-1", {}),
    ]


def test_context_manager_closes_owned_session(monkeypatch):
    created_sessions = []

    class FakeClientSession(FakeSession):
        def __init__(self, timeout=None):
            super().__init__()
            self.timeout = timeout
            created_sessions.append(self)

    monkeypatch.setattr(agent_sdk_demo.aiohttp, "ClientSession", FakeClientSession)

    async def use_context_manager():
        async with agent_sdk_demo.AgentEconomyClient("http://node.local") as client:
            assert client.session is created_sessions[0]
            assert await client.get_marketplace_stats() == {"job_id": "job-1"}
        assert created_sessions[0].closed is True

    run(use_context_manager())
