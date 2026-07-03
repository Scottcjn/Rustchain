"""RIP-310 Anti-Gaming Measures.

Frequency caps, content quality checks, and RIP-309 epoch-based metric
rotation integration to prevent social mining exploitation.
"""

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from social_mining import (
    ActionType,
    BeaconID,
    Platform,
    SocialAction,
    SocialMiningEngine,
)


@dataclass
class FrequencyTracker:
    """Tracks action frequency per beacon per type per day."""
    _counts: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    _windows: dict[str, float] = field(default_factory=dict)  # beacon_key -> window start

    def _window_key(self, beacon_hash: str, action_type: ActionType) -> str:
        return f"{beacon_hash}:{action_type.value}"

    def _get_window_start(self) -> float:
        t = time.time()
        return t - (t % 86400)

    def increment(self, beacon_hash: str, action_type: ActionType) -> int:
        key = self._window_key(beacon_hash, action_type)
        now = time.time()
        window_start = self._get_window_start()
        stored = self._windows.get(key)
        if stored is None or stored < window_start:
            self._counts[key] = defaultdict(int)
            self._windows[key] = now
        self._counts[key][str(int(now // 86400))] += 1
        return self._counts[key][str(int(now // 86400))]

    def get_count(self, beacon_hash: str, action_type: ActionType) -> int:
        key = self._window_key(beacon_hash, action_type)
        day = str(int(time.time() // 86400))
        return self._counts[key].get(day, 0)


FREQUENCY_LIMITS: dict[ActionType, int] = {
    ActionType.POST: 5,
    ActionType.THREAD: 5,
    ActionType.VIDEO: 3,
    ActionType.COMMENT: 20,
    ActionType.UPVOTE_RECEIVED: 999_999,  # effectively uncapped
    ActionType.TIP_RECEIVED: 999_999,
}

MIN_COMMENT_LENGTH = 50

# RIP-309 metric rotation: weights shift each epoch
METRIC_ROTATION_WEIGHTS = [
    {"engagement": 0.4, "quality": 0.3, "recency": 0.3},
    {"engagement": 0.3, "quality": 0.4, "recency": 0.3},
    {"engagement": 0.3, "quality": 0.3, "recency": 0.4},
]


@dataclass
class ContentFingerprint:
    """Fingerprint of content to detect duplicates."""
    content_hash: str
    timestamp: float = field(default_factory=time.time)


class AntiGamingModule:
    """Enforces anti-gaming rules for social mining."""

    def __init__(self, engine: SocialMiningEngine) -> None:
        self.engine = engine
        self.frequency_tracker = FrequencyTracker()
        self.content_fingerprints: dict[str, list[ContentFingerprint]] = defaultdict(list)
        self.flagged_beacons: set[str] = set()

    def check_frequency_cap(
        self, beacon_hash: str, action_type: ActionType
    ) -> tuple[bool, int]:
        """Returns (allowed, current_count)."""
        limit = FREQUENCY_LIMITS.get(action_type, 0)
        current = self.frequency_tracker.get_count(beacon_hash, action_type)
        return current < limit, current

    def check_content_quality(self, action: SocialAction) -> bool:
        """Substantive comments must be >50 characters."""
        if action.action_type == ActionType.COMMENT:
            return action.comment_length > MIN_COMMENT_LENGTH
        return True

    def check_duplicate_content(self, action: SocialAction) -> bool:
        """Detect duplicate content from the same beacon within 1 hour."""
        fps = self.content_fingerprints[action.beacon.beacon_hash]
        now = time.time()
        for fp in fps:
            if (
                fp.content_hash == action.content_hash
                and now - fp.timestamp < 3600
            ):
                return False
        fps.append(ContentFingerprint(content_hash=action.content_hash))
        return True

    def validate_action(self, action: SocialAction) -> tuple[bool, str]:
        """Full anti-gaming validation. Returns (allowed, reason)."""
        if not action.beacon.verify():
            return False, "Invalid or inactive Beacon ID"

        if action.beacon.beacon_hash in self.flagged_beacons:
            return False, "Beacon flagged for gaming"

        allowed, count = self.check_frequency_cap(
            action.beacon.beacon_hash, action.action_type
        )
        if not allowed:
            return False, f"Frequency cap reached for {action.action_type.value}"

        if not self.check_content_quality(action):
            return False, "Comment does not meet minimum quality threshold (>50 chars)"

        if not self.check_duplicate_content(action):
            return False, "Duplicate content detected within cooldown window"

        return True, "passed"

    def record_action(self, action: SocialAction) -> None:
        """Record the action for frequency tracking after validation passes."""
        self.frequency_tracker.increment(
            action.beacon.beacon_hash, action.action_type
        )

    def flag_beacon(self, beacon_hash: str) -> None:
        self.flagged_beacons.add(beacon_hash)

    def unflag_beacon(self, beacon_hash: str) -> None:
        self.flagged_beacons.discard(beacon_hash)

    def get_metric_weights(self, epoch_id: int) -> dict[str, float]:
        """RIP-309 epoch-based metric rotation."""
        idx = epoch_id % len(METRIC_ROTATION_WEIGHTS)
        return METRIC_ROTATION_WEIGHTS[idx]

    def calculate_rotation_score(
        self, epoch_id: int, engagement: float, quality: float, recency: float
    ) -> float:
        """Apply metric rotation weights to composite score."""
        weights = self.get_metric_weights(epoch_id)
        return (
            engagement * weights["engagement"]
            + quality * weights["quality"]
            + recency * weights["recency"]
        )
