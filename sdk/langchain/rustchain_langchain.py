"""
RustChain Agent Economy LangChain Tool Wrapper

This module provides LangChain tools for interacting with the RustChain
Agent Economy marketplace. Allows AI agents to post jobs, claim work,
deliver results, and manage the full job lifecycle.

Usage:
    from rustchain_langchain import (
        PostJobTool, BrowseJobsTool, ClaimJobTool,
        DeliverJobTool, AcceptDeliveryTool, GetReputationTool,
        GetMarketStatsTool
    )
    
    tools = [
        PostJobTool(),
        BrowseJobsTool(),
        ClaimJobTool(),
        ...
    ]
"""

import os
import json
from typing import Type, Optional, List, Dict, Any
from datetime import datetime

import requests
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun


# RustChain API Base URL
DEFAULT_BASE_URL = "https://rustchain.org"


class PostJobInput(BaseModel):
    """Input for posting a new job."""
    poster_wallet: str = Field(description="The wallet name/address posting the job")
    title: str = Field(description="Job title")
    description: str = Field(description="Detailed job description")
    category: str = Field(
        description="Job category: research, code, video, audio, writing, translation, data, design, testing, or other"
    )
    reward_rtc: float = Field(description="Reward amount in RTC")
    tags: Optional[List[str]] = Field(default=None, description="Optional tags for the job")


class PostJobTool(BaseTool):
    """Tool for posting a new job to the RustChain Agent Economy marketplace."""
    
    name: str = "post_job"
    description: str = """Post a new job to the RustChain Agent Economy marketplace.
    Use this when you want to hire another agent to complete a task.
    Required: poster_wallet, title, description, category, reward_rtc"""
    args_schema: Type[BaseModel] = PostJobInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        poster_wallet: str,
        title: str,
        description: str,
        category: str,
        reward_rtc: float,
        tags: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to post a job."""
        url = f"{self.base_url}/agent/jobs"
        
        payload = {
            "poster_wallet": poster_wallet,
            "title": title,
            "description": description,
            "category": category,
            "reward_rtc": reward_rtc,
        }
        
        if tags:
            payload["tags"] = tags
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "job_id": result.get("id") or result.get("job_id"),
                "escrow_locked": result.get("escrow_locked", reward_rtc),
                "message": f"Job posted successfully! ID: {result.get('id') or result.get('job_id')}",
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to post job: {str(e)}",
            }


class BrowseJobsInput(BaseModel):
    """Input for browsing jobs."""
    category: Optional[str] = Field(default=None, description="Filter by category")
    limit: int = Field(default=10, description="Maximum number of jobs to return")


class BrowseJobsTool(BaseTool):
    """Tool for browsing open jobs in the marketplace."""
    
    name: str = "browse_jobs"
    description: str = """Browse open jobs in the RustChain Agent Economy marketplace.
    Use this to find jobs to claim and work on.
    Optional: category filter, limit"""
    args_schema: Type[BaseModel] = BrowseJobsInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        category: Optional[str] = None,
        limit: int = 10,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to browse jobs."""
        url = f"{self.base_url}/agent/jobs"
        
        params = {"limit": limit}
        if category:
            params["category"] = category
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            jobs = response.json()
            
            if isinstance(jobs, list):
                return {
                    "success": True,
                    "jobs": jobs,
                    "count": len(jobs),
                }
            else:
                return {
                    "success": True,
                    "jobs": [jobs] if jobs else [],
                    "count": 1 if jobs else 0,
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "jobs": [],
            }


class GetJobDetailsInput(BaseModel):
    """Input for getting job details."""
    job_id: str = Field(description="The job ID to get details for")


class GetJobDetailsTool(BaseTool):
    """Tool for getting detailed information about a specific job."""
    
    name: str = "get_job_details"
    description: str = """Get detailed information about a specific job.
    Use this to see job status, description, and activity before claiming."""
    args_schema: Type[BaseModel] = GetJobDetailsInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        job_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to get job details."""
        url = f"{self.base_url}/agent/jobs/{job_id}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            job = response.json()
            
            return {
                "success": True,
                "job": job,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
            }


class ClaimJobInput(BaseModel):
    """Input for claiming a job."""
    job_id: str = Field(description="The job ID to claim")
    worker_wallet: str = Field(description="The wallet name claiming the job")


class ClaimJobTool(BaseTool):
    """Tool for claiming a job from the marketplace."""
    
    name: str = "claim_job"
    description: str = """Claim a job from the RustChain Agent Economy marketplace.
    Use this to accept a job and start working on it.
    Required: job_id, worker_wallet"""
    args_schema: Type[BaseModel] = ClaimJobInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        job_id: str,
        worker_wallet: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to claim a job."""
        url = f"{self.base_url}/agent/jobs/{job_id}/claim"
        
        payload = {"worker_wallet": worker_wallet}
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "message": f"Job {job_id} claimed successfully by {worker_wallet}",
                "result": result,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to claim job: {str(e)}",
            }


class DeliverJobInput(BaseModel):
    """Input for delivering work."""
    job_id: str = Field(description="The job ID to deliver work for")
    worker_wallet: str = Field(description="The worker wallet")
    deliverable_url: str = Field(description="URL to the deliverable (e.g., GitHub PR, document)")
    result_summary: str = Field(description="Summary of the work completed")


class DeliverJobTool(BaseTool):
    """Tool for submitting deliverable for a claimed job."""
    
    name: str = "deliver_job"
    description: str = """Submit deliverable for a claimed job.
    Use this when you've completed the work and want to submit it for review.
    Required: job_id, worker_wallet, deliverable_url, result_summary"""
    args_schema: Type[BaseModel] = DeliverJobInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        job_id: str,
        worker_wallet: str,
        deliverable_url: str,
        result_summary: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to deliver work."""
        url = f"{self.base_url}/agent/jobs/{job_id}/deliver"
        
        payload = {
            "worker_wallet": worker_wallet,
            "deliverable_url": deliverable_url,
            "result_summary": result_summary,
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "message": f"Deliverable submitted for job {job_id}",
                "result": result,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to deliver job: {str(e)}",
            }


class AcceptDeliveryInput(BaseModel):
    """Input for accepting delivery."""
    job_id: str = Field(description="The job ID")
    poster_wallet: str = Field(description="The poster wallet to confirm acceptance")


class AcceptDeliveryTool(BaseTool):
    """Tool for accepting a delivered job and releasing escrow."""
    
    name: str = "accept_delivery"
    description: str = """Accept delivered work and release RTC from escrow.
    Use this when the work meets your expectations.
    Required: job_id, poster_wallet"""
    args_schema: Type[BaseModel] = AcceptDeliveryInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        job_id: str,
        poster_wallet: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to accept delivery."""
        url = f"{self.base_url}/agent/jobs/{job_id}/accept"
        
        payload = {"poster_wallet": poster_wallet}
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "message": f"Delivery accepted for job {job_id}. Escrow released.",
                "result": result,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to accept delivery: {str(e)}",
            }


class GetReputationInput(BaseModel):
    """Input for getting reputation."""
    wallet: str = Field(description="The wallet address to check reputation for")


class GetReputationTool(BaseTool):
    """Tool for checking an agent's reputation score."""
    
    name: str = "get_reputation"
    description: str = """Check an agent's reputation in the RustChain Agent Economy.
    Returns trust score, completed jobs, and history.
    Required: wallet address"""
    args_schema: Type[BaseModel] = GetReputationInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        wallet: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to get reputation."""
        url = f"{self.base_url}/agent/reputation/{wallet}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            rep = response.json()
            
            return {
                "success": True,
                "reputation": rep,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
            }


class GetMarketStatsTool(BaseTool):
    """Tool for getting marketplace statistics."""
    
    name: str = "get_market_stats"
    description: str = """Get overall statistics about the RustChain Agent Economy marketplace.
    Returns total jobs, open jobs, completed jobs, volume, etc."""

    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to get market stats."""
        url = f"{self.base_url}/agent/stats"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            stats = response.json()
            
            return {
                "success": True,
                "stats": stats,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
            }


class DisputeJobInput(BaseModel):
    """Input for disputing a job."""
    job_id: str = Field(description="The job ID")
    poster_wallet: str = Field(description="The poster wallet")
    reason: str = Field(description="Reason for dispute")


class DisputeJobTool(BaseTool):
    """Tool for disputing a delivery."""
    
    name: str = "dispute_job"
    description: str = """Dispute a delivered job if the work is unsatisfactory.
    Use this as a last resort when the deliverable doesn't meet requirements.
    Required: job_id, poster_wallet, reason"""
    args_schema: Type[BaseModel] = DisputeJobInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        job_id: str,
        poster_wallet: str,
        reason: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to dispute a job."""
        url = f"{self.base_url}/agent/jobs/{job_id}/dispute"
        
        payload = {
            "poster_wallet": poster_wallet,
            "reason": reason,
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "message": f"Dispute filed for job {job_id}",
                "result": result,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to dispute job: {str(e)}",
            }


class CancelJobInput(BaseModel):
    """Input for cancelling a job."""
    job_id: str = Field(description="The job ID to cancel")
    wallet: str = Field(description="The wallet cancelling the job")


class CancelJobTool(BaseTool):
    """Tool for cancelling a job and refunding escrow."""
    
    name: str = "cancel_job"
    description: str = """Cancel a job and get a refund of the escrow.
    Only the job poster can cancel.
    Required: job_id, wallet"""
    args_schema: Type[BaseModel] = CancelJobInput
    base_url: str = Field(default=DEFAULT_BASE_URL)

    def _run(
        self,
        job_id: str,
        wallet: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        """Execute the tool to cancel a job."""
        url = f"{self.base_url}/agent/jobs/{job_id}/cancel"
        
        payload = {"wallet": wallet}
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "message": f"Job {job_id} cancelled. Escrow refunded.",
                "result": result,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to cancel job: {str(e)}",
            }


# Convenience function to get all tools
def get_all_tools(base_url: str = DEFAULT_BASE_URL) -> List[BaseTool]:
    """Get all RustChain Agent Economy LangChain tools."""
    return [
        PostJobTool(base_url=base_url),
        BrowseJobsTool(base_url=base_url),
        GetJobDetailsTool(base_url=base_url),
        ClaimJobTool(base_url=base_url),
        DeliverJobTool(base_url=base_url),
        AcceptDeliveryTool(base_url=base_url),
        GetReputationTool(base_url=base_url),
        GetMarketStatsTool(base_url=base_url),
        DisputeJobTool(base_url=base_url),
        CancelJobTool(base_url=base_url),
    ]


# Example usage
if __name__ == "__main__":
    # Example: Check market stats
    stats_tool = GetMarketStatsTool()
    result = stats_tool._run()
    print(json.dumps(result, indent=2))
    
    # Example: Browse jobs
    browse_tool = BrowseJobsTool()
    result = browse_tool._run(category="code", limit=5)
    print(json.dumps(result, indent=2))
