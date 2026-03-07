"""
Tests for RustChain Bounty Claims System

Tests cover:
- Database initialization
- Claim submission validation
- Claim retrieval
- Status updates
- Admin operations
- API endpoint integration
"""

import pytest
import os
import sys
import time
import json
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add node directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from node.bounty_claims import (
    init_bounty_tables,
    submit_claim,
    get_claim,
    get_claims_by_miner,
    get_claims_by_bounty,
    update_claim_status,
    mark_claim_paid,
    get_bounty_statistics,
    validate_claim_payload,
    generate_claim_id,
    CLAIM_STATUS_PENDING,
    CLAIM_STATUS_APPROVED,
    CLAIM_STATUS_REJECTED,
    CLAIM_STATUS_UNDER_REVIEW,
    VALID_BOUNTY_IDS,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_bounty_tables(db_path)
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def sample_claim_data():
    """Sample claim data for testing."""
    return {
        "bounty_id": "bounty_dos_port",
        "claimant_miner_id": "RTC_test_miner_123",
        "description": "Completed MS-DOS validator with BIOS date entropy and FAT filesystem output.",
        "claimant_pubkey": "ed25519_pubkey_hex_abc123",
        "github_pr_url": "https://github.com/user/rustchain-dos/pull/1",
        "github_repo": "user/rustchain-dos",
        "commit_hash": "abc123def456789012345678901234567890abcd",  # 40 chars
        "evidence_urls": [
            "https://github.com/user/rustchain-dos",
            "https://example.com/demo.mp4",
        ],
    }


class TestClaimValidation:
    """Test claim payload validation."""

    def test_valid_payload(self, sample_claim_data):
        """Test validation of valid claim payload."""
        is_valid, error_msg = validate_claim_payload(sample_claim_data)
        assert is_valid is True
        assert error_msg is None

    def test_missing_required_fields(self):
        """Test validation fails with missing required fields."""
        # Missing description
        data = {
            "bounty_id": "bounty_dos_port",
            "claimant_miner_id": "RTC_test",
        }
        is_valid, error_msg = validate_claim_payload(data)
        assert is_valid is False
        assert "Missing required field" in error_msg

    def test_invalid_bounty_id(self):
        """Test validation fails with invalid bounty_id."""
        data = {
            "bounty_id": "invalid_bounty",
            "claimant_miner_id": "RTC_test",
            "description": "Test description",
        }
        is_valid, error_msg = validate_claim_payload(data)
        assert is_valid is False
        assert "Invalid bounty_id" in error_msg

    def test_invalid_miner_id_length(self):
        """Test validation fails with too long miner_id."""
        data = {
            "bounty_id": "bounty_dos_port",
            "claimant_miner_id": "R" * 200,
            "description": "Test description",
        }
        is_valid, error_msg = validate_claim_payload(data)
        assert is_valid is False

    def test_invalid_github_pr_url(self):
        """Test validation fails with invalid GitHub PR URL."""
        data = {
            "bounty_id": "bounty_dos_port",
            "claimant_miner_id": "RTC_test",
            "description": "Test",
            "github_pr_url": "https://example.com/not-github",
        }
        is_valid, error_msg = validate_claim_payload(data)
        assert is_valid is False
        assert "GitHub PR URL" in error_msg

    def test_invalid_commit_hash(self):
        """Test validation fails with invalid commit hash."""
        data = {
            "bounty_id": "bounty_dos_port",
            "claimant_miner_id": "RTC_test",
            "description": "Test",
            "commit_hash": "invalid_hash!",
        }
        is_valid, error_msg = validate_claim_payload(data)
        assert is_valid is False
        assert "commit_hash" in error_msg

    def test_valid_short_commit_hash(self):
        """Test validation passes with valid 7-char commit hash."""
        data = {
            "bounty_id": "bounty_dos_port",
            "claimant_miner_id": "RTC_test",
            "description": "Test",
            "commit_hash": "abc1234",
        }
        is_valid, error_msg = validate_claim_payload(data)
        assert is_valid is True

    def test_empty_payload(self):
        """Test validation fails with empty payload."""
        is_valid, error_msg = validate_claim_payload({})
        assert is_valid is False

    def test_non_dict_payload(self):
        """Test validation fails with non-dict payload."""
        is_valid, error_msg = validate_claim_payload("not a dict")
        assert is_valid is False


class TestClaimGeneration:
    """Test claim ID generation."""

    def test_generate_claim_id(self):
        """Test claim ID generation is deterministic."""
        claim_id1 = generate_claim_id("bounty_dos_port", "RTC_test", 1234567890)
        claim_id2 = generate_claim_id("bounty_dos_port", "RTC_test", 1234567890)
        claim_id3 = generate_claim_id("bounty_dos_port", "RTC_test", 1234567891)

        assert claim_id1 == claim_id2
        assert claim_id1 != claim_id3
        assert claim_id1.startswith("CLM-")
        assert len(claim_id1) == 16  # "CLM-" + 12 hex chars


class TestClaimSubmission:
    """Test claim submission operations."""

    def test_submit_claim_success(self, temp_db, sample_claim_data):
        """Test successful claim submission."""
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id=sample_claim_data["bounty_id"],
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description=sample_claim_data["description"],
            claimant_pubkey=sample_claim_data.get("claimant_pubkey"),
            github_pr_url=sample_claim_data.get("github_pr_url"),
            github_repo=sample_claim_data.get("github_repo"),
            commit_hash=sample_claim_data.get("commit_hash"),
            evidence_urls=sample_claim_data.get("evidence_urls"),
        )

        assert success is True
        assert "claim_id" in result
        assert result["bounty_id"] == sample_claim_data["bounty_id"]
        assert result["status"] == CLAIM_STATUS_PENDING
        assert "submitted_at" in result

    def test_submit_claim_duplicate_pending(self, temp_db, sample_claim_data):
        """Test duplicate claim submission is rejected."""
        # Submit first claim
        submit_claim(
            db_path=temp_db,
            bounty_id=sample_claim_data["bounty_id"],
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description=sample_claim_data["description"],
        )

        # Try to submit duplicate
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id=sample_claim_data["bounty_id"],
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description="Another description",
        )

        assert success is False
        assert result["error"] == "duplicate_claim"

    def test_submit_claim_different_bounty_allowed(self, temp_db, sample_claim_data):
        """Test submitting claim for different bounty is allowed."""
        # Submit first claim
        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description="First claim",
        )

        # Submit claim for different bounty
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id="bounty_macos_75",
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description="Second claim for different bounty",
        )

        assert success is True
        assert result["bounty_id"] == "bounty_macos_75"


class TestClaimRetrieval:
    """Test claim retrieval operations."""

    def test_get_claim_by_id(self, temp_db, sample_claim_data):
        """Test retrieving claim by ID."""
        # Submit claim
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id=sample_claim_data["bounty_id"],
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description=sample_claim_data["description"],
        )

        claim_id = result["claim_id"]
        retrieved = get_claim(temp_db, claim_id)

        assert retrieved is not None
        assert retrieved["claim_id"] == claim_id
        assert retrieved["bounty_id"] == sample_claim_data["bounty_id"]
        assert retrieved["claimant_miner_id"] == sample_claim_data["claimant_miner_id"]

    def test_get_claim_not_found(self, temp_db):
        """Test retrieving non-existent claim."""
        retrieved = get_claim(temp_db, "CLM-NONEXISTENT")
        assert retrieved is None

    def test_get_claims_by_miner(self, temp_db, sample_claim_data):
        """Test retrieving claims by miner ID."""
        # Submit multiple claims
        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description="First claim",
        )

        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_macos_75",
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description="Second claim",
        )

        claims = get_claims_by_miner(temp_db, sample_claim_data["claimant_miner_id"])

        assert len(claims) == 2
        assert all(c["claimant_miner_id"] == sample_claim_data["claimant_miner_id"] for c in claims)

    def test_get_claims_by_miner_limit(self, temp_db, sample_claim_data):
        """Test claim retrieval respects limit."""
        # Submit 5 claims for different bounties (to avoid duplicate detection)
        bounties = ["bounty_dos_port", "bounty_macos_75", "bounty_win31_progman", "bounty_beos_tracker", "bounty_web_explorer"]
        for i, bounty in enumerate(bounties):
            submit_claim(
                db_path=temp_db,
                bounty_id=bounty,
                claimant_miner_id=sample_claim_data["claimant_miner_id"],
                description=f"Claim {i}",
            )

        claims = get_claims_by_miner(temp_db, sample_claim_data["claimant_miner_id"], limit=2)
        assert len(claims) == 2

    def test_get_claims_by_bounty(self, temp_db, sample_claim_data):
        """Test retrieving claims by bounty ID."""
        # Submit claims for different bounties
        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id="RTC_miner_1",
            description="DOS claim 1",
        )

        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id="RTC_miner_2",
            description="DOS claim 2",
        )

        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_macos_75",
            claimant_miner_id="RTC_miner_1",
            description="MacOS claim",
        )

        dos_claims = get_claims_by_bounty(temp_db, "bounty_dos_port")
        macos_claims = get_claims_by_bounty(temp_db, "bounty_macos_75")

        assert len(dos_claims) == 2
        assert len(macos_claims) == 1

    def test_get_claims_by_bounty_with_status(self, temp_db, sample_claim_data):
        """Test retrieving claims by bounty and status."""
        # Submit and update claims
        success, result1 = submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id="RTC_miner_1",
            description="Claim 1",
        )
        update_claim_status(temp_db, result1["claim_id"], CLAIM_STATUS_APPROVED, "reviewer_1")

        success, result2 = submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id="RTC_miner_2",
            description="Claim 2",
        )
        # Leave as pending

        approved = get_claims_by_bounty(temp_db, "bounty_dos_port", status=CLAIM_STATUS_APPROVED)
        pending = get_claims_by_bounty(temp_db, "bounty_dos_port", status=CLAIM_STATUS_PENDING)

        assert len(approved) == 1
        assert len(pending) == 1


class TestClaimStatusUpdates:
    """Test claim status update operations."""

    def test_update_claim_status_success(self, temp_db, sample_claim_data):
        """Test successful status update."""
        # Submit claim
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id=sample_claim_data["bounty_id"],
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description=sample_claim_data["description"],
        )

        claim_id = result["claim_id"]

        # Update to approved
        success, result = update_claim_status(
            db_path=temp_db,
            claim_id=claim_id,
            status=CLAIM_STATUS_APPROVED,
            reviewer_id="admin_1",
            reviewer_notes="Excellent work!",
            reward_amount_rtc=500.0,
        )

        assert success is True
        assert result["status"] == CLAIM_STATUS_APPROVED

        # Verify in database
        claim = get_claim(temp_db, claim_id)
        assert claim["status"] == CLAIM_STATUS_APPROVED
        assert claim["reviewer_notes"] == "Excellent work!"
        assert claim["reward_amount_rtc"] == 500.0

    def test_update_claim_not_found(self, temp_db):
        """Test updating non-existent claim."""
        success, result = update_claim_status(
            db_path=temp_db,
            claim_id="CLM-NONEXISTENT",
            status=CLAIM_STATUS_APPROVED,
            reviewer_id="admin_1",
        )

        assert success is False
        assert result["error"] == "not_found"

    def test_update_claim_invalid_status(self, temp_db, sample_claim_data):
        """Test updating with invalid status."""
        # Submit claim
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id=sample_claim_data["bounty_id"],
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description=sample_claim_data["description"],
        )

        success, result = update_claim_status(
            db_path=temp_db,
            claim_id=result["claim_id"],
            status="invalid_status",
            reviewer_id="admin_1",
        )

        assert success is False
        assert "invalid_status" in result["error"]


class TestClaimPayment:
    """Test claim payment operations."""

    def test_mark_claim_paid(self, temp_db, sample_claim_data):
        """Test marking claim as paid."""
        # Submit and approve claim
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id=sample_claim_data["bounty_id"],
            claimant_miner_id=sample_claim_data["claimant_miner_id"],
            description=sample_claim_data["description"],
        )

        claim_id = result["claim_id"]
        update_claim_status(temp_db, claim_id, CLAIM_STATUS_APPROVED, "admin_1", reward_amount_rtc=500.0)

        # Mark as paid
        success, result = mark_claim_paid(
            db_path=temp_db,
            claim_id=claim_id,
            payment_tx_id="tx_abc123def456",
            admin_id="admin_1",
        )

        assert success is True
        assert result["paid"] is True
        assert result["payment_tx_id"] == "tx_abc123def456"

        # Verify in database
        claim = get_claim(temp_db, claim_id)
        assert claim["reward_paid"] == 1
        assert claim["payment_tx_id"] == "tx_abc123def456"


class TestBountyStatistics:
    """Test bounty statistics operations."""

    def test_get_bounty_statistics_empty(self, temp_db):
        """Test statistics with no claims."""
        stats = get_bounty_statistics(temp_db)

        assert stats["total_claims"] == 0
        assert stats["status_breakdown"][CLAIM_STATUS_PENDING] == 0
        assert stats["total_rewards_paid_rtc"] == 0

    def test_get_bounty_statistics_with_claims(self, temp_db, sample_claim_data):
        """Test statistics with claims."""
        # Submit claims
        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id="RTC_miner_1",
            description="Claim 1",
        )

        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id="RTC_miner_2",
            description="Claim 2",
        )

        submit_claim(
            db_path=temp_db,
            bounty_id="bounty_macos_75",
            claimant_miner_id="RTC_miner_1",
            description="Claim 3",
        )

        stats = get_bounty_statistics(temp_db)

        assert stats["total_claims"] == 3
        assert stats["status_breakdown"][CLAIM_STATUS_PENDING] == 3
        assert "bounty_dos_port" in stats["by_bounty"]
        assert "bounty_macos_75" in stats["by_bounty"]

    def test_get_bounty_statistics_with_payments(self, temp_db, sample_claim_data):
        """Test statistics includes payment info."""
        # Submit and approve claim
        success, result = submit_claim(
            db_path=temp_db,
            bounty_id="bounty_dos_port",
            claimant_miner_id="RTC_miner_1",
            description="Claim",
        )

        claim_id = result["claim_id"]
        update_claim_status(temp_db, claim_id, CLAIM_STATUS_APPROVED, "admin_1", reward_amount_rtc=500.0)
        mark_claim_paid(temp_db, claim_id, "tx_123", "admin_1")

        stats = get_bounty_statistics(temp_db)

        assert stats["total_rewards_paid_rtc"] == 500.0


class TestValidBountyIds:
    """Test that all expected bounty IDs are defined."""

    def test_valid_bounty_ids_defined(self):
        """Test that expected bounty IDs are in VALID_BOUNTY_IDS."""
        expected_bounties = {
            "bounty_dos_port",
            "bounty_macos_75",
            "bounty_win31_progman",
            "bounty_beos_tracker",
            "bounty_web_explorer",
            "bounty_relic_lore_scribe",
        }

        assert VALID_BOUNTY_IDS == expected_bounties
