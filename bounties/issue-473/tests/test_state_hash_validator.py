#!/usr/bin/env python3
"""
Unit tests for State Hash Validator
"""

import unittest
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from state_hash_validator import (
    NodeState,
    ValidationResult,
    ComparisonReport,
    RustChainNodeClient,
    StateHashValidator,
    VERSION,
)


class TestNodeState(unittest.TestCase):
    """Tests for NodeState dataclass."""
    
    def test_compute_state_hash_deterministic(self):
        """State hash should be deterministic for same input."""
        node_state = NodeState(
            node_id="test-node",
            node_url="https://test.node.org",
            current_slot=1000,
            current_epoch=10,
            chain_tip_hash="abc123",
            miner_ids=["miner1", "miner2", "miner3"],
            epoch_numbers=[5, 6, 7, 8, 9, 10],
            total_supply=1_000_000_000,
            reported_state_hash="",
            timestamp=int(datetime.now().timestamp()),
        )
        
        hash1 = node_state.compute_state_hash()
        hash2 = node_state.compute_state_hash()
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 16)  # 16 hex characters
    
    def test_compute_state_hash_order_independent(self):
        """State hash should be independent of miner/epoch order."""
        node_state1 = NodeState(
            node_id="test-node",
            node_url="https://test.node.org",
            current_slot=1000,
            current_epoch=10,
            chain_tip_hash="abc123",
            miner_ids=["miner1", "miner2", "miner3"],
            epoch_numbers=[5, 6, 7, 8, 9, 10],
            total_supply=1_000_000_000,
            reported_state_hash="",
            timestamp=int(datetime.now().timestamp()),
        )
        
        node_state2 = NodeState(
            node_id="test-node",
            node_url="https://test.node.org",
            current_slot=1000,
            current_epoch=10,
            chain_tip_hash="abc123",
            miner_ids=["miner3", "miner1", "miner2"],  # Different order
            epoch_numbers=[10, 9, 8, 7, 6, 5],  # Different order
            total_supply=1_000_000_000,
            reported_state_hash="",
            timestamp=int(datetime.now().timestamp()),
        )
        
        self.assertEqual(node_state1.compute_state_hash(), node_state2.compute_state_hash())
    
    def test_compute_state_hash_changes_with_data(self):
        """State hash should change when data changes."""
        node_state1 = NodeState(
            node_id="test-node",
            node_url="https://test.node.org",
            current_slot=1000,
            current_epoch=10,
            chain_tip_hash="abc123",
            miner_ids=["miner1", "miner2"],
            epoch_numbers=[9, 10],
            total_supply=1_000_000_000,
            reported_state_hash="",
            timestamp=int(datetime.now().timestamp()),
        )
        
        node_state2 = NodeState(
            node_id="test-node",
            node_url="https://test.node.org",
            current_slot=1001,  # Different slot
            current_epoch=10,
            chain_tip_hash="abc123",
            miner_ids=["miner1", "miner2"],
            epoch_numbers=[9, 10],
            total_supply=1_000_000_000,
            reported_state_hash="",
            timestamp=int(datetime.now().timestamp()),
        )
        
        self.assertNotEqual(node_state1.compute_state_hash(), node_state2.compute_state_hash())


class TestValidationResult(unittest.TestCase):
    """Tests for ValidationResult dataclass."""
    
    def test_to_dict(self):
        """ValidationResult should convert to dict correctly."""
        result = ValidationResult(
            node_url="https://test.node.org",
            validation_time="2026-03-13T12:00:00Z",
            state_hash_match=True,
            reported_hash="abc123def456",
            computed_hash="abc123def456",
            epoch=100,
            slot=14400,
            miner_count=50,
            status="valid",
            response_time_ms=123.45,
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict["node_url"], "https://test.node.org")
        self.assertEqual(result_dict["state_hash_match"], True)
        self.assertEqual(result_dict["status"], "valid")
    
    def test_to_markdown(self):
        """ValidationResult should convert to markdown correctly."""
        result = ValidationResult(
            node_url="https://test.node.org",
            validation_time="2026-03-13T12:00:00Z",
            state_hash_match=True,
            reported_hash="abc123def456",
            computed_hash="abc123def456",
            epoch=100,
            slot=14400,
            miner_count=50,
            status="valid",
        )
        
        md = result.to_markdown()
        
        self.assertIn("https://test.node.org", md)
        self.assertIn("abc123def456", md)
        self.assertIn("valid", md.lower())


class TestComparisonReport(unittest.TestCase):
    """Tests for ComparisonReport dataclass."""
    
    def test_all_converged_true(self):
        """all_converged should be True when all nodes match."""
        result1 = ValidationResult(
            node_url="https://node1.org",
            validation_time="2026-03-13T12:00:00Z",
            state_hash_match=True,
            reported_hash="abc123",
            computed_hash="abc123",
            epoch=100,
            slot=14400,
            miner_count=50,
            status="valid",
        )
        
        result2 = ValidationResult(
            node_url="https://node2.org",
            validation_time="2026-03-13T12:00:00Z",
            state_hash_match=True,
            reported_hash="abc123",
            computed_hash="abc123",
            epoch=100,
            slot=14400,
            miner_count=50,
            status="valid",
        )
        
        report = ComparisonReport(
            timestamp="2026-03-13T12:00:00Z",
            nodes_compared=2,
            all_converged=True,
            consensus_hash="abc123",
            node_results={"node1": result1, "node2": result2},
            divergence_count=0,
            recommendations=["All nodes are in consensus"],
        )
        
        self.assertTrue(report.all_converged)
        self.assertEqual(report.divergence_count, 0)
    
    def test_to_dict(self):
        """ComparisonReport should convert to dict correctly."""
        result1 = ValidationResult(
            node_url="https://node1.org",
            validation_time="2026-03-13T12:00:00Z",
            state_hash_match=True,
            reported_hash="abc123",
            computed_hash="abc123",
            epoch=100,
            slot=14400,
            miner_count=50,
            status="valid",
        )
        
        report = ComparisonReport(
            timestamp="2026-03-13T12:00:00Z",
            nodes_compared=1,
            all_converged=True,
            consensus_hash="abc123",
            node_results={"node1": result1},
            divergence_count=0,
            recommendations=[],
        )
        
        report_dict = report.to_dict()
        
        self.assertEqual(report_dict["nodes_compared"], 1)
        self.assertIn("node1", report_dict["node_results"])


class TestRustChainNodeClient(unittest.TestCase):
    """Tests for RustChainNodeClient."""
    
    @patch('state_hash_validator.requests.Session')
    def test_health_check_success(self, mock_session_class):
        """Health check should return True on success."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        client = RustChainNodeClient("https://test.node.org")
        result = client.health_check()
        
        self.assertTrue(result)
    
    @patch('state_hash_validator.requests.Session')
    def test_health_check_failure(self, mock_session_class):
        """Health check should return False on failure."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = Exception("Connection error")
        
        client = RustChainNodeClient("https://test.node.org")
        result = client.health_check()
        
        self.assertFalse(result)
    
    @patch('state_hash_validator.requests.Session')
    def test_get_epoch_info(self, mock_session_class):
        """Should fetch epoch info correctly."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"epoch": 100, "slot": 14400}
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        client = RustChainNodeClient("https://test.node.org")
        result = client.get_epoch_info()
        
        self.assertEqual(result["epoch"], 100)
        self.assertEqual(result["slot"], 14400)


class TestStateHashValidator(unittest.TestCase):
    """Tests for StateHashValidator."""
    
    @patch('state_hash_validator.RustChainNodeClient')
    def test_validate_node_success(self, mock_client_class):
        """Should validate node successfully."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.health_check.return_value = True
        mock_client.get_state.return_value = NodeState(
            node_id="test-node",
            node_url="https://test.node.org",
            current_slot=1000,
            current_epoch=10,
            chain_tip_hash="abc123",
            miner_ids=["miner1", "miner2"],
            epoch_numbers=[9, 10],
            total_supply=1_000_000_000,
            reported_state_hash="",  # Will be computed
            timestamp=int(datetime.now().timestamp()),
        )
        
        validator = StateHashValidator()
        result = validator.validate_node("https://test.node.org")
        
        self.assertEqual(result.status, "valid")
        self.assertTrue(result.state_hash_match)
    
    @patch('state_hash_validator.RustChainNodeClient')
    def test_validate_node_unreachable(self, mock_client_class):
        """Should handle unreachable node."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.health_check.return_value = False
        
        validator = StateHashValidator()
        result = validator.validate_node("https://unreachable.node.org")
        
        self.assertEqual(result.status, "unreachable")
    
    @patch('state_hash_validator.StateHashValidator.validate_node')
    def test_compare_nodes_converged(self, mock_validate):
        """Should detect when nodes converge."""
        mock_validate.return_value = ValidationResult(
            node_url="https://node1.org",
            validation_time="2026-03-13T12:00:00Z",
            state_hash_match=True,
            reported_hash="abc123",
            computed_hash="abc123",
            epoch=100,
            slot=14400,
            miner_count=50,
            status="valid",
        )
        
        validator = StateHashValidator()
        report = validator.compare_nodes(["https://node1.org", "https://node2.org"])
        
        self.assertTrue(report.all_converged)
        self.assertEqual(report.divergence_count, 0)


class TestIntegration(unittest.TestCase):
    """Integration tests (require network access)."""
    
    @unittest.skipUnless(
        Path("/tmp/live_node_test.flag").exists(),
        "Skipping live node test - set flag to enable"
    )
    def test_validate_live_node(self):
        """Test validation against live RustChain node."""
        validator = StateHashValidator()
        result = validator.validate_node("https://rustchain.org")
        
        # Should complete without error
        self.assertIsNotNone(result)
        self.assertIn(result.status, ["valid", "unreachable", "error"])


if __name__ == "__main__":
    unittest.main()
