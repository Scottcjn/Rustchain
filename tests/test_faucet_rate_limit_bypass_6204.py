"""Tests for faucet rate-limit bypass fix (#6204)"""
import os
import tempfile
import pytest
from tools.testnet_faucet import _limit_for_identity, create_app


class TestLimitForIdentity:
    """Test the _limit_for_identity function with the fix."""

    def test_no_username_gets_anonymous_limit(self):
        assert _limit_for_identity(None, None) == 0.5

    def test_verified_old_account_gets_max_limit(self):
        assert _limit_for_identity("realuser", 365) == 2.0

    def test_verified_new_account_gets_standard_limit(self):
        assert _limit_for_identity("realuser", 30) == 1.0

    def test_unverified_username_gets_anonymous_limit(self):
        """The bug fix: unverified GitHub usernames should fall back to 0.5"""
        assert _limit_for_identity("fakeuser", None) == 0.5

    def test_empty_string_username_gets_anonymous_limit(self):
        assert _limit_for_identity("", None) == 0.5


class TestFaucetRateLimitBypass:
    """Integration tests for the faucet rate-limit bypass scenario."""

    def _make_app(self, tmp_path):
        db_path = str(tmp_path / "faucet_test.db")
        return create_app({"DB_PATH": db_path, "DRY_RUN": True}), db_path

    def test_unverified_username_gets_anonymous_drip_amount(self, tmp_path):
        """Unverified GitHub username should receive 0.5 RTC, not 1.0"""
        app, _ = self._make_app(tmp_path)
        with app.test_client() as client:
            resp = client.post("/faucet/drip", json={
                "wallet": "RTC1TestWallet1234567890abcdef",
                "github_username": "nonexistent-user-xyz"
            })
            data = resp.get_json()
            if resp.status_code == 200:
                assert data.get("amount") == 0.5, (
                    f"Unverified user should get 0.5, got {data.get('amount')}"
                )

    def test_rotating_fake_usernames_still_ip_limited(self, tmp_path):
        """The core bug: rotating fake GitHub usernames should NOT bypass IP rate limit"""
        app, _ = self._make_app(tmp_path)
        with app.test_client() as client:
            amounts = []
            # Request with fake username 1
            resp1 = client.post("/faucet/drip", json={
                "wallet": "RTC1Wallet1Aaaaaaaaaaaaaaaaaaaa",
                "github_username": "ghost-user-1-fake-xyz"
            })
            if resp1.status_code == 200:
                amounts.append(resp1.get_json().get("amount"))

            # Request with fake username 2 (same IP, different name)
            resp2 = client.post("/faucet/drip", json={
                "wallet": "RTC1Wallet2Bbbbbbbbbbbbbbbbbbbb",
                "github_username": "ghost-user-2-fake-xyz"
            })
            if resp2.status_code == 200:
                amounts.append(resp2.get_json().get("amount"))

            # All unverified usernames should get 0.5 amount
            for amt in amounts:
                assert amt == 0.5, f"Unverified user should get 0.5 RTC, got {amt}"

            # Total should not exceed 0.5 daily limit (at most 1 drip)
            total = sum(amounts)
            assert total <= 0.5 + 0.01, f"Total drips {total} should not exceed 0.5 limit"
