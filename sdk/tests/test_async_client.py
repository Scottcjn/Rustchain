"""
Unit tests for RustChain Async Client
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from rustchain.async_client import AsyncRustChainClient
from rustchain.exceptions import (
    ConnectionError,
    ValidationError,
    APIError,
    AttestationError,
    TransferError,
)


class AsyncContextManager:
    """Helper class to mock async context manager"""
    def __init__(self, response):
        self.response = response
    
    async def __aenter__(self):
        return self.response
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestAsyncRustChainClient:
    """Test AsyncRustChainClient initialization and configuration"""

    def test_init_with_defaults(self):
        """Test client initialization with default parameters"""
        client = AsyncRustChainClient("https://rustchain.org")
        assert client.base_url == "https://rustchain.org"
        assert client.verify_ssl is True
        assert client.timeout == 30

    def test_init_without_ssl_verification(self):
        """Test client initialization without SSL verification"""
        client = AsyncRustChainClient("https://rustchain.org", verify_ssl=False)
        assert client.verify_ssl is False

    def test_init_with_custom_timeout(self):
        """Test client initialization with custom timeout"""
        client = AsyncRustChainClient("https://rustchain.org", timeout=60)
        assert client.timeout == 60

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base URL"""
        client = AsyncRustChainClient("https://rustchain.org/")
        assert client.base_url == "https://rustchain.org"

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test client as async context manager"""
        async with AsyncRustChainClient("https://rustchain.org") as client:
            assert client.base_url == "https://rustchain.org"
        # Session should be closed after exiting context


class TestAsyncHealthEndpoint:
    """Test /health endpoint"""

    @pytest.mark.asyncio
    async def test_health_success(self):
        """Test successful health check"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "ok": True,
            "uptime_s": 55556,
            "version": "2.2.1-rip200",
            "db_rw": True,
        })
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                health = await client.health()

            assert health["ok"] is True
            assert health["uptime_s"] == 55556
            assert health["version"] == "2.2.1-rip200"
            assert health["db_rw"] is True

    @pytest.mark.asyncio
    async def test_health_connection_error(self):
        """Test health check with connection error"""
        import aiohttp
        
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientConnectionError("Failed to connect"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            with pytest.raises(ConnectionError) as exc_info:
                async with AsyncRustChainClient("https://rustchain.org") as client:
                    await client.health()

            assert "Failed to connect" in str(exc_info.value)


class TestAsyncEpochEndpoint:
    """Test /epoch endpoint"""

    @pytest.mark.asyncio
    async def test_epoch_success(self):
        """Test successful epoch query"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "epoch": 74,
            "slot": 10745,
            "blocks_per_epoch": 144,
            "enrolled_miners": 32,
            "epoch_pot": 1.5,
        })
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                epoch = await client.epoch()

            assert epoch["epoch"] == 74
            assert epoch["slot"] == 10745
            assert epoch["blocks_per_epoch"] == 144
            assert epoch["enrolled_miners"] == 32
            assert epoch["epoch_pot"] == 1.5


class TestAsyncMinersEndpoint:
    """Test /api/miners endpoint"""

    @pytest.mark.asyncio
    async def test_miners_success(self):
        """Test successful miners query"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {
                "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
                "antiquity_multiplier": 2.5,
                "hardware_type": "PowerPC G4 (Vintage)",
                "device_arch": "G4",
                "last_attest": 1771154269,
            },
            {
                "miner": "modern-sophia-Pow-9862e3be",
                "antiquity_multiplier": 1.0,
                "hardware_type": "x86-64 (Modern)",
                "device_arch": "modern",
                "last_attest": 1771154254,
            },
        ])
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                miners = await client.miners()

            assert len(miners) == 2
            assert miners[0]["antiquity_multiplier"] == 2.5
            assert miners[1]["hardware_type"] == "x86-64 (Modern)"

    @pytest.mark.asyncio
    async def test_miners_empty_list(self):
        """Test miners endpoint returning empty list"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                miners = await client.miners()

            assert miners == []


class TestAsyncBalanceEndpoint:
    """Test /wallet/balance endpoint"""

    @pytest.mark.asyncio
    async def test_balance_success(self):
        """Test successful balance query"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "miner_pk": "test_wallet_address",
            "balance": 123.456,
            "epoch_rewards": 10.0,
            "total_earned": 1000.0,
        })
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                balance = await client.balance("test_wallet_address")

            assert balance["balance"] == 123.456
            assert balance["epoch_rewards"] == 10.0
            assert balance["total_earned"] == 1000.0
            mock_request.assert_called_once()
            assert mock_request.call_args.kwargs["url"] == "https://rustchain.org/wallet/balance"
            assert mock_request.call_args.kwargs["params"] == {"miner_id": "test_wallet_address"}

    @pytest.mark.asyncio
    async def test_balance_empty_miner_id(self):
        """Test balance with empty miner_id raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.balance("")

        assert "miner_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_balance_none_miner_id(self):
        """Test balance with None miner_id raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.balance(None)

        assert "miner_id" in str(exc_info.value)


class TestAsyncTransferEndpoint:
    """Test /wallet/transfer/signed endpoint"""

    @pytest.mark.asyncio
    async def test_transfer_success(self):
        """Test successful transfer"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "success": True,
            "tx_id": "tx_abc123",
            "fee": 0.01,
            "new_balance": 89.99,
        })
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                result = await client.transfer(
                    from_addr="wallet1",
                    to_addr="wallet2",
                    amount=10.0,
                )

            assert result["success"] is True
            assert result["tx_id"] == "tx_abc123"
            assert result["fee"] == 0.01

    @pytest.mark.asyncio
    async def test_transfer_with_signature(self):
        """Test transfer with signature"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "success": True,
            "tx_id": "tx_def456",
            "fee": 0.01,
            "new_balance": 89.99,
        })
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                result = await client.transfer(
                    from_addr="wallet1",
                    to_addr="wallet2",
                    amount=10.0,
                    signature="sig_xyz789",
                )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_transfer_negative_amount(self):
        """Test transfer with negative amount raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.transfer("wallet1", "wallet2", -10.0)

        assert "amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transfer_zero_amount(self):
        """Test transfer with zero amount raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.transfer("wallet1", "wallet2", 0.0)

        assert "amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transfer_empty_from_addr(self):
        """Test transfer with empty from_addr raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.transfer("", "wallet2", 10.0)

        assert "from_addr" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transfer_empty_to_addr(self):
        """Test transfer with empty to_addr raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.transfer("wallet1", "", 10.0)

        assert "to_addr" in str(exc_info.value)


class TestAsyncAttestationEndpoint:
    """Test /attest/submit endpoint"""

    @pytest.mark.asyncio
    async def test_submit_attestation_success(self):
        """Test successful attestation submission"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "success": True,
            "epoch": 74,
            "slot": 10745,
            "multiplier": 2.5,
        })
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            payload = {
                "miner_id": "wallet_address",
                "device": {"arch": "G4", "cores": 1},
                "fingerprint": {"checks": {}},
                "nonce": "unique_nonce",
            }

            async with AsyncRustChainClient("https://rustchain.org") as client:
                result = await client.submit_attestation(payload)

            assert result["success"] is True
            assert result["epoch"] == 74
            assert result["multiplier"] == 2.5

    @pytest.mark.asyncio
    async def test_submit_attestation_missing_miner_id(self):
        """Test attestation without miner_id raises ValidationError"""
        payload = {
            "device": {"arch": "G4"},
            "fingerprint": {"checks": {}},
        }

        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.submit_attestation(payload)

        assert "miner_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_attestation_missing_device(self):
        """Test attestation without device raises ValidationError"""
        payload = {
            "miner_id": "wallet_address",
            "fingerprint": {"checks": {}},
        }

        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.submit_attestation(payload)

        assert "device" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_attestation_empty_payload(self):
        """Test attestation with empty payload raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            async with AsyncRustChainClient("https://rustchain.org") as client:
                await client.submit_attestation({})

        assert "payload" in str(exc_info.value)


class TestAsyncTransferHistory:
    """Test /wallet/history endpoint"""

    @pytest.mark.asyncio
    async def test_transfer_history_success(self):
        """Test successful transfer history query"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {
                "tx_id": "tx_abc123",
                "from_addr": "wallet1",
                "to_addr": "wallet2",
                "amount": 10.0,
                "timestamp": 1771154269,
                "status": "completed",
            },
            {
                "tx_id": "tx_def456",
                "from_addr": "wallet3",
                "to_addr": "wallet1",
                "amount": 5.0,
                "timestamp": 1771154200,
                "status": "completed",
            },
        ])
        mock_response.reason = "OK"
        
        mock_cm = AsyncContextManager(mock_response)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_request = Mock(return_value=mock_cm)
            mock_session = Mock()
            mock_session.request = mock_request
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            async with AsyncRustChainClient("https://rustchain.org") as client:
                history = await client.transfer_history("wallet_address", limit=10)

            assert len(history) == 2
            assert history[0]["amount"] == 10.0
            assert history[1]["amount"] == 5.0
