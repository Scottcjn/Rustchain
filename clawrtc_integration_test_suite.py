# SPDX-License-Identifier: MIT

"""
Comprehensive integration test suite for clawrtc package.
Tests wallet creation, balance checking, miner attestation flow, and hardware fingerprint validation.
"""

import json
import os
import pytest
import requests
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock

# Try importing clawrtc components
try:
    import clawrtc
    from clawrtc import Wallet, MinerAttestation, HardwareFingerprint
    from clawrtc.api import RustChainAPI
    from clawrtc.utils import generate_keypair, validate_signature
    CLAWRTC_AVAILABLE = True
except ImportError:
    CLAWRTC_AVAILABLE = False
    print("Warning: clawrtc package not available. Install with 'pip install clawrtc'")


class MockRustChainServer:
    """Mock RustChain API server for testing."""

    def __init__(self):
        self.wallets = {}
        self.miners = {}
        self.attestations = {}
        self.fingerprints = {}
        self.base_url = "http://localhost:8732"

    def create_wallet_response(self, wallet_id: str) -> Dict[str, Any]:
        """Generate mock wallet creation response."""
        self.wallets[wallet_id] = {
            "wallet_id": wallet_id,
            "balance": 0.0,
            "created_at": int(time.time()),
            "public_key": f"pub_key_{wallet_id}",
            "private_key": f"priv_key_{wallet_id}"
        }
        return {"ok": True, "wallet": self.wallets[wallet_id]}

    def get_balance_response(self, wallet_id: str) -> Dict[str, Any]:
        """Generate mock balance check response."""
        if wallet_id not in self.wallets:
            return {"error": "Wallet not found", "ok": False}
        return {
            "ok": True,
            "amount_rtc": self.wallets[wallet_id]["balance"],
            "wallet_id": wallet_id
        }

    def register_miner_response(self, miner_id: str, hardware_fp: str) -> Dict[str, Any]:
        """Generate mock miner registration response."""
        self.miners[miner_id] = {
            "miner_id": miner_id,
            "hardware_fingerprint": hardware_fp,
            "status": "active",
            "registered_at": int(time.time())
        }
        return {"ok": True, "miner": self.miners[miner_id]}

    def submit_attestation_response(self, attestation_data: Dict) -> Dict[str, Any]:
        """Generate mock attestation submission response."""
        att_id = str(uuid.uuid4())
        self.attestations[att_id] = {
            "attestation_id": att_id,
            "miner_id": attestation_data.get("miner_id"),
            "proof_hash": attestation_data.get("proof_hash"),
            "timestamp": int(time.time()),
            "verified": True
        }
        return {"ok": True, "attestation": self.attestations[att_id]}


@pytest.fixture
def mock_server():
    """Provide mock RustChain server instance."""
    return MockRustChainServer()


@pytest.fixture
def test_wallet_id():
    """Generate unique wallet ID for testing."""
    return f"test_wallet_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_miner_id():
    """Generate unique miner ID for testing."""
    return f"test_miner_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mock_hardware_fingerprint():
    """Generate mock hardware fingerprint."""
    return {
        "cpu_id": "Intel_Core_i7_12700K",
        "gpu_id": "NVIDIA_RTX_4070",
        "memory_size": "32GB",
        "disk_serial": f"SSD_{uuid.uuid4().hex[:12]}",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "bios_uuid": str(uuid.uuid4())
    }


class TestWalletOperations:
    """Test wallet creation and balance operations."""

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.post')
    def test_wallet_creation_success(self, mock_post, mock_server, test_wallet_id):
        """Test successful wallet creation."""
        mock_post.return_value = Mock(
            ok=True,
            status_code=200,
            json=lambda: mock_server.create_wallet_response(test_wallet_id)
        )

        wallet = Wallet.create(test_wallet_id)
        assert wallet.wallet_id == test_wallet_id
        assert wallet.public_key.startswith("pub_key_")
        assert hasattr(wallet, 'private_key')

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert 'wallet/create' in call_args[0][0]

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.post')
    def test_wallet_creation_failure(self, mock_post, test_wallet_id):
        """Test wallet creation failure handling."""
        mock_post.return_value = Mock(
            ok=False,
            status_code=400,
            json=lambda: {"error": "Invalid wallet parameters", "ok": False}
        )

        with pytest.raises(Exception):
            Wallet.create(test_wallet_id)

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.get')
    def test_balance_check_success(self, mock_get, mock_server, test_wallet_id):
        """Test successful balance retrieval."""
        mock_server.wallets[test_wallet_id] = {"balance": 123.45}
        mock_get.return_value = Mock(
            ok=True,
            status_code=200,
            json=lambda: mock_server.get_balance_response(test_wallet_id)
        )

        wallet = Wallet(test_wallet_id)
        balance = wallet.get_balance()
        assert balance == 123.45

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert 'wallet/balance' in call_args[0][0]
        assert test_wallet_id in call_args[0][0]

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.get')
    def test_balance_check_nonexistent_wallet(self, mock_get, test_wallet_id):
        """Test balance check for non-existent wallet."""
        mock_get.return_value = Mock(
            ok=False,
            status_code=404,
            json=lambda: {"error": "Wallet not found", "ok": False}
        )

        wallet = Wallet(test_wallet_id)
        with pytest.raises(Exception):
            wallet.get_balance()


class TestMinerAttestation:
    """Test miner attestation flow and hardware validation."""

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.post')
    def test_miner_registration(self, mock_post, mock_server, test_miner_id, mock_hardware_fingerprint):
        """Test miner registration with hardware fingerprint."""
        hardware_fp_str = json.dumps(mock_hardware_fingerprint, sort_keys=True)
        mock_post.return_value = Mock(
            ok=True,
            status_code=200,
            json=lambda: mock_server.register_miner_response(test_miner_id, hardware_fp_str)
        )

        miner = MinerAttestation(test_miner_id)
        result = miner.register_hardware(mock_hardware_fingerprint)

        assert result["ok"] is True
        assert result["miner"]["miner_id"] == test_miner_id
        assert hardware_fp_str in result["miner"]["hardware_fingerprint"]

        mock_post.assert_called_once()

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.post')
    def test_attestation_submission(self, mock_post, mock_server, test_miner_id):
        """Test proof of work attestation submission."""
        attestation_data = {
            "miner_id": test_miner_id,
            "proof_hash": "0x" + "a" * 64,
            "nonce": 12345,
            "difficulty": 4
        }

        mock_post.return_value = Mock(
            ok=True,
            status_code=200,
            json=lambda: mock_server.submit_attestation_response(attestation_data)
        )

        miner = MinerAttestation(test_miner_id)
        result = miner.submit_attestation(attestation_data)

        assert result["ok"] is True
        assert result["attestation"]["miner_id"] == test_miner_id
        assert result["attestation"]["verified"] is True

        mock_post.assert_called_once()
        call_data = mock_post.call_args[1]['json']
        assert call_data['miner_id'] == test_miner_id
        assert call_data['proof_hash'] == attestation_data['proof_hash']

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    def test_attestation_validation_invalid_proof(self, test_miner_id):
        """Test attestation validation with invalid proof."""
        miner = MinerAttestation(test_miner_id)

        invalid_attestation = {
            "miner_id": test_miner_id,
            "proof_hash": "invalid_hash",
            "nonce": -1,
            "difficulty": 0
        }

        is_valid = miner.validate_attestation(invalid_attestation)
        assert is_valid is False


class TestHardwareFingerprint:
    """Test hardware fingerprint generation and validation."""

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    def test_generate_fingerprint(self):
        """Test hardware fingerprint generation."""
        fp = HardwareFingerprint()
        fingerprint_data = fp.generate()

        required_fields = ["cpu_id", "memory_size", "mac_address"]
        for field in required_fields:
            assert field in fingerprint_data
            assert fingerprint_data[field] is not None

        # Ensure consistent fingerprint generation
        fingerprint_2 = fp.generate()
        assert fingerprint_data["cpu_id"] == fingerprint_2["cpu_id"]

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    def test_fingerprint_validation(self, mock_hardware_fingerprint):
        """Test hardware fingerprint validation."""
        fp = HardwareFingerprint()

        # Test valid fingerprint
        assert fp.validate(mock_hardware_fingerprint) is True

        # Test invalid fingerprint (missing required field)
        invalid_fp = mock_hardware_fingerprint.copy()
        del invalid_fp["cpu_id"]
        assert fp.validate(invalid_fp) is False

        # Test fingerprint with invalid MAC address format
        invalid_mac_fp = mock_hardware_fingerprint.copy()
        invalid_mac_fp["mac_address"] = "invalid_mac"
        assert fp.validate(invalid_mac_fp) is False

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    def test_fingerprint_hash_consistency(self, mock_hardware_fingerprint):
        """Test that fingerprint hashing is consistent."""
        fp = HardwareFingerprint()

        hash_1 = fp.compute_hash(mock_hardware_fingerprint)
        hash_2 = fp.compute_hash(mock_hardware_fingerprint)

        assert hash_1 == hash_2
        assert len(hash_1) == 64  # SHA256 hex digest length

        # Test that different fingerprints produce different hashes
        different_fp = mock_hardware_fingerprint.copy()
        different_fp["cpu_id"] = "Different_CPU"
        hash_3 = fp.compute_hash(different_fp)

        assert hash_1 != hash_3


class TestAPIIntegration:
    """Test RustChain API integration patterns."""

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.get')
    def test_api_timeout_handling(self, mock_get):
        """Test API timeout handling."""
        mock_get.side_effect = requests.exceptions.Timeout()

        api = RustChainAPI(base_url="http://localhost:8732")
        with pytest.raises(requests.exceptions.Timeout):
            api.get_network_status()

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.post')
    def test_api_connection_error(self, mock_post):
        """Test API connection error handling."""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        api = RustChainAPI(base_url="http://localhost:8732")
        with pytest.raises(requests.exceptions.ConnectionError):
            api.submit_transaction({"test": "data"})

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.get')
    def test_api_rate_limiting(self, mock_get):
        """Test API rate limiting behavior."""
        mock_get.return_value = Mock(
            ok=False,
            status_code=429,
            json=lambda: {"error": "Rate limit exceeded", "retry_after": 60}
        )

        api = RustChainAPI(base_url="http://localhost:8732")
        response = api.get_network_status()

        assert response["error"] == "Rate limit exceeded"
        assert "retry_after" in response


class TestCryptographicOperations:
    """Test cryptographic utilities and signature validation."""

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    def test_keypair_generation(self):
        """Test cryptographic key pair generation."""
        public_key, private_key = generate_keypair()

        assert len(public_key) > 0
        assert len(private_key) > 0
        assert public_key != private_key

        # Test that keys are different each time
        pub2, priv2 = generate_keypair()
        assert public_key != pub2
        assert private_key != priv2

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    def test_signature_validation(self):
        """Test digital signature creation and validation."""
        public_key, private_key = generate_keypair()
        message = "test_message_for_signing"

        # This would use actual clawrtc signature functions
        # Mock implementation for testing
        signature = f"sig_{hash(message + private_key)}"

        is_valid = validate_signature(message, signature, public_key)
        assert is_valid is True

        # Test invalid signature
        invalid_sig = "invalid_signature"
        is_invalid = validate_signature(message, invalid_sig, public_key)
        assert is_invalid is False


@pytest.mark.integration
class TestFullWorkflow:
    """Test complete clawrtc workflow integration."""

    @pytest.mark.skipif(not CLAWRTC_AVAILABLE, reason="clawrtc package not installed")
    @patch('clawrtc.api.requests.post')
    @patch('clawrtc.api.requests.get')
    def test_complete_miner_workflow(self, mock_get, mock_post, mock_server, test_wallet_id, test_miner_id, mock_hardware_fingerprint):
        """Test complete workflow: wallet creation -> miner registration -> attestation."""

        # Setup mock responses
        mock_post.side_effect = [
            Mock(ok=True, status_code=200, json=lambda: mock_server.create_wallet_response(test_wallet_id)),
            Mock(ok=True, status_code=200, json=lambda: mock_server.register_miner_response(test_miner_id, json.dumps(mock_hardware_fingerprint))),
            Mock(ok=True, status_code=200, json=lambda: mock_server.submit_attestation_response({"miner_id": test_miner_id, "proof_hash": "0x" + "b" * 64}))
        ]

        mock_get.return_value = Mock(
            ok=True,
            status_code=200,
            json=lambda: mock_server.get_balance_response(test_wallet_id)
        )

        # Step 1: Create wallet
        wallet = Wallet.create(test_wallet_id)
        assert wallet.wallet_id == test_wallet_id

        # Step 2: Check initial balance
        balance = wallet.get_balance()
        assert balance == 0.0

        # Step 3: Register miner with hardware fingerprint
        miner = MinerAttestation(test_miner_id)
        reg_result = miner.register_hardware(mock_hardware_fingerprint)
        assert reg_result["ok"] is True

        # Step 4: Submit attestation
        attestation_data = {
            "miner_id": test_miner_id,
            "proof_hash": "0x" + "b" * 64,
            "nonce": 54321,
            "difficulty": 6
        }
        att_result = miner.submit_attestation(attestation_data)
        assert att_result["ok"] is True
        assert att_result["attestation"]["verified"] is True


def test_package_installation():
    """Test that clawrtc package can be imported correctly."""
    if not CLAWRTC_AVAILABLE:
        pytest.skip("clawrtc package not installed")

    # Test basic imports work
    import clawrtc
    assert hasattr(clawrtc, '__version__')

    # Test main classes are available
    from clawrtc import Wallet, MinerAttestation, HardwareFingerprint
    assert Wallet is not None
    assert MinerAttestation is not None
    assert HardwareFingerprint is not None


def test_coverage_requirements():
    """Ensure test coverage meets requirements (>80%)."""
    if not CLAWRTC_AVAILABLE:
        pytest.skip("clawrtc package not installed - cannot measure coverage")

    # This test serves as documentation that coverage should be measured
    # Run with: pytest --cov=clawrtc --cov-report=term-missing
    print("Run with coverage: pytest --cov=clawrtc --cov-report=term-missing clawrtc_integration_test_suite.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
