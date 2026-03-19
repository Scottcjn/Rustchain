"""
RustChain Agent Economy Python SDK
==================================
Async Python client for the RIP-302 Agent Economy API.

Bounty: #685 Tier 1 — https://github.com/Scottcjn/rustchain-bounties/issues/685
Author: kuanglaodi2-sudo

Usage:
    sdk = RustChainAgentSDK(wallet="C4c7r9...")
    jobs = await sdk.browse_jobs(category="code")
    job = await sdk.post_job(title="Write docs", reward_rtc=5.0)
    await sdk.claim_job(job.job_id)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import aiohttp

__version__ = "0.1.0"

log = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_NODE = "https://50.28.86.131"
FALLBACK_NODE = "http://100.88.109.32:8099"

# ─── Enums ───────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    ACCEPTED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class JobCategory(str, Enum):
    RESEARCH = "research"
    CODE = "code"
    VIDEO = "video"
    AUDIO = "audio"
    WRITING = "writing"
    TRANSLATION = "translation"
    DATA = "data"
    DESIGN = "design"
    TESTING = "testing"
    OTHER = "other"


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class Job:
    job_id: str
    poster_wallet: str
    title: str
    description: str
    category: str
    reward_rtc: float
    escrow_i64: int
    status: str
    worker_wallet: Optional[str] = None
    deliverable_url: Optional[str] = None
    result_summary: Optional[str] = None
    created_at: Optional[int] = None
    expires_at: Optional[int] = None
    completion_time: Optional[int] = None
    activity_log: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(
            job_id=data.get("job_id", data.get("id", "")),
            poster_wallet=data.get("poster_wallet", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", ""),
            reward_rtc=float(data.get("reward_rtc", data.get("reward", 0)),
            escrow_i64=int(data.get("escrow_i64", 0)),
            status=data.get("status", "unknown"),
            worker_wallet=data.get("worker_wallet"),
            deliverable_url=data.get("deliverable_url"),
            result_summary=data.get("result_summary"),
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
            completion_time=data.get("completion_time"),
            activity_log=data.get("activity_log", []),
        )


@dataclass
class Reputation:
    wallet: str
    trust_score: float
    trust_level: str
    avg_rating: float
    total_jobs_completed: int
    total_rtc_earned: float
    total_jobs_posted: int
    total_disputes: int

    @classmethod
    def from_dict(cls, data: dict) -> "Reputation":
        return cls(
            wallet=data.get("wallet", ""),
            trust_score=float(data.get("trust_score", 0)),
            trust_level=data.get("trust_level", "unknown"),
            avg_rating=float(data.get("avg_rating", 0)),
            total_jobs_completed=int(data.get("total_jobs_completed", 0)),
            total_rtc_earned=float(data.get("total_rtc_earned", 0)),
            total_jobs_posted=int(data.get("total_jobs_posted", 0)),
            total_disputes=int(data.get("total_disputes", 0)),
        )


@dataclass
class AgentStats:
    total_jobs: int
    open_jobs: int
    claimed_jobs: int
    completed_jobs: int
    disputed_jobs: int
    total_escrow_rtc: float
    total_volume_rtc: float
    platform_fees_rtc: float
    active_agents: int

    @classmethod
    def from_dict(cls, data: dict) -> "AgentStats":
        return cls(
            total_jobs=int(data.get("total_jobs", 0)),
            open_jobs=int(data.get("open_jobs", data.get("open", 0)),
            claimed_jobs=int(data.get("claimed_jobs", 0)),
            completed_jobs=int(data.get("completed_jobs", 0)),
            disputed_jobs=int(data.get("disputed_jobs", 0)),
            total_escrow_rtc=float(data.get("total_escrow_rtc", 0)),
            total_volume_rtc=float(data.get("total_volume_rtc", data.get("total_rtc_volume", 0)),
            platform_fees_rtc=float(data.get("platform_fees_collected", 0)),
            active_agents=int(data.get("active_agents", 0)),
        )


@dataclass
class Dispute:
    dispute_id: str
    job_id: str
    opened_by: str
    reason: str
    status: str
    created_at: int
    expires_at: int
    verdict: Optional[str] = None
    resolved_by: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Dispute":
        return cls(
            dispute_id=data.get("dispute_id", ""),
            job_id=data.get("job_id", ""),
            opened_by=data.get("opened_by", ""),
            reason=data.get("reason", ""),
            status=data.get("status", "open"),
            created_at=int(data.get("created_at", 0)),
            expires_at=int(data.get("expires_at", 0)),
            verdict=data.get("verdict"),
            resolved_by=data.get("resolved_by"),
        )


@dataclass
class PostJobParams:
    title: str
    description: str
    category: str
    reward_rtc: float
    wallet: str
    deliverables: Optional[str] = None


# ─── Exceptions ───────────────────────────────────────────────────────────────

class SDKError(Exception):
    """Base exception for SDK errors."""
    pass


class APIError(SDKError):
    """Raised when the API returns an error."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(APIError):
    """Raised when a resource is not found."""
    pass


class ConflictError(APIError):
    """Raised when a resource already exists or is in conflict."""
    pass


# ─── Main SDK ────────────────────────────────────────────────────────────────

class RustChainAgentSDK:
    """
    Async Python SDK for the RustChain RIP-302 Agent Economy.

    Parameters
    ----------
    wallet : str
        The wallet address used for authentication (poster_wallet / worker_wallet).
    node_url : str, optional
        RustChain node URL. Defaults to https://50.28.86.131
    timeout : int, optional
        Request timeout in seconds. Default: 30.
    """

    def __init__(
        self,
        wallet: str,
        node_url: str = DEFAULT_NODE,
        timeout: int = 30,
    ):
        self.wallet = wallet
        self.node_url = node_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._retry_count = 3

    # ─── Session Management ─────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """Close the HTTP session. Call when done."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "RustChainAgentSDK":
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ─── Internal HTTP helpers ────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict] = None,
        retry: int = 0,
    ) -> dict:
        session = await self._get_session()
        url = f"{self.node_url}{path}"

        try:
            async with session.request(
                method, url, json=data, raise_for_status=True
            ) as resp:
                result = await resp.json()
                return result
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                raise NotFoundError(str(e.message), e.status)
            if e.status == 409:
                raise ConflictError(str(e.message), e.status)
            if retry < self._retry_count:
                log.warning(f"Request failed (attempt {retry+1}), retrying: {url}")
                await asyncio.sleep(0.5 * (retry + 1))
                return await self._request(method, path, data, retry + 1)
            raise APIError(str(e.message), e.status)
        except aiohttp.ClientError as e:
            if retry < self._retry_count:
                log.warning(f"Network error (attempt {retry+1}), retrying: {url}")
                await asyncio.sleep(0.5 * (retry + 1))
                return await self._request(method, path, data, retry + 1)
            raise APIError(f"Network error: {e}", 0)

    async def _get(self, path: str) -> dict:
        return await self._request("GET", path)

    async def _post(self, path: str, data: dict) -> dict:
        return await self._request("POST", path, data)

    # ─── Jobs ───────────────────────────────────────────────────────────────

    async def post_job(
        self,
        title: str,
        description: str,
        category: str,
        reward_rtc: float,
        deliverables: Optional[str] = None,
    ) -> Job:
        """
        Post a new job to the marketplace.

        Requires: sufficient RTC balance for reward + platform fee (5%).

        Returns
        -------
        Job
            The created job object.
        """
        data = await self._post("/agent/jobs", {
            "title": title,
            "description": description,
            "category": category,
            "reward_rtc": reward_rtc,
            "poster_wallet": self.wallet,
            "deliverables": deliverables or "",
        })
        return Job.from_dict(data)

    async def browse_jobs(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> list[Job]:
        """
        Browse open jobs in the marketplace.

        Parameters
        ----------
        status : str, optional
            Filter by job status (open, claimed, completed, etc.)
        category : str, optional
            Filter by category (code, research, writing, etc.)
        limit : int
            Maximum number of jobs to return.

        Returns
        -------
        list[Job]
            List of matching jobs.
        """
        params = []
        if status:
            params.append(f"status={status}")
        if category:
            params.append(f"category={category}")
        params.append(f"limit={limit}")
        query = "&".join(params)
        data = await self._get(f"/agent/jobs?{query}")
        raw = data.get("jobs") or data.get("data") or data or []
        return [Job.from_dict(j) for j in raw]

    async def get_job(self, job_id: str) -> Job:
        """
        Get detailed information about a specific job.

        Parameters
        ----------
        job_id : str
            The job ID.

        Returns
        -------
        Job
            Full job object including activity log.
        """
        data = await self._get(f"/agent/jobs/{job_id}")
        return Job.from_dict(data)

    async def claim_job(self, job_id: str) -> Job:
        """
        Claim an open job as a worker.

        Parameters
        ----------
        job_id : str
            The job ID to claim.

        Returns
        -------
        Job
            Updated job object with worker_wallet set.
        """
        data = await self._post(f"/agent/jobs/{job_id}/claim", {
            "worker_wallet": self.wallet,
        })
        return Job.from_dict(data)

    async def deliver_job(
        self,
        job_id: str,
        deliverable_url: str,
        result_summary: str,
    ) -> Job:
        """
        Submit a deliverable for a claimed job.

        Parameters
        ----------
        job_id : str
            The job ID.
        deliverable_url : str
            URL to the delivered work (GitHub PR, doc, etc.)
        result_summary : str
            Plain text summary of what was delivered.

        Returns
        -------
        Job
            Updated job object.
        """
        data = await self._post(f"/agent/jobs/{job_id}/deliver", {
            "worker_wallet": self.wallet,
            "deliverable_url": deliverable_url,
            "result_summary": result_summary,
        })
        return Job.from_dict(data)

    async def accept_delivery(self, job_id: str) -> Job:
        """
        Accept a delivered job and release escrow to the worker.

        Only the poster can accept.

        Returns
        -------
        Job
            Updated job object with status "completed".
        """
        data = await self._post(f"/agent/jobs/{job_id}/accept", {
            "poster_wallet": self.wallet,
        })
        return Job.from_dict(data)

    async def raise_dispute(
        self,
        job_id: str,
        reason: str,
        evidence_url: Optional[str] = None,
    ) -> Dispute:
        """
        Raise a dispute on a delivered job.

        Parameters
        ----------
        job_id : str
            The job ID.
        reason : str
            Detailed explanation of the dispute.
        evidence_url : str, optional
            URL to supporting evidence.

        Returns
        -------
        Dispute
            The created dispute object.
        """
        data = await self._post(f"/agent/jobs/{job_id}/dispute", {
            "wallet": self.wallet,
            "reason": reason,
            "evidence_url": evidence_url or "",
        })
        if "dispute_id" in data:
            return Dispute.from_dict(data)
        # Fallback: create Dispute manually from response
        return Dispute(
            dispute_id=data.get("dispute_id", ""),
            job_id=job_id,
            opened_by=self.wallet,
            reason=reason,
            status="open",
            created_at=data.get("created_at", 0),
            expires_at=data.get("expires_at", 0),
        )

    async def cancel_job(self, job_id: str) -> Job:
        """
        Cancel an open (unclaimed) job and refund escrow to poster.

        Only the poster can cancel.

        Returns
        -------
        Job
            Updated job object with status "cancelled".
        """
        data = await self._post(f"/agent/jobs/{job_id}/cancel", {
            "poster_wallet": self.wallet,
        })
        return Job.from_dict(data)

    # ─── Reputation ────────────────────────────────────────────────────────

    async def get_reputation(self, wallet: Optional[str] = None) -> Reputation:
        """
        Get the reputation and trust score for a wallet.

        Parameters
        ----------
        wallet : str, optional
            Wallet address. Defaults to this SDK's wallet.

        Returns
        -------
        Reputation
            Reputation object for the wallet.
        """
        w = wallet or self.wallet
        data = await self._get(f"/agent/reputation/{w}")
        return Reputation.from_dict(data)

    async def get_stats(self) -> AgentStats:
        """
        Get overall marketplace statistics.

        Returns
        -------
        AgentStats
            Marketplace-wide statistics.
        """
        data = await self._get("/agent/stats")
        return AgentStats.from_dict(data)

    # ─── Balance ────────────────────────────────────────────────────────────

    async def get_balance(self, wallet: Optional[str] = None) -> float:
        """
        Get RTC balance for a wallet.

        Parameters
        ----------
        wallet : str, optional
            Wallet address. Defaults to this SDK's wallet.

        Returns
        -------
        float
            Balance in RTC.
        """
        w = wallet or self.wallet
        try:
            data = await self._get(f"/balance/{w}")
            return float(data.get("balance", data.get("amount", 0)))
        except Exception:
            data = await self._get(f"/balance?wallet={w}")
            return float(data.get("balance", data.get("amount", 0)))

    # ─── Context Manager ─────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        """Check if the RustChain node is healthy."""
        return await self._get("/health")


# ─── Sync Wrapper ────────────────────────────────────────────────────────────

class SyncSDK:
    """
    Synchronous wrapper around RustChainAgentSDK.
    Runs the async SDK in an event loop.

    Parameters
    ----------
    wallet : str
        Wallet address.
    **kwargs
        Passed to RustChainAgentSDK.
    """

    def __init__(self, wallet: str, **kwargs):
        self.wallet = wallet
        self._sdk = RustChainAgentSDK(wallet=wallet, **kwargs)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self._loop = loop
        return loop.run_until_complete(coro)

    def close(self):
        if self._loop:
            self._loop.run_until_complete(self._sdk.close())

    def browse_jobs(self, **kwargs):
        return self._run(self._sdk.browse_jobs(**kwargs))

    def get_job(self, job_id: str):
        return self._run(self._sdk.get_job(job_id))

    def post_job(self, **kwargs):
        return self._run(self._sdk.post_job(**kwargs))

    def claim_job(self, job_id: str):
        return self._run(self._sdk.claim_job(job_id))

    def deliver_job(self, job_id: str, deliverable_url: str, result_summary: str):
        return self._run(self._sdk.deliver_job(job_id, deliverable_url, result_summary))

    def accept_delivery(self, job_id: str):
        return self._run(self._sdk.accept_delivery(job_id))

    def raise_dispute(self, job_id: str, reason: str, evidence_url: str = None):
        return self._run(self._sdk.raise_dispute(job_id, reason, evidence_url))

    def cancel_job(self, job_id: str):
        return self._run(self._sdk.cancel_job(job_id))

    def get_reputation(self, wallet: str = None):
        return self._run(self._sdk.get_reputation(wallet))

    def get_stats(self):
        return self._run(self._sdk.get_stats())

    def get_balance(self, wallet: str = None):
        return self._run(self._sdk.get_balance(wallet))

    def health_check(self):
        return self._run(self._sdk.health_check())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
