"""
Tests for RustChain Python SDK
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from rustchain import RustChainClient, Wallet, Transaction
from rustchain.exceptions import (
    RustChainError,
    WalletError,
    TransactionError,
    NetworkError,
    AuthenticationError
)


class TestRustChainClient:
    """Test cases for RustChainClient"""
    
    @pytest.fixture
    def client(self):
        """Create a test client"""
        return RustChainClient(
            node_url="https://test-node.example.com",
            admin_key="test-admin-key",
            timeout=5
        )
    
    @patch('rustchain.client.requests.Session')
    def test_get_balance_success(self, mock_session, client):
        """Test successful balance query"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "miner_id": "test-wallet",
            "balance_rtc": 100.5
        }
        mock_response.raise_for_status.return_value = None
        
        session_instance = mock_session.return_value
        session_instance.request.return_value = mock_response
        
        result = client.get_balance("test-wallet")
        
        assert result["miner_id"] == "test-wallet"
        assert result["balance_rtc"] == 100.5
        session_instance.request.assert_called_once()
    
    @patch('rustchain.client.requests.Session')
    def test_get_balance_network_error(self, mock_session, client):
        """Test network error handling"""
        session_instance = mock_session.return_value
        session_instance.request.side_effect = requests.ConnectionError()
        
        with pytest.raises(NetworkError):
            client.get_balance("test-wallet")
    
    @patch('rustchain.client.requests.Session')
    def test_check_wallet_exists(self, mock_session, client):
        """Test wallet existence check"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "miner_id": "test-wallet",
            "balance_rtc": 0
        }
        mock_response.raise_for_status.return_value = None
        
        session_instance = mock_session.return_value
        session_instance.request.return_value = mock_response
        
        exists = client.check_wallet_exists("test-wallet")
        assert exists is True
    
    @patch('rustchain.client.requests.Session')
    def test_transfer_rtc(self, mock_session, client):
        """Test RTC transfer"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "pending_id": "tx-123",
            "status": "pending"
        }
        mock_response.raise_for_status.return_value = None
        
        session_instance = mock_session.return_value
        session_instance.request.return_value = mock_response
        
        result = client.transfer_rtc("wallet1", "wallet2", 10.0)
        
        assert result["pending_id"] == "tx-123"
        session_instance.request.assert_called_once()
    
    def test_transfer_rtc_no_admin_key(self):
        """Test transfer without admin key"""
        client = RustChainClient()
        
        with pytest.raises(AuthenticationError):
            client.transfer_rtc("wallet1", "wallet2", 10.0)
    
    @patch('rustchain.client.requests.Session')
    def test_get_epoch_info(self, mock_session, client):
        """Test epoch info retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "epoch": 42,
            "slot": 100,
            "enrolled_miners": ["miner1", "miner2"]
        }
        mock_response.raise_for_status.return_value = None
        
        session_instance = mock_session.return_value
        session_instance.request.return_value = mock_response
        
        result = client.get_epoch_info()
        
        assert result["epoch"] == 42
        assert result["slot"] == 100
        assert len(result["enrolled_miners"]) == 2


class TestWallet:
    """Test cases for Wallet class"""
    
    @pytest.fixture
    def wallet(self):
        """Create a Wallet instance"""
        client = RustChainClient(node_url="https://test-node.example.com")
        return Wallet(client)
    
    def test_validate_name_valid(self, wallet):
        """Test valid wallet name validation"""
        is_valid, msg = wallet.validate_name("my-wallet")
        assert is_valid is True
        assert "Valid" in msg
    
    def test_validate_name_too_short(self, wallet):
        """Test wallet name that's too short"""
        is_valid, msg = wallet.validate_name("ab")
        assert is_valid is False
        assert "3 characters" in msg
    
    def test_validate_name_too_long(self, wallet):
        """Test wallet name that's too long"""
        long_name = "a" * 100
        is_valid, msg = wallet.validate_name(long_name)
        assert is_valid is False
        assert "64 characters" in msg
    
    def test_validate_name_uppercase(self, wallet):
        """Test wallet name with uppercase letters"""
        is_valid, msg = wallet.validate_name("My-Wallet")
        assert is_valid is False
        assert "lowercase" in msg
    
    def test_validate_name_invalid_chars(self, wallet):
        """Test wallet name with invalid characters"""
        is_valid, msg = wallet.validate_name("my_wallet")
        assert is_valid is False
        assert "only contain lowercase letters, digits, and hyphens" in msg
    
    @patch.object(RustChainClient, 'check_wallet_exists')
    def test_wallet_exists(self, mock_check, wallet):
        """Test wallet existence check"""
        mock_check.return_value = True
        exists = wallet.exists("test-wallet")
        assert exists is True
        mock_check.assert_called_once_with("test-wallet")
    
    @patch.object(RustChainClient, 'get_balance')
    def test_get_balance(self, mock_get_balance, wallet):
        """Test wallet balance retrieval"""
        mock_get_balance.return_value = {
            "miner_id": "test-wallet",
            "balance_rtc": 50.0
        }
        balance = wallet.get_balance("test-wallet")
        assert balance == 50.0
        mock_get_balance.assert_called_once()


class TestTransaction:
    """Test cases for Transaction class"""
    
    @pytest.fixture
    def transaction(self):
        """Create a Transaction instance"""
        client = RustChainClient(
            node_url="https://test-node.example.com",
            admin_key="test-key"
        )
        return Transaction(client)
    
    def test_build_transfer(self, transaction):
        """Test transaction building"""
        preview = transaction.build_transfer("wallet1", "wallet2", 10.0)
        
        assert preview["from_miner"] == "wallet1"
        assert preview["to_miner"] == "wallet2"
        assert preview["amount_rtc"] == 10.0
        assert preview["status"] == "preview"
    
    def test_validate_transfer_valid(self, transaction):
        """Test valid transaction validation"""
        with patch.object(RustChainClient, 'check_wallet_exists', return_value=True):
            is_valid, msg = transaction.validate_transfer("wallet1", "wallet2", 10.0)
            assert is_valid is True
            assert "valid" in msg.lower()
    
    def test_validate_transfer_zero_amount(self, transaction):
        """Test transaction with zero amount"""
        is_valid, msg = transaction.validate_transfer("wallet1", "wallet2", 0)
        assert is_valid is False
        assert "greater than 0" in msg
    
    def test_validate_transfer_same_wallet(self, transaction):
        """Test transaction to same wallet"""
        is_valid, msg = transaction.validate_transfer("wallet1", "wallet1", 10.0)
        assert is_valid is False
        assert "same wallet" in msg
    
    @patch.object(RustChainClient, 'transfer_rtc')
    def test_send_transaction(self, mock_transfer, transaction):
        """Test sending transaction"""
        mock_transfer.return_value = {
            "pending_id": "tx-456",
            "status": "pending"
        }
        
        result = transaction.send("wallet1", "wallet2", 10.0)
        
        assert result["pending_id"] == "tx-456"
        mock_transfer.assert_called_once()
    
    def test_send_negative_amount(self, transaction):
        """Test sending negative amount"""
        with pytest.raises(TransactionError) as exc_info:
            transaction.send("wallet1", "wallet2", -10.0)
        assert "greater than 0" in str(exc_info.value)


class TestExceptions:
    """Test exception classes"""
    
    def test_rustchain_error(self):
        """Test RustChainError"""
        error = RustChainError("Test error", status_code=500)
        assert str(error) == "500: Test error"
        assert error.status_code == 500
    
    def test_rustchain_error_no_status(self):
        """Test RustChainError without status code"""
        error = RustChainError("Test error")
        assert str(error) == "Test error"
    
    def test_wallet_error(self):
        """Test WalletError"""
        error = WalletError("Wallet not found")
        assert isinstance(error, RustChainError)
    
    def test_transaction_error(self):
        """Test TransactionError"""
        error = TransactionError("Transaction failed")
        assert isinstance(error, RustChainError)
    
    def test_network_error(self):
        """Test NetworkError"""
        error = NetworkError("Connection failed")
        assert isinstance(error, RustChainError)
    
    def test_authentication_error(self):
        """Test AuthenticationError"""
        error = AuthenticationError("Invalid key")
        assert isinstance(error, RustChainError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
