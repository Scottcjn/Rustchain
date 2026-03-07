"""
Reward Agent (Agent 3)

Calculates and distributes RTC rewards for validated and settled
transactions. Handles reward tiers, multipliers, and distribution
receipts.
"""

import hashlib
import json
import time
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class RewardTier(Enum):
    """Reward calculation tiers"""
    MICRO = "micro"  # 1-10 RTC
    STANDARD = "standard"  # 20-50 RTC
    MAJOR = "major"  # 75-100 RTC
    CRITICAL = "critical"  # 100-150 RTC


class RewardType(Enum):
    """Types of rewards"""
    VALIDATION = "validation"
    MINING = "mining"
    BOUNTY = "bounty"
    REFERRAL = "referral"
    LOYALTY = "loyalty"


@dataclass
class RewardDistribution:
    """Record of a reward distribution"""
    distribution_id: str
    reward_type: str
    amount: float
    recipient: str
    source: str
    timestamp: str
    transaction_reference: str
    multiplier: float
    tier: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RewardAgent:
    """
    Agent 3: Reward Agent
    
    Responsibilities:
    - Calculate rewards based on transaction type and tier
    - Apply multipliers (hardware age, loyalty, etc.)
    - Distribute rewards to recipients
    - Track reward pool balance
    - Generate distribution receipts
    """
    
    # Base reward rates (RTC)
    BASE_RATES = {
        RewardType.VALIDATION: 5.0,
        RewardType.MINING: 10.0,
        RewardType.BOUNTY: 50.0,
        RewardType.REFERRAL: 2.0,
        RewardType.LOYALTY: 1.0
    }
    
    # Tier multipliers
    TIER_MULTIPLIERS = {
        RewardTier.MICRO: 1.0,
        RewardTier.STANDARD: 2.0,
        RewardTier.MAJOR: 5.0,
        RewardTier.CRITICAL: 10.0
    }
    
    def __init__(
        self,
        agent_id: str = "reward-001",
        mode: str = "mock",
        reward_pool_balance: float = 10000.0
    ):
        self.agent_id = agent_id
        self.mode = mode
        self.reward_pool_balance = reward_pool_balance
        self.initial_pool_balance = reward_pool_balance
        
        self.distributions: List[RewardDistribution] = []
        self.stats = {
            "total_distributed": 0,
            "total_recipients": 0,
            "average_reward": 0.0,
            "largest_reward": 0.0
        }
        
        logger.info(f"RewardAgent {agent_id} initialized in {mode} mode")
    
    def calculate_reward(
        self,
        reward_type: RewardType,
        tier: RewardTier = RewardTier.STANDARD,
        base_amount: Optional[float] = None,
        multipliers: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate reward amount based on type, tier, and multipliers.
        
        Args:
            reward_type: Type of reward
            tier: Reward tier
            base_amount: Optional base amount (overrides BASE_RATES)
            multipliers: Additional multipliers to apply
            
        Returns:
            Calculated reward amount in RTC
        """
        base = base_amount if base_amount else self.BASE_RATES[reward_type]
        tier_mult = self.TIER_MULTIPLIERS[tier]
        
        # Apply tier multiplier
        reward = base * tier_mult
        
        # Apply additional multipliers
        if multipliers:
            for name, mult in multipliers.items():
                logger.debug(f"Applying multiplier {name}: {mult}x")
                reward *= mult
        
        # Round to 2 decimal places
        reward = round(reward, 2)
        
        logger.info(
            f"Calculated reward: {reward} RTC "
            f"(base={base}, tier={tier.value}, type={reward_type.value})"
        )
        
        return reward
    
    def distribute_reward(
        self,
        reward_type: RewardType,
        recipient: str,
        amount: float,
        transaction_reference: str,
        tier: RewardTier = RewardTier.STANDARD,
        multipliers: Optional[Dict[str, float]] = None,
        source: str = "0xREWARD_POOL"
    ) -> Optional[RewardDistribution]:
        """
        Distribute a reward to a recipient.
        
        Args:
            reward_type: Type of reward
            recipient: Recipient wallet address
            amount: Reward amount (if 0, will be calculated)
            transaction_reference: Reference to original transaction
            tier: Reward tier
            multipliers: Additional multipliers
            source: Source of funds
            
        Returns:
            RewardDistribution if successful, None if failed
        """
        # Calculate final amount if not provided
        if amount <= 0:
            amount = self.calculate_reward(
                reward_type, tier, multipliers=multipliers
            )
        
        # Check pool balance
        if amount > self.reward_pool_balance:
            logger.error(
                f"Insufficient pool balance: need {amount}, have {self.reward_pool_balance}"
            )
            return None
        
        distribution_id = hashlib.sha256(
            f"{recipient}{transaction_reference}{time.time()}".encode()
        ).hexdigest()[:16]
        
        if self.mode == "mock":
            # Mock mode: simulate distribution
            time.sleep(0.02)  # Simulate processing
            
            # Deduct from pool
            self.reward_pool_balance -= amount
        else:
            # Real mode: would execute actual transfer
            logger.info(f"REAL mode: Would transfer {amount} RTC to {recipient}")
            self.reward_pool_balance -= amount
        
        distribution = RewardDistribution(
            distribution_id=distribution_id,
            reward_type=reward_type.value,
            amount=amount,
            recipient=recipient,
            source=source,
            timestamp=datetime.utcnow().isoformat() + "Z",
            transaction_reference=transaction_reference,
            multiplier=self.TIER_MULTIPLIERS[tier],
            tier=tier.value,
            metadata={
                "mode": self.mode,
                "base_rate": self.BASE_RATES[reward_type],
                "multipliers_applied": multipliers or {}
            }
        )
        
        self.distributions.append(distribution)
        
        # Update stats
        self.stats["total_distributed"] += 1
        unique_recipients = len(set(d.recipient for d in self.distributions))
        self.stats["total_recipients"] = unique_recipients
        self.stats["average_reward"] = (
            (self.initial_pool_balance - self.reward_pool_balance) /
            self.stats["total_distributed"]
        )
        self.stats["largest_reward"] = max(
            self.stats["largest_reward"], amount
        )
        
        logger.info(
            f"Reward distributed: {amount} RTC to {recipient} "
            f"(distribution_id: {distribution_id})"
        )
        
        return distribution
    
    def get_distribution_receipt(
        self,
        distribution: RewardDistribution
    ) -> Dict[str, Any]:
        """
        Generate cryptographic receipt for reward distribution.
        
        Returns:
            Distribution receipt for verification
        """
        receipt_data = {
            "distribution_id": distribution.distribution_id,
            "recipient": distribution.recipient,
            "amount": distribution.amount,
            "reward_type": distribution.reward_type,
            "tier": distribution.tier,
            "timestamp": distribution.timestamp
        }
        
        receipt_hash = hashlib.sha256(
            json.dumps(receipt_data, sort_keys=True).encode()
        ).hexdigest()
        
        return {
            "receipt_type": "reward_distribution_receipt",
            "receipt_hash": receipt_hash,
            "data": receipt_data,
            "issued_by": self.agent_id,
            "issued_at": datetime.utcnow().isoformat() + "Z",
            "pool_balance_remaining": self.reward_pool_balance,
            "verifiable": True
        }
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get current reward pool status"""
        return {
            "initial_balance": self.initial_pool_balance,
            "current_balance": self.reward_pool_balance,
            "total_distributed": self.initial_pool_balance - self.reward_pool_balance,
            "distribution_count": len(self.distributions),
            "utilization_percent": round(
                (self.initial_pool_balance - self.reward_pool_balance) /
                self.initial_pool_balance * 100,
                2
            )
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            "agent_id": self.agent_id,
            "mode": self.mode,
            **self.stats,
            "pool_status": self.get_pool_status()
        }


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)
    
    agent = RewardAgent(mode="mock", reward_pool_balance=10000.0)
    
    # Test reward calculation
    reward = agent.calculate_reward(
        reward_type=RewardType.VALIDATION,
        tier=RewardTier.MAJOR,
        multipliers={"hardware_age": 1.5, "loyalty": 1.2}
    )
    print(f"Calculated reward: {reward} RTC")
    
    # Test distribution
    distribution = agent.distribute_reward(
        reward_type=RewardType.BOUNTY,
        recipient="0xCONTRIBUTOR789",
        amount=0,  # Calculate automatically
        transaction_reference="tx-bounty-685",
        tier=RewardTier.CRITICAL,
        multipliers={"early_adopter": 1.5}
    )
    
    if distribution:
        print("\n=== Reward Distribution ===")
        print(json.dumps(distribution.to_dict(), indent=2))
        
        receipt = agent.get_distribution_receipt(distribution)
        print("\n=== Distribution Receipt ===")
        print(json.dumps(receipt, indent=2))
    
    print("\n=== Pool Status ===")
    print(json.dumps(agent.get_pool_status(), indent=2))
    
    print("\n=== Agent Stats ===")
    print(json.dumps(agent.get_stats(), indent=2))
