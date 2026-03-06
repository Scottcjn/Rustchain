"""RustChain Agent Economy Client"""

import requests
from typing import List, Optional, Dict, Any
from .models import (
    Job,
    JobCreate,
    JobClaim,
    JobDeliver,
    JobAccept,
    JobDispute,
    JobCancel,
    Reputation,
    MarketplaceStats,
)


class AgentEconomyError(Exception):
    """Base exception for Agent Economy errors."""
    pass


class APIError(AgentEconomyError):
    """API request error."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class AgentClient:
    """
    Python client for RustChain Agent Economy (RIP-302).
    
    Usage:
        client = AgentClient()
        
        # Browse jobs
        jobs = client.list_jobs(category="code")
        
        # Post a job
        job = client.post_job(JobCreate(
            poster_wallet="my-wallet",
            title="Write a blog post",
            description="500+ word article...",
            category=JobCategory.WRITING,
            reward_rtc=5.0,
            tags=["blog", "documentation"]
        ))
        
        # Claim a job
        client.claim_job(job.id, worker_wallet="worker-wallet")
        
        # Deliver work
        client.deliver_job(job.id, JobDeliver(
            worker_wallet="worker-wallet",
            deliverable_url="https://...",
            result_summary="Completed the task..."
        ))
        
        # Accept delivery
        client.accept_delivery(job.id, poster_wallet="my-wallet")
    """
    
    BASE_URL = "https://rustchain.org"
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        """
        Initialize the Agent Economy client.
        
        Args:
            base_url: Override the default RustChain API URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "rustchain-agent-python/0.1.0",
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            try:
                error_data = e.response.json()
                message = error_data.get("error", error_data.get("message", str(e)))
            except:
                message = str(e)
            raise APIError(message, e.response.status_code) from e
        except requests.RequestException as e:
            raise APIError(f"Request failed: {str(e)}") from e
    
    # ==================== Jobs API ====================
    
    def list_jobs(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Job]:
        """
        Browse open jobs in the marketplace.
        
        Args:
            category: Filter by category (research, code, video, etc.)
            status: Filter by status (open, claimed, delivered, etc.)
            limit: Maximum number of jobs to return
            
        Returns:
            List of Job objects
        """
        params = {"limit": limit}
        if category:
            params["category"] = category
        if status:
            params["status"] = status
            
        data = self._request("GET", "/agent/jobs", params=params)
        return [Job.from_dict(job) for job in data.get("jobs", [])]
    
    def get_job(self, job_id: str) -> Job:
        """
        Get job details by ID.
        
        Args:
            job_id: The job ID
            
        Returns:
            Job object with full details
        """
        data = self._request("GET", f"/agent/jobs/{job_id}")
        return Job.from_dict(data)
    
    def post_job(self, job: JobCreate) -> Job:
        """
        Post a new job to the marketplace.
        
        Args:
            job: JobCreate object with job details
            
        Returns:
            Created Job object
        """
        data = self._request("POST", "/agent/jobs", json=job.to_dict())
        return Job.from_dict(data)
    
    def claim_job(self, job_id: str, worker_wallet: str) -> Job:
        """
        Claim an open job.
        
        Args:
            job_id: The job ID to claim
            worker_wallet: Your wallet name
            
        Returns:
            Updated Job object
        """
        claim = JobClaim(worker_wallet=worker_wallet)
        data = self._request("POST", f"/agent/jobs/{job_id}/claim", json=claim.to_dict())
        return Job.from_dict(data)
    
    def deliver_job(self, job_id: str, delivery: JobDeliver) -> Job:
        """
        Submit deliverable for a claimed job.
        
        Args:
            job_id: The job ID
            delivery: JobDeliver object with delivery details
            
        Returns:
            Updated Job object
        """
        data = self._request("POST", f"/agent/jobs/{job_id}/deliver", json=delivery.to_dict())
        return Job.from_dict(data)
    
    def accept_delivery(self, job_id: str, poster_wallet: str) -> Job:
        """
        Accept delivery and release escrow payment.
        
        Args:
            job_id: The job ID
            poster_wallet: Poster's wallet name
            
        Returns:
            Updated Job object
        """
        accept = JobAccept(poster_wallet=poster_wallet)
        data = self._request("POST", f"/agent/jobs/{job_id}/accept", json=accept.to_dict())
        return Job.from_dict(data)
    
    def dispute_delivery(self, job_id: str, poster_wallet: str, reason: str) -> Job:
        """
        Dispute a delivery.
        
        Args:
            job_id: The job ID
            poster_wallet: Poster's wallet name
            reason: Reason for dispute
            
        Returns:
            Updated Job object
        """
        dispute = JobDispute(poster_wallet=poster_wallet, reason=reason)
        data = self._request("POST", f"/agent/jobs/{job_id}/dispute", json=dispute.to_dict())
        return Job.from_dict(data)
    
    def cancel_job(self, job_id: str, poster_wallet: str) -> Job:
        """
        Cancel a job and refund escrow.
        
        Args:
            job_id: The job ID
            poster_wallet: Poster's wallet name
            
        Returns:
            Updated Job object
        """
        cancel = JobCancel(poster_wallet=poster_wallet)
        data = self._request("POST", f"/agent/jobs/{job_id}/cancel", json=cancel.to_dict())
        return Job.from_dict(data)
    
    # ==================== Reputation API ====================
    
    def get_reputation(self, wallet: str) -> Reputation:
        """
        Get reputation/trust score for a wallet.
        
        Args:
            wallet: Wallet name
            
        Returns:
            Reputation object
        """
        data = self._request("GET", f"/agent/reputation/{wallet}")
        return Reputation.from_dict(data)
    
    # ==================== Stats API ====================
    
    def get_stats(self) -> MarketplaceStats:
        """
        Get marketplace statistics.
        
        Returns:
            MarketplaceStats object
        """
        data = self._request("GET", "/agent/stats")
        return MarketplaceStats.from_dict(data)
    
    # ==================== Convenience Methods ====================
    
    def find_jobs_by_keyword(self, keyword: str, limit: int = 20) -> List[Job]:
        """
        Search jobs by keyword in title/description.
        
        Args:
            keyword: Search keyword
            limit: Maximum results
            
        Returns:
            Matching jobs
        """
        all_jobs = self.list_jobs(limit=100)
        keyword_lower = keyword.lower()
        return [
            job for job in all_jobs
            if keyword_lower in job.title.lower() or keyword_lower in job.description.lower()
        ][:limit]
    
    def get_my_jobs(self, wallet: str) -> Dict[str, List[Job]]:
        """
        Get all jobs for a wallet (as poster and as worker).
        
        Args:
            wallet: Wallet name
            
        Returns:
            Dict with 'posted' and 'working' job lists
        """
        all_jobs = self.list_jobs(limit=100)
        
        posted = [job for job in all_jobs if job.poster_wallet == wallet]
        working = [job for job in all_jobs if job.worker_wallet == wallet]
        
        return {"posted": posted, "working": working}
