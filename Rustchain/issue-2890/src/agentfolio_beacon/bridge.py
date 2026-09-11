"""
BeaconBridge — Adapter connecting Agent Economy SDK to Beacon Atlas APIs.

Provides methods on top of AgentEconomyClient that query Beacon Atlas
Flask endpoints (relay agents, reputation, contracts, envelopes).

All methods are read-only — no state mutation.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class BeaconBridge:
    """
    Bridge adapter that queries Beacon Atlas data via the Agent Economy client.

    The Beacon Atlas Flask API (node/beacon_api.py) exposes these endpoints:
      - GET /api/agent/<id>         — single relay agent
      - GET /beacon/atlas           — all relay agents
      - GET /api/reputation/<id>    — agent reputation
      - GET /api/contracts          — all contracts
      - GET /api/bounties           — open bounties

    This adapter wraps an AgentEconomyClient and routes Beacon-specific
    queries through it, returning plain dicts/lists (no SDK dataclasses).

    Example:
        >>> from rustchain.agent_economy import AgentEconomyClient
        >>> from agentfolio_beacon import BeaconBridge
        >>>
        >>> client = AgentEconomyClient(base_url="http://localhost:5000")
        >>> bridge = BeaconBridge(client)
        >>>
        >>> agents = bridge.list_relay_agents()
        >>> rep = bridge.get_beacon_reputation("my-agent")
    """

    def __init__(self, economy_client, beacon_base_url: Optional[str] = None):
        """
        Initialize the bridge.

        Args:
            economy_client: An AgentEconomyClient instance
            beacon_base_url: Override URL for Beacon API. If None, uses
                             the economy client's base_url (assumes co-located).
        """
        self._client = economy_client
        self._beacon_url = beacon_base_url

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Route request through the economy client, optionally overriding base URL."""
        if self._beacon_url:
            kwargs["base_url"] = self._beacon_url
        return self._client._request(method, endpoint, **kwargs)

    # --- Relay Agent Discovery ---

    def get_relay_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single relay agent by ID.

        Maps to: GET /api/agent/<agent_id>

        Returns:
            Agent dict with agent_id, pubkey_hex, name, status, etc.
            or None if not found.
        """
        try:
            result = self._request("GET", f"/api/agent/{agent_id}")
            if isinstance(result, dict) and "error" in result:
                return None
            return result
        except Exception:
            return None

    def list_relay_agents(
        self,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all registered relay agents.

        Maps to: GET /beacon/atlas

        Args:
            status: Optional status filter (e.g. "active")

        Returns:
            List of agent dicts.
        """
        try:
            params = {}
            if status:
                params["status"] = status
            result = self._request("GET", "/beacon/atlas", params=params)
            if isinstance(result, dict) and "agents" in result:
                return result["agents"]
            if isinstance(result, list):
                return result
            return []
        except Exception:
            return []

    # --- Beacon Reputation ---

    def get_beacon_reputation(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an agent's Beacon reputation score.

        Maps to: GET /api/reputation/<agent_id>

        Returns:
            Dict with score, bounties_completed, contracts_completed, etc.
            or None if not found.
        """
        try:
            result = self._request("GET", f"/api/reputation/{agent_id}")
            if isinstance(result, dict) and "error" in result:
                return None
            return result
        except Exception:
            return None

    def list_all_reputation(self) -> List[Dict[str, Any]]:
        """
        List all agent reputations (sorted by score descending).

        Maps to: GET /api/reputation

        Returns:
            List of reputation dicts.
        """
        try:
            result = self._request("GET", "/api/reputation")
            if isinstance(result, list):
                return result
            return []
        except Exception:
            return []

    # --- Contracts ---

    def get_contracts(
        self,
        agent_id: Optional[str] = None,
        state: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get contracts, optionally filtered by agent or state.

        Maps to: GET /api/contracts

        Args:
            agent_id: Filter to contracts involving this agent
            state: Filter by contract state (offered, active, completed, etc.)

        Returns:
            List of contract dicts.
        """
        try:
            result = self._request("GET", "/api/contracts")
            contracts = result if isinstance(result, list) else []

            if agent_id:
                contracts = [
                    c for c in contracts
                    if c.get("from_agent") == agent_id or c.get("to_agent") == agent_id
                ]
            if state:
                contracts = [c for c in contracts if c.get("state") == state]

            return contracts
        except Exception:
            return []

    def count_active_contracts(self, agent_id: str) -> int:
        """Count contracts in 'active' state for a given agent."""
        contracts = self.get_contracts(agent_id=agent_id, state="active")
        return len(contracts)

    # --- Bounties (Beacon side) ---

    def get_open_bounties(self) -> List[Dict[str, Any]]:
        """
        Get open bounties from Beacon Atlas.

        Maps to: GET /api/bounties

        Returns:
            List of bounty dicts.
        """
        try:
            result = self._request("GET", "/api/bounties")
            if isinstance(result, list):
                return result
            return []
        except Exception:
            return []

    # --- Envelope summaries (direct DB query via API) ---

    def get_recent_envelopes(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get recent beacon envelope summaries.

        Note: This endpoint may not exist on all nodes. Returns empty list
        on failure rather than raising.

        Maps to: GET /api/beacon/envelopes (if available)

        Args:
            agent_id: Filter envelopes by agent
            limit: Maximum number of results

        Returns:
            List of envelope summary dicts.
        """
        try:
            params = {"limit": limit}
            if agent_id:
                params["agent_id"] = agent_id
            result = self._request("GET", "/api/beacon/envelopes", params=params)
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "envelopes" in result:
                return result["envelopes"]
            return []
        except Exception:
            return []

    def count_agent_envelopes(self, agent_id: str) -> int:
        """Count total envelopes sent by an agent (best effort)."""
        envelopes = self.get_recent_envelopes(agent_id=agent_id, limit=10000)
        return len(envelopes)

    # --- Health ---

    def beacon_health(self) -> Optional[Dict[str, Any]]:
        """
        Check Beacon Atlas API health.

        Maps to: GET /api/health

        Returns:
            Health dict or None on failure.
        """
        try:
            result = self._request("GET", "/api/health")
            return result if isinstance(result, dict) else None
        except Exception:
            return None

    # --- Unified agent lookup ---

    def lookup_agent_everything(self, agent_id: str) -> Dict[str, Any]:
        """
        Convenience method: fetch all Beacon data for a single agent.

        Returns a dict with:
            - relay_agent: relay agent record or None
            - reputation: beacon reputation or None
            - active_contracts: count of active contracts
            - total_contracts: total contract count involving agent
            - envelopes_recent: recent envelope count
        """
        return {
            "relay_agent": self.get_relay_agent(agent_id),
            "reputation": self.get_beacon_reputation(agent_id),
            "active_contracts": self.count_active_contracts(agent_id),
            "total_contracts": len(self.get_contracts(agent_id=agent_id)),
            "envelopes_recent": self.count_agent_envelopes(agent_id),
        }
