#!/usr/bin/env python3
"""Audience Tracker for BoTTube Agents.

Tracks viewer/commenter history, identifies regulars, new viewers,
and returning absent viewers. Maintains per-agent audience memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib


class ViewerStatus(Enum):
    """Viewer relationship status with the agent."""
    NEW = "new"  # First comment ever
    REGULAR = "regular"  # 3+ videos commented
    RETURNING = "returning"  # Back after absence
    OCCASIONAL = "occasional"  # 1-2 videos commented
    CRITIC = "critic"  # Frequently negative sentiment
    SUPERFAN = "superfan"  # 5+ videos, positive sentiment


@dataclass
class CommentRecord:
    """Record of a single comment."""
    comment_id: str
    video_id: str
    content: str
    timestamp: datetime
    sentiment: float  # -1.0 to 1.0 (negative to positive)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "video_id": self.video_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "sentiment": self.sentiment,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommentRecord":
        return cls(
            comment_id=data["comment_id"],
            video_id=data["video_id"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sentiment=data["sentiment"],
        )


@dataclass
class ViewerProfile:
    """Complete profile of a viewer for an agent."""
    viewer_id: str
    viewer_name: str
    first_seen: datetime
    last_seen: datetime
    videos_commented: set[str]
    comments: List[CommentRecord]
    avg_sentiment: float = 0.0
    _forced_status: Optional[ViewerStatus] = field(default=None, repr=False)
    
    @property
    def status(self) -> ViewerStatus:
        """Determine viewer status based on behavior."""
        # Allow forced status for testing
        if self._forced_status is not None:
            return self._forced_status
        
        video_count = len(self.videos_commented)
        
        # Check for returning after absence (30+ days)
        days_since_last = (datetime.now() - self.last_seen).days
        if days_since_last > 30 and video_count >= 3:
            return ViewerStatus.RETURNING
        
        # Check for superfan
        if video_count >= 5 and self.avg_sentiment > 0.3:
            return ViewerStatus.SUPERFAN
        
        # Check for critic
        if video_count >= 3 and self.avg_sentiment < -0.3:
            return ViewerStatus.CRITIC
        
        # Check for regular
        if video_count >= 3:
            return ViewerStatus.REGULAR
        
        # Check for new viewer
        if video_count == 1 and (datetime.now() - self.first_seen).days < 7:
            return ViewerStatus.NEW
        
        return ViewerStatus.OCCASIONAL
    
    @status.setter
    def status(self, value: ViewerStatus) -> None:
        """Allow setting status for testing purposes."""
        self._forced_status = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "viewer_id": self.viewer_id,
            "viewer_name": self.viewer_name,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "videos_commented": list(self.videos_commented),
            "comments": [c.to_dict() for c in self.comments],
            "avg_sentiment": self.avg_sentiment,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ViewerProfile":
        return cls(
            viewer_id=data["viewer_id"],
            viewer_name=data["viewer_name"],
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            videos_commented=set(data["videos_commented"]),
            comments=[CommentRecord.from_dict(c) for c in data["comments"]],
            avg_sentiment=data["avg_sentiment"],
        )


class AudienceTracker:
    """Tracks and manages audience data for a BoTTube agent."""
    
    REGULAR_THRESHOLD = 3  # Videos needed to be regular
    ABSENCE_THRESHOLD_DAYS = 30  # Days to consider returning
    SENTIMENT_POSITIVE = 0.3
    SENTIMENT_NEGATIVE = -0.3
    
    def __init__(self, agent_id: str, storage_path: Optional[Path] = None):
        self.agent_id = agent_id
        self.storage_path = storage_path or Path(f".audience_{agent_id}.json")
        self.viewers: Dict[str, ViewerProfile] = {}
        self.video_commenters: Dict[str, set[str]] = {}  # video_id -> set of viewer_ids
        self._load()
    
    def _load(self) -> None:
        """Load audience data from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.viewers = {
                    vid: ViewerProfile.from_dict(vdata)
                    for vid, vdata in data.get("viewers", {}).items()
                }
                self.video_commenters = {
                    vid: set(viewers)
                    for vid, viewers in data.get("video_commenters", {}).items()
                }
            except (json.JSONDecodeError, KeyError):
                # Start fresh if data is corrupted
                self.viewers = {}
                self.video_commenters = {}
    
    def _save(self) -> None:
        """Save audience data to storage."""
        data = {
            "agent_id": self.agent_id,
            "viewers": {vid: v.to_dict() for vid, v in self.viewers.items()},
            "video_commenters": {vid: list(v) for vid, v in self.video_commenters.items()},
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment of a text. Simple heuristic-based approach.
        
        For production, this should use a proper sentiment analysis model.
        """
        text_lower = text.lower()
        
        positive_words = [
            "love", "great", "amazing", "awesome", "fantastic", "excellent",
            "wonderful", "brilliant", "best", "perfect", "thanks", "thank",
            "appreciate", "helpful", "insightful", "beautiful", "cool"
        ]
        negative_words = [
            "hate", "bad", "terrible", "awful", "horrible", "worst",
            "boring", "disappointing", "waste", "wrong", "stupid", "dumb",
            "annoying", "confusing", "broken", "failed"
        ]
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        total = pos_count + neg_count
        
        if total == 0:
            return 0.0
        
        return (pos_count - neg_count) / total
    
    def record_comment(
        self,
        viewer_id: str,
        viewer_name: str,
        video_id: str,
        comment_id: str,
        content: str,
        timestamp: Optional[datetime] = None,
        sentiment: Optional[float] = None,
    ) -> ViewerStatus:
        """Record a new comment and return the viewer's status.
        
        Args:
            viewer_id: Unique identifier for the viewer
            viewer_name: Display name of the viewer
            video_id: ID of the video being commented on
            comment_id: Unique identifier for the comment
            content: The comment text
            timestamp: When the comment was made (defaults to now)
            sentiment: Pre-calculated sentiment (-1 to 1, or None to auto-calculate)
        
        Returns:
            The viewer's current status after this comment
        """
        timestamp = timestamp or datetime.now()
        if sentiment is None:
            sentiment = self._calculate_sentiment(content)
        
        comment = CommentRecord(
            comment_id=comment_id,
            video_id=video_id,
            content=content,
            timestamp=timestamp,
            sentiment=sentiment,
        )
        
        if viewer_id not in self.viewers:
            # New viewer
            profile = ViewerProfile(
                viewer_id=viewer_id,
                viewer_name=viewer_name,
                first_seen=timestamp,
                last_seen=timestamp,
                videos_commented={video_id},
                comments=[comment],
                avg_sentiment=sentiment,
            )
            self.viewers[viewer_id] = profile
        else:
            # Existing viewer
            profile = self.viewers[viewer_id]
            profile.last_seen = timestamp
            profile.videos_commented.add(video_id)
            profile.comments.append(comment)
            # Update average sentiment
            profile.avg_sentiment = sum(c.sentiment for c in profile.comments) / len(profile.comments)
        
        # Track video commenters
        if video_id not in self.video_commenters:
            self.video_commenters[video_id] = set()
        self.video_commenters[video_id].add(viewer_id)
        
        self._save()
        return profile.status
    
    def get_viewer(self, viewer_id: str) -> Optional[ViewerProfile]:
        """Get a viewer's profile."""
        return self.viewers.get(viewer_id)
    
    def get_viewer_status(self, viewer_id: str) -> Optional[ViewerStatus]:
        """Get a viewer's current status."""
        profile = self.viewers.get(viewer_id)
        return profile.status if profile else None
    
    def get_regulars(self) -> List[ViewerProfile]:
        """Get all regular viewers (3+ videos)."""
        return [
            v for v in self.viewers.values()
            if v.status in (ViewerStatus.REGULAR, ViewerStatus.SUPERFAN)
        ]
    
    def get_top_commenters(self, days: int = 7, limit: int = 5) -> List[ViewerProfile]:
        """Get top commenters in the last N days.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of commenters to return
        
        Returns:
            List of viewer profiles sorted by comment count
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        comment_counts: Dict[str, int] = {}
        for viewer in self.viewers.values():
            recent_comments = [
                c for c in viewer.comments
                if c.timestamp >= cutoff
            ]
            if recent_comments:
                comment_counts[viewer.viewer_id] = len(recent_comments)
        
        sorted_ids = sorted(
            comment_counts.keys(),
            key=lambda x: comment_counts[x],
            reverse=True
        )[:limit]
        
        return [self.viewers[vid] for vid in sorted_ids]
    
    def get_video_commenters(self, video_id: str) -> List[ViewerProfile]:
        """Get all commenters for a specific video."""
        viewer_ids = self.video_commenters.get(video_id, set())
        return [self.viewers[vid] for vid in viewer_ids if vid in self.viewers]
    
    def get_new_commenters_since(self, since: datetime) -> List[ViewerProfile]:
        """Get viewers who made their first comment since a given date."""
        return [
            v for v in self.viewers.values()
            if v.first_seen >= since and v.status == ViewerStatus.NEW
        ]
    
    def get_returning_viewers(self) -> List[ViewerProfile]:
        """Get viewers who have returned after absence."""
        return [
            v for v in self.viewers.values()
            if v.status == ViewerStatus.RETURNING
        ]
    
    def get_sentiment_summary(self) -> Dict[str, float]:
        """Get overall sentiment summary for the audience."""
        if not self.viewers:
            return {"avg_sentiment": 0.0, "positive_ratio": 0.0, "negative_ratio": 0.0}
        
        sentiments = [v.avg_sentiment for v in self.viewers.values()]
        avg = sum(sentiments) / len(sentiments)
        
        positive = sum(1 for s in sentiments if s > self.SENTIMENT_POSITIVE)
        negative = sum(1 for s in sentiments if s < self.SENTIMENT_NEGATIVE)
        total = len(sentiments)
        
        return {
            "avg_sentiment": round(avg, 3),
            "positive_ratio": round(positive / total, 3) if total else 0.0,
            "negative_ratio": round(negative / total, 3) if total else 0.0,
        }
    
    def get_audience_stats(self) -> Dict[str, Any]:
        """Get comprehensive audience statistics."""
        status_counts = {}
        for status in ViewerStatus:
            status_counts[status.value] = sum(
                1 for v in self.viewers.values() if v.status == status
            )
        
        return {
            "total_viewers": len(self.viewers),
            "total_videos_with_comments": len(self.video_commenters),
            "status_breakdown": status_counts,
            "sentiment": self.get_sentiment_summary(),
        }