"""
Integration tests for RustChain SDK Bounty Claims methods

These tests verify the SDK client methods for bounty operations.
"""

import pytest
from unittest.mock import patch, MagicMock
from rustchain import RustChainClient, BountyError
from rustchain.exceptions import ValidationError, APIError


@pytest.fixture
def client():
    """Create test client."""
    client = RustChainClient("https://rustchain.org", verify_ssl=False, timeout=10)
    yield client
    client.close()


class TestListBounties:
    """Test list_bounties method."""

    def test_list_bounties_success(self, client):
        """Test successful bounty list retrieval."""
        mock_response = {
            "bounties": [
                {
                    "bounty_id": "bounty_dos_port",
                    "title": "MS-DOS Validator Port",
                    "reward": "Uber Dev Badge + RUST 500",
                    "status": "Open",
                    "claim_count": 5,
                    "pending_claims": 2,
                },
                {
                    "bounty_id": "bounty_macos_75",
                    "title": "Classic Mac OS 7.5.x Validator",
                    "reward": "Uber Dev Badge + RUST 750",
                    "status": "Open",
                    "claim_count": 3,
                    "pending_claims": 1,
                },
            ],
            "count": 2,
        }

        with patch.object(client, "_request", return_value=mock_response) as mock_request:
            bounties = client.list_bounties()

            mock_request.assert_called_once_with("GET", "/api/bounty/list")
            assert len(bounties) == 2
            assert bounties[0]["bounty_id"] == "bounty_dos_port"
            assert bounties[0]["claim_count"] == 5

    def test_list_bounties_empty(self, client):
        """Test bounty list when empty."""
        with patch.object(client, "_request", return_value={"bounties": [], "count": 0}) as mock_request:
            bounties = client.list_bounties()
            assert bounties == []


class TestSubmitBountyClaim:
    """Test submit_bounty_claim method."""

    def test_submit_claim_success(self, client):
        """Test successful claim submission."""
        mock_response = {
            "claim_id": "CLM-ABC123DEF456",
            "bounty_id": "bounty_dos_port",
            "status": "pending",
            "submitted_at": 1234567890,
            "message": "Claim submitted successfully",
        }

        with patch.object(client, "_request", return_value=mock_response) as mock_request:
            result = client.submit_bounty_claim(
                bounty_id="bounty_dos_port",
                claimant_miner_id="RTC_test_miner",
                description="Completed MS-DOS validator",
                github_pr_url="https://github.com/user/rustchain-dos/pull/1",
            )

            mock_request.assert_called_once_with(
                "POST",
                "/api/bounty/claims",
                json_payload={
                    "bounty_id": "bounty_dos_port",
                    "claimant_miner_id": "RTC_test_miner",
                    "description": "Completed MS-DOS validator",
                    "github_pr_url": "https://github.com/user/rustchain-dos/pull/1",
                },
            )

            assert result["claim_id"] == "CLM-ABC123DEF456"
            assert result["status"] == "pending"

    def test_submit_claim_with_all_fields(self, client):
        """Test claim submission with all optional fields."""
        mock_response = {"claim_id": "CLM-123", "status": "pending"}

        with patch.object(client, "_request", return_value=mock_response):
            result = client.submit_bounty_claim(
                bounty_id="bounty_macos_75",
                claimant_miner_id="RTC_miner",
                description="MacOS validator",
                claimant_pubkey="ed25519_pubkey",
                github_pr_url="https://github.com/user/repo/pull/1",
                github_repo="user/repo",
                commit_hash="abc123def",
                evidence_urls=["https://example.com/demo.mp4"],
            )

            assert result["claim_id"] == "CLM-123"

    def test_submit_claim_validation_error_empty_bounty(self, client):
        """Test validation fails with empty bounty_id."""
        with pytest.raises(ValidationError) as exc_info:
            client.submit_bounty_claim(
                bounty_id="",
                claimant_miner_id="RTC_miner",
                description="Test",
            )
        assert "bounty_id must be a non-empty string" in str(exc_info.value)

    def test_submit_claim_validation_error_empty_miner(self, client):
        """Test validation fails with empty miner_id."""
        with pytest.raises(ValidationError) as exc_info:
            client.submit_bounty_claim(
                bounty_id="bounty_dos_port",
                claimant_miner_id="",
                description="Test",
            )
        assert "claimant_miner_id must be a non-empty string" in str(exc_info.value)

    def test_submit_claim_validation_error_empty_description(self, client):
        """Test validation fails with empty description."""
        with pytest.raises(ValidationError) as exc_info:
            client.submit_bounty_claim(
                bounty_id="bounty_dos_port",
                claimant_miner_id="RTC_miner",
                description="",
            )
        assert "description must be a non-empty string" in str(exc_info.value)

    def test_submit_claim_validation_error_description_too_long(self, client):
        """Test validation fails with description too long."""
        with pytest.raises(ValidationError) as exc_info:
            client.submit_bounty_claim(
                bounty_id="bounty_dos_port",
                claimant_miner_id="RTC_miner",
                description="X" * 5001,
            )
        assert "description must be 1-5000 characters" in str(exc_info.value)

    def test_submit_claim_error_response(self, client):
        """Test handling of error response from server."""
        mock_error_response = {
            "error": "duplicate_claim",
            "message": "You already have a pending claim for this bounty",
        }

        with patch.object(client, "_request", return_value=mock_error_response):
            with pytest.raises(BountyError) as exc_info:
                client.submit_bounty_claim(
                    bounty_id="bounty_dos_port",
                    claimant_miner_id="RTC_miner",
                    description="Test",
                )

            assert "Claim submission failed" in str(exc_info.value)

    def test_submit_claim_api_error(self, client):
        """Test handling of API error."""
        with patch.object(client, "_request", side_effect=APIError("HTTP 500: Internal Server Error", status_code=500)):
            with pytest.raises(BountyError) as exc_info:
                client.submit_bounty_claim(
                    bounty_id="bounty_dos_port",
                    claimant_miner_id="RTC_miner",
                    description="Test",
                )

            assert "Claim submission failed" in str(exc_info.value)


class TestGetBountyClaim:
    """Test get_bounty_claim method."""

    def test_get_claim_success(self, client):
        """Test successful claim retrieval."""
        mock_response = {
            "claim_id": "CLM-ABC123DEF456",
            "bounty_id": "bounty_dos_port",
            "claimant_miner_id": "RTC_test...",
            "submission_ts": 1234567890,
            "status": "under_review",
            "github_pr_url": "https://github.com/user/rustchain-dos/pull/1",
            "reward_amount_rtc": 500.0,
            "reward_paid": 0,
        }

        with patch.object(client, "_request", return_value=mock_response) as mock_request:
            claim = client.get_bounty_claim("CLM-ABC123DEF456")

            mock_request.assert_called_once_with("GET", "/api/bounty/claims/CLM-ABC123DEF456")
            assert claim["claim_id"] == "CLM-ABC123DEF456"
            assert claim["status"] == "under_review"

    def test_get_claim_validation_error(self, client):
        """Test validation fails with empty claim_id."""
        with pytest.raises(ValidationError) as exc_info:
            client.get_bounty_claim("")
        assert "claim_id must be a non-empty string" in str(exc_info.value)


class TestGetMinerBountyClaims:
    """Test get_miner_bounty_claims method."""

    def test_get_miner_claims_success(self, client):
        """Test successful retrieval of miner claims."""
        mock_response = {
            "miner_id": "RTC_test_miner",
            "claims": [
                {
                    "claim_id": "CLM-111",
                    "bounty_id": "bounty_dos_port",
                    "status": "approved",
                    "reward_amount_rtc": 500.0,
                },
                {
                    "claim_id": "CLM-222",
                    "bounty_id": "bounty_macos_75",
                    "status": "pending",
                    "reward_amount_rtc": None,
                },
            ],
            "count": 2,
        }

        with patch.object(client, "_request", return_value=mock_response) as mock_request:
            claims = client.get_miner_bounty_claims("RTC_test_miner")

            mock_request.assert_called_once_with(
                "GET",
                "/api/bounty/claims/miner/RTC_test_miner",
                params={"limit": 50},
            )
            assert len(claims) == 2
            assert claims[0]["claim_id"] == "CLM-111"

    def test_get_miner_claims_with_limit(self, client):
        """Test claim retrieval with custom limit."""
        mock_response = {"miner_id": "RTC_test", "claims": [], "count": 0}

        with patch.object(client, "_request", return_value=mock_response) as mock_request:
            client.get_miner_bounty_claims("RTC_test", limit=10)

            mock_request.assert_called_once_with(
                "GET",
                "/api/bounty/claims/miner/RTC_test",
                params={"limit": 10},
            )

    def test_get_miner_claims_validation_error(self, client):
        """Test validation fails with empty miner_id."""
        with pytest.raises(ValidationError) as exc_info:
            client.get_miner_bounty_claims("")
        assert "miner_id must be a non-empty string" in str(exc_info.value)


class TestGetBountyStatistics:
    """Test get_bounty_statistics method."""

    def test_get_statistics_success(self, client):
        """Test successful statistics retrieval."""
        mock_response = {
            "total_claims": 25,
            "status_breakdown": {
                "pending": 10,
                "approved": 8,
                "rejected": 5,
                "under_review": 2,
            },
            "total_rewards_paid_rtc": 4500.0,
            "by_bounty": {
                "bounty_dos_port": {"pending": 3, "approved": 2},
                "bounty_macos_75": {"pending": 2, "approved": 3},
            },
        }

        with patch.object(client, "_request", return_value=mock_response) as mock_request:
            stats = client.get_bounty_statistics()

            mock_request.assert_called_once_with("GET", "/api/bounty/statistics")
            assert stats["total_claims"] == 25
            assert stats["total_rewards_paid_rtc"] == 4500.0
            assert "bounty_dos_port" in stats["by_bounty"]


class TestBountyError:
    """Test BountyError exception."""

    def test_bounty_error_with_status_code(self):
        """Test BountyError preserves status code."""
        error = BountyError("Test error", status_code=400, response={"error": "bad_request"})

        assert str(error) == "Test error"
        assert error.status_code == 400
        assert error.response == {"error": "bad_request"}

    def test_bounty_error_without_status_code(self):
        """Test BountyError works without status code."""
        error = BountyError("Test error")

        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.response is None
