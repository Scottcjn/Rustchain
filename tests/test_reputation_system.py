#!/usr/bin/env python3
"""
RIP-302 Reputation System - Comprehensive Test Suite

This test suite covers all aspects of the Cross-Epoch Reputation &
Loyalty Rewards system including unit tests, integration tests, and
simulation tests.

Usage:
    python -m pytest tests/test_reputation_system.py -v
    python tests/test_reputation_system.py

Author: Scott Boudreaux (Elyan Labs)
License: Apache 2.0
"""

import json
import os
import sys
import unittest
from pathlib import Path
from datetime import datetime

# Add the reputation system to path
sys.path.insert(0, str(Path(__file__).parent.parent / "rips" / "python" / "rustchain"))

from reputation_system import (
    ReputationSystem,
    MinerReputation,
    DecayEvent,
    AttestationHistory,
    ChallengeHistory,
    LoyaltyTier,
    calculate_reputation_score,
    calculate_reputation_multiplier,
    get_loyalty_tier,
    get_loyalty_bonus,
    calculate_combined_multiplier
)


class TestLoyaltyTier(unittest.TestCase):
    """Tests for LoyaltyTier enumeration."""
    
    def test_loyalty_tier_values(self):
        """Test that all loyalty tiers have correct values."""
        self.assertEqual(LoyaltyTier.NONE.value, "none")
        self.assertEqual(LoyaltyTier.BRONZE.value, "bronze")
        self.assertEqual(LoyaltyTier.SILVER.value, "silver")
        self.assertEqual(LoyaltyTier.GOLD.value, "gold")
        self.assertEqual(LoyaltyTier.PLATINUM.value, "platinum")
        self.assertEqual(LoyaltyTier.DIAMOND.value, "diamond")


class TestGetLoyaltyTier(unittest.TestCase):
    """Tests for get_loyalty_tier function."""
    
    def test_no_tier(self):
        """Test miners with <10 epochs have no tier."""
        for epochs in [0, 1, 5, 9]:
            self.assertEqual(get_loyalty_tier(epochs), LoyaltyTier.NONE)
    
    def test_bronze_tier(self):
        """Test bronze tier threshold."""
        for epochs in [10, 20, 49]:
            self.assertEqual(get_loyalty_tier(epochs), LoyaltyTier.BRONZE)
    
    def test_silver_tier(self):
        """Test silver tier threshold."""
        for epochs in [50, 75, 99]:
            self.assertEqual(get_loyalty_tier(epochs), LoyaltyTier.SILVER)
    
    def test_gold_tier(self):
        """Test gold tier threshold."""
        for epochs in [100, 200, 499]:
            self.assertEqual(get_loyalty_tier(epochs), LoyaltyTier.GOLD)
    
    def test_platinum_tier(self):
        """Test platinum tier threshold."""
        for epochs in [500, 750, 999]:
            self.assertEqual(get_loyalty_tier(epochs), LoyaltyTier.PLATINUM)
    
    def test_diamond_tier(self):
        """Test diamond tier threshold."""
        for epochs in [1000, 1500, 5000]:
            self.assertEqual(get_loyalty_tier(epochs), LoyaltyTier.DIAMOND)


class TestGetLoyaltyBonus(unittest.TestCase):
    """Tests for get_loyalty_bonus function."""
    
    def test_no_bonus(self):
        """Test no tier gets 1.0x bonus."""
        self.assertEqual(get_loyalty_bonus(LoyaltyTier.NONE), 1.00)
    
    def test_bronze_bonus(self):
        """Test bronze tier gets 1.05x bonus."""
        self.assertEqual(get_loyalty_bonus(LoyaltyTier.BRONZE), 1.05)
    
    def test_silver_bonus(self):
        """Test silver tier gets 1.10x bonus."""
        self.assertEqual(get_loyalty_bonus(LoyaltyTier.SILVER), 1.10)
    
    def test_gold_bonus(self):
        """Test gold tier gets 1.20x bonus."""
        self.assertEqual(get_loyalty_bonus(LoyaltyTier.GOLD), 1.20)
    
    def test_platinum_bonus(self):
        """Test platinum tier gets 1.50x bonus."""
        self.assertEqual(get_loyalty_bonus(LoyaltyTier.PLATINUM), 1.50)
    
    def test_diamond_bonus(self):
        """Test diamond tier gets 2.00x bonus."""
        self.assertEqual(get_loyalty_bonus(LoyaltyTier.DIAMOND), 2.00)


class TestReputationScoreCalculation(unittest.TestCase):
    """Tests for reputation score calculation."""
    
    def test_zero_rp(self):
        """Test 0 RP gives 1.0 score."""
        self.assertEqual(calculate_reputation_score(0), 1.0)
    
    def test_100_rp(self):
        """Test 100 RP gives 2.0 score."""
        self.assertEqual(calculate_reputation_score(100), 2.0)
    
    def test_200_rp(self):
        """Test 200 RP gives 3.0 score."""
        self.assertEqual(calculate_reputation_score(200), 3.0)
    
    def test_300_rp(self):
        """Test 300 RP gives 4.0 score."""
        self.assertEqual(calculate_reputation_score(300), 4.0)
    
    def test_400_rp(self):
        """Test 400 RP gives 5.0 score (cap)."""
        self.assertEqual(calculate_reputation_score(400), 5.0)
    
    def test_500_rp(self):
        """Test 500 RP still gives 5.0 score (capped)."""
        self.assertEqual(calculate_reputation_score(500), 5.0)
    
    def test_negative_rp(self):
        """Test negative RP gives 1.0 score (minimum)."""
        self.assertEqual(calculate_reputation_score(-50), 1.0)


class TestReputationMultiplierCalculation(unittest.TestCase):
    """Tests for reputation multiplier calculation."""
    
    def test_score_1_0(self):
        """Test score 1.0 gives 1.0x multiplier."""
        self.assertEqual(calculate_reputation_multiplier(1.0), 1.0)
    
    def test_score_2_0(self):
        """Test score 2.0 gives 1.25x multiplier."""
        self.assertEqual(calculate_reputation_multiplier(2.0), 1.25)
    
    def test_score_3_0(self):
        """Test score 3.0 gives 1.50x multiplier."""
        self.assertEqual(calculate_reputation_multiplier(3.0), 1.50)
    
    def test_score_4_0(self):
        """Test score 4.0 gives 1.75x multiplier."""
        self.assertEqual(calculate_reputation_multiplier(4.0), 1.75)
    
    def test_score_5_0(self):
        """Test score 5.0 gives 2.0x multiplier."""
        self.assertEqual(calculate_reputation_multiplier(5.0), 2.0)


class TestCombinedMultiplier(unittest.TestCase):
    """Tests for combined multiplier calculation."""
    
    def test_new_miner(self):
        """Test new miner with no reputation or loyalty."""
        result = calculate_combined_multiplier(
            antiquity_multiplier=2.5,
            total_rp=0,
            epochs_participated=0
        )
        # 2.5 * 1.0 * 1.0 = 2.5
        self.assertAlmostEqual(result, 2.5, places=4)
    
    def test_veteran_miner(self):
        """Test veteran miner with good reputation."""
        result = calculate_combined_multiplier(
            antiquity_multiplier=2.5,
            total_rp=200,  # Score 3.0, mult 1.5x
            epochs_participated=100  # Gold tier, 1.20x
        )
        # 2.5 * 1.5 * 1.20 = 4.5
        self.assertAlmostEqual(result, 4.5, places=4)
    
    def test_legend_miner(self):
        """Test legend miner with max reputation."""
        result = calculate_combined_multiplier(
            antiquity_multiplier=2.8,
            total_rp=500,  # Score 5.0 (capped), mult 2.0x
            epochs_participated=1000  # Diamond tier, 2.00x
        )
        # 2.8 * 2.0 * 2.0 = 11.2
        self.assertAlmostEqual(result, 11.2, places=4)


class TestDecayEvent(unittest.TestCase):
    """Tests for DecayEvent dataclass."""
    
    def test_create_decay_event(self):
        """Test creating a decay event."""
        event = DecayEvent(
            epoch=100,
            reason="missed_epoch",
            rp_lost=5,
            new_rp=95
        )
        self.assertEqual(event.epoch, 100)
        self.assertEqual(event.reason, "missed_epoch")
        self.assertEqual(event.rp_lost, 5)
        self.assertEqual(event.new_rp, 95)
        self.assertIsInstance(event.timestamp, str)
    
    def test_decay_event_to_dict(self):
        """Test decay event serialization."""
        event = DecayEvent(epoch=100, reason="test", rp_lost=10, new_rp=90)
        data = event.to_dict()
        
        self.assertEqual(data["epoch"], 100)
        self.assertEqual(data["reason"], "test")
        self.assertEqual(data["rp_lost"], 10)
        self.assertEqual(data["new_rp"], 90)
        self.assertIn("timestamp", data)
    
    def test_decay_event_from_dict(self):
        """Test decay event deserialization."""
        data = {
            "epoch": 100,
            "reason": "fleet_detection",
            "rp_lost": 25,
            "new_rp": 75,
            "timestamp": "2026-03-06T12:00:00"
        }
        event = DecayEvent.from_dict(data)
        
        self.assertEqual(event.epoch, 100)
        self.assertEqual(event.reason, "fleet_detection")
        self.assertEqual(event.rp_lost, 25)
        self.assertEqual(event.new_rp, 75)


class TestAttestationHistory(unittest.TestCase):
    """Tests for AttestationHistory dataclass."""
    
    def test_empty_history(self):
        """Test empty attestation history."""
        history = AttestationHistory()
        self.assertEqual(history.total, 0)
        self.assertEqual(history.passed, 0)
        self.assertEqual(history.failed, 0)
        self.assertEqual(history.pass_rate, 1.0)  # Default to 100%
    
    def test_pass_rate_calculation(self):
        """Test pass rate calculation."""
        history = AttestationHistory(total=10, passed=8, failed=2)
        self.assertAlmostEqual(history.pass_rate, 0.8, places=4)
    
    def test_perfect_record(self):
        """Test perfect attestation record."""
        history = AttestationHistory(total=100, passed=100, failed=0)
        self.assertEqual(history.pass_rate, 1.0)
    
    def test_serialization(self):
        """Test attestation history serialization."""
        history = AttestationHistory(total=50, passed=45, failed=5)
        data = history.to_dict()
        
        self.assertEqual(data["total"], 50)
        self.assertEqual(data["passed"], 45)
        self.assertEqual(data["failed"], 5)
        self.assertAlmostEqual(data["pass_rate"], 0.9, places=4)


class TestChallengeHistory(unittest.TestCase):
    """Tests for ChallengeHistory dataclass."""
    
    def test_empty_history(self):
        """Test empty challenge history."""
        history = ChallengeHistory()
        self.assertEqual(history.total, 0)
        self.assertEqual(history.passed, 0)
        self.assertEqual(history.failed, 0)
        self.assertEqual(history.pass_rate, 1.0)
    
    def test_pass_rate_calculation(self):
        """Test challenge pass rate calculation."""
        history = ChallengeHistory(total=20, passed=18, failed=2)
        self.assertAlmostEqual(history.pass_rate, 0.9, places=4)


class TestMinerReputation(unittest.TestCase):
    """Tests for MinerReputation dataclass."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.miner = MinerReputation(miner_id="RTC_test_001")
    
    def test_initial_state(self):
        """Test initial miner state."""
        self.assertEqual(self.miner.miner_id, "RTC_test_001")
        self.assertEqual(self.miner.total_rp, 0)
        self.assertEqual(self.miner.epochs_participated, 0)
        self.assertEqual(self.miner.epochs_consecutive, 0)
        self.assertEqual(self.miner.last_epoch, 0)
        self.assertEqual(self.miner.reputation_score, 1.0)
        self.assertEqual(self.miner.reputation_multiplier, 1.0)
        self.assertEqual(self.miner.loyalty_tier, LoyaltyTier.NONE)
        self.assertEqual(self.miner.loyalty_bonus, 1.0)
    
    def test_reputation_score_property(self):
        """Test reputation score calculation."""
        self.miner.total_rp = 250
        self.assertAlmostEqual(self.miner.reputation_score, 3.5, places=4)
    
    def test_reputation_multiplier_property(self):
        """Test reputation multiplier calculation."""
        self.miner.total_rp = 200  # Score 3.0
        self.assertAlmostEqual(self.miner.reputation_multiplier, 1.5, places=4)
    
    def test_loyalty_tier_progression(self):
        """Test loyalty tier progression."""
        tier_epochs = [
            (0, LoyaltyTier.NONE),
            (10, LoyaltyTier.BRONZE),
            (50, LoyaltyTier.SILVER),
            (100, LoyaltyTier.GOLD),
            (500, LoyaltyTier.PLATINUM),
            (1000, LoyaltyTier.DIAMOND)
        ]
        
        for epochs, expected_tier in tier_epochs:
            self.miner.epochs_participated = epochs
            self.assertEqual(self.miner.loyalty_tier, expected_tier,
                           f"Failed at {epochs} epochs")
    
    def test_combined_multiplier(self):
        """Test combined multiplier calculation."""
        self.miner.total_rp = 200  # 1.5x rep mult
        self.miner.epochs_participated = 100  # 1.20x loyalty
        # 1.5 * 1.20 = 1.8
        self.assertAlmostEqual(self.miner.combined_multiplier, 1.8, places=4)
    
    def test_epochs_to_next_tier(self):
        """Test epochs to next tier calculation."""
        test_cases = [
            (0, 10),
            (5, 5),
            (10, 40),
            (50, 50),
            (100, 400),
            (500, 500),
            (1000, 0)
        ]
        
        for epochs, expected in test_cases:
            self.miner.epochs_participated = epochs
            self.assertEqual(self.miner.epochs_to_next_tier, expected,
                           f"Failed at {epochs} epochs")
    
    def test_serialization(self):
        """Test miner reputation serialization to dict."""
        self.miner.total_rp = 150
        self.miner.epochs_participated = 75
        self.miner.epochs_consecutive = 10
        self.miner.last_epoch = 100
        
        data = self.miner.to_dict()
        
        self.assertEqual(data["miner_id"], "RTC_test_001")
        self.assertEqual(data["total_rp"], 150)
        self.assertEqual(data["epochs_participated"], 75)
        self.assertAlmostEqual(data["reputation_score"], 2.5, places=4)
        self.assertEqual(data["loyalty_tier"], "silver")
    
    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        self.miner.total_rp = 200
        self.miner.epochs_participated = 100
        
        # Serialize to JSON
        json_str = self.miner.to_json()
        
        # Deserialize from JSON
        restored = MinerReputation.from_json(json_str)
        
        self.assertEqual(restored.miner_id, self.miner.miner_id)
        self.assertEqual(restored.total_rp, self.miner.total_rp)
        self.assertEqual(restored.epochs_participated, self.miner.epochs_participated)
        self.assertEqual(restored.reputation_score, self.miner.reputation_score)


class TestReputationSystem(unittest.TestCase):
    """Tests for the main ReputationSystem class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.system = ReputationSystem()
    
    def test_get_or_create_miner(self):
        """Test getting or creating a miner."""
        miner1 = self.system.get_or_create_miner("RTC_test_001")
        self.assertEqual(miner1.miner_id, "RTC_test_001")
        
        # Getting same miner should return same object
        miner2 = self.system.get_or_create_miner("RTC_test_001")
        self.assertIs(miner1, miner2)
        
        # Different miner should be different object
        miner3 = self.system.get_or_create_miner("RTC_test_002")
        self.assertIsNot(miner1, miner3)
    
    def test_record_epoch_participation(self):
        """Test recording epoch participation."""
        rp_earned = self.system.record_epoch_participation(
            miner_id="RTC_test_001",
            epoch=1,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
        
        # Max RP should be 7 (1+1+3+1+1 = 7, capped at 7)
        # But actually: 1 (enrollment) + 1 (clean) + 3 (full) + 1 (settlement) = 6
        # The challenge response RP is separate
        self.assertEqual(rp_earned, 6)  # 1+1+3+1 = 6
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        self.assertEqual(miner.total_rp, rp_earned)
        self.assertEqual(miner.epochs_participated, 1)
        self.assertEqual(miner.last_epoch, 1)
        self.assertEqual(miner.epochs_consecutive, 1)
    
    def test_consecutive_epochs(self):
        """Test consecutive epoch tracking."""
        for epoch in range(1, 11):
            self.system.current_epoch = epoch
            self.system.record_epoch_participation(
                miner_id="RTC_test_001",
                epoch=epoch,
                clean_attestation=True,
                full_participation=True,
                on_time_settlement=True
            )
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        self.assertEqual(miner.epochs_consecutive, 10)
        self.assertEqual(miner.epochs_participated, 10)
    
    def test_missed_epoch_decay(self):
        """Test decay from missed epochs."""
        # Participate in epoch 1
        self.system.record_epoch_participation(
            miner_id="RTC_test_001",
            epoch=1,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
        
        # Skip to epoch 15 (14 epoch gap)
        self.system.current_epoch = 15
        self.system.record_epoch_participation(
            miner_id="RTC_test_001",
            epoch=15,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        
        # Should have extended absence decay
        self.assertGreater(len(miner.decay_events), 0)
        self.assertEqual(miner.epochs_consecutive, 1)  # Reset
    
    def test_failed_attestation_decay(self):
        """Test decay from failed attestation."""
        # First get enough RP (need at least 10 for the decay test)
        for epoch in range(1, 4):
            self.system.current_epoch = epoch
            self.system.record_epoch_participation(
                miner_id="RTC_test_001",
                epoch=epoch,
                clean_attestation=True,
                full_participation=True,
                on_time_settlement=True
            )
        
        # Now fail an attestation
        self.system.current_epoch = 4
        self.system.record_epoch_participation(
            miner_id="RTC_test_001",
            epoch=4,
            clean_attestation=False,  # Failed
            full_participation=True,
            on_time_settlement=True
        )
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        
        # Should have decay event for failed attestation
        decay_events = [e for e in miner.decay_events if e.reason == "failed_attestation"]
        self.assertEqual(len(decay_events), 1)
        # Decay should have removed the expected amount
        self.assertEqual(decay_events[0].rp_lost, ReputationSystem.DECAY_FAILED_ATTESTATION)
    
    def test_fleet_detection_decay(self):
        """Test decay from fleet detection."""
        # First get enough RP (need at least 25 for the decay test)
        for epoch in range(1, 6):
            self.system.current_epoch = epoch
            self.system.record_epoch_participation(
                miner_id="RTC_test_001",
                epoch=epoch,
                clean_attestation=True,
                full_participation=True,
                on_time_settlement=True
            )
        
        # Now trigger fleet detection
        self.system.current_epoch = 6
        self.system.record_fleet_detection("RTC_test_001", epoch=6)
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        
        decay_events = [e for e in miner.decay_events if e.reason == "fleet_detection"]
        self.assertEqual(len(decay_events), 1)
        self.assertGreater(decay_events[0].rp_lost, 0)
        self.assertEqual(decay_events[0].rp_lost, ReputationSystem.DECAY_FLEET_DETECTION)
    
    def test_challenge_result(self):
        """Test challenge result recording."""
        # Pass a challenge
        self.system.record_challenge_result("RTC_test_001", passed=True, epoch=10)
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        self.assertEqual(miner.challenge_history.total, 1)
        self.assertEqual(miner.challenge_history.passed, 1)
        self.assertEqual(miner.total_rp, ReputationSystem.RP_CHALLENGE_RESPONSE)
        
        # Fail a challenge
        self.system.record_challenge_result("RTC_test_001", passed=False, epoch=11)
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        self.assertEqual(miner.challenge_history.total, 2)
        self.assertEqual(miner.challenge_history.failed, 1)
        
        # Should have decay
        decay_events = [e for e in miner.decay_events if e.reason == "challenge_failure"]
        self.assertEqual(len(decay_events), 1)
    
    def test_recovery_bonus(self):
        """Test recovery bonus after decay."""
        # Get some RP
        self.system.record_epoch_participation(
            miner_id="RTC_test_001",
            epoch=1,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
        
        # Trigger decay
        self.system.record_fleet_detection("RTC_test_001", epoch=2)
        
        miner = self.system.get_or_create_miner("RTC_test_001")
        rp_after_decay = miner.total_rp
        
        # Next epoch should have recovery bonus
        self.system.current_epoch = 3
        rp_earned = self.system.record_epoch_participation(
            miner_id="RTC_test_001",
            epoch=3,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
        
        # Should earn at least the normal amount (recovery bonus may exceed cap)
        self.assertGreaterEqual(rp_earned, 6)  # Normal epoch without challenge response
    
    def test_leaderboard(self):
        """Test leaderboard generation."""
        # Create multiple miners with different RP
        miners = [
            ("RTC_miner_a", 300),
            ("RTC_miner_b", 100),
            ("RTC_miner_c", 500),
            ("RTC_miner_d", 50),
            ("RTC_miner_e", 200)
        ]
        
        for miner_id, rp in miners:
            self.system.miners[miner_id] = MinerReputation(
                miner_id=miner_id,
                total_rp=rp
            )
        
        # Get leaderboard
        leaderboard = self.system.get_reputation_leaderboard(limit=3)
        
        self.assertEqual(len(leaderboard), 3)
        self.assertEqual(leaderboard[0]["miner_id"], "RTC_miner_c")  # Highest RP
        self.assertEqual(leaderboard[1]["miner_id"], "RTC_miner_a")
        self.assertEqual(leaderboard[2]["miner_id"], "RTC_miner_e")
        
        # Check ranks
        for i, entry in enumerate(leaderboard, 1):
            self.assertEqual(entry["rank"], i)
    
    def test_tier_filter(self):
        """Test leaderboard tier filtering."""
        # Create miners with different tiers
        self.system.miners["RTC_bronze"] = MinerReputation(
            miner_id="RTC_bronze", total_rp=50, epochs_participated=10
        )
        self.system.miners["RTC_silver"] = MinerReputation(
            miner_id="RTC_silver", total_rp=100, epochs_participated=50
        )
        self.system.miners["RTC_gold"] = MinerReputation(
            miner_id="RTC_gold", total_rp=200, epochs_participated=100
        )
        
        # Filter by silver
        leaderboard = self.system.get_reputation_leaderboard(
            limit=10,
            tier_filter="silver"
        )
        
        self.assertEqual(len(leaderboard), 1)
        self.assertEqual(leaderboard[0]["miner_id"], "RTC_silver")
    
    def test_global_stats(self):
        """Test global statistics calculation."""
        # Create some miners with different tiers
        self.system.miners["RTC_a"] = MinerReputation(
            miner_id="RTC_a", total_rp=100, epochs_participated=50  # Silver
        )
        self.system.miners["RTC_b"] = MinerReputation(
            miner_id="RTC_b", total_rp=200, epochs_participated=100  # Gold
        )
        self.system.miners["RTC_c"] = MinerReputation(
            miner_id="RTC_c", total_rp=500, epochs_participated=1000  # Diamond
        )
        
        stats = self.system.get_global_stats()
        
        self.assertEqual(stats["total_miners"], 3)
        self.assertEqual(stats["reputation_holders"]["silver"], 1)
        self.assertEqual(stats["reputation_holders"]["gold"], 1)
        self.assertEqual(stats["reputation_holders"]["diamond"], 1)
        self.assertGreater(stats["average_reputation_score"], 0)
    
    def test_projection(self):
        """Test reputation projection."""
        miner = MinerReputation(
            miner_id="RTC_test",
            total_rp=100,
            epochs_participated=50
        )
        self.system.miners["RTC_test"] = miner
        
        projection = self.system.calculate_miner_projection("RTC_test", epochs_ahead=100)
        
        self.assertEqual(projection["current_rp"], 100)
        self.assertGreater(projection["projected_rp"], 100)
        self.assertGreater(projection["projected_multiplier"], projection["current_multiplier"])
    
    def test_state_export_import(self):
        """Test state export and import."""
        # Set up some state
        self.system.current_epoch = 100
        self.system.miners["RTC_test"] = MinerReputation(
            miner_id="RTC_test",
            total_rp=250,
            epochs_participated=75
        )
        
        # Export
        state = self.system.export_state()
        
        # Create new system and import
        new_system = ReputationSystem()
        new_system.import_state(state)
        
        # Verify
        self.assertEqual(new_system.current_epoch, 100)
        self.assertIn("RTC_test", new_system.miners)
        self.assertEqual(new_system.miners["RTC_test"].total_rp, 250)


class TestReputationSystemIntegration(unittest.TestCase):
    """Integration tests for the reputation system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.system = ReputationSystem()
    
    def test_full_epoch_lifecycle(self):
        """Test complete epoch lifecycle with multiple miners."""
        miners = ["RTC_a", "RTC_b", "RTC_c"]
        num_epochs = 50
        
        for epoch in range(1, num_epochs + 1):
            self.system.current_epoch = epoch
            
            for miner_id in miners:
                # Enroll
                self.system.record_epoch_participation(
                    miner_id=miner_id,
                    epoch=epoch,
                    clean_attestation=True,
                    full_participation=True,
                    on_time_settlement=True
                )
        
        # Verify all miners have correct stats
        for miner_id in miners:
            miner = self.system.get_or_create_miner(miner_id)
            self.assertEqual(miner.epochs_participated, num_epochs)
            self.assertEqual(miner.epochs_consecutive, num_epochs)
            self.assertGreater(miner.total_rp, 0)
    
    def test_mixed_participation(self):
        """Test scenario with mixed participation quality."""
        miner_id = "RTC_mixed"
        
        # 30 good epochs
        for epoch in range(1, 31):
            self.system.current_epoch = epoch
            self.system.record_epoch_participation(
                miner_id=miner_id,
                epoch=epoch,
                clean_attestation=True,
                full_participation=True,
                on_time_settlement=True
            )
        
        # 5 bad epochs (failed attestations)
        for epoch in range(31, 36):
            self.system.current_epoch = epoch
            self.system.record_epoch_participation(
                miner_id=miner_id,
                epoch=epoch,
                clean_attestation=False,
                full_participation=True,
                on_time_settlement=True
            )
        
        # 15 good epochs again
        for epoch in range(36, 51):
            self.system.current_epoch = epoch
            self.system.record_epoch_participation(
                miner_id=miner_id,
                epoch=epoch,
                clean_attestation=True,
                full_participation=True,
                on_time_settlement=True
            )
        
        miner = self.system.get_or_create_miner(miner_id)
        
        # Should have 5 decay events from failed attestations
        failed_decays = [e for e in miner.decay_events if e.reason == "failed_attestation"]
        self.assertEqual(len(failed_decays), 5)
        
        # Should still have positive RP overall
        self.assertGreater(miner.total_rp, 0)
    
    def test_economic_impact(self):
        """Test economic impact of reputation on rewards."""
        # Create two miners: one dedicated, one casual
        dedicated = "RTC_dedicated"
        casual = "RTC_casual"
        
        # Dedicated: 100 epochs, perfect participation
        for epoch in range(1, 101):
            self.system.current_epoch = epoch
            self.system.record_epoch_participation(
                miner_id=dedicated,
                epoch=epoch,
                clean_attestation=True,
                full_participation=True,
                on_time_settlement=True
            )
        
        # Casual: 100 epochs, 50% participation
        for epoch in range(1, 101):
            self.system.current_epoch = epoch
            if epoch % 2 == 0:  # Only participate in even epochs
                self.system.record_epoch_participation(
                    miner_id=casual,
                    epoch=epoch,
                    clean_attestation=True,
                    full_participation=True,
                    on_time_settlement=True
                )
            else:
                self.system.record_missed_epoch(casual, epoch)
        
        dedicated_miner = self.system.get_or_create_miner(dedicated)
        casual_miner = self.system.get_or_create_miner(casual)
        
        # Dedicated should have more RP
        self.assertGreater(dedicated_miner.total_rp, casual_miner.total_rp)
        
        # Dedicated should have better multiplier
        self.assertGreater(
            dedicated_miner.combined_multiplier,
            casual_miner.combined_multiplier
        )


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.system = ReputationSystem()
    
    def test_rp_never_negative(self):
        """Test that RP never goes negative."""
        miner = MinerReputation(miner_id="RTC_test", total_rp=10)
        self.system.miners["RTC_test"] = miner
        
        # Apply large decay
        self.system.apply_decay("RTC_test", "test", 100, epoch=1)
        
        miner = self.system.get_or_create_miner("RTC_test")
        self.assertGreaterEqual(miner.total_rp, 0)
    
    def test_score_caps_at_5(self):
        """Test that reputation score caps at 5.0."""
        miner = MinerReputation(miner_id="RTC_test", total_rp=10000)
        self.system.miners["RTC_test"] = miner
        
        self.assertEqual(miner.reputation_score, 5.0)
    
    def test_empty_system_stats(self):
        """Test global stats with no miners."""
        stats = self.system.get_global_stats()
        
        self.assertEqual(stats["total_miners"], 0)
        self.assertEqual(stats["average_reputation_score"], 0.0)
    
    def test_single_miner_leaderboard(self):
        """Test leaderboard with single miner."""
        self.system.miners["RTC_solo"] = MinerReputation(
            miner_id="RTC_solo", total_rp=100
        )
        
        leaderboard = self.system.get_reputation_leaderboard(limit=10)
        
        self.assertEqual(len(leaderboard), 1)
        self.assertEqual(leaderboard[0]["rank"], 1)
    
    def test_zero_epochs_projection(self):
        """Test projection with zero epochs."""
        miner = MinerReputation(miner_id="RTC_new", total_rp=0, epochs_participated=0)
        self.system.miners["RTC_new"] = miner
        
        projection = self.system.calculate_miner_projection("RTC_new", epochs_ahead=0)
        
        self.assertEqual(projection["current_rp"], 0)
        self.assertEqual(projection["epochs_to_next_tier"], 10)


def run_tests():
    """Run all tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestLoyaltyTier,
        TestGetLoyaltyTier,
        TestGetLoyaltyBonus,
        TestReputationScoreCalculation,
        TestReputationMultiplierCalculation,
        TestCombinedMultiplier,
        TestDecayEvent,
        TestAttestationHistory,
        TestChallengeHistory,
        TestMinerReputation,
        TestReputationSystem,
        TestReputationSystemIntegration,
        TestEdgeCases
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print(" RIP-302 Reputation System - Test Suite")
    print("=" * 70)
    print()
    
    result = run_tests()
    
    print()
    print("=" * 70)
    print(f" Tests Run: {result.testsRun}")
    print(f" Failures: {len(result.failures)}")
    print(f" Errors: {len(result.errors)}")
    print(f" Skipped: {len(result.skipped)}")
    print("=" * 70)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
