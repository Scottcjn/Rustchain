// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import aiohttp
import asyncio
import json
import time
import random


class AgentEconomyClient:
    def __init__(self, node_url="http://localhost:5000"):
        self.node_url = node_url.rstrip('/')
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(self, method, path, **kwargs):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        async with self.session.request(method, f"{self.node_url}{path}", **kwargs) as resp:
            return await resp.json()

    async def post_job(self, title, description, reward, category="general", requirements=None):
        """Post a new job to the marketplace"""
        data = {
            'title': title,
            'description': description,
            'reward': reward,
            'category': category,
            'requirements': requirements or {}
        }
        return await self._request('POST', '/api/agent_economy/jobs', json=data)

    async def get_jobs(self, status="open", category=None):
        """Browse available jobs"""
        params = {'status': status}
        if category:
            params['category'] = category
        return await self._request('GET', '/api/agent_economy/jobs', params=params)

    async def claim_job(self, job_id, agent_id):
        """Claim a job for work"""
        data = {'agent_id': agent_id}
        return await self._request('POST', f'/api/agent_economy/jobs/{job_id}/claim', json=data)

    async def deliver_work(self, job_id, deliverable_url, summary):
        """Submit completed work"""
        data = {
            'deliverable_url': deliverable_url,
            'summary': summary
        }
        return await self._request('POST', f'/api/agent_economy/jobs/{job_id}/deliver', json=data)

    async def review_work(self, job_id, accept=True, feedback=""):
        """Accept or reject delivered work"""
        data = {
            'accept': accept,
            'feedback': feedback
        }
        return await self._request('POST', f'/api/agent_economy/jobs/{job_id}/review', json=data)

    async def get_agent_profile(self, agent_id):
        """Get agent profile and reputation"""
        return await self._request('GET', f'/api/agent_economy/agents/{agent_id}')

    async def get_job(self, job_id):
        """Get job details"""
        return await self._request('GET', f'/api/agent_economy/jobs/{job_id}')

    async def cancel_job(self, job_id, reason=""):
        """Cancel a job"""
        data = {'reason': reason}
        return await self._request('POST', f'/api/agent_economy/jobs/{job_id}/cancel', json=data)

    async def dispute_job(self, job_id, reason):
        """Dispute a job delivery"""
        data = {'reason': reason}
        return await self._request('POST', f'/api/agent_economy/jobs/{job_id}/dispute', json=data)


async def main():
    """Example usage of the Agent Economy SDK"""
    async with AgentEconomyClient() as client:
        # Post a job
        job = await client.post_job(
            title="Smart Contract Audit",
            description="Audit our ERC-20 token contract for vulnerabilities",
            reward=5.0,
            category="security"
        )
        print(f"Posted job: {job}")

        # Browse jobs
        jobs = await client.get_jobs(status="open", category="security")
        print(f"Available jobs: {jobs}")

        # Get agent profile
        profile = await client.get_agent_profile("agent_123")
        print(f"Agent profile: {profile}")


if __name__ == "__main__":
    asyncio.run(main())
