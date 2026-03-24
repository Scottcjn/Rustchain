"""
RIP-302 Agent Economy Client

Main client for interacting with RustChain's Agent Economy APIs.
Provides unified access to agent wallets, x402 payments, reputation, and analytics.
"""

from typing import Dict, List, Optional, Any, Union
import requests
import json
from dataclasses import dataclass, field
from datetime import datetime

from rustchain.exceptions import RustChainError, ConnectionError, ValidationError, APIError


@dataclass
class AgentEconomyConfig:
    """Configuration for Agent Economy Client"""
    base_url: str = "https://rustchain.org"
    bottube_url: str = "https://bottube.ai"
    beacon_url: str = "https://beacon.rustchain.org"
    verify_ssl: bool = True
    timeout: int = 30
    api_key: Optional[str] = None
    agent_id: Optional[str] = None
    wallet_address: Optional[str] = None


class AgentEconomyClient:
    """
    Unified client for RustChain RIP-302 Agent Economy APIs.
    
    Provides access to:
    - Agent wallet management (Coinbase Base integration)
    - x402 payment protocol for machine-to-machine payments
    - BoTTube video platform integration
    - Beacon Atlas reputation system
    - Agent analytics and metrics
    - Bounty system for automated claims
    
    Example:
        >>> from rustchain.agent_economy import AgentEconomyClient
        >>> 
        >>> client = AgentEconomyClient(
        ...     agent_id="my-ai-agent",
        ...     wallet_address="agent_wallet_123"
        ... )
        >>> 
        >>> # Get agent reputation
        >>> reputation = client.reputation.get_score()
        >>> print(f"Reputation score: {reputation.score}")
        >>> 
        >>> # Send x402 payment
        >>> payment = client.payments.send(
        ...     to="content-creator-agent",
        ...     amount=0.5,
        ...     memo="Video tip"
        ... )
        >>> 
        >>> client.close()
    """

    def __init__(
        self,
        base_url: str = "https://rustchain.org",
        agent_id: Optional[str] = None,
        wallet_address: Optional[str] = None,
        api_key: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize Agent Economy Client.
        
        Args:
            base_url: Base URL of RustChain node (default: https://rustchain.org)
            agent_id: Unique identifier for this AI agent
            wallet_address: Agent's wallet address for payments
            api_key: Optional API key for premium endpoints
            verify_ssl: Whether to verify SSL certificates (default: True)
            timeout: Request timeout in seconds (default: 30)
        """
        self.config = AgentEconomyConfig(
            base_url=base_url.rstrip("/"),
            verify_ssl=verify_ssl,
            timeout=timeout,
            api_key=api_key,
            agent_id=agent_id,
            wallet_address=wallet_address,
        )
        
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
        if api_key:
            self.session.headers["X-API-Key"] = api_key
        
        # Initialize sub-clients
        from rustchain.agent_economy.agents import AgentManager
        from rustchain.agent_economy.payments import PaymentProcessor
        from rustchain.agent_economy.reputation import ReputationClient
        from rustchain.agent_economy.analytics import AnalyticsClient
        from rustchain.agent_economy.bounties import BountyClient
        
        self.agents = AgentManager(self)
        self.payments = PaymentProcessor(self)
        self.reputation = ReputationClient(self)
        self.analytics = AnalyticsClient(self)
        self.bounties = BountyClient(self)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_payload: Optional[Dict] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Agent Economy API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: URL query parameters
            json_payload: JSON payload for POST/PUT requests
            base_url: Override base URL (for external services like BoTTube)
            
        Returns:
            Response JSON as dict
            
        Raises:
            ConnectionError: If request fails
            APIError: If API returns error
        """
        url_base = base_url or self.config.base_url
        url = f"{url_base}/{endpoint.lstrip('/')}"
        
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_payload,
                headers=headers,
                timeout=self.config.timeout,
            )
            
            try:
                response.raise_for_status()
            except requests.HTTPError as e:
                raise APIError(
                    f"HTTP {response.status_code}: {e}",
                    status_code=response.status_code,
                    response=response.text,
                ) from e
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"raw_response": response.text}
                
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to {url}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise ConnectionError(f"Request timeout to {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Request failed: {e}") from e

    def health(self) -> Dict[str, Any]:
        """
        Check Agent Economy API health.
        
        Returns:
            Dict with health status
        """
        return self._request("GET", "/api/agent/health")

    def get_agent_info(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about an agent.
        
        Args:
            agent_id: Agent ID (uses client's agent_id if not provided)
            
        Returns:
            Dict with agent information
        """
        aid = agent_id or self.config.agent_id
        if not aid:
            raise ValidationError("agent_id must be provided")
        return self._request("GET", f"/api/agent/{aid}")

    def close(self):
        """Close the HTTP session"""
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
