"""
Unit tests for RIP-305 Track C+D: Airdrop API
Tests for eligibility, claim, anti-Sybil, and ledger endpoints.

Run: python -m pytest bridge/test_airdrop_api.py -v
"""

import json
import os
import sys
import time
import tempfile
import pytest
import sqlite3

# Isolated temp DB per test session
_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db").name
os.environ["AIRDROP_DB_PATH"] = _test_db_file
os.environ["AIRDROP_ADMIN_KEY"] = "test-admin-key-1149"
os.environ["GITHUB_CLIENT_ID"] = "test_client_id"
os.environ["GITHUB_CLIENT_SECRET"] = "test_client_secret"

# Ensure clean import of airdrop_api with correct env
if "bridge.airdrop_api" in sys.modules:
    del sys.modules["bridge.airdrop_api"]
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _fresh_client():
    """Create a fresh Flask test client with clean DB state."""
    import sqlite3
    from bridge.airdrop_api import Flask, register_airdrop_routes, init_airdrop_db

    # Ensure DB schema is created
    init_airdrop_db()

    # Reset all data
    conn = sqlite3.connect(_test_db_file)
    conn.execute("DELETE FROM eligibility_cache")
    conn.execute("DELETE FROM airdrop_claims")
    conn.execute("DELETE FROM airdrop_events")
    conn.commit()
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_airdrop_routes(app)
    return app.test_client()


# ── Test helpers ──────────────────────────────────────────────────────────────

def _gh_user_response(login="testuser", github_id=12345, created_at="2010-01-01T00:00:00Z"):
    return {"login": login, "id": github_id, "created_at": created_at}


# ── TestEligibilityValidation ────────────────────────────────────────────────

class TestEligibilityValidation:
    def test_eligibility_requires_token_or_code(self):
        client = _fresh_client()
        resp = client.get("/airdrop/eligibility")
        assert resp.status_code == 400
        assert b"github_token or code required" in resp.data

    def test_invalid_oauth_code_without_client_credentials(self):
        client = _fresh_client()
        resp = client.get("/airdrop/eligibility?code=invalid-code")
        data = resp.get_json()
        assert data["error"] in ("oauth_not_configured", "invalid_oauth_code")


# ── TestAntiSybilGitHubAge ────────────────────────────────────────────────────

class TestAntiSybilGitHubAge:
    def test_github_account_too_new_rejected(self):
        import datetime
        import bridge.airdrop_api as api
        recent_date = (datetime.datetime.utcnow() - datetime.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        original = api._get_github_user
        try:
            api._get_github_user = lambda t: _gh_user_response(created_at=recent_date)
            client = _fresh_client()
            resp = client.get("/airdrop/eligibility?github_token=test-token")
            data = resp.get_json()
            assert data["eligible"] is False
            assert data["reason"] == "github_account_too_new"
            assert "30 days" in data["message"]
        finally:
            api._get_github_user = original


# ── TestTierDetermination ────────────────────────────────────────────────────

class TestTierDetermination:
    def test_tier_stargazer(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response()
            api._check_github_repo_stars = lambda t, u: 15
            api._check_github_prs = lambda t, u: {"merged_prs": 0}
            client = _fresh_client()
            resp = client.get("/airdrop/eligibility?github_token=test-token")
            data = resp.get_json()
            assert data["eligible"] is True
            assert data["tier"] == "stargazer"
            assert data["base_amount"] == 25
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars

    def test_tier_contributor(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response()
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()
            resp = client.get("/airdrop/eligibility?github_token=test-token")
            data = resp.get_json()
            assert data["eligible"] is True
            assert data["tier"] == "contributor"
            assert data["base_amount"] == 50
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars

    def test_tier_builder(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response()
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 3}
            client = _fresh_client()
            resp = client.get("/airdrop/eligibility?github_token=test-token")
            data = resp.get_json()
            assert data["eligible"] is True
            assert data["tier"] == "builder"
            assert data["base_amount"] == 100
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars

    def test_tier_core(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response()
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 7}
            client = _fresh_client()
            resp = client.get("/airdrop/eligibility?github_token=test-token")
            data = resp.get_json()
            assert data["eligible"] is True
            assert data["tier"] == "core"
            assert data["base_amount"] == 200
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars

    def test_no_tier_match(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response()
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 0}
            client = _fresh_client()
            resp = client.get("/airdrop/eligibility?github_token=test-token")
            data = resp.get_json()
            assert data["eligible"] is False
            assert data["reason"] == "no_tier_match"
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestClaimValidation ───────────────────────────────────────────────────────

class TestClaimValidation:
    def test_claim_requires_github_token(self):
        client = _fresh_client()
        resp = client.post("/airdrop/claim", json={
            "rustchain_wallet": "test-wallet",
            "target_chain": "solana",
            "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        })
        assert resp.status_code == 400
        assert b"github_token required" in resp.data

    def test_claim_requires_rustchain_wallet(self):
        client = _fresh_client()
        resp = client.post("/airdrop/claim", json={
            "github_token": "test-token",
            "target_chain": "solana",
            "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        })
        assert resp.status_code == 400
        assert b"rustchain_wallet required" in resp.data

    def test_claim_invalid_target_chain(self):
        client = _fresh_client()
        resp = client.post("/airdrop/claim", json={
            "github_token": "test-token",
            "rustchain_wallet": "test-wallet",
            "target_chain": "ethereum",
            "target_address": "0xABC123",
        })
        assert resp.status_code == 400
        assert b"'solana' or 'base'" in resp.data

    def test_claim_base_address_must_start_0x(self):
        client = _fresh_client()
        resp = client.post("/airdrop/claim", json={
            "github_token": "test-token",
            "rustchain_wallet": "test-wallet",
            "target_chain": "base",
            "target_address": "ABC123",
        })
        assert resp.status_code == 400
        assert b"0x" in resp.data

    def test_claim_solana_address_min_length(self):
        client = _fresh_client()
        resp = client.post("/airdrop/claim", json={
            "github_token": "test-token",
            "rustchain_wallet": "test-wallet",
            "target_chain": "solana",
            "target_address": "short",
        })
        assert resp.status_code == 400
        assert b"Invalid Solana address" in resp.data


# ── TestClaimAntiSybil ───────────────────────────────────────────────────────

class TestClaimAntiSybil:
    def test_already_claimed_github_rejected(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="repeat-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()

            # First claim succeeds
            resp1 = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "wallet-1",
                "target_chain": "solana",
                "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            })
            assert resp1.status_code == 201

            # Second claim with same GitHub account is rejected
            resp2 = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "wallet-2",
                "target_chain": "base",
                "target_address": "0xABC1234567890123456789012345678901234567",
            })
            assert resp2.status_code == 409
            assert resp2.get_json()["error"] == "already_claimed"
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars

    def test_wallet_recycling_blocked(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}

            client = _fresh_client()

            # First user claims
            api._get_github_user = lambda t: _gh_user_response(login="user-a")
            resp1 = client.post("/airdrop/claim", json={
                "github_token": "token-a",
                "rustchain_wallet": "shared-wallet",
                "target_chain": "solana",
                "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            })
            assert resp1.status_code == 201

            # Second user tries same wallet
            api._get_github_user = lambda t: _gh_user_response(login="user-b")
            resp2 = client.post("/airdrop/claim", json={
                "github_token": "token-b",
                "rustchain_wallet": "shared-wallet",
                "target_chain": "solana",
                "target_address": "Abcdefghijklmnopqrstuvwxyz123456789ABCDEFG",
            })
            assert resp2.status_code == 409
            assert resp2.get_json()["error"] == "wallet_already_used"
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestClaimSuccess ─────────────────────────────────────────────────────────

class TestClaimSuccess:
    def test_claim_creates_pending_record(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="claim-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 2}
            client = _fresh_client()

            resp = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "my-rtc-wallet",
                "target_chain": "base",
                "target_address": "0xABC1234567890123456789012345678901234567",
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["state"] == "pending"
            assert data["tier"] == "contributor"
            assert data["base_amount"] == 50
            assert "claim_id" in data
            assert data["claim_id"].startswith("claim_")
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestClaimStatus ──────────────────────────────────────────────────────────

class TestClaimStatus:
    def test_status_not_found(self):
        client = _fresh_client()
        resp = client.get("/airdrop/status/claim_nonexistent12345")
        assert resp.status_code == 404
        assert b"not found" in resp.data

    def test_status_returns_correct_data(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="status-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()

            resp = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "status-wallet",
                "target_chain": "solana",
                "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            })
            claim_id = resp.get_json()["claim_id"]

            resp2 = client.get(f"/airdrop/status/{claim_id}")
            assert resp2.status_code == 200
            data = resp2.get_json()
            assert data["claim_id"] == claim_id
            assert data["state"] == "pending"
            assert "events" in data
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestWalletClaims ─────────────────────────────────────────────────────────

class TestWalletClaims:
    def test_wallet_not_found(self):
        client = _fresh_client()
        resp = client.get("/airdrop/wallet/nonexistent-wallet-xyz")
        assert resp.status_code == 404

    def test_wallet_shows_claims(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="wallet-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()

            client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "query-wallet",
                "target_chain": "base",
                "target_address": "0xABC1234567890123456789012345678901234567",
            })

            resp2 = client.get("/airdrop/wallet/query-wallet")
            assert resp2.status_code == 200
            data = resp2.get_json()
            assert data["wallet"] == "query-wallet"
            assert len(data["claims"]) == 1
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestAdminProcess ─────────────────────────────────────────────────────────

class TestAdminProcess:
    def test_process_requires_admin(self):
        client = _fresh_client()
        resp = client.post("/airdrop/process", json={
            "claim_id": "claim_test123",
            "tx_hash": "0xabc",
        })
        assert resp.status_code == 403

    def test_process_completes_claim(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="admin-process-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()

            resp = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "admin-test-wallet",
                "target_chain": "base",
                "target_address": "0xABC1234567890123456789012345678901234567",
            })
            claim_id = resp.get_json()["claim_id"]

            resp2 = client.post("/airdrop/process",
                headers={"X-Admin-Key": "test-admin-key-1149"},
                json={"claim_id": claim_id, "tx_hash": "0xFINALMINT1234567890",
                      "notes": "wRTC minted successfully"}
            )
            assert resp2.status_code == 200, f"Got {resp2.status_code}: {resp2.get_json()}"
            data2 = resp2.get_json()
            assert data2["state"] == "complete"
            assert data2["tx_hash"] == "0xFINALMINT1234567890"

            resp3 = client.get(f"/airdrop/status/{claim_id}")
            assert resp3.get_json()["state"] == "complete"
            assert resp3.get_json()["tx_hash"] == "0xFINALMINT1234567890"
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars

    def test_process_nonexistent_claim(self):
        client = _fresh_client()
        resp = client.post("/airdrop/process",
            headers={"X-Admin-Key": "test-admin-key-1149"},
            json={"claim_id": "claim_does_not_exist", "tx_hash": "0xtx"}
        )
        assert resp.status_code == 404

    def test_process_already_completed(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="already-done-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()

            resp = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "double-process-wallet",
                "target_chain": "solana",
                "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            })
            claim_id = resp.get_json()["claim_id"]

            client.post("/airdrop/process",
                headers={"X-Admin-Key": "test-admin-key-1149"},
                json={"claim_id": claim_id, "tx_hash": "0xfirst"}
            )

            resp2 = client.post("/airdrop/process",
                headers={"X-Admin-Key": "test-admin-key-1149"},
                json={"claim_id": claim_id, "tx_hash": "0xsecond"}
            )
            assert resp2.status_code == 409
            assert b"already processed" in resp2.data
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestAdminReject ───────────────────────────────────────────────────────────

class TestAdminReject:
    def test_reject_pending_claim(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="reject-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()

            resp = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "reject-wallet",
                "target_chain": "solana",
                "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            })
            claim_id = resp.get_json()["claim_id"]

            resp2 = client.post("/airdrop/reject",
                headers={"X-Admin-Key": "test-admin-key-1149"},
                json={"claim_id": claim_id, "reason": "failed anti-Sybil check"}
            )
            assert resp2.status_code == 200
            assert resp2.get_json()["state"] == "failed"
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestLeaderboard ───────────────────────────────────────────────────────────

class TestLeaderboard:
    def test_leaderboard_empty(self):
        client = _fresh_client()
        resp = client.get("/airdrop/leaderboard")
        assert resp.status_code == 200
        assert resp.get_json()["leaderboard"] == []

    def test_leaderboard_with_claims(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="top-contributor")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 5}
            client = _fresh_client()

            resp = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "leaderboard-wallet",
                "target_chain": "base",
                "target_address": "0xABC1234567890123456789012345678901234567",
            })
            claim_id = resp.get_json()["claim_id"]

            client.post("/airdrop/process",
                headers={"X-Admin-Key": "test-admin-key-1149"},
                json={"claim_id": claim_id, "tx_hash": "0xLEADER123"}
            )

            resp2 = client.get("/airdrop/leaderboard")
            data2 = resp2.get_json()
            assert len(data2["leaderboard"]) == 1
            assert data2["leaderboard"][0]["github_username"] == "top-contributor"
            assert data2["leaderboard"][0]["tier"] == "core"
            assert data2["leaderboard"][0]["rank"] == 1
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestStats ─────────────────────────────────────────────────────────────────

class TestStats:
    def test_stats_empty(self):
        client = _fresh_client()
        resp = client.get("/airdrop/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_claims" in data
        assert data["allocations"]["solana"]["total"] == 30_000
        assert data["allocations"]["base"]["total"] == 20_000

    def test_stats_updates_after_claim(self):
        import bridge.airdrop_api as api
        orig_get = api._get_github_user
        orig_prs = api._check_github_prs
        orig_stars = api._check_github_repo_stars
        try:
            api._get_github_user = lambda t: _gh_user_response(login="stats-user")
            api._check_github_repo_stars = lambda t, u: 0
            api._check_github_prs = lambda t, u: {"merged_prs": 1}
            client = _fresh_client()

            resp = client.post("/airdrop/claim", json={
                "github_token": "valid-token",
                "rustchain_wallet": "stats-wallet",
                "target_chain": "solana",
                "target_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            })
            claim_id = resp.get_json()["claim_id"]

            client.post("/airdrop/process",
                headers={"X-Admin-Key": "test-admin-key-1149"},
                json={"claim_id": claim_id, "tx_hash": "0xSTATSTX"}
            )

            resp2 = client.get("/airdrop/stats")
            data2 = resp2.get_json()
            assert data2["total_claims"] == 1
            assert data2["by_tier"]["contributor"]["count"] == 1
            assert data2["by_chain"]["solana"]["claimed_count"] == 1
        finally:
            api._get_github_user = orig_get
            api._check_github_prs = orig_prs
            api._check_github_repo_stars = orig_stars


# ── TestTierIntegrity ────────────────────────────────────────────────────────

class TestTierIntegrity:
    def test_all_tiers_have_base_amount(self):
        from bridge.airdrop_api import TIER_DEFINITIONS
        expected = {
            "stargazer": 25, "contributor": 50, "builder": 100,
            "security": 150, "core": 200, "miner": 100,
        }
        for tier, expected_base in expected.items():
            assert tier in TIER_DEFINITIONS
            assert TIER_DEFINITIONS[tier]["base"] == expected_base

    def test_allocation_totals(self):
        from bridge.airdrop_api import SOLANA_ALLOCATION, BASE_ALLOCATION
        assert SOLANA_ALLOCATION == 30_000
        assert BASE_ALLOCATION == 20_000
        assert SOLANA_ALLOCATION + BASE_ALLOCATION == 50_000
