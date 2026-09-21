"""
test_award_rtc.py — Unit tests for the RTC auto-bounty action.

Run with:  python3 -m pytest test_award_rtc.py -v
   or:     python3 test_award_rtc.py
"""

from __future__ import annotations

import unittest

from award_rtc import (
    BountyClaim,
    Verdict,
    allocate_pool,
    parse_claim,
    to_json,
    verify_claim,
    verify_engagement_claim,
)


DISCLOSURE = "I received RTC compensation for this post."


class TestParseClaim(unittest.TestCase):
    def test_extracts_wallet_and_url(self):
        body = (
            "Starred and posted!\n"
            "Post: https://x.com/me/status/123\n"
            "Wallet: RTC1abcDEFghijKLMnopQRS\n"
        )
        claim = parse_claim(body, author="alice")
        self.assertEqual(claim.claimant, "alice")
        self.assertEqual(claim.wallet, "RTC1abcDEFghijKLMnopQRS")
        self.assertEqual(claim.post_url, "https://x.com/me/status/123")

    def test_no_wallet(self):
        claim = parse_claim("Post: https://x.com/me/status/1", author="bob")
        self.assertIsNone(claim.wallet)
        self.assertEqual(claim.post_url, "https://x.com/me/status/1")


class TestEngagementVerifier(unittest.TestCase):
    def _valid_body(self) -> str:
        return (
            "What I reviewed: https://github.com/Scottcjn/Rustchain/blob/main/src/miner/oscillator_drift.rs\n"
            "Why I liked it: The oscillator-drift fingerprinting is a genuinely novel way to "
            "reward vintage hardware instead of burning energy on SHA-256.\n"
            f"{DISCLOSURE}\n"
            "Post: https://x.com/me/status/999\n"
            "Wallet: RTC1abcDEFghijKLMnopQRS\n"
        )

    def test_valid_claim(self):
        claim = parse_claim(self._valid_body(), author="alice")
        verdict = verify_engagement_claim(claim)
        self.assertTrue(verdict.valid, msg=verdict.reason)
        self.assertTrue(verdict.claim.disclosure)
        self.assertIsNotNone(verdict.claim.reviewed)
        self.assertIsNotNone(verdict.claim.reason)

    def test_missing_disclosure_rejected(self):
        body = self._valid_body().replace(DISCLOSURE, "Thanks for the bounty!")
        claim = parse_claim(body, author="alice")
        verdict = verify_engagement_claim(claim)
        self.assertFalse(verdict.valid)
        self.assertIn("disclosure", verdict.reason.lower())

    def test_missing_reviewed_rejected(self):
        body = (
            "Why I liked it: The oscillator-drift fingerprinting is a genuinely novel way to "
            "reward vintage hardware instead of burning energy on SHA-256.\n"
            f"{DISCLOSURE}\n"
            "Post: https://x.com/me/status/999\n"
        )
        claim = parse_claim(body, author="alice")
        verdict = verify_engagement_claim(claim)
        self.assertFalse(verdict.valid)
        self.assertIn("reviewed", verdict.reason.lower())

    def test_generic_reason_rejected(self):
        body = (
            "What I reviewed: https://github.com/Scottcjn/Rustchain/blob/main/README.md\n"
            "Why I liked it: Great project\n"
            f"{DISCLOSURE}\n"
            "Post: https://x.com/me/status/999\n"
        )
        claim = parse_claim(body, author="alice")
        verdict = verify_engagement_claim(claim)
        self.assertFalse(verdict.valid)
        self.assertIn("generic", verdict.reason.lower())

    def test_short_reason_rejected(self):
        body = (
            "What I reviewed: https://github.com/Scottcjn/Rustchain/blob/main/README.md\n"
            "Why I liked it: cool\n"
            f"{DISCLOSURE}\n"
            "Post: https://x.com/me/status/999\n"
        )
        claim = parse_claim(body, author="alice")
        verdict = verify_engagement_claim(claim)
        self.assertFalse(verdict.valid)
        self.assertIn("short", verdict.reason.lower())

    def test_missing_post_url_rejected(self):
        body = (
            "What I reviewed: https://github.com/Scottcjn/Rustchain/blob/main/README.md\n"
            "Why I liked it: The oscillator-drift fingerprinting is a genuinely novel way to "
            "reward vintage hardware instead of burning energy on SHA-256.\n"
            f"{DISCLOSURE}\n"
            "Wallet: RTC1abcDEFghijKLMnopQRS\n"
        )
        claim = parse_claim(body, author="alice")
        verdict = verify_engagement_claim(claim)
        self.assertFalse(verdict.valid)
        self.assertIn("post url", verdict.reason.lower())

    def test_missing_wallet_warns_but_still_valid(self):
        body = (
            "What I reviewed: https://github.com/Scottcjn/Rustchain/blob/main/README.md\n"
            "Why I liked it: The oscillator-drift fingerprinting is a genuinely novel way to "
            "reward vintage hardware instead of burning energy on SHA-256.\n"
            f"{DISCLOSURE}\n"
            "Post: https://x.com/me/status/999\n"
        )
        claim = parse_claim(body, author="alice")
        verdict = verify_engagement_claim(claim)
        self.assertTrue(verdict.valid, msg=verdict.reason)
        self.assertTrue(any("wallet" in w.lower() for w in verdict.warnings))


class TestPoolAllocation(unittest.TestCase):
    def _claim(self, name: str) -> BountyClaim:
        return parse_claim(
            (
                "What I reviewed: https://github.com/Scottcjn/Rustchain/blob/main/README.md\n"
                "Why I liked it: The oscillator-drift fingerprinting is a genuinely novel way to "
                "reward vintage hardware instead of burning energy on SHA-256.\n"
                f"{DISCLOSURE}\n"
                f"Post: https://x.com/{name}/status/1\n"
                f"Wallet: RTC1{name}abcDEFghijKLMnopQRS\n"
            ),
            author=name,
        )

    def test_pool_exhausts_at_100(self):
        # Pool of 300 RTC at 3 RTC/claim = exactly 100 slots.
        claims = [self._claim(f"user{i}") for i in range(105)]
        verdicts = allocate_pool(claims, pool=300, per_claim=3)
        valid = sum(1 for v in verdicts if v.valid)
        self.assertEqual(valid, 100)
        # The 101st..105th must be rejected for pool exhaustion.
        for v in verdicts[100:]:
            self.assertFalse(v.valid)
            self.assertIn("pool exhausted", v.reason.lower())

    def test_first_come_first_served_order(self):
        claims = [self._claim(f"user{i}") for i in range(3)]
        verdicts = allocate_pool(claims, pool=6, per_claim=3)
        self.assertTrue(verdicts[0].valid)
        self.assertTrue(verdicts[1].valid)
        self.assertFalse(verdicts[2].valid)


class TestSerialization(unittest.TestCase):
    def test_to_json_roundtrip(self):
        claim = parse_claim(
            "Post: https://x.com/me/1\nWallet: RTC1abcDEFghijKLMnopQRS",
            author="alice",
        )
        verdicts = [verify_claim(claim)]
        out = to_json(verdicts)
        self.assertIn("alice", out)
        self.assertIn("RTC1abcDEFghijKLMnopQRS", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
