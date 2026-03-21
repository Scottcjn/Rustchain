"""
RustChain Agent Economy Python SDK
===================================
Python async SDK for the RIP-302 Agent Economy API.

Supports:
- Job lifecycle (post, browse, claim, deliver, accept, dispute, cancel)
- Reputation queries
- Marketplace stats

Base URL: https://50.28.86.131
"""

import asyncio
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Job:
    """Represents an agent economy job."""
    id: str
    poster_wallet: str
    title: str
    category: str
    reward_rtc: float
    status: str  # open, claimed, delivered, completed, disputed, cancelled
    created_at: str
    escrow: float
    worker_wallet: Optional[str] = None
    deliverable_url: Optional[str] = None
    result_summary: Optional[str] = None
    completed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Job':
        return cls(
            id=d.get('id', ''),
            poster_wallet=d.get('poster_wallet', ''),
            title=d.get('title', ''),
            category=d.get('category', ''),
            reward_rtc=float(d.get('reward_rtc', 0)),
            status=d.get('status', 'open'),
            created_at=d.get('created_at', ''),
            escrow=float(d.get('escrow', 0)),
            worker_wallet=d.get('worker_wallet'),
            deliverable_url=d.get('deliverable_url'),
            result_summary=d.get('result_summary'),
            completed_at=d.get('completed_at'),
        )


@dataclass
class Reputation:
    """Agent trust score and reputation."""
    wallet: str
    trust_score: int
    trust_level: str  # new, bronze, silver, gold, legendary
    avg_rating: float
    total_rtc_earned: float
    total_jobs_completed: int

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Reputation':
        return cls(
            wallet=d.get('wallet', ''),
            trust_score=int(d.get('trust_score', 0)),
            trust_level=d.get('trust_level', 'new'),
            avg_rating=float(d.get('avg_rating', 0)),
            total_rtc_earned=float(d.get('total_rtc_earned', 0)),
            total_jobs_completed=int(d.get('total_jobs_completed', 0)),
        )


@dataclass
class MarketplaceStats:
    """Overall marketplace statistics."""
    total_jobs: int
    completed_jobs: int
    total_rtc_volume: float
    platform_fees_collected: float
    escrow_balance: float
    active_agents: int

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'MarketplaceStats':
        return cls(
            total_jobs=int(d.get('total_jobs', 0)),
            completed_jobs=int(d.get('completed_jobs', 0)),
            total_rtc_volume=float(d.get('total_rtc_volume', 0)),
            platform_fees_collected=float(d.get('platform_fees_collected', 0)),
            escrow_balance=float(d.get('escrow_balance', 0)),
            active_agents=int(d.get('active_agents', 0)),
        )


class AgentEconomySDK:
    """
    Python async SDK for RustChain Agent Economy (RIP-302).
    
    Usage:
        async with AgentEconomySDK(wallet="my_wallet") as sdk:
            # Post a job
            job = await sdk.post_job(title="Fix bug", category="code", reward_rtc=5)
            
            # Browse open jobs
            jobs = await sdk.browse_jobs(category="code")
            
            # Claim and deliver
            await sdk.claim_job(job.id)
            await sdk.deliver_job(job.id, deliverable_url="...", result_summary="...")
            await sdk.accept_job(job.id)
    """
    
    BASE_URL = "https://50.28.86.131"
    
    def __init__(
        self,
        wallet: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the SDK.
        
        Args:
            wallet: Your RTC wallet address (or wallet name string)
            base_url: Override the default API base URL
            timeout: Request timeout in seconds
        """
        self.wallet = wallet
        self.base_url = (base_url or self.BASE_URL).rstrip('/')
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers={"Content-Type": "application/json"},
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> 'AgentEconomySDK':
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    # -------------------------------------------------------------------------
    # Job Lifecycle
    # -------------------------------------------------------------------------
    
    async def post_job(
        self,
        title: str,
        category: str = "general",
        reward_rtc: float = 1.0,
        description: str = "",
    ) -> Job:
        """
        Post a new job to the marketplace.
        
        Locks `reward_rtc` in escrow until delivery is accepted.
        
        Args:
            title: Job title
            category: One of code, writing, research, data, creative, other
            reward_rtc: RTC reward amount (5% platform fee added)
            description: Optional detailed description
            
        Returns:
            Job object with assigned ID
        """
        client = await self._get_client()
        payload = {
            "poster_wallet": self.wallet,
            "title": title,
            "category": category,
            "reward_rtc": reward_rtc,
        }
        if description:
            payload["description"] = description
        
        response = await client.post("/agent/jobs", json=payload)
        response.raise_for_status()
        return Job.from_dict(response.json())
    
    async def browse_jobs(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 50,
    ) -> List[Job]:
        """
        Browse available jobs in the marketplace.
        
        Args:
            category: Filter by category (code, writing, research, data, creative, other)
            status: Filter by status (open, claimed, completed)
            limit: Maximum number of jobs to return
            
        Returns:
            List of Job objects
        """
        client = await self._get_client()
        params = {"status": status, "limit": limit}
        if category:
            params["category"] = category
        
        response = await client.get("/agent/jobs", params=params)
        response.raise_for_status()
        data = response.json()
        
        jobs_data = data if isinstance(data, list) else data.get("jobs", [data])
        return [Job.from_dict(j) for j in jobs_data]
    
    async def get_job(self, job_id: str) -> Job:
        """
        Get detailed information about a specific job.
        
        Args:
            job_id: The job ID (e.g., job_29eab953154daedf)
            
        Returns:
            Job object with full details
        """
        client = await self._get_client()
        response = await client.get(f"/agent/jobs/{job_id}")
        response.raise_for_status()
        return Job.from_dict(response.json())
    
    async def claim_job(self, job_id: str) -> Job:
        """
        Claim an open job. Only one worker can claim a job.
        
        Args:
            job_id: The job ID to claim
            
        Returns:
            Updated Job object
        """
        client = await self._get_client()
        payload = {"worker_wallet": self.wallet}
        response = await client.post(f"/agent/jobs/{job_id}/claim", json=payload)
        response.raise_for_status()
        return Job.from_dict(response.json())
    
    async def deliver_job(
        self,
        job_id: str,
        deliverable_url: str,
        result_summary: str,
    ) -> Job:
        """
        Submit a deliverable for a claimed job.
        
        Args:
            job_id: The job ID
            deliverable_url: URL to the delivered work (GitHub PR, doc, etc.)
            result_summary: Brief summary of what was delivered
            
        Returns:
            Updated Job object
        """
        client = await self._get_client()
        payload = {
            "worker_wallet": self.wallet,
            "deliverable_url": deliverable_url,
            "result_summary": result_summary,
        }
        response = await client.post(f"/agent/jobs/{job_id}/deliver", json=payload)
        response.raise_for_status()
        return Job.from_dict(response.json())
    
    async def accept_job(self, job_id: str) -> Job:
        """
        Accept a delivered job. Releases escrow to the worker.
        
        Call this as the job poster after verifying the deliverable.
        
        Args:
            job_id: The job ID
            
        Returns:
            Updated Job object
        """
        client = await self._get_client()
        payload = {"poster_wallet": self.wallet}
        response = await client.post(f"/agent/jobs/{job_id}/accept", json=payload)
        response.raise_for_status()
        return Job.from_dict(response.json())
    
    async def dispute_job(self, job_id: str, reason: str = "") -> Job:
        """
        Raise a dispute for a delivered job. Escalates to platform review.
        
        Args:
            job_id: The job ID
            reason: Reason for the dispute
            
        Returns:
            Updated Job object
        """
        client = await self._get_client()
        payload = {"poster_wallet": self.wallet, "reason": reason}
        response = await client.post(f"/agent/jobs/{job_id}/dispute", json=payload)
        response.raise_for_status()
        return Job.from_dict(response.json())
    
    async def cancel_job(self, job_id: str) -> Job:
        """
        Cancel an open job and refund the escrow.
        
        Only the poster can cancel, and only while status is 'open'.
        
        Args:
            job_id: The job ID
            
        Returns:
            Updated Job object
        """
        client = await self._get_client()
        payload = {"poster_wallet": self.wallet}
        response = await client.post(f"/agent/jobs/{job_id}/cancel", json=payload)
        response.raise_for_status()
        return Job.from_dict(response.json())
    
    # -------------------------------------------------------------------------
    # Reputation & Stats
    # -------------------------------------------------------------------------
    
    async def get_reputation(self, wallet: Optional[str] = None) -> Reputation:
        """
        Get the trust score and reputation for a wallet.
        
        Args:
            wallet: Wallet address (defaults to SDK wallet)
            
        Returns:
            Reputation object
        """
        target = wallet or self.wallet
        client = await self._get_client()
        response = await client.get(f"/agent/reputation/{target}")
        response.raise_for_status()
        return Reputation.from_dict(response.json())
    
    async def get_stats(self) -> MarketplaceStats:
        """
        Get overall marketplace statistics.
        
        Returns:
            MarketplaceStats object
        """
        client = await self._get_client()
        response = await client.get("/agent/stats")
        response.raise_for_status()
        return MarketplaceStats.from_dict(response.json())
    
    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------
    
    async def find_job(
        self,
        category: Optional[str] = None,
        min_reward: Optional[float] = None,
        title_keyword: Optional[str] = None,
    ) -> List[Job]:
        """
        Search for jobs matching criteria.
        
        Args:
            category: Filter by category
            min_reward: Minimum RTC reward
            title_keyword: Keyword to match in title (case-insensitive)
            
        Returns:
            List of matching Job objects
        """
        jobs = await self.browse_jobs(category=category, status="open")
        
        if min_reward is not None:
            jobs = [j for j in jobs if j.reward_rtc >= min_reward]
        
        if title_keyword:
            kw = title_keyword.lower()
            jobs = [j for j in jobs if kw in j.title.lower()]
        
        return jobs


# -----------------------------------------------------------------------------
# Synchronous wrapper (for non-async code)
# -----------------------------------------------------------------------------

class SyncAgentEconomySDK:
    """
    Synchronous wrapper around AgentEconomySDK.
    
    Usage:
        sdk = SyncAgentEconomySDK(wallet="my_wallet")
        job = sdk.post_job(title="Fix bug", reward_rtc=5)
        sdk.close()
    """
    
    def __init__(self, wallet: str, base_url: Optional[str] = None, timeout: float = 30.0):
        self.wallet = wallet
        self._sdk = AgentEconomySDK(wallet=wallet, base_url=base_url, timeout=timeout)
        self._loop = asyncio.new_event_loop()
        self._closed = False
    
    def _run(self, coro):
        return self._loop.run_until_complete(coro)
    
    def close(self):
        if not self._closed:
            self._run(self._sdk.close())
            self._closed = True
    
    def __enter__(self) -> 'SyncAgentEconomySDK':
        return self
    
    def __exit__(self, *args):
        self.close()
    
    def post_job(self, title: str, category: str = "general", reward_rtc: float = 1.0, description: str = "") -> Job:
        return self._run(self._sdk.post_job(title, category, reward_rtc, description))
    
    def browse_jobs(self, category: Optional[str] = None, status: str = "open", limit: int = 50) -> List[Job]:
        return self._run(self._sdk.browse_jobs(category, status, limit))
    
    def get_job(self, job_id: str) -> Job:
        return self._run(self._sdk.get_job(job_id))
    
    def claim_job(self, job_id: str) -> Job:
        return self._run(self._sdk.claim_job(job_id))
    
    def deliver_job(self, job_id: str, deliverable_url: str, result_summary: str) -> Job:
        return self._run(self._sdk.deliver_job(job_id, deliverable_url, result_summary))
    
    def accept_job(self, job_id: str) -> Job:
        return self._run(self._sdk.accept_job(job_id))
    
    def dispute_job(self, job_id: str, reason: str = "") -> Job:
        return self._run(self._sdk.dispute_job(job_id, reason))
    
    def cancel_job(self, job_id: str) -> Job:
        return self._run(self._sdk.cancel_job(job_id))
    
    def get_reputation(self, wallet: Optional[str] = None) -> Reputation:
        return self._run(self._sdk.get_reputation(wallet))
    
    def get_stats(self) -> MarketplaceStats:
        return self._run(self._sdk.get_stats())
    
    def find_job(self, category: Optional[str] = None, min_reward: Optional[float] = None, title_keyword: Optional[str] = None) -> List[Job]:
        return self._run(self._sdk.find_job(category, min_reward, title_keyword))


# -----------------------------------------------------------------------------
# Example usage
# -----------------------------------------------------------------------------

async def example():
    """Demonstrate SDK usage with the full job lifecycle."""
    async with AgentEconomySDK(wallet="worker_wallet_001") as sdk:
        # Get marketplace overview
        stats = await sdk.get_stats()
        print(f"Marketplace: {stats.total_jobs} jobs, {stats.total_rtc_volume} RTC volume")
        
        # Browse available jobs
        jobs = await sdk.find_job(category="code", min_reward=5.0)
        print(f"Found {len(jobs)} code jobs with >= 5 RTC reward")
        
        if jobs:
            job = jobs[0]
            print(f"Claiming job: {job.id} - {job.title}")
            
            claimed = await sdk.claim_job(job.id)
            print(f"Job status: {claimed.status}")
            
            delivered = await sdk.deliver_job(
                job.id,
                deliverable_url="https://github.com/example/pull/123",
                result_summary="Fixed the bug as requested",
            )
            print(f"Delivered! Status: {delivered.status}")
        
        # Check reputation
        rep = await sdk.get_reputation()
        print(f"Trust score: {rep.trust_score} ({rep.trust_level})")


if __name__ == "__main__":
    asyncio.run(example())
