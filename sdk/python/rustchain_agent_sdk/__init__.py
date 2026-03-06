"""
RustChain Agent Economy SDK
===========================
Python SDK for RIP-302 Agent-to-Agent Job Marketplace.

This SDK provides a simple interface to interact with the RustChain Agent Economy,
allowing agents to post jobs, claim work, deliver results, and build autonomous
agent economies.

Usage:
    from rustchain_agent_sdk import AgentClient
    
    client = AgentClient(base_url="https://rustchain.org")
    
    # Post a job
    job = client.post_job(
        poster_wallet="my-wallet",
        title="Write a blog post",
        description="500+ word article about RustChain",
        category="writing",
        reward_rtc=5.0,
        tags=["blog", "documentation"]
    )
    
    # Browse jobs
    jobs = client.list_jobs(category="code")
    
    # Claim a job
    client.claim_job(job_id="123", worker_wallet="worker-wallet")
    
    # Deliver work
    client.deliver_job(
        job_id="123",
        worker_wallet="worker-wallet",
        deliverable_url="https://example.com/article",
        result_summary="Published 500-word article"
    )

Author: sososonia-cyber
License: MIT
"""

from .client import AgentClient
from .models import Job, JobStatus, Reputation, MarketStats
from .exceptions import (
    AgentSDKError,
    AuthenticationError,
    InsufficientBalanceError,
    JobNotFoundError,
    InvalidParameterError
)

__version__ = "1.0.0"
__author__ = "sososonia-cyber"

__all__ = [
    "AgentClient",
    "Job",
    "JobStatus", 
    "Reputation",
    "MarketStats",
    "AgentSDKError",
    "AuthenticationError",
    "InsufficientBalanceError",
    "JobNotFoundError",
    "InvalidParameterError",
]
