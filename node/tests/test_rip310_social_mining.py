# SPDX-License-Identifier: Apache-2.0
import unittest
from decimal import Decimal
from node.social_mining import SocialMiningPool, MIN_TIP_RTC


class TestRip310SocialMining(unittest.TestCase):
    def setUp(self):
        self.pool = SocialMiningPool()
        self.pool.deposit_bootstrap(Decimal("100.0"))
        self.pool.register_beacon("alice", "beacon-alice-001", initial_balance=Decimal("10.0"))
        self.pool.register_beacon("bob", "beacon-bob-002", initial_balance=Decimal("2.0"))

    def test_beacon_id_required_for_tipping_and_mining(self):
        with self.assertRaises(PermissionError):
            self.pool.process_tip("alice", "unverified_user", Decimal("1.0"))
        with self.assertRaises(PermissionError):
            self.pool.record_engagement("unverified_user", "moltbook_post", "2026-10-31")

    def test_tip_deducts_8_percent_platform_fee_to_pool(self):
        res = self.pool.process_tip("alice", "bob", Decimal("5.0"))
        self.assertEqual(res.fee_amount, Decimal("0.400000"))
        self.assertEqual(res.net_amount, Decimal("4.600000"))
        self.assertEqual(self.pool.user_balances["alice"], Decimal("5.000000"))
        self.assertEqual(self.pool.user_balances["bob"], Decimal("6.600000"))
        self.assertEqual(self.pool.balance, Decimal("100.400000"))

    def test_reaction_tip_lobster_emoji(self):
        res = self.pool.process_reaction_tip("alice", "bob", "🦞")
        self.assertEqual(res.gross_amount, Decimal("0.100000"))
        self.assertEqual(res.fee_amount, Decimal("0.008000"))
        self.assertEqual(res.net_amount, Decimal("0.092000"))

    def test_daily_frequency_caps_and_substantive_comment_length(self):
        # 5 posts/day cap on Moltbook
        for _ in range(5):
            r = self.pool.record_engagement("alice", "moltbook_post", "2026-10-31")
            self.assertEqual(r, Decimal("0.010000"))
        sixth = self.pool.record_engagement("alice", "moltbook_post", "2026-10-31")
        self.assertEqual(sixth, Decimal("0"))

        # Comment <= 50 chars gets 0 RTC
        short_comment = self.pool.record_engagement(
            "alice", "substantive_comment", "2026-10-31", content_text="Too short comment"
        )
        self.assertEqual(short_comment, Decimal("0"))

        # Comment > 50 chars earns 0.002 RTC
        long_comment = self.pool.record_engagement(
            "alice",
            "substantive_comment",
            "2026-10-31",
            content_text="This is a substantive technical comment exceeding fifty characters in length!",
        )
        self.assertEqual(long_comment, Decimal("0.002000"))

    def test_epoch_mining_redirection_and_rip309_metric_rotation(self):
        inflow = self.pool.redirect_epoch_mining_reward(Decimal("50.0"))
        self.assertEqual(inflow, Decimal("5.000000"))
        metric = self.pool.select_active_metric("epoch-2026-nonce-99")
        self.assertIn(
            metric,
            ("posting_frequency", "comment_depth", "upvote_quality", "cross_platform_consistency"),
        )


if __name__ == "__main__":
    unittest.main()
