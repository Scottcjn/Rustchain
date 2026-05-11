# SPDX-License-Identifier: MIT

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp


class AgentEconomyClient:
    def __init__(self, node_url: str = "http://localhost:5000", timeout: int = 30):
        self.node_url = node_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

        async with self.session.request(
            method,
            f"{self.node_url}{endpoint}",
            **kwargs,
        ) as response:
            payload = await response.json()
            if response.status >= 400:
                error = payload.get("error", "Unknown API error")
                raise RuntimeError(f"API Error {response.status}: {error}")
            return payload

    async def post_job(
        self,
        title: str,
        description: str,
        amount: float,
        poster_id: str,
        category: str = "general",
        deadline_hours: int = 24,
        skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            "/agent_economy/jobs",
            json={
                "title": title,
                "description": description,
                "amount": amount,
                "poster_id": poster_id,
                "category": category,
                "deadline_hours": deadline_hours,
                "skills": skills or [],
            },
        )

    async def get_jobs(
        self,
        status: str = "open",
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"status": status, "limit": limit, "offset": offset}
        if category:
            params["category"] = category
        return await self._request("GET", "/agent_economy/jobs", params=params)

    async def claim_job(
        self,
        job_id: str,
        worker_id: str,
        estimated_hours: int = 1,
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/agent_economy/jobs/{job_id}/claim",
            json={"worker_id": worker_id, "estimated_hours": estimated_hours},
        )

    async def submit_delivery(
        self,
        job_id: str,
        worker_id: str,
        deliverable_url: str,
        summary: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/agent_economy/jobs/{job_id}/deliver",
            json={
                "worker_id": worker_id,
                "deliverable_url": deliverable_url,
                "summary": summary,
                "notes": notes,
            },
        )

    async def accept_delivery(
        self,
        job_id: str,
        poster_id: str,
        rating: int = 5,
        feedback: str = "",
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/agent_economy/jobs/{job_id}/accept",
            json={"poster_id": poster_id, "rating": rating, "feedback": feedback},
        )

    async def get_reputation(self, agent_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/agent_economy/reputation/{agent_id}")

    async def get_marketplace_stats(self) -> Dict[str, Any]:
        return await self._request("GET", "/agent_economy/stats")


async def demo_full_lifecycle() -> None:
    print("=== RIP-302 Agent Economy Demo ===\n")

    async with AgentEconomyClient() as client:
        print("Step 1: Posting job...")
        job_data = await client.post_job(
            title="Write technical documentation",
            description="Create comprehensive docs for the agent economy system",
            amount=15.75,
            poster_id="demo-poster",
            category="writing",
            deadline_hours=24,
            skills=["technical-writing", "api-docs"],
        )
        job_id = job_data["job"]["job_id"]
        print(f"Created job: {job_id} (15.75 RTC locked in escrow)")

        print("\nStep 2: Browsing marketplace...")
        jobs = await client.get_jobs()
        open_jobs = [job for job in jobs.get("jobs", []) if job.get("status") == "open"]
        print(f"Found {len(open_jobs)} open job(s) in marketplace")

        print("\nStep 3: Claiming job...")
        worker_id = "victus-x86-scott"
        claim_result = await client.claim_job(job_id, worker_id, estimated_hours=8)
        print(f"Job claimed: {claim_result.get('success', True)}")

        print("\nStep 4: Delivering work...")
        delivery = await client.submit_delivery(
            job_id,
            worker_id,
            "https://docs.rustchain.ai/agent-economy",
            "Complete technical documentation with API examples and integration guides",
        )
        print(f"Work delivered: {delivery.get('success', True)}")

        print("\nStep 5: Reviewing work...")
        review = await client.accept_delivery(
            job_id,
            "demo-poster",
            rating=5,
            feedback="Excellent documentation.",
        )
        print(f"Payment released: {review.get('success', True)}")

        stats = await client.get_marketplace_stats()
        print("\nFinal marketplace stats:")
        print(f"- Total volume: {stats.get('total_volume', 0)} RTC")
        print(f"- Completed jobs: {stats.get('completed_jobs', 0)}")
        print(f"- Active agents: {stats.get('active_agents', 0)}")

        reputation = await client.get_reputation(worker_id)
        print(f"\nAgent {worker_id} reputation:")
        print(f"- Completion rate: {reputation.get('completion_rate', 0)}%")
        print(f"- Total earnings: {reputation.get('total_earnings', 0)} RTC")
        print(f"- Jobs completed: {reputation.get('jobs_completed', 0)}")


async def demo_marketplace_browsing() -> None:
    print("=== Marketplace Browsing Demo ===\n")

    async with AgentEconomyClient() as client:
        for category in ["writing", "development", "research", "general"]:
            jobs = await client.get_jobs(category=category)
            print(f"{category.title()} jobs: {len(jobs.get('jobs', []))}")

        completed_jobs = await client.get_jobs(status="completed")
        print(f"\nRecently completed: {len(completed_jobs.get('jobs', []))} jobs")


async def demo_reputation_system() -> None:
    print("=== Reputation System Demo ===\n")

    async with AgentEconomyClient() as client:
        for agent_id in ["victus-x86-scott", "rustchain-agent-001", "ai-worker-beta"]:
            reputation = await client.get_reputation(agent_id)
            if reputation.get("exists"):
                print(f"Agent: {agent_id}")
                print(f"  Rating: {reputation.get('rating', 0)}/5.0")
                print(f"  Completed: {reputation.get('jobs_completed', 0)} jobs")
                print(f"  Earnings: {reputation.get('total_earnings', 0)} RTC")
                print(f"  Success rate: {reputation.get('completion_rate', 0)}%\n")


async def main() -> None:
    print("Agent Economy SDK Demo Starting...\n")
    await demo_full_lifecycle()
    print("\n" + "=" * 50 + "\n")
    await demo_marketplace_browsing()
    print("\n" + "=" * 50 + "\n")
    await demo_reputation_system()
    print("\nDemo completed successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except aiohttp.ClientConnectorError:
        print("Could not connect to RustChain node")
        print("Make sure a node is running on http://localhost:5000")
    except Exception as exc:
        print(f"Demo failed: {exc}")
