# SPDX-License-Identifier: MIT
"""Both Python clients must preserve the node's unified wallet history."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from rustchain import RustChainClient
from rustchain.async_client import AsyncRustChainClient
from rustchain.exceptions import APIError


# Contract: node/tests/test_wallet_history.py and GET /wallet/history.
TRANSACTIONS = [
    {"type": "transfer_in", "amount": 5.0, "epoch": 200,
     "timestamp": 1700000000, "tx_hash": "example-transfer", "from": "bob"},
    {"type": "reward", "amount": 0.5, "epoch": 199,
     "timestamp": 1699999900, "tx_hash": None},
]


def history(client_kind, payload):
    if client_kind == "sync":
        with RustChainClient("https://example.invalid") as client:
            with patch.object(client, "_request", return_value=payload) as request:
                result = client.transfer_history("alice", limit=2)
    else:
        async def run():
            async with AsyncRustChainClient("https://example.invalid") as client:
                with patch.object(client, "_request", new_callable=AsyncMock) as request:
                    request.return_value = payload
                    return await client.transfer_history("alice", limit=2), request
        result, request = asyncio.run(run())
    request.assert_called_once_with(
        "GET", "/wallet/history", params={"miner_id": "alice", "limit": 2}
    )
    return result


@pytest.mark.parametrize("client_kind", ["sync", "async"])
@pytest.mark.parametrize("transactions", [TRANSACTIONS, []])
@pytest.mark.parametrize("enveloped", [True, False])
def test_history_preserves_current_and_legacy_responses(client_kind, transactions, enveloped):
    payload = ({"ok": True, "miner_id": "alice", "transactions": transactions,
                "total": len(transactions)} if enveloped else transactions)
    assert history(client_kind, payload) == transactions


@pytest.mark.parametrize("client_kind", ["sync", "async"])
@pytest.mark.parametrize("payload", [
    None, "unavailable", {}, {"raw_response": "<html>Proxy error</html>"},
    {"ok": True, "transactions": None}, {"ok": True, "transactions": {}},
])
def test_malformed_history_is_not_reported_as_empty(client_kind, payload):
    with pytest.raises(APIError, match="Expected transaction history"):
        history(client_kind, payload)
