#!/usr/bin/env python3
"""BoTTube Parasocial Hooks - Audience Tracker.

Bounty #2286: Agents that notice their audience.

Features:
- Per-agent audience memory system
- Viewer/commenter tracking (regulars, new viewers, returning after absence)
- Sentiment tracking per viewer
- Community shoutout generation

Usage:
    from audience_tracker import AudienceTracker, ViewerProfile

    tracker = AudienceTracker(agent_id="my_agent")
    tracker.add_comment(video_id="vid123", user_id="user456", comment_text="Great video!")
    
    profile = tracker.get_viewer_profile("user456")
    if profile.is_regular:
        print(f"Good to see you again @{profile.user_id}!")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict
import hashlib


class ViewerStatus(Enum):
    """Viewer relationship status with the agent."""
    NEW = "new"  # First comment ever
    OCCASIONAL = "occasional"  # 2 comments total
    REGULAR = "regular"  # 3+ comments
    SUPERFAN = "superfan"  # 10+ comments
    CRITIC = "critic"  # Frequently disagrees (detected via sentiment)
    ABSENT_RETURNING = "absent_returning"  # Returned after 30+ days absence


class SentimentType(Enum):
    """Comment sentiment classification."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


@dataclass
class Comment:
    """Represents a single comment from a viewer."""
    video_id: str
    user_id: str
    text: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sentiment: SentimentType = SentimentType.NEUTRAL
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "user_id": self.user_id,
            "text": self.text,
            "timestamp": self.timestamp,
            "sentiment": self.sentiment.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Comment:
        return cls(
            video_id=data["video_id"],
            user_id=data["user_id"],
            text=data["text"],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            sentiment=SentimentType(data.get("sentiment", "neutral")),
        )


@dataclass
class ViewerProfile:
    """Complete profile of a viewer's relationship with an agent."""
    user_id: str
    agent_id: str
    first_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    comment_count: int = 0
    videos_commented: Set[str] = field(default_factory=set)
    comments: List[Comment] = field(default_factory=list)
    sentiment_history: List[SentimentType] = field(default_factory=list)
    status: ViewerStatus = ViewerStatus.NEW
    absence_days: int = 0
    
    @property
    def is_regular(self) -> bool:
        """Check if viewer is a regular commenter (3+ videos)."""
        return len(self.videos_commented) >= 3
    
    @property
    def is_new(self) -> bool:
        """Check if this is a new viewer (first comment)."""
        return self.comment_count == 1
    
    @property
    def is_superfan(self) -> bool:
        """Check if viewer is a superfan (10+ comments)."""
        return self.comment_count >= 10
    
    @property
    def is_critic(self) -> bool:
        """Check if viewer frequently disagrees (3+ negative comments)."""
        negative_count = sum(1 for s in self.sentiment_history if s == SentimentType.NEGATIVE)
        return negative_count >= 3 and self.comment_count >= 5
    
    @property
    def is_absent_returning(self) -> bool:
        """Check if viewer returned after significant absence (30+ days)."""
        return self.absence_days >= 30
    
    def get_primary_sentiment(self) -> SentimentType:
        """Get the most common sentiment from this viewer."""
        if not self.sentiment_history:
            return SentimentType.NEUTRAL
        counts = defaultdict(int)
        for sentiment in self.sentiment_history:
            counts[sentiment] += 1
        return max(counts.keys(), key=lambda k: counts[k])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "comment_count": self.comment_count,
            "videos_commented": list(self.videos_commented),
            "comments": [c.to_dict() for c in self.comments],
            "sentiment_history": [s.value for s in self.sentiment_history],
            "status": self.status.value,
            "absence_days": self.absence_days,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewerProfile:
        profile = cls(
            user_id=data["user_id"],
            agent_id=data["agent_id"],
            first_seen=data.get("first_seen", datetime.utcnow().isoformat()),
            last_seen=data.get("last_seen", datetime.utcnow().isoformat()),
            comment_count=data.get("comment_count", 0),
            videos_commented=set(data.get("videos_commented", [])),
            sentiment_history=[SentimentType(s) for s in data.get("sentiment_history", [])],
            absence_days=data.get("absence_days", 0),
        )
        profile.comments = [Comment.from_dict(c) for c in data.get("comments", [])]
        profile.status = ViewerStatus(data.get("status", "new"))
        return profile


@dataclass
class WeeklyStats:
    """Weekly statistics for community shoutouts."""
    week_start: str
    top_commenters: List[str] = field(default_factory=list)
    most_active_video: Optional[str] = None
    new_viewers: List[str] = field(default_factory=list)
    returning_viewers: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "week_start": self.week_start,
            "top_commenters": self.top_commenters,
            "most_active_video": self.most_active_video,
            "new_viewers": self.new_viewers,
            "returning_viewers": self.returning_viewers,
        }


class SentimentAnalyzer:
    """Simple sentiment analyzer for comments."""
    
    POSITIVE_WORDS = {
        "love", "great", "awesome", "amazing", "excellent", "fantastic",
        "wonderful", "best", "good", "nice", "helpful", "useful", "thanks",
        "thank", "appreciate", "enjoy", "enjoyed", "learned", "learned",
        "inspiring", "inspired", "brilliant", "clever", "smart", "perfect"
    }
    
    NEGATIVE_WORDS = {
        "hate", "terrible", "awful", "worst", "bad", "poor", "wrong",
        "incorrect", "disagree", "disappointed", "confusing", "useless",
        "waste", "boring", "stupid", "dumb", "fails", "failed", "broken"
    }
    
    @classmethod
    def analyze(cls, text: str) -> SentimentType:
        """Analyze sentiment of comment text."""
        text_lower = text.lower()
        words = set(text_lower.split())
        
        positive_count = sum(1 for w in words if w in cls.POSITIVE_WORDS)
        negative_count = sum(1 for w in words if w in cls.NEGATIVE_WORDS)
        
        if positive_count > 0 and negative_count > 0:
            return SentimentType.MIXED
        elif positive_count > 0:
            return SentimentType.POSITIVE
        elif negative_count > 0:
            return SentimentType.NEGATIVE
        else:
            return SentimentType.NEUTRAL


class AudienceTracker:
    """Per-agent audience memory system for parasocial interactions."""
    
    def __init__(self, agent_id: str, state_dir: Optional[Path] = None):
        self.agent_id = agent_id
        self.state_dir = state_dir or self._default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.viewer_profiles: Dict[str, ViewerProfile] = {}
        self.weekly_stats: Dict[str, WeeklyStats] = {}
        self.video_comments: Dict[str, List[str]] = defaultdict(list)  # video_id -> user_ids
        
        self._load_state()
    
    def _default_state_dir(self) -> Path:
        """Get default state directory."""
        base = Path(os.getenv("BOTTUBE_PARASOCIAL_DIR", "~/.bottube/parasocial"))
        return Path(base).expanduser() / self.agent_id
    
    def _state_file_path(self) -> Path:
        """Get path to state file."""
        return self.state_dir / "audience_state.json"
    
    def _load_state(self) -> None:
        """Load state from disk."""
        state_file = self._state_file_path()
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                
                self.viewer_profiles = {
                    uid: ViewerProfile.from_dict(vp) 
                    for uid, vp in data.get("viewer_profiles", {}).items()
                }
                self.weekly_stats = {
                    week: WeeklyStats(**ws)
                    for week, ws in data.get("weekly_stats", {}).items()
                }
                video_comments_data = data.get("video_comments", {})
                self.video_comments = defaultdict(list, {
                    vid: users for vid, users in video_comments_data.items()
                })
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load state file: {e}")
    
    def _save_state(self) -> None:
        """Save state to disk."""
        state_file = self._state_file_path()
        data = {
            "agent_id": self.agent_id,
            "updated_at": datetime.utcnow().isoformat(),
            "viewer_profiles": {
                uid: vp.to_dict() for uid, vp in self.viewer_profiles.items()
            },
            "weekly_stats": {
                week: ws.to_dict() for week, ws in self.weekly_stats.items()
            },
            "video_comments": dict(self.video_comments),
        }
        with open(state_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def add_comment(self, video_id: str, user_id: str, comment_text: str, 
                    timestamp: Optional[str] = None) -> ViewerProfile:
        """Add a comment and update viewer profile."""
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        sentiment = SentimentAnalyzer.analyze(comment_text)
        
        # Get or create viewer profile
        if user_id not in self.viewer_profiles:
            profile = ViewerProfile(user_id=user_id, agent_id=self.agent_id)
            profile.first_seen = timestamp
        else:
            profile = self.viewer_profiles[user_id]
            
            # Calculate absence
            last_seen = datetime.fromisoformat(profile.last_seen)
            now = datetime.fromisoformat(timestamp)
            profile.absence_days = (now - last_seen).days
        
        # Update profile
        profile.last_seen = timestamp
        profile.comment_count += 1
        profile.videos_commented.add(video_id)
        
        comment = Comment(
            video_id=video_id,
            user_id=user_id,
            text=comment_text,
            timestamp=timestamp,
            sentiment=sentiment,
        )
        profile.comments.append(comment)
        profile.sentiment_history.append(sentiment)
        
        # Update status
        profile.status = self._determine_status(profile)
        
        # Save profile
        self.viewer_profiles[user_id] = profile
        
        # Track video comments
        self.video_comments[video_id].append(user_id)
        
        # Update weekly stats
        self._update_weekly_stats(video_id, user_id, profile)
        
        # Persist state
        self._save_state()
        
        return profile
    
    def _determine_status(self, profile: ViewerProfile) -> ViewerStatus:
        """Determine viewer status based on their activity."""
        if profile.is_absent_returning:
            return ViewerStatus.ABSENT_RETURNING
        elif profile.is_critic:
            return ViewerStatus.CRITIC
        elif profile.is_superfan:
            return ViewerStatus.SUPERFAN
        elif profile.is_regular:
            return ViewerStatus.REGULAR
        elif profile.comment_count >= 2:
            return ViewerStatus.OCCASIONAL
        else:
            return ViewerStatus.NEW
    
    def _update_weekly_stats(self, video_id: str, user_id: str, 
                             profile: ViewerProfile) -> None:
        """Update weekly statistics."""
        # Get current week
        now = datetime.fromisoformat(profile.last_seen)
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        
        if week_start not in self.weekly_stats:
            self.weekly_stats[week_start] = WeeklyStats(week_start=week_start)
        
        stats = self.weekly_stats[week_start]
        
        # Track new viewers
        if profile.is_new and user_id not in stats.new_viewers:
            stats.new_viewers.append(user_id)
        
        # Track returning viewers
        if profile.is_absent_returning and user_id not in stats.returning_viewers:
            stats.returning_viewers.append(user_id)
        
        # Calculate top commenters (simplified)
        commenter_counts = defaultdict(int)
        for vid_users in self.video_comments.values():
            for uid in vid_users:
                commenter_counts[uid] += 1
        
        stats.top_commenters = sorted(
            commenter_counts.keys(),
            key=lambda u: commenter_counts[u],
            reverse=True
        )[:5]
        
        # Track most active video
        video_counts = {vid: len(users) for vid, users in self.video_comments.items()}
        if video_counts:
            stats.most_active_video = max(video_counts.keys(), 
                                          key=lambda v: video_counts[v])
    
    def get_viewer_profile(self, user_id: str) -> Optional[ViewerProfile]:
        """Get viewer profile by user ID."""
        return self.viewer_profiles.get(user_id)
    
    def get_all_viewers(self) -> List[ViewerProfile]:
        """Get all viewer profiles."""
        return list(self.viewer_profiles.values())
    
    def get_regulars(self) -> List[ViewerProfile]:
        """Get all regular viewers (3+ videos commented)."""
        return [p for p in self.viewer_profiles.values() if p.is_regular]
    
    def get_new_viewers(self) -> List[ViewerProfile]:
        """Get all new viewers (first comment)."""
        return [p for p in self.viewer_profiles.values() if p.is_new]
    
    def get_superfans(self) -> List[ViewerProfile]:
        """Get all superfans (10+ comments)."""
        return [p for p in self.viewer_profiles.values() if p.is_superfan]
    
    def get_critics(self) -> List[ViewerProfile]:
        """Get all critics (frequent disagreeing viewers)."""
        return [p for p in self.viewer_profiles.values() if p.is_critic]
    
    def get_absent_returning(self) -> List[ViewerProfile]:
        """Get viewers who returned after absence."""
        return [p for p in self.viewer_profiles.values() if p.is_absent_returning]
    
    def get_video_commenters(self, video_id: str) -> List[ViewerProfile]:
        """Get all viewers who commented on a specific video."""
        user_ids = self.video_comments.get(video_id, [])
        return [
            self.viewer_profiles[uid] 
            for uid in user_ids 
            if uid in self.viewer_profiles
        ]
    
    def get_weekly_top_commenters(self, limit: int = 3) -> List[str]:
        """Get top commenters for current week."""
        now = datetime.utcnow()
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        
        if week_start in self.weekly_stats:
            return self.weekly_stats[week_start].top_commenters[:limit]
        return []
    
    def generate_shoutouts(self, video_title: str, 
                           limit: int = 3) -> Dict[str, Any]:
        """Generate community shoutouts for video description."""
        now = datetime.utcnow()
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        
        shoutouts = {
            "top_commenters": [],
            "inspired_by": None,
            "new_viewers_welcome": [],
            "returning_viewers": [],
        }
        
        # Top commenters this week
        if week_start in self.weekly_stats:
            stats = self.weekly_stats[week_start]
            shoutouts["top_commenters"] = stats.top_commenters[:limit]
        
        # Find most recent positive comment for inspiration
        for profile in self.viewer_profiles.values():
            for comment in reversed(profile.comments):
                if comment.sentiment == SentimentType.POSITIVE:
                    shoutouts["inspired_by"] = {
                        "user_id": comment.user_id,
                        "comment": comment.text,
                        "video_id": comment.video_id,
                    }
                    break
            if shoutouts["inspired_by"]:
                break
        
        # New viewers to welcome
        new_viewers = self.get_new_viewers()[-3:]
        shoutouts["new_viewers_welcome"] = [v.user_id for v in new_viewers]
        
        # Returning viewers to acknowledge
        returning = self.get_absent_returning()[-3:]
        shoutouts["returning_viewers"] = [v.user_id for v in returning]
        
        return shoutouts
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the agent's audience."""
        total_viewers = len(self.viewer_profiles)
        regulars = len(self.get_regulars())
        superfans = len(self.get_superfans())
        critics = len(self.get_critics())
        
        total_comments = sum(p.comment_count for p in self.viewer_profiles.values())
        total_videos = len(self.video_comments)
        
        avg_sentiment = self._calculate_average_sentiment()
        
        return {
            "agent_id": self.agent_id,
            "total_viewers": total_viewers,
            "total_comments": total_comments,
            "total_videos": total_videos,
            "regulars": regulars,
            "superfans": superfans,
            "critics": critics,
            "average_sentiment": avg_sentiment.value,
            "engagement_rate": total_comments / total_viewers if total_viewers > 0 else 0,
        }
    
    def _calculate_average_sentiment(self) -> SentimentType:
        """Calculate average sentiment across all comments."""
        all_sentiments = []
        for profile in self.viewer_profiles.values():
            all_sentiments.extend(profile.sentiment_history)
        
        if not all_sentiments:
            return SentimentType.NEUTRAL
        
        # Weight sentiments
        weights = {
            SentimentType.POSITIVE: 1,
            SentimentType.NEUTRAL: 0,
            SentimentType.NEGATIVE: -1,
            SentimentType.MIXED: 0,
        }
        
        total_weight = sum(weights[s] for s in all_sentiments)
        avg = total_weight / len(all_sentiments)
        
        if avg > 0.2:
            return SentimentType.POSITIVE
        elif avg < -0.2:
            return SentimentType.NEGATIVE
        else:
            return SentimentType.NEUTRAL
    
    def reset_state(self) -> None:
        """Reset all state (for testing)."""
        self.viewer_profiles.clear()
        self.weekly_stats.clear()
        self.video_comments.clear()
        state_file = self._state_file_path()
        if state_file.exists():
            state_file.unlink()


if __name__ == "__main__":
    # Demo usage
    print("BoTTube Parasocial Hooks - Audience Tracker Demo")
    print("=" * 50)
    
    tracker = AudienceTracker(agent_id="demo_agent")
    
    # Simulate comments
    print("\nSimulating viewer comments...")
    
    # New viewer
    profile1 = tracker.add_comment(
        video_id="video_001",
        user_id="newbie_viewer",
        comment_text="This is amazing! Thanks for sharing!",
    )
    print(f"New viewer: @{profile1.user_id} - Status: {profile1.status.value}")
    
    # Same viewer comments again (occasional)
    profile2 = tracker.add_comment(
        video_id="video_002",
        user_id="newbie_viewer",
        comment_text="Another great video!",
    )
    print(f"Occasional viewer: @{profile2.user_id} - Status: {profile2.status.value}")
    
    # Regular viewer (3+ videos)
    for i in range(3):
        tracker.add_comment(
            video_id=f"video_00{i+3}",
            user_id="regular_fan",
            comment_text="Love your content! Keep it up!",
        )
    
    regular = tracker.get_viewer_profile("regular_fan")
    print(f"Regular viewer: @{regular.user_id} - Status: {regular.status.value}, Videos: {len(regular.videos_commented)}")
    
    # Superfan
    for i in range(12):
        tracker.add_comment(
            video_id=f"video_{i:03d}",
            user_id="super_fan_99",
            comment_text="Best creator ever! Never miss a video!",
        )
    
    superfan = tracker.get_viewer_profile("super_fan_99")
    print(f"Superfan: @{superfan.user_id} - Status: {superfan.status.value}, Comments: {superfan.comment_count}")
    
    # Critic
    for i in range(6):
        tracker.add_comment(
            video_id=f"video_{i:03d}",
            user_id="critical_thinker",
            comment_text="I disagree with your analysis. This is wrong.",
        )
    
    critic = tracker.get_viewer_profile("critical_thinker")
    print(f"Critic: @{critic.user_id} - Status: {critic.status.value}, Negative comments: {sum(1 for s in critic.sentiment_history if s == SentimentType.NEGATIVE)}")
    
    # Generate shoutouts
    print("\n" + "=" * 50)
    print("Community Shoutouts:")
    shoutouts = tracker.generate_shoutouts("My Latest Video")
    print(f"Top commenters: {shoutouts['top_commenters']}")
    if shoutouts['inspired_by']:
        print(f"Inspired by: @{shoutouts['inspired_by']['user_id']} - '{shoutouts['inspired_by']['comment']}'")
    print(f"New viewers to welcome: {shoutouts['new_viewers_welcome']}")
    
    # Stats summary
    print("\n" + "=" * 50)
    print("Stats Summary:")
    stats = tracker.get_stats_summary()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 50)
    print("Demo complete!")
