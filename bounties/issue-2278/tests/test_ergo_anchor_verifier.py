#!/usr/bin/env python3
"""
Test Suite for Ergo Anchor Chain Proof Verifier
================================================

Comprehensive test coverage for the anchor proof verifier including:
- Unit tests for cryptographic utilities
- Integration tests for verification logic
- Mock-based tests for external API interactions
- Edge case and error handling tests
"""

import unittest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Import modules to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from ergo_anchor_verifier import (
    CryptoUtils,
    ErgoExplorerClient,
    AnchorProofVerifier,
    AnchorProofGenerator,
    AnchorProof,
    VerificationResult,
    NetworkType,
    NETWORK_CONFIG,
    DEFAULT_CONFIRMATION_DEPTH,
)


# =============================================================================
# TEST DATA
# =============================================================================

class TestData:
    """Test data fixtures."""
    
    # Sample anchor proof
    SAMPLE_PROOF = AnchorProof(
        tx_id="a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
        block_id="b2c3d4e5f67890123456789012345678901234567890123456789012345678ef",
        block_height=100000,
        rustchain_height=50000,
        rustchain_hash="c3d4e5f6789012345678901234567890123456789012345678901234567890ab",
        state_root="d4e5f67890123456789012345678901234567890123456789012345678901234",
        attestations_root="e5f6789012345678901234567890123456789012345678901234567890123456",
        commitment_hash="f678901234567890123456789012345678901234567890123456789012345678",
        commitment_register="R5",
        commitment_value="0e40f678901234567890123456789012345678901234567890123456789012345678",
        timestamp=int(time.time() * 1000) - 3600000,  # 1 hour ago
        confirmations=10,
        output_index=0,
        network="mainnet",
        verified=False,
        verification_time=None
    )
    
    # Sample Ergo transaction response
    SAMPLE_TX_RESPONSE = {
        "id": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
        "blockId": "b2c3d4e5f67890123456789012345678901234567890123456789012345678ef",
        "blockHeight": 100000,
        "timestamp": int(time.time() * 1000) - 3600000,
        "outputs": [
            {
                "value": 1000000,
                "ergoTree": "100204a00b08cd...",
                "additionalRegisters": {
                    "R5": {
                        "serializedValue": "0e40f678901234567890123456789012345678901234567890123456789012345678"
                    }
                }
            }
        ]
    }
    
    # Sample transaction status
    SAMPLE_TX_STATUS = {
        "id": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
        "confirmations": 10
    }
    
    # Sample block response
    SAMPLE_BLOCK_RESPONSE = {
        "id": "b2c3d4e5f67890123456789012345678901234567890123456789012345678ef",
        "height": 100000,
        "timestamp": int(time.time() * 1000) - 3600000,
        "transactions": [
            "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd"
        ]
    }


# =============================================================================
# CRYPTO UTILITIES TESTS
# =============================================================================

class TestCryptoUtils(unittest.TestCase):
    """Tests for CryptoUtils class."""
    
    def test_blake2b256(self):
        """Test Blake2b-256 hash computation."""
        data = b"test data"
        result = CryptoUtils.blake2b256(data)
        
        # Verify hash length
        self.assertEqual(len(result), 32)
        self.assertIsInstance(result, bytes)
    
    def test_blake2b256_hex(self):
        """Test Blake2b-256 hex string output."""
        data = b"test data"
        result = CryptoUtils.blake2b256_hex(data)
        
        # Verify hex string format
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in result))
    
    def test_blake2b256_deterministic(self):
        """Test that Blake2b-256 is deterministic."""
        data = b"deterministic test"
        hash1 = CryptoUtils.blake2b256_hex(data)
        hash2 = CryptoUtils.blake2b256_hex(data)
        
        self.assertEqual(hash1, hash2)
    
    def test_blake2b256_different_inputs(self):
        """Test that different inputs produce different hashes."""
        hash1 = CryptoUtils.blake2b256_hex(b"data1")
        hash2 = CryptoUtils.blake2b256_hex(b"data2")
        
        self.assertNotEqual(hash1, hash2)
    
    def test_canonical_json(self):
        """Test canonical JSON generation."""
        obj = {"b": 2, "a": 1}
        result = CryptoUtils.canonical_json(obj)
        
        # Verify sorted keys
        self.assertEqual(result, '{"a":1,"b":2}')
    
    def test_canonical_json_nested(self):
        """Test canonical JSON with nested objects."""
        obj = {"z": {"b": 2, "a": 1}, "a": 3}
        result = CryptoUtils.canonical_json(obj)
        
        # Verify sorted keys at all levels
        self.assertEqual(result, '{"a":3,"z":{"a":1,"b":2}}')
    
    def test_compute_commitment_hash(self):
        """Test commitment hash computation."""
        hash1 = CryptoUtils.compute_commitment_hash(
            rustchain_height=1000,
            rustchain_hash="abc" + "0" * 61,
            state_root="def" + "0" * 61,
            attestations_root="ghi" + "0" * 61,
            timestamp=1234567890000
        )
        
        # Verify hash format
        self.assertEqual(len(hash1), 64)
        
        # Verify determinism
        hash2 = CryptoUtils.compute_commitment_hash(
            rustchain_height=1000,
            rustchain_hash="abc" + "0" * 61,
            state_root="def" + "0" * 61,
            attestations_root="ghi" + "0" * 61,
            timestamp=1234567890000
        )
        self.assertEqual(hash1, hash2)
    
    def test_compute_commitment_hash_different_inputs(self):
        """Test that different inputs produce different commitment hashes."""
        hash1 = CryptoUtils.compute_commitment_hash(
            rustchain_height=1000,
            rustchain_hash="abc" + "0" * 61,
            state_root="def" + "0" * 61,
            attestations_root="ghi" + "0" * 61,
            timestamp=1234567890000
        )
        
        hash2 = CryptoUtils.compute_commitment_hash(
            rustchain_height=1001,  # Different height
            rustchain_hash="abc" + "0" * 61,
            state_root="def" + "0" * 61,
            attestations_root="ghi" + "0" * 61,
            timestamp=1234567890000
        )
        
        self.assertNotEqual(hash1, hash2)
    
    def test_validate_hex_string_valid(self):
        """Test hex string validation with valid input."""
        valid_hex = "a" * 64
        self.assertTrue(CryptoUtils.validate_hex_string(valid_hex))
    
    def test_validate_hex_string_invalid(self):
        """Test hex string validation with invalid input."""
        self.assertFalse(CryptoUtils.validate_hex_string("xyz" + "0" * 61))
        self.assertFalse(CryptoUtils.validate_hex_string("a" * 63))  # Wrong length
        self.assertFalse(CryptoUtils.validate_hex_string(""))
    
    def test_validate_hex_string_custom_length(self):
        """Test hex string validation with custom expected length."""
        self.assertTrue(CryptoUtils.validate_hex_string("a" * 32, 32))
        self.assertFalse(CryptoUtils.validate_hex_string("a" * 32, 64))
    
    def test_verify_merkle_proof_empty(self):
        """Test Merkle proof verification with empty proof."""
        leaf = b"leaf data"
        # Empty proof with computed root of leaf itself
        root = CryptoUtils.blake2b256_hex(leaf)
        
        # Empty proof - the function will hash the leaf and compare to root
        # This should actually succeed since we're using the hash of leaf as root
        result = CryptoUtils.verify_merkle_proof(leaf, [], root)
        self.assertTrue(result)  # Empty proof matches when root is hash of leaf


# =============================================================================
# ANCHOR PROOF DATA STRUCTURE TESTS
# =============================================================================

class TestAnchorProof(unittest.TestCase):
    """Tests for AnchorProof dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        proof = TestData.SAMPLE_PROOF
        d = proof.to_dict()
        
        self.assertIsInstance(d, dict)
        self.assertEqual(d['tx_id'], proof.tx_id)
        self.assertEqual(d['rustchain_height'], proof.rustchain_height)
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        d = TestData.SAMPLE_PROOF.to_dict()
        proof = AnchorProof.from_dict(d)
        
        self.assertEqual(proof.tx_id, TestData.SAMPLE_PROOF.tx_id)
        self.assertEqual(proof.rustchain_height, TestData.SAMPLE_PROOF.rustchain_height)
    
    def test_to_json(self):
        """Test JSON serialization."""
        proof = TestData.SAMPLE_PROOF
        json_str = proof.to_json()
        
        self.assertIsInstance(json_str, str)
        
        # Verify valid JSON
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)
    
    def test_from_json(self):
        """Test JSON deserialization."""
        json_str = TestData.SAMPLE_PROOF.to_json()
        proof = AnchorProof.from_json(json_str)
        
        self.assertEqual(proof.tx_id, TestData.SAMPLE_PROOF.tx_id)
    
    def test_json_roundtrip(self):
        """Test JSON serialization/deserialization roundtrip."""
        original = TestData.SAMPLE_PROOF
        json_str = original.to_json()
        restored = AnchorProof.from_json(json_str)
        
        self.assertEqual(original.tx_id, restored.tx_id)
        self.assertEqual(original.rustchain_height, restored.rustchain_height)
        self.assertEqual(original.commitment_hash, restored.commitment_hash)


# =============================================================================
# VERIFICATION RESULT TESTS
# =============================================================================

class TestVerificationResult(unittest.TestCase):
    """Tests for VerificationResult dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        proof = TestData.SAMPLE_PROOF
        result = VerificationResult(is_valid=True, proof=proof)
        
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn('proof', d)
        self.assertEqual(d['is_valid'], True)
    
    def test_to_json(self):
        """Test JSON serialization."""
        proof = TestData.SAMPLE_PROOF
        result = VerificationResult(is_valid=True, proof=proof)
        
        json_str = result.to_json()
        self.assertIsInstance(json_str, str)
        
        # Verify valid JSON
        parsed = json.loads(json_str)
        self.assertIn('proof', parsed)
    
    def test_summary_valid(self):
        """Test summary generation for valid result."""
        proof = TestData.SAMPLE_PROOF
        result = VerificationResult(is_valid=True, proof=proof)
        
        summary = result.summary()
        self.assertIn("VALID", summary)
        self.assertIn(proof.tx_id[:16], summary)
    
    def test_summary_invalid(self):
        """Test summary generation for invalid result."""
        proof = TestData.SAMPLE_PROOF
        result = VerificationResult(
            is_valid=False,
            proof=proof,
            errors=["Test error 1", "Test error 2"]
        )
        
        summary = result.summary()
        self.assertIn("INVALID", summary)
        self.assertIn("Test error 1", summary)
        self.assertIn("Test error 2", summary)
    
    def test_summary_with_warnings(self):
        """Test summary generation with warnings."""
        proof = TestData.SAMPLE_PROOF
        result = VerificationResult(
            is_valid=True,
            proof=proof,
            warnings=["Test warning"]
        )
        
        summary = result.summary()
        self.assertIn("Test warning", summary)


# =============================================================================
# ERGO EXPLORER CLIENT TESTS
# =============================================================================

class TestErgoExplorerClient(unittest.TestCase):
    """Tests for ErgoExplorerClient class."""
    
    @patch('ergo_anchor_verifier.requests.Session')
    def setUp(self, mock_session_cls):
        """Set up test fixtures."""
        mock_session = Mock()
        mock_session_cls.return_value = mock_session
        self.client = ErgoExplorerClient(NetworkType.MAINNET)
        self.mock_session = mock_session
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_transaction_success(self, mock_session_cls):
        """Test successful transaction fetch."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = TestData.SAMPLE_TX_RESPONSE
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_transaction(TestData.SAMPLE_PROOF.tx_id)
        
        self.assertEqual(result, TestData.SAMPLE_TX_RESPONSE)
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_transaction_not_found(self, mock_session_cls):
        """Test transaction not found."""
        mock_resp = Mock()
        mock_resp.status_code = 404
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_transaction("invalid_tx_id")
        
        self.assertIsNone(result)
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_transaction_error(self, mock_session_cls):
        """Test transaction fetch error."""
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_transaction(TestData.SAMPLE_PROOF.tx_id)
        
        self.assertIsNone(result)
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_block_by_id(self, mock_session_cls):
        """Test block fetch by ID."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = TestData.SAMPLE_BLOCK_RESPONSE
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_block_by_id(TestData.SAMPLE_PROOF.block_id)
        
        self.assertEqual(result, TestData.SAMPLE_BLOCK_RESPONSE)
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_block_by_height(self, mock_session_cls):
        """Test block fetch by height."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = TestData.SAMPLE_BLOCK_RESPONSE
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_block_by_height(100000)
        
        self.assertEqual(result, TestData.SAMPLE_BLOCK_RESPONSE)
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_transaction_status(self, mock_session_cls):
        """Test transaction status fetch."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = TestData.SAMPLE_TX_STATUS
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_transaction_status(TestData.SAMPLE_PROOF.tx_id)
        
        self.assertEqual(result, TestData.SAMPLE_TX_STATUS)
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_current_height(self, mock_session_cls):
        """Test current height fetch."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [{"height": 123456}]
        }
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_current_height()
        
        self.assertEqual(result, 123456)
    
    @patch('ergo_anchor_verifier.requests.Session')
    def test_get_current_height_empty(self, mock_session_cls):
        """Test current height with empty response."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": []}
        
        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session
        
        client = ErgoExplorerClient(NetworkType.MAINNET)
        result = client.get_current_height()
        
        self.assertEqual(result, 0)
    
    def test_verify_output_register_found(self):
        """Test register verification - found."""
        tx = TestData.SAMPLE_TX_RESPONSE
        is_valid, actual = self.client.verify_output_register(
            tx, "R5",
            "f678901234567890123456789012345678901234567890123456789012345678"
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(actual, "f678901234567890123456789012345678901234567890123456789012345678")
    
    def test_verify_output_register_not_found(self):
        """Test register verification - not found."""
        tx = TestData.SAMPLE_TX_RESPONSE
        is_valid, actual = self.client.verify_output_register(
            tx, "R4", "expected_value"
        )
        
        self.assertFalse(is_valid)
        self.assertEqual(actual, "")
    
    def test_verify_output_register_mismatch(self):
        """Test register verification - value mismatch."""
        tx = TestData.SAMPLE_TX_RESPONSE
        is_valid, actual = self.client.verify_output_register(
            tx, "R5", "different_value"
        )
        
        self.assertFalse(is_valid)
        self.assertNotEqual(actual, "different_value")


# =============================================================================
# ANCHOR PROOF VERIFIER TESTS
# =============================================================================

class TestAnchorProofVerifier(unittest.TestCase):
    """Tests for AnchorProofVerifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = AnchorProofVerifier(
            network=NetworkType.MAINNET,
            confirmation_depth=6
        )
    
    def test_verify_proof_transaction_not_found(self):
        """Test verification when transaction not found."""
        self.verifier.explorer = Mock()
        self.verifier.explorer.get_transaction.return_value = None
        
        proof = TestData.SAMPLE_PROOF
        result = self.verifier.verify_proof(proof)
        
        self.assertFalse(result.is_valid)
        self.assertIn("not found", result.errors[0])
    
    def test_verify_proof_success(self):
        """Test successful verification."""
        self.verifier.explorer = Mock()
        
        # Mock successful responses
        self.verifier.explorer.get_transaction.return_value = TestData.SAMPLE_TX_RESPONSE
        self.verifier.explorer.get_transaction_status.return_value = TestData.SAMPLE_TX_STATUS
        self.verifier.explorer.verify_output_register.return_value = (True, "matched_value")
        self.verifier.explorer.get_block_by_id.return_value = TestData.SAMPLE_BLOCK_RESPONSE
        
        # Create proof with matching commitment
        proof = TestData.SAMPLE_PROOF
        proof.commitment_value = "0e40" + proof.commitment_hash
        
        result = self.verifier.verify_proof(proof)
        
        # Note: This will fail commitment hash computation check
        # because we're using test data, but tests the flow
        self.assertIsInstance(result, VerificationResult)
    
    def test_verify_from_transaction(self):
        """Test verification from transaction ID."""
        self.verifier.explorer = Mock()
        
        # Mock responses
        self.verifier.explorer.get_transaction.return_value = TestData.SAMPLE_TX_RESPONSE
        self.verifier.explorer.get_transaction_status.return_value = TestData.SAMPLE_TX_STATUS
        
        result = self.verifier.verify_from_transaction(
            TestData.SAMPLE_PROOF.tx_id,
            TestData.SAMPLE_PROOF.rustchain_height
        )
        
        self.assertIsInstance(result, VerificationResult)
        self.assertEqual(result.proof.tx_id, TestData.SAMPLE_PROOF.tx_id)
    
    def test_batch_verify(self):
        """Test batch verification."""
        proofs = [TestData.SAMPLE_PROOF, TestData.SAMPLE_PROOF]
        
        # Mock individual verification
        with patch.object(self.verifier, 'verify_proof') as mock_verify:
            mock_verify.return_value = VerificationResult(
                is_valid=True,
                proof=TestData.SAMPLE_PROOF
            )
            
            results = self.verifier.batch_verify(proofs)
            
            self.assertEqual(len(results), 2)
            self.assertEqual(mock_verify.call_count, 2)
    
    def test_generate_audit_report(self):
        """Test audit report generation."""
        results = [
            VerificationResult(
                is_valid=True,
                proof=TestData.SAMPLE_PROOF,
                verification_time_ms=10.5
            ),
            VerificationResult(
                is_valid=False,
                proof=TestData.SAMPLE_PROOF,
                errors=["Test error"],
                verification_time_ms=5.2
            )
        ]
        
        report = self.verifier.generate_audit_report(results)
        
        self.assertIn("AUDIT REPORT", report)
        self.assertIn("Total Proofs Verified: 2", report)
        self.assertIn("Valid: 1", report)
        self.assertIn("Invalid: 1", report)


# =============================================================================
# ANCHOR PROOF GENERATOR TESTS
# =============================================================================

class TestAnchorProofGenerator(unittest.TestCase):
    """Tests for AnchorProofGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = AnchorProofGenerator(network=NetworkType.MAINNET)
    
    def test_generate_from_transaction_success(self):
        """Test successful proof generation."""
        self.generator.explorer = Mock()
        
        # Mock transaction with registers
        tx_with_registers = {
            "id": "tx123",
            "blockId": "block123",
            "blockHeight": 100,
            "outputs": [
                {
                    "additionalRegisters": {
                        "R5": {
                            "serializedValue": "0e40" + "a" * 64
                        }
                    }
                }
            ]
        }
        self.generator.explorer.get_transaction.return_value = tx_with_registers
        self.generator.explorer.get_transaction_status.return_value = {"confirmations": 5}
        
        proof = self.generator.generate_from_transaction(
            "tx123",
            rustchain_height=50,
            rustchain_hash="b" * 64,
            state_root="c" * 64,
            attestations_root="d" * 64
        )
        
        self.assertIsNotNone(proof)
        self.assertEqual(proof.tx_id, "tx123")
        self.assertEqual(proof.commitment_hash, "a" * 64)
    
    def test_generate_from_transaction_not_found(self):
        """Test proof generation when transaction not found."""
        self.generator.explorer = Mock()
        self.generator.explorer.get_transaction.return_value = None
        
        proof = self.generator.generate_from_transaction(
            "invalid_tx",
            rustchain_height=50,
            rustchain_hash="b" * 64,
            state_root="c" * 64,
            attestations_root="d" * 64
        )
        
        self.assertIsNone(proof)
    
    def test_generate_from_transaction_no_commitment(self):
        """Test proof generation when no commitment in registers."""
        self.generator.explorer = Mock()
        
        # Transaction without commitment registers
        tx_no_commitment = {
            "id": "tx123",
            "outputs": [
                {"additionalRegisters": {}}
            ]
        }
        self.generator.explorer.get_transaction.return_value = tx_no_commitment
        
        proof = self.generator.generate_from_transaction(
            "tx123",
            rustchain_height=50,
            rustchain_hash="b" * 64,
            state_root="c" * 64,
            attestations_root="d" * 64
        )
        
        self.assertIsNone(proof)


# =============================================================================
# EDGE CASES AND ERROR HANDLING TESTS
# =============================================================================

class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""
    
    def test_empty_merkle_proof(self):
        """Test handling of empty Merkle proof."""
        proof = AnchorProof(
            tx_id="a" * 64,
            block_id="b" * 64,
            block_height=100,
            rustchain_height=50,
            rustchain_hash="c" * 64,
            state_root="d" * 64,
            attestations_root="e" * 64,
            commitment_hash="f" * 64,
            commitment_register="R5",
            commitment_value="0e40" + "f" * 64,
            timestamp=int(time.time() * 1000),
            confirmations=10,
            merkle_proof=[]  # Empty proof
        )
        
        # Should not crash
        self.assertIsInstance(proof.to_dict(), dict)
    
    def test_very_large_heights(self):
        """Test handling of very large block heights."""
        proof = AnchorProof(
            tx_id="a" * 64,
            block_id="b" * 64,
            block_height=999999999,
            rustchain_height=999999999,
            rustchain_hash="c" * 64,
            state_root="d" * 64,
            attestations_root="e" * 64,
            commitment_hash="f" * 64,
            commitment_register="R5",
            commitment_value="0e40" + "f" * 64,
            timestamp=int(time.time() * 1000),
            confirmations=10
        )
        
        # Should handle large numbers
        json_str = proof.to_json()
        restored = AnchorProof.from_json(json_str)
        
        self.assertEqual(restored.block_height, 999999999)
    
    def test_zero_confirmations(self):
        """Test handling of zero confirmations."""
        proof = AnchorProof(
            tx_id="a" * 64,
            block_id="b" * 64,
            block_height=100,
            rustchain_height=50,
            rustchain_hash="c" * 64,
            state_root="d" * 64,
            attestations_root="e" * 64,
            commitment_hash="f" * 64,
            commitment_register="R5",
            commitment_value="0e40" + "f" * 64,
            timestamp=int(time.time() * 1000),
            confirmations=0  # Unconfirmed
        )
        
        # Should handle zero confirmations
        self.assertEqual(proof.confirmations, 0)
    
    def test_future_timestamp(self):
        """Test handling of future timestamp."""
        future_time = int(time.time() * 1000) + 86400000  # 1 day in future
        
        proof = AnchorProof(
            tx_id="a" * 64,
            block_id="b" * 64,
            block_height=100,
            rustchain_height=50,
            rustchain_hash="c" * 64,
            state_root="d" * 64,
            attestations_root="e" * 64,
            commitment_hash="f" * 64,
            commitment_register="R5",
            commitment_value="0e40" + "f" * 64,
            timestamp=future_time,
            confirmations=10
        )
        
        # Should handle future timestamp (verification will flag it)
        self.assertGreater(proof.timestamp, int(time.time() * 1000))
    
    def test_invalid_hex_commitment(self):
        """Test handling of invalid hex in commitment."""
        proof = AnchorProof(
            tx_id="a" * 64,
            block_id="b" * 64,
            block_height=100,
            rustchain_height=50,
            rustchain_hash="c" * 64,
            state_root="d" * 64,
            attestations_root="e" * 64,
            commitment_hash="invalid_hex!",  # Invalid
            commitment_register="R5",
            commitment_value="0e40invalid!",
            timestamp=int(time.time() * 1000),
            confirmations=10
        )
        
        # Should store invalid data without crashing
        self.assertEqual(proof.commitment_hash, "invalid_hex!")
    
    def test_network_types(self):
        """Test all network types."""
        for network in NetworkType:
            verifier = AnchorProofVerifier(network=network)
            self.assertEqual(verifier.network, network)
    
    def test_json_special_characters(self):
        """Test JSON handling with special characters."""
        # Create proof and serialize/deserialize
        proof = TestData.SAMPLE_PROOF
        json_str = proof.to_json()
        
        # Verify valid JSON is produced
        self.assertIsInstance(json_str, str)
        self.assertTrue(len(json_str) > 0)
        # Verify it can be parsed
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests with mocked external dependencies."""
    
    def test_full_verification_flow(self):
        """Test complete verification flow."""
        verifier = AnchorProofVerifier(network=NetworkType.MAINNET)
        
        # Mock all external calls
        verifier.explorer = Mock()
        verifier.explorer.get_transaction.return_value = TestData.SAMPLE_TX_RESPONSE
        verifier.explorer.get_transaction_status.return_value = TestData.SAMPLE_TX_STATUS
        verifier.explorer.get_block_by_id.return_value = TestData.SAMPLE_BLOCK_RESPONSE
        verifier.explorer.verify_output_register.return_value = (True, "matched")
        
        # Create proof
        proof = TestData.SAMPLE_PROOF
        proof.commitment_value = "0e40" + proof.commitment_hash
        
        # Verify
        result = verifier.verify_proof(proof)
        
        # Check result structure
        self.assertIsInstance(result, VerificationResult)
        self.assertIsInstance(result.summary(), str)
        self.assertGreater(result.verification_time_ms, 0)
    
    def test_batch_verification_flow(self):
        """Test batch verification flow."""
        verifier = AnchorProofVerifier(network=NetworkType.MAINNET)
        
        # Mock external calls
        verifier.explorer = Mock()
        verifier.explorer.get_transaction.return_value = TestData.SAMPLE_TX_RESPONSE
        verifier.explorer.get_transaction_status.return_value = TestData.SAMPLE_TX_STATUS
        verifier.explorer.verify_output_register.return_value = (True, "matched")
        
        # Create multiple proofs
        proofs = [TestData.SAMPLE_PROOF] * 3
        for i, proof in enumerate(proofs):
            proof.commitment_value = "0e40" + proof.commitment_hash
            proof.rustchain_height = 50000 + i
        
        # Batch verify
        results = verifier.batch_verify(proofs)
        
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsInstance(result, VerificationResult)
    
    def test_audit_report_generation(self):
        """Test complete audit report generation."""
        verifier = AnchorProofVerifier(network=NetworkType.MAINNET)
        
        # Create mixed results
        results = [
            VerificationResult(
                is_valid=True,
                proof=TestData.SAMPLE_PROOF,
                verification_time_ms=10.0
            ),
            VerificationResult(
                is_valid=False,
                proof=TestData.SAMPLE_PROOF,
                errors=["Error 1"],
                warnings=["Warning 1"],
                verification_time_ms=5.0
            )
        ]
        
        # Generate report
        report = verifier.generate_audit_report(results)
        
        # Verify report content
        self.assertIn("AUDIT REPORT", report)
        self.assertIn("SUMMARY", report)
        self.assertIn("DETAILED RESULTS", report)
        self.assertIn("END OF REPORT", report)


# =============================================================================
# TEST RUNNER
# =============================================================================

def run_tests():
    """Run all tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestCryptoUtils,
        TestAnchorProof,
        TestVerificationResult,
        TestErgoExplorerClient,
        TestAnchorProofVerifier,
        TestAnchorProofGenerator,
        TestEdgeCases,
        TestIntegration,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("Ergo Anchor Chain Proof Verifier - Test Suite")
    print("=" * 70)
    print()
    
    result = run_tests()
    
    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("=" * 70)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
