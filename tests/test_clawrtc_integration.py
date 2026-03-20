# SPDX-License-Identifier: MIT
"""
Integration tests for clawrtc package core modules.
Tests wallet operations, balance queries, attestation flows, and hardware fingerprinting.
"""
import json
import os
import sqlite3
import tempfile
import unittest.mock
from unittest.mock import MagicMock, patch

import pytest

try:
    import clawrtc
    from clawrtc.wallet import Wallet
    from clawrtc.miner import MinerAttestation
    from clawrtc.hardware import HardwareFingerprint
    from clawrtc.balance import BalanceChecker
    from clawrtc.client import RustChainClient
except ImportError:
    pytest.skip("clawrtc not installed", allow_module_level=True)


class TestWalletOperations:

    def test_wallet_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet_path = os.path.join(tmpdir, "test_wallet.db")
            wallet = Wallet.create(wallet_path, passphrase="test123")

            assert wallet is not None
            assert os.path.exists(wallet_path)
            assert wallet.address is not None
            assert len(wallet.address) == 42  # Standard ETH address length

    def test_wallet_load_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet_path = os.path.join(tmpdir, "existing_wallet.db")

            # Create wallet first
            original = Wallet.create(wallet_path, passphrase="secret")
            original_addr = original.address

            # Load existing wallet
            loaded = Wallet.load(wallet_path, passphrase="secret")

            assert loaded.address == original_addr

    def test_wallet_wrong_passphrase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet_path = os.path.join(tmpdir, "protected_wallet.db")

            Wallet.create(wallet_path, passphrase="correct")

            with pytest.raises(Exception):  # Should raise auth error
                Wallet.load(wallet_path, passphrase="wrong")

    def test_wallet_sign_transaction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet_path = os.path.join(tmpdir, "signer_wallet.db")
            wallet = Wallet.create(wallet_path, passphrase="sign123")

            tx_data = {
                "to": "0x742d35Cc6634C0532925a3b8D8C0532925a3b8D8",
                "value": 100,
                "gas": 21000,
                "gasPrice": 20000000000
            }

            signature = wallet.sign_transaction(tx_data)

            assert signature is not None
            assert isinstance(signature, (str, bytes, dict))


class TestBalanceOperations:

    @patch('clawrtc.client.requests.get')
    def test_balance_query_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "amount_rtc": 250.75,
            "miner_id": "test_miner_123",
            "last_update": "2024-01-15T10:30:00Z"
        }
        mock_get.return_value = mock_response

        checker = BalanceChecker(node_url="http://localhost:8332")
        balance = checker.get_balance("test_miner_123")

        assert balance == 250.75
        mock_get.assert_called_once()

    @patch('clawrtc.client.requests.get')
    def test_balance_query_network_error(self, mock_get):
        mock_get.side_effect = ConnectionError("Network unreachable")

        checker = BalanceChecker(node_url="http://unreachable:8332")

        with pytest.raises(ConnectionError):
            checker.get_balance("test_miner")

    @patch('clawrtc.client.requests.get')
    def test_balance_query_invalid_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Miner not found"}
        mock_get.return_value = mock_response

        checker = BalanceChecker()
        balance = checker.get_balance("nonexistent_miner")

        assert balance == 0.0


class TestMinerAttestation:

    def test_attestation_creation(self):
        attestation = MinerAttestation(
            miner_id="miner_node_001",
            hardware_hash="abc123def456",
            stake_amount=50.0
        )

        assert attestation.miner_id == "miner_node_001"
        assert attestation.hardware_hash == "abc123def456"
        assert attestation.stake_amount == 50.0
        assert attestation.timestamp is not None

    @patch('clawrtc.miner.requests.post')
    def test_attestation_submission(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "attestation_id": "att_789xyz",
            "status": "verified",
            "valid_until": "2024-12-31T23:59:59Z"
        }
        mock_post.return_value = mock_response

        attestation = MinerAttestation("miner_042", "hw_hash_042", 75.5)
        result = attestation.submit()

        assert result["status"] == "verified"
        assert result["attestation_id"] == "att_789xyz"
        mock_post.assert_called_once()

    @patch('clawrtc.miner.requests.post')
    def test_attestation_submission_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Invalid stake amount"}
        mock_post.return_value = mock_response

        attestation = MinerAttestation("bad_miner", "bad_hash", -10.0)

        with pytest.raises(Exception):
            attestation.submit()

    def test_attestation_validation(self):
        # Valid attestation
        valid_att = MinerAttestation("valid_miner", "valid_hw_hash", 100.0)
        assert valid_att.is_valid()

        # Invalid attestations
        invalid_stake = MinerAttestation("miner", "hash", 0.0)
        assert not invalid_stake.is_valid()

        invalid_hash = MinerAttestation("miner", "", 50.0)
        assert not invalid_hash.is_valid()


class TestHardwareFingerprinting:

    def test_hardware_fingerprint_generation(self):
        fingerprint = HardwareFingerprint.generate()

        assert fingerprint is not None
        assert isinstance(fingerprint, str)
        assert len(fingerprint) >= 32  # Should be substantial hash

    @patch('clawrtc.hardware.platform.processor')
    @patch('clawrtc.hardware.platform.system')
    def test_hardware_components_detection(self, mock_system, mock_processor):
        mock_system.return_value = "Linux"
        mock_processor.return_value = "Intel64 Family 6 Model 142 Stepping 12, GenuineIntel"

        components = HardwareFingerprint.get_components()

        assert "cpu" in components
        assert "system" in components
        assert components["system"] == "Linux"

    def test_hardware_fingerprint_consistency(self):
        # Multiple calls should return same fingerprint
        fp1 = HardwareFingerprint.generate()
        fp2 = HardwareFingerprint.generate()

        assert fp1 == fp2

    @patch('clawrtc.hardware.uuid.getnode')
    def test_mac_address_component(self, mock_getnode):
        mock_getnode.return_value = 123456789012

        components = HardwareFingerprint.get_components()

        assert "mac" in components
        mock_getnode.assert_called_once()


class TestRustChainClient:

    def test_client_initialization(self):
        client = RustChainClient(node_url="http://localhost:8332")

        assert client.node_url == "http://localhost:8332"
        assert client.timeout == 30  # Default timeout

    @patch('clawrtc.client.requests.get')
    def test_node_info_query(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "version": "2.2.1",
            "block_height": 12345,
            "network": "mainnet",
            "sync_status": "synced"
        }
        mock_get.return_value = mock_response

        client = RustChainClient()
        info = client.get_node_info()

        assert info["version"] == "2.2.1"
        assert info["block_height"] == 12345
        assert info["sync_status"] == "synced"

    @patch('clawrtc.client.requests.post')
    def test_transaction_broadcast(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "tx_hash": "0xabc123def456789",
            "status": "pending",
            "gas_used": 21000
        }
        mock_post.return_value = mock_response

        client = RustChainClient()
        tx_data = {"from": "0x123", "to": "0x456", "value": 100}
        result = client.broadcast_transaction(tx_data)

        assert result["tx_hash"] == "0xabc123def456789"
        assert result["status"] == "pending"
        mock_post.assert_called_once()

    def test_client_custom_timeout(self):
        client = RustChainClient(timeout=60)

        assert client.timeout == 60


class TestEdgeCases:

    def test_empty_wallet_path(self):
        with pytest.raises(ValueError):
            Wallet.create("", passphrase="test")

    def test_none_passphrase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet_path = os.path.join(tmpdir, "none_pass.db")

            with pytest.raises(ValueError):
                Wallet.create(wallet_path, passphrase=None)

    @patch('clawrtc.client.requests.get')
    def test_malformed_json_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Invalid response format"
        mock_get.return_value = mock_response

        client = RustChainClient()

        with pytest.raises(Exception):
            client.get_node_info()

    def test_negative_stake_attestation(self):
        with pytest.raises(ValueError):
            MinerAttestation("miner", "hash", -50.0)

    def test_extremely_large_stake(self):
        # Should handle large numbers gracefully
        attestation = MinerAttestation("big_miner", "big_hash", 1e18)

        assert attestation.stake_amount == 1e18
        assert attestation.is_valid()

    @patch('clawrtc.hardware.platform.system')
    def test_unknown_system_detection(self, mock_system):
        mock_system.side_effect = Exception("Unknown system")

        # Should handle gracefully without crashing
        components = HardwareFingerprint.get_components()

        assert isinstance(components, dict)
        # Should still have some fallback components


class TestIntegrationFlows:

    @patch('clawrtc.client.requests.post')
    @patch('clawrtc.client.requests.get')
    def test_full_miner_registration_flow(self, mock_get, mock_post):
        # Mock balance check
        mock_get.return_value = MagicMock(
            ok=True,
            json=lambda: {"amount_rtc": 0.0}
        )

        # Mock attestation submission
        mock_post.return_value = MagicMock(
            ok=True,
            json=lambda: {"attestation_id": "att_integration", "status": "verified"}
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            wallet_path = os.path.join(tmpdir, "integration_wallet.db")

            # Create wallet
            wallet = Wallet.create(wallet_path, passphrase="integration")

            # Generate hardware fingerprint
            hw_hash = HardwareFingerprint.generate()

            # Check initial balance
            checker = BalanceChecker()
            initial_balance = checker.get_balance(wallet.address)
            assert initial_balance == 0.0

            # Create and submit attestation
            attestation = MinerAttestation(wallet.address, hw_hash, 100.0)
            result = attestation.submit()

            assert result["status"] == "verified"
            assert result["attestation_id"] == "att_integration"

    def test_wallet_persistence_across_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet_path = os.path.join(tmpdir, "persistent_wallet.db")
            passphrase = "persist123"

            # Session 1: Create wallet
            wallet1 = Wallet.create(wallet_path, passphrase=passphrase)
            addr1 = wallet1.address

            # Simulate app restart - load existing wallet
            wallet2 = Wallet.load(wallet_path, passphrase=passphrase)
            addr2 = wallet2.address

            assert addr1 == addr2
            assert os.path.exists(wallet_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=clawrtc", "--cov-report=term-missing"])
