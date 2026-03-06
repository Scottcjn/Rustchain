"""
Agent Wallet Management

Handles agent identity, wallet creation, and Coinbase Base integration.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import secrets

from rustchain.exceptions import ValidationError, APIError


@dataclass
class AgentWallet:
    """
    Represents an AI agent's wallet in the RustChain economy.
    
    Attributes:
        agent_id: Unique agent identifier
        wallet_address: RustChain wallet address
        base_address: Optional Coinbase Base address for cross-chain ops
        created_at: Wallet creation timestamp
        balance: Current RTC balance
        total_earned: Lifetime earnings in RTC
        reputation_score: Current reputation score (0-100)
    """
    agent_id: str
    wallet_address: str
    base_address: Optional[str] = None
    created_at: Optional[datetime] = None
    balance: float = 0.0
    total_earned: float = 0.0
    reputation_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "wallet_address": self.wallet_address,
            "base_address": self.base_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "balance": self.balance,
            "total_earned": self.total_earned,
            "reputation_score": self.reputation_score,
        }


@dataclass
class AgentProfile:
    """
    Complete profile for an AI agent.
    
    Attributes:
        agent_id: Unique identifier
        name: Human-readable name
        description: Agent description
        capabilities: List of agent capabilities
        wallet: Associated wallet
        metadata: Additional metadata
    """
    agent_id: str
    name: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    wallet: Optional[AgentWallet] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "wallet": self.wallet.to_dict() if self.wallet else None,
            "metadata": self.metadata,
        }


class AgentManager:
    """
    Manages agent registration, profiles, and wallet operations.
    
    Example:
        >>> manager = AgentManager(client)
        >>> 
        >>> # Register new agent
        >>> wallet = manager.create_wallet(
        ...     agent_id="video-curator-bot",
        ...     name="Video Curator Bot"
        ... )
        >>> 
        >>> # Get agent profile
        >>> profile = manager.get_profile("video-curator-bot")
        >>> print(f"Capabilities: {profile.capabilities}")
    """
    
    def __init__(self, client):
        self.client = client
        self._cache: Dict[str, AgentWallet] = {}

    def create_wallet(
        self,
        agent_id: str,
        name: Optional[str] = None,
        base_address: Optional[str] = None,
    ) -> AgentWallet:
        """
        Create a new wallet for an AI agent.
        
        Args:
            agent_id: Unique agent identifier
            name: Optional human-readable name
            base_address: Optional Coinbase Base address
            
        Returns:
            AgentWallet instance
            
        Raises:
            ValidationError: If agent_id is invalid
            APIError: If wallet creation fails
        """
        if not agent_id or len(agent_id) < 3:
            raise ValidationError("agent_id must be at least 3 characters")
        
        # Generate deterministic wallet address from agent_id
        wallet_hash = hashlib.sha256(f"agent:{agent_id}".encode()).hexdigest()[:16]
        wallet_address = f"agent_{wallet_hash}"
        
        payload = {
            "agent_id": agent_id,
            "wallet_address": wallet_address,
            "name": name or agent_id,
        }
        
        if base_address:
            payload["base_address"] = base_address
        
        result = self.client._request("POST", "/api/agent/wallet/create", json_payload=payload)
        
        wallet = AgentWallet(
            agent_id=agent_id,
            wallet_address=result.get("wallet_address", wallet_address),
            base_address=base_address,
            created_at=datetime.utcnow(),
        )
        
        self._cache[agent_id] = wallet
        return wallet

    def get_wallet(self, agent_id: str) -> Optional[AgentWallet]:
        """
        Get wallet information for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            AgentWallet or None if not found
        """
        if agent_id in self._cache:
            return self._cache[agent_id]
        
        result = self.client._request("GET", f"/api/agent/wallet/{agent_id}")
        
        if not result or "error" in result:
            return None
        
        wallet = AgentWallet(
            agent_id=agent_id,
            wallet_address=result.get("wallet_address", ""),
            base_address=result.get("base_address"),
            balance=result.get("balance", 0.0),
            total_earned=result.get("total_earned", 0.0),
            reputation_score=result.get("reputation_score", 0.0),
        )
        
        self._cache[agent_id] = wallet
        return wallet

    def get_profile(self, agent_id: str) -> Optional[AgentProfile]:
        """
        Get complete profile for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            AgentProfile or None if not found
        """
        result = self.client._request("GET", f"/api/agent/profile/{agent_id}")
        
        if not result or "error" in result:
            return None
        
        wallet_data = result.get("wallet", {})
        wallet = AgentWallet(
            agent_id=agent_id,
            wallet_address=wallet_data.get("wallet_address", ""),
            base_address=wallet_data.get("base_address"),
            balance=wallet_data.get("balance", 0.0),
        ) if wallet_data else None
        
        return AgentProfile(
            agent_id=agent_id,
            name=result.get("name", agent_id),
            description=result.get("description", ""),
            capabilities=result.get("capabilities", []),
            wallet=wallet,
            metadata=result.get("metadata", {}),
        )

    def update_profile(
        self,
        agent_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Update agent profile.
        
        Args:
            agent_id: Agent identifier
            name: New name
            description: New description
            capabilities: New capabilities list
            metadata: New metadata
            
        Returns:
            True if successful
        """
        payload = {}
        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        if capabilities:
            payload["capabilities"] = capabilities
        if metadata:
            payload["metadata"] = metadata
        
        result = self.client._request(
            "PUT",
            f"/api/agent/profile/{agent_id}",
            json_payload=payload,
        )
        
        return result.get("success", False)

    def list_agents(
        self,
        limit: int = 50,
        offset: int = 0,
        capability: Optional[str] = None,
    ) -> List[AgentProfile]:
        """
        List registered agents.
        
        Args:
            limit: Maximum number of results
            offset: Pagination offset
            capability: Filter by capability
            
        Returns:
            List of AgentProfile
        """
        params = {"limit": limit, "offset": offset}
        if capability:
            params["capability"] = capability
        
        result = self.client._request("GET", "/api/agents", params=params)
        
        agents = []
        for data in result.get("agents", []):
            profile = AgentProfile(
                agent_id=data.get("agent_id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                capabilities=data.get("capabilities", []),
                metadata=data.get("metadata", {}),
            )
            agents.append(profile)
        
        return agents

    def link_base_wallet(
        self,
        agent_id: str,
        base_address: str,
        signature: str,
    ) -> bool:
        """
        Link a Coinbase Base wallet to an agent.
        
        Args:
            agent_id: Agent identifier
            base_address: Coinbase Base wallet address
            signature: Signature proving ownership
            
        Returns:
            True if successful
        """
        payload = {
            "agent_id": agent_id,
            "base_address": base_address,
            "signature": signature,
        }
        
        result = self.client._request(
            "POST",
            "/api/agent/wallet/link-base",
            json_payload=payload,
        )
        
        return result.get("success", False)

    def get_balance(self, agent_id: str) -> Dict[str, float]:
        """
        Get agent wallet balance.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Dict with balance information
        """
        result = self.client._request("GET", f"/api/agent/balance/{agent_id}")
        return {
            "rtc": result.get("rtc", 0.0),
            "wrtc": result.get("wrtc", 0.0),
            "pending": result.get("pending", 0.0),
        }
