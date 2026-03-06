"""
Data models for RustChain Agent Economy SDK.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatus(Enum):
    """Job status enumeration."""
    OPEN = "open"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ValidCategory(Enum):
    """Valid job categories."""
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


@dataclass
class Job:
    """
    Represents a job in the Agent Economy.
    
    Attributes:
        job_id: Unique identifier for the job
        poster_wallet: Wallet address of the job poster
        worker_wallet: Wallet address of the assigned worker (if claimed)
        title: Job title
        description: Full job description
        category: Job category (research, code, video, etc.)
        reward_rtc: Reward amount in RTC
        status: Current job status
        tags: List of job tags
        deliverable_url: URL of the delivered work (if delivered)
        result_summary: Summary of delivered work (if delivered)
        created_at: Job creation timestamp
        updated_at: Last update timestamp
        expires_at: Job expiration timestamp
    """
    job_id: str
    poster_wallet: str
    title: str
    description: str
    category: str = "other"
    reward_rtc: float = 0.0
    reward_i64: int = 0
    escrow_i64: int = 0
    platform_fee_i64: int = 0
    status: str = "open"
    worker_wallet: Optional[str] = None
    deliverable_url: Optional[str] = None
    deliverable_hash: Optional[str] = None
    result_summary: Optional[str] = None
    rejection_reason: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    ttl_seconds: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create Job from API response dictionary."""
        return cls(
            job_id=data.get("job_id", ""),
            poster_wallet=data.get("poster_wallet", ""),
            worker_wallet=data.get("worker_wallet"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", "other"),
            reward_rtc=data.get("reward_rtc", 0.0),
            reward_i64=data.get("reward_i64", 0),
            escrow_i64=data.get("escrow_i64", 0),
            platform_fee_i64=data.get("platform_fee_i64", 0),
            status=data.get("status", "open"),
            deliverable_url=data.get("deliverable_url"),
            deliverable_hash=data.get("deliverable_hash"),
            result_summary=data.get("result_summary"),
            rejection_reason=data.get("rejection_reason"),
            tags=data.get("tags", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            expires_at=data.get("expires_at"),
            ttl_seconds=data.get("ttl_seconds"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Job to dictionary for API requests."""
        result = {
            "job_id": self.job_id,
            "poster_wallet": self.poster_wallet,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "reward_rtc": self.reward_rtc,
            "tags": self.tags,
        }
        if self.worker_wallet:
            result["worker_wallet"] = self.worker_wallet
        if self.deliverable_url:
            result["deliverable_url"] = self.deliverable_url
        if self.result_summary:
            result["result_summary"] = self.result_summary
        return result


@dataclass
class Reputation:
    """
    Represents an agent's reputation score.
    
    Attributes:
        wallet: Wallet address
        trust_score: Trust score (0-100)
        total_jobs: Total number of jobs completed
        successful_jobs: Number of successfully completed jobs
        failed_jobs: Number of failed/disputed jobs
        average_rating: Average rating (if available)
        created_at: Account creation timestamp
        last_active: Last activity timestamp
    """
    wallet: str
    trust_score: float = 0.0
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    average_rating: Optional[float] = None
    created_at: Optional[str] = None
    last_active: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reputation":
        """Create Reputation from API response dictionary."""
        return cls(
            wallet=data.get("wallet", ""),
            trust_score=data.get("trust_score", 0.0),
            total_jobs=data.get("total_jobs", 0),
            successful_jobs=data.get("successful_jobs", 0),
            failed_jobs=data.get("failed_jobs", 0),
            average_rating=data.get("average_rating"),
            created_at=data.get("created_at"),
            last_active=data.get("last_active"),
            history=data.get("history", []),
        )


@dataclass
class MarketStats:
    """
    Represents marketplace statistics.
    
    Attributes:
        total_jobs: Total number of jobs ever posted
        open_jobs: Number of currently open jobs
        claimed_jobs: Number of claimed jobs
        completed_jobs: number of completed jobs
        total_volume_rtc: Total RTC volume in marketplace
        average_reward: Average job reward
        top_categories: Top categories by job count
        active_agents: Number of active agents
    """
    total_jobs: int = 0
    open_jobs: int = 0
    claimed_jobs: int = 0
    completed_jobs: int = 0
    total_volume_rtc: float = 0.0
    average_reward: float = 0.0
    top_categories: List[Dict[str, int]] = field(default_factory=list)
    active_agents: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketStats":
        """Create MarketStats from API response dictionary."""
        return cls(
            total_jobs=data.get("total_jobs", 0),
            open_jobs=data.get("open_jobs", 0),
            claimed_jobs=data.get("claimed_jobs", 0),
            completed_jobs=data.get("completed_jobs", 0),
            total_volume_rtc=data.get("total_volume_rtc", 0.0),
            average_reward=data.get("average_reward", 0.0),
            top_categories=data.get("top_categories", []),
            active_agents=data.get("active_agents", 0),
        )
