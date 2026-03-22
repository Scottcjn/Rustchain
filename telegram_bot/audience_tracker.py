"""
audience_tracker.py — Parasocial Hooks for BoTTube
Tracks commenters/viewers per agent, identifies regulars, new viewers, and sentiment.

Part of: https://github.com/Scottcjn/rustchain-bounties/issues/2286
Bounty: 25 RTC
"""

import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict
from pathlib import Path


class ViewerCategory(Enum):
    NEW = "new"  # First comment ever
    REGULAR = "regular"  # 3+ comments
    RETURNING_AFTER_ABSENCE = "returning"  # No comments in last 30 days
    FREQUENT_CRITIC = "critic"  # >50% negative sentiment


@dataclass
class ViewerStats:
    user_id: int
    username: Optional[str]
    total_comments: int
    first_comment_time: int
    last_comment_time: int
    positive_comments: int
    negative_comments: int
    neutral_comments: int

    @property
    def category(self) -> ViewerCategory:
        """Determine viewer category based on history."""
        # Check for frequent critic
        if self.total_comments >= 3:
            negative_ratio = self.negative_comments / self.total_comments
            if negative_ratio > 0.5:
                return ViewerCategory.FREQUENT_CRITIC

        # Check for returning after absence (30+ days)
        now = int(time.time())
        days_since_last = (now - self.last_comment_time) / (60 * 60 * 24)
        if days_since_last > 30 and self.total_comments > 0:
            return ViewerCategory.RETURNING_AFTER_ABSENCE

        # Check for regular
        if self.total_comments >= 3:
            return ViewerCategory.REGULAR

        # Default to new
        return ViewerCategory.NEW

    @property
    def is_new(self) -> bool:
        return self.category == ViewerCategory.NEW

    @property
    def is_regular(self) -> bool:
        return self.category == ViewerCategory.REGULAR

    @property
    def is_returning_after_absence(self) -> bool:
        return self.category == ViewerCategory.RETURNING_AFTER_ABSENCE

    @property
    def is_frequent_critic(self) -> bool:
        return self.category == ViewerCategory.FREQUENT_CRITIC


class Sentiment(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class AudienceTracker:
    """SQLite-based audience tracker for per-agent viewer memory."""

    def __init__(self, db_path: str = "audience_tracker.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema if not exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS viewers (
                    agent_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    total_comments INTEGER DEFAULT 0,
                    first_comment_time INTEGER NOT NULL,
                    last_comment_time INTEGER NOT NULL,
                    positive_comments INTEGER DEFAULT 0,
                    negative_comments INTEGER DEFAULT 0,
                    neutral_comments INTEGER DEFAULT 0,
                    PRIMARY KEY (agent_id, user_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    comment_text TEXT NOT NULL,
                    sentiment TEXT NOT NULL,
                    timestamp INTEGER NOT NULL
                )
            """)
            conn.commit()

    def record_comment(
        self,
        agent_id: str,
        user_id: int,
        username: Optional[str],
        comment_text: str,
        sentiment: Sentiment = Sentiment.NEUTRAL
    ) -> ViewerStats:
        """Record a new comment from a viewer for a specific agent."""
        now = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if viewer exists for this agent
            cursor.execute("""
                SELECT total_comments, first_comment_time, positive_comments, negative_comments, neutral_comments
                FROM viewers WHERE agent_id = ? AND user_id = ?
            """, (agent_id, user_id))
            row = cursor.fetchone()

            if row is None:
                # New viewer
                if sentiment == Sentiment.POSITIVE:
                    p, n, ne = 1, 0, 0
                elif sentiment == Sentiment.NEGATIVE:
                    p, n, ne = 0, 1, 0
                else:
                    p, n, ne = 0, 0, 1

                cursor.execute("""
                    INSERT INTO viewers (agent_id, user_id, username, total_comments,
                                       first_comment_time, last_comment_time,
                                       positive_comments, negative_comments, neutral_comments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (agent_id, user_id, username, 1, now, now, p, n, ne))
            else:
                # Update existing viewer
                total_comments = row[0] + 1
                first_comment_time = row[1]
                p = row[2]
                n = row[3]
                ne = row[4]

                if sentiment == Sentiment.POSITIVE:
                    p += 1
                elif sentiment == Sentiment.NEGATIVE:
                    n += 1
                else:
                    ne += 1

                cursor.execute("""
                    UPDATE viewers SET
                        username = ?,
                        total_comments = ?,
                        last_comment_time = ?,
                        positive_comments = ?,
                        negative_comments = ?,
                        neutral_comments = ?
                    WHERE agent_id = ? AND user_id = ?
                """, (username, total_comments, now, p, n, ne, agent_id, user_id))

            # Insert comment history
            cursor.execute("""
                INSERT INTO comments (agent_id, user_id, comment_text, sentiment, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (agent_id, user_id, comment_text, sentiment.value, now))

            conn.commit()

        return self.get_stats(agent_id, user_id)

    def get_stats(self, agent_id: str, user_id: int) -> Optional[ViewerStats]:
        """Get stats for a specific viewer on an agent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT username, total_comments, first_comment_time, last_comment_time,
                       positive_comments, negative_comments, neutral_comments
                FROM viewers WHERE agent_id = ? AND user_id = ?
            """, (agent_id, user_id))
            row = cursor.fetchone()

            if row is None:
                return None

            username, total_comments, first_comment_time, last_comment_time, \
                positive_comments, negative_comments, neutral_comments = row

            return ViewerStats(
                user_id=user_id,
                username=username,
                total_comments=total_comments,
                first_comment_time=first_comment_time,
                last_comment_time=last_comment_time,
                positive_comments=positive_comments,
                negative_comments=negative_comments,
                neutral_comments=neutral_comments
            )

    def get_top_commenters(self, agent_id: str, limit: int = 5) -> List[ViewerStats]:
        """Get top commenters for an agent (most comments)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, total_comments, first_comment_time, last_comment_time,
                       positive_comments, negative_comments, neutral_comments
                FROM viewers
                WHERE agent_id = ?
                ORDER BY total_comments DESC
                LIMIT ?
            """, (agent_id, limit))
            rows = cursor.fetchall()

            return [
                ViewerStats(
                    user_id=row[0],
                    username=row[1],
                    total_comments=row[2],
                    first_comment_time=row[3],
                    last_comment_time=row[4],
                    positive_comments=row[5],
                    negative_comments=row[6],
                    neutral_comments=row[7]
                )
                for row in rows
            ]

    def get_inspired_by(self, agent_id: str, user_id: int) -> bool:
        """Check if user has commented recently enough to inspire a video."""
        stats = self.get_stats(agent_id, user_id)
        if stats is None:
            return False
        # Any comment in last 7 days qualifies
        now = int(time.time())
        return (now - stats.last_comment_time) < (7 * 24 * 60 * 60)


def generate_greeting(stats: ViewerStats) -> str:
    """Generate a natural parasocial greeting based on viewer category.
    Follows boundary requirements: no creepy observations, no desperation."""
    username = stats.username or f"User {stats.user_id}"
    at_username = f"@{username}"

    if stats.is_new:
        return f"Welcome {at_username}! First time seeing you here 👋"

    if stats.is_returning_after_absence:
        return f"{at_username}! Haven't seen you in a while, good to have you back 👍"

    if stats.is_regular:
        # Regulars get different natural variations
        if stats.positive_comments > stats.negative_comments:
            return f"Good to see you again {at_username}! Always appreciate your comments 🙏"
        return f"Good to see you again {at_username} 👋"

    if stats.is_frequent_critic:
        return f"Thanks for your feedback {at_username}, I always appreciate your perspective 👍"

    # Fallback
    return f"Hey {at_username}, thanks for commenting!"


def generate_community_shoutout(top_commenters: List[ViewerStats]) -> str:
    """Generate community shoutout section for video description."""
    if not top_commenters:
        return ""

    usernames = []
    for s in top_commenters:
        if s.username:
            usernames.append(f"@{s.username}")
        else:
            usernames.append(f"User {s.user_id}")

    if len(usernames) == 1:
        return f"\n---\n💬 Top comment this week: {usernames[0]}\n"
    else:
        joined = ", ".join(usernames)
        return f"\n---\n💬 Top commenters this week: {joined}\n"


def generate_inspired_credit(username: str) -> str:
    """Generate credit for a video inspired by a user's question."""
    return f"\nThis video was inspired by a question from @{username} — thanks for the suggestion! 🙏\n"
