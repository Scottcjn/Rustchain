"""
AgentFolio — Unified agent profile aggregating Beacon + Agent Economy data.

An AgentFolio is a best-effort snapshot of an agent's identity, reputation,
and activity across both the Beacon Atlas and Agent Economy (RIP-302) systems.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agentfolio_beacon.bridge import BeaconBridge


@dataclass
class AgentFolio:
    """
    Unified agent profile from Beacon Atlas + Agent Economy sources.

    All fields are best-effort — missing data is represented as None or 0.
    This is a read-only snapshot, not a live connection.

    Attributes:
        agent_id: Unique agent identifier
        beacon_pubkey_hex: Ed25519 pubkey from Beacon relay registration
        wallet_address: Agent Economy wallet address
        base_address: Optional Coinbase Base address

        # Reputation (Beacon side)
        beacon_score: Beacon reputation score (integer, from beacon_reputation)
        beacon_bounties_completed: Bounties completed per Beacon
        economy_score: RIP-302 reputation score (float, 0-100)
        economy_bounties_completed: Bounties completed per Economy SDK
        contracts_completed: Contracts completed (Beacon)
        contracts_breached: Contracts breached (Beacon)

        # Activity summary
        total_envelopes_sent: Count of beacon_envelopes for this agent
        active_contracts: Contracts currently in 'active' state
        open_claims: Bounties claimed but not yet completed

        # Metadata
        first_seen_beacon: Unix timestamp of first Beacon registration
        first_seen_economy: Unix timestamp of first Economy wallet creation
        assembled_at: Unix timestamp when this folio was assembled
    """
    # Core identity
    agent_id: str = ""
    beacon_pubkey_hex: Optional[str] = None
    wallet_address: Optional[str] = None
    base_address: Optional[str] = None

    # Reputation (Beacon)
    beacon_score: Optional[int] = None
    beacon_bounties_completed: int = 0
    beacon_contracts_completed: int = 0
    beacon_contracts_breached: int = 0

    # Reputation (Economy)
    economy_score: Optional[float] = None
    economy_bounties_completed: int = 0

    # Activity summary
    total_envelopes_sent: int = 0
    active_contracts: int = 0
    open_claims: int = 0

    # Metadata
    first_seen_beacon: Optional[float] = None
    first_seen_economy: Optional[float] = None
    assembled_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "beacon_pubkey_hex": self.beacon_pubkey_hex,
            "wallet_address": self.wallet_address,
            "base_address": self.base_address,
            "beacon_score": self.beacon_score,
            "beacon_bounties_completed": self.beacon_bounties_completed,
            "beacon_contracts_completed": self.beacon_contracts_completed,
            "beacon_contracts_breached": self.beacon_contracts_breached,
            "economy_score": self.economy_score,
            "economy_bounties_completed": self.economy_bounties_completed,
            "total_envelopes_sent": self.total_envelopes_sent,
            "active_contracts": self.active_contracts,
            "open_claims": self.open_claims,
            "first_seen_beacon": self.first_seen_beacon,
            "first_seen_economy": self.first_seen_economy,
            "assembled_at": self.assembled_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentFolio":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        parts = [f"AgentFolio({self.agent_id}"]
        if self.beacon_score is not None:
            parts.append(f"beacon={self.beacon_score}")
        if self.economy_score is not None:
            parts.append(f"economy={self.economy_score:.0f}")
        if self.total_envelopes_sent:
            parts.append(f"envelopes={self.total_envelopes_sent}")
        if self.active_contracts:
            parts.append(f"contracts={self.active_contracts}")
        parts.append(")")
        return " ".join(parts)

    @property
    def has_beacon_identity(self) -> bool:
        """Whether the agent has a registered Beacon identity."""
        return self.beacon_pubkey_hex is not None

    @property
    def has_economy_wallet(self) -> bool:
        """Whether the agent has an Economy wallet."""
        return self.wallet_address is not None

    @property
    def combined_reputation_score(self) -> Optional[float]:
        """
        Return a combined reputation score, preferring Economy score
        (more granular) and falling back to Beacon score.
        """
        if self.economy_score is not None:
            return self.economy_score
        if self.beacon_score is not None:
            return float(self.beacon_score)
        return None


def assemble_folio(
    agent_id: str,
    economy_client,
    beacon_bridge: "BeaconBridge",
) -> AgentFolio:
    """
    Assemble a unified AgentFolio for the given agent.

    This is the primary entry point. It queries both the Agent Economy SDK
    and the Beacon Bridge, aggregating all available data. Failures in
    either source are silently caught — the folio will have None/0 for
    missing fields.

    Args:
        agent_id: The agent to assemble a folio for
        economy_client: An AgentEconomyClient instance
        beacon_bridge: A BeaconBridge wrapping the same (or different) client

    Returns:
        AgentFolio with best-effort populated fields

    Example:
        >>> from rustchain.agent_economy import AgentEconomyClient
        >>> from agentfolio_beacon import BeaconBridge, assemble_folio
        >>>
        >>> client = AgentEconomyClient(base_url="http://localhost:5000")
        >>> bridge = BeaconBridge(client)
        >>> folio = assemble_folio("my-agent", client, bridge)
        >>> print(folio.summary())
    """
    folio = AgentFolio(agent_id=agent_id, assembled_at=time.time())

    # --- Beacon Atlas data ---
    try:
        beacon_data = beacon_bridge.lookup_agent_everything(agent_id)

        # Relay agent info
        relay = beacon_data.get("relay_agent")
        if relay:
            folio.beacon_pubkey_hex = relay.get("pubkey_hex")
            folio.base_address = relay.get("coinbase_address")
            folio.first_seen_beacon = relay.get("created_at")

        # Beacon reputation
        rep = beacon_data.get("reputation")
        if rep:
            folio.beacon_score = rep.get("score")
            folio.beacon_bounties_completed = rep.get("bounties_completed", 0)
            folio.beacon_contracts_completed = rep.get("contracts_completed", 0)
            folio.beacon_contracts_breached = rep.get("contracts_breached", 0)

        # Activity counts
        folio.total_envelopes_sent = beacon_data.get("envelopes_recent", 0)
        folio.active_contracts = beacon_data.get("active_contracts", 0)

    except Exception:
        pass  # Beacon data unavailable — leave fields as defaults

    # --- Agent Economy data ---
    try:
        # Wallet info
        wallet = economy_client.agents.get_wallet(agent_id)
        if wallet:
            folio.wallet_address = wallet.wallet_address
            if wallet.base_address:
                folio.base_address = wallet.base_address

        # Reputation
        try:
            rep_score = economy_client.reputation.get_score(agent_id)
            if rep_score:
                folio.economy_score = rep_score.score
        except Exception:
            pass

        # Bounty claims (open = claimed but not completed)
        try:
            claims = economy_client.bounties.get_my_claims(agent_id=agent_id)
            folio.open_claims = len(claims)
        except Exception:
            pass

    except Exception:
        pass  # Economy data unavailable — leave fields as defaults

    return folio


def folio_diff(old: AgentFolio, new: AgentFolio) -> Dict[str, Any]:
    """
    Compute the difference between two folios of the same agent.

    Returns a dict of changed fields with (old_value, new_value) tuples.
    """
    changes = {}
    old_dict = old.to_dict()
    new_dict = new.to_dict()

    for key in old_dict:
        if key == "assembled_at":
            continue  # Always different
        old_val = old_dict[key]
        new_val = new_dict[key]
        if old_val != new_val:
            changes[key] = (old_val, new_val)

    return changes


def folios_to_table(folios: list) -> List[Dict[str, Any]]:
    """
    Convert a list of AgentFolios to a table-friendly format.

    Returns list of dicts suitable for CSV/JSON export.
    """
    rows = []
    for f in folios:
        row = f.to_dict()
        row["combined_score"] = f.combined_reputation_score
        row["has_beacon_identity"] = f.has_beacon_identity
        row["has_economy_wallet"] = f.has_economy_wallet
        rows.append(row)
    return rows
