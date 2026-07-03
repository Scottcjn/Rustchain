"""RIP-310 Platform-Specific Reward Calculations.

Exact reward rates and daily caps per the RIP-310 specification:
  - Post on Moltbook: 0.01 RTC, 5 posts/day cap
  - Post on 4claw: 0.01 RTC, 5 threads/day cap
  - Upload video on BoTTube: 0.05 RTC, 3 videos/day cap
  - Comment (substantive, >50 chars): 0.002 RTC, 20/day cap
  - Receive upvote: 0.001 RTC, uncapped
  - Receive tip: full amount minus 8% fee, uncapped
"""

from dataclasses import dataclass
from typing import Optional

from social_mining import (
    ActionType,
    BeaconID,
    Platform,
    SocialAction,
    SocialMiningEngine,
)


@dataclass
class RewardRule:
    action_type: ActionType
    rtc_reward: float
    daily_cap: Optional[int]  # None = uncapped


REWARD_TABLE: dict[tuple[Platform, ActionType], RewardRule] = {
    (Platform.MOLTBOOK, ActionType.POST): RewardRule(
        action_type=ActionType.POST, rtc_reward=0.01, daily_cap=5
    ),
    (Platform.FOURCLAW, ActionType.THREAD): RewardRule(
        action_type=ActionType.THREAD, rtc_reward=0.01, daily_cap=5
    ),
    (Platform.BOTUBE, ActionType.VIDEO): RewardRule(
        action_type=ActionType.VIDEO, rtc_reward=0.05, daily_cap=3
    ),
    (Platform.MOLTBOOK, ActionType.COMMENT): RewardRule(
        action_type=ActionType.COMMENT, rtc_reward=0.002, daily_cap=20
    ),
    (Platform.FOURCLAW, ActionType.COMMENT): RewardRule(
        action_type=ActionType.COMMENT, rtc_reward=0.002, daily_cap=20
    ),
    (Platform.BOTUBE, ActionType.COMMENT): RewardRule(
        action_type=ActionType.COMMENT, rtc_reward=0.002, daily_cap=20
    ),
    (Platform.MOLTBOOK, ActionType.UPVOTE_RECEIVED): RewardRule(
        action_type=ActionType.UPVOTE_RECEIVED, rtc_reward=0.001, daily_cap=None
    ),
    (Platform.FOURCLAW, ActionType.UPVOTE_RECEIVED): RewardRule(
        action_type=ActionType.UPVOTE_RECEIVED, rtc_reward=0.001, daily_cap=None
    ),
    (Platform.BOTUBE, ActionType.UPVOTE_RECEIVED): RewardRule(
        action_type=ActionType.UPVOTE_RECEIVED, rtc_reward=0.001, daily_cap=None
    ),
}

TIP_FEE_RATE = 0.08  # 8% platform fee


class PlatformRewardCalculator:
    """Calculates rewards per RIP-310 specification."""

    def __init__(self, engine: SocialMiningEngine) -> None:
        self.engine = engine

    def get_reward_rule(
        self, platform: Platform, action_type: ActionType
    ) -> Optional[RewardRule]:
        return REWARD_TABLE.get((platform, action_type))

    def calculate_reward(self, action: SocialAction) -> float:
        rule = self.get_reward_rule(action.platform, action.action_type)
        if rule is None:
            return 0.0

        # Enforce content quality for comments
        if action.action_type == ActionType.COMMENT and action.comment_length <= 50:
            return 0.0

        # Enforce daily cap
        if rule.daily_cap is not None:
            today_count = self.engine.get_actions_today(
                action.beacon.beacon_hash, action.action_type
            )
            if today_count >= rule.daily_cap:
                return 0.0

        return rule.rtc_reward

    def calculate_tip_reward(self, tip_amount: float) -> float:
        """Tip reward: full amount minus 8% platform fee to social_mining_pool."""
        if tip_amount <= 0:
            return 0.0
        fee = tip_amount * TIP_FEE_RATE
        return tip_amount - fee

    def process_tip(self, action: SocialAction, tip_amount: float) -> float:
        """Process a tip action: collect fee into treasury, return net to user."""
        if action.action_type != ActionType.TIP_RECEIVED:
            return 0.0
        if tip_amount <= 0:
            return 0.0
        net = self.calculate_tip_reward(tip_amount)
        self.engine.treasury.collect_tip_fee(tip_amount)
        return net

    def process_action(self, action: SocialAction) -> float:
        """Process any social action and return the RTC reward."""
        if not action.beacon.verify():
            return 0.0

        if action.action_type == ActionType.TIP_RECEIVED:
            return self.process_tip(action, action.tip_amount or 0.0)

        reward = self.calculate_reward(action)
        if reward > 0:
            self.engine.record_reward(action, reward)
        return reward
