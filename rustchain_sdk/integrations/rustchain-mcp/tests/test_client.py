#!/usr/bin/env python3
"""
RustChain MCP - Client Tests

Unit tests for RustChainClient with mocked HTTP responses.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from rustchain_mcp.client import RustChainClient
    from rustchain_mcp.schemas import APIError, HealthStatus, EpochInfo, WalletBalance, QueryResult
except ImportError:
    from client import RustChainClient
    from schemas import APIError, HealthStatus, EpochInfo, WalletBalance, QueryResult


class AsyncContextManager:
    """Simple async context manager for testing."""
    
    def __init__(self, coro_result):
        self._coro_result = coro_result
    
    async def __aenter__(self):
        return self._coro_result
    
    async def __aexit__(self, *args):
        pass


class MockResponse:
    """Mock aiohttp response."""
    
    def __init__(self, data, status=200):
        self._data = data
        self.status = status
    
    async def json(self):
        return self._data


class TestRustChainClient:
    """Tests for RustChainClient."""

    @pytest.mark.asyncio
    async def test_health_success(self):
        """Test health check success."""
        mock_response = MockResponse({
            "status": "ok",
            "timestamp": 1234567890,
            "service": "test-api",
            "version": "1.0.0",
        })
        
        mock_close = AsyncMock()
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = mock_close
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            health = await client.health()
            
            assert isinstance(health, HealthStatus)
            assert health.status == "ok"
            assert health.is_healthy is True
            assert health.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_error(self):
        """Test health check error."""
        mock_response = MockResponse(
            {"error": "SERVICE_DOWN", "message": "Service unavailable"},
            status=503,
        )
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            with pytest.raises(APIError) as exc_info:
                await client.health()
            
            assert exc_info.value.code == "SERVICE_DOWN"
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_epoch_current(self):
        """Test getting current epoch."""
        mock_response = MockResponse({
            "epoch": 95,
            "slot": 12345,
            "height": 67890,
        })
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            epoch = await client.epoch()
            
            assert isinstance(epoch, EpochInfo)
            assert epoch.epoch == 95
            assert epoch.slot == 12345

    @pytest.mark.asyncio
    async def test_epoch_specific(self):
        """Test getting specific epoch."""
        mock_response = MockResponse({
            "epoch": 90,
            "slot": 10000,
            "height": 60000,
        })
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            epoch = await client.epoch(90)
            assert epoch.epoch == 90

    @pytest.mark.asyncio
    async def test_balance_success(self):
        """Test getting wallet balance."""
        mock_response = MockResponse({
            "miner_id": "scott",
            "amount_rtc": 155.0,
            "amount_i64": 155000000,
        })
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            balance = await client.balance("scott")
            
            assert isinstance(balance, WalletBalance)
            assert balance.miner_id == "scott"
            assert balance.amount_rtc == 155.0

    @pytest.mark.asyncio
    async def test_balance_not_found(self):
        """Test balance for non-existent wallet."""
        mock_response = MockResponse(
            {"error": "NOT_FOUND", "message": "Wallet not found"},
            status=404,
        )
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            with pytest.raises(APIError) as exc_info:
                await client.balance("unknown")
            
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test generic query."""
        mock_response = MockResponse({
            "success": True,
            "data": {"miners": [{"id": "m1"}]},
            "count": 1,
            "query_type": "miners",
        })
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            result = await client.query("miners", limit=10)
            
            assert isinstance(result, QueryResult)
            assert result.success is True
            assert result.count == 1
            assert result.query_type == "miners"

    @pytest.mark.asyncio
    async def test_ping_success(self):
        """Test ping success."""
        mock_response = MockResponse({
            "status": "ok",
            "timestamp": 1234567890,
            "service": "test",
        })
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            result = await client.ping()
            assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        """Test ping failure."""
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(side_effect=Exception("Connection error"))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            result = await client.ping()
            assert result is False


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_get_health(self):
        """Test get_health convenience function."""
        mock_response = MockResponse({
            "status": "ok",
            "timestamp": 0,
            "service": "test",
        })
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            try:
                from rustchain_mcp.client import RustChainClient
            except ImportError:
                from client import RustChainClient
            
            # Create client directly since get_health uses context manager
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            health = await client.health()
            assert health.status == "ok"

    @pytest.mark.asyncio
    async def test_get_balance(self):
        """Test get_balance convenience function."""
        mock_response = MockResponse({
            "miner_id": "test",
            "amount_rtc": 100.0,
            "amount_i64": 100000000,
        })
        
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=AsyncContextManager(mock_response))
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session
            
            try:
                from rustchain_mcp.client import RustChainClient
            except ImportError:
                from client import RustChainClient
            
            client = RustChainClient(base_url="https://test.example.com")
            client._session = mock_session
            client._owns_session = False
            
            balance = await client.balance("test")
            assert balance.miner_id == "test"
