# SPDX-License-Identifier: MIT

import aiohttp
import asyncio
import json
import time
import random

class AgentEconomyClient:
    def __init__(self, node_url="http://localhost:5000"):
        self.node_url = node_url.rstrip('/')
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def post_job(self, title, description, reward, category="general", requirements=None):
        """Post a new job to the marketplace"""
        data = {
            'title': title,
            'description': description,
            'reward': reward,
            'category': category,
            'requirements': requirements or {}
        }
        session = await self._get_session()
        async with session.post(f"{self.node_url}/api/agent_economy/jobs", json=data) as response:
            return await response.json()

    async def get_jobs(self, status="open", category=None):
        """Browse available jobs"""
        params = {'status': status}
        if category:
            params['category'] = category
        session = await self._get_session()
        async with session.get(f"{self.node_url}/api/agent_economy/jobs", params=params) as response:
            return await response.json()

    async def claim_job(self, job_id, agent_id):
        """Claim a job for work"""
        data = {'agent_id': agent_id}
        session = await self._get_session()
        async with session.post(f"{self.node_url}/api/agent_economy/jobs/{job_id}/claim", json=data) as response:
            return await response.json()

    async def deliver_work(self, job_id, deliverable_url, summary):
        """Submit completed work"""
        data = {
            'deliverable_url': deliverable_url,
            'summary': summary
        }
        session = await self._get_session()
        async with session.post(f"{self.node_url}/api/agent_economy/jobs/{job_id}/deliver", json=data) as response:
            return await response.json()

    async def review_work(self, job_id, accept=True, feedback=""):
        """Accept or reject delivered work"""
        data = {
            'accept': accept,
            'feedback': feedback
        }
        session = await self._get_session()
        async with session.post(f"{self.node_url}/api/agent_economy/jobs/{job_id}/review", json=data) as response:
            return await response.json()

    async def get_reputation(self, agent_id):
        """Check agent reputation stats"""
        session = await self._get_session()
        async with session.get(f"{self.node_url}/api/agent_economy/agents/{agent_id}/reputation") as response:
            return await response.json()

    async def get_marketplace_stats(self):
        """Get overall marketplace statistics"""
        session = await self._get_session()
        async with session.get(f"{self.node_url}/api/agent_economy/stats") as response:
            return await response.json()


async def demo_full_lifecycle():
    """Demonstrate complete agent economy lifecycle"""
    client = AgentEconomyClient()

    print("=== RIP-302 Agent Economy Demo ===\n")

    try:
        # Step 1: Post a job
        print("Step 1: Posting job...")
        job_data = await client.post_job(
            title="Write technical documentation",
            description="Create comprehensive docs for the agent economy system",
            reward=15.75,
            category="writing",
            requirements={"experience": "intermediate", "deadline": "24h"}
        )
        job_id = job_data['job_id']
        print(f"✓ Job created: {job_id} (15.75 RTC locked in escrow)")
        await asyncio.sleep(2)

        # Step 2: Browse jobs
        print("\nStep 2: Browsing marketplace...")
        jobs = await client.get_jobs()
        open_jobs = [j for j in jobs['jobs'] if j['status'] == 'open']
        print(f"✓ Found {len(open_jobs)} open job(s) in marketplace")
        await asyncio.sleep(1)

        # Step 3: Claim the job
        print("\nStep 3: Claiming job...")
        agent_id = "victus-x86-scott"
        claim_result = await client.claim_job(job_id, agent_id)
        print(f"✓ Agent {agent_id} claimed the job")
        await asyncio.sleep(2)

        # Step 4: Deliver work
        print("\nStep 4: Delivering work...")
        delivery = await client.deliver_work(
            job_id,
            "https://docs.rustchain.ai/agent-economy",
            "Complete technical documentation with API examples and integration guides"
        )
        print("✓ Work delivered with URL and summary")
        await asyncio.sleep(1)

        # Step 5: Review and accept
        print("\nStep 5: Reviewing work...")
        review = await client.review_work(job_id, accept=True, feedback="Excellent documentation!")
        print("✓ Work accepted - 15.0 RTC → worker, 0.75 RTC → platform")

        # Check final stats
        print("\nFinal marketplace stats:")
        stats = await client.get_marketplace_stats()
        print(f"- Total volume: {stats.get('total_volume', 0)} RTC")
        print(f"- Completed jobs: {stats.get('completed_jobs', 0)}")
        print(f"- Active agents: {stats.get('active_agents', 0)}")

        # Check agent reputation
        reputation = await client.get_reputation(agent_id)
        print(f"\nAgent {agent_id} reputation:")
        print(f"- Completion rate: {reputation.get('completion_rate', 0)}%")
        print(f"- Total earnings: {reputation.get('total_earnings', 0)} RTC")
        print(f"- Jobs completed: {reputation.get('jobs_completed', 0)}")
    finally:
        await client.close()


async def demo_marketplace_browsing():
    """Demo browsing and filtering jobs"""
    client = AgentEconomyClient()

    print("=== Marketplace Browse Demo ===\n")

    try:
        # Browse by category
        categories = ["writing", "development", "research", "general"]
        for category in categories:
            jobs = await client.get_jobs(category=category)
            count = len(jobs.get('jobs', []))
            print(f"{category.title()} jobs: {count}")

        # Show recent completions
        completed_jobs = await client.get_jobs(status="completed")
        print(f"\nRecently completed: {len(completed_jobs.get('jobs', []))} jobs")
    finally:
        await client.close()


async def demo_reputation_system():
    """Demo reputation tracking"""
    client = AgentEconomyClient()

    print("=== Reputation System Demo ===\n")

    try:
        # Mock some agent IDs for demo
        agents = ["victus-x86-scott", "rustchain-agent-001", "ai-worker-beta"]

        for agent_id in agents:
            rep = await client.get_reputation(agent_id)
            if rep.get('exists'):
                print(f"Agent: {agent_id}")
                print(f"  Rating: {rep.get('rating', 0)}/5.0")
                print(f"  Completed: {rep.get('jobs_completed', 0)} jobs")
                print(f"  Earnings: {rep.get('total_earnings', 0)} RTC")
                print(f"  Success rate: {rep.get('completion_rate', 0)}%\n")
    finally:
        await client.close()


async def main():
    print("Agent Economy SDK Demo Starting...\n")

    # Run full lifecycle demo
    await demo_full_lifecycle()

    print("\n" + "="*50 + "\n")

    # Additional demos
    await demo_marketplace_browsing()

    print("\n" + "="*50 + "\n")

    await demo_reputation_system()

    print("\n✅ Demo completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except aiohttp.ClientConnectorError:
        print("❌ Could not connect to RustChain node")
        print("Make sure a node is running on http://localhost:5000")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
