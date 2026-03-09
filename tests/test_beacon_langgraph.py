"""Tests for Beacon LangGraph integration.

Run with: pytest tests/test_beacon_langgraph.py -v

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
        from beacon_langgraph import BeaconConfig

        config = BeaconConfig(agent_id="test-agent")

        assert config.agent_id == "test-agent"
        assert config.beacon_host == "127.0.0.1"
        assert config.beacon_port == 38400
        assert config.data_dir is None
        assert config.use_mnemonic is False
        assert config.broadcast_heartbeats is False
        assert config.heartbeat_interval_seconds == 60

    def test_custom_values(self):
        from beacon_langgraph import BeaconConfig

        config = BeaconConfig(
            agent_id="custom-agent",
            beacon_host="0.0.0.0",
            beacon_port=38401,
            use_mnemonic=True,
            broadcast_heartbeats=True,
        )

        assert config.agent_id == "custom-agent"
        assert config.beacon_host == "0.0.0.0"
        assert config.beacon_port == 38401
        assert config.use_mnemonic is True
        assert config.broadcast_heartbeats is True


class TestModuleImports:
    """Test that module imports correctly."""

    def test_beacon_langgraph_imports(self):
        """Test that beacon_langgraph module can be imported."""
        import beacon_langgraph

        assert hasattr(beacon_langgraph, "BeaconConfig")
        assert hasattr(beacon_langgraph, "BeaconNode")
        assert hasattr(beacon_langgraph, "BeaconGraphState")
        assert hasattr(beacon_langgraph, "create_beacon_graph")
        assert hasattr(beacon_langgraph, "create_beacon_tools")
        assert hasattr(beacon_langgraph, "LANGGRAPH_AVAILABLE")
        assert hasattr(beacon_langgraph, "LANGCHAIN_AVAILABLE")


class TestLangGraphAvailability:
    """Test LangGraph availability detection."""

    def test_langgraph_available_flag(self):
        """Test LANGGRAPH_AVAILABLE flag reflects actual state."""
        import beacon_langgraph

        # Flag should be boolean
        assert isinstance(beacon_langgraph.LANGGRAPH_AVAILABLE, bool)

    def test_langchain_available_flag(self):
        """Test LANGCHAIN_AVAILABLE flag reflects actual state."""
        import beacon_langgraph

        # Flag should be boolean
        assert isinstance(beacon_langgraph.LANGCHAIN_AVAILABLE, bool)


class TestBeaconNodeStructure:
    """Test BeaconNode class structure."""

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


class TestCreateBeaconGraph:
    """Test create_beacon_graph function."""

    def test_raises_without_langgraph(self):
        """Test that create_beacon_graph raises when LangGraph unavailable."""
        with patch("beacon_langgraph.LANGGRAPH_AVAILABLE", False):
            from beacon_langgraph import create_beacon_graph

            with pytest.raises(ImportError, match="langgraph package not installed"):
                create_beacon_graph(agent_id="test")


class TestCreateBeaconTools:
    """Test create_beacon_tools function."""

    def test_returns_empty_without_langchain(self):
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

        # TypedDict should have the right metaclass
        assert isinstance(BeaconGraphState, type)
        # Check it's a TypedDict by checking for __annotations__
        assert hasattr(BeaconGraphState, "__annotations__")
        assert isinstance(BeaconGraphState.__annotations__, dict)

    def test_state_has_expected_keys(self):
        """Test that BeaconGraphState has expected keys."""
        from beacon_langgraph import BeaconGraphState

        annotations = BeaconGraphState.__annotations__
        
        # Check for some expected keys
        expected_keys = ["action", "messages", "identity", "error"]
        found_keys = [k for k in expected_keys if k in annotations]
        assert len(found_keys) > 0, f"Expected at least one of {expected_keys}"


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

    def test_beacon_contracts_imports(self):
        """Test that beacon_skill.contracts is properly imported."""
        try:
            from beacon_skill.contracts import ContractManager
            assert callable(ContractManager)
        except ImportError:
            pytest.skip("beacon_skill not installed")

    def test_beacon_udp_imports(self):
        """Test that beacon_skill.transports.udp is properly imported."""
        try:
            from beacon_skill.transports.udp import udp_send, udp_listen
            assert callable(udp_send)
            assert callable(udp_listen)
        except ImportError:
            pytest.skip("beacon_skill not installed")


class TestNodeInitialization:
    """Test BeaconNode initialization."""

    def test_node_requires_config(self):
        """Test that BeaconNode requires a config."""
        import beacon_langgraph

        # Config is required
        with pytest.raises(TypeError):
            beacon_langgraph.BeaconNode()  # type: ignore


class TestCrewAIIntegration:
    """Test CrewAI integration from LangGraph module."""

    def test_crewai_available_flag_in_langgraph(self):
        """Test that LangGraph module also checks CrewAI availability."""
        # Both modules should have CREWAI_AVAILABLE
        import beacon_crewai
        import beacon_langgraph

        assert isinstance(beacon_crewai.CREWAI_AVAILABLE, bool)
        # LangGraph module doesn't directly use CrewAI, but should be aware


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
