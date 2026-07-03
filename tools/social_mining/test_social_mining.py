"""Comprehensive tests for RIP-310 Social Mining Protocol."""

import time
import unittest
from unittest.mock import patch

from social_mining import (
    ActionType,
    BeaconID,
    Epoch,
    EpochState,
    Platform,
    RewardRecord,
    SocialAction,
    SocialMiningEngine,
    TreasuryPool,
)
from platform_rewards import (
    REWARD_TABLE,
    TIP_FEE_RATE,
    PlatformRewardCalculator,
    RewardRule,
)
from anti_gaming import (
    FREQUENCY_LIMITS,
    METRIC_ROTATION_WEIGHTS,
    MIN_COMMENT_LENGTH,
    AntiGamingModule,
    FrequencyTracker,
)


class TestBeaconID(unittest.TestCase):
    def test_valid_beacon(self):
        beacon = BeaconID(beacon_hash="a" * 64, public_key="test_key")
        self.assertTrue(beacon.verify())

    def test_inactive_beacon(self):
        beacon = BeaconID(beacon_hash="a" * 64, public_key="test_key", is_active=False)
        self.assertFalse(beacon.verify())

    def test_short_hash_rejected(self):
        beacon = BeaconID(beacon_hash="short", public_key="test_key")
        self.assertFalse(beacon.verify())

    def test_empty_hash_rejected(self):
        beacon = BeaconID(beacon_hash="", public_key="test_key")
        self.assertFalse(beacon.verify())

    def test_generate_from_key(self):
        beacon = BeaconID.generate_from_key("my_public_key")
        self.assertEqual(len(beacon.beacon_hash), 64)
        self.assertTrue(beacon.verify())

    def test_deterministic_generation(self):
        b1 = BeaconID.generate_from_key("key")
        b2 = BeaconID.generate_from_key("key")
        self.assertEqual(b1.beacon_hash, b2.beacon_hash)


class TestTreasuryPool(unittest.TestCase):
    def test_deposit(self):
        pool = TreasuryPool()
        pool.deposit(100.0)
        self.assertEqual(pool.balance, 100.0)
        self.assertEqual(pool.total_inflow, 100.0)

    def test_withdraw(self):
        pool = TreasuryPool()
        pool.deposit(100.0)
        self.assertTrue(pool.withdraw_reward(30.0))
        self.assertEqual(pool.balance, 70.0)
        self.assertEqual(pool.total_outflow, 30.0)

    def test_insufficient_withdraw(self):
        pool = TreasuryPool()
        pool.deposit(10.0)
        self.assertFalse(pool.withdraw_reward(20.0))
        self.assertEqual(pool.balance, 10.0)

    def test_tip_fee_collection(self):
        pool = TreasuryPool()
        fee = pool.collect_tip_fee(100.0)
        self.assertAlmostEqual(fee, 8.0)
        self.assertAlmostEqual(pool.balance, 8.0)

    def test_tip_fee_rate(self):
        self.assertAlmostEqual(TIP_FEE_RATE, 0.08)


class TestEpoch(unittest.TestCase):
    def test_active_epoch(self):
        now = time.time()
        epoch = Epoch(epoch_id=0, start_time=now, end_time=now + 86400)
        self.assertTrue(epoch.is_active())
        self.assertTrue(epoch.is_within(now))

    def test_settle(self):
        now = time.time()
        epoch = Epoch(epoch_id=0, start_time=now, end_time=now + 86400)
        epoch.settle()
        self.assertEqual(epoch.state, EpochState.SETTLED)
        self.assertFalse(epoch.is_active())

    def test_finalize(self):
        now = time.time()
        epoch = Epoch(epoch_id=0, start_time=now, end_time=now + 86400)
        epoch.settle()
        epoch.finalize()
        self.assertEqual(epoch.state, EpochState.FINALIZED)

    def test_cannot_settle_finalized(self):
        now = time.time()
        epoch = Epoch(epoch_id=0, start_time=now, end_time=now + 86400)
        epoch.state = EpochState.FINALIZED
        epoch.settle()
        self.assertEqual(epoch.state, EpochState.FINALIZED)


class TestSocialMiningEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SocialMiningEngine()

    def test_register_beacon(self):
        beacon = self.engine.register_beacon("pub_key_123")
        self.assertIn(beacon.beacon_hash, self.engine.beacons)
        self.assertTrue(beacon.verify())

    def test_get_beacon(self):
        beacon = self.engine.register_beacon("pub_key_456")
        retrieved = self.engine.get_beacon(beacon.beacon_hash)
        self.assertEqual(retrieved.beacon_hash, beacon.beacon_hash)

    def test_start_epoch(self):
        epoch = self.engine.start_epoch(86400)
        self.assertTrue(epoch.is_active())
        self.assertEqual(self.engine.current_epoch.epoch_id, 0)

    def test_settle_current_epoch(self):
        self.engine.start_epoch(86400)
        settled = self.engine.settle_current_epoch()
        self.assertIsNotNone(settled)
        self.assertEqual(settled.state, EpochState.SETTLED)
        self.assertIsNone(self.engine.current_epoch)

    def test_record_reward(self):
        self.engine.start_epoch(86400)
        beacon = BeaconID(beacon_hash="a" * 64, public_key="key")
        action = SocialAction(
            action_id="act_1",
            platform=Platform.MOLTBOOK,
            action_type=ActionType.POST,
            beacon=beacon,
            content_hash="hash1",
        )
        record = self.engine.record_reward(action, 0.01)
        self.assertEqual(record.rtc_amount, 0.01)
        self.assertEqual(record.epoch_id, 0)

    def test_reward_without_epoch_raises(self):
        beacon = BeaconID(beacon_hash="a" * 64, public_key="key")
        action = SocialAction(
            action_id="act_1",
            platform=Platform.MOLTBOOK,
            action_type=ActionType.POST,
            beacon=beacon,
            content_hash="hash1",
        )
        with self.assertRaises(RuntimeError):
            self.engine.record_reward(action, 0.01)

    def test_rewards_for_epoch(self):
        self.engine.start_epoch(86400)
        beacon = BeaconID(beacon_hash="a" * 64, public_key="key")
        for i in range(3):
            action = SocialAction(
                action_id=f"act_{i}",
                platform=Platform.MOLTBOOK,
                action_type=ActionType.POST,
                beacon=beacon,
                content_hash=f"hash{i}",
            )
            self.engine.record_reward(action, 0.01)
        rewards = self.engine.get_rewards_for_epoch(0)
        self.assertEqual(len(rewards), 3)
        self.assertAlmostEqual(self.engine.total_rewards_for_epoch(0), 0.03)

    def test_rewards_for_beacon(self):
        self.engine.start_epoch(86400)
        b1 = BeaconID(beacon_hash="a" * 64, public_key="k1")
        b2 = BeaconID(beacon_hash="b" * 64, public_key="k2")
        a1 = SocialAction(
            action_id="a1", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=b1, content_hash="h1",
        )
        a2 = SocialAction(
            action_id="a2", platform=Platform.FOURCLAW,
            action_type=ActionType.THREAD, beacon=b2, content_hash="h2",
        )
        self.engine.record_reward(a1, 0.01)
        self.engine.record_reward(a2, 0.01)
        self.assertEqual(len(self.engine.get_rewards_for_beacon(b1.beacon_hash)), 1)
        self.assertEqual(len(self.engine.get_rewards_for_beacon(b2.beacon_hash)), 1)


class TestRewardTable(unittest.TestCase):
    def test_moltbook_post_rate(self):
        rule = REWARD_TABLE[(Platform.MOLTBOOK, ActionType.POST)]
        self.assertAlmostEqual(rule.rtc_reward, 0.01)
        self.assertEqual(rule.daily_cap, 5)

    def test_fourclaw_thread_rate(self):
        rule = REWARD_TABLE[(Platform.FOURCLAW, ActionType.THREAD)]
        self.assertAlmostEqual(rule.rtc_reward, 0.01)
        self.assertEqual(rule.daily_cap, 5)

    def test_botube_video_rate(self):
        rule = REWARD_TABLE[(Platform.BOTUBE, ActionType.VIDEO)]
        self.assertAlmostEqual(rule.rtc_reward, 0.05)
        self.assertEqual(rule.daily_cap, 3)

    def test_comment_rate(self):
        for platform in Platform:
            rule = REWARD_TABLE[(platform, ActionType.COMMENT)]
            self.assertAlmostEqual(rule.rtc_reward, 0.002)
            self.assertEqual(rule.daily_cap, 20)

    def test_upvote_rate(self):
        for platform in Platform:
            rule = REWARD_TABLE[(platform, ActionType.UPVOTE_RECEIVED)]
            self.assertAlmostEqual(rule.rtc_reward, 0.001)
            self.assertIsNone(rule.daily_cap)


class TestPlatformRewardCalculator(unittest.TestCase):
    def setUp(self):
        self.engine = SocialMiningEngine()
        self.calc = PlatformRewardCalculator(self.engine)
        self.engine.start_epoch(86400)
        self.beacon = BeaconID(beacon_hash="a" * 64, public_key="key")

    def test_moltbook_post_reward(self):
        action = SocialAction(
            action_id="p1", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=self.beacon, content_hash="h1",
        )
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 0.01)

    def test_comment_too_short(self):
        action = SocialAction(
            action_id="c1", platform=Platform.MOLTBOOK,
            action_type=ActionType.COMMENT, beacon=self.beacon,
            content_hash="h2", comment_length=30,
        )
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 0.0)

    def test_comment_valid(self):
        action = SocialAction(
            action_id="c2", platform=Platform.MOLTBOOK,
            action_type=ActionType.COMMENT, beacon=self.beacon,
            content_hash="h3", comment_length=51,
        )
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 0.002)

    def test_tip_reward(self):
        action = SocialAction(
            action_id="t1", platform=Platform.MOLTBOOK,
            action_type=ActionType.TIP_RECEIVED, beacon=self.beacon,
            content_hash="h4", tip_amount=10.0,
        )
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 9.2)  # 10 * (1 - 0.08)
        self.assertAlmostEqual(self.engine.treasury.balance, 0.8)

    def test_tip_zero_amount(self):
        action = SocialAction(
            action_id="t2", platform=Platform.MOLTBOOK,
            action_type=ActionType.TIP_RECEIVED, beacon=self.beacon,
            content_hash="h5", tip_amount=0.0,
        )
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 0.0)

    def test_invalid_beacon_rejected(self):
        inactive = BeaconID(beacon_hash="b" * 64, public_key="k", is_active=False)
        action = SocialAction(
            action_id="x1", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=inactive, content_hash="h6",
        )
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 0.0)

    def test_daily_cap_enforced(self):
        for i in range(5):
            action = SocialAction(
                action_id=f"cap_{i}", platform=Platform.MOLTBOOK,
                action_type=ActionType.POST, beacon=self.beacon,
                content_hash=f"cap_h{i}",
            )
            self.assertAlmostEqual(self.calc.process_action(action), 0.01)
        overflow = SocialAction(
            action_id="cap_overflow", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=self.beacon,
            content_hash="cap_overflow_h",
        )
        self.assertAlmostEqual(self.calc.process_action(overflow), 0.0)


class TestAntiGaming(unittest.TestCase):
    def setUp(self):
        self.engine = SocialMiningEngine()
        self.anti = AntiGamingModule(self.engine)
        self.beacon = BeaconID(beacon_hash="a" * 64, public_key="key")

    def test_frequency_cap_check(self):
        allowed, count = self.anti.check_frequency_cap(
            self.beacon.beacon_hash, ActionType.POST
        )
        self.assertTrue(allowed)
        self.assertEqual(count, 0)

    def test_frequency_limit_exists(self):
        self.assertEqual(FREQUENCY_LIMITS[ActionType.POST], 5)
        self.assertEqual(FREQUENCY_LIMITS[ActionType.THREAD], 5)
        self.assertEqual(FREQUENCY_LIMITS[ActionType.VIDEO], 3)
        self.assertEqual(FREQUENCY_LIMITS[ActionType.COMMENT], 20)

    def test_content_quality_pass(self):
        action = SocialAction(
            action_id="q1", platform=Platform.MOLTBOOK,
            action_type=ActionType.COMMENT, beacon=self.beacon,
            content_hash="q1h", comment_length=51,
        )
        self.assertTrue(self.anti.check_content_quality(action))

    def test_content_quality_fail(self):
        action = SocialAction(
            action_id="q2", platform=Platform.MOLTBOOK,
            action_type=ActionType.COMMENT, beacon=self.beacon,
            content_hash="q2h", comment_length=50,
        )
        self.assertFalse(self.anti.check_content_quality(action))

    def test_non_comment_always_passes_quality(self):
        action = SocialAction(
            action_id="q3", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=self.beacon,
            content_hash="q3h", comment_length=5,
        )
        self.assertTrue(self.anti.check_content_quality(action))

    def test_duplicate_content_detected(self):
        action = SocialAction(
            action_id="d1", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=self.beacon,
            content_hash="dup_hash",
        )
        self.assertTrue(self.anti.check_duplicate_content(action))
        self.assertFalse(self.anti.check_duplicate_content(action))

    def test_validate_action_passes(self):
        action = SocialAction(
            action_id="v1", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=self.beacon,
            content_hash="v1h",
        )
        allowed, reason = self.anti.validate_action(action)
        self.assertTrue(allowed)
        self.assertEqual(reason, "passed")

    def test_validate_action_invalid_beacon(self):
        inactive = BeaconID(beacon_hash="b" * 64, public_key="k", is_active=False)
        action = SocialAction(
            action_id="v2", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=inactive, content_hash="v2h",
        )
        allowed, reason = self.anti.validate_action(action)
        self.assertFalse(allowed)
        self.assertIn("Beacon", reason)

    def test_validate_action_flagged_beacon(self):
        self.anti.flag_beacon(self.beacon.beacon_hash)
        action = SocialAction(
            action_id="v3", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=self.beacon, content_hash="v3h",
        )
        allowed, _ = self.anti.validate_action(action)
        self.assertFalse(allowed)

    def test_flag_unflag_beacon(self):
        self.anti.flag_beacon(self.beacon.beacon_hash)
        self.assertIn(self.beacon.beacon_hash, self.anti.flagged_beacons)
        self.anti.unflag_beacon(self.beacon.beacon_hash)
        self.assertNotIn(self.beacon.beacon_hash, self.anti.flagged_beacons)

    def test_metric_rotation_weights(self):
        w0 = self.anti.get_metric_weights(0)
        w1 = self.anti.get_metric_weights(1)
        w2 = self.anti.get_metric_weights(2)
        w3 = self.anti.get_metric_weights(3)
        self.assertNotEqual(w0["engagement"], w1["engagement"])
        self.assertEqual(w0, w3)

    def test_rotation_score_calculation(self):
        score = self.anti.calculate_rotation_score(0, 1.0, 1.0, 1.0)
        self.assertAlmostEqual(score, 1.0)
        score2 = self.anti.calculate_rotation_score(0, 1.0, 0.0, 0.0)
        self.assertAlmostEqual(score2, 0.4)

    def test_frequency_tracker(self):
        tracker = FrequencyTracker()
        for _ in range(3):
            tracker.increment("beacon1", ActionType.POST)
        self.assertEqual(tracker.get_count("beacon1", ActionType.POST), 3)


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests."""

    def setUp(self):
        self.engine = SocialMiningEngine()
        self.calc = PlatformRewardCalculator(self.engine)
        self.anti = AntiGamingModule(self.engine)
        self.beacon = self.engine.register_beacon("integration_pub_key")
        self.engine.start_epoch(86400)

    def test_full_flow_post(self):
        self.engine.treasury.deposit(100.0)
        action = SocialAction(
            action_id="int_1", platform=Platform.MOLTBOOK,
            action_type=ActionType.POST, beacon=self.beacon,
            content_hash="int_h1",
        )
        allowed, _ = self.anti.validate_action(action)
        self.assertTrue(allowed)
        self.anti.record_action(action)
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 0.01)
        self.assertAlmostEqual(self.engine.treasury.balance, 99.99)

    def test_full_flow_tip(self):
        action = SocialAction(
            action_id="int_t1", platform=Platform.MOLTBOOK,
            action_type=ActionType.TIP_RECEIVED, beacon=self.beacon,
            content_hash="int_th1", tip_amount=50.0,
        )
        allowed, _ = self.anti.validate_action(action)
        self.assertTrue(allowed)
        reward = self.calc.process_action(action)
        self.assertAlmostEqual(reward, 46.0)
        self.assertAlmostEqual(self.engine.treasury.balance, 4.0)

    def test_frequency_cap_integration(self):
        video_cap = FREQUENCY_LIMITS[ActionType.VIDEO]  # 3
        for i in range(video_cap):
            action = SocialAction(
                action_id=f"int_cap_{i}", platform=Platform.BOTUBE,
                action_type=ActionType.VIDEO, beacon=self.beacon,
                content_hash=f"int_cap_h{i}",
            )
            self.anti.validate_action(action)
            self.anti.record_action(action)
            self.assertAlmostEqual(self.calc.process_action(action), 0.05)
        overflow = SocialAction(
            action_id="int_cap_overflow", platform=Platform.BOTUBE,
            action_type=ActionType.VIDEO, beacon=self.beacon,
            content_hash="int_cap_overflow_h",
        )
        allowed, reason = self.anti.validate_action(overflow)
        self.assertFalse(allowed)
        self.assertIn("cap", reason.lower())

    def test_epoch_settlement(self):
        for i in range(3):
            action = SocialAction(
                action_id=f"ep_{i}", platform=Platform.FOURCLAW,
                action_type=ActionType.THREAD, beacon=self.beacon,
                content_hash=f"ep_h{i}",
            )
            self.anti.validate_action(action)
            self.calc.process_action(action)
        settled = self.engine.settle_current_epoch()
        self.assertIsNotNone(settled)
        self.assertEqual(len(self.engine.get_rewards_for_epoch(0)), 3)
        self.assertAlmostEqual(self.engine.total_rewards_for_epoch(0), 0.03)


if __name__ == "__main__":
    unittest.main()
