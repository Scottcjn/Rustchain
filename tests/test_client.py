"""Unit tests for RustChainClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from rustchain.client import RustChainClient
from rustchain.exceptions import APIError, NetworkError, WalletError


class TestHealth:
    """Tests for client.health()."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "version": "1.0.0"}
        mock_response.raise_for_status = MagicMock()

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_response)

        result = await client.health()
        assert result.status == "ok"
        assert result.version == "1.0.0"
        await client.close()

    @pytest.mark.asyncio
    async def test_health_timeout_raises_network_error(self):
        import httpx

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(NetworkError) as exc_info:
            await client.health()
        assert "timed out" in exc_info.value.message
        await client.close()

    @pytest.mark.asyncio
    async def test_health_http_error_raises_api_error(self):
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_response
        ))

        with pytest.raises(APIError) as exc_info:
            await client.health()
        assert exc_info.value.status_code == 500
        await client.close()


class TestEpoch:
    """Tests for client.epoch()."""

    @pytest.mark.asyncio
    async def test_epoch_returns_info(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "epoch": 42,
            "start_block": 1000,
            "end_block": 2000,
        }
        mock_response.raise_for_status = MagicMock()

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_response)

        result = await client.epoch()
        assert result.epoch == 42
        assert result.start_block == 1000
        await client.close()


class TestMiners:
    """Tests for client.miners()."""

    @pytest.mark.asyncio
    async def test_miners_returns_list(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "miners": [
                {
                    "miner_id": "miner1",
                    "wallet_id": "wallet1",
                    "status": "active",
                    "power": 100,
                    "rewards": 1.5,
                }
            ],
            "total": 1,
            "page": 1,
            "per_page": 20,
        }
        mock_response.raise_for_status = MagicMock()

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_response)

        result = await client.miners()
        assert len(result.miners) == 1
        assert result.total == 1
        assert result.miners[0].miner_id == "miner1"
        await client.close()

    @pytest.mark.asyncio
    async def test_miners_respects_pagination_params(self):
        client = RustChainClient()
        client._http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"miners": [], "total": 0, "page": 3, "per_page": 50}
        mock_response.raise_for_status = MagicMock()
        client._http.get = AsyncMock(return_value=mock_response)

        await client.miners(page=3, per_page=50)
        client._http.get.assert_called_once()
        call_args = client._http.get.call_args
        assert call_args.kwargs["params"]["page"] == 3
        assert call_args.kwargs["params"]["per_page"] == 50
        await client.close()


class TestBalance:
    """Tests for client.balance()."""

    @pytest.mark.asyncio
    async def test_balance_returns_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "wallet_id": "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
            "balance": 100.5,
            "locked": 10.0,
        }
        mock_response.raise_for_status = MagicMock()

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_response)

        result = await client.balance("C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg")
        assert result.balance == 100.5
        assert result.locked == 10.0
        await client.close()

    @pytest.mark.asyncio
    async def test_balance_invalid_address_raises_wallet_error(self):
        client = RustChainClient()
        with pytest.raises(WalletError) as exc_info:
            await client.balance("not-a-valid-address!!!")
        assert "Invalid wallet address" in exc_info.value.message
        await client.close()


class TestTransfer:
    """Tests for client.transfer()."""

    @pytest.mark.asyncio
    async def test_transfer_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tx_hash": "abc123",
            "from_wallet": "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
            "to_wallet": "AnotherWallet12345678901234567890123456",
            "amount": 50.0,
            "fee": 0.001,
            "status": "confirmed",
        }
        mock_response.raise_for_status = MagicMock()

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        result = await client.transfer(
            "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
            "AnotherWallet12345678901234567890123456",
            50.0,
            "sig123",
        )
        assert result.tx_hash == "abc123"
        assert result.status == "confirmed"
        await client.close()

    @pytest.mark.asyncio
    async def test_transfer_negative_amount_raises_wallet_error(self):
        client = RustChainClient()
        with pytest.raises(WalletError) as exc_info:
            await client.transfer(
                "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
                "AnotherWallet12345678901234567890123456",
                -10.0,
                "sig",
            )
        assert "positive" in exc_info.value.message
        await client.close()

    @pytest.mark.asyncio
    async def test_transfer_invalid_sender_raises_wallet_error(self):
        client = RustChainClient()
        with pytest.raises(WalletError) as exc_info:
            await client.transfer(
                "bad",
                "AnotherWallet12345678901234567890123456",
                10.0,
                "sig",
            )
        assert "Invalid sender address" in exc_info.value.message
        await client.close()


class TestAttestationStatus:
    """Tests for client.attestation_status()."""

    @pytest.mark.asyncio
    async def test_attestation_status_returns_info(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "miner_id": "miner_001",
            "attested": True,
            "attestations_count": 100,
            "score": 95.5,
        }
        mock_response.raise_for_status = MagicMock()

        client = RustChainClient()
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_response)

        result = await client.attestation_status("miner_001")
        assert result.attested is True
        assert result.score == 95.5
        await client.close()


class TestContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_aenter_returns_client(self):
        async with RustChainClient() as client:
            assert isinstance(client, RustChainClient)

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        client = RustChainClient()
        client._http = AsyncMock()
        client._http.aclose = AsyncMock()

        async with client:
            pass

        client._http.aclose.assert_awaited_once()
