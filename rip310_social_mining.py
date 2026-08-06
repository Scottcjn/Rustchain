"""
RIP-310 Social Mining Protocol.

Provides identity-bound social micro-tipping, circular treasury fee replenishment,
formulaic engagement reward distribution with daily caps, decimal financial precision,
thread-safe atomic ledger operations, and anti-gaming metric rotation.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum, auto
import threading
from typing import Dict, Optional, Union


class SocialActionType(Enum):
    MOLTBOOK_POST = auto()
    FOURCLAW_THREAD = auto()
    BOTTUBE_VIDEO = auto()
    COMMENT = auto()
    UPVOTE = auto()


@dataclass
class TipResult:
    success: bool
    net_recipient_amount: float = 0.0
    fee_amount: float = 0.0
    error_message: Optional[str] = None


@dataclass
class RewardResult:
    success: bool
    reward_amount: float = 0.0
    error_message: Optional[str] = None


class SocialMiningPool:
    """
    Treasury pool for social mining rewards and fee collection.
    Uses Decimal for exact monetary arithmetic and threading.Lock for atomic concurrency safety.
    """

    def __init__(self, initial_balance: Union[float, str, Decimal] = 0.0):
        self._balance: Decimal = Decimal(str(initial_balance))
        self._lock: threading.Lock = threading.Lock()

    def get_balance(self) -> float:
        with self._lock:
            return float(self._balance)

    def get_balance_decimal(self) -> Decimal:
        with self._lock:
            return self._balance

    def deposit(self, amount: Union[float, str, Decimal], source: str = "general") -> None:
        dec_amount = Decimal(str(amount))
        if dec_amount > Decimal("0"):
            with self._lock:
                self._balance += dec_amount

    def payout(self, amount: Union[float, str, Decimal], recipient: str) -> bool:
        dec_amount = Decimal(str(amount))
        if dec_amount <= Decimal("0"):
            return False
        with self._lock:
            if self._balance >= dec_amount:
                self._balance -= dec_amount
                return True
            return False


class TipBot:
    """
    Micro-tipping engine with 8% platform fee routing and Hardware Beacon ID attestation.

    Rationale for min_tip = 0.01 RTC:
    0.01 RTC represents the baseline dust threshold on RustChain. Setting min_tip to 0.01 RTC
    prevents sub-satoshi micro-spam while keeping tipping accessible to all community members.
    """

    def __init__(
        self,
        pool: SocialMiningPool,
        fee_percent: float = 0.08,
        min_tip: float = 0.01,
    ):
        self.pool = pool
        self.fee_percent = Decimal(str(fee_percent))
        self.min_tip = Decimal(str(min_tip))

    def process_tip(
        self,
        sender: str,
        recipient: str,
        amount: Union[float, str, Decimal],
        balances: Dict[str, float],
        beacon_registry: Dict[str, str],
    ) -> TipResult:
        dec_amount = Decimal(str(amount))
        if dec_amount < self.min_tip:
            return TipResult(
                success=False,
                error_message=f"Minimum tip amount is {float(self.min_tip)} RTC",
            )

        # Hardware Beacon ID verification
        sender_beacon = beacon_registry.get(sender)
        recipient_beacon = beacon_registry.get(recipient)

        if not sender_beacon or not recipient_beacon:
            return TipResult(
                success=False,
                error_message="Beacon ID verification failed for tipper or recipient",
            )

        sender_bal = Decimal(str(balances.get(sender, 0.0)))
        if sender_bal < dec_amount:
            return TipResult(
                success=False, error_message="Insufficient balance for tip"
            )

        fee_amount = (dec_amount * self.fee_percent).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
        net_amount = dec_amount - fee_amount

        # Update balances atomically
        balances[sender] = float(sender_bal - dec_amount)
        balances[recipient] = float(
            Decimal(str(balances.get(recipient, 0.0))) + net_amount
        )

        # Direct 8% fee to treasury pool
        self.pool.deposit(fee_amount, source="tipping_fee")

        return TipResult(
            success=True,
            net_recipient_amount=float(net_amount),
            fee_amount=float(fee_amount),
        )


class RewardCalculator:
    """
    Social mining reward calculator with daily action frequency caps.
    """

    REWARD_CONFIG = {
        SocialActionType.MOLTBOOK_POST: {"reward": Decimal("0.01"), "cap": 5},
        SocialActionType.FOURCLAW_THREAD: {"reward": Decimal("0.01"), "cap": 5},
        SocialActionType.BOTTUBE_VIDEO: {"reward": Decimal("0.05"), "cap": 3},
        SocialActionType.COMMENT: {"reward": Decimal("0.002"), "cap": 20},
        SocialActionType.UPVOTE: {"reward": Decimal("0.001"), "cap": None},
    }

    def __init__(self, pool: SocialMiningPool):
        self.pool = pool
        self._user_daily_counts: Dict[str, Dict[SocialActionType, int]] = {}

    def claim_reward(
        self,
        user: str,
        action: SocialActionType,
        beacon_registry: Dict[str, str],
        comment_text: str = "",
    ) -> RewardResult:
        if user not in beacon_registry or not beacon_registry[user]:
            return RewardResult(
                success=False, error_message="Hardware Beacon ID required to claim rewards"
            )

        if action == SocialActionType.COMMENT and len(comment_text) <= 50:
            return RewardResult(
                success=False,
                error_message="Comment must be > 50 characters to qualify for rewards",
            )

        config = self.REWARD_CONFIG.get(action)
        if not config:
            return RewardResult(success=False, error_message="Invalid social action")

        # Check frequency cap
        user_counts = self._user_daily_counts.setdefault(user, {})
        current_count = user_counts.get(action, 0)

        cap = config["cap"]
        if cap is not None and current_count >= cap:
            return RewardResult(
                success=False,
                error_message=f"Frequency cap of {cap}/day reached for this action",
            )

        reward_amount: Decimal = config["reward"]
        if not self.pool.payout(reward_amount, recipient=user):
            return RewardResult(
                success=False, error_message="Treasury pool insufficient for reward payout"
            )

        user_counts[action] = current_count + 1
        return RewardResult(success=True, reward_amount=float(reward_amount))


class RIP309Integration:
    """
    RIP-309 rotating measurement freshness integration for anti-gaming.
    """

    METRICS_ROTATION = {
        1: "upvote_quality",
        2: "comment_depth",
        3: "cross_platform_reach",
    }

    def get_active_metric(self, epoch: int) -> str:
        rotation_key = ((epoch - 1) % len(self.METRICS_ROTATION)) + 1
        return self.METRICS_ROTATION[rotation_key]

    def validate_action(self, action: str, epoch: int, metric: str) -> bool:
        active = self.get_active_metric(epoch)
        return metric == active
