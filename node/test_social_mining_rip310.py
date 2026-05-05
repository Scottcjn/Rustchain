#!/usr/bin/env python3
"""
Tests for RIP-310 Social Mining Protocol
========================================

Covers:
  Phase 1 — Tip Bot + Social Mining Pool
  Phase 2 — Automated Rewards + RIP-309 Anti-Gaming
  Phase 3 — Cross-Platform Tipping + Video Rewards
  Phase 4 — Quality Scoring + Leaderboards + Treasury
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

# Ensure the node directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "node"))

from social_mining_rip310 import (
    init_social_mining_db,
    register_beacon_user,
    verify_beacon_id,
    process_tip,
    record_social_action,
    award_video_upload,
    compute_cross_platform_bonus,
    update_content_quality,
    get_leaderboard,
    get_treasury_report,
    get_or_create_epoch,
    redirect_epoch_reward_to_social_pool,
    MINIMUM_TIP_URTC,
    TIP_FEE_PCT,
    UNIT,
    Platform,
    Action,
    TipMethod,
    CAP_MOLBOOK_POSTS,
    CAP_COMMENTS,
    MIN_COMMENT_LENGTH,
    MIN_VIDEO_DURATION_SEC,
)


class TestSocialMiningBase(unittest.TestCase):
    """Base test class with temporary database."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix="_social_mining.db")
        init_social_mining_db(self.db_path)
        # Register test users
        register_beacon_user("alice", "beacon_alice_001", self.db_path)
        register_beacon_user("bob", "beacon_bob_002", self.db_path)
        register_beacon_user("charlie", "beacon_charlie_003", self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)


# ─── Phase 1: Tipping Engine Tests ─────────────────────────────────────────

class TestPhase1Tipping(TestSocialMiningBase):

    def test_valid_tip(self):
        """Phase 1: Valid tip between two beacon-verified users."""
        result = process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=5_000_000,  # 5 RTC
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["amount_urtc"], 5_000_000)
        expected_fee = int(5_000_000 * TIP_FEE_PCT)
        self.assertEqual(result["fee_urtc"], expected_fee)
        self.assertEqual(result["net_urtc"], 5_000_000 - expected_fee)
        self.assertEqual(result["tipper_id"], "alice")
        self.assertEqual(result["recipient_id"], "bob")

    def test_tip_below_minimum(self):
        """Phase 1: Tip below minimum amount should fail."""
        result = process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=MINIMUM_TIP_URTC - 1,
            db_path=self.db_path,
        )
        self.assertFalse(result["success"])
        self.assertIn("minimum", result["error"].lower())

    def test_tip_tipper_no_beacon(self):
        """Phase 1: Tipper without Beacon ID should fail."""
        result = process_tip(
            tipper_id="unknown", tipper_beacon="",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=5_000_000,
            db_path=self.db_path,
        )
        self.assertFalse(result["success"])
        self.assertIn("tipper", result["error"].lower())

    def test_tip_recipient_no_beacon(self):
        """Phase 1: Recipient without Beacon ID should fail."""
        result = process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="unknown", recipient_beacon="",
            amount_urtc=5_000_000,
            db_path=self.db_path,
        )
        self.assertFalse(result["success"])
        self.assertIn("recipient", result["error"].lower())

    def test_tip_pool_receives_fee(self):
        """Phase 1: Social mining pool balance should increase by fee."""
        initial_balance = 0
        process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=10_000_000,  # 10 RTC
            db_path=self.db_path,
        )
        report = get_treasury_report(self.db_path)
        expected_fee = int(10_000_000 * TIP_FEE_PCT)
        self.assertEqual(report["balance_urtc"], expected_fee)
        self.assertEqual(report["total_inflow_urtc"], expected_fee)

    def test_emoji_tip(self):
        """Phase 1: Emoji-based micro-tip should work."""
        result = process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=100_000,  # 0.1 RTC
            tip_method=TipMethod.EMOJI.value,
            emoji="🦞",
            platform=Platform.MOLBOOK.value,
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["fee_urtc"], int(100_000 * TIP_FEE_PCT))

    def test_user_stats_updated(self):
        """Phase 1: Tipper and recipient stats should be updated."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=1_000_000,
            db_path=self.db_path,
        )

        alice = conn.execute(
            "SELECT total_tips_sent_urtc FROM user_social_stats WHERE user_id = 'alice'"
        ).fetchone()
        bob = conn.execute(
            "SELECT total_tips_received_urtc FROM user_social_stats WHERE user_id = 'bob'"
        ).fetchone()
        conn.close()

        self.assertEqual(alice["total_tips_sent_urtc"], 1_000_000)
        expected_net = 1_000_000 - int(1_000_000 * TIP_FEE_PCT)
        self.assertEqual(bob["total_tips_received_urtc"], expected_net)


# ─── Phase 2: Automated Social Rewards Tests ───────────────────────────────

class TestPhase2Rewards(TestSocialMiningBase):

    def test_moltbook_post_reward(self):
        """Phase 2: Moltbook post should earn reward."""
        result = record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="molt_post_001",
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["reward_urtc"], 0)
        self.assertIn("epoch_num", result)
        self.assertIn("metric_weight", result)

    def test_comment_reward(self):
        """Phase 2: Substantive comment should earn reward."""
        result = record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.COMMENT.value,
            content_id="comment_001",
            content_length=120,
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["reward_urtc"], 0)

    def test_short_comment_rejected(self):
        """Phase 2: Comment below minimum length should be rejected."""
        result = record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.COMMENT.value,
            content_id="comment_short",
            content_length=10,
            db_path=self.db_path,
        )
        self.assertFalse(result["success"])
        self.assertIn("short", result["error"].lower())

    def test_no_beacon_rejected(self):
        """Phase 2: Action without Beacon ID should be rejected."""
        result = record_social_action(
            user_id="unknown", beacon_id="",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="post_no_beacon",
            db_path=self.db_path,
        )
        self.assertFalse(result["success"])
        self.assertIn("beacon", result["error"].lower())

    def test_frequency_cap_moltbook(self):
        """Phase 2: Should enforce Moltbook post frequency cap."""
        for i in range(CAP_MOLBOOK_POSTS):
            result = record_social_action(
                user_id="alice", beacon_id="beacon_alice_001",
                platform=Platform.MOLBOOK.value,
                action_type=Action.POST.value,
                content_id=f"cap_post_{i}",
                db_path=self.db_path,
            )
            self.assertTrue(result["success"], f"Post {i} should succeed")

        # Next post should fail (cap reached)
        result = record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="cap_post_overflow",
            db_path=self.db_path,
        )
        self.assertFalse(result["success"])
        self.assertIn("cap", result["error"].lower())

    def test_pool_balance_decreases_on_reward(self):
        """Phase 2: Pool balance should decrease when rewards are paid."""
        # Fund the pool first
        process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=10_000_000,
            db_path=self.db_path,
        )
        initial_balance = get_treasury_report(self.db_path)["balance_urtc"]

        record_social_action(
            user_id="bob", beacon_id="beacon_bob_002",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="reward_test_post",
            db_path=self.db_path,
        )
        
        new_balance = get_treasury_report(self.db_path)["balance_urtc"]
        self.assertLess(new_balance, initial_balance)

    def test_rip309_epoch_created(self):
        """Phase 2: RIP-309 epoch should be automatically created."""
        record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="epoch_test_post",
            db_path=self.db_path,
        )
        epoch = get_or_create_epoch(db_path=self.db_path)
        self.assertIsNotNone(epoch["nonce"])
        self.assertIn("active_metrics", epoch)
        self.assertIn("metric_weights", epoch)
        self.assertGreaterEqual(len(epoch["active_metrics"]), 3)


# ─── Phase 3: Cross-Platform Tests ─────────────────────────────────────────

class TestPhase3CrossPlatform(TestSocialMiningBase):

    def test_video_upload_reward(self):
        """Phase 3: Valid video upload should earn reward."""
        result = award_video_upload(
            user_id="alice", beacon_id="beacon_alice_001",
            content_id="video_001",
            video_duration_sec=60,
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["reward_urtc"], 0)

    def test_video_too_short(self):
        """Phase 3: Video below minimum duration should be rejected."""
        result = award_video_upload(
            user_id="alice", beacon_id="beacon_alice_001",
            content_id="video_short",
            video_duration_sec=10,
            db_path=self.db_path,
        )
        self.assertFalse(result["success"])
        self.assertIn("short", result["error"].lower())

    def test_cross_platform_bonus(self):
        """Phase 3: User active on multiple platforms should get bonus."""
        # Post on Moltbook
        record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="molt_cross_001",
            db_path=self.db_path,
        )
        # Post on 4claw
        record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.FOURCLAW.value,
            action_type=Action.POST.value,
            content_id="4claw_cross_001",
            db_path=self.db_path,
        )

        bonus = compute_cross_platform_bonus("alice", self.db_path)
        self.assertGreater(bonus, 0)

    def test_video_upload_includes_cross_platform_bonus(self):
        """Phase 3: Video upload should include cross-platform bonus."""
        # First, establish activity on another platform
        record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="molt_for_bonus",
            db_path=self.db_path,
        )
        # Then upload video
        result = award_video_upload(
            user_id="alice", beacon_id="beacon_alice_001",
            content_id="video_bonus_test",
            video_duration_sec=60,
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        # Should have cross-platform bonus since active on 2 platforms
        self.assertIn("cross_platform_bonus_urtc", result)
        self.assertGreater(result["cross_platform_bonus_urtc"], 0)

    def test_single_platform_no_bonus(self):
        """Phase 3: User on single platform should get no bonus."""
        bonus = compute_cross_platform_bonus("bob", self.db_path)
        self.assertEqual(bonus, 0)


# ─── Phase 4: Quality & Leaderboard Tests ───────────────────────────────────

class TestPhase4Quality(TestSocialMiningBase):

    def test_content_quality_update(self):
        """Phase 4: Content quality score should update with engagement."""
        result = update_content_quality(
            content_id="post_quality_001",
            platform=Platform.MOLBOOK.value,
            user_id="alice",
            upvote_delta=5,
            tip_delta_urtc=500_000,
            comment_delta=3,
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["quality_score"], 0.5)
        self.assertLessEqual(result["quality_score"], 1.0)

    def test_content_quality_multiple_updates(self):
        """Phase 4: Quality score should increase with more engagement."""
        update_content_quality(
            content_id="post_quality_002",
            platform=Platform.MOLBOOK.value,
            user_id="alice",
            upvote_delta=1,
            db_path=self.db_path,
        )
        result1 = update_content_quality(
            content_id="post_quality_002",
            platform=Platform.MOLBOOK.value,
            user_id="alice",
            upvote_delta=10,
            db_path=self.db_path,
        )
        self.assertGreater(result1["quality_score"], 0.5)

    def test_leaderboard(self):
        """Phase 4: Leaderboard should return sorted users."""
        # Alice earns via tips and posts
        process_tip(
            tipper_id="bob", tipper_beacon="beacon_bob_002",
            recipient_id="alice", recipient_beacon="beacon_alice_001",
            amount_urtc=2_000_000,
            db_path=self.db_path,
        )
        record_social_action(
            user_id="alice", beacon_id="beacon_alice_001",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="leader_test_001",
            db_path=self.db_path,
        )

        leaderboard = get_leaderboard(db_path=self.db_path)
        self.assertGreater(len(leaderboard), 0)
        # Alice should be in the leaderboard
        alice_entry = [u for u in leaderboard if u["user_id"] == "alice"]
        self.assertEqual(len(alice_entry), 1)
        self.assertGreater(alice_entry[0]["total_earned_urtc"], 0)

    def test_leaderboard_limit(self):
        """Phase 4: Leaderboard should respect limit parameter."""
        leaderboard = get_leaderboard(limit=2, db_path=self.db_path)
        self.assertLessEqual(len(leaderboard), 2)

    def test_treasury_report(self):
        """Phase 4: Treasury report should show pool metrics."""
        # Fund pool
        process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=10_000_000,
            db_path=self.db_path,
        )
        report = get_treasury_report(self.db_path)
        self.assertIn("balance_urtc", report)
        self.assertIn("balance_rtc", report)
        self.assertIn("total_inflow_urtc", report)
        self.assertIn("inflow_24h_urtc", report)
        self.assertIn("active_users_24h", report)
        self.assertGreater(report["balance_urtc"], 0)
        self.assertGreater(report["balance_rtc"], 0)

    def test_epoch_reward_redirect(self):
        """Phase 4: Epoch reward redirect should fund pool."""
        result = redirect_epoch_reward_to_social_pool(
            epoch_reward_urtc=5_000_000,
            db_path=self.db_path,
        )
        self.assertTrue(result["success"])
        expected = int(5_000_000 * 0.10)
        self.assertEqual(result["redirected_urtc"], expected)

        report = get_treasury_report(self.db_path)
        self.assertEqual(report["balance_urtc"], expected)


# ─── Integration Tests ──────────────────────────────────────────────────────

class TestIntegration(TestSocialMiningBase):

    def test_full_tip_and_reward_cycle(self):
        """Integration: Full tip → fee → reward cycle."""
        # 1. Alice tips Bob
        tip_result = process_tip(
            tipper_id="alice", tipper_beacon="beacon_alice_001",
            recipient_id="bob", recipient_beacon="beacon_bob_002",
            amount_urtc=5_000_000,
            db_path=self.db_path,
        )
        self.assertTrue(tip_result["success"])
        
        fee = tip_result["fee_urtc"]
        net = tip_result["net_urtc"]

        # 2. Verify pool received fee
        report = get_treasury_report(self.db_path)
        self.assertEqual(report["balance_urtc"], fee)

        # 3. Bob posts content (earns reward from pool)
        post_result = record_social_action(
            user_id="bob", beacon_id="beacon_bob_002",
            platform=Platform.MOLBOOK.value,
            action_type=Action.POST.value,
            content_id="integration_post_001",
            db_path=self.db_path,
        )
        self.assertTrue(post_result["success"])
        reward = post_result["reward_urtc"]

        # 4. Pool balance should be fee - reward
        report2 = get_treasury_report(self.db_path)
        self.assertEqual(report2["balance_urtc"], fee - reward)

    def test_sustainability_check(self):
        """Integration: Simulate sustainable economy (tips > rewards)."""
        # 10 users each tip 1 RTC → 800,000 uRTC fees total
        for i in range(10):
            user_id = f"user_{i}"
            beacon_id = f"beacon_user_{i:03d}"
            register_beacon_user(user_id, beacon_id, self.db_path)
            
            process_tip(
                tipper_id=user_id, tipper_beacon=beacon_id,
                recipient_id="alice", recipient_beacon="beacon_alice_001",
                amount_urtc=1_000_000,
                db_path=self.db_path,
            )

        # Pool should have significant inflow (10 * 1M * 8% = 800,000 uRTC)
        report = get_treasury_report(self.db_path)
        self.assertEqual(report["total_inflow_urtc"], 800_000)
        # Should be sustainable (positive net)
        self.assertGreater(report["balance_urtc"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
