"""RIP-310 Social Mining Protocol - Core Logic.

Beacon ID verification, reward tracking, and epoch settlement for
social mining on 4claw, Moltbook, and BoTTube.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import hashlib
import time


class Platform(Enum):
    MOLTBOOK = "moltbook"
    FOURCLAW = "4claw"
    BOTUBE = "botube"


class ActionType(Enum):
    POST = "post"
    THREAD = "thread"
    VIDEO = "video"
    COMMENT = "comment"
    UPVOTE_RECEIVED = "upvote_received"
    TIP_RECEIVED = "tip_received"


class EpochState(Enum):
    ACTIVE = "active"
    SETTLED = "settled"
    FINALIZED = "finalized"


@dataclass
class BeaconID:
    """Hardware-attested identity for a social mining participant."""
    beacon_hash: str
    public_key: str
    registered_at: float = field(default_factory=time.time)
    is_active: bool = True

    def verify(self) -> bool:
        if not self.is_active:
            return False
        if not self.beacon_hash or len(self.beacon_hash) < 64:
            return False
        return True

    @staticmethod
    def generate_from_key(public_key: str) -> "BeaconID":
        h = hashlib.sha256(public_key.encode()).hexdigest()
        return BeaconID(beacon_hash=h, public_key=public_key)


@dataclass
class SocialAction:
    """A single social mining action submitted for reward."""
    action_id: str
    platform: Platform
    action_type: ActionType
    beacon: BeaconID
    content_hash: str
    timestamp: float = field(default_factory=time.time)
    tip_amount: Optional[float] = None  # only for TIP_RECEIVED
    comment_length: int = 0  # only for COMMENT


@dataclass
class RewardRecord:
    """Record of a reward credited to a participant."""
    action_id: str
    beacon_hash: str
    platform: Platform
    action_type: ActionType
    rtc_amount: float
    epoch_id: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class Epoch:
    """An epoch period for settlement."""
    epoch_id: int
    start_time: float
    end_time: float
    state: EpochState = EpochState.ACTIVE

    def is_active(self) -> bool:
        return self.state == EpochState.ACTIVE

    def is_within(self, timestamp: float) -> bool:
        return self.start_time <= timestamp < self.end_time

    def settle(self) -> None:
        if self.state == EpochState.ACTIVE:
            self.state = EpochState.SETTLED

    def finalize(self) -> None:
        if self.state == EpochState.SETTLED:
            self.state = EpochState.FINALIZED


@dataclass
class TreasuryPool:
    """Treasury pool for social mining rewards."""
    total_inflow: float = 0.0
    total_outflow: float = 0.0
    balance: float = 0.0
    tip_fee_rate: float = 0.08  # 8% platform fee on tips

    def deposit(self, amount: float) -> None:
        self.total_inflow += amount
        self.balance += amount

    def withdraw_reward(self, amount: float) -> bool:
        if amount > self.balance:
            return False
        self.total_outflow += amount
        self.balance -= amount
        return True

    def collect_tip_fee(self, tip_amount: float) -> float:
        fee = tip_amount * self.tip_fee_rate
        self.deposit(fee)
        return fee


class SocialMiningEngine:
    """Core engine coordinating Beacon verification, rewards, and epochs."""

    def __init__(self) -> None:
        self.beacons: dict[str, BeaconID] = {}
        self.epochs: list[Epoch] = []
        self.current_epoch: Optional[Epoch] = None
        self.reward_records: list[RewardRecord] = []
        self.treasury = TreasuryPool()
        self._action_history: dict[str, list[str]] = {}  # beacon_hash -> [action_ids]

    def register_beacon(self, public_key: str) -> BeaconID:
        beacon = BeaconID.generate_from_key(public_key)
        self.beacons[beacon.beacon_hash] = beacon
        return beacon

    def get_beacon(self, beacon_hash: str) -> Optional[BeaconID]:
        return self.beacons.get(beacon_hash)

    def start_epoch(self, duration_seconds: float) -> Epoch:
        if self.current_epoch and self.current_epoch.is_active():
            self.current_epoch.settle()
        now = time.time()
        epoch = Epoch(
            epoch_id=len(self.epochs),
            start_time=now,
            end_time=now + duration_seconds,
        )
        self.epochs.append(epoch)
        self.current_epoch = epoch
        return epoch

    def settle_current_epoch(self) -> Optional[Epoch]:
        if self.current_epoch and self.current_epoch.is_active():
            self.current_epoch.settle()
            settled = self.current_epoch
            self.current_epoch = None
            return settled
        return None

    def record_reward(self, action: SocialAction, rtc_amount: float) -> RewardRecord:
        if self.current_epoch is None:
            raise RuntimeError("No active epoch to record rewards in")
        record = RewardRecord(
            action_id=action.action_id,
            beacon_hash=action.beacon.beacon_hash,
            platform=action.platform,
            action_type=action.action_type,
            rtc_amount=rtc_amount,
            epoch_id=self.current_epoch.epoch_id,
        )
        self.reward_records.append(record)
        self.treasury.withdraw_reward(rtc_amount)
        self._action_history.setdefault(action.beacon.beacon_hash, []).append(action.action_id)
        return record

    def get_rewards_for_epoch(self, epoch_id: int) -> list[RewardRecord]:
        return [r for r in self.reward_records if r.epoch_id == epoch_id]

    def get_rewards_for_beacon(self, beacon_hash: str) -> list[RewardRecord]:
        return [r for r in self.reward_records if r.beacon_hash == beacon_hash]

    def total_rewards_for_epoch(self, epoch_id: int) -> float:
        return sum(r.rtc_amount for r in self.get_rewards_for_epoch(epoch_id))

    def get_actions_today(self, beacon_hash: str, action_type: ActionType) -> int:
        """Count actions of a given type for a beacon in the current day."""
        today_start = self._today_start()
        count = 0
        for record in self.reward_records:
            if record.beacon_hash == beacon_hash and record.action_type == action_type:
                if record.timestamp >= today_start:
                    count += 1
        return count

    @staticmethod
    def _today_start() -> float:
        t = time.time()
        return t - (t % 86400)
