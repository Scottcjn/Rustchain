# SPDX-License-Identifier: Apache-2.0
"""
RIP-310: Social Mining Protocol Engine
Enables circular RTC economy across Moltbook, 4claw, and BoTTube with:
- Beacon ID hardware-attested identity verification
- Social Mining Pool treasury accounting (8% platform tip fee + 10% epoch mining inflow)
- Daily frequency-capped social engagement rewards
- RIP-309 rotating epoch measurement nonces for anti-gaming
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Set


RTC_QUANT = Decimal("0.000001")
MIN_TIP_RTC = Decimal("0.01")
TIP_FEE_RATE = Decimal("0.08")
REACTION_TIP_AMOUNTS: Dict[str, Decimal] = {
    "🦞": Decimal("0.1"),
}

ACTION_REWARDS: Dict[str, Decimal] = {
    "moltbook_post": Decimal("0.01"),
    "4claw_post": Decimal("0.01"),
    "bottube_video": Decimal("0.05"),
    "substantive_comment": Decimal("0.002"),
    "upvote_received": Decimal("0.001"),
}

DAILY_CAPS: Dict[str, Optional[int]] = {
    "moltbook_post": 5,
    "4claw_post": 5,
    "bottube_video": 3,
    "substantive_comment": 20,
    "upvote_received": None,  # Uncapped
}

RIP309_METRICS = (
    "posting_frequency",
    "comment_depth",
    "upvote_quality",
    "cross_platform_consistency",
)


def _quantize(amount: Decimal | float | str) -> Decimal:
    return Decimal(str(amount)).quantize(RTC_QUANT, rounding=ROUND_DOWN)


@dataclass
class TipResult:
    sender: str
    recipient: str
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    pool_balance: Decimal


@dataclass
class SocialMiningPool:
    """Treasury wallet for RIP-310 social mining rewards and tip fees."""

    wallet_id: str = "social_mining_pool"
    balance: Decimal = field(default_factory=lambda: Decimal("0"))
    registered_beacons: Set[str] = field(default_factory=set)
    user_balances: Dict[str, Decimal] = field(default_factory=dict)
    daily_action_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def register_beacon(self, username: str, beacon_id: str, initial_balance: Decimal = Decimal("0")) -> None:
        if not username or not beacon_id or not beacon_id.strip():
            raise ValueError("Valid username and hardware-attested Beacon ID are required")
        self.registered_beacons.add(username)
        self.user_balances.setdefault(username, _quantize(initial_balance))

    def has_beacon(self, username: str) -> bool:
        return username in self.registered_beacons

    def deposit_bootstrap(self, amount: Decimal | float | str, source: str = "founder_community") -> Decimal:
        val = _quantize(amount)
        if val <= Decimal("0"):
            raise ValueError("Bootstrap deposit must be positive")
        self.balance = _quantize(self.balance + val)
        return self.balance

    def redirect_epoch_mining_reward(self, total_epoch_reward: Decimal | float | str) -> Decimal:
        """Redirects 10% of hardware epoch mining rewards into social_mining_pool."""
        total = _quantize(total_epoch_reward)
        if total <= Decimal("0"):
            raise ValueError("Epoch reward must be positive")
        inflow = _quantize(total * Decimal("0.10"))
        self.balance = _quantize(self.balance + inflow)
        return inflow

    def select_active_metric(self, epoch_nonce: str) -> str:
        """RIP-309 deterministic metric rotation based on epoch measurement nonce."""
        digest = hashlib.sha256(epoch_nonce.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % len(RIP309_METRICS)
        return RIP309_METRICS[idx]

    def process_tip(
        self,
        sender: str,
        recipient: str,
        amount: Decimal | float | str,
    ) -> TipResult:
        if sender == recipient:
            raise ValueError("Cannot tip yourself")
        if not self.has_beacon(sender) or not self.has_beacon(recipient):
            raise PermissionError("Both tipper and recipient must have verified Beacon IDs")

        gross = _quantize(amount)
        if gross < MIN_TIP_RTC:
            raise ValueError(f"Minimum tip is {MIN_TIP_RTC} RTC")

        sender_bal = self.user_balances.get(sender, Decimal("0"))
        if sender_bal < gross:
            raise ValueError("Insufficient RTC balance for tip")

        fee = _quantize(gross * TIP_FEE_RATE)
        net = _quantize(gross - fee)

        self.user_balances[sender] = _quantize(sender_bal - gross)
        self.user_balances[recipient] = _quantize(self.user_balances.get(recipient, Decimal("0")) + net)
        self.balance = _quantize(self.balance + fee)

        return TipResult(
            sender=sender,
            recipient=recipient,
            gross_amount=gross,
            fee_amount=fee,
            net_amount=net,
            pool_balance=self.balance,
        )

    def process_reaction_tip(self, sender: str, recipient: str, emoji: str) -> TipResult:
        if emoji not in REACTION_TIP_AMOUNTS:
            raise ValueError(f"Unsupported reaction tip emoji: {emoji}")
        return self.process_tip(sender, recipient, REACTION_TIP_AMOUNTS[emoji])

    def record_engagement(
        self,
        username: str,
        action: str,
        day_key: str,
        content_text: str = "",
        quality_multiplier: Decimal = Decimal("1.0"),
    ) -> Decimal:
        if not self.has_beacon(username):
            raise PermissionError("Beacon ID required for social mining rewards")
        if action not in ACTION_REWARDS:
            raise ValueError(f"Unknown social mining action: {action}")
        if action == "substantive_comment" and len(content_text.strip()) <= 50:
            return Decimal("0")

        user_day_key = f"{username}:{day_key}"
        counts = self.daily_action_counts.setdefault(user_day_key, {})
        current_count = counts.get(action, 0)
        cap = DAILY_CAPS[action]
        if cap is not None and current_count >= cap:
            return Decimal("0")

        reward = _quantize(ACTION_REWARDS[action] * quality_multiplier)
        if self.balance < reward:
            raise RuntimeError("Insufficient social_mining_pool treasury balance")

        counts[action] = current_count + 1
        self.balance = _quantize(self.balance - reward)
        self.user_balances[username] = _quantize(self.user_balances.get(username, Decimal("0")) + reward)
        return reward
