#!/usr/bin/env python3
"""
Tests for A2A Transaction Badge Verification Tool

Run with: python -m pytest tests/test_a2a_badges.py -v
Or: python tests/test_a2a_badges.py
"""

import unittest
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from a2a_badge_verifier import (
    A2ABadgeVerifier,
    BadgeTier,
    A2ATransaction,
    BadgeCriteria,
    WalletStats,
)


class TestBadgeTier(unittest.TestCase):
    """Test BadgeTier enum."""
    
    def test_tier_colors(self):
        """Test badge tier color values."""
        self.assertEqual(BadgeTier.MYTHIC.color, "#FF1493")
        self.assertEqual(BadgeTier.LEGENDARY.color, "#FFD700")
        self.assertEqual(BadgeTier.EPIC.color, "#9370DB")
        self.assertEqual(BadgeTier.RARE.color, "#4169E1")
        self.assertEqual(BadgeTier.UNCOMMON.color, "#32CD32")
        self.assertEqual(BadgeTier.COMMON.color, "#C0C0C0")
    
    def test_tier_stars(self):
        """Test badge tier star counts."""
        self.assertEqual(BadgeTier.MYTHIC.stars, 6)
        self.assertEqual(BadgeTier.LEGENDARY.stars, 5)
        self.assertEqual(BadgeTier.EPIC.stars, 4)
        self.assertEqual(BadgeTier.RARE.stars, 3)
        self.assertEqual(BadgeTier.UNCOMMON.stars, 2)
        self.assertEqual(BadgeTier.COMMON.stars, 1)


class TestA2ABadgeVerifier(unittest.TestCase):
    """Test A2ABadgeVerifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = A2ABadgeVerifier()
        self.test_wallet_1 = "0x1234567890abcdef1234567890abcdef12345678"
        self.test_wallet_2 = "0xabcdef1234567890abcdef1234567890abcdef12"
        self.test_wallet_3 = "0x9876543210fedcba9876543210fedcba98765432"
    
    def test_verify_transaction(self):
        """Test transaction verification."""
        tx = self.verifier.verify_transaction(
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            from_wallet=self.test_wallet_1,
            to_wallet=self.test_wallet_2,
            amount=100.5,
            timestamp=datetime.now(),
            protocol="x402",
            block_height=1000
        )
        
        self.assertEqual(tx.from_wallet, self.test_wallet_1)
        self.assertEqual(tx.to_wallet, self.test_wallet_2)
        self.assertEqual(tx.amount, 100.5)
        self.assertTrue(tx.verified)
    
    def test_verify_transaction_invalid_address(self):
        """Test transaction verification with invalid address."""
        with self.assertRaises(ValueError):
            self.verifier.verify_transaction(
                tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                from_wallet="invalid_address",
                to_wallet=self.test_wallet_2,
                amount=100.5,
                timestamp=datetime.now(),
            )
    
    def test_verify_transaction_invalid_amount(self):
        """Test transaction verification with invalid amount."""
        with self.assertRaises(ValueError):
            self.verifier.verify_transaction(
                tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                from_wallet=self.test_wallet_1,
                to_wallet=self.test_wallet_2,
                amount=-100,
                timestamp=datetime.now(),
            )
    
    def test_wallet_stats_update(self):
        """Test wallet statistics are updated correctly."""
        # Create multiple transactions
        for i in range(5):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'a' * 64}{i}",
                from_wallet=self.test_wallet_1,
                to_wallet=self.test_wallet_2 if i % 2 == 0 else self.test_wallet_3,
                amount=10.0,
                timestamp=datetime.now() - timedelta(days=i),
                protocol="x402",
                block_height=1000 + i
            )
        
        stats = self.verifier.get_wallet_stats(self.test_wallet_1)
        
        self.assertEqual(stats.total_transactions, 5)
        self.assertEqual(stats.total_volume, 50.0)
        self.assertEqual(stats.unique_counterparties, 2)
        self.assertIn("x402", stats.protocols_used)
    
    def test_counterparty_tracking(self):
        """Test unique counterparty tracking."""
        wallets = [
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            "0x3333333333333333333333333333333333333333",
        ]
        
        for i, wallet in enumerate(wallets):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'b' * 64}{i}",
                from_wallet=self.test_wallet_1,
                to_wallet=wallet,
                amount=10.0,
                timestamp=datetime.now(),
                protocol="x402",
                block_height=1000 + i
            )
        
        stats = self.verifier.get_wallet_stats(self.test_wallet_1)
        self.assertEqual(stats.unique_counterparties, 3)
    
    def test_protocol_tracking(self):
        """Test protocol tracking."""
        protocols = ["x402", "lightning", "base_native"]
        
        for i, protocol in enumerate(protocols):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'c' * 64}{i}",
                from_wallet=self.test_wallet_1,
                to_wallet=self.test_wallet_2,
                amount=10.0,
                timestamp=datetime.now(),
                protocol=protocol,
                block_height=1000 + i
            )
        
        stats = self.verifier.get_wallet_stats(self.test_wallet_1)
        self.assertEqual(len(stats.protocols_used), 3)
        self.assertIn("x402", stats.protocols_used)
        self.assertIn("lightning", stats.protocols_used)
        self.assertIn("base_native", stats.protocols_used)


class TestBadgeEligibility(unittest.TestCase):
    """Test badge eligibility checking."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = A2ABadgeVerifier()
        self.test_wallet = "0x1234567890abcdef1234567890abcdef12345678"
    
    def test_a2a_trader_eligibility(self):
        """Test A2A Trader badge eligibility (100+ transactions)."""
        # Create 100 transactions
        for i in range(100):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'d' * 64}{i}",
                from_wallet=self.test_wallet,
                to_wallet=f"0x{i:040x}",
                amount=10.0,
                timestamp=datetime.now(),
                protocol="x402",
                block_height=1000 + i
            )
        
        eligibility = self.verifier.check_badge_eligibility(self.test_wallet)
        trader_badge = next((b for b in eligibility if b.badge_id == "badge_a2a_trader"), None)
        
        self.assertIsNotNone(trader_badge)
        self.assertTrue(trader_badge.earned)
        self.assertEqual(trader_badge.current_progress, 100)
        self.assertEqual(trader_badge.threshold, 100)
    
    def test_a2a_connector_eligibility(self):
        """Test A2A Connector badge eligibility (10+ unique counterparties)."""
        # Create transactions with 10 unique wallets
        for i in range(10):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'e' * 64}{i}",
                from_wallet=self.test_wallet,
                to_wallet=f"0x{i:040x}",
                amount=10.0,
                timestamp=datetime.now(),
                protocol="x402",
                block_height=1000 + i
            )
        
        eligibility = self.verifier.check_badge_eligibility(self.test_wallet)
        connector_badge = next((b for b in eligibility if b.badge_id == "badge_a2a_connector"), None)
        
        self.assertIsNotNone(connector_badge)
        self.assertTrue(connector_badge.earned)
        self.assertEqual(connector_badge.current_progress, 10)
    
    def test_x402_native_eligibility(self):
        """Test x402 Native badge eligibility (x402 only)."""
        # Create 50 transactions using only x402
        for i in range(50):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'f' * 64}{i}",
                from_wallet=self.test_wallet,
                to_wallet=f"0x{i:040x}",
                amount=10.0,
                timestamp=datetime.now(),
                protocol="x402",
                block_height=1000 + i
            )
        
        eligibility = self.verifier.check_badge_eligibility(self.test_wallet)
        native_badge = next((b for b in eligibility if b.badge_id == "badge_x402_native"), None)
        
        self.assertIsNotNone(native_badge)
        self.assertTrue(native_badge.earned)
    
    def test_multi_protocol_eligibility(self):
        """Test Multi-Protocol badge eligibility (3+ protocols)."""
        protocols = ["x402", "lightning", "base_native"]
        
        for i, protocol in enumerate(protocols):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'g' * 64}{i}",
                from_wallet=self.test_wallet,
                to_wallet=f"0x{i:040x}",
                amount=10.0,
                timestamp=datetime.now(),
                protocol=protocol,
                block_height=1000 + i
            )
        
        eligibility = self.verifier.check_badge_eligibility(self.test_wallet)
        multi_badge = next((b for b in eligibility if b.badge_id == "badge_multi_protocol"), None)
        
        self.assertIsNotNone(multi_badge)
        self.assertTrue(multi_badge.earned)
        self.assertEqual(multi_badge.current_progress, 3)


class TestBadgeMetadataGeneration(unittest.TestCase):
    """Test badge metadata generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = A2ABadgeVerifier()
        self.test_wallet = "0x1234567890abcdef1234567890abcdef12345678"
    
    def test_generate_badge_metadata(self):
        """Test badge metadata generation."""
        metadata = self.verifier.generate_badge_metadata(
            badge_id="badge_a2a_pioneer",
            wallet_address=self.test_wallet,
            earned_timestamp=datetime.now()
        )
        
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["nft_id"], "badge_a2a_pioneer")
        self.assertEqual(metadata["owner"], self.test_wallet)
        self.assertIn("badge_hash", metadata)
        self.assertEqual(metadata["version"], "1.0")
        self.assertTrue(metadata["soulbound"])
    
    def test_generate_invalid_badge_metadata(self):
        """Test metadata generation for invalid badge."""
        metadata = self.verifier.generate_badge_metadata(
            badge_id="badge_nonexistent",
            wallet_address=self.test_wallet
        )
        
        self.assertIsNone(metadata)


class TestWalletReport(unittest.TestCase):
    """Test wallet report generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = A2ABadgeVerifier()
        self.test_wallet = "0x1234567890abcdef1234567890abcdef12345678"
    
    def test_export_wallet_report(self):
        """Test wallet report export."""
        # Create some transactions
        for i in range(15):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'h' * 64}{i}",
                from_wallet=self.test_wallet,
                to_wallet=f"0x{i:040x}",
                amount=10.0 + i,
                timestamp=datetime.now() - timedelta(days=i),
                protocol="x402",
                block_height=1000 + i
            )
        
        report = self.verifier.export_wallet_report(self.test_wallet)
        
        self.assertIn("wallet_address", report)
        self.assertIn("generated_at", report)
        self.assertIn("statistics", report)
        self.assertIn("earned_badges", report)
        self.assertIn("pending_badges", report)
        
        stats = report["statistics"]
        self.assertEqual(stats["total_transactions"], 15)
        self.assertEqual(stats["unique_counterparties"], 15)
    
    def test_export_nonexistent_wallet_report(self):
        """Test report for nonexistent wallet."""
        report = self.verifier.export_wallet_report("0x0000000000000000000000000000000000000000")
        
        self.assertIn("error", report)


class TestX402HeaderValidation(unittest.TestCase):
    """Test x402 header validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = A2ABadgeVerifier()
    
    def test_valid_x402_headers(self):
        """Test valid x402 headers."""
        headers = {
            "X-Payment-Amount": "100.5",
            "X-Payment-From": "0x1234567890abcdef1234567890abcdef12345678",
            "X-Payment-To": "0xabcdef1234567890abcdef1234567890abcdef12",
            "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        }
        
        is_valid, error = self.verifier.verify_x402_headers(headers)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_missing_header(self):
        """Test missing required header."""
        headers = {
            "X-Payment-Amount": "100.5",
            "X-Payment-From": "0x1234567890abcdef1234567890abcdef12345678",
            # Missing X-Payment-To
            "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        }
        
        is_valid, error = self.verifier.verify_x402_headers(headers)
        self.assertFalse(is_valid)
        self.assertIn("Missing required headers", error)
    
    def test_invalid_address_format(self):
        """Test invalid wallet address format."""
        headers = {
            "X-Payment-Amount": "100.5",
            "X-Payment-From": "invalid_address",
            "X-Payment-To": "0xabcdef1234567890abcdef1234567890abcdef12",
            "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        }
        
        is_valid, error = self.verifier.verify_x402_headers(headers)
        self.assertFalse(is_valid)
        self.assertIn("Invalid X-Payment-From", error)
    
    def test_invalid_amount(self):
        """Test invalid amount."""
        headers = {
            "X-Payment-Amount": "not_a_number",
            "X-Payment-From": "0x1234567890abcdef1234567890abcdef12345678",
            "X-Payment-To": "0xabcdef1234567890abcdef1234567890abcdef12",
            "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        }
        
        is_valid, error = self.verifier.verify_x402_headers(headers)
        self.assertFalse(is_valid)
        self.assertIn("Invalid payment amount", error)
    
    def test_negative_amount(self):
        """Test negative amount."""
        headers = {
            "X-Payment-Amount": "-100",
            "X-Payment-From": "0x1234567890abcdef1234567890abcdef12345678",
            "X-Payment-To": "0xabcdef1234567890abcdef1234567890abcdef12",
            "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        }
        
        is_valid, error = self.verifier.verify_x402_headers(headers)
        self.assertFalse(is_valid)
        self.assertIn("positive", error)


class TestProgressTracking(unittest.TestCase):
    """Test badge progress tracking."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = A2ABadgeVerifier()
        self.test_wallet = "0x1234567890abcdef1234567890abcdef12345678"
    
    def test_get_progress(self):
        """Test getting progress toward a badge."""
        # Create 50 transactions
        for i in range(50):
            self.verifier.verify_transaction(
                tx_hash=f"0x{'i' * 64}{i}",
                from_wallet=self.test_wallet,
                to_wallet=f"0x{i:040x}",
                amount=10.0,
                timestamp=datetime.now(),
                protocol="x402",
                block_height=1000 + i
            )
        
        progress = self.verifier.get_progress(self.test_wallet, "badge_a2a_trader")
        
        self.assertIsNotNone(progress)
        self.assertEqual(progress.current_progress, 50)
        self.assertEqual(progress.threshold, 100)
        self.assertFalse(progress.earned)
    
    def test_get_progress_nonexistent_badge(self):
        """Test getting progress for nonexistent badge."""
        progress = self.verifier.get_progress(self.test_wallet, "badge_nonexistent")
        self.assertIsNone(progress)


class TestListAvailableBadges(unittest.TestCase):
    """Test listing available badges."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = A2ABadgeVerifier()
    
    def test_list_badges(self):
        """Test listing all available badges."""
        badges = self.verifier.list_available_badges()
        
        self.assertGreater(len(badges), 0)
        
        # Check for expected badges
        badge_ids = [b["nft_id"] for b in badges]
        self.assertIn("badge_a2a_pioneer", badge_ids)
        self.assertIn("badge_a2a_trader", badge_ids)
        self.assertIn("badge_a2a_merchant", badge_ids)
        self.assertIn("badge_a2a_whale", badge_ids)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBadgeTier))
    suite.addTests(loader.loadTestsFromTestCase(TestA2ABadgeVerifier))
    suite.addTests(loader.loadTestsFromTestCase(TestBadgeEligibility))
    suite.addTests(loader.loadTestsFromTestCase(TestBadgeMetadataGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestWalletReport))
    suite.addTests(loader.loadTestsFromTestCase(TestX402HeaderValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestProgressTracking))
    suite.addTests(loader.loadTestsFromTestCase(TestListAvailableBadges))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
