"""
Pytest configuration for RustChain MCP Server tests.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure asyncio test mode
pytest_plugins = ('pytest_asyncio',)


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


class AsyncContextManagerMock:
    """Mock for async context managers (async with)."""
    
    def __init__(self, return_value):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


@pytest.fixture
def mcp_server():
    """Create MCP server instance."""
    from mcp_server import RustChainMCP
    server = RustChainMCP()
    return server


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session with proper async context manager support."""
    session = AsyncMock()
    
    # Create a mock response that can be configured per test
    mock_response = AsyncMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    
    # Setup session.get to return the context manager
    session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
    
    return session


@pytest.fixture
def mock_response_factory():
    """Factory for creating mock HTTP responses."""
    def create_response(status=200, json_data=None):
        mock_response = AsyncMock()
        mock_response.status = status
        if json_data is not None:
            mock_response.json = AsyncMock(return_value=json_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        return mock_response
    return create_response
