"""
Tests for RustChainClient.
Uses respx for HTTP mocking.
"""

import pytest
import respx
import httpx
import json
from rustchain_sdk.client import RustChainClient
from rustchain_sdk.exceptions import ConnectionError, APIError


class TestRustChainClientInit:
    """Test client initialization."""

    def test_default_base_url(self):
        """Default base URL is set correctly."""
        client = RustChainClient()
        assert client._base_url == "https://50.28.86.131"

    def test_custom_base_url(self):
        """Custom base URL is set correctly."""
        client = RustChainClient(base_url="https://custom.node.com")
        assert client._base_url == "https://custom.node.com"

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash is stripped from base URL."""
        client = RustChainClient(base_url="https://node.com/")
        assert client._base_url == "https://node.com"

    def test_default_timeout(self):
        """Default timeout is 30 seconds."""
        client = RustChainClient()
        assert client._timeout == 30.0


class TestRustChainClientContextManager:
    """Test async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        """Context manager closes the HTTP client on exit."""
        client = RustChainClient()
        async with client as c:
            assert c is client
        # Client should be closed after exiting
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Calling close multiple times is safe."""
        client = RustChainClient()
        await client.close()
        await client.close()  # Should not raise


class TestRustChainClientHealth:
    """Test health endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_returns_dict(self):
        """Health returns a dict."""
        route = respx.get("https://50.28.86.131/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "version": "1.0.0"})
        )
        async with RustChainClient() as client:
            result = await client.health()
        assert isinstance(result, dict)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_raises_on_connection_error(self):
        """Connection error raises RustChainError."""
        route = respx.get("https://50.28.86.131/health").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        async with RustChainClient() as client:
            with pytest.raises(ConnectionError):
                await client.health()


class TestRustChainClientEpoch:
    """Test epoch endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_epoch_returns_dict(self):
        """get_epoch returns epoch info dict."""
        route = respx.get("https://50.28.86.131/epoch").mock(
            return_value=httpx.Response(200, json={
                "epoch_number": 42,
                "start_time": 1700000000,
                "end_time": 1700064000,
            })
        )
        async with RustChainClient() as client:
            result = await client.get_epoch()
        assert isinstance(result, dict)
        assert result["epoch_number"] == 42


class TestRustChainClientMiners:
    """Test miners endpoints."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_miners_returns_list(self):
        """get_miners returns a list of miner dicts."""
        route = respx.get("https://50.28.86.131/miners").mock(
            return_value=httpx.Response(200, json=[
                {"public_key": "pk1", "score": 100},
                {"public_key": "pk2", "score": 90},
            ])
        )
        async with RustChainClient() as client:
            miners = await client.get_miners()
        assert isinstance(miners, list)
        assert len(miners) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_miners_handles_dict_response(self):
        """get_miners handles miners nested in dict response."""
        route = respx.get("https://50.28.86.131/miners").mock(
            return_value=httpx.Response(200, json={
                "miners": [{"public_key": "pk1", "score": 100}]
            })
        )
        async with RustChainClient() as client:
            miners = await client.get_miners()
        assert isinstance(miners, list)
        assert len(miners) == 1


class TestRustChainClientBalance:
    """Test balance endpoints."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_balance_returns_dict(self):
        """get_balance returns balance info dict."""
        route = respx.get("https://50.28.86.131/wallet/balance").mock(
            return_value=httpx.Response(200, json={
                "address": "RTCabc123",
                "balance": 1000,
                "nonce": 5,
            })
        )
        async with RustChainClient() as client:
            result = await client.get_balance("RTCabc123")
        assert result["balance"] == 1000
        assert result["nonce"] == 5


class TestRustChainClientTransfer:
    """Test transfer endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_transfer_signed_success(self):
        """transfer_signed returns tx result."""
        route = respx.post("https://50.28.86.131/wallet/transfer/signed").mock(
            return_value=httpx.Response(200, json={
                "tx_hash": "0xabc123",
                "status": "confirmed",
            })
        )
        async with RustChainClient() as client:
            result = await client.transfer_signed(
                from_address="RTCfrom",
                to_address="RTCto",
                amount=100,
                fee=1,
                signature="sighex",
                timestamp=1700000000,
                public_key="pubhex",
                memo="sdk test",
            )
        assert result["tx_hash"] == "0xabc123"
        assert result["status"] == "confirmed"
        assert route.calls[0].request.url.path == "/wallet/transfer/signed"
        assert json.loads(route.calls[0].request.content) == {
            "from_address": "RTCfrom",
            "to_address": "RTCto",
            "amount_rtc": 100,
            "nonce": 1700000000,
            "signature": "sighex",
            "public_key": "pubhex",
            "memo": "sdk test",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_transfer_signed_raises_on_api_error(self):
        """API error raises APIError with status code."""
        route = respx.post("https://50.28.86.131/wallet/transfer/signed").mock(
            return_value=httpx.Response(400, json={"message": "Invalid signature"})
        )
        async with RustChainClient() as client:
            with pytest.raises(APIError) as exc_info:
                await client.transfer_signed(
                    "RTCfrom", "RTCto", 100, 0, "bad", 0, public_key="pubhex"
                )
            assert exc_info.value.status_code == 400


class TestRustChainClientExplorer:
    """Test explorer endpoints."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_explorer_blocks_returns_list(self):
        """explorer_blocks returns list of blocks."""
        route = respx.get("https://50.28.86.131/explorer/blocks").mock(
            return_value=httpx.Response(200, json=[
                {"height": 100, "hash": "0x1"},
                {"height": 99, "hash": "0x2"},
            ])
        )
        async with RustChainClient() as client:
            blocks = await client.explorer_blocks(limit=20)
        assert isinstance(blocks, list)
        assert len(blocks) == 2
        assert blocks[0]["height"] == 100

    @pytest.mark.asyncio
    @respx.mock
    async def test_explorer_transactions_filters_by_address(self):
        """explorer_transactions sends address as param."""
        route = respx.get("https://50.28.86.131/explorer/transactions").mock(
            return_value=httpx.Response(200, json=[])
        )
        async with RustChainClient() as client:
            await client.explorer_transactions(address="RTCabc", limit=10)
        assert route.called
        assert route.calls[0].request.url.params["address"] == "RTCabc"


class TestRustChainClientGovernance:
    """Test governance endpoints."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_governance_proposals(self):
        """list_governance_proposals returns list."""
        route = respx.get("https://50.28.86.131/governance/proposals").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "type": "param_change", "status": "active"},
            ])
        )
        async with RustChainClient() as client:
            proposals = await client.list_governance_proposals()
        assert isinstance(proposals, list)
        assert proposals[0]["id"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_governance_vote_success(self):
        """governance_vote returns vote result."""
        route = respx.post("https://50.28.86.131/governance/vote").mock(
            return_value=httpx.Response(200, json={
                "proposal_id": 1,
                "vote": "yes",
                "result": "accepted",
            })
        )
        async with RustChainClient() as client:
            result = await client.governance_vote(
                voter="RTCvoter",
                proposal_id=1,
                vote="yes",
                signature="sighex",
            )
        assert result["result"] == "accepted"


class TestRustChainClientAttestation:
    """Test attestation endpoints."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_attest_challenge_returns_challenge(self):
        """attest_challenge returns challenge string."""
        route = respx.post("https://50.28.86.131/attestation/challenge").mock(
            return_value=httpx.Response(200, json={
                "challenge": "random-challenge-string",
                "expires_at": 1700010000,
            })
        )
        async with RustChainClient() as client:
            result = await client.attest_challenge("pk-hex")
        assert result["challenge"] == "random-challenge-string"

    @pytest.mark.asyncio
    @respx.mock
    async def test_attest_submit_success(self):
        """attest_submit returns submission result."""
        route = respx.post("https://50.28.86.131/attestation/submit").mock(
            return_value=httpx.Response(200, json={
                "status": "attested",
                "miner_public_key": "pk-hex",
            })
        )
        async with RustChainClient() as client:
            result = await client.attest_submit("pk-hex", "response", "sig")
        assert result["status"] == "attested"
