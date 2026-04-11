"""Tests for schema dataclasses and MCP input schemas."""

import pytest
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rustchain_bounties_mcp.schemas import (
    APIError,
    AttestChallenge,
    AttestSubmitResult,
    BountyInfo,
    EpochInfo,
    HealthStatus,
    MinerInfo,
    WalletBalance,
    WalletVerifyResult,
    BALANCE_SCHEMA,
    BOUNTIES_SCHEMA,
    EPOCH_SCHEMA,
    HEALTH_SCHEMA,
    MINERS_SCHEMA,
    SUBMIT_ATTESTATION_SCHEMA,
    VERIFY_WALLET_SCHEMA,
)


# -- HealthStatus -----------------------------------------------------------

class TestHealthStatus:
    def test_from_dict_full(self):
        h = HealthStatus.from_dict({
            "ok": True, "version": "2.2.1", "uptime_s": 86400,
            "db_rw": True, "backup_age_hours": 12.5, "tip_age_slots": 3,
        })
        assert h.ok is True
        assert h.is_healthy is True
        assert h.version == "2.2.1"
        assert h.uptime_s == 86400

    def test_from_dict_minimal(self):
        h = HealthStatus.from_dict({"ok": False, "version": "x", "uptime_s": 0, "db_rw": False})
        assert h.is_healthy is False

    def test_from_dict_defaults(self):
        h = HealthStatus.from_dict({"ok": True, "version": "v", "uptime_s": 10, "db_rw": True})
        assert h.backup_age_hours is None
        assert h.tip_age_slots is None


# -- EpochInfo --------------------------------------------------------------

class TestEpochInfo:
    def test_from_dict(self):
        e = EpochInfo.from_dict({
            "epoch": 95, "slot": 12345, "epoch_pot": 1000.0,
            "enrolled_miners": 42, "blocks_per_epoch": 100, "total_supply_rtc": 21000000.0,
        })
        assert e.epoch == 95
        assert e.slot == 12345
        assert e.epoch_pot == 1000.0


# -- WalletBalance ----------------------------------------------------------

class TestWalletBalance:
    def test_from_dict(self):
        b = WalletBalance.from_dict({"miner_id": "scott", "amount_i64": 155000000, "amount_rtc": 155.0})
        assert b.miner_id == "scott"
        assert b.amount_rtc == 155.0
        assert b.amount_i64 == 155000000


# -- MinerInfo --------------------------------------------------------------

class TestMinerInfo:
    def test_from_dict(self):
        m = MinerInfo.from_dict({
            "miner": "alice", "last_attest": 1700000000,
            "device_family": "PowerPC", "device_arch": "g4",
            "entropy_score": 0.95, "antiquity_multiplier": 2.0,
            "hardware_type": "PowerPC G4 (Vintage)",
        })
        assert m.miner == "alice"
        assert m.antiquity_multiplier == 2.0
        assert "PowerPC" in m.hardware_type


# -- WalletVerifyResult -----------------------------------------------------

class TestWalletVerifyResult:
    def test_from_dict(self):
        r = WalletVerifyResult.from_dict({
            "wallet_address": "0xabc", "exists": True, "balance_rtc": 100.0, "message": "ok",
        })
        assert r.wallet_address == "0xabc"
        assert r.exists is True
        assert r.balance_rtc == 100.0

    def test_from_dict_legacy_keys(self):
        """Backwards compat: 'created' maps to 'exists'."""
        r = WalletVerifyResult.from_dict({
            "wallet_address": "0xdef", "created": True, "amount_rtc": 50.0, "message": "legacy",
        })
        assert r.exists is True
        assert r.balance_rtc == 50.0


# -- AttestChallenge --------------------------------------------------------

class TestAttestChallenge:
    def test_from_dict(self):
        c = AttestChallenge.from_dict({
            "nonce": "deadbeef", "expires_at": 1700000300, "server_time": 1700000000,
        })
        assert c.nonce == "deadbeef"
        assert c.expires_at == 1700000300


# -- AttestSubmitResult -----------------------------------------------------

class TestAttestSubmitResult:
    def test_from_dict_success(self):
        r = AttestSubmitResult.from_dict({
            "ok": True, "message": "enrolled", "miner_id": "bob", "enrolled_epoch": 95,
        })
        assert r.ok is True
        assert r.enrolled_epoch == 95

    def test_from_dict_failure(self):
        r = AttestSubmitResult.from_dict({"ok": False, "message": "invalid nonce"})
        assert r.ok is False
        assert r.miner_id is None


# -- BountyInfo -------------------------------------------------------------

class TestBountyInfo:
    def test_from_dict(self):
        b = BountyInfo.from_dict({
            "issue_number": 2859, "title": "MCP Server", "reward_rtc": 500.0,
            "status": "open", "difficulty": "medium",
            "tags": ["python", "mcp", "ai"],
        })
        assert b.issue_number == 2859
        assert b.reward_rtc == 500.0
        assert "mcp" in b.tags


# -- APIError ---------------------------------------------------------------

class TestAPIError:
    def test_from_response_dict(self):
        e = APIError.from_response(400, {"error": "BAD_INPUT", "message": "missing field"})
        assert e.code == "BAD_INPUT"
        assert e.status_code == 400

    def test_to_dict(self):
        e = APIError(code="X", message="y", status_code=500)
        d = e.to_dict()
        assert d["error"] == "X"
        assert d["message"] == "y"

    def test_from_response_plain(self):
        e = APIError.from_response(503, "service unavailable")
        assert e.code == "HTTP_ERROR"


# -- MCP Input Schemas ------------------------------------------------------

class TestInputSchemas:
    def test_health_schema_empty(self):
        assert HEALTH_SCHEMA["type"] == "object"
        assert HEALTH_SCHEMA.get("required") is None

    def test_epoch_schema_no_required(self):
        assert EPOCH_SCHEMA["type"] == "object"

    def test_balance_requires_miner_id(self):
        assert "miner_id" in BALANCE_SCHEMA["required"]

    def test_miners_schema_optional_params(self):
        assert "limit" in MINERS_SCHEMA["properties"]
        assert "hardware_type" in MINERS_SCHEMA["properties"]

    def test_verify_wallet_requires_miner_id(self):
        assert "miner_id" in VERIFY_WALLET_SCHEMA["required"]

    def test_attestation_requires_miner_id_and_device(self):
        req = SUBMIT_ATTESTATION_SCHEMA["required"]
        assert "miner_id" in req
        assert "device" in req

    def test_bounties_schema_optional(self):
        assert BOUNTIES_SCHEMA.get("required") is None


# -- GitHub Bounty Parsing (client-side) ------------------------------------

class TestGitHubBountyParsing:
    """Test the _parse_github_issue static method on RustChainClient."""

    def _parse(self, issue: dict) -> Optional[BountyInfo]:
        # Import here to avoid circular deps; the method lives on the client.
        from rustchain_bounties_mcp.client import RustChainClient
        return RustChainClient._parse_github_issue(issue)

    def test_parse_issue_with_rtc_in_title(self):
        issue = {
            "number": 42,
            "title": "Bounty: MCP Server (500 RTC)",
            "html_url": "https://github.com/Scottcjn/rustchain-bounties/issues/42",
            "state": "open",
            "labels": [{"name": "bounty"}, {"name": "medium"}],
            "body": "Build an MCP server for RustChain.",
        }
        b = self._parse(issue)
        assert b is not None
        assert b.issue_number == 42
        assert b.reward_rtc == 500.0
        assert b.difficulty == "medium"
        assert "bounty" in b.tags

    def test_parse_issue_with_rtc_in_label(self):
        issue = {
            "number": 10,
            "title": "Add documentation",
            "html_url": "https://github.com/Scottcjn/rustchain-bounties/issues/10",
            "state": "open",
            "labels": [{"name": "bounty: 50 RTC"}, {"name": "easy"}],
            "body": None,
        }
        b = self._parse(issue)
        assert b is not None
        assert b.reward_rtc == 50.0
        assert b.difficulty == "easy"

    def test_parse_pr_is_skipped(self):
        issue = {
            "number": 99,
            "title": "Fix typo",
            "html_url": "https://github.com/Scottcjn/rustchain-bounties/pull/99",
            "state": "open",
            "labels": [],
            "body": "",
            "pull_request": {"merged_at": None},
        }
        # The client filters these out before calling _parse_github_issue,
        # but the parser itself doesn't skip — the caller does.
        b = self._parse(issue)
        assert b is not None  # parser doesn't check pull_request
        assert b.issue_number == 99

    def test_parse_no_reward(self):
        issue = {
            "number": 1,
            "title": "General discussion",
            "html_url": "https://github.com/Scottcjn/rustchain-bounties/issues/1",
            "state": "open",
            "labels": [{"name": "discussion"}],
            "body": "Just a discussion thread.",
        }
        b = self._parse(issue)
        assert b is not None
        assert b.reward_rtc == 0.0
        assert b.difficulty is None
