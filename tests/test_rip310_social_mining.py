"""
Unit test suite for RIP-310 Social Mining Protocol.
Tests Beacon ID attestation, tip bot fee routing, treasury pool management,
reward frequency caps, decimal precision, thread safety, and RIP-309 anti-gaming rotation.
"""

from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from rip310_social_mining import (
    SocialMiningPool,
    TipBot,
    RewardCalculator,
    RIP309Integration,
    SocialActionType,
    TipResult,
    RewardResult,
)


@pytest.fixture
def social_pool():
    return SocialMiningPool(initial_balance=100.0)


@pytest.fixture
def tip_bot(social_pool):
    return TipBot(pool=social_pool, fee_percent=0.08)


@pytest.fixture
def reward_calc(social_pool):
    return RewardCalculator(pool=social_pool)


@pytest.fixture
def rip309_anti_gaming():
    return RIP309Integration()


class TestSocialMiningPool:
    def test_initial_balance(self, social_pool):
        assert social_pool.get_balance() == pytest.approx(100.0)

    def test_deposit_fee(self, social_pool):
        social_pool.deposit(8.0, source="tipping_fee")
        assert social_pool.get_balance() == pytest.approx(108.0)

    def test_payout_reward(self, social_pool):
        success = social_pool.payout(10.0, recipient="user_alice")
        assert success is True
        assert social_pool.get_balance() == pytest.approx(90.0)

    def test_payout_insufficient_treasury(self, social_pool):
        success = social_pool.payout(500.0, recipient="user_alice")
        assert success is False
        assert social_pool.get_balance() == pytest.approx(100.0)

    def test_decimal_precision(self):
        pool = SocialMiningPool(initial_balance="0.03")
        pool.deposit("0.01", source="micro_tip")
        assert pool.get_balance_decimal() == Decimal("0.04")
        assert pool.get_balance() == pytest.approx(0.04)

    def test_concurrent_payouts_thread_safety(self):
        # Pool with balance 100.0
        pool = SocialMiningPool(initial_balance=100.0)

        # 30 concurrent threads trying to withdraw 5.0 each (total 150.0 > 100.0)
        def withdraw_task():
            return pool.payout(5.0, recipient="concurrent_user")

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda _: withdraw_task(), range(30)))

        successful_payouts = [r for r in results if r is True]

        # Exactly 20 payouts should succeed (20 * 5.0 = 100.0), balance should reach exactly 0.0
        assert len(successful_payouts) == 20
        assert pool.get_balance() == pytest.approx(0.0)


class TestTipBot:
    def test_successful_tip(self, tip_bot, social_pool):
        sender_balances = {"user_alice": 10.0, "user_bob": 2.0}
        valid_beacons = {"user_alice": "BEACON-HW-101", "user_bob": "BEACON-HW-102"}

        result = tip_bot.process_tip(
            sender="user_alice",
            recipient="user_bob",
            amount=5.0,
            balances=sender_balances,
            beacon_registry=valid_beacons,
        )

        assert result.success is True
        assert result.net_recipient_amount == pytest.approx(4.60)  # 5.0 - 0.40 (8%)
        assert result.fee_amount == pytest.approx(0.40)
        assert sender_balances["user_alice"] == pytest.approx(5.0)
        assert sender_balances["user_bob"] == pytest.approx(6.60)
        assert social_pool.get_balance() == pytest.approx(100.40)

    def test_tip_rejected_without_beacon(self, tip_bot):
        sender_balances = {"user_alice": 10.0, "user_bob": 2.0}
        valid_beacons = {"user_alice": "BEACON-HW-101"}

        result = tip_bot.process_tip(
            sender="user_alice",
            recipient="user_bob",
            amount=1.0,
            balances=sender_balances,
            beacon_registry=valid_beacons,
        )

        assert result.success is False
        assert "Beacon ID" in result.error_message

    def test_tip_below_minimum(self, tip_bot):
        sender_balances = {"user_alice": 10.0, "user_bob": 2.0}
        valid_beacons = {"user_alice": "BEACON-HW-101", "user_bob": "BEACON-HW-102"}

        result = tip_bot.process_tip(
            sender="user_alice",
            recipient="user_bob",
            amount=0.005,
            balances=sender_balances,
            beacon_registry=valid_beacons,
        )

        assert result.success is False
        assert "Minimum tip" in result.error_message


class TestRewardCalculator:
    def test_moltbook_post_reward(self, reward_calc, social_pool):
        user = "user_charlie"
        beacon_registry = {user: "BEACON-HW-103"}

        res = reward_calc.claim_reward(
            user=user,
            action=SocialActionType.MOLTBOOK_POST,
            beacon_registry=beacon_registry,
        )

        assert res.success is True
        assert res.reward_amount == pytest.approx(0.01)

    def test_moltbook_post_frequency_cap(self, reward_calc):
        user = "user_charlie"
        beacon_registry = {user: "BEACON-HW-103"}

        for _ in range(5):
            res = reward_calc.claim_reward(
                user=user,
                action=SocialActionType.MOLTBOOK_POST,
                beacon_registry=beacon_registry,
            )
            assert res.success is True

        res_cap = reward_calc.claim_reward(
            user=user,
            action=SocialActionType.MOLTBOOK_POST,
            beacon_registry=beacon_registry,
        )
        assert res_cap.success is False
        assert "Frequency cap" in res_cap.error_message

    def test_bottube_video_reward(self, reward_calc):
        user = "user_dave"
        beacon_registry = {user: "BEACON-HW-104"}

        res = reward_calc.claim_reward(
            user=user,
            action=SocialActionType.BOTTUBE_VIDEO,
            beacon_registry=beacon_registry,
        )
        assert res.success is True
        assert res.reward_amount == pytest.approx(0.05)

    def test_short_comment_rejected(self, reward_calc):
        user = "user_eve"
        beacon_registry = {user: "BEACON-HW-105"}

        res = reward_calc.claim_reward(
            user=user,
            action=SocialActionType.COMMENT,
            comment_text="Great post!",
            beacon_registry=beacon_registry,
        )
        assert res.success is False
        assert "50 characters" in res.error_message

    def test_whitespace_comment_rejected(self, reward_calc):
        user = "user_eve"
        beacon_registry = {user: "BEACON-HW-105"}

        # Comment with > 50 spaces but non-whitespace text <= 50 chars
        res = reward_calc.claim_reward(
            user=user,
            action=SocialActionType.COMMENT,
            comment_text=" " * 52,
            beacon_registry=beacon_registry,
        )
        assert res.success is False
        assert "50 characters" in res.error_message


class TestConcurrentRaceConditions:
    """Concurrent race detection tests for TOCTOU vulnerabilities.

    These tests use threading.Barrier to force true simultaneous access,
    overcoming Python's GIL serialization of bytecode operations.
    """

    def test_concurrent_tips_no_double_spend(self):
        """Verify that concurrent tips from the same sender do not double-spend."""
        import threading

        pool = SocialMiningPool(initial_balance=0.0)
        tip_bot = TipBot(pool=pool, fee_percent=0.08)

        balances = {"alice": 10.0, "bob": 0.0}
        beacons = {"alice": "BEACON-1", "bob": "BEACON-2"}
        results = []
        barrier = threading.Barrier(15)

        def tip_one_rtc():
            barrier.wait()  # All threads start simultaneously
            result = tip_bot.process_tip(
                sender="alice",
                recipient="bob",
                amount=1.0,
                balances=balances,
                beacon_registry=beacons,
            )
            results.append(result)

        threads = [threading.Thread(target=tip_one_rtc) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successful = [r for r in results if r.success]
        total_sent = sum(r.net_recipient_amount + r.fee_amount for r in successful)

        assert len(successful) <= 10, (
            f"Double-spend detected: {len(successful)} tips succeeded "
            f"but sender only had 10.0 RTC (total sent: {total_sent})"
        )
        assert total_sent <= 10.0, f"Sent {total_sent} but sender only had 10.0"

    def test_concurrent_reward_claims_cap_enforced(self):
        """Verify that daily frequency cap is not bypassed via concurrent claims."""
        import threading

        pool = SocialMiningPool(initial_balance=100.0)
        calc = RewardCalculator(pool=pool)
        user = "charlie"
        beacons = {user: "BEACON-3"}
        results = []
        barrier = threading.Barrier(15)

        def claim_moltbook():
            barrier.wait()  # All threads start simultaneously
            result = calc.claim_reward(
                user=user,
                action=SocialActionType.MOLTBOOK_POST,
                beacon_registry=beacons,
            )
            results.append(result)

        threads = [threading.Thread(target=claim_moltbook) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successful = [r for r in results if r.success]
        assert len(successful) <= 5, (
            f"Cap bypass detected: {len(successful)} claims succeeded "
            f"but daily cap is 5"
        )


class TestRIP309AntiGaming:
    def test_epoch_metric_rotation(self, rip309_anti_gaming):
        active_metric_epoch_1 = rip309_anti_gaming.get_active_metric(epoch=1)
        active_metric_epoch_2 = rip309_anti_gaming.get_active_metric(epoch=2)

        assert active_metric_epoch_1 != active_metric_epoch_2
        assert rip309_anti_gaming.validate_action(
            action="comment_depth", epoch=1, metric=active_metric_epoch_1
        ) is True
