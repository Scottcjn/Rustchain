#!/usr/bin/env python3
"""
Tests for RustChain Airdrop V2 (RIP-305)

Tests cover:
- Eligibility checks (GitHub, wallet, anti-Sybil)
- Tier determination
- Claim processing
- Bridge operations
- Allocation tracking
- Database persistence
"""
import json
import gc
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import airdrop module
from airdrop_v2 import (
    AirdropV2,
    EligibilityTier,
    EligibilityResult,
    ClaimRecord,
    BridgeLock,
    Chain,
    AIRDROP_SCHEMA,
    TOTAL_SOLANA_ALLOCATION,
    TOTAL_BASE_ALLOCATION,
    init_airdrop_routes,
)

try:
    from flask import Flask
except ImportError:
    Flask = None


class TestEligibilityTier(unittest.TestCase):
    """Test eligibility tier definitions."""

    def test_tier_rewards(self):
        """Verify tier reward amounts."""
        self.assertEqual(EligibilityTier.STARGAZER.reward_uwrtc, 25 * 1_000_000)
        self.assertEqual(EligibilityTier.CONTRIBUTOR.reward_uwrtc, 50 * 1_000_000)
        self.assertEqual(EligibilityTier.BUILDER.reward_uwrtc, 100 * 1_000_000)
        self.assertEqual(EligibilityTier.SECURITY.reward_uwrtc, 150 * 1_000_000)
        self.assertEqual(EligibilityTier.CORE.reward_uwrtc, 200 * 1_000_000)
        self.assertEqual(EligibilityTier.MINER.reward_uwrtc, 100 * 1_000_000)

    def test_tier_descriptions(self):
        """Verify tier descriptions."""
        self.assertEqual(EligibilityTier.STARGAZER.description, "10+ repos starred")
        self.assertEqual(EligibilityTier.CONTRIBUTOR.description, "1+ merged PR")
        self.assertEqual(EligibilityTier.BUILDER.description, "3+ merged PRs")
        self.assertEqual(EligibilityTier.CORE.description, "5+ merged PRs / Star King")


class TestAirdropV2Database(unittest.TestCase):
    """Test database initialization and schema."""

    def setUp(self):
        """Create in-memory database for each test."""
        self.airdrop = AirdropV2(db_path=":memory:")

    def test_database_initialization(self):
        """Verify database tables are created."""
        conn = self.airdrop._get_conn()
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        self.assertIn("airdrop_claims", tables)
        self.assertIn("bridge_locks", tables)
        self.assertIn("sybil_cache", tables)
        self.assertIn("airdrop_allocation", tables)

        conn.close()

    def test_initial_allocation(self):
        """Verify initial allocation is set correctly."""
        conn = self.airdrop._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT chain, total_uwrtc FROM airdrop_allocation")
        rows = cursor.fetchall()
        conn.close()

        allocation = {row[0]: row[1] for row in rows}
        self.assertEqual(allocation["solana"], TOTAL_SOLANA_ALLOCATION)
        self.assertEqual(allocation["base"], TOTAL_BASE_ALLOCATION)


class TestEligibilityChecks(unittest.TestCase):
    """Test eligibility check logic."""

    def setUp(self):
        """Create airdrop instance with temp database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)

    def tearDown(self):
        """Clean up temp database."""
        os.unlink(self.temp_db.name)

    @patch("requests.get")
    def test_eligibility_with_mock_github(self, mock_get):
        """Test eligibility check with mocked GitHub API."""
        # Mock GitHub user response
        mock_user = Mock()
        mock_user.status_code = 200
        mock_user.json.return_value = {
            "login": "testuser",
            "created_at": "2020-01-01T00:00:00Z",
            "starred_url": "https://api.github.com/users/testuser/starred{/owner}{/repo}",
        }
        mock_user.headers = {}

        # Mock starred repos response
        mock_stars = Mock()
        mock_stars.status_code = 200
        mock_stars.headers = {
            "Link": '<https://api.github.com/user/starred?page=5>; rel="last"'
        }
        mock_stars.json.return_value = []

        # Mock contributions response
        mock_contrib = Mock()
        mock_contrib.status_code = 200
        mock_contrib.json.return_value = {"total_count": 3}

        # Setup mock chain
        def side_effect(url, *args, **kwargs):
            if "users/testuser" in url and "starred" not in url:
                return mock_user
            elif "starred" in url:
                return mock_stars
            elif "search/commits" in url:
                return mock_contrib
            return Mock(status_code=404)

        mock_get.side_effect = side_effect

        # Test eligibility (skip anti-Sybil wallet checks, but use GitHub for tier)
        result = self.airdrop.check_eligibility(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            skip_antisybil=True,  # Skip wallet checks, but still determine tier from GitHub
        )

        # With mock returning 3 PRs, user should be eligible for Builder tier
        self.assertTrue(result.eligible)
        self.assertEqual(result.tier, "builder")  # 3 PRs = Builder tier
        self.assertEqual(result.reward_uwrtc, 100 * 1_000_000)

    def test_invalid_chain(self):
        """Test eligibility check with invalid chain."""
        result = self.airdrop.check_eligibility(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="ethereum",  # Invalid
            skip_antisybil=True,
        )

        self.assertFalse(result.eligible)
        self.assertIn("Unsupported chain", result.reason)

    def test_duplicate_claim_prevention(self):
        """Test that duplicate claims are prevented."""
        # Create a claim
        success, _, _ = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )
        self.assertTrue(success)

        # Try to claim again
        result = self.airdrop.check_eligibility(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            skip_antisybil=True,
        )

        self.assertFalse(result.eligible)
        self.assertIn("Already claimed", result.reason)

    def test_same_github_cannot_claim_with_different_wallet(self):
        """A GitHub account cannot bypass claim limits by changing wallets."""
        success, _, _ = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1111111111111111111111111111111111111111",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )
        self.assertTrue(success)

        result = self.airdrop.check_eligibility(
            github_username="testuser",
            wallet_address="RTC2222222222222222222222222222222222222222",
            chain="base",
            skip_antisybil=True,
        )

        self.assertFalse(result.eligible)
        self.assertIn("Already claimed", result.reason)

    def test_same_wallet_cannot_claim_with_different_github(self):
        """A wallet cannot bypass claim limits by changing GitHub accounts."""
        wallet = "RTC3333333333333333333333333333333333333333"
        success, _, _ = self.airdrop.claim_airdrop(
            github_username="firstuser",
            wallet_address=wallet,
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )
        self.assertTrue(success)

        result = self.airdrop.check_eligibility(
            github_username="seconduser",
            wallet_address=wallet,
            chain="base",
            skip_antisybil=True,
        )

        self.assertFalse(result.eligible)
        self.assertIn("Already claimed", result.reason)


class TestClaimProcessing(unittest.TestCase):
    """Test claim creation and finalization."""

    def setUp(self):
        """Create airdrop instance with temp database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)

    def tearDown(self):
        """Clean up temp database."""
        os.unlink(self.temp_db.name)

    def test_create_claim(self):
        """Test claim creation."""
        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )

        self.assertTrue(success)
        self.assertIsNotNone(claim)
        self.assertEqual(claim.github_username, "testuser")
        self.assertEqual(claim.tier, "contributor")
        self.assertEqual(claim.amount_uwrtc, 50 * 1_000_000)
        self.assertEqual(claim.status, "pending")

    def test_finalize_claim(self):
        """Test claim finalization with tx signature."""
        # Create claim
        success, _, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )
        self.assertTrue(success)

        # Finalize with tx signature
        success, message = self.airdrop.finalize_claim(
            claim_id=claim.claim_id,
            tx_signature="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        )

        self.assertTrue(success)

        # Verify claim status updated
        updated_claim = self.airdrop.get_claim(claim.claim_id)
        self.assertEqual(updated_claim.status, "completed")
        self.assertEqual(
            updated_claim.tx_signature,
            "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        )

    def test_invalid_tier_mismatch(self):
        """Test claim with invalid tier name."""
        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="invalid_tier",  # Invalid tier name
            skip_antisybil=True,
        )

        # Should fail because tier name is invalid
        self.assertFalse(success)
        self.assertIn("Invalid tier", message)


class TestBridgeOperations(unittest.TestCase):
    """Test bridge lock operations."""

    def setUp(self):
        """Create airdrop instance with temp database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)

    def tearDown(self):
        """Clean up temp database."""
        os.unlink(self.temp_db.name)

    def test_create_bridge_lock(self):
        """Test bridge lock creation."""
        success, message, lock = self.airdrop.create_bridge_lock(
            from_address="RTC1234567890123456789012345678901234567890",
            to_address="0x1234567890123456789012345678901234567890",
            from_chain="rustchain",
            to_chain="base",
            amount_uwrtc=100 * 1_000_000,  # 100 wRTC
        )

        self.assertTrue(success)
        self.assertIsNotNone(lock)
        self.assertEqual(lock.from_chain, "rustchain")
        self.assertEqual(lock.to_chain, "base")
        self.assertEqual(lock.amount_uwrtc, 100 * 1_000_000)
        self.assertEqual(lock.status, "pending")

    def test_bridge_lock_same_chain_rejected(self):
        """Test that same-chain bridge is rejected."""
        success, message, lock = self.airdrop.create_bridge_lock(
            from_address="RTC1234567890123456789012345678901234567890",
            to_address="0x1234567890123456789012345678901234567890",
            from_chain="base",
            to_chain="base",  # Same chain
            amount_uwrtc=100 * 1_000_000,
        )

        self.assertFalse(success)
        self.assertIn("must differ", message)

    def test_confirm_bridge_lock(self):
        """Test bridge lock confirmation."""
        # Create lock
        success, _, lock = self.airdrop.create_bridge_lock(
            from_address="RTC1234567890123456789012345678901234567890",
            to_address="0x1234567890123456789012345678901234567890",
            from_chain="rustchain",
            to_chain="base",
            amount_uwrtc=100 * 1_000_000,
        )
        self.assertTrue(success)

        # Confirm with source tx
        success, message = self.airdrop.confirm_bridge_lock(
            lock_id=lock.lock_id,
            source_tx="solana_tx_signature_1234567890",
        )

        self.assertTrue(success)

        # Verify lock status
        updated_lock = self.airdrop.get_lock(lock.lock_id)
        self.assertEqual(updated_lock.status, "locked")
        self.assertEqual(updated_lock.source_tx, "solana_tx_signature_1234567890")

    def test_release_bridge_lock(self):
        """Test bridge lock release."""
        # Create and confirm lock
        success, _, lock = self.airdrop.create_bridge_lock(
            from_address="RTC1234567890123456789012345678901234567890",
            to_address="0x1234567890123456789012345678901234567890",
            from_chain="rustchain",
            to_chain="base",
            amount_uwrtc=100 * 1_000_000,
        )
        self.assertTrue(success)

        success, _ = self.airdrop.confirm_bridge_lock(
            lock_id=lock.lock_id,
            source_tx="solana_tx_signature_1234567890",
        )
        self.assertTrue(success)

        # Release with dest tx
        success, message = self.airdrop.release_bridge_lock(
            lock_id=lock.lock_id,
            dest_tx="base_tx_signature_abcdef",
        )

        self.assertTrue(success)

        # Verify lock status
        updated_lock = self.airdrop.get_lock(lock.lock_id)
        self.assertEqual(updated_lock.status, "released")
        self.assertEqual(updated_lock.dest_tx, "base_tx_signature_abcdef")


@unittest.skipIf(Flask is None, "Flask is not installed")
class TestAirdropRoutes(unittest.TestCase):
    """Test Flask route request validation."""

    def setUp(self):
        """Create a test app and temp database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_airdrop_routes(self.app, self.airdrop, self.temp_db.name)
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up temp database."""
        self.client = None
        self.app = None
        self.airdrop = None
        gc.collect()
        os.unlink(self.temp_db.name)

    def test_write_routes_reject_non_object_json(self):
        """Write routes should reject JSON arrays instead of raising."""
        routes = [
            ("/api/airdrop/eligibility", {}),
            ("/api/airdrop/claim", {}),
            ("/api/bridge/lock", {}),
            ("/api/bridge/lock/test-lock/confirm", {"X-Admin-Key": "test-admin"}),
            ("/api/bridge/lock/test-lock/release", {"X-Admin-Key": "test-admin"}),
        ]

        with patch.dict(os.environ, {"RC_ADMIN_KEY": "test-admin"}):
            for route, headers in routes:
                with self.subTest(route=route):
                    response = self.client.post(
                        route,
                        json=["not", "an", "object"],
                        headers=headers,
                    )

                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json()["error"], "invalid_json")

    def test_write_routes_reject_non_string_fields(self):
        """Text fields should be strings before they are stripped."""
        cases = [
            (
                "/api/airdrop/eligibility",
                {
                    "github_username": {"name": "octo"},
                    "wallet_address": "RTC1234567890123456789012345678901234567890",
                    "chain": "base",
                },
                "github_username",
                {},
            ),
            (
                "/api/airdrop/claim",
                {
                    "github_username": "octo",
                    "wallet_address": "RTC1234567890123456789012345678901234567890",
                    "chain": "base",
                    "tier": ["builder"],
                },
                "tier",
                {},
            ),
            (
                "/api/bridge/lock",
                {
                    "from_address": "RTC1234567890123456789012345678901234567890",
                    "to_address": {"address": "0x1234567890123456789012345678901234567890"},
                    "from_chain": "rustchain",
                    "to_chain": "base",
                    "amount_wrtc": "1.5",
                },
                "to_address",
                {},
            ),
            (
                "/api/bridge/lock/test-lock/confirm",
                {"source_tx": {"tx": "abc"}},
                "source_tx",
                {"X-Admin-Key": "test-admin"},
            ),
            (
                "/api/bridge/lock/test-lock/release",
                {"dest_tx": ["abc"]},
                "dest_tx",
                {"X-Admin-Key": "test-admin"},
            ),
        ]

        with patch.dict(os.environ, {"RC_ADMIN_KEY": "test-admin"}):
            for route, body, field, headers in cases:
                with self.subTest(route=route, field=field):
                    response = self.client.post(route, json=body, headers=headers)
                    payload = response.get_json()

                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(payload["error"], "invalid_field_type")
                    self.assertEqual(payload["field"], field)

    def test_bridge_lock_rejects_invalid_amount_type(self):
        """Bridge amount conversion errors should be handled as 400s."""
        for amount in ({"value": "1.5"}, True, False):
            with self.subTest(amount=amount):
                response = self.client.post(
                    "/api/bridge/lock",
                    json={
                        "from_address": "RTC1234567890123456789012345678901234567890",
                        "to_address": "0x1234567890123456789012345678901234567890",
                        "from_chain": "rustchain",
                        "to_chain": "base",
                        "amount_wrtc": amount,
                    },
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], "invalid_amount")


class TestAllocationTracking(unittest.TestCase):
    """Test allocation tracking."""

    def setUp(self):
        """Create airdrop instance with temp database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)

    def tearDown(self):
        """Clean up temp database."""
        os.unlink(self.temp_db.name)

    def test_allocation_updated_on_claim(self):
        """Test that allocation is updated when claim is created."""
        # Get initial allocation
        initial = self.airdrop.get_allocation_status()
        initial_claimed = initial["base"]["claimed_wrtc"]

        # Create claim
        success, _, _ = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )
        self.assertTrue(success)

        # Check allocation updated
        updated = self.airdrop.get_allocation_status()
        self.assertEqual(
            updated["base"]["claimed_wrtc"], initial_claimed + 50  # 50 wRTC for contributor
        )

    def test_allocation_exhaustion(self):
        """Test claim rejection when allocation exhausted."""
        # Manually exhaust allocation
        conn = self.airdrop._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE airdrop_allocation SET claimed_uwrtc = total_uwrtc WHERE chain = 'base'"
        )
        conn.commit()
        conn.close()

        # Try to claim
        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIn("exhausted", message)


class TestStatistics(unittest.TestCase):
    """Test statistics and reporting."""

    def setUp(self):
        """Create airdrop instance with temp database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)

    def tearDown(self):
        """Clean up temp database."""
        os.unlink(self.temp_db.name)

    def test_get_stats(self):
        """Test statistics retrieval."""
        # Create some claims
        for i in range(3):
            self.airdrop.claim_airdrop(
                github_username=f"user{i}",
                wallet_address=f"RTC123456789012345678901234567890123456789{i}",
                chain="base",
                tier="contributor",
                skip_antisybil=True,
            )

        for i in range(2):
            self.airdrop.claim_airdrop(
                github_username=f"starer{i}",
                wallet_address=f"RTC123456789012345678901234567890123456788{i}",
                chain="solana",
                tier="stargazer",
                skip_antisybil=True,
            )

        stats = self.airdrop.get_stats()

        self.assertEqual(stats["total_claims"], 5)
        self.assertEqual(stats["by_tier"]["contributor"]["count"], 3)
        self.assertEqual(stats["by_tier"]["stargazer"]["count"], 2)
        self.assertEqual(stats["by_chain"]["base"]["count"], 3)
        self.assertEqual(stats["by_chain"]["solana"]["count"], 2)

    def test_get_claims_by_github(self):
        """Test retrieving claims by GitHub username."""
        # Create multiple claims for same user
        self.airdrop.claim_airdrop(
            github_username="multiuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
        )

        self.airdrop.claim_airdrop(
            github_username="multiuser",
            wallet_address="SolanaWallet12345678901234567890123456789",
            chain="solana",
            tier="builder",
            skip_antisybil=True,
        )

        claims = self.airdrop.get_claims_by_github("multiuser")

        self.assertEqual(len(claims), 2)
        tiers = {c.tier for c in claims}
        self.assertEqual(tiers, {"contributor", "builder"})


class TestClaimRecordSerialization(unittest.TestCase):
    """Test claim record serialization."""

    def test_claim_to_dict(self):
        """Test ClaimRecord to_dict method."""
        claim = ClaimRecord(
            claim_id="test123",
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            amount_uwrtc=50_000_000,
            amount_wrtc=50.0,
            timestamp=int(time.time()),
            tx_signature="0xabc123",
            status="completed",
        )

        result = claim.to_dict()

        self.assertEqual(result["claim_id"], "test123")
        self.assertEqual(result["github_username"], "testuser")
        self.assertEqual(result["amount_wrtc"], 50.0)
        self.assertIn("timestamp_iso", result)
        self.assertEqual(result["status"], "completed")


class TestBridgeLockSerialization(unittest.TestCase):
    """Test bridge lock serialization."""

    def test_lock_to_dict(self):
        """Test BridgeLock to_dict method."""
        lock = BridgeLock(
            lock_id="bridge123",
            from_address="RTC1234567890123456789012345678901234567890",
            to_address="0x1234567890123456789012345678901234567890",
            from_chain="rustchain",
            to_chain="base",
            amount_uwrtc=100_000_000,
            amount_wrtc=100.0,
            timestamp=int(time.time()),
            status="locked",
            source_tx="solana_tx_123",
            dest_tx=None,
        )

        result = lock.to_dict()

        self.assertEqual(result["lock_id"], "bridge123")
        self.assertEqual(result["amount_wrtc"], 100.0)
        self.assertEqual(result["status"], "locked")
        self.assertIn("timestamp_iso", result)


class TestEligibilityResultSerialization(unittest.TestCase):
    """Test eligibility result serialization."""

    def test_result_to_dict(self):
        """Test EligibilityResult to_dict method."""
        result = EligibilityResult(
            eligible=True,
            tier="builder",
            reward_uwrtc=100_000_000,
            reward_wrtc=100.0,
            reason="Eligible for 3+ merged PRs",
            checks={"github_valid": True, "wallet_valid": True},
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
        )

        result_dict = result.to_dict()

        self.assertTrue(result_dict["eligible"])
        self.assertEqual(result_dict["tier"], "builder")
        self.assertEqual(result_dict["reward_wrtc"], 100.0)
        self.assertEqual(result_dict["checks"]["github_valid"], True)


if __name__ == "__main__":
    unittest.main()
