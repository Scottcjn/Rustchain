"""
Bounty System Client

Manages bounty discovery, claims, and automated payments.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class BountyStatus(Enum):
    """Bounty status enumeration"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    PAID = "paid"
    CANCELLED = "cancelled"


class BountyTier(Enum):
    """Bounty tier enumeration"""
    TRIVIAL = "trivial"       # 5-15 RTC
    MINOR = "minor"           # 15-30 RTC
    MEDIUM = "medium"         # 30-50 RTC
    MAJOR = "major"           # 50-100 RTC
    CRITICAL = "critical"     # 100-200 RTC
    SECURITY = "security"     # 200+ RTC


@dataclass
class Bounty:
    """
    Represents a RustChain bounty.
    
    Attributes:
        bounty_id: Unique bounty identifier
        title: Bounty title
        description: Full description
        status: Current status
        tier: Bounty tier
        reward: Reward amount in RTC
        reward_range: Reward range string
        created_at: Creation timestamp
        deadline: Submission deadline
        claimant: Agent who claimed the bounty
        issuer: Agent/organization issuing bounty
        tags: List of tags
        requirements: List of requirements
        submissions_count: Number of submissions
    """
    bounty_id: str
    title: str
    description: str
    status: BountyStatus = BountyStatus.OPEN
    tier: BountyTier = BountyTier.MEDIUM
    reward: float = 0.0
    reward_range: str = ""
    created_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    claimant: Optional[str] = None
    issuer: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    submissions_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "bounty_id": self.bounty_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "tier": self.tier.value,
            "reward": self.reward,
            "reward_range": self.reward_range,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "claimant": self.claimant,
            "issuer": self.issuer,
            "tags": self.tags,
            "requirements": self.requirements,
            "submissions_count": self.submissions_count,
        }
    
    @property
    def is_claimable(self) -> bool:
        """Check if bounty can be claimed"""
        return self.status == BountyStatus.OPEN and self.claimant is None
    
    @property
    def is_expired(self) -> bool:
        """Check if bounty deadline has passed"""
        if not self.deadline:
            return False
        return datetime.utcnow() > self.deadline


@dataclass
class BountySubmission:
    """
    Represents a bounty submission.
    
    Attributes:
        submission_id: Unique submission identifier
        bounty_id: Related bounty ID
        submitter: Agent who submitted
        pr_url: Pull request URL
        description: Submission description
        status: Submission status
        submitted_at: Submission timestamp
        review_feedback: Reviewer feedback
        payment_tx: Payment transaction hash
    """
    submission_id: str
    bounty_id: str
    submitter: str
    pr_url: Optional[str] = None
    description: str = ""
    status: BountyStatus = BountyStatus.SUBMITTED
    submitted_at: Optional[datetime] = None
    review_feedback: Optional[str] = None
    payment_tx: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "submission_id": self.submission_id,
            "bounty_id": self.bounty_id,
            "submitter": self.submitter,
            "pr_url": self.pr_url,
            "description": self.description,
            "status": self.status.value,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "review_feedback": self.review_feedback,
            "payment_tx": self.payment_tx,
        }


class BountyClient:
    """
    Client for RustChain bounty system.
    
    Provides bounty discovery, claiming, submission, and
    automated payment processing.
    
    Example:
        >>> bounties = BountyClient(agent_economy_client)
        >>> 
        >>> # Find open bounties
        >>> open_bounties = bounties.list(status=BountyStatus.OPEN)
        >>> 
        >>> # Claim a bounty
        >>> bounty = bounties.claim("bounty_123")
        >>> 
        >>> # Submit work
        >>> submission = bounties.submit(
        ...     bounty_id="bounty_123",
        ...     pr_url="https://github.com/...",
        ...     description="Implemented feature X"
        ... )
        >>> 
        >>> # Check submissions
        >>> my_submissions = bounties.get_my_submissions()
    """
    
    def __init__(self, client):
        self.client = client

    def list(
        self,
        status: Optional[BountyStatus] = None,
        tier: Optional[BountyTier] = None,
        tag: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Bounty]:
        """
        List bounties with optional filters.
        
        Args:
            status: Filter by status
            tier: Filter by tier
            tag: Filter by tag
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Bounty
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value
        if tier:
            params["tier"] = tier.value
        if tag:
            params["tag"] = tag
        
        result = self.client._request("GET", "/api/bounties", params=params)
        
        bounties = []
        for data in result.get("bounties", []):
            bounty = Bounty(
                bounty_id=data.get("bounty_id", ""),
                title=data.get("title", ""),
                description=data.get("description", ""),
                status=BountyStatus(data.get("status", "open")),
                tier=BountyTier(data.get("tier", "medium")),
                reward=data.get("reward", 0.0),
                reward_range=data.get("reward_range", ""),
                claimant=data.get("claimant"),
                issuer=data.get("issuer"),
                tags=data.get("tags", []),
                requirements=data.get("requirements", []),
                submissions_count=data.get("submissions_count", 0),
            )
            bounties.append(bounty)
        
        return bounties

    def get(self, bounty_id: str) -> Optional[Bounty]:
        """
        Get details for a specific bounty.
        
        Args:
            bounty_id: Bounty identifier
            
        Returns:
            Bounty or None if not found
        """
        result = self.client._request("GET", f"/api/bounty/{bounty_id}")
        
        if not result or "error" in result:
            return None
        
        return Bounty(
            bounty_id=bounty_id,
            title=result.get("title", ""),
            description=result.get("description", ""),
            status=BountyStatus(result.get("status", "open")),
            tier=BountyTier(result.get("tier", "medium")),
            reward=result.get("reward", 0.0),
            reward_range=result.get("reward_range", ""),
            claimant=result.get("claimant"),
            issuer=result.get("issuer"),
            tags=result.get("tags", []),
            requirements=result.get("requirements", []),
            submissions_count=result.get("submissions_count", 0),
        )

    def claim(self, bounty_id: str, description: Optional[str] = None) -> bool:
        """
        Claim a bounty.
        
        Args:
            bounty_id: Bounty identifier
            description: Claim description/plan
            
        Returns:
            True if successful
        """
        agent_id = self.client.config.agent_id
        if not agent_id:
            raise ValueError("client must have agent_id configured")
        
        payload = {
            "agent_id": agent_id,
            "description": description,
        }
        
        result = self.client._request(
            "POST",
            f"/api/bounty/{bounty_id}/claim",
            json_payload=payload,
        )
        
        return result.get("success", False)

    def submit(
        self,
        bounty_id: str,
        pr_url: str,
        description: str,
        evidence: Optional[List[str]] = None,
    ) -> BountySubmission:
        """
        Submit work for a bounty.
        
        Args:
            bounty_id: Bounty identifier
            pr_url: Pull request URL with the work
            description: Submission description
            evidence: List of evidence URLs/hashes
            
        Returns:
            BountySubmission instance
        """
        agent_id = self.client.config.agent_id
        if not agent_id:
            raise ValueError("client must have agent_id configured")
        
        payload = {
            "submitter": agent_id,
            "pr_url": pr_url,
            "description": description,
            "evidence": evidence or [],
        }
        
        result = self.client._request(
            "POST",
            f"/api/bounty/{bounty_id}/submit",
            json_payload=payload,
        )
        
        return BountySubmission(
            submission_id=result.get("submission_id", ""),
            bounty_id=bounty_id,
            submitter=agent_id,
            pr_url=pr_url,
            description=description,
            submitted_at=datetime.utcnow(),
        )

    def get_submission(self, submission_id: str) -> Optional[BountySubmission]:
        """
        Get submission details.
        
        Args:
            submission_id: Submission identifier
            
        Returns:
            BountySubmission or None if not found
        """
        result = self.client._request("GET", f"/api/bounty/submission/{submission_id}")
        
        if not result or "error" in result:
            return None
        
        return BountySubmission(
            submission_id=submission_id,
            bounty_id=result.get("bounty_id", ""),
            submitter=result.get("submitter", ""),
            pr_url=result.get("pr_url"),
            description=result.get("description", ""),
            status=BountyStatus(result.get("status", "submitted")),
            review_feedback=result.get("review_feedback"),
            payment_tx=result.get("payment_tx"),
        )

    def get_my_submissions(
        self,
        agent_id: Optional[str] = None,
        status: Optional[BountyStatus] = None,
    ) -> List[BountySubmission]:
        """
        Get submissions for an agent.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            status: Filter by status
            
        Returns:
            List of BountySubmission
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        params = {}
        if status:
            params["status"] = status.value
        
        result = self.client._request(
            "GET",
            f"/api/bounty/submissions/{aid}",
            params=params,
        )
        
        submissions = []
        for data in result.get("submissions", []):
            submission = BountySubmission(
                submission_id=data.get("submission_id", ""),
                bounty_id=data.get("bounty_id", ""),
                submitter=data.get("submitter", ""),
                pr_url=data.get("pr_url"),
                description=data.get("description", ""),
                status=BountyStatus(data.get("status", "submitted")),
                review_feedback=data.get("review_feedback"),
                payment_tx=data.get("payment_tx"),
            )
            submissions.append(submission)
        
        return submissions

    def get_my_claims(
        self,
        agent_id: Optional[str] = None,
        status: Optional[BountyStatus] = None,
    ) -> List[Bounty]:
        """
        Get bounties claimed by an agent.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            status: Filter by status
            
        Returns:
            List of Bounty
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        params = {}
        if status:
            params["status"] = status.value
        
        result = self.client._request(
            "GET",
            f"/api/bounty/claims/{aid}",
            params=params,
        )
        
        bounties = []
        for data in result.get("claims", []):
            bounty = Bounty(
                bounty_id=data.get("bounty_id", ""),
                title=data.get("title", ""),
                description=data.get("description", ""),
                status=BountyStatus(data.get("status", "in_progress")),
                tier=BountyTier(data.get("tier", "medium")),
                reward=data.get("reward", 0.0),
            )
            bounties.append(bounty)
        
        return bounties

    def release_payment(
        self,
        submission_id: str,
        issuer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Release payment for a completed submission.
        
        Args:
            submission_id: Submission identifier
            issuer_id: Issuer agent ID (uses client's if not provided)
            
        Returns:
            Dict with payment information
        """
        issuer = issuer_id or self.client.config.agent_id
        if not issuer:
            raise ValueError("issuer_id must be provided")
        
        return self.client._request(
            "POST",
            f"/api/bounty/submission/{submission_id}/pay",
            json_payload={"issuer_id": issuer},
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get bounty system statistics.
        
        Returns:
            Dict with statistics
        """
        return self.client._request("GET", "/api/bounty/stats")

    def create_bounty(
        self,
        title: str,
        description: str,
        reward: float,
        tier: BountyTier = BountyTier.MEDIUM,
        requirements: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        deadline_days: int = 30,
    ) -> Bounty:
        """
        Create a new bounty.
        
        Args:
            title: Bounty title
            description: Full description
            reward: Reward amount in RTC
            tier: Bounty tier
            requirements: List of requirements
            tags: List of tags
            deadline_days: Days until deadline
            
        Returns:
            Created Bounty
        """
        issuer = self.client.config.agent_id
        if not issuer:
            raise ValueError("client must have agent_id configured")
        
        deadline = datetime.utcnow() + timedelta(days=deadline_days)
        
        payload = {
            "issuer_id": issuer,
            "title": title,
            "description": description,
            "reward": reward,
            "tier": tier.value,
            "requirements": requirements or [],
            "tags": tags or [],
            "deadline": deadline.isoformat(),
        }
        
        result = self.client._request(
            "POST",
            "/api/bounty/create",
            json_payload=payload,
        )
        
        return Bounty(
            bounty_id=result.get("bounty_id", ""),
            title=title,
            description=description,
            tier=tier,
            reward=reward,
            issuer=issuer,
            requirements=requirements or [],
            tags=tags or [],
            deadline=deadline,
            created_at=datetime.utcnow(),
        )
