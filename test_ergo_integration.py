#!/usr/bin/env python3
"""
Unit Tests for Ergo Integration (Phase 2)
==========================================

Tests for:
- ergo_token_issuance.py - Token creation
- ergo_bridge.py - Bridge operations

Run:
    python test_ergo_integration.py -v
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import time

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

from ergo_token_issuance import (
    ErgoTokenIssuer,
    ErgoNodeClient,
    TokenMetadata,
    TokenInfo,
    MIN_BOX_VALUE,
    TOKEN_CREATION_FEE
)

from ergo_bridge import (
    RustChainErgoBridge,
    RustChainClient,
    ErgoBridgeClient,
    LockEvent,
    BurnEvent,
    BridgeStatus,
    BridgeStats,
    MIN_LOCK_AMOUNT,
    MAX_LOCK_AMOUNT,
    BRIDGE_FEE_PERCENT,
    CONFIRMATIONS_REQUIRED
)


class TestTokenMetadata:
    """Tests for TokenMetadata class"""
    
    def test_basic_metadata(self):
        """Test basic token metadata creation"""
        metadata = TokenMetadata(
            name="RustChain Token",
            description="Native token",
            symbol="RTC",
            decimals=9
        )
        
        assert metadata.name == "RustChain Token"
        assert metadata.symbol == "RTC"
        assert metadata.decimals == 9
    
    def test_to_registers(self):
        """Test metadata to EIP-4 registers conversion"""
        metadata = TokenMetadata(
            name="Test Token",
            description="Test",
            symbol="TTK",
            decimals=2
        )
        
        registers = metadata.to_registers()
        
        assert 4 in registers
        assert 5 in registers
        assert 6 in registers
        assert 7 in registers
        assert registers[4] == '"Test Token"'
        assert registers[6] == '"TTK"'
        assert registers[7] == "2"
    
    def test_metadata_with_icon(self):
        """Test metadata with optional icon (box42)"""
        metadata = TokenMetadata(
            name="Token",
            description="Desc",
            symbol="TKN",
            box42="box_id_123"
        )
        
        registers = metadata.to_registers()
        assert 8 in registers
        assert registers[8] == '"box_id_123"'


class TestErgoNodeClient:
    """Tests for ErgoNodeClient class"""
    
    @patch('ergo_token_issuance.requests.Session')
    def test_get_balance(self, mock_session):
        """Test balance retrieval"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"balance": "1000000000"}
        mock_response.raise_for_status.return_value = None
        mock_session.return_value.get.return_value = mock_response
        
        client = ErgoNodeClient("api_key", "http://localhost:9053")
        balance = client.get_balance("test_address")
        
        assert balance == 1000000000
    
    @patch('ergo_token_issuance.requests.Session')
    def test_get_balance_error(self, mock_session):
        """Test balance retrieval with error"""
        mock_session.return_value.get.side_effect = Exception("Connection failed")
        
        client = ErgoNodeClient("api_key", "http://localhost:9053")
        balance = client.get_balance("test_address")
        
        assert balance == 0  # Should return 0 on error
    
    @patch('ergo_token_issuance.requests.Session')
    def test_get_unspent_boxes(self, mock_session):
        """Test getting unspent boxes"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"boxId": "box1", "value": "10000000"},
                {"boxId": "box2", "value": "20000000"}
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_session.return_value.get.return_value = mock_response
        
        client = ErgoNodeClient("api_key", "http://localhost:9053")
        boxes = client.get_unspent_boxes("test_address")
        
        assert len(boxes) == 2
        assert boxes[0]["boxId"] == "box1"


class TestErgoTokenIssuer:
    """Tests for ErgoTokenIssuer class"""
    
    @patch('ergo_token_issuance.ErgoNodeClient')
    def test_create_rtc_token(self, mock_client_class):
        """Test RTC token creation"""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_unspent_boxes.return_value = [
            {"boxId": "box1", "value": "20000000"}
        ]
        mock_client.get_current_height.return_value = 1000
        
        issuer = ErgoTokenIssuer("api_key", "http://localhost:9053", "issuer_addr")
        
        # Mock internal methods
        issuer._select_boxes = lambda boxes, min_val: boxes
        issuer._build_token_creation_tx = lambda **kwargs: {"tx": "data"}
        issuer._sign_transaction = lambda tx: tx
        issuer._address_to_tree = lambda addr: "tree"
        issuer._extract_token_id = lambda tx: "token_123"
        
        mock_client.send_transaction.return_value = "tx_123"
        
        token_id = issuer.create_rtc_token(initial_supply=1000000 * 10**9)
        
        assert token_id == "token_123"
        assert issuer.token_info is not None
        assert issuer.token_info.symbol == "RTC"
    
    @patch('ergo_token_issuance.ErgoNodeClient')
    def test_insufficient_funds(self, mock_client_class):
        """Test token creation with insufficient funds"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_unspent_boxes.return_value = []
        
        issuer = ErgoTokenIssuer("api_key", "http://localhost:9053", "issuer_addr")
        
        with pytest.raises(ValueError, match="No unspent boxes"):
            issuer.create_rtc_token()
    
    @patch('ergo_token_issuance.ErgoNodeClient')
    def test_select_boxes(self, mock_client_class):
        """Test box selection algorithm"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        issuer = ErgoTokenIssuer("api_key", "http://localhost:9053", "issuer_addr")
        
        boxes = [
            {"boxId": "box1", "value": "5000000"},
            {"boxId": "box2", "value": "10000000"},
            {"boxId": "box3", "value": "15000000"}
        ]
        
        selected = issuer._select_boxes(boxes, 12000000)
        
        # Should select largest boxes first (box3 = 15M is enough for 12M)
        assert len(selected) >= 1
        assert sum(int(box["value"]) for box in selected) >= 12000000


class TestBridgeOperations:
    """Tests for RustChainErgoBridge class"""
    
    @patch('ergo_bridge.RustChainClient')
    @patch('ergo_bridge.ErgoBridgeClient')
    def test_lock_rtc(self, mock_ergo_client, mock_rustchain_client):
        """Test locking RTC on RustChain"""
        # Setup mocks
        mock_rustchain = MagicMock()
        mock_rustchain_client.return_value = mock_rustchain
        mock_rustchain.get_block_height.return_value = 1000
        mock_rustchain.send_transaction.return_value = "rustchain_tx_123"
        
        mock_ergo = MagicMock()
        mock_ergo_client.return_value = mock_ergo
        
        bridge = RustChainErgoBridge(
            rustchain_node="http://localhost:8080",
            ergo_node="http://localhost:9053",
            ergo_api_key="api_key",
            multisig_addresses=["addr1", "addr2", "addr3"],
            rtc_token_id="token_123"
        )
        
        # Mock internal method
        bridge._create_lock_tx = lambda **kwargs: {"tx": "data"}
        
        tx_id = bridge.lock_rtc(
            amount=100 * 10**9,  # 100 RTC
            ergo_recipient="ergo_addr",
            sender="rustchain_addr"
        )
        
        assert tx_id == "rustchain_tx_123"
        assert bridge.stats.lock_count == 1
        assert bridge.stats.total_locked == 100 * 10**9
    
    @patch('ergo_bridge.RustChainClient')
    @patch('ergo_bridge.ErgoBridgeClient')
    def test_lock_minimum_amount(self, mock_ergo_client, mock_rustchain_client):
        """Test lock with minimum amount"""
        mock_rustchain = MagicMock()
        mock_rustchain_client.return_value = mock_rustchain
        
        mock_ergo = MagicMock()
        mock_ergo_client.return_value = mock_ergo
        
        bridge = RustChainErgoBridge(
            rustchain_node="http://localhost:8080",
            ergo_node="http://localhost:9053",
            ergo_api_key="api_key",
            multisig_addresses=["addr1"],
            rtc_token_id="token_123"
        )
        
        # Should fail with amount below minimum
        with pytest.raises(ValueError, match="Minimum lock amount"):
            bridge.lock_rtc(
                amount=5 * 10**9,  # 5 RTC (below minimum)
                ergo_recipient="ergo_addr",
                sender="rustchain_addr"
            )
    
    @patch('ergo_bridge.RustChainClient')
    @patch('ergo_bridge.ErgoBridgeClient')
    def test_bridge_fee_calculation(self, mock_ergo_client, mock_rustchain_client):
        """Test bridge fee calculation"""
        mock_rustchain = MagicMock()
        mock_rustchain_client.return_value = mock_rustchain
        mock_rustchain.get_block_height.return_value = 1000
        mock_rustchain.send_transaction.return_value = "tx_123"
        
        mock_ergo = MagicMock()
        mock_ergo_client.return_value = mock_ergo
        
        bridge = RustChainErgoBridge(
            rustchain_node="http://localhost:8080",
            ergo_node="http://localhost:9053",
            ergo_api_key="api_key",
            multisig_addresses=["addr1"],
            rtc_token_id="token_123"
        )
        
        bridge._create_lock_tx = lambda **kwargs: {"tx": "data"}
        
        amount = 100 * 10**9
        bridge.lock_rtc(amount=amount, ergo_recipient="ergo_addr", sender="rustchain_addr")
        
        expected_fee = int(amount * BRIDGE_FEE_PERCENT)
        assert bridge.stats.total_fees == expected_fee
    
    @patch('ergo_bridge.RustChainClient')
    @patch('ergo_bridge.ErgoBridgeClient')
    def test_complete_lock_with_confirmations(self, mock_ergo_client, mock_rustchain_client):
        """Test completing lock after confirmations"""
        mock_rustchain = MagicMock()
        mock_rustchain_client.return_value = mock_rustchain
        mock_rustchain.get_block_height.return_value = 1000
        mock_rustchain.send_transaction.return_value = "rustchain_tx"
        mock_rustchain.get_confirmations.return_value = CONFIRMATIONS_REQUIRED
        
        mock_ergo = MagicMock()
        mock_ergo_client.return_value = mock_ergo
        mock_ergo.get_block_height.return_value = 2000
        
        bridge = RustChainErgoBridge(
            rustchain_node="http://localhost:8080",
            ergo_node="http://localhost:9053",
            ergo_api_key="api_key",
            multisig_addresses=["addr1"],
            rtc_token_id="token_123"
        )
        
        bridge._create_lock_tx = lambda **kwargs: {"tx": "data"}
        bridge._create_mint_tx = lambda **kwargs: {"tx": "data"}
        bridge._send_ergo_transaction = lambda tx: "ergo_tx"
        
        # First lock
        tx_id = bridge.lock_rtc(
            amount=100 * 10**9,
            ergo_recipient="ergo_addr",
            sender="rustchain_addr"
        )
        
        # Get event ID
        event_id = list(bridge.lock_events.keys())[0]
        
        # Complete lock
        ergo_tx_id = bridge.complete_lock(event_id)
        
        assert ergo_tx_id == "ergo_tx"
        assert bridge.lock_events[event_id].status == BridgeStatus.COMPLETED
        assert bridge.stats.pending_locks == 0
    
    @patch('ergo_bridge.RustChainClient')
    @patch('ergo_bridge.ErgoBridgeClient')
    def test_insufficient_confirmations(self, mock_ergo_client, mock_rustchain_client):
        """Test lock completion with insufficient confirmations"""
        mock_rustchain = MagicMock()
        mock_rustchain_client.return_value = mock_rustchain
        mock_rustchain.get_block_height.return_value = 1000
        mock_rustchain.send_transaction.return_value = "rustchain_tx"
        mock_rustchain.get_confirmations.return_value = 2  # Below required
        
        mock_ergo = MagicMock()
        mock_ergo_client.return_value = mock_ergo
        
        bridge = RustChainErgoBridge(
            rustchain_node="http://localhost:8080",
            ergo_node="http://localhost:9053",
            ergo_api_key="api_key",
            multisig_addresses=["addr1"],
            rtc_token_id="token_123"
        )
        
        bridge._create_lock_tx = lambda **kwargs: {"tx": "data"}
        
        # Lock
        bridge.lock_rtc(
            amount=100 * 10**9,
            ergo_recipient="ergo_addr",
            sender="rustchain_addr"
        )
        
        event_id = list(bridge.lock_events.keys())[0]
        
        # Should fail with insufficient confirmations
        with pytest.raises(ValueError, match="Insufficient confirmations"):
            bridge.complete_lock(event_id)
    
    @patch('ergo_bridge.RustChainClient')
    @patch('ergo_bridge.ErgoBridgeClient')
    def test_burn_ertc(self, mock_ergo_client, mock_rustchain_client):
        """Test burning eRTC on Ergo"""
        mock_rustchain = MagicMock()
        mock_rustchain_client.return_value = mock_rustchain
        
        mock_ergo = MagicMock()
        mock_ergo_client.return_value = mock_ergo
        mock_ergo.get_block_height.return_value = 2000
        mock_ergo.send_transaction = lambda tx: "ergo_tx"
        
        bridge = RustChainErgoBridge(
            rustchain_node="http://localhost:8080",
            ergo_node="http://localhost:9053",
            ergo_api_key="api_key",
            multisig_addresses=["addr1"],
            rtc_token_id="token_123"
        )
        
        bridge._create_burn_tx = lambda **kwargs: {"tx": "data"}
        bridge._send_ergo_transaction = lambda tx: "ergo_tx_123"
        
        tx_id = bridge.burn_ertc(
            amount=50 * 10**9,
            rustchain_recipient="rustchain_addr",
            sender="ergo_addr"
        )
        
        assert tx_id == "ergo_tx_123"
        assert bridge.stats.unlock_count == 1
        assert bridge.stats.pending_unlocks == 1


class TestBridgeStats:
    """Tests for bridge statistics"""
    
    @patch('ergo_bridge.RustChainClient')
    @patch('ergo_bridge.ErgoBridgeClient')
    def test_stats_tracking(self, mock_ergo_client, mock_rustchain_client):
        """Test bridge statistics tracking"""
        mock_rustchain = MagicMock()
        mock_rustchain_client.return_value = mock_rustchain
        mock_rustchain.get_block_height.return_value = 1000
        mock_rustchain.send_transaction.return_value = "tx"
        
        mock_ergo = MagicMock()
        mock_ergo_client.return_value = mock_ergo
        
        bridge = RustChainErgoBridge(
            rustchain_node="http://localhost:8080",
            ergo_node="http://localhost:9053",
            ergo_api_key="api_key",
            multisig_addresses=["addr1"],
            rtc_token_id="token_123"
        )
        
        bridge._create_lock_tx = lambda **kwargs: {"tx": "data"}
        
        # Perform multiple locks
        for i in range(3):
            bridge.lock_rtc(
                amount=100 * 10**9,
                ergo_recipient=f"ergo_addr_{i}",
                sender=f"rustchain_addr_{i}"
            )
        
        stats = bridge.get_stats()
        
        assert stats.lock_count == 3
        assert stats.total_locked == 300 * 10**9
        assert stats.pending_locks == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
