import pytest
import respx
from httpx import Response
from rustchain.client import RustChainClient

@respx.mock
def test_get_health():
    client = RustChainClient("https://api.rustchain.test")
    respx.get("https://api.rustchain.test/health").mock(return_value=Response(200, json={"ok": True, "version": "2.2.1"}))
    health = client.get_health()
    assert health["ok"] is True

@respx.mock
def test_get_stats():
    client = RustChainClient("https://api.rustchain.test")
    respx.get("https://api.rustchain.test/api/stats").mock(return_value=Response(200, json={"epoch": 61, "total_miners": 100, "total_balance": 5000.0}))
    stats = client.get_stats()
    assert stats.epoch == 61
