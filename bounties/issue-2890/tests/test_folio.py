"""
Tests for AgentFolio dataclass and assemble_folio function.

Run with: pytest tests/test_folio.py -v
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentfolio_beacon.folio import (
    AgentFolio,
    assemble_folio,
    folio_diff,
    folios_to_table,
)


class TestAgentFolioDataclass:
    """Test AgentFolio dataclass."""

    def test_default_values(self):
        """Test default field values."""
        folio = AgentFolio(agent_id="test-agent")
        assert folio.agent_id == "test-agent"
        assert folio.beacon_pubkey_hex is None
        assert folio.wallet_address is None
        assert folio.beacon_score is None
        assert folio.economy_score is None
        assert folio.total_envelopes_sent == 0
        assert folio.assembled_at == 0.0

    def test_to_dict(self):
        """Test dictionary serialization."""
        folio = AgentFolio(
            agent_id="test-agent",
            beacon_pubkey_hex="deadbeef",
            wallet_address="wallet_123",
            beacon_score=75,
            economy_score=82.5,
            total_envelopes_sent=10,
            active_contracts=2,
            assembled_at=1712700000.0,
        )
        d = folio.to_dict()
        assert d["agent_id"] == "test-agent"
        assert d["beacon_pubkey_hex"] == "deadbeef"
        assert d["wallet_address"] == "wallet_123"
        assert d["beacon_score"] == 75
        assert d["economy_score"] == 82.5
        assert d["total_envelopes_sent"] == 10

    def test_from_dict(self):
        """Test dictionary deserialization."""
        data = {
            "agent_id": "test-agent",
            "beacon_pubkey_hex": "deadbeef",
            "wallet_address": "wallet_123",
            "beacon_score": 75,
            "economy_score": 82.5,
            "total_envelopes_sent": 10,
            "active_contracts": 2,
            "assembled_at": 1712700000.0,
            "extra_field": "should_be_ignored",  # Unknown fields ignored
        }
        folio = AgentFolio.from_dict(data)
        assert folio.agent_id == "test-agent"
        assert folio.beacon_pubkey_hex == "deadbeef"
        assert not hasattr(folio, "extra_field")

    def test_summary_with_data(self):
        """Test human-readable summary with data."""
        folio = AgentFolio(
            agent_id="test-agent",
            beacon_score=75,
            economy_score=82.5,
            total_envelopes_sent=10,
            active_contracts=2,
        )
        summary = folio.summary()
        assert "test-agent" in summary
        assert "beacon=75" in summary
        assert "economy=82" in summary
        assert "envelopes=10" in summary
        assert "contracts=2" in summary

    def test_summary_minimal(self):
        """Test summary with minimal data."""
        folio = AgentFolio(agent_id="minimal-agent")
        summary = folio.summary()
        assert "minimal-agent" in summary
        assert "beacon=" not in summary
        assert "economy=" not in summary

    def test_has_beacon_identity(self):
        """Test beacon identity property."""
        folio_with = AgentFolio(agent_id="a", beacon_pubkey_hex="deadbeef")
        folio_without = AgentFolio(agent_id="b")
        assert folio_with.has_beacon_identity is True
        assert folio_without.has_beacon_identity is False

    def test_has_economy_wallet(self):
        """Test economy wallet property."""
        folio_with = AgentFolio(agent_id="a", wallet_address="wallet_123")
        folio_without = AgentFolio(agent_id="b")
        assert folio_with.has_economy_wallet is True
        assert folio_without.has_economy_wallet is False

    def test_combined_reputation_score_prefers_economy(self):
        """Test combined score prefers economy score."""
        folio = AgentFolio(
            agent_id="a",
            beacon_score=75,
            economy_score=82.5,
        )
        assert folio.combined_reputation_score == 82.5

    def test_combined_reputation_score_falls_back_to_beacon(self):
        """Test combined score falls back to beacon score."""
        folio = AgentFolio(
            agent_id="a",
            beacon_score=75,
            economy_score=None,
        )
        assert folio.combined_reputation_score == 75.0

    def test_combined_reputation_score_none(self):
        """Test combined score is None when both unavailable."""
        folio = AgentFolio(agent_id="a")
        assert folio.combined_reputation_score is None


class TestAssembleFolio:
    """Test folio assembly function."""

    def _make_mock_client_and_bridge(self):
        """Create mock economy client and beacon bridge."""
        # Mock economy client
        economy_client = MagicMock()

        # Mock wallet
        mock_wallet = MagicMock()
        mock_wallet.wallet_address = "wallet_abc"
        mock_wallet.base_address = "0xBase123"
        economy_client.agents.get_wallet.return_value = mock_wallet

        # Mock reputation
        mock_rep_score = MagicMock()
        mock_rep_score.score = 85.0
        economy_client.reputation.get_score.return_value = mock_rep_score

        # Mock bounty claims
        economy_client.bounties.get_my_claims.return_value = [
            {"bounty_id": "b1"},
            {"bounty_id": "b2"},
        ]

        # Mock beacon bridge
        beacon_bridge = MagicMock()
        beacon_bridge.lookup_agent_everything.return_value = {
            "relay_agent": {
                "agent_id": "test-agent",
                "pubkey_hex": "deadbeef",
                "coinbase_address": "0xRelay456",
                "created_at": 1712600000,
            },
            "reputation": {
                "agent_id": "test-agent",
                "score": 75,
                "bounties_completed": 5,
                "contracts_completed": 3,
                "contracts_breached": 1,
            },
            "active_contracts": 2,
            "total_contracts": 5,
            "envelopes_recent": 10,
        }

        return economy_client, beacon_bridge

    def test_assemble_folio_populates_all_fields(self):
        """Test that folio assembly populates fields from both sources."""
        economy_client, beacon_bridge = self._make_mock_client_and_bridge()

        folio = assemble_folio("test-agent", economy_client, beacon_bridge)

        # Identity
        assert folio.agent_id == "test-agent"
        assert folio.beacon_pubkey_hex == "deadbeef"
        assert folio.wallet_address == "wallet_abc"
        # Economy wallet's base_address overwrites beacon's coinbase_address
        # (economy data is assembled after beacon data)
        assert folio.base_address == "0xBase123"

        # Beacon reputation
        assert folio.beacon_score == 75
        assert folio.beacon_bounties_completed == 5
        assert folio.beacon_contracts_completed == 3
        assert folio.beacon_contracts_breached == 1

        # Economy reputation
        assert folio.economy_score == 85.0

        # Activity
        assert folio.total_envelopes_sent == 10
        assert folio.active_contracts == 2
        assert folio.open_claims == 2

        # Metadata
        assert folio.first_seen_beacon == 1712600000
        assert folio.assembled_at > 0

    def test_assemble_folio_handles_beacon_failure(self):
        """Test folio assembly continues when Beacon data unavailable."""
        economy_client = MagicMock()
        mock_wallet = MagicMock()
        mock_wallet.wallet_address = "wallet_abc"
        mock_wallet.base_address = None
        economy_client.agents.get_wallet.return_value = mock_wallet

        mock_rep_score = MagicMock()
        mock_rep_score.score = 80.0
        economy_client.reputation.get_score.return_value = mock_rep_score
        economy_client.bounties.get_my_claims.return_value = []

        beacon_bridge = MagicMock()
        beacon_bridge.lookup_agent_everything.side_effect = Exception("Beacon down")

        folio = assemble_folio("test-agent", economy_client, beacon_bridge)

        # Economy data should still be populated
        assert folio.wallet_address == "wallet_abc"
        assert folio.economy_score == 80.0
        # Beacon data should be defaults
        assert folio.beacon_score is None
        assert folio.beacon_pubkey_hex is None

    def test_assemble_folio_handles_economy_failure(self):
        """Test folio assembly continues when Economy data unavailable."""
        economy_client = MagicMock()
        economy_client.agents.get_wallet.side_effect = Exception("Economy down")

        beacon_bridge = MagicMock()
        beacon_bridge.lookup_agent_everything.return_value = {
            "relay_agent": {
                "agent_id": "test-agent",
                "pubkey_hex": "deadbeef",
                "created_at": 1712600000,
            },
            "reputation": {
                "score": 75,
                "bounties_completed": 5,
                "contracts_completed": 3,
                "contracts_breached": 0,
            },
            "active_contracts": 2,
            "total_contracts": 5,
            "envelopes_recent": 10,
        }

        folio = assemble_folio("test-agent", economy_client, beacon_bridge)

        # Beacon data should still be populated
        assert folio.beacon_pubkey_hex == "deadbeef"
        assert folio.beacon_score == 75
        # Economy data should be defaults
        assert folio.wallet_address is None
        assert folio.economy_score is None

    def test_assemble_folio_handles_all_failure(self):
        """Test folio assembly returns empty folio when both sources fail."""
        economy_client = MagicMock()
        economy_client.agents.get_wallet.side_effect = Exception("Down")

        beacon_bridge = MagicMock()
        beacon_bridge.lookup_agent_everything.side_effect = Exception("Down")

        folio = assemble_folio("test-agent", economy_client, beacon_bridge)

        assert folio.agent_id == "test-agent"
        assert folio.beacon_pubkey_hex is None
        assert folio.wallet_address is None
        assert folio.assembled_at > 0

    def test_assemble_folio_handles_missing_optional_fields(self):
        """Test folio assembly handles missing optional fields gracefully."""
        economy_client = MagicMock()
        mock_wallet = MagicMock()
        mock_wallet.wallet_address = "wallet_abc"
        mock_wallet.base_address = None  # No base address
        economy_client.agents.get_wallet.return_value = mock_wallet

        # Reputation lookup fails
        economy_client.reputation.get_score.side_effect = Exception("No rep")
        economy_client.bounties.get_my_claims.side_effect = Exception("No claims")

        beacon_bridge = MagicMock()
        beacon_bridge.lookup_agent_everything.return_value = {
            "relay_agent": None,  # No relay agent
            "reputation": None,   # No beacon reputation
            "active_contracts": 0,
            "total_contracts": 0,
            "envelopes_recent": 0,
        }

        folio = assemble_folio("test-agent", economy_client, beacon_bridge)

        assert folio.wallet_address == "wallet_abc"
        assert folio.base_address is None
        assert folio.beacon_pubkey_hex is None
        assert folio.beacon_score is None
        assert folio.economy_score is None


class TestFolioDiff:
    """Test folio difference computation."""

    def test_detects_changes(self):
        """Test that changed fields are detected."""
        old = AgentFolio(
            agent_id="test",
            beacon_score=70,
            total_envelopes_sent=5,
            assembled_at=1000.0,
        )
        new = AgentFolio(
            agent_id="test",
            beacon_score=80,
            total_envelopes_sent=10,
            assembled_at=2000.0,
        )

        changes = folio_diff(old, new)

        assert "beacon_score" in changes
        assert changes["beacon_score"] == (70, 80)
        assert "total_envelopes_sent" in changes
        assert changes["total_envelopes_sent"] == (5, 10)
        # assembled_at should be excluded
        assert "assembled_at" not in changes

    def test_no_changes(self):
        """Test that identical folios show no changes."""
        old = AgentFolio(agent_id="test", beacon_score=70)
        new = AgentFolio(agent_id="test", beacon_score=70)

        changes = folio_diff(old, new)

        assert changes == {}


class TestFoliosToTable:
    """Test folio table conversion."""

    def test_converts_to_table(self):
        """Test folios are converted to table format."""
        folios = [
            AgentFolio(
                agent_id="agent-a",
                beacon_score=75,
                beacon_pubkey_hex="deadbeef",
                wallet_address="wallet_1",
            ),
            AgentFolio(
                agent_id="agent-b",
                economy_score=85.0,
            ),
        ]

        table = folios_to_table(folios)

        assert len(table) == 2
        assert table[0]["agent_id"] == "agent-a"
        assert table[0]["combined_score"] == 75.0
        assert table[0]["has_beacon_identity"] is True
        assert table[0]["has_economy_wallet"] is True

        assert table[1]["agent_id"] == "agent-b"
        assert table[1]["combined_score"] == 85.0
        assert table[1]["has_beacon_identity"] is False
        assert table[1]["has_economy_wallet"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
