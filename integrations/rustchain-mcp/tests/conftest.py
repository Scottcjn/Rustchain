#!/usr/bin/env python3
"""
RustChain MCP - Pytest Configuration
"""

import pytest
import asyncio


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
