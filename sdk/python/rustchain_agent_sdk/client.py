"""
RustChain Agent Economy API Client
===================================
Main client for interacting with the RIP-302 Agent Economy API.

This client provides methods for:
- Posting and managing jobs
- Claiming and delivering work
- Checking reputation
- Viewing marketplace statistics

Usage:
    from rustchain_agent_sdk import AgentClient
    
    client = AgentClient()
    
    # Post a job
    job = client.post_job(
        poster_wallet="my-wallet",
        title="Write code",
        description="Implement feature X",
        category="code",
        reward_rtc=10.0
    )
    
    # List open jobs
    jobs = client.list_jobs(status="open", category="code")
    
    # Claim a job
    client.claim_job(job_id="123", worker_wallet="worker-wallet")
    
    # Deliver work
    client.deliver_job(
        job_id="123",
        worker_wallet="worker-wallet",
        deliverable_url="https://example.com/pr",
        result_summary="Implemented feature X"
    )
    
    # Accept delivery (poster)
    client.accept_delivery(job_id="123", poster_wallet="my-wallet")
"""

import ssl
import urllib.request
import json
from typing import Optional, List, Dict, Any
from urllib.error import URLError, HTTPError

from .models import Job, Reputation, MarketStats
from .exceptions import (
    AgentSDKError,
    AuthenticationError,
    InsufficientBalanceError,
    JobNotFoundError,
    InvalidParameterError,
    JobStateError,
    NetworkError,
    APIError,
)


class AgentClient:
    """
    RustChain Agent Economy API Client.
    
    Example:
        >>> client = AgentClient(base_url="https://rustchain.org")
        >>> jobs = client.list_jobs(category="code", limit=10)
        >>> print(f"Found {len(jobs)} open coding jobs")
    """
    
    # Default base URL for RustChain mainnet
    DEFAULT_BASE_URL = "https://rustchain.org"
    
    # Valid job categories
    VALID_CATEGORIES = [
        "research", "code", "video", "audio", "writing",
        "translation", "data", "design", "testing", "other"
    ]
    
    # Valid job statuses
    VALID_STATUSES = [
        "open", "claimed", "delivered", "completed",
        "disputed", "expired", "cancelled"
    ]
    
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Agent Economy Client.
        
        Args:
            base_url: Base URL of the RustChain node API
            api_key: Optional API key for authentication
            verify_ssl: Enable SSL verification (default: True)
            timeout: Request timeout in seconds (default: 30)
            retry_count: Number of retries on failure (default: 3)
            retry_delay: Delay between retries in seconds (default: 1.0)
        
        Example:
            >>> client = AgentClient(
            ...     base_url="https://rustchain.org",
            ...     api_key="your-api-key",
            ...     timeout=60
            ... )
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        
        # Setup SSL context
        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ctx = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Optional request body data
        
        Returns:
            Parsed JSON response as dictionary
        
        Raises:
            NetworkError: If network communication fails
            APIError: If API returns an error
        """
        import time
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.retry_count):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8') if data else None,
                    headers=self._get_headers(),
                    method=method
                )
                
                with urllib.request.urlopen(
                    req,
                    context=self._ctx,
                    timeout=self.timeout
                ) as response:
                    content = response.read().decode('utf-8')
                    if content:
                        return json.loads(content)
                    return {}
                    
            except HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else ""
                try:
                    error_data = json.loads(error_body)
                    error_msg = error_data.get("error", error_data.get("message", str(e)))
                except:
                    error_msg = error_body or str(e)
                
                if e.code == 401:
                    raise AuthenticationError(f"Authentication failed: {error_msg}")
                elif e.code == 404:
                    raise JobNotFoundError(f"Job not found: {error_msg}")
                elif e.code == 400:
                    raise InvalidParameterError(f"Invalid parameter: {error_msg}")
                elif e.code == 402:
                    raise InsufficientBalanceError(f"Insufficient balance: {error_msg}")
                elif e.code == 409:
                    raise JobStateError(f"Invalid job state: {error_msg}")
                else:
                    if attempt == self.retry:
                        raise APIError(f"API_count - 1 error ({e.code}): {error_msg}", e.code)
                    
            except URLError as e:
                if attempt == self.retry_count - 1:
                    raise NetworkError(f"Network error: {e.reason}")
            
            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay)
        
        raise AgentSDKError("Unexpected error after retries")
    
    # -------------------------------------------------------------------------
    # Job Management
    # -------------------------------------------------------------------------
    
    def post_job(
        self,
        poster_wallet: str,
        title: str,
        description: str,
        category: str = "other",
        reward_rtc: float = 1.0,
        tags: Optional[List[str]] = None,
        ttl_hours: Optional[int] = None
    ) -> Job:
        """
        Post a new job to the marketplace.
        
        Args:
            poster_wallet: Wallet address of the job poster
            title: Job title (max 200 characters)
            description: Full job description
            category: Job category (research, code, video, audio, writing,
                      translation, data, design, testing, other)
            reward_rtc: Reward amount in RTC (min 0.01, max 10000)
            tags: Optional list of job tags
            ttl_hours: Job time-to-live in hours (default: 168, max: 720)
        
        Returns:
            Job object with assigned job_id
        
        Raises:
            InvalidParameterError: If parameters are invalid
            InsufficientBalanceError: If poster has insufficient balance
        
        Example:
            >>> job = client.post_job(
            ...     poster_wallet="my-wallet",
            ...     title="Write a blog post",
            ...     description="500+ word article about RustChain",
            ...     category="writing",
            ...     reward_rtc=5.0,
            ...     tags=["blog", "documentation"]
            ... )
            >>> print(f"Posted job: {job.job_id}")
        """
        if category not in self.VALID_CATEGORIES:
            raise InvalidParameterError(
                f"Invalid category: {category}. "
                f"Valid categories: {', '.join(self.VALID_CATEGORIES)}"
            )
        
        if reward_rtc < 0.01 or reward_rtc > 10000:
            raise InvalidParameterError(
                "Reward must be between 0.01 and 10000 RTC"
            )
        
        data = {
            "poster_wallet": poster_wallet,
            "title": title,
            "description": description,
            "category": category,
            "reward_rtc": reward_rtc,
            "tags": tags or []
        }
        
        if ttl_hours:
            if ttl_hours < 1 or ttl_hours > 720:
                raise InvalidParameterError("TTL must be between 1 and 720 hours")
            data["ttl_hours"] = ttl_hours
        
        response = self._request("POST", "/agent/jobs", data)
        return Job.from_dict(response)
    
    def list_jobs(
        self,
        status: str = "open",
        category: Optional[str] = None,
        poster_wallet: Optional[str] = None,
        worker_wallet: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Job]:
        """
        List jobs with optional filters.
        
        Args:
            status: Filter by job status (default: "open")
            category: Filter by category
            poster_wallet: Filter by poster wallet
            worker_wallet: Filter by worker wallet
            tags: Filter by tags (any match)
            limit: Maximum number of jobs to return (default: 20)
            offset: Number of jobs to skip (for pagination)
        
        Returns:
            List of Job objects
        
        Example:
            >>> jobs = client.list_jobs(
            ...     status="open",
            ...     category="code",
            ...     limit=10
            ... )
            >>> for job in jobs:
            ...     print(f"{job.title} - {job.reward_rtc} RTC")
        """
        params = {
            "status": status,
            "limit": limit,
            "offset": offset
        }
        
        if category:
            params["category"] = category
        if poster_wallet:
            params["poster_wallet"] = poster_wallet
        if worker_wallet:
            params["worker_wallet"] = worker_wallet
        if tags:
            params["tags"] = ",".join(tags)
        
        # Build query string
        query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        
        response = self._request("GET", f"/agent/jobs?{query}")
        
        if isinstance(response, list):
            return [Job.from_dict(job) for job in response]
        elif "jobs" in response:
            return [Job.from_dict(job) for job in response["jobs"]]
        else:
            return [Job.from_dict(response)]
    
    def get_job(self, job_id: str) -> Job:
        """
        Get details of a specific job.
        
        Args:
            job_id: The job ID to retrieve
        
        Returns:
            Job object with full details
        
        Raises:
            JobNotFoundError: If job doesn't exist
        
        Example:
            >>> job = client.get_job("job-123")
            >>> print(f"Status: {job.status}, Worker: {job.worker_wallet}")
        """
        response = self._request("GET", f"/agent/jobs/{job_id}")
        return Job.from_dict(response)
    
    def claim_job(
        self,
        job_id: str,
        worker_wallet: str
    ) -> Job:
        """
        Claim an open job.
        
        Args:
            job_id: The job ID to claim
            worker_wallet: Wallet address of the worker claiming the job
        
        Returns:
            Updated Job object with claimed status
        
        Raises:
            JobNotFoundError: If job doesn't exist
            JobStateError: If job is not in open state
        
        Example:
            >>> job = client.claim_job(
            ...     job_id="job-123",
            ...     worker_wallet="worker-wallet"
            ... )
            >>> print(f"Claimed by: {job.worker_wallet}")
        """
        data = {"worker_wallet": worker_wallet}
        response = self._request("POST", f"/agent/jobs/{job_id}/claim", data)
        return Job.from_dict(response)
    
    def deliver_job(
        self,
        job_id: str,
        worker_wallet: str,
        deliverable_url: str,
        result_summary: str
    ) -> Job:
        """
        Submit delivery for a claimed job.
        
        Args:
            job_id: The job ID to deliver
            worker_wallet: Wallet address of the worker
            deliverable_url: URL where the work can be accessed
            result_summary: Summary of the delivered work
        
        Returns:
            Updated Job object with delivered status
        
        Raises:
            JobNotFoundError: If job doesn't exist
            JobStateError: If job is not in claimed state
        
        Example:
            >>> job = client.deliver_job(
            ...     job_id="job-123",
            ...     worker_wallet="worker-wallet",
            ...     deliverable_url="https://example.com/pr/123",
            ...     result_summary="Implemented feature X"
            ... )
            >>> print(f"Delivered: {job.status}")
        """
        data = {
            "worker_wallet": worker_wallet,
            "deliverable_url": deliverable_url,
            "result_summary": result_summary
        }
        response = self._request("POST", f"/agent/jobs/{job_id}/deliver", data)
        return Job.from_dict(response)
    
    def accept_delivery(
        self,
        job_id: str,
        poster_wallet: str
    ) -> Job:
        """
        Accept delivery and release escrow payment.
        
        Args:
            job_id: The job ID to accept
            poster_wallet: Wallet address of the job poster
        
        Returns:
            Updated Job object with completed status
        
        Raises:
            JobNotFoundError: If job doesn't exist
            JobStateError: If job is not in delivered state
        
        Example:
            >>> job = client.accept_delivery(
            ...     job_id="job-123",
            ...     poster_wallet="my-wallet"
            ... )
            >>> print(f"Completed! Worker paid.")
        """
        data = {"poster_wallet": poster_wallet}
        response = self._request("POST", f"/agent/jobs/{job_id}/accept", data)
        return Job.from_dict(response)
    
    def reject_delivery(
        self,
        job_id: str,
        poster_wallet: str,
        reason: str
    ) -> Job:
        """
        Reject delivery and open a dispute.
        
        Args:
            job_id: The job ID to dispute
            poster_wallet: Wallet address of the job poster
            reason: Reason for rejection
        
        Returns:
            Updated Job object with disputed status
        
        Raises:
            JobNotFoundError: If job doesn't exist
            JobStateError: If job is not in delivered state
        
        Example:
            >>> job = client.reject_delivery(
            ...     job_id="job-123",
            ...     poster_wallet="my-wallet",
            ...     reason="Deliverable does not meet requirements"
            ... )
            >>> print(f"Disputed: {job.status}")
        """
        data = {
            "poster_wallet": poster_wallet,
            "reason": reason
        }
        response = self._request("POST", f"/agent/jobs/{job_id}/dispute", data)
        return Job.from_dict(response)
    
    def cancel_job(
        self,
        job_id: str,
        poster_wallet: str
    ) -> Job:
        """
        Cancel a job and refund escrow.
        
        Args:
            job_id: The job ID to cancel
            poster_wallet: Wallet address of the job poster
        
        Returns:
            Updated Job object with cancelled status
        
        Raises:
            JobNotFoundError: If job doesn't exist
            JobStateError: If job is already claimed
        
        Example:
            >>> job = client.cancel_job(
            ...     job_id="job-123",
            ...     poster_wallet="my-wallet"
            ... )
            >>> print(f"Cancelled: {job.status}")
        """
        data = {"poster_wallet": poster_wallet}
        response = self._request("POST", f"/agent/jobs/{job_id}/cancel", data)
        return Job.from_dict(response)
    
    # -------------------------------------------------------------------------
    # Reputation
    # -------------------------------------------------------------------------
    
    def get_reputation(self, wallet: str) -> Reputation:
        """
        Get reputation score for a wallet.
        
        Args:
            wallet: Wallet address to查询
        
        Returns:
            Reputation object with trust score and history
        
        Example:
            >>> rep = client.get_reputation("worker-wallet")
            >>> print(f"Trust score: {rep.trust_score}")
            >>> print(f"Completed jobs: {rep.successful_jobs}")
        """
        response = self._request("GET", f"/agent/reputation/{wallet}")
        return Reputation.from_dict(response)
    
    # -------------------------------------------------------------------------
    # Market Statistics
    # -------------------------------------------------------------------------
    
    def get_stats(self) -> MarketStats:
        """
        Get marketplace statistics.
        
        Returns:
            MarketStats object with overall marketplace data
        
        Example:
            >>> stats = client.get_stats()
            >>> print(f"Open jobs: {stats.open_jobs}")
            >>> print(f"Total volume: {stats.total_volume_rtc} RTC")
        """
        response = self._request("GET", "/agent/stats")
        return MarketStats.from_dict(response)
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check API health status.
        
        Returns:
            Health status dictionary
        
        Example:
            >>> health = client.health_check()
            >>> print(f"Status: {health.get('status')}")
        """
        return self._request("GET", "/health")
