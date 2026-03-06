#!/usr/bin/env python3
"""
RIP-302: Cross-Epoch Reputation & Loyalty Rewards System

This module implements the reputation scoring, loyalty tiers, and decay mechanics
for RustChain's Cross-Epoch Reputation System.

Author: Scott Boudreaux (Elyan Labs)
License: Apache 2.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import json
import math


class LoyaltyTier(Enum):
    """Loyalty tier enumeration with associated bonuses."""
    NONE = "none"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


@dataclass
class DecayEvent:
    """Represents a reputation decay event."""
    epoch: int
    reason: str
    rp_lost: int
    new_rp: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "epoch": self.epoch,
            "reason": self.reason,
            "rp_lost": self.rp_lost,
            "new_rp": self.new_rp,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DecayEvent':
        return cls(
            epoch=data["epoch"],
            reason=data["reason"],
            rp_lost=data["rp_lost"],
            new_rp=data["new_rp"],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat())
        )


@dataclass
class AttestationHistory:
    """Tracks attestation statistics for a miner."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    
    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return self.passed / self.total
    
    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4)
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AttestationHistory':
        return cls(
            total=data.get("total", 0),
            passed=data.get("passed", 0),
            failed=data.get("failed", 0)
        )


@dataclass
class ChallengeHistory:
    """Tracks challenge-response statistics for a miner."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    
    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return self.passed / self.total
    
    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4)
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ChallengeHistory':
        return cls(
            total=data.get("total", 0),
            passed=data.get("passed", 0),
            failed=data.get("failed", 0)
        )


@dataclass
class MinerReputation:
    """
    Complete reputation record for a miner.
    
    Attributes:
        miner_id: Unique miner identifier
        total_rp: Total accumulated Reputation Points
        epochs_participated: Total epochs the miner has participated in
        epochs_consecutive: Current consecutive epoch streak
        last_epoch: Last epoch the miner participated in
        attestation_history: Record of attestation successes/failures
        challenge_history: Record of challenge successes/failures
        decay_events: List of reputation decay events
    """
    miner_id: str
    total_rp: int = 0
    epochs_participated: int = 0
    epochs_consecutive: int = 0
    last_epoch: int = 0
    attestation_history: AttestationHistory = field(default_factory=AttestationHistory)
    challenge_history: ChallengeHistory = field(default_factory=ChallengeHistory)
    decay_events: List[DecayEvent] = field(default_factory=list)
    
    @property
    def reputation_score(self) -> float:
        """
        Calculate reputation score from total RP.
        
        Formula: min(5.0, 1.0 + (total_rp / 100))
        Caps at 5.0 (requires 400 RP to reach)
        Minimum is 1.0 (even with negative RP)
        """
        return max(1.0, min(5.0, 1.0 + (self.total_rp / 100.0)))
    
    @property
    def reputation_multiplier(self) -> float:
        """
        Calculate reputation multiplier for reward distribution.
        
        Formula: 1.0 + ((reputation_score - 1.0) × 0.25)
        
        Returns:
            Multiplier between 1.0x and 2.0x
        """
        return 1.0 + ((self.reputation_score - 1.0) * 0.25)
    
    @property
    def loyalty_tier(self) -> LoyaltyTier:
        """
        Determine loyalty tier based on epochs participated.
        
        Tiers:
            - Diamond: 1000+ epochs
            - Platinum: 500+ epochs
            - Gold: 100+ epochs
            - Silver: 50+ epochs
            - Bronze: 10+ epochs
            - None: <10 epochs
        """
        if self.epochs_participated >= 1000:
            return LoyaltyTier.DIAMOND
        elif self.epochs_participated >= 500:
            return LoyaltyTier.PLATINUM
        elif self.epochs_participated >= 100:
            return LoyaltyTier.GOLD
        elif self.epochs_participated >= 50:
            return LoyaltyTier.SILVER
        elif self.epochs_participated >= 10:
            return LoyaltyTier.BRONZE
        else:
            return LoyaltyTier.NONE
    
    @property
    def loyalty_bonus(self) -> float:
        """
        Calculate loyalty bonus multiplier based on tier.
        
        Bonuses:
            - Diamond: 2.00x (+100%)
            - Platinum: 1.50x (+50%)
            - Gold: 1.20x (+20%)
            - Silver: 1.10x (+10%)
            - Bronze: 1.05x (+5%)
            - None: 1.00x (no bonus)
        """
        tier_bonuses = {
            LoyaltyTier.DIAMOND: 2.00,
            LoyaltyTier.PLATINUM: 1.50,
            LoyaltyTier.GOLD: 1.20,
            LoyaltyTier.SILVER: 1.10,
            LoyaltyTier.BRONZE: 1.05,
            LoyaltyTier.NONE: 1.00
        }
        return tier_bonuses[self.loyalty_tier]
    
    @property
    def combined_multiplier(self) -> float:
        """
        Calculate combined reputation and loyalty multiplier.
        
        Formula: reputation_multiplier × loyalty_bonus
        
        This is applied on top of the antiquity multiplier.
        """
        return self.reputation_multiplier * self.loyalty_bonus
    
    @property
    def epochs_to_next_tier(self) -> int:
        """Calculate epochs needed to reach next loyalty tier."""
        tier_thresholds = [10, 50, 100, 500, 1000]
        for threshold in tier_thresholds:
            if self.epochs_participated < threshold:
                return threshold - self.epochs_participated
        return 0  # Already at max tier
    
    @property
    def next_tier_name(self) -> str:
        """Get name of next loyalty tier."""
        if self.epochs_participated < 10:
            return "bronze"
        elif self.epochs_participated < 50:
            return "silver"
        elif self.epochs_participated < 100:
            return "gold"
        elif self.epochs_participated < 500:
            return "platinum"
        elif self.epochs_participated < 1000:
            return "diamond"
        else:
            return "max"
    
    def to_dict(self) -> dict:
        """Serialize reputation record to dictionary."""
        return {
            "miner_id": self.miner_id,
            "total_rp": self.total_rp,
            "reputation_score": round(self.reputation_score, 4),
            "reputation_multiplier": round(self.reputation_multiplier, 4),
            "epochs_participated": self.epochs_participated,
            "epochs_consecutive": self.epochs_consecutive,
            "loyalty_tier": self.loyalty_tier.value,
            "loyalty_bonus": round(self.loyalty_bonus, 4),
            "combined_multiplier": round(self.combined_multiplier, 4),
            "last_epoch": self.last_epoch,
            "decay_events": [e.to_dict() for e in self.decay_events],
            "attestation_history": self.attestation_history.to_dict(),
            "challenge_history": self.challenge_history.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MinerReputation':
        """Deserialize reputation record from dictionary."""
        decay_events = [
            DecayEvent.from_dict(e) for e in data.get("decay_events", [])
        ]
        return cls(
            miner_id=data["miner_id"],
            total_rp=data.get("total_rp", 0),
            epochs_participated=data.get("epochs_participated", 0),
            epochs_consecutive=data.get("epochs_consecutive", 0),
            last_epoch=data.get("last_epoch", 0),
            attestation_history=AttestationHistory.from_dict(
                data.get("attestation_history", {})
            ),
            challenge_history=ChallengeHistory.from_dict(
                data.get("challenge_history", {})
            ),
            decay_events=decay_events
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MinerReputation':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


class ReputationSystem:
    """
    Central reputation system manager.
    
    Handles reputation tracking, RP distribution, decay events,
    and provides query interfaces for the reputation system.
    """
    
    # Configuration constants (can be adjusted via governance)
    RP_PER_EPOCH_MAX = 7  # Maximum RP earnable per epoch
    RP_ENROLLMENT = 1  # RP for enrolling in epoch
    RP_CLEAN_ATTESTATION = 1  # RP for clean attestation
    RP_FULL_PARTICIPATION = 3  # RP for full epoch participation
    RP_ON_TIME_SETTLEMENT = 1  # RP for on-time settlement
    RP_CHALLENGE_RESPONSE = 1  # RP for successful challenge response
    
    # Decay constants
    DECAY_MISSED_EPOCH = 5  # RP lost for missing epoch
    DECAY_FAILED_ATTESTATION = 10  # RP lost for failed attestation
    DECAY_FLEET_DETECTION = 25  # RP lost for fleet detection
    DECAY_CHALLENGE_FAILURE = 15  # RP lost for failed challenge
    DECAY_EXTENDED_ABSENCE = 50  # RP lost for 10+ epoch absence
    EXTENDED_ABSENCE_THRESHOLD = 10  # Epochs before extended absence penalty
    
    # Recovery bonus (1.5x RP earning for first 10 epochs after decay)
    RECOVERY_BONUS_EPOCHS = 10
    RECOVERY_BONUS_MULTIPLIER = 1.5
    
    # Reputation cap
    REPUTATION_CAP = 5.0
    
    def __init__(self):
        """Initialize the reputation system."""
        self.miners: Dict[str, MinerReputation] = {}
        self.current_epoch = 0
        self.epoch_history: Dict[int, dict] = {}
    
    def get_or_create_miner(self, miner_id: str) -> MinerReputation:
        """Get existing miner reputation or create new one."""
        if miner_id not in self.miners:
            self.miners[miner_id] = MinerReputation(miner_id=miner_id)
        return self.miners[miner_id]
    
    def record_epoch_participation(
        self,
        miner_id: str,
        epoch: int,
        clean_attestation: bool = True,
        full_participation: bool = True,
        on_time_settlement: bool = True
    ) -> int:
        """
        Record a miner's epoch participation and award RP.
        
        Args:
            miner_id: Unique miner identifier
            epoch: Epoch number
            clean_attestation: Whether attestation passed all checks
            full_participation: Whether miner participated full epoch
            on_time_settlement: Whether reward was claimed on time
        
        Returns:
            Total RP earned for this epoch
        """
        miner = self.get_or_create_miner(miner_id)
        
        # Check for extended absence
        if miner.last_epoch > 0:
            gap = epoch - miner.last_epoch
            if gap > self.EXTENDED_ABSENCE_THRESHOLD:
                self.apply_decay(miner_id, "extended_absence", self.DECAY_EXTENDED_ABSENCE, epoch)
                # Reset consecutive streak
                miner.epochs_consecutive = 0
        
        # Update epoch tracking
        miner.epochs_participated += 1
        if miner.last_epoch == epoch - 1 or miner.last_epoch == 0:
            miner.epochs_consecutive += 1
        else:
            miner.epochs_consecutive = 1
        miner.last_epoch = epoch
        
        # Calculate RP earned
        rp_earned = 0
        
        # Base RP for enrollment
        rp_earned += self.RP_ENROLLMENT
        
        # Bonus RP for clean attestation
        if clean_attestation:
            rp_earned += self.RP_CLEAN_ATTESTATION
            miner.attestation_history.passed += 1
        else:
            miner.attestation_history.failed += 1
            self.apply_decay(miner_id, "failed_attestation", self.DECAY_FAILED_ATTESTATION, epoch)
        
        miner.attestation_history.total += 1
        
        # Bonus RP for full participation
        if full_participation:
            rp_earned += self.RP_FULL_PARTICIPATION
        
        # Bonus RP for on-time settlement
        if on_time_settlement:
            rp_earned += self.RP_ON_TIME_SETTLEMENT
        
        # Apply recovery bonus if recently decayed
        if miner.decay_events:
            last_decay = miner.decay_events[-1]
            epochs_since_decay = epoch - last_decay.epoch
            if epochs_since_decay <= self.RECOVERY_BONUS_EPOCHS:
                # Apply recovery bonus to base RP (not bonuses)
                base_rp = self.RP_ENROLLMENT + self.RP_CLEAN_ATTESTATION
                bonus_rp = base_rp * (self.RECOVERY_BONUS_MULTIPLIER - 1.0)
                rp_earned += int(bonus_rp)

        # Cap RP at maximum (unless recovery bonus applies)
        if miner.decay_events and epochs_since_decay <= self.RECOVERY_BONUS_EPOCHS:
            # Allow exceeding cap during recovery period
            pass
        else:
            rp_earned = min(rp_earned, self.RP_PER_EPOCH_MAX)

        # Award RP
        miner.total_rp += rp_earned
        
        return rp_earned
    
    def record_challenge_result(
        self,
        miner_id: str,
        passed: bool,
        epoch: Optional[int] = None
    ) -> None:
        """
        Record a challenge-response result.
        
        Args:
            miner_id: Unique miner identifier
            passed: Whether the challenge was passed
            epoch: Current epoch (defaults to current_epoch)
        """
        if epoch is None:
            epoch = self.current_epoch
        
        miner = self.get_or_create_miner(miner_id)
        miner.challenge_history.total += 1
        
        if passed:
            miner.challenge_history.passed += 1
            # Award RP for successful challenge
            miner.total_rp += self.RP_CHALLENGE_RESPONSE
        else:
            miner.challenge_history.failed += 1
            # Apply decay for failed challenge
            self.apply_decay(miner_id, "challenge_failure", self.DECAY_CHALLENGE_FAILURE, epoch)
    
    def apply_decay(
        self,
        miner_id: str,
        reason: str,
        rp_lost: int,
        epoch: int
    ) -> int:
        """
        Apply reputation decay to a miner.
        
        Args:
            miner_id: Unique miner identifier
            reason: Reason for decay (e.g., "missed_epoch", "fleet_detection")
            rp_lost: Amount of RP to remove
            epoch: Current epoch number
        
        Returns:
            New total RP after decay
        """
        miner = self.get_or_create_miner(miner_id)
        
        # Ensure we don't go negative
        rp_lost = min(rp_lost, miner.total_rp)
        miner.total_rp -= rp_lost
        
        # Record decay event
        decay_event = DecayEvent(
            epoch=epoch,
            reason=reason,
            rp_lost=rp_lost,
            new_rp=miner.total_rp
        )
        miner.decay_events.append(decay_event)
        
        # Reset consecutive streak for serious offenses
        if reason in ["fleet_detection", "extended_absence"]:
            miner.epochs_consecutive = 0
        
        return miner.total_rp
    
    def record_missed_epoch(self, miner_id: str, epoch: int) -> None:
        """Record that a miner missed an epoch."""
        miner = self.get_or_create_miner(miner_id)
        
        # Only apply decay if miner has participated before
        if miner.last_epoch > 0:
            self.apply_decay(miner_id, "missed_epoch", self.DECAY_MISSED_EPOCH, epoch)
    
    def record_fleet_detection(self, miner_id: str, epoch: int) -> None:
        """Record fleet detection event for a miner."""
        self.apply_decay(miner_id, "fleet_detection", self.DECAY_FLEET_DETECTION, epoch)
    
    def get_reputation_leaderboard(
        self,
        limit: int = 10,
        tier_filter: Optional[str] = None
    ) -> List[dict]:
        """
        Get reputation leaderboard.
        
        Args:
            limit: Number of entries to return
            tier_filter: Optional filter by loyalty tier
        
        Returns:
            List of miner reputation summaries, sorted by reputation score
        """
        miners = list(self.miners.values())
        
        # Apply tier filter if specified
        if tier_filter:
            miners = [m for m in miners if m.loyalty_tier.value == tier_filter]
        
        # Sort by reputation score (descending)
        miners.sort(key=lambda m: (m.reputation_score, m.epochs_participated), reverse=True)
        
        # Return top N
        leaderboard = []
        for i, miner in enumerate(miners[:limit], 1):
            entry = miner.to_dict()
            entry["rank"] = i
            leaderboard.append(entry)
        
        return leaderboard
    
    def get_epoch_summary(self, epoch: int) -> dict:
        """
        Get reputation summary for a specific epoch.
        
        Args:
            epoch: Epoch number
        
        Returns:
            Summary statistics for the epoch
        """
        if epoch not in self.epoch_history:
            return {
                "epoch": epoch,
                "participating_miners": 0,
                "average_reputation": 0.0,
                "tier_distribution": {},
                "total_rp_earned": 0,
                "decay_events": 0
            }
        
        return self.epoch_history[epoch]
    
    def calculate_miner_projection(
        self,
        miner_id: str,
        epochs_ahead: int = 100
    ) -> dict:
        """
        Calculate projected reputation at future epochs.
        
        Args:
            miner_id: Unique miner identifier
            epochs_ahead: Number of epochs to project
        
        Returns:
            Projection data including future score and multiplier
        """
        miner = self.get_or_create_miner(miner_id)
        
        # Assume perfect participation (max RP per epoch)
        projected_rp = miner.total_rp + (self.RP_PER_EPOCH_MAX * epochs_ahead)
        projected_score = min(self.REPUTATION_CAP, 1.0 + (projected_rp / 100.0))
        projected_multiplier = 1.0 + ((projected_score - 1.0) * 0.25)
        
        # Calculate epochs to next tier
        epochs_to_next = miner.epochs_to_next_tier
        will_reach_tier = epochs_ahead >= epochs_to_next if epochs_to_next > 0 else False
        
        return {
            "current_rp": miner.total_rp,
            "current_score": round(miner.reputation_score, 4),
            "current_multiplier": round(miner.reputation_multiplier, 4),
            "projected_rp": projected_rp,
            "projected_score": round(projected_score, 4),
            "projected_multiplier": round(projected_multiplier, 4),
            "epochs_ahead": epochs_ahead,
            "epochs_to_next_tier": epochs_to_next,
            "next_tier": miner.next_tier_name,
            "will_reach_tier": will_reach_tier
        }
    
    def get_global_stats(self) -> dict:
        """Get global reputation system statistics."""
        if not self.miners:
            return {
                "current_epoch": self.current_epoch,
                "total_miners": 0,
                "reputation_holders": {},
                "average_reputation_score": 0.0,
                "total_rp_distributed": 0
            }
        
        # Count tier distribution
        tier_counts = {tier.value: 0 for tier in LoyaltyTier}
        total_score = 0.0
        total_rp = 0
        
        for miner in self.miners.values():
            tier_counts[miner.loyalty_tier.value] += 1
            total_score += miner.reputation_score
            total_rp += miner.total_rp
        
        return {
            "current_epoch": self.current_epoch,
            "total_miners": len(self.miners),
            "reputation_holders": {
                "diamond": tier_counts["diamond"],
                "platinum": tier_counts["platinum"],
                "gold": tier_counts["gold"],
                "silver": tier_counts["silver"],
                "bronze": tier_counts["bronze"],
                "none": tier_counts["none"]
            },
            "average_reputation_score": round(total_score / len(self.miners), 4),
            "total_rp_distributed": total_rp
        }
    
    def export_state(self) -> dict:
        """Export complete reputation system state."""
        return {
            "current_epoch": self.current_epoch,
            "miners": {mid: m.to_dict() for mid, m in self.miners.items()},
            "epoch_history": self.epoch_history,
            "config": {
                "RP_PER_EPOCH_MAX": self.RP_PER_EPOCH_MAX,
                "REPUTATION_CAP": self.REPUTATION_CAP,
                "DECAY_MISSED_EPOCH": self.DECAY_MISSED_EPOCH,
                "DECAY_FAILED_ATTESTATION": self.DECAY_FAILED_ATTESTATION,
                "DECAY_FLEET_DETECTION": self.DECAY_FLEET_DETECTION,
                "DECAY_CHALLENGE_FAILURE": self.DECAY_CHALLENGE_FAILURE,
                "DECAY_EXTENDED_ABSENCE": self.DECAY_EXTENDED_ABSENCE
            }
        }
    
    def import_state(self, state: dict) -> None:
        """Import reputation system state."""
        self.current_epoch = state.get("current_epoch", 0)
        self.epoch_history = state.get("epoch_history", {})
        
        for miner_id, miner_data in state.get("miners", {}).items():
            self.miners[miner_id] = MinerReputation.from_dict(miner_data)


# Convenience functions for direct use
def calculate_reputation_score(total_rp: int) -> float:
    """Calculate reputation score from total RP."""
    return max(1.0, min(5.0, 1.0 + (total_rp / 100.0)))


def calculate_reputation_multiplier(reputation_score: float) -> float:
    """Calculate reputation multiplier from reputation score."""
    return 1.0 + ((reputation_score - 1.0) * 0.25)


def get_loyalty_tier(epochs: int) -> LoyaltyTier:
    """Get loyalty tier from epoch count."""
    if epochs >= 1000:
        return LoyaltyTier.DIAMOND
    elif epochs >= 500:
        return LoyaltyTier.PLATINUM
    elif epochs >= 100:
        return LoyaltyTier.GOLD
    elif epochs >= 50:
        return LoyaltyTier.SILVER
    elif epochs >= 10:
        return LoyaltyTier.BRONZE
    else:
        return LoyaltyTier.NONE


def get_loyalty_bonus(tier: LoyaltyTier) -> float:
    """Get loyalty bonus multiplier from tier."""
    bonuses = {
        LoyaltyTier.DIAMOND: 2.00,
        LoyaltyTier.PLATINUM: 1.50,
        LoyaltyTier.GOLD: 1.20,
        LoyaltyTier.SILVER: 1.10,
        LoyaltyTier.BRONZE: 1.05,
        LoyaltyTier.NONE: 1.00
    }
    return bonuses[tier]


def calculate_combined_multiplier(
    antiquity_multiplier: float,
    total_rp: int,
    epochs_participated: int
) -> float:
    """
    Calculate final combined multiplier including all factors.
    
    Args:
        antiquity_multiplier: Base antiquity multiplier (from RIP-200)
        total_rp: Total reputation points
        epochs_participated: Total epochs participated
    
    Returns:
        Combined multiplier for reward calculation
    """
    rep_score = calculate_reputation_score(total_rp)
    rep_multiplier = calculate_reputation_multiplier(rep_score)
    loyalty_bonus = get_loyalty_bonus(get_loyalty_tier(epochs_participated))
    
    return antiquity_multiplier * rep_multiplier * loyalty_bonus


if __name__ == "__main__":
    # Demo usage
    print("=== RIP-302 Reputation System Demo ===\n")
    
    # Create reputation system
    system = ReputationSystem()
    
    # Simulate miner participation
    miner_id = "RTC_vintage_g4_001"
    
    print(f"Simulating 150 epochs for miner: {miner_id}\n")
    
    for epoch in range(1, 151):
        system.current_epoch = epoch
        system.record_epoch_participation(
            miner_id=miner_id,
            epoch=epoch,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
        
        # Record a challenge at epoch 50
        if epoch == 50:
            system.record_challenge_result(miner_id, passed=True, epoch=epoch)
        
        # Simulate one failed attestation at epoch 75
        if epoch == 75:
            system.record_epoch_participation(
                miner_id=miner_id,
                epoch=epoch,
                clean_attestation=False,
                full_participation=True,
                on_time_settlement=True
            )
    
    # Get miner reputation
    miner = system.get_or_create_miner(miner_id)
    
    print("=== Miner Reputation Summary ===")
    print(f"Miner ID: {miner.miner_id}")
    print(f"Total RP: {miner.total_rp}")
    print(f"Reputation Score: {miner.reputation_score:.4f}")
    print(f"Reputation Multiplier: {miner.reputation_multiplier:.4f}x")
    print(f"Loyalty Tier: {miner.loyalty_tier.value}")
    print(f"Loyalty Bonus: {miner.loyalty_bonus:.4f}x")
    print(f"Combined Multiplier: {miner.combined_multiplier:.4f}x")
    print(f"Epochs Participated: {miner.epochs_participated}")
    print(f"Epochs Consecutive: {miner.epochs_consecutive}")
    print(f"Attestation Pass Rate: {miner.attestation_history.pass_rate:.2%}")
    print(f"Challenge Pass Rate: {miner.challenge_history.pass_rate:.2%}")
    print(f"Decay Events: {len(miner.decay_events)}")
    print(f"Epochs to Next Tier: {miner.epochs_to_next_tier}")
    print(f"\nFull JSON:\n{miner.to_json()}")
    
    print("\n\n=== Global Statistics ===")
    stats = system.get_global_stats()
    print(json.dumps(stats, indent=2))
    
    print("\n\n=== Leaderboard (Top 5) ===")
    leaderboard = system.get_reputation_leaderboard(limit=5)
    for entry in leaderboard:
        print(f"#{entry['rank']}: {entry['miner_id']} - "
              f"Score: {entry['reputation_score']:.4f}, "
              f"Tier: {entry['loyalty_tier']}")
