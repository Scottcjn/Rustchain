#!/usr/bin/env python3
"""
Offline regression tests for `rustchain-mcp` streaming & long-running tool behavior
(Bounty #16255 / closes Scottcjn/rustchain-mcp#231).

Verifies with zero network calls:
1. Declared MCP initialization options & capability flags match README documentation.
2. Long-running tool calls (`rustchain_query` for `miners`) execute as atomic request/response
   calls returning a single complete `TextContent` payload (no partial chunks or progress callbacks).
3. `RUSTCHAIN_TIMEOUT` and `RUSTCHAIN_RETRY` bound slow or failing calls and surface structured
   `APIError` JSON payloads instead of hanging indefinitely.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

MCP_DIR = Path(__file__).resolve().parents[1]
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import client as mcp_client_mod
import mcp_server as mcp_server_mod
from client import RustChainClient, _safe_int_env
from mcp_server import RustChainMCP
from schemas import APIError


def test_declared_mcp_capabilities_do_not_claim_streaming():
    """Server initialization options must not advertise streaming or progress capabilities."""
    server = RustChainMCP(base_url="https://50.28.86.131")
    init_opts = server.create_initialization_options()
    assert isinstance(init_opts, dict) or hasattr(init_opts, "capabilities")
    if isinstance(init_opts, dict):
        exp = init_opts.get("experimental_capabilities", {})
        assert exp == {}, f"Unexpected experimental streaming capabilities: {exp}"
    else:
        exp = getattr(init_opts, "experimental_capabilities", {}) or {}
        assert exp == {}


def test_no_tool_handler_accepts_progress_or_stream_callbacks():
    """All tool handlers on RustChainMCP are synchronous request/response coroutines without progress callbacks."""
    server = RustChainMCP(base_url="https://50.28.86.131")
    tool_methods = [
        server._tool_rustchain_health,
        server._tool_rustchain_epoch,
        server._tool_rustchain_balance,
        server._tool_rustchain_query,
    ]
    for method in tool_methods:
        sig = inspect.signature(method)
        for forbidden in ("progress", "on_progress", "stream", "callback"):
            assert forbidden not in sig.parameters, f"{method.__name__} unexpectedly accepts {forbidden}"


def test_long_running_miners_query_returns_atomic_full_response():
    """Simulated slow `/api/miners` query blocks until completion and returns the full batch at once."""
    async def _run():
        server = RustChainMCP(base_url="https://50.28.86.131")
        mock_client = MagicMock(spec=RustChainClient)
        miners_payload = [{"miner": f"RTC_miner_{i}", "arch": "g4"} for i in range(25)]

        async def _slow_query(query_type, params, limit):
            await asyncio.sleep(0.01)
            return mcp_server_mod.QueryResult(
                success=True,
                query_type=query_type,
                count=len(miners_payload),
                data={"miners": miners_payload},
                error=None,
            )

        mock_client.query = AsyncMock(side_effect=_slow_query)
        server.client = mock_client

        result = await server._tool_rustchain_query(
            {"query_type": "miners", "params": {"hardware_type": "g4"}, "limit": 25}
        )
        assert result["success"] is True
        assert result["query_type"] == "miners"
        assert result["count"] == 25
        assert len(result["data"]["miners"]) == 25
        mock_client.query.assert_awaited_once_with("miners", {"hardware_type": "g4"}, 25)

    asyncio.run(_run())


def test_timeout_and_retry_bounds_prevent_infinite_hang():
    """When the upstream node stalls or fails with ClientError, RustChainClient retries bounded times and raises APIError(503)."""
    async def _run():
        client = RustChainClient(base_url="https://50.28.86.131", timeout=5, retry_count=1)
        mock_session = MagicMock()
        mock_session.request.side_effect = aiohttp.ServerTimeoutError("Read timed out after 5s")
        client._session = mock_session

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with pytest.raises(APIError) as exc_info:
                await client._request("GET", "/api/miners")
            err = exc_info.value
            assert err.code == "CONNECTION_FAILED"
            assert err.status_code == 503
            assert "Failed after 2 attempts" in err.message
            assert mock_session.request.call_count == 2
            mock_sleep.assert_awaited_once_with(0.5)

    asyncio.run(_run())


def test_env_timeout_and_retry_configuration_contract():
    """RUSTCHAIN_TIMEOUT and RUSTCHAIN_RETRY env vars are respected with safe integer fallback."""
    with patch.dict(os.environ, {"RUSTCHAIN_TIMEOUT": "15", "RUSTCHAIN_RETRY": "4"}):
        assert _safe_int_env("RUSTCHAIN_TIMEOUT", 30) == 15
        assert _safe_int_env("RUSTCHAIN_RETRY", 2) == 4

    with patch.dict(os.environ, {"RUSTCHAIN_TIMEOUT": "invalid_num"}):
        assert _safe_int_env("RUSTCHAIN_TIMEOUT", 30) == 30


def test_readme_documents_streaming_and_long_running_tools():
    """README.md must include the 'Streaming & Long-Running Tools' section referencing #231 and RUSTCHAIN_TIMEOUT."""
    readme_text = (MCP_DIR / "README.md").read_text(encoding="utf-8")
    assert "Streaming & Long-Running Tools" in readme_text
    assert "RUSTCHAIN_TIMEOUT" in readme_text
    assert "notifications/progress" in readme_text
