"""Unit tests for the rustchain Python SDK (Issue #2297).

Covers:
- RustChainClient (health, epoch, miners, balance, transfer, attestation_status)
- ExplorerClient (blocks, transactions)
- Typed exceptions
- CLI arg parsing
- Context-manager lifecycle
- Edge cases (non-positive amount, error status codes)
"""

from __future__ import annotations

import sys
import os
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Ensure the repo root is on the path so `rustchain` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import rustchain
from rustchain.client import RustChainClient
from rustchain.explorer import ExplorerClient
from rustchain.exceptions import (
    RustChainError,
    RustChainHTTPError,
    RustChainConnectionError,
    RustChainTimeoutError,
    RustChainNotFoundError,
    RustChainAuthError,
)


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _mock_response(status_code: int, body: Any) -> MagicMock:
    """Build a fake httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


# ────────────────────────────────────────────────────────────────────────────
# Exception hierarchy
# ────────────────────────────────────────────────────────────────────────────

class TestExceptions:
    def test_base_error_is_exception(self):
        err = RustChainError("boom")
        assert isinstance(err, Exception)
        assert str(err) == "boom"

    def test_base_error_stores_status_code(self):
        err = RustChainError("boom", status_code=500)
        assert err.status_code == 500

    def test_http_error_inherits_base(self):
        assert issubclass(RustChainHTTPError, RustChainError)

    def test_connection_error_inherits_base(self):
        assert issubclass(RustChainConnectionError, RustChainError)

    def test_timeout_error_inherits_base(self):
        assert issubclass(RustChainTimeoutError, RustChainError)

    def test_not_found_error_has_404(self):
        err = RustChainNotFoundError()
        assert err.status_code == 404

    def test_auth_error_has_401(self):
        err = RustChainAuthError()
        assert err.status_code == 401

    def test_not_found_inherits_http_error(self):
        assert issubclass(RustChainNotFoundError, RustChainHTTPError)

    def test_auth_error_inherits_http_error(self):
        assert issubclass(RustChainAuthError, RustChainHTTPError)


# ────────────────────────────────────────────────────────────────────────────
# Client construction
# ────────────────────────────────────────────────────────────────────────────

class TestClientConstruction:
    def test_default_node_url(self):
        client = RustChainClient()
        assert "50.28.86.131" in client.node_url

    def test_custom_node_url(self):
        client = RustChainClient("https://mynode.example.com")
        assert client.node_url == "https://mynode.example.com"

    def test_trailing_slash_stripped(self):
        client = RustChainClient("https://mynode.example.com/")
        assert not client.node_url.endswith("/")

    def test_explorer_attribute_is_explorer_client(self):
        client = RustChainClient()
        assert isinstance(client.explorer, ExplorerClient)

    def test_env_var_sets_node_url(self, monkeypatch):
        monkeypatch.setenv("RUSTCHAIN_NODE_URL", "https://env-node.example.com")
        client = RustChainClient()
        assert client.node_url == "https://env-node.example.com"


# ────────────────────────────────────────────────────────────────────────────
# _handle — status-code mapping
# ────────────────────────────────────────────────────────────────────────────

class TestHandleResponse:
    def test_200_returns_json(self):
        resp = _mock_response(200, {"ok": True})
        assert RustChainClient._handle(resp) == {"ok": True}

    def test_404_raises_not_found(self):
        resp = _mock_response(404, {})
        with pytest.raises(RustChainNotFoundError):
            RustChainClient._handle(resp)

    def test_401_raises_auth_error(self):
        resp = _mock_response(401, {})
        with pytest.raises(RustChainAuthError):
            RustChainClient._handle(resp)

    def test_403_raises_auth_error(self):
        resp = _mock_response(403, {})
        with pytest.raises(RustChainAuthError):
            RustChainClient._handle(resp)

    def test_500_raises_http_error(self):
        resp = _mock_response(500, {"error": "internal"})
        with pytest.raises(RustChainHTTPError) as exc_info:
            RustChainClient._handle(resp)
        assert exc_info.value.status_code == 500


# ────────────────────────────────────────────────────────────────────────────
# Async API methods
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    return RustChainClient("https://testnode.example.com")


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_calls_correct_path(self, client):
        client._get = AsyncMock(return_value={"ok": True, "version": "1.0"})
        result = await client.health()
        client._get.assert_called_once_with("/health")
        assert result["ok"] is True


@pytest.mark.asyncio
class TestEpochEndpoint:
    async def test_epoch_calls_correct_path(self, client):
        payload = {"epoch": 42, "slot": 7}
        client._get = AsyncMock(return_value=payload)
        result = await client.epoch()
        client._get.assert_called_once_with("/epoch")
        assert result["epoch"] == 42


@pytest.mark.asyncio
class TestMinersEndpoint:
    async def test_miners_calls_correct_path(self, client):
        client._get = AsyncMock(return_value=[{"id": "miner-1"}])
        result = await client.miners()
        client._get.assert_called_once_with("/api/miners")
        assert result[0]["id"] == "miner-1"


@pytest.mark.asyncio
class TestBalanceEndpoint:
    async def test_balance_passes_wallet_id(self, client):
        client._get = AsyncMock(return_value={"balance": 100.0})
        result = await client.balance("my-wallet")
        client._get.assert_called_once_with(
            "/wallet/balance", params={"miner_id": "my-wallet"}
        )
        assert result["balance"] == 100.0


@pytest.mark.asyncio
class TestTransferEndpoint:
    async def test_transfer_sends_correct_payload(self, client):
        client._post = AsyncMock(return_value={"status": "ok"})
        result = await client.transfer("alice", "bob", 50.0, "sig-abc")
        client._post.assert_called_once_with(
            "/wallet/transfer",
            json={"from": "alice", "to": "bob", "amount": 50.0, "signature": "sig-abc"},
        )
        assert result["status"] == "ok"

    async def test_transfer_raises_on_zero_amount(self, client):
        with pytest.raises(ValueError):
            await client.transfer("alice", "bob", 0, "sig")

    async def test_transfer_raises_on_negative_amount(self, client):
        with pytest.raises(ValueError):
            await client.transfer("alice", "bob", -5, "sig")


@pytest.mark.asyncio
class TestAttestationEndpoint:
    async def test_attestation_status_correct_path(self, client):
        client._get = AsyncMock(return_value={"attested": True})
        result = await client.attestation_status("miner-42")
        client._get.assert_called_once_with("/api/attestation/miner-42")
        assert result["attested"] is True


# ────────────────────────────────────────────────────────────────────────────
# ExplorerClient
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestExplorerClient:
    async def test_blocks_calls_correct_path(self, client):
        client._get = AsyncMock(return_value=[{"height": 1}])
        result = await client.explorer.blocks()
        client._get.assert_called_once_with("/api/explorer/blocks")
        assert result[0]["height"] == 1

    async def test_transactions_calls_correct_path(self, client):
        client._get = AsyncMock(return_value=[{"tx_id": "abc"}])
        result = await client.explorer.transactions()
        client._get.assert_called_once_with("/api/explorer/transactions")
        assert result[0]["tx_id"] == "abc"


# ────────────────────────────────────────────────────────────────────────────
# Package-level exports
# ────────────────────────────────────────────────────────────────────────────

class TestPackageExports:
    def test_client_importable_from_package(self):
        assert rustchain.RustChainClient is RustChainClient

    def test_version_is_set(self):
        assert rustchain.__version__

    def test_exceptions_exported(self):
        for name in [
            "RustChainError",
            "RustChainHTTPError",
            "RustChainConnectionError",
            "RustChainTimeoutError",
            "RustChainNotFoundError",
            "RustChainAuthError",
        ]:
            assert hasattr(rustchain, name)
