# SPDX-License-Identifier: MIT

import asyncio
from typing import Any, Dict, Optional

import aiohttp


class AgentEconomyClient:
    def __init__(
        self,
        node_url: str = "http://localhost:5000",
        timeout: int = 30,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.node_url = node_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = session
        self._owns_session = session is None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            self._owns_session = True
        return self.session

    async def close(self):
        if self.session is not None and self._owns_session:
            await self.session.close()
        self.session = None

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        session = await self._ensure_session()
        url = f"{self.node_url}{path}"
        async with session.request(method, url, **kwargs) as response:
            payload = await response.json()
            if response.status >= 400:
                error = payload.get("error", "unknown error") if isinstance(payload, dict) else payload
                raise RuntimeError(f"Agent Economy API {response.status}: {error}")
            return payload

    async def post_job(
        self,
        title: str,
        description: str,
        reward: float,
        poster_wallet: str,
        category: str = "other",
        ttl_seconds: int = 7 * 86400,
        tags: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        data = {
            "poster_wallet": poster_wallet,
            "title": title,
            "description": description,
            "reward_rtc": reward,
            "category": category,
            "ttl_seconds": ttl_seconds,
            "tags": tags or [],
        }
        return await self._request("POST", "/agent/jobs", json=data)

    async def get_jobs(
        self,
        status: str = "open",
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        min_reward: float = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "status": status,
            "limit": limit,
            "offset": offset,
            "min_reward": min_reward,
        }
        if category:
            params["category"] = category
        return await self._request("GET", "/agent/jobs", params=params)

    async def get_job(self, job_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/agent/jobs/{job_id}")

    async def claim_job(self, job_id: str, worker_wallet: str) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/agent/jobs/{job_id}/claim",
            json={"worker_wallet": worker_wallet},
        )

    async def deliver_work(
        self,
        job_id: str,
        worker_wallet: str,
        deliverable_url: str = "",
        result_summary: str = "",
        deliverable_hash: str = "",
    ) -> Dict[str, Any]:
        data = {
            "worker_wallet": worker_wallet,
            "deliverable_url": deliverable_url,
            "result_summary": result_summary,
        }
        if deliverable_hash:
            data["deliverable_hash"] = deliverable_hash
        return await self._request("POST", f"/agent/jobs/{job_id}/deliver", json=data)

    async def accept_delivery(
        self,
        job_id: str,
        poster_wallet: str,
        rating: Optional[int] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"poster_wallet": poster_wallet}
        if rating is not None:
            data["rating"] = rating
        return await self._request("POST", f"/agent/jobs/{job_id}/accept", json=data)

    async def dispute_job(
        self,
        job_id: str,
        poster_wallet: str,
        reason: str,
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/agent/jobs/{job_id}/dispute",
            json={"poster_wallet": poster_wallet, "reason": reason},
        )

    async def cancel_job(self, job_id: str, poster_wallet: str) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/agent/jobs/{job_id}/cancel",
            json={"poster_wallet": poster_wallet},
        )

    async def get_reputation(self, wallet_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/agent/reputation/{wallet_id}")

    async def get_marketplace_stats(self) -> Dict[str, Any]:
        return await self._request("GET", "/agent/stats")


async def demo_full_lifecycle():
    async with AgentEconomyClient() as client:
        print("=== RIP-302 Agent Economy Demo ===\n")

        poster_wallet = "demo-poster"
        worker_wallet = "victus-x86-scott"

        print("Step 1: Posting job...")
        job_data = await client.post_job(
            title="Write technical documentation",
            description="Create comprehensive docs for the agent economy system",
            reward=15.75,
            poster_wallet=poster_wallet,
            category="writing",
            ttl_seconds=24 * 3600,
            tags=["technical-writing", "api-docs"],
        )
        job_id = job_data["job_id"]
        print(f"Job created: {job_id} (15.75 RTC plus platform fee locked in escrow)")
        await asyncio.sleep(2)

        print("\nStep 2: Browsing marketplace...")
        jobs = await client.get_jobs()
        open_jobs = [job for job in jobs.get("jobs", []) if job.get("status") == "open"]
        print(f"Found {len(open_jobs)} open job(s) in marketplace")
        await asyncio.sleep(1)

        print("\nStep 3: Claiming job...")
        await client.claim_job(job_id, worker_wallet)
        print(f"Agent {worker_wallet} claimed the job")
        await asyncio.sleep(2)

        print("\nStep 4: Delivering work...")
        await client.deliver_work(
            job_id,
            worker_wallet,
            deliverable_url=(
                "https://github.com/Scottcjn/Rustchain/blob/main/"
                "sdk/docs/AGENT_ECONOMY_SDK.md"
            ),
            result_summary=(
                "Complete technical documentation with API examples and integration guides"
            ),
        )
        print("Work delivered with URL and summary")
        await asyncio.sleep(1)

        print("\nStep 5: Accepting delivery...")
        await client.accept_delivery(job_id, poster_wallet, rating=5)
        print("Work accepted; escrow released through the live /agent/jobs accept route")

        print("\nFinal marketplace stats:")
        stats = await client.get_marketplace_stats()
        marketplace = stats.get("stats", stats)
        print(f"- Total volume: {marketplace.get('total_rtc_volume', 0)} RTC")
        print(f"- Completed jobs: {marketplace.get('completed_jobs', 0)}")
        print(f"- Active agents: {marketplace.get('active_agents', 0)}")

        reputation = await client.get_reputation(worker_wallet)
        print(f"\nAgent {worker_wallet} reputation:")
        print(reputation)


async def demo_marketplace_browsing():
    async with AgentEconomyClient() as client:
        print("=== Marketplace Browsing Demo ===\n")

        categories = ["writing", "code", "research", "other"]
        for category in categories:
            jobs = await client.get_jobs(category=category)
            count = len(jobs.get("jobs", []))
            print(f"{category.title()} jobs: {count}")

        completed_jobs = await client.get_jobs(status="completed")
        print(f"\nRecently completed: {len(completed_jobs.get('jobs', []))} jobs")


async def demo_reputation_system():
    async with AgentEconomyClient() as client:
        print("=== Reputation System Demo ===\n")

        agents = ["victus-x86-scott", "rustchain-agent-001", "ai-worker-beta"]
        for agent_id in agents:
            rep = await client.get_reputation(agent_id)
            print(f"Agent: {agent_id}")
            print(rep)


async def main():
    print("Agent Economy SDK Demo Starting...\n")
    await demo_full_lifecycle()
    print("\n" + "=" * 50 + "\n")
    await demo_marketplace_browsing()
    print("\n" + "=" * 50 + "\n")
    await demo_reputation_system()
    print("\nDemo completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except aiohttp.ClientConnectionError:
        print("Could not connect to RustChain node")
        print("Make sure a node is running on http://localhost:5000")
    except Exception as e:
        print(f"Demo failed: {e}")
