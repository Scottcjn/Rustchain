"""
Unit tests for RustChain Client (with mocked responses)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from rustchain import RustChainClient
from rustchain.exceptions import (
    ConnectionError,
    ValidationError,
    APIError,
    AttestationError,
    TransferError,
)


class TestRustChainClient:
    """Test RustChainClient initialization and configuration"""

    def test_init_with_defaults(self):
        """Test client initialization with default parameters"""
        client = RustChainClient("https://50.28.86.131")
        assert client.base_url == "https://50.28.86.131"
        assert client.verify_ssl is True
        assert client.timeout == 30
        client.close()

    def test_init_without_ssl_verification(self):
        """Test client initialization without SSL verification"""
        client = RustChainClient("https://50.28.86.131", verify_ssl=False)
        assert client.verify_ssl is False
        assert client.session.verify is False
        client.close()

    def test_init_with_custom_timeout(self):
        """Test client initialization with custom timeout"""
        client = RustChainClient("https://50.28.86.131", timeout=60)
        assert client.timeout == 60
        client.close()

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base URL"""
        client = RustChainClient("https://50.28.86.131/")
        assert client.base_url == "https://50.28.86.131"
        client.close()

    def test_context_manager(self):
        """Test client as context manager"""
        with RustChainClient("https://50.28.86.131") as client:
            assert client.base_url == "https://50.28.86.131"
        # Session should be closed after exiting context


class TestHealthEndpoint:
    """Test /health endpoint"""

    @patch("requests.Session.request")
    def test_health_success(self, mock_request):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "uptime_s": 55556,
            "version": "2.2.1-rip200",
            "db_rw": True,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            health = client.health()

        assert health["ok"] is True
        assert health["uptime_s"] == 55556
        assert health["version"] == "2.2.1-rip200"
        assert health["db_rw"] is True

        mock_request.assert_called_once()

    @patch("requests.Session.request")
    def test_health_connection_error(self, mock_request):
        """Test health check with connection error"""
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError("Failed to connect")

        with pytest.raises(ConnectionError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.health()

        assert "Failed to connect" in str(exc_info.value)


class TestEpochEndpoint:
    """Test /epoch endpoint"""

    @patch("requests.Session.request")
    def test_epoch_success(self, mock_request):
        """Test successful epoch query"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "epoch": 74,
            "slot": 10745,
            "blocks_per_epoch": 144,
            "enrolled_miners": 32,
            "epoch_pot": 1.5,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            epoch = client.epoch()

        assert epoch["epoch"] == 74
        assert epoch["slot"] == 10745
        assert epoch["blocks_per_epoch"] == 144
        assert epoch["enrolled_miners"] == 32
        assert epoch["epoch_pot"] == 1.5


class TestMinersEndpoint:
    """Test /api/miners endpoint"""

    @patch("requests.Session.request")
    def test_miners_success(self, mock_request):
        """Test successful miners query"""
        mock_response = Mock()
        mock_response.json.return_value = [
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
        ]
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            miners = client.miners()

        assert len(miners) == 2
        assert miners[0]["antiquity_multiplier"] == 2.5
        assert miners[1]["hardware_type"] == "x86-64 (Modern)"

    @patch("requests.Session.request")
    def test_miners_empty_list(self, mock_request):
        """Test miners endpoint returning empty list"""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            miners = client.miners()

        assert miners == []


class TestBalanceEndpoint:
    """Test /balance endpoint"""

    @patch("requests.Session.request")
    def test_balance_success(self, mock_request):
        """Test successful balance query"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "miner_pk": "test_wallet_address",
            "balance": 123.456,
            "epoch_rewards": 10.0,
            "total_earned": 1000.0,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            balance = client.balance("test_wallet_address")

        assert balance["balance"] == 123.456
        assert balance["epoch_rewards"] == 10.0
        assert balance["total_earned"] == 1000.0

    def test_balance_empty_miner_id(self):
        """Test balance with empty miner_id raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.balance("")

        assert "miner_id" in str(exc_info.value)

    def test_balance_none_miner_id(self):
        """Test balance with None miner_id raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.balance(None)

        assert "miner_id" in str(exc_info.value)


class TestTransferEndpoint:
    """Test /wallet/transfer/signed endpoint"""

    @patch("requests.Session.request")
    def test_transfer_success(self, mock_request):
        """Test successful transfer"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "tx_id": "tx_abc123",
            "fee": 0.01,
            "new_balance": 89.99,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            result = client.transfer(
                from_addr="wallet1",
                to_addr="wallet2",
                amount=10.0,
            )

        assert result["success"] is True
        assert result["tx_id"] == "tx_abc123"
        assert result["fee"] == 0.01

    @patch("requests.Session.request")
    def test_transfer_with_signature(self, mock_request):
        """Test transfer with signature"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "tx_id": "tx_def456",
            "fee": 0.01,
            "new_balance": 89.99,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            result = client.transfer(
                from_addr="wallet1",
                to_addr="wallet2",
                amount=10.0,
                signature="sig_xyz789",
            )

        assert result["success"] is True

    def test_transfer_negative_amount(self):
        """Test transfer with negative amount raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.transfer("wallet1", "wallet2", -10.0)

        assert "amount must be positive" in str(exc_info.value)

    def test_transfer_zero_amount(self):
        """Test transfer with zero amount raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.transfer("wallet1", "wallet2", 0.0)

        assert "amount must be positive" in str(exc_info.value)

    def test_transfer_empty_from_addr(self):
        """Test transfer with empty from_addr raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.transfer("", "wallet2", 10.0)

        assert "from_addr" in str(exc_info.value)

    def test_transfer_empty_to_addr(self):
        """Test transfer with empty to_addr raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.transfer("wallet1", "", 10.0)

        assert "to_addr" in str(exc_info.value)


class TestAttestationEndpoint:
    """Test /attest/submit endpoint"""

    @patch("requests.Session.request")
    def test_submit_attestation_success(self, mock_request):
        """Test successful attestation submission"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "epoch": 74,
            "slot": 10745,
            "multiplier": 2.5,
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        payload = {
            "miner_id": "wallet_address",
            "device": {"arch": "G4", "cores": 1},
            "fingerprint": {"checks": {}},
            "nonce": "unique_nonce",
        }

        with RustChainClient("https://50.28.86.131") as client:
            result = client.submit_attestation(payload)

        assert result["success"] is True
        assert result["epoch"] == 74
        assert result["multiplier"] == 2.5

    def test_submit_attestation_missing_miner_id(self):
        """Test attestation without miner_id raises ValidationError"""
        payload = {
            "device": {"arch": "G4"},
            "fingerprint": {"checks": {}},
        }

        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.submit_attestation(payload)

        assert "miner_id" in str(exc_info.value)

    def test_submit_attestation_missing_device(self):
        """Test attestation without device raises ValidationError"""
        payload = {
            "miner_id": "wallet_address",
            "fingerprint": {"checks": {}},
        }

        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.submit_attestation(payload)

        assert "device" in str(exc_info.value)

    def test_submit_attestation_empty_payload(self):
        """Test attestation with empty payload raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            with RustChainClient("https://50.28.86.131") as client:
                client.submit_attestation({})

        assert "payload" in str(exc_info.value)


class TestTransferHistory:
    """Test /wallet/history endpoint"""

    @patch("requests.Session.request")
    def test_transfer_history_success(self, mock_request):
        """Test successful transfer history query"""
        mock_response = Mock()
        mock_response.json.return_value = [
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
        ]
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        with RustChainClient("https://50.28.86.131") as client:
            history = client.transfer_history("wallet_address", limit=10)

        assert len(history) == 2
        assert history[0]["amount"] == 10.0
        assert history[1]["amount"] == 5.0
