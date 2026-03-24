"""Tests for RustChain Python SDK."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from rustchain.client import RustChainClient
from rustchain.models import NodeHealth, EpochInfo, MinerInfo, BalanceInfo, SignedTransfer
from rustchain.exceptions import APIError, ValidationError, AuthenticationError
import httpx


# --- Fixtures ---

@pytest.fixture
def mock_httpx_response():
    def make(status_code: int = 200, json_data: dict | list | None = None):
        response = MagicMock()
        response.status_code = status_code
        response.text = ""
        if json_data is not None:
            response.json.return_value = json_data
        return response
    return make


@pytest.fixture
def health_data():
    return {
        "ok": True,
        "version": "1.0.0",
        "uptime_s": 86400,
        "db_rw": True,
        "tip_age_slots": 5,
        "backup_age_hours": 1.0,
    }


@pytest.fixture
def epoch_data():
    return {
        "epoch": 42,
        "slot": 128,
        "blocks_per_epoch": 1024,
        "epoch_pot": 5000.0,
        "enrolled_miners": 100,
    }


@pytest.fixture
def miners_data():
    return [
        {
            "miner": "miner001",
            "device_arch": "x86_64",
            "device_family": "CPU",
            "hardware_type": "generic",
            "antiquity_multiplier": 1.5,
            "last_attest": 1234567890,
        },
        {
            "miner": "miner002",
            "device_arch": "arm64",
            "device_family": "GPU",
            "hardware_type": "nvidia",
            "antiquity_multiplier": 2.0,
            "last_attest": 1234567900,
        },
    ]


@pytest.fixture
def balance_data():
    return {
        "ok": True,
        "miner_id": "miner001",
        "amount_rtc": 1234.56,
        "amount_i64": 1234560000,
    }


# --- Model Tests ---

class TestModels:
    def test_node_health_from_dict(self, health_data):
        h = NodeHealth(**health_data)
        assert h.ok is True
        assert h.version == "1.0.0"
        assert h.uptime_s == 86400

    def test_epoch_info_from_dict(self, epoch_data):
        e = EpochInfo(**epoch_data)
        assert e.epoch == 42
        assert e.slot == 128
        assert e.blocks_per_epoch == 1024

    def test_miner_info_from_dict(self, miners_data):
        m = MinerInfo(**miners_data[0])
        assert m.miner == "miner001"
        assert m.device_arch == "x86_64"
        assert m.antiquity_multiplier == 1.5

    def test_balance_info_from_dict(self, balance_data):
        b = BalanceInfo(**balance_data)
        assert b.ok is True
        assert b.miner_id == "miner001"
        assert b.amount_rtc == 1234.56

    def test_signed_transfer_to_dict(self):
        tx = SignedTransfer(
            from_address="addr_from",
            to_address="addr_to",
            amount_rtc=100.0,
            nonce=5,
            signature="sig123",
            public_key="pub456",
        )
        d = tx.to_dict()
        assert d["from_address"] == "addr_from"
        assert d["to_address"] == "addr_to"
        assert d["amount_rtc"] == 100.0
        assert d["nonce"] == 5


# --- Client Tests ---

class TestRustChainClientInit:
    def test_default_base_url(self):
        client = RustChainClient()
        assert client.base_url == "https://rustchain.org"
        assert client.timeout == 30.0

    def test_custom_base_url(self):
        client = RustChainClient(base_url="https://node.example.com/", timeout=60.0)
        assert client.base_url == "https://node.example.com"
        assert client.timeout == 60.0


class TestRustChainClientContextManager:
    @pytest.mark.asyncio
    async def test_context_manager_enters(self):
        async with RustChainClient() as client:
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_context_manager_exits(self):
        async with RustChainClient() as client:
            pass
        assert client._client is None

    @pytest.mark.asyncio
    async def test_client_not_initialized_error(self):
        client = RustChainClient()
        with pytest.raises(RuntimeError, match="not initialized"):
            await client.get_health()


class TestGetHealth:
    @pytest.mark.asyncio
    async def test_get_health_success(self, health_data, mock_httpx_response):
        mock_resp = mock_httpx_response(200, health_data)
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            async with RustChainClient() as client:
                health = await client.get_health()
                assert health.ok is True
                assert health.version == "1.0.0"
                assert health.uptime_s == 86400


class TestGetEpoch:
    @pytest.mark.asyncio
    async def test_get_epoch_success(self, epoch_data, mock_httpx_response):
        mock_resp = mock_httpx_response(200, epoch_data)
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            async with RustChainClient() as client:
                epoch = await client.get_epoch()
                assert epoch.epoch == 42
                assert epoch.slot == 128
                assert epoch.blocks_per_epoch == 1024


class TestGetMiners:
    @pytest.mark.asyncio
    async def test_get_miners_success(self, miners_data, mock_httpx_response):
        mock_resp = mock_httpx_response(200, miners_data)
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            async with RustChainClient() as client:
                miners = await client.get_miners()
                assert len(miners) == 2
                assert miners[0].miner == "miner001"


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_get_balance_success(self, balance_data, mock_httpx_response):
        mock_resp = mock_httpx_response(200, balance_data)
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            async with RustChainClient() as client:
                bal = await client.get_balance("miner001")
                assert bal.ok is True
                assert bal.miner_id == "miner001"
                assert bal.amount_rtc == 1234.56


class TestSubmitTransferSigned:
    @pytest.mark.asyncio
    async def test_submit_transfer_signed_success(self, mock_httpx_response):
        mock_resp = mock_httpx_response(200, {"ok": True, "tx_hash": "0xabc"})
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            tx = SignedTransfer(
                from_address="from_addr",
                to_address="to_addr",
                amount_rtc=50.0,
                nonce=1,
                signature="sig_abc",
                public_key="pub_xyz",
            )
            async with RustChainClient() as client:
                result = await client.submit_transfer_signed(tx)
                assert result["ok"] is True
                assert result["tx_hash"] == "0xabc"


class TestAdminTransfer:
    @pytest.mark.asyncio
    async def test_admin_transfer_success(self, mock_httpx_response):
        mock_resp = mock_httpx_response(200, {"ok": True})
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            async with RustChainClient() as client:
                result = await client.admin_transfer(
                    admin_key="secret_key",
                    from_miner="miner_a",
                    to_miner="miner_b",
                    amount_rtc=100.0,
                )
                assert result["ok"] is True


class TestSettleRewards:
    @pytest.mark.asyncio
    async def test_settle_rewards_success(self, mock_httpx_response):
        mock_resp = mock_httpx_response(200, {"ok": True, "settled": 50})
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            async with RustChainClient() as client:
                result = await client.settle_rewards(admin_key="admin_secret")
                assert result["ok"] is True
                assert result["settled"] == 50


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_validation_error_400(self, mock_httpx_response):
        mock_resp = mock_httpx_response(400, {"error": "bad request"})
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            async with RustChainClient() as client:
                with pytest.raises(ValidationError):
                    await client.get_health()

    @pytest.mark.asyncio
    async def test_authentication_error_403(self, mock_httpx_response):
        mock_resp = mock_httpx_response(403, {"error": "forbidden"})
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            async with RustChainClient() as client:
                with pytest.raises(AuthenticationError):
                    await client.settle_rewards(admin_key="bad_key")

    @pytest.mark.asyncio
    async def test_api_error_500(self, mock_httpx_response):
        mock_resp = mock_httpx_response(500, {"error": "server error"})
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            async with RustChainClient() as client:
                with pytest.raises(APIError) as exc_info:
                    await client.get_epoch()
                assert exc_info.value.status_code == 500
