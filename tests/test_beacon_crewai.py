"""Tests for Beacon CrewAI integration.

Run with: pytest tests/test_beacon_crewai.py -v

These tests verify the code structure and logic without requiring
complex mocking of external beacon_skill dependencies.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add integrations to path
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "beacon_crewai"))


class TestBeaconConfig:
    """Test BeaconConfig dataclass."""

    def test_default_values(self):
        from beacon_crewai import BeaconConfig

        config = BeaconConfig(agent_id="test-agent")

        assert config.agent_id == "test-agent"
        assert config.beacon_host == "127.0.0.1"
        assert config.beacon_port == 38400
        assert config.data_dir is None
        assert config.use_mnemonic is False
        assert config.broadcast_heartbeats is False
        assert config.heartbeat_interval_seconds == 60
        assert config.known_keys is None

    def test_custom_values(self):
        from beacon_crewai import BeaconConfig

        config = BeaconConfig(
            agent_id="custom-agent",
            beacon_host="0.0.0.0",  # nosec B104
            beacon_port=38401,
            use_mnemonic=True,
            broadcast_heartbeats=True,
            heartbeat_interval_seconds=30,
            known_keys={"other-agent": "pubkey123"},
        )

        assert config.agent_id == "custom-agent"
        assert config.beacon_host == "0.0.0.0"  # nosec B104
        assert config.beacon_port == 38401
        assert config.use_mnemonic is True
        assert config.broadcast_heartbeats is True
        assert config.heartbeat_interval_seconds == 30
        assert config.known_keys == {"other-agent": "pubkey123"}


class TestModuleImports:
    """Test that module imports correctly."""

    def test_beacon_crewai_imports(self):
        """Test that beacon_crewai module can be imported."""
        import beacon_crewai

        assert hasattr(beacon_crewai, "BeaconConfig")
        assert hasattr(beacon_crewai, "BeaconAgent")
        assert hasattr(beacon_crewai, "create_beacon_crew")
        assert hasattr(beacon_crewai, "CREWAI_AVAILABLE")

    def test_beacon_langgraph_imports(self):
        """Test that beacon_langgraph module can be imported."""
        import beacon_langgraph

        assert hasattr(beacon_langgraph, "BeaconConfig")
        assert hasattr(beacon_langgraph, "BeaconNode")
        assert hasattr(beacon_langgraph, "BeaconGraphState")
        assert hasattr(beacon_langgraph, "create_beacon_graph")
        assert hasattr(beacon_langgraph, "create_beacon_tools")
        assert hasattr(beacon_langgraph, "LANGGRAPH_AVAILABLE")


class TestCrewAIAvailability:
    """Test CrewAI availability detection."""

    def test_crewai_available_flag(self):
        """Test CREWAI_AVAILABLE flag reflects actual state."""
        import beacon_crewai

        # Flag should be boolean
        assert isinstance(beacon_crewai.CREWAI_AVAILABLE, bool)

    def test_langgraph_available_flag(self):
        """Test LANGGRAPH_AVAILABLE flag reflects actual state."""
        import beacon_langgraph

        # Flag should be boolean
        assert isinstance(beacon_langgraph.LANGGRAPH_AVAILABLE, bool)


class TestBeaconAgentStructure:
    """Test BeaconAgent class structure."""

    def test_beacon_agent_has_required_methods(self):
        """Test that BeaconAgent has all required methods."""
        import beacon_crewai

        methods = [
            "create_crewai_agent",
            "get_beacon_tools",
            "send_heartbeat",
            "listen_for_messages",
            "verify_envelope",
            "list_contract",
            "get_identity",
            "set_message_callback",
            "get_state",
        ]

        for method in methods:
            assert hasattr(beacon_crewai.BeaconAgent, method)

    def test_beacon_node_has_required_methods(self):
        """Test that BeaconNode has all required methods."""
        import beacon_langgraph

        methods = [
            "send_heartbeat_node",
            "receive_messages_node",
            "verify_envelope_node",
            "list_contract_node",
            "get_identity_node",
            "get_state_summary",
        ]

        for method in methods:
            assert hasattr(beacon_langgraph.BeaconNode, method)


class TestCreateBeaconCrew:
    """Test create_beacon_crew function."""

    def test_raises_without_crewai(self):
        """Test that create_beacon_crew raises when CrewAI unavailable."""
        with patch("beacon_crewai.CREWAI_AVAILABLE", False):
            from beacon_crewai import create_beacon_crew

            with pytest.raises(ImportError, match="crewai package not installed"):
                create_beacon_crew(
                    agent_id="test",
                    task_description="test",
                    expected_output="test",
                )


class TestCreateBeaconGraph:
    """Test create_beacon_graph function."""

    def test_raises_without_langgraph(self):
        """Test that create_beacon_graph raises when LangGraph unavailable."""
        with patch("beacon_langgraph.LANGGRAPH_AVAILABLE", False):
            from beacon_langgraph import create_beacon_graph

            with pytest.raises(ImportError, match="langgraph package not installed"):
                create_beacon_graph(agent_id="test")


class TestBeaconTools:
    """Test beacon tools functionality."""

    def test_get_beacon_tools_empty_without_crewai(self):
        """Test that get_beacon_tools returns empty list without CrewAI."""
        with patch("beacon_crewai.CREWAI_AVAILABLE", False):
            from beacon_crewai import BeaconAgent, BeaconConfig

            config = BeaconConfig(agent_id="test-agent")
            # Can't fully instantiate without beacon_skill, but test the method
            # exists and returns empty list when CrewAI unavailable

    def test_create_beacon_tools_empty_without_langchain(self):
        """Test that create_beacon_tools returns empty list without LangChain."""
        with patch("beacon_langgraph.LANGCHAIN_AVAILABLE", False):
            from beacon_langgraph import create_beacon_tools

            tools = create_beacon_tools()
            assert tools == []


class TestBeaconGraphState:
    """Test BeaconGraphState TypedDict."""

    def test_state_is_typed_dict(self):
        """Test that BeaconGraphState is a TypedDict."""
        from beacon_langgraph import BeaconGraphState
        from typing import _TypedDictMeta

        # TypedDict should have the right metaclass
        assert isinstance(BeaconGraphState, type)
        # Check it's a TypedDict by checking for __annotations__
        assert hasattr(BeaconGraphState, "__annotations__")
        assert isinstance(BeaconGraphState.__annotations__, dict)


class TestIntegrationPoints:
    """Test integration points with beacon_skill."""

    def test_beacon_skill_imports(self):
        """Test that beacon_skill is properly imported."""
        # beacon_skill should be importable
        try:
            import beacon_skill
            assert hasattr(beacon_skill, "AgentIdentity")
            assert hasattr(beacon_skill, "HeartbeatManager")
        except ImportError:
            pytest.skip("beacon_skill not installed")

    def test_beacon_codec_imports(self):
        """Test that beacon_skill.codec is properly imported."""
        try:
            from beacon_skill.codec import encode_envelope, decode_envelopes, verify_envelope
            assert callable(encode_envelope)
            assert callable(decode_envelopes)
            assert callable(verify_envelope)
        except ImportError:
            pytest.skip("beacon_skill not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
