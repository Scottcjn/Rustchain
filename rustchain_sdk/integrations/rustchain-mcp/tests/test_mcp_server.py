#!/usr/bin/env python3
"""
RustChain MCP - Server Tests

Unit tests for MCP server tools and resources.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from rustchain_mcp.mcp_server import RustChainMCP
    from rustchain_mcp.schemas import HealthStatus, EpochInfo, WalletBalance, QueryResult
except ImportError:
    from mcp_server import RustChainMCP
    from schemas import HealthStatus, EpochInfo, WalletBalance, QueryResult


class MockClient:
    """Mock RustChainClient for testing."""
    
    def __init__(self):
        self.health_data = HealthStatus(status="ok", timestamp=1234567890, service="test")
        self.epoch_data = EpochInfo(epoch=95, slot=12345, height=67890)
        self.balance_data = WalletBalance(
            miner_id="test", amount_rtc=100.0, amount_i64=100000000
        )
        self.query_data = QueryResult(
            success=True, data={"result": "test"}, count=1, query_type="miners"
        )
    
    async def health(self):
        return self.health_data
    
    async def epoch(self, epoch_num=None):
        return self.epoch_data
    
    async def balance(self, miner_id):
        return self.balance_data
    
    async def query(self, query_type, params=None, limit=50):
        # Return query_type from the request
        return QueryResult(
            success=True, data={"result": "test"}, count=1, query_type=query_type
        )


class TestRustChainMCP:
    """Tests for RustChainMCP server."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return RustChainMCP(base_url="https://test.example.com")

    @pytest.fixture
    def server_with_client(self, server):
        """Create server with mock client."""
        server.client = MockClient()
        return server

    @pytest.mark.asyncio
    async def test_tool_health(self, server_with_client):
        """Test rustchain_health tool."""
        result = await server_with_client._tool_rustchain_health({})
        
        assert result["status"] == "ok"
        assert result["healthy"] is True
        assert result["timestamp"] == 1234567890
        assert result["service"] == "test"

    @pytest.mark.asyncio
    async def test_tool_health_no_client(self, server):
        """Test rustchain_health without client."""
        result = await server._tool_rustchain_health({})
        
        assert "error" in result
        assert "not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_tool_epoch_current(self, server_with_client):
        """Test rustchain_epoch tool for current epoch."""
        result = await server_with_client._tool_rustchain_epoch({})
        
        assert result["epoch"] == 95
        assert result["slot"] == 12345
        assert result["height"] == 67890

    @pytest.mark.asyncio
    async def test_tool_epoch_specific(self, server_with_client):
        """Test rustchain_epoch tool for specific epoch."""
        result = await server_with_client._tool_rustchain_epoch({"epoch": 90})
        
        assert result["epoch"] == 95  # Mock returns same data

    @pytest.mark.asyncio
    async def test_tool_balance(self, server_with_client):
        """Test rustchain_balance tool."""
        result = await server_with_client._tool_rustchain_balance(
            {"miner_id": "scott"}
        )
        
        assert result["miner_id"] == "test"
        assert result["balance_rtc"] == 100.0
        assert result["balance_i64"] == 100000000
        assert result["total_rtc"] == 100.0

    @pytest.mark.asyncio
    async def test_tool_balance_missing_id(self, server_with_client):
        """Test rustchain_balance with missing miner_id."""
        result = await server_with_client._tool_rustchain_balance({})
        
        assert "error" in result
        assert "required" in result["error"]

    @pytest.mark.asyncio
    async def test_tool_query(self, server_with_client):
        """Test rustchain_query tool."""
        result = await server_with_client._tool_rustchain_query({
            "query_type": "miners",
            "limit": 10,
        })
        
        assert result["success"] is True
        assert result["query_type"] == "miners"
        assert result["count"] == 1
        assert result["data"] == {"result": "test"}

    @pytest.mark.asyncio
    async def test_tool_query_missing_type(self, server_with_client):
        """Test rustchain_query with missing query_type."""
        result = await server_with_client._tool_rustchain_query({})
        
        assert "error" in result
        assert "required" in result["error"]


class TestResourceTemplates:
    """Tests for resource template handling."""

    @pytest.fixture
    def server(self):
        """Create server with mock client."""
        server = RustChainMCP(base_url="https://test.example.com")
        server.client = MockClient()
        return server

    @pytest.mark.asyncio
    async def test_read_resource_health(self, server):
        """Test reading rustchain://health resource."""
        content, mime_type = await server._read_resource_impl("rustchain://health")
        
        data = json.loads(content)
        assert mime_type == "application/json"
        assert data["status"] == "ok"
        assert data["healthy"] is True

    @pytest.mark.asyncio
    async def test_read_resource_epoch_current(self, server):
        """Test reading rustchain://epoch/current resource."""
        content, mime_type = await server._read_resource_impl(
            "rustchain://epoch/current"
        )
        
        data = json.loads(content)
        assert mime_type == "application/json"
        assert data["epoch"] == 95

    @pytest.mark.asyncio
    async def test_read_resource_epoch_specific(self, server):
        """Test reading rustchain://epoch/{n} resource."""
        content, mime_type = await server._read_resource_impl(
            "rustchain://epoch/90"
        )
        
        data = json.loads(content)
        assert mime_type == "application/json"
        assert "epoch" in data

    @pytest.mark.asyncio
    async def test_read_resource_wallet(self, server):
        """Test reading rustchain://wallet/{id} resource."""
        content, mime_type = await server._read_resource_impl(
            "rustchain://wallet/scott"
        )
        
        data = json.loads(content)
        assert mime_type == "application/json"
        assert "balance_rtc" in data

    @pytest.mark.asyncio
    async def test_read_resource_docs(self, server):
        """Test reading rustchain://docs/api resource."""
        content, mime_type = await server._read_resource_impl(
            "rustchain://docs/api"
        )
        
        assert mime_type == "text/markdown"
        assert "RustChain API" in content
        assert "/api/health" in content

    @pytest.mark.asyncio
    async def test_read_resource_unknown(self, server):
        """Test reading unknown resource."""
        with pytest.raises(ValueError) as exc_info:
            await server._read_resource_impl("rustchain://unknown")
        
        assert "Unknown resource" in str(exc_info.value)


class TestToolSchemas:
    """Tests for tool input schemas."""

    def test_health_schema_empty(self):
        """Test health schema allows empty input."""
        from schemas import HEALTH_SCHEMA
        
        assert HEALTH_SCHEMA["type"] == "object"
        assert len(HEALTH_SCHEMA["properties"]) == 0

    def test_epoch_schema_optional(self):
        """Test epoch schema has optional epoch parameter."""
        from schemas import EPOCH_SCHEMA
        
        assert "epoch" in EPOCH_SCHEMA["properties"]
        assert "epoch" not in EPOCH_SCHEMA.get("required", [])

    def test_balance_schema_required_miner_id(self):
        """Test balance schema requires miner_id."""
        from schemas import BALANCE_SCHEMA
        
        assert "miner_id" in BALANCE_SCHEMA["properties"]
        assert "miner_id" in BALANCE_SCHEMA["required"]

    def test_query_schema_required_type(self):
        """Test query schema requires query_type."""
        from schemas import QUERY_SCHEMA
        
        assert "query_type" in QUERY_SCHEMA["properties"]
        assert "query_type" in QUERY_SCHEMA["required"]
        assert "limit" in QUERY_SCHEMA["properties"]
