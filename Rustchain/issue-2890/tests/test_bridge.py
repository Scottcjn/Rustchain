"""
Tests for BeaconBridge adapter.

Run with: pytest tests/test_bridge.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentfolio_beacon.bridge import BeaconBridge


def make_mock_client():
    """Create a mock AgentEconomyClient."""
    client = MagicMock()
    client._request = MagicMock(return_value={})
    return client


class TestBeaconBridgeInit:
    """Test BeaconBridge initialization."""

    def test_init_with_default_url(self):
        """Test bridge uses client's base_url by default."""
        client = make_mock_client()
        client.config.base_url = "http://localhost:5000"
        bridge = BeaconBridge(client)
        assert bridge._beacon_url is None  # Uses client's URL

    def test_init_with_override_url(self):
        """Test bridge can override beacon URL."""
        client = make_mock_client()
        bridge = BeaconBridge(client, beacon_base_url="http://beacon.example.com")
        assert bridge._beacon_url == "http://beacon.example.com"


class TestBeaconBridgeRelayAgents:
    """Test relay agent discovery methods."""

    def test_get_relay_agent_success(self):
        """Test successful relay agent lookup."""
        client = make_mock_client()
        client._request.return_value = {
            "agent_id": "test-agent",
            "pubkey_hex": "deadbeef",
            "name": "Test Agent",
            "status": "active",
        }
        bridge = BeaconBridge(client)

        result = bridge.get_relay_agent("test-agent")

        assert result is not None
        assert result["agent_id"] == "test-agent"
        assert result["pubkey_hex"] == "deadbeef"
        client._request.assert_called_once_with("GET", "/api/agent/test-agent")

    def test_get_relay_agent_not_found(self):
        """Test relay agent not found returns None."""
        client = make_mock_client()
        client._request.return_value = {"error": "Agent not found"}
        bridge = BeaconBridge(client)

        result = bridge.get_relay_agent("nonexistent")

        assert result is None

    def test_get_relay_agent_exception(self):
        """Test relay agent exception returns None."""
        client = make_mock_client()
        client._request.side_effect = Exception("Connection refused")
        bridge = BeaconBridge(client)

        result = bridge.get_relay_agent("test-agent")

        assert result is None

    def test_list_relay_agents(self):
        """Test listing relay agents."""
        client = make_mock_client()
        client._request.return_value = {
            "agents": [
                {"agent_id": "agent-a", "status": "active"},
                {"agent_id": "agent-b", "status": "active"},
            ],
            "total": 2,
        }
        bridge = BeaconBridge(client)

        result = bridge.list_relay_agents()

        assert len(result) == 2
        assert result[0]["agent_id"] == "agent-a"
        client._request.assert_called_once_with("GET", "/beacon/atlas", params={})

    def test_list_relay_agents_with_status_filter(self):
        """Test listing relay agents with status filter."""
        client = make_mock_client()
        client._request.return_value = {
            "agents": [{"agent_id": "agent-a", "status": "active"}],
            "total": 1,
        }
        bridge = BeaconBridge(client)

        result = bridge.list_relay_agents(status="active")

        client._request.assert_called_once_with(
            "GET", "/beacon/atlas", params={"status": "active"}
        )

    def test_list_relay_agents_returns_list_directly(self):
        """Test handling API that returns list directly."""
        client = make_mock_client()
        client._request.return_value = [
            {"agent_id": "agent-a"},
        ]
        bridge = BeaconBridge(client)

        result = bridge.list_relay_agents()

        assert len(result) == 1


class TestBeaconBridgeReputation:
    """Test reputation query methods."""

    def test_get_beacon_reputation_success(self):
        """Test successful reputation lookup."""
        client = make_mock_client()
        client._request.return_value = {
            "agent_id": "test-agent",
            "score": 75,
            "bounties_completed": 5,
            "contracts_completed": 3,
            "contracts_breached": 0,
        }
        bridge = BeaconBridge(client)

        result = bridge.get_beacon_reputation("test-agent")

        assert result is not None
        assert result["score"] == 75
        assert result["bounties_completed"] == 5
        client._request.assert_called_once_with(
            "GET", "/api/reputation/test-agent"
        )

    def test_get_beacon_reputation_not_found(self):
        """Test reputation not found returns None."""
        client = make_mock_client()
        client._request.return_value = {"error": "Agent not found"}
        bridge = BeaconBridge(client)

        result = bridge.get_beacon_reputation("nonexistent")

        assert result is None

    def test_list_all_reputation(self):
        """Test listing all reputations."""
        client = make_mock_client()
        client._request.return_value = [
            {"agent_id": "agent-a", "score": 90},
            {"agent_id": "agent-b", "score": 75},
        ]
        bridge = BeaconBridge(client)

        result = bridge.list_all_reputation()

        assert len(result) == 2
        assert result[0]["score"] == 90


class TestBeaconBridgeContracts:
    """Test contract query methods."""

    def test_get_contracts(self):
        """Test getting all contracts."""
        client = make_mock_client()
        client._request.return_value = [
            {"id": "c1", "from_agent": "a", "to_agent": "b", "state": "active"},
            {"id": "c2", "from_agent": "a", "to_agent": "c", "state": "completed"},
        ]
        bridge = BeaconBridge(client)

        result = bridge.get_contracts()

        assert len(result) == 2

    def test_get_contracts_filtered_by_agent(self):
        """Test filtering contracts by agent."""
        client = make_mock_client()
        client._request.return_value = [
            {"id": "c1", "from_agent": "a", "to_agent": "b", "state": "active"},
            {"id": "c2", "from_agent": "x", "to_agent": "y", "state": "active"},
            {"id": "c3", "from_agent": "b", "to_agent": "a", "state": "completed"},
        ]
        bridge = BeaconBridge(client)

        result = bridge.get_contracts(agent_id="a")

        assert len(result) == 2  # c1 and c3 involve agent "a"

    def test_get_contracts_filtered_by_state(self):
        """Test filtering contracts by state."""
        client = make_mock_client()
        client._request.return_value = [
            {"id": "c1", "state": "active"},
            {"id": "c2", "state": "completed"},
            {"id": "c3", "state": "active"},
        ]
        bridge = BeaconBridge(client)

        result = bridge.get_contracts(state="active")

        assert len(result) == 2

    def test_count_active_contracts(self):
        """Test counting active contracts."""
        client = make_mock_client()
        client._request.return_value = [
            {"id": "c1", "from_agent": "a", "state": "active"},
            {"id": "c2", "from_agent": "a", "state": "completed"},
            {"id": "c3", "from_agent": "a", "state": "active"},
        ]
        bridge = BeaconBridge(client)

        count = bridge.count_active_contracts("a")

        assert count == 2


class TestBeaconBridgeBounties:
    """Test bounty query methods."""

    def test_get_open_bounties(self):
        """Test getting open bounties."""
        client = make_mock_client()
        client._request.return_value = [
            {"id": "b1", "title": "Fix bug", "reward_rtc": 50.0},
        ]
        bridge = BeaconBridge(client)

        result = bridge.get_open_bounties()

        assert len(result) == 1
        assert result[0]["title"] == "Fix bug"
        client._request.assert_called_once_with("GET", "/api/bounties")


class TestBeaconBridgeEnvelopes:
    """Test envelope query methods."""

    def test_get_recent_envelopes(self):
        """Test getting recent envelopes."""
        client = make_mock_client()
        client._request.return_value = [
            {"id": 1, "agent_id": "a", "kind": "heartbeat"},
        ]
        bridge = BeaconBridge(client)

        result = bridge.get_recent_envelopes(agent_id="a", limit=10)

        assert len(result) == 1
        client._request.assert_called_once_with(
            "GET", "/api/beacon/envelopes", params={"limit": 10, "agent_id": "a"}
        )

    def test_get_recent_envelopes_on_failure(self):
        """Test envelope query returns empty list on failure."""
        client = make_mock_client()
        client._request.side_effect = Exception("Endpoint not found")
        bridge = BeaconBridge(client)

        result = bridge.get_recent_envelopes()

        assert result == []

    def test_count_agent_envelopes(self):
        """Test counting agent envelopes."""
        client = make_mock_client()
        client._request.return_value = [
            {"id": i, "agent_id": "a"} for i in range(5)
        ]
        bridge = BeaconBridge(client)

        count = bridge.count_agent_envelopes("a")

        assert count == 5


class TestBeaconBridgeHealth:
    """Test health check."""

    def test_beacon_health_success(self):
        """Test successful health check."""
        client = make_mock_client()
        client._request.return_value = {
            "status": "ok",
            "timestamp": 1712700000,
            "service": "beacon-atlas-api",
        }
        bridge = BeaconBridge(client)

        result = bridge.beacon_health()

        assert result is not None
        assert result["status"] == "ok"

    def test_beacon_health_failure(self):
        """Test health check returns None on failure."""
        client = make_mock_client()
        client._request.side_effect = Exception("Connection refused")
        bridge = BeaconBridge(client)

        result = bridge.beacon_health()

        assert result is None


class TestBeaconBridgeLookupAgentEverything:
    """Test the unified agent lookup convenience method."""

    def test_lookup_agent_everything(self):
        """Test unified agent lookup aggregates all data."""
        client = make_mock_client()

        def mock_request(method, endpoint, **kwargs):
            if endpoint == "/api/agent/test-agent":
                return {
                    "agent_id": "test-agent",
                    "pubkey_hex": "deadbeef",
                    "created_at": 1712600000,
                }
            elif endpoint == "/api/reputation/test-agent":
                return {
                    "agent_id": "test-agent",
                    "score": 80,
                    "bounties_completed": 5,
                    "contracts_completed": 3,
                    "contracts_breached": 0,
                }
            elif endpoint == "/api/contracts":
                return [
                    {"id": "c1", "from_agent": "test-agent", "state": "active"},
                    {"id": "c2", "from_agent": "test-agent", "state": "completed"},
                ]
            elif endpoint == "/api/beacon/envelopes":
                return [{"id": 1, "agent_id": "test-agent"}]
            return {}

        client._request = MagicMock(side_effect=mock_request)
        bridge = BeaconBridge(client)

        result = bridge.lookup_agent_everything("test-agent")

        assert result["relay_agent"] is not None
        assert result["relay_agent"]["pubkey_hex"] == "deadbeef"
        assert result["reputation"] is not None
        assert result["reputation"]["score"] == 80
        assert result["active_contracts"] == 1  # Only "active" state
        assert result["total_contracts"] == 2
        assert result["envelopes_recent"] == 1


class TestBeaconBridgeBaseUrlOverride:
    """Test that beacon_base_url override works correctly."""

    def test_request_uses_override_url(self):
        """Test that requests go to override URL when set."""
        client = make_mock_client()
        bridge = BeaconBridge(client, beacon_base_url="http://beacon.local:9000")

        bridge.get_relay_agent("test-agent")

        # Check that base_url was passed to _request
        call_kwargs = client._request.call_args[1]
        assert call_kwargs["base_url"] == "http://beacon.local:9000"

    def test_request_no_override_when_not_set(self):
        """Test that requests don't include base_url when not overridden."""
        client = make_mock_client()
        bridge = BeaconBridge(client)

        bridge.get_relay_agent("test-agent")

        call_kwargs = client._request.call_args[1]
        assert "base_url" not in call_kwargs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
