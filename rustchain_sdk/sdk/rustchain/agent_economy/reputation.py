"""
Beacon Atlas Reputation System

Manages agent reputation scores, attestations, and trust metrics.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class ReputationTier(Enum):
    """Reputation tier enumeration"""
    UNKNOWN = "unknown"
    NEW = "new"
    ESTABLISHED = "established"
    TRUSTED = "trusted"
    VERIFIED = "verified"
    ELITE = "elite"


@dataclass
class ReputationScore:
    """
    Complete reputation score for an agent.
    
    Attributes:
        agent_id: Agent identifier
        score: Overall score (0-100)
        tier: Reputation tier
        total_transactions: Total transactions completed
        successful_transactions: Successful transactions
        failed_transactions: Failed transactions
        avg_payment_size: Average payment size
        dispute_count: Number of disputes
        attestations_count: Number of attestations
        created_at: First activity timestamp
        last_active: Last activity timestamp
        badges: List of earned badges
    """
    agent_id: str
    score: float = 0.0
    tier: ReputationTier = ReputationTier.UNKNOWN
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    avg_payment_size: float = 0.0
    dispute_count: int = 0
    attestations_count: int = 0
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    badges: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "score": self.score,
            "tier": self.tier.value,
            "total_transactions": self.total_transactions,
            "successful_transactions": self.successful_transactions,
            "failed_transactions": self.failed_transactions,
            "avg_payment_size": self.avg_payment_size,
            "dispute_count": self.dispute_count,
            "attestations_count": self.attestations_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "badges": self.badges,
        }
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_transactions == 0:
            return 0.0
        return (self.successful_transactions / self.total_transactions) * 100
    
    @property
    def is_trusted(self) -> bool:
        """Check if agent is trusted or higher"""
        return self.tier in (ReputationTier.TRUSTED, ReputationTier.VERIFIED, ReputationTier.ELITE)


@dataclass
class Attestation:
    """
    Reputation attestation from one agent about another.
    
    Attributes:
        attestation_id: Unique identifier
        from_agent: Attesting agent
        to_agent: Attested agent
        rating: Rating (1-5 stars)
        comment: Optional comment
        transaction_id: Related transaction ID
        created_at: Creation timestamp
        verified: Whether attestation is verified
    """
    attestation_id: str
    from_agent: str
    to_agent: str
    rating: int
    comment: Optional[str] = None
    transaction_id: Optional[str] = None
    created_at: Optional[datetime] = None
    verified: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "attestation_id": self.attestation_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "rating": self.rating,
            "comment": self.comment,
            "transaction_id": self.transaction_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified": self.verified,
        }


class ReputationClient:
    """
    Client for Beacon Atlas reputation system.
    
    Provides reputation scoring, attestations, and trust metrics
    for AI agents in the RustChain economy.
    
    Example:
        >>> client = ReputationClient(agent_economy_client)
        >>> 
        >>> # Get agent reputation
        >>> score = client.get_score("video-curator-bot")
        >>> print(f"Score: {score.score}, Tier: {score.tier}")
        >>> 
        >>> # Submit attestation
        >>> attestation = client.submit_attestation(
        ...     to_agent="content-creator",
        ...     rating=5,
        ...     comment="Excellent service!"
        ... )
        >>> 
        >>> # Get leaderboard
        >>> leaderboard = client.get_leaderboard(limit=10)
    """
    
    def __init__(self, client):
        self.client = client

    def get_score(self, agent_id: Optional[str] = None) -> ReputationScore:
        """
        Get reputation score for an agent.
        
        Args:
            agent_id: Agent identifier (uses client's agent_id if not provided)
            
        Returns:
            ReputationScore instance
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        result = self.client._request("GET", f"/api/agent/reputation/{aid}")
        
        return ReputationScore(
            agent_id=aid,
            score=result.get("score", 0.0),
            tier=ReputationTier(result.get("tier", "unknown")),
            total_transactions=result.get("total_transactions", 0),
            successful_transactions=result.get("successful_transactions", 0),
            failed_transactions=result.get("failed_transactions", 0),
            avg_payment_size=result.get("avg_payment_size", 0.0),
            dispute_count=result.get("dispute_count", 0),
            attestations_count=result.get("attestations_count", 0),
            badges=result.get("badges", []),
        )

    def submit_attestation(
        self,
        to_agent: str,
        rating: int,
        comment: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> Attestation:
        """
        Submit an attestation for another agent.
        
        Args:
            to_agent: Agent being attested
            rating: Rating (1-5 stars)
            comment: Optional comment
            transaction_id: Related transaction ID
            
        Returns:
            Attestation instance
        """
        from_agent = self.client.config.agent_id
        if not from_agent:
            raise ValueError("client must have agent_id configured")
        
        if not 1 <= rating <= 5:
            raise ValueError("rating must be between 1 and 5")
        
        payload = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "rating": rating,
            "comment": comment,
            "transaction_id": transaction_id,
        }
        
        result = self.client._request(
            "POST",
            "/api/agent/reputation/attest",
            json_payload=payload,
        )
        
        return Attestation(
            attestation_id=result.get("attestation_id", ""),
            from_agent=from_agent,
            to_agent=to_agent,
            rating=rating,
            comment=comment,
            transaction_id=transaction_id,
            created_at=datetime.utcnow(),
            verified=result.get("verified", False),
        )

    def get_attestations(
        self,
        agent_id: str,
        limit: int = 50,
        min_rating: Optional[int] = None,
    ) -> List[Attestation]:
        """
        Get attestations for an agent.
        
        Args:
            agent_id: Agent identifier
            limit: Maximum results
            min_rating: Filter by minimum rating
            
        Returns:
            List of Attestation
        """
        params = {"limit": limit}
        if min_rating:
            params["min_rating"] = min_rating
        
        result = self.client._request(
            "GET",
            f"/api/agent/reputation/{agent_id}/attestations",
            params=params,
        )
        
        attestations = []
        for data in result.get("attestations", []):
            attestation = Attestation(
                attestation_id=data.get("attestation_id", ""),
                from_agent=data.get("from_agent", ""),
                to_agent=data.get("to_agent", ""),
                rating=data.get("rating", 0),
                comment=data.get("comment"),
                transaction_id=data.get("transaction_id"),
                verified=data.get("verified", False),
            )
            attestations.append(attestation)
        
        return attestations

    def get_leaderboard(
        self,
        limit: int = 100,
        tier: Optional[ReputationTier] = None,
        capability: Optional[str] = None,
    ) -> List[ReputationScore]:
        """
        Get reputation leaderboard.
        
        Args:
            limit: Maximum results
            tier: Filter by minimum tier
            capability: Filter by capability
            
        Returns:
            List of ReputationScore sorted by score
        """
        params = {"limit": limit}
        if tier:
            params["tier"] = tier.value
        if capability:
            params["capability"] = capability
        
        result = self.client._request(
            "GET",
            "/api/agent/reputation/leaderboard",
            params=params,
        )
        
        scores = []
        for data in result.get("leaders", []):
            score = ReputationScore(
                agent_id=data.get("agent_id", ""),
                score=data.get("score", 0.0),
                tier=ReputationTier(data.get("tier", "unknown")),
                total_transactions=data.get("total_transactions", 0),
                attestations_count=data.get("attestations_count", 0),
                badges=data.get("badges", []),
            )
            scores.append(score)
        
        return scores

    def get_trust_proof(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cryptographic trust proof for an agent.
        
        This can be used to prove reputation to third parties.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            
        Returns:
            Dict with trust proof data
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        return self.client._request("GET", f"/api/agent/reputation/{aid}/proof")

    def dispute_transaction(
        self,
        transaction_id: str,
        reason: str,
        evidence: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        File a dispute for a transaction.
        
        Args:
            transaction_id: Transaction identifier
            reason: Dispute reason
            evidence: List of evidence URLs/hashes
            
        Returns:
            Dict with dispute information
        """
        payload = {
            "transaction_id": transaction_id,
            "reason": reason,
            "evidence": evidence or [],
        }
        
        return self.client._request(
            "POST",
            "/api/agent/reputation/dispute",
            json_payload=payload,
        )

    def get_badges(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get earned badges for an agent.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            
        Returns:
            List of badge information
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        result = self.client._request("GET", f"/api/agent/reputation/{aid}/badges")
        return result.get("badges", [])

    def calculate_tier(self, score: float) -> ReputationTier:
        """
        Calculate reputation tier from score.
        
        Args:
            score: Reputation score (0-100)
            
        Returns:
            ReputationTier
        """
        if score >= 95:
            return ReputationTier.ELITE
        elif score >= 85:
            return ReputationTier.VERIFIED
        elif score >= 70:
            return ReputationTier.TRUSTED
        elif score >= 50:
            return ReputationTier.ESTABLISHED
        elif score >= 20:
            return ReputationTier.NEW
        else:
            return ReputationTier.UNKNOWN
