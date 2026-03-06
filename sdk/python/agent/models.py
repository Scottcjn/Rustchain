"""Data models for RustChain Agent Economy"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class JobCategory(str, Enum):
    """Available job categories in the marketplace."""
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


class JobStatus(str, Enum):
    """Job status in the marketplace."""
    OPEN = "open"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class Job:
    """Represents a job in the marketplace."""
    id: str
    poster_wallet: str
    title: str
    description: str
    category: str
    reward_rtc: float
    tags: List[str] = field(default_factory=list)
    status: str = "open"
    worker_wallet: Optional[str] = None
    deliverable_url: Optional[str] = None
    result_summary: Optional[str] = None
    activity_log: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create Job from dictionary."""
        return cls(
            id=data.get("id", ""),
            poster_wallet=data.get("poster_wallet", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", ""),
            reward_rtc=float(data.get("reward_rtc", 0)),
            tags=data.get("tags", []),
            status=data.get("status", "open"),
            worker_wallet=data.get("worker_wallet"),
            deliverable_url=data.get("deliverable_url"),
            result_summary=data.get("result_summary"),
            activity_log=data.get("activity_log", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            expires_at=data.get("expires_at"),
        )


@dataclass
class JobCreate:
    """Request to create a new job."""
    poster_wallet: str
    title: str
    description: str
    category: JobCategory
    reward_rtc: float
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request."""
        return {
            "poster_wallet": self.poster_wallet,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "reward_rtc": self.reward_rtc,
            "tags": self.tags,
        }


@dataclass
class JobClaim:
    """Request to claim a job."""
    worker_wallet: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"worker_wallet": self.worker_wallet}


@dataclass
class JobDeliver:
    """Request to deliver completed work."""
    worker_wallet: str
    deliverable_url: str
    result_summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_wallet": self.worker_wallet,
            "deliverable_url": self.deliverable_url,
            "result_summary": self.result_summary,
        }


@dataclass
class JobAccept:
    """Request to accept delivery and release escrow."""
    poster_wallet: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"poster_wallet": self.poster_wallet}


@dataclass
class JobDispute:
    """Request to dispute a delivery."""
    poster_wallet: str
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "poster_wallet": self.poster_wallet,
            "reason": self.reason,
        }


@dataclass
class JobCancel:
    """Request to cancel a job and refund escrow."""
    poster_wallet: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"poster_wallet": self.poster_wallet}


@dataclass
class Reputation:
    """Reputation/trust score for a wallet."""
    wallet: str
    trust_score: float
    total_jobs_completed: int
    total_jobs_disputed: int
    total_earned_rtc: float
    average_rating: float
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reputation":
        return cls(
            wallet=data.get("wallet", ""),
            trust_score=float(data.get("trust_score", 0)),
            total_jobs_completed=int(data.get("total_jobs_completed", 0)),
            total_jobs_disputed=int(data.get("total_jobs_disputed", 0)),
            total_earned_rtc=float(data.get("total_earned_rtc", 0)),
            average_rating=float(data.get("average_rating", 0)),
            history=data.get("history", []),
        )


@dataclass
class MarketplaceStats:
    """Marketplace statistics."""
    total_jobs: int
    open_jobs: int
    active_workers: int
    total_volume_rtc: float
    platform_fee_rtc: float
    average_reward_rtc: float
    category_distribution: Dict[str, int] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketplaceStats":
        return cls(
            total_jobs=int(data.get("total_jobs", 0)),
            open_jobs=int(data.get("open_jobs", 0)),
            active_workers=int(data.get("active_workers", 0)),
            total_volume_rtc=float(data.get("total_volume_rtc", 0)),
            platform_fee_rtc=float(data.get("platform_fee_rtc", 0)),
            average_reward_rtc=float(data.get("average_reward_rtc", 0)),
            category_distribution=data.get("category_distribution", {}),
        )
