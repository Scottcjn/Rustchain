# SPDX-License-Identifier: MIT

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from aioresponses import aioresponses
import aiohttp

from rustchain_agent_sdk import RustChainAgent, AgentError, JobPostError, NetworkError


class TestRustChainAgent:

    @pytest.fixture
    def agent(self):
        return RustChainAgent(
            agent_id="test-agent-123",
            wallet_address="wallet-abc789",
            base_url="http://localhost:3001"
        )

    @pytest.fixture
    def mock_job_data(self):
        return {
            "job_id": "job_29eab953154daedf",
            "title": "Write technical documentation",
            "description": "Create API docs for blockchain SDK",
            "budget_rtc": 15.75,
            "deadline": "2026-03-12T10:00:00Z",
            "status": "open",
            "poster": "client-wallet-456"
        }

    def test_client_initialization(self, agent):
        assert agent.agent_id == "test-agent-123"
        assert agent.wallet_address == "wallet-abc789"
        assert agent.base_url == "http://localhost:3001"
        assert agent.session is None

    @pytest.mark.asyncio
    async def test_context_manager_session_lifecycle(self, agent):
        async with agent as client:
            assert client.session is not None
            assert isinstance(client.session, aiohttp.ClientSession)
        assert client.session.closed

    @pytest.mark.asyncio
    async def test_job_posting_success(self, agent, mock_job_data):
        with aioresponses() as m:
            m.post(
                "http://localhost:3001/api/jobs/post",
                payload={
                    "ok": True,
                    "job_id": "job_29eab953154daedf",
                    "escrow_total_rtc": 15.75,
                    "status": "open"
                },
                status=200
            )

            async with agent as client:
                result = await client.post_job(
                    title="Write technical documentation",
                    description="Create API docs for blockchain SDK",
                    budget_rtc=15.0,
                    deadline="2026-03-12T10:00:00Z"
                )

            assert result["job_id"] == "job_29eab953154daedf"
            assert result["escrow_total_rtc"] == 15.75

    @pytest.mark.asyncio
    async def test_job_posting_insufficient_funds(self, agent):
        with aioresponses() as m:
            m.post(
                "http://localhost:3001/api/jobs/post",
                payload={"error": "Insufficient balance for escrow"},
                status=400
            )

            async with agent as client:
                with pytest.raises(JobPostError, match="Insufficient balance"):
                    await client.post_job(
                        title="Expensive task",
                        description="High-budget work",
                        budget_rtc=1000.0,
                        deadline="2026-03-15T12:00:00Z"
                    )

    @pytest.mark.asyncio
    async def test_browse_jobs_with_filters(self, agent):
        jobs_data = [
            {
                "job_id": "job_abc123",
                "title": "Python development",
                "budget_rtc": 25.5,
                "status": "open",
                "tags": ["python", "backend"]
            },
            {
                "job_id": "job_def456",
                "title": "Frontend work",
                "budget_rtc": 18.0,
                "status": "open",
                "tags": ["react", "frontend"]
            }
        ]

        with aioresponses() as m:
            m.get(
                "http://localhost:3001/api/jobs/browse?status=open&min_budget=20",
                payload={"jobs": jobs_data, "total": 2},
                status=200
            )

            async with agent as client:
                result = await client.browse_jobs(
                    status="open",
                    min_budget=20.0
                )

            assert len(result["jobs"]) == 2
            assert result["jobs"][0]["job_id"] == "job_abc123"

    @pytest.mark.asyncio
    async def test_claim_job_success(self, agent):
        with aioresponses() as m:
            m.post(
                "http://localhost:3001/api/jobs/job_xyz789/claim",
                payload={
                    "success": True,
                    "job_id": "job_xyz789",
                    "worker": "test-agent-123",
                    "claimed_at": "2026-03-05T14:30:00Z"
                },
                status=200
            )

            async with agent as client:
                result = await client.claim_job("job_xyz789")

            assert result["success"] is True
            assert result["worker"] == "test-agent-123"

    @pytest.mark.asyncio
    async def test_claim_job_already_claimed(self, agent):
        with aioresponses() as m:
            m.post(
                "http://localhost:3001/api/jobs/job_taken123/claim",
                payload={"error": "Job already claimed by another agent"},
                status=409
            )

            async with agent as client:
                with pytest.raises(AgentError, match="already claimed"):
                    await client.claim_job("job_taken123")

    @pytest.mark.asyncio
    async def test_submit_delivery_with_files(self, agent):
        with aioresponses() as m:
            m.post(
                "http://localhost:3001/api/jobs/job_deliver456/deliver",
                payload={
                    "delivery_id": "delivery_abc123",
                    "job_id": "job_deliver456",
                    "submitted_at": "2026-03-05T15:45:00Z",
                    "status": "pending_review"
                },
                status=200
            )

            delivery_data = {
                "summary": "Completed documentation with 15 pages",
                "deliverable_url": "https://docs.example.com/api-v2",
                "notes": "Includes code examples and tutorials"
            }

            async with agent as client:
                result = await client.submit_delivery("job_deliver456", delivery_data)

            assert result["delivery_id"] == "delivery_abc123"
            assert result["status"] == "pending_review"

    @pytest.mark.asyncio
    async def test_get_reputation_stats(self, agent):
        reputation_data = {
            "agent_id": "test-agent-123",
            "total_jobs": 47,
            "completed_jobs": 43,
            "success_rate": 91.5,
            "avg_rating": 4.2,
            "total_earned_rtc": 234.75,
            "reputation_score": 892
        }

        with aioresponses() as m:
            m.get(
                "http://localhost:3001/api/agents/test-agent-123/reputation",
                payload=reputation_data,
                status=200
            )

            async with agent as client:
                result = await client.get_reputation()

            assert result["success_rate"] == 91.5
            assert result["total_earned_rtc"] == 234.75
            assert result["reputation_score"] == 892

    @pytest.mark.asyncio
    async def test_network_error_handling(self, agent):
        with aioresponses() as m:
            m.get(
                "http://localhost:3001/api/jobs/browse",
                exception=aiohttp.ClientConnectorError(
                    connection_key=MagicMock(),
                    os_error=OSError("Connection refused")
                )
            )

            async with agent as client:
                with pytest.raises(NetworkError, match="Network connection failed"):
                    await client.browse_jobs()

    @pytest.mark.asyncio
    async def test_server_error_retry_logic(self, agent):
        with aioresponses() as m:
            # First call fails with 503, second succeeds
            m.get(
                "http://localhost:3001/api/agents/test-agent-123/balance",
                payload={"error": "Service temporarily unavailable"},
                status=503
            )
            m.get(
                "http://localhost:3001/api/agents/test-agent-123/balance",
                payload={"balance_rtc": 45.25, "miner_id": "test-agent-123"},
                status=200
            )

            async with agent as client:
                result = await client.get_balance()

            assert result["balance_rtc"] == 45.25

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, agent):
        with aioresponses() as m:
            # Mock multiple endpoints
            m.get(
                "http://localhost:3001/api/agents/test-agent-123/balance",
                payload={"balance_rtc": 100.0}
            )
            m.get(
                "http://localhost:3001/api/agents/test-agent-123/reputation",
                payload={"reputation_score": 850}
            )
            m.get(
                "http://localhost:3001/api/jobs/browse",
                payload={"jobs": [], "total": 0}
            )

            async with agent as client:
                balance_task = client.get_balance()
                reputation_task = client.get_reputation()
                browse_task = client.browse_jobs()

                balance, reputation, jobs = await asyncio.gather(
                    balance_task, reputation_task, browse_task
                )

            assert balance["balance_rtc"] == 100.0
            assert reputation["reputation_score"] == 850
            assert jobs["total"] == 0

    def test_invalid_agent_initialization(self):
        with pytest.raises(ValueError, match="agent_id cannot be empty"):
            RustChainAgent("", "wallet123", "http://localhost:3001")

        with pytest.raises(ValueError, match="Invalid base_url format"):
            RustChainAgent("agent1", "wallet123", "not-a-url")
