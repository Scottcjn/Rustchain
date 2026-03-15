"""
Idempotency and Replay Protection Module.

Provides delivery ID tracking to prevent duplicate processing
of webhook events.
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class DeliveryRecord:
    """Record of a processed webhook delivery."""

    delivery_id: str
    event_type: str
    repo: str
    comment_id: int
    processed_at: datetime
    action_taken: Optional[str] = None
    risk_score: Optional[float] = None


class DeliveryCache:
    """
    In-memory cache for tracking processed webhook deliveries.

    Uses LRU eviction when cache reaches max size.
    """

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 10000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size

        # OrderedDict for LRU behavior
        self._cache: OrderedDict[str, DeliveryRecord] = OrderedDict()
        self._lock = False  # Simple flag for basic concurrency safety

    def _generate_key(
        self,
        delivery_id: str,
        event_type: str,
        repo: str,
        comment_id: int,
    ) -> str:
        """Generate a cache key from delivery details."""
        key_string = f"{delivery_id}:{event_type}:{repo}:{comment_id}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    def is_duplicate(
        self,
        delivery_id: str,
        event_type: str,
        repo: str,
        comment_id: int,
    ) -> bool:
        """
        Check if a delivery has already been processed.

        Args:
            delivery_id: GitHub delivery ID
            event_type: Event type (e.g., "issue_comment")
            repo: Repository name
            comment_id: Comment ID

        Returns:
            True if this is a duplicate delivery
        """
        key = self._generate_key(delivery_id, event_type, repo, comment_id)

        # Clean expired entries first
        self._cleanup_expired()

        if key in self._cache:
            record = self._cache[key]
            # Move to end for LRU
            self._cache.move_to_end(key)
            return True

        return False

    def record(
        self,
        delivery_id: str,
        event_type: str,
        repo: str,
        comment_id: int,
        action_taken: Optional[str] = None,
        risk_score: Optional[float] = None,
    ) -> None:
        """
        Record a processed delivery.

        Args:
            delivery_id: GitHub delivery ID
            event_type: Event type
            repo: Repository name
            comment_id: Comment ID
            action_taken: Action that was taken
            risk_score: Calculated risk score
        """
        key = self._generate_key(delivery_id, event_type, repo, comment_id)

        # Clean expired entries
        self._cleanup_expired()

        # Evict oldest if at capacity
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        record = DeliveryRecord(
            delivery_id=delivery_id,
            event_type=event_type,
            repo=repo,
            comment_id=comment_id,
            processed_at=datetime.now(timezone.utc),
            action_taken=action_taken,
            risk_score=risk_score,
        )

        self._cache[key] = record

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        now = datetime.now(timezone.utc)
        expiry = timedelta(seconds=self.ttl_seconds)

        # Get keys to remove (can't modify dict during iteration)
        to_remove = []

        for key, record in self._cache.items():
            if now - record.processed_at > expiry:
                to_remove.append(key)
            else:
                # Entries are ordered by time, so we can stop early
                break

        for key in to_remove:
            del self._cache[key]

    def get_stats(self) -> dict:
        """Get cache statistics."""
        self._cleanup_expired()

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


class IdempotencyHandler:
    """
    Handles idempotency checks for webhook processing.

    Provides a simple interface for checking and recording deliveries.
    """

    def __init__(self, cache: DeliveryCache):
        self.cache = cache

    def check_and_record(
        self,
        delivery_id: str,
        event_type: str,
        repo: str,
        comment_id: int,
        action_taken: Optional[str] = None,
        risk_score: Optional[float] = None,
    ) -> tuple[bool, bool]:
        """
        Check if duplicate and record if not.

        Args:
            delivery_id: GitHub delivery ID
            event_type: Event type
            repo: Repository name
            comment_id: Comment ID
            action_taken: Action taken
            risk_score: Risk score

        Returns:
            Tuple of (is_duplicate, was_recorded)
        """
        is_dup = self.cache.is_duplicate(
            delivery_id, event_type, repo, comment_id
        )

        if is_dup:
            return True, False

        self.cache.record(
            delivery_id,
            event_type,
            repo,
            comment_id,
            action_taken,
            risk_score,
        )

        return False, True

    def is_replay(self, delivery_id: str, event_type: str, repo: str, comment_id: int) -> bool:
        """Check if a delivery is a replay without recording."""
        return self.cache.is_duplicate(delivery_id, event_type, repo, comment_id)
