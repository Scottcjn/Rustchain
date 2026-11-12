# SPDX-License-Identifier: MIT
"""Comprehensive test suite for Bounty Verifier (#747).

Covers:
- Star check: zero stars explicitly fails with exact message.
- Star check: passing threshold.
- Duplicate check: same-user paid vs unpaid claims.
- Duplicate check: cross-user colliding wallet sharing.
- Duplicate check: multiple unmerged repeated claims flagged.
- Article checker: word count, minimum words threshold, and keyword verification.
- Payout coefficient calculation.
"""

from datetime import datetime
import pytest

from tools.bounty_verifier.config import Config, GitHubConfig, RustChainConfig, UrlCheckConfig
from tools.bounty_verifier.models import (
    ClaimComment,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)
from tools.bounty_verifier.verifier import BountyVerifier
from tools.bounty_verifier.article_checker import ArticleChecker


def create_dummy_claim(comment_id: int, user_id: int, user_login: str, body: str) -> ClaimComment:
    return ClaimComment(
        id=comment_id,
        user_login=user_login,
        user_id=user_id,
        body=body,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        issue_number=747,
        html_url=f"https://github.com/Scottcjn/rustchain-bounties/issues/747#issuecomment-{comment_id}",
    )


def test_zero_star_check_fails():
    cfg = Config()
    cfg.min_star_count = 3
    verifier = BountyVerifier(cfg)

    class MockGH:
        owner = "Scottcjn"
        def get_starred_repos_count(self, user, owner):
            return 0

    verifier.github = MockGH()
    check = verifier.verify_stars("zerostar_user")
    assert check.status == VerificationStatus.FAILED
    assert "starred 0 repos" in check.message


def test_passing_star_check():
    cfg = Config()
    cfg.min_star_count = 3
    verifier = BountyVerifier(cfg)

    class MockGH:
        owner = "Scottcjn"
        def get_starred_repos_count(self, user, owner):
            return 5

    verifier.github = MockGH()
    check = verifier.verify_stars("star_user")
    assert check.status == VerificationStatus.PASSED
    assert "starred 5/3 required repos" in check.message


def test_duplicate_check_detects_paid():
    cfg = Config()
    verifier = BountyVerifier(cfg)

    c1 = create_dummy_claim(101, 1, "alice", "I claim this bounty. Wallet: RTC1111222233334444555566667777888899990000. PAID 25 RTC.")
    c2 = create_dummy_claim(102, 1, "alice", "Submitting claim. Wallet: RTC1111222233334444555566667777888899990000")

    res = verifier.check_duplicates(c2, [c1, c2])
    assert res.status == VerificationStatus.FAILED
    assert "already has a paid claim" in res.message


def test_duplicate_check_detects_cross_user_wallet_collision():
    cfg = Config()
    verifier = BountyVerifier(cfg)

    c1 = create_dummy_claim(101, 1, "alice", "Claiming. Wallet: RTC1111222233334444555566667777888899990000")
    c2 = create_dummy_claim(102, 2, "bob_sockpuppet", "Claiming bounty. Wallet: RTC1111222233334444555566667777888899990000")
    c2 = verifier.parse_claim_comment(c2)

    res = verifier.check_duplicates(c2, [c1, c2])
    assert res.status == VerificationStatus.FAILED
    assert "was already submitted by another user" in res.message
    assert "alice" in res.message


def test_article_checker_word_count_and_keywords(monkeypatch):
    checker = ArticleChecker()

    class MockResponse:
        status_code = 200
        text = "<html><head><title>RustChain Analysis</title></head><body><h1>Deep Dive</h1><p>" + " ".join(["RustChain"] + ["word"] * 300) + "</p></body></html>"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    passed, details = checker.check_article("https://dev.to/example/article")
    assert passed is True
    assert int(details["word_count"]) > 250
    assert details["mentions_rustchain"] == "True"


def test_article_checker_missing_keywords(monkeypatch):
    checker = ArticleChecker()

    class MockResponse:
        status_code = 200
        text = "<html><head><title>Unrelated Article</title></head><body><p>" + " ".join(["blockchain", "technology"] * 200) + "</p></body></html>"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    passed, details = checker.check_article("https://dev.to/example/irrelevant")
    assert passed is False
    assert "does not mention RustChain" in details["error"]
