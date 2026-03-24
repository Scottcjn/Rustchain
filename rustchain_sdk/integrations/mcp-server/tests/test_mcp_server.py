#!/usr/bin/env python3
"""
Tests for RustChain MCP Server
"""

# Import server module
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, ".")

# Mock mcp module if not available (for Python 3.9 testing)
try:
    import mcp
except ImportError:
    import mcp_mock as mcp  # type: ignore

from mcp_server import RustChainMCP


@pytest.fixture
def mcp_server():
    """Create MCP server instance."""
    return RustChainMCP()


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session with proper async context manager support."""
    session = AsyncMock()

    # Create a mock response that can be configured per test
    mock_response = AsyncMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    # Setup session.get to return the context manager
    session.get = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    return session


class AsyncContextManagerMock:
    """Mock for async context managers (async with)."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class TestMinerInfo:
    """Tests for miner info tools."""

    @pytest.mark.asyncio
    async def test_get_miner_info_found(self, mcp_server):
        """Test getting miner info when miner exists."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "miners": [
                    {
                        "miner_id": "test_miner_123",
                        "wallet": "wallet_abc",
                        "hardware": "PowerPC G4",
                        "score": 245.8,
                        "epochs_mined": 1250,
                        "status": "active",
                    }
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_miner_info({"miner_id": "test_miner_123"})

        # Verify
        assert result["found"] is True
        assert result["miner"]["miner_id"] == "test_miner_123"
        assert result["miner"]["hardware"] == "PowerPC G4"

    @pytest.mark.asyncio
    async def test_get_miner_info_not_found(self, mcp_server):
        """Test getting miner info when miner doesn't exist."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"miners": []})

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_miner_info({"miner_id": "nonexistent"})

        # Verify
        assert result["found"] is False
        assert "hint" in result


class TestBlockInfo:
    """Tests for block info tools."""

    @pytest.mark.asyncio
    async def test_get_block_info_by_epoch(self, mcp_server):
        """Test getting block info by epoch number."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "epoch": 1234,
                "hash": "0xabc123",
                "timestamp": 1234567890,
                "miner": "miner_xyz",
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_block_info({"block_id": "1234"})

        # Verify
        assert result["found"] is True
        assert result["block"]["epoch"] == 1234


class TestNetworkStats:
    """Tests for network statistics."""

    @pytest.mark.asyncio
    async def test_get_network_stats(self, mcp_server):
        """Test getting network stats."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"current_epoch": 5678, "active_miners": 142, "total_rewards": 12345.67}
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_network_stats()

        # Verify
        assert "current_epoch" in result
        assert "active_miners" in result


class TestActiveMiners:
    """Tests for active miners list."""

    @pytest.mark.asyncio
    async def test_get_active_miners_no_filters(self, mcp_server):
        """Test getting active miners without filters."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "miners": [
                    {"miner_id": "m1", "score": 300},
                    {"miner_id": "m2", "score": 200},
                    {"miner_id": "m3", "score": 100},
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_active_miners({"limit": 10})

        # Verify
        assert result["count"] == 3
        assert len(result["miners"]) == 3
        # Should be sorted by score descending
        assert result["miners"][0]["score"] == 300

    @pytest.mark.asyncio
    async def test_get_active_miners_hardware_filter(self, mcp_server):
        """Test getting active miners with hardware filter."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "miners": [
                    {"miner_id": "m1", "hardware": "PowerPC G4", "score": 300},
                    {"miner_id": "m2", "hardware": "x86_64", "score": 200},
                    {"miner_id": "m3", "hardware": "PowerPC G5", "score": 100},
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool with hardware filter
        result = await mcp_server._tool_get_active_miners({"limit": 10, "hardware_type": "PowerPC"})

        # Verify - should only include PowerPC miners
        assert result["count"] == 2
        for miner in result["miners"]:
            assert "PowerPC" in miner["hardware"]


class TestWalletBalance:
    """Tests for wallet balance tools."""

    @pytest.mark.asyncio
    async def test_get_wallet_balance_found(self, mcp_server):
        """Test getting wallet balance when wallet exists."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"balance": 1234.56, "transactions": 42})

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_wallet_balance({"wallet": "wallet_abc"})

        # Verify
        assert result["found"] is True
        assert result["balance"]["balance"] == 1234.56

    @pytest.mark.asyncio
    async def test_get_wallet_balance_not_found(self, mcp_server):
        """Test getting wallet balance when wallet doesn't exist."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_wallet_balance({"wallet": "nonexistent"})

        # Verify
        assert result["found"] is False


class TestBountyInfo:
    """Tests for bounty information tools."""

    @pytest.mark.asyncio
    async def test_get_bounty_info_single(self, mcp_server):
        """Test getting single bounty by issue number."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "number": 23,
                "title": "🔗 BOUNTY: ERGO MAINNET BRIDGE (150 RTC)",
                "body": "Anchor RustChain state to Ergo mainnet",
                "created_at": "2026-02-03T00:00:00Z",
                "html_url": "https://github.com/Scottcjn/RustChain/issues/23",
                "labels": [{"name": "bounty"}, {"name": "enhancement"}],
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Call tool
        result = await mcp_server._tool_get_bounty_info({"issue_number": 23})

        # Verify
        assert result["found"] is True
        assert result["bounty"]["issue_number"] == 23
        assert result["bounty"]["reward_rtc"] == 150

    @pytest.mark.asyncio
    async def test_parse_bounty_issue(self, mcp_server):
        """Test parsing bounty issue."""
        issue = {
            "number": 166,
            "title": "[BOUNTY] Mine for 7 Days — Prove Sustained Mining, Earn 15 RTC",
            "body": "Pool: 500 RTC",
            "created_at": "2026-02-13T00:00:00Z",
            "html_url": "https://github.com/Scottcjn/RustChain/issues/166",
            "labels": [{"name": "bounty"}, {"name": "good first issue"}],
        }

        result = mcp_server._parse_bounty_issue(issue)

        assert result["issue_number"] == 166
        assert result["reward_rtc"] == 15
        assert "bounty" in result["labels"]


class TestHardwareVerification:
    """Tests for hardware verification tools."""

    @pytest.mark.asyncio
    async def test_verify_hardware_powerpc_g4(self, mcp_server):
        """Test verifying PowerPC G4 hardware."""
        result = await mcp_server._tool_verify_hardware(
            {"cpu_model": "PowerPC G4", "architecture": "PowerPC", "is_vm": False}
        )

        assert result["eligible"] is True
        assert result["multiplier"] == 2.5
        assert result["estimated_bonus"] == "+150%"
        assert result["warning"] is None

    @pytest.mark.asyncio
    async def test_verify_hardware_vm_penalty(self, mcp_server):
        """Test VM penalty on hardware verification."""
        result = await mcp_server._tool_verify_hardware(
            {"cpu_model": "PowerPC G4", "architecture": "PowerPC", "is_vm": True}
        )

        assert result["multiplier"] == 0.025  # 2.5 * 0.01
        assert "significantly reduce" in result["warning"]

    @pytest.mark.asyncio
    async def test_verify_hardware_modern_x86(self, mcp_server):
        """Test verifying modern x86 hardware."""
        result = await mcp_server._tool_verify_hardware(
            {"cpu_model": "Intel Core i7", "architecture": "x86_64", "is_vm": False}
        )

        assert result["eligible"] is True
        assert result["multiplier"] == 1.0
        assert result["estimated_bonus"] == "+0%"


class TestMiningRewards:
    """Tests for mining reward calculation tools."""

    @pytest.mark.asyncio
    async def test_calculate_rewards_powerpc_g4(self, mcp_server):
        """Test calculating rewards for PowerPC G4."""
        result = await mcp_server._tool_calculate_mining_rewards(
            {"hardware_type": "PowerPC G4", "epochs": 1008, "uptime_percent": 100}  # 7 days
        )

        assert result["hardware_type"] == "PowerPC G4"
        assert result["multiplier"] == 2.5
        assert result["epochs"] == 1008
        # Base: 1008 * 0.1 = 100.8, Adjusted: 100.8 * 2.5 = 252.0
        assert result["estimated_rewards_rtc"] == 252.0

    @pytest.mark.asyncio
    async def test_calculate_rewards_with_uptime(self, mcp_server):
        """Test calculating rewards with less than 100% uptime."""
        result = await mcp_server._tool_calculate_mining_rewards(
            {"hardware_type": "Modern x86", "epochs": 1008, "uptime_percent": 80}
        )

        # Base: 1008 * 0.1 = 100.8, Adjusted: 100.8 * 1.0 * 0.8 = 80.64
        assert result["estimated_rewards_rtc"] == 80.64

    @pytest.mark.asyncio
    async def test_calculate_rewards_breakdown(self, mcp_server):
        """Test reward calculation breakdown."""
        result = await mcp_server._tool_calculate_mining_rewards(
            {"hardware_type": "PowerPC G5", "epochs": 100, "uptime_percent": 100}
        )

        assert "breakdown" in result
        assert "base" in result["breakdown"]
        assert "hardware_bonus" in result["breakdown"]
        assert "uptime_adjustment" in result["breakdown"]


class TestResources:
    """Tests for resource reading."""

    @pytest.mark.asyncio
    async def test_read_resource_network_stats(self, mcp_server):
        """Test reading network stats resource."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"current_epoch": 1234})

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Read resource
        content, mime_type = await mcp_server._read_resource_impl("rustchain://network/stats")

        # Verify
        assert mime_type == "application/json"
        assert "current_epoch" in content

    @pytest.mark.asyncio
    async def test_read_resource_quickstart(self, mcp_server):
        """Test reading quickstart guide resource."""
        content, mime_type = await mcp_server._read_resource_impl("rustchain://docs/quickstart")

        # Verify
        assert mime_type == "text/markdown"
        assert "RustChain" in content
        assert "pip install clawrtc" in content

    @pytest.mark.asyncio
    async def test_read_resource_miner_template(self, mcp_server):
        """Test reading miner resource template."""
        # Create mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"miners": [{"miner_id": "test123"}]})

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        # Read resource
        content, mime_type = await mcp_server._read_resource_impl("rustchain://miner/test123")

        # Verify
        assert mime_type == "application/json"


class TestQuickstartGuide:
    """Tests for quickstart guide generation."""

    def test_get_quickstart_guide(self, mcp_server):
        """Test quickstart guide content."""
        content = mcp_server._get_quickstart_guide()

        assert "# RustChain Quickstart Guide" in content
        assert "pip install clawrtc" in content
        assert "PowerPC G4" in content
        assert "2.5x" in content
        assert "Modern x86" in content


class TestBoTTube:
    """Tests for BoTTube integration tools."""

    @pytest.mark.asyncio
    async def test_get_video_info_found(self, mcp_server):
        """Test getting video info when video exists."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "id": "video_123",
                "title": "AI Tutorial",
                "agent": "agent_abc",
                "views": 1500,
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_get_video_info({"video_id": "video_123"})

        assert result["found"] is True
        assert result["video"]["id"] == "video_123"
        assert result["video"]["title"] == "AI Tutorial"

    @pytest.mark.asyncio
    async def test_get_video_info_not_found(self, mcp_server):
        """Test getting video info when video doesn't exist."""
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_get_video_info({"video_id": "nonexistent"})

        assert result["found"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_list_videos(self, mcp_server):
        """Test listing videos."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "videos": [
                    {"id": "v1", "title": "Video 1"},
                    {"id": "v2", "title": "Video 2"},
                    {"id": "v3", "title": "Video 3"},
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_list_videos({"limit": 10})

        assert result["count"] == 3
        assert len(result["videos"]) == 3

    @pytest.mark.asyncio
    async def test_list_videos_with_agent_filter(self, mcp_server):
        """Test listing videos with agent filter."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "videos": [
                    {"id": "v1", "title": "Video 1", "agent": "agent_xyz"},
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_list_videos({"limit": 10, "agent": "agent_xyz"})

        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_agent_videos(self, mcp_server):
        """Test getting agent's videos."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "videos": [
                    {"id": "v1", "title": "Agent Video 1"},
                    {"id": "v2", "title": "Agent Video 2"},
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_get_agent_videos({"agent_id": "agent_xyz"})

        assert result["agent_id"] == "agent_xyz"
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_search_videos(self, mcp_server):
        """Test searching videos."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "videos": [
                    {"id": "v1", "title": "RustChain Tutorial"},
                    {"id": "v2", "title": "Blockchain Basics"},
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_search_videos({"query": "blockchain", "limit": 10})

        assert result["query"] == "blockchain"
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_feed(self, mcp_server):
        """Test getting feed."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "items": [
                    {"type": "upload", "video_id": "v1"},
                    {"type": "like", "video_id": "v2"},
                ],
                "next_cursor": "cursor_abc",
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_get_feed({"limit": 20})

        assert result["count"] == 2
        assert result["next_cursor"] == "cursor_abc"

    @pytest.mark.asyncio
    async def test_get_feed_with_cursor(self, mcp_server):
        """Test getting feed with pagination cursor."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "items": [{"type": "comment", "video_id": "v3"}],
                "next_cursor": "cursor_xyz",
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        mcp_server.session = mock_session

        result = await mcp_server._tool_get_feed({"cursor": "cursor_abc", "limit": 20})

        assert result["count"] == 1


class TestToolList:
    """Tests for tool listing."""

    def test_list_tools_registered(self, mcp_server):
        """Test that all expected tools are registered."""
        # Verify the server has the tool handlers registered
        # The tools are registered via @self.app.list_tools() decorator
        # We verify by checking the handler methods exist on the server

        expected_tools = [
            # RustChain tools
            "get_miner_info",
            "get_block_info",
            "get_epoch_info",
            "get_network_stats",
            "get_active_miners",
            "get_wallet_balance",
            "get_bounty_info",
            "get_agent_info",
            "verify_hardware",
            "calculate_mining_rewards",
            # BoTTube tools
            "get_video_info",
            "list_videos",
            "get_agent_videos",
            "search_videos",
            "get_feed",
        ]

        # Check that all tool handler methods exist
        for tool in expected_tools:
            handler_name = f"_tool_{tool}"
            assert hasattr(mcp_server, handler_name), f"Missing tool handler: {handler_name}"
            assert callable(
                getattr(mcp_server, handler_name)
            ), f"Tool handler not callable: {handler_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
