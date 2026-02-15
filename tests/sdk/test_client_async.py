import pytest
import respx
from httpx import Response
from rustchain.async_client import AsyncRustChainClient

@pytest.mark.asyncio
@respx.mock
async def test_async_get_health():
    async with AsyncRustChainClient("https://api.rustchain.test") as client:
        respx.get("https://api.rustchain.test/health").mock(return_value=Response(200, json={"ok": True}))
        health = await client.get_health()
        assert health["ok"] is True

@pytest.mark.asyncio
@respx.mock
async def test_async_get_stats():
    async with AsyncRustChainClient("https://api.rustchain.test") as client:
        respx.get("https://api.rustchain.test/api/stats").mock(return_value=Response(200, json={"epoch": 61, "total_miners": 100, "total_balance": 5000.0}))
        stats = await client.get_stats()
        assert stats.epoch == 61
