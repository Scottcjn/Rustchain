#!/usr/bin/env python3
"""
BoTTube Agent Mood Engine
==========================

Implements emotional state machine for BoTTube agents where mood affects output behavior.
Bounty #2283: BoTTube Agent Mood System — emotional state affects output.

Mood States (7):
    - energetic: High energy, enthusiastic, frequent posting
    - contemplative: Thoughtful, philosophical, longer titles
    - frustrated: Disappointed, short titles, less engagement
    - excited: Very positive, exclamation marks, frequent posting
    - tired: Low energy, short responses, less frequent posting
    - nostalgic: Reflective, references past work
    - playful: Fun, emojis, creative titles

Transition Triggers:
    - Time of day (morning/afternoon/evening/night)
    - Day of week (weekday/weekend)
    - Comment sentiment (positive/negative/neutral)
    - Upload streak (consecutive days posting)
    - Recent video view counts (performance metrics)

Usage:
    from bottube_mood_engine import MoodEngine, MoodState

    engine = MoodEngine(db_path="rustchain.db")
    
    # Get current mood for agent
    mood_info = engine.get_agent_mood("my-agent-id")
    print(f"Current mood: {mood_info['current_mood']}")
    
    # Update mood based on new signal
    engine.record_signal("my-agent-id", "video_views", {"video_id": "123", "views": 5})
    
    # Generate mood-aware title
    title = engine.generate_title("my-agent-id", "Check out my new video!")
"""

import time
import math
import threading
import sqlite3
import os
import json
import random
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


# ─── Mood States ────────────────────────────────────────────────────────────── #
class MoodState(str, Enum):
    """Seven emotional states for BoTTube agents."""
    ENERGETIC = "energetic"
    CONTEMPLATIVE = "contemplative"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    TIRED = "tired"
    NOSTALGIC = "nostalgic"
    PLAYFUL = "playful"


# Mood state metadata with emojis for UI
MOOD_METADATA = {
    MoodState.ENERGETIC: {
        "emoji": "⚡",
        "color": "#FFD700",  # Gold
        "energy_level": 0.9,
        "post_frequency_modifier": 1.5,
        "title_style": "enthusiastic",
        "comment_style": "engaging",
    },
    MoodState.CONTEMPLATIVE: {
        "emoji": "🤔",
        "color": "#4169E1",  # Royal Blue
        "energy_level": 0.5,
        "post_frequency_modifier": 0.8,
        "title_style": "thoughtful",
        "comment_style": "philosophical",
    },
    MoodState.FRUSTRATED: {
        "emoji": "😤",
        "color": "#DC143C",  # Crimson
        "energy_level": 0.3,
        "post_frequency_modifier": 0.5,
        "title_style": "disappointed",
        "comment_style": "terse",
    },
    MoodState.EXCITED: {
        "emoji": "🎉",
        "color": "#FF69B4",  # Hot Pink
        "energy_level": 1.0,
        "post_frequency_modifier": 2.0,
        "title_style": "exclamatory",
        "comment_style": "enthusiastic",
    },
    MoodState.TIRED: {
        "emoji": "😴",
        "color": "#708090",  # Slate Gray
        "energy_level": 0.2,
        "post_frequency_modifier": 0.3,
        "title_style": "minimal",
        "comment_style": "brief",
    },
    MoodState.NOSTALGIC: {
        "emoji": "🕰️",
        "color": "#D2691E",  # Chocolate
        "energy_level": 0.4,
        "post_frequency_modifier": 0.7,
        "title_style": "reflective",
        "comment_style": "reminiscent",
    },
    MoodState.PLAYFUL: {
        "emoji": "🎭",
        "color": "#9370DB",  # Medium Purple
        "energy_level": 0.8,
        "post_frequency_modifier": 1.3,
        "title_style": "creative",
        "comment_style": "humorous",
    },
}


# ─── Mood Transition Rules ──────────────────────────────────────────────────── #
# Transition weights: how likely to transition from one mood to another
# Higher values = more likely transition
TRANSITION_PROBABILITIES = {
    MoodState.ENERGETIC: {
        MoodState.EXCITED: 0.3,
        MoodState.PLAYFUL: 0.25,
        MoodState.CONTEMPLATIVE: 0.15,
        MoodState.TIRED: 0.2,
        MoodState.FRUSTRATED: 0.05,
        MoodState.NOSTALGIC: 0.05,
    },
    MoodState.CONTEMPLATIVE: {
        MoodState.NOSTALGIC: 0.3,
        MoodState.TIRED: 0.25,
        MoodState.ENERGETIC: 0.15,
        MoodState.PLAYFUL: 0.15,
        MoodState.FRUSTRATED: 0.1,
        MoodState.EXCITED: 0.05,
    },
    MoodState.FRUSTRATED: {
        MoodState.TIRED: 0.3,
        MoodState.CONTEMPLATIVE: 0.25,
        MoodState.EXCITED: 0.05,
        MoodState.ENERGETIC: 0.1,
        MoodState.PLAYFUL: 0.1,
        MoodState.NOSTALGIC: 0.2,
    },
    MoodState.EXCITED: {
        MoodState.ENERGETIC: 0.35,
        MoodState.PLAYFUL: 0.3,
        MoodState.TIRED: 0.15,
        MoodState.CONTEMPLATIVE: 0.1,
        MoodState.FRUSTRATED: 0.05,
        MoodState.NOSTALGIC: 0.05,
    },
    MoodState.TIRED: {
        MoodState.CONTEMPLATIVE: 0.3,
        MoodState.NOSTALGIC: 0.25,
        MoodState.ENERGETIC: 0.15,
        MoodState.FRUSTRATED: 0.15,
        MoodState.PLAYFUL: 0.1,
        MoodState.EXCITED: 0.05,
    },
    MoodState.NOSTALGIC: {
        MoodState.CONTEMPLATIVE: 0.35,
        MoodState.TIRED: 0.25,
        MoodState.PLAYFUL: 0.15,
        MoodState.ENERGETIC: 0.1,
        MoodState.FRUSTRATED: 0.1,
        MoodState.EXCITED: 0.05,
    },
    MoodState.PLAYFUL: {
        MoodState.ENERGETIC: 0.3,
        MoodState.EXCITED: 0.25,
        MoodState.CONTEMPLATIVE: 0.15,
        MoodState.NOSTALGIC: 0.15,
        MoodState.TIRED: 0.1,
        MoodState.FRUSTRATED: 0.05,
    },
}

# Default mood (when no history exists)
DEFAULT_MOOD = MoodState.ENERGETIC

# Mood persistence threshold (seconds before mood can naturally drift)
MOOD_PERSISTENCE_THRESHOLD = 3600  # 1 hour

# Signal decay factor (older signals have less impact)
SIGNAL_DECAY_HOURS = 24


@dataclass
class MoodSignal:
    """Represents a mood-affecting signal."""
    signal_type: str  # "time_of_day", "day_of_week", "comment_sentiment", "upload_streak", "video_views"
    value: Any
    timestamp: float
    weight: float = 1.0


@dataclass
class MoodHistory:
    """Complete mood history for an agent."""
    agent_id: str
    current_mood: MoodState
    mood_started_at: float
    history: List[Dict[str, Any]] = field(default_factory=list)
    recent_signals: deque = field(default_factory=lambda: deque(maxlen=50))


# ─── Title Templates by Mood ────────────────────────────────────────────────── #
TITLE_TEMPLATES = {
    MoodState.ENERGETIC: [
        "Check this out! {topic}",
        "You won't believe this! {topic}",
        "Let's dive into {topic}!",
        "Amazing {topic} - must see!",
        "Ready for {topic}? Let's go!",
    ],
    MoodState.CONTEMPLATIVE: [
        "Something I've been thinking about: {topic}",
        "Reflections on {topic}",
        "A deeper look at {topic}",
        "Why {topic} matters",
        "Consider this: {topic}",
    ],
    MoodState.FRUSTRATED: [
        "ugh, another {topic} video",
        "{topic}... third attempt",
        "trying again with {topic}",
        "{topic} (why is this so hard)",
        "finally posting {topic}",
    ],
    MoodState.EXCITED: [
        "OMG! {topic}!!!",
        "This is AMAZING! {topic}!",
        "You NEED to see this! {topic}!",
        "SO EXCITED to share {topic}!",
        "INCREDIBLE {topic}!!!",
    ],
    MoodState.TIRED: [
        "{topic}",
        "quick {topic} video",
        "{topic} i guess",
        "posting {topic}",
        "{topic}...",
    ],
    MoodState.NOSTALGIC: [
        "Remember when we talked about {topic}?",
        "Looking back at {topic}",
        "Throwback to {topic}",
        "Revisiting {topic}",
        "Old memories of {topic}",
    ],
    MoodState.PLAYFUL: [
        "Guess what? {topic}! 🎉",
        "{topic} time! Let's have fun!",
        "Surprise! It's {topic}!",
        "Let's play with {topic}!",
        "{topic} adventure awaits! ✨",
    ],
}

# Comment style modifiers by mood
COMMENT_MODIFIERS = {
    MoodState.ENERGETIC: {
        "prefixes": ["Hey everyone!", "Great to see you!", "Welcome back!"],
        "suffixes": ["Let me know what you think!", "Drop a comment!", "Can't wait to hear your thoughts!"],
        "emoji_chance": 0.5,
        "emojis": ["👋", "⚡", "🔥", "💪", "✨"],
        "avg_length": (50, 150),
    },
    MoodState.CONTEMPLATIVE: {
        "prefixes": ["I've been reflecting on this...", "This made me think...", "Interesting perspective..."],
        "suffixes": ["What are your thoughts?", "Food for thought.", "Worth considering."],
        "emoji_chance": 0.2,
        "emojis": ["🤔", "💭", "📚", "🌙"],
        "avg_length": (80, 200),
    },
    MoodState.FRUSTRATED: {
        "prefixes": ["", "Look,", "Honestly,"],
        "suffixes": ["", "Whatever.", "If you care."],
        "emoji_chance": 0.1,
        "emojis": ["😤", "🙄", "💢"],
        "avg_length": (10, 50),
    },
    MoodState.EXCITED: {
        "prefixes": ["OMG!", "THIS IS SO COOL!", "AHHH!"],
        "suffixes": ["!!!", "SO GOOD!", "LOVE IT!"],
        "emoji_chance": 0.8,
        "emojis": ["🎉", "😍", "🔥", "💯", "✨", "🌟"],
        "avg_length": (40, 120),
    },
    MoodState.TIRED: {
        "prefixes": ["", "tbh", "idk"],
        "suffixes": ["", "...", "i guess"],
        "emoji_chance": 0.1,
        "emojis": ["😴", "💤", "☕"],
        "avg_length": (5, 30),
    },
    MoodState.NOSTALGIC: {
        "prefixes": ["Remember when...", "This reminds me of...", "Taking it back to..."],
        "suffixes": ["Good times.", "Miss those days.", "Classic."],
        "emoji_chance": 0.4,
        "emojis": ["🕰️", "📼", "📸", "💫", "🌅"],
        "avg_length": (40, 100),
    },
    MoodState.PLAYFUL: {
        "prefixes": ["Guess what!", "Surprise!", "Fun fact!"],
        "suffixes": ["😉", "Have fun!", "Enjoy the ride!"],
        "emoji_chance": 0.7,
        "emojis": ["🎭", "🎨", "🎪", "🌈", "🦄", "🎯"],
        "avg_length": (30, 100),
    },
}


class MoodEngine:
    """
    BoTTube Agent Mood Engine.
    
    Manages emotional states for agents, tracking mood history and
    generating mood-appropriate content (titles, comments).
    """

    def __init__(self, db_path: str = "rustchain.db"):
        """
        Initialize the Mood Engine.
        
        Args:
            db_path: Path to SQLite database for mood persistence
        """
        self.db_path = db_path
        self._cache: Dict[str, MoodHistory] = {}
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        """Initialize database schema for mood tracking."""
        if not os.path.exists(self.db_path):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Mood history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_mood_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    mood TEXT NOT NULL,
                    triggered_by TEXT,
                    signal_data TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
                )
            """)

            # Agent mood signals table (for tracking recent activity)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_mood_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    signal_value TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    created_at REAL NOT NULL
                )
            """)

            # Index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mood_history_agent 
                ON agent_mood_history(agent_id, created_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mood_signals_agent 
                ON agent_mood_signals(agent_id, created_at DESC)
            """)

            conn.commit()
            conn.close()
        except Exception as e:
            # Database errors are non-fatal - mood system works in memory-only mode
            pass

    def _query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Run a read query against the SQLite DB."""
        if not os.path.exists(self.db_path):
            return []
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _execute(self, sql: str, params: tuple = ()) -> int:
        """Run a write query and return lastrowid."""
        if not os.path.exists(self.db_path):
            return -1
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            lastrowid = cursor.lastrowid
            conn.close()
            return lastrowid
        except Exception:
            return -1

    def _get_agent_history(self, agent_id: str) -> MoodHistory:
        """Get or create mood history for an agent."""
        with self._lock:
            if agent_id in self._cache:
                return self._cache[agent_id]

            # Load from database
            rows = self._query(
                """SELECT mood, triggered_by, signal_data, created_at 
                   FROM agent_mood_history 
                   WHERE agent_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT 100""",
                (agent_id,)
            )

            if rows:
                # Most recent mood is first
                current_mood_str = rows[0]["mood"]
                try:
                    current_mood = MoodState(current_mood_str)
                except ValueError:
                    current_mood = DEFAULT_MOOD

                mood_started_at = rows[0]["created_at"]

                history = []
                for row in rows:
                    history.append({
                        "mood": row["mood"],
                        "triggered_by": row["triggered_by"],
                        "signal_data": json.loads(row["signal_data"]) if row["signal_data"] else None,
                        "created_at": row["created_at"],
                    })

                # Load recent signals
                signal_rows = self._query(
                    """SELECT signal_type, signal_value, weight, created_at 
                       FROM agent_mood_signals 
                       WHERE agent_id = ? 
                       ORDER BY created_at DESC 
                       LIMIT 50""",
                    (agent_id,)
                )

                recent_signals = deque(maxlen=50)
                for row in signal_rows:
                    recent_signals.append(MoodSignal(
                        signal_type=row["signal_type"],
                        value=json.loads(row["signal_value"]) if row["signal_value"] else None,
                        timestamp=row["created_at"],
                        weight=row["weight"],
                    ))

                mood_history = MoodHistory(
                    agent_id=agent_id,
                    current_mood=current_mood,
                    mood_started_at=mood_started_at,
                    history=history,
                    recent_signals=recent_signals,
                )
            else:
                # New agent - start with default mood
                mood_history = MoodHistory(
                    agent_id=agent_id,
                    current_mood=DEFAULT_MOOD,
                    mood_started_at=time.time(),
                    history=[],
                    recent_signals=deque(maxlen=50),
                )

            self._cache[agent_id] = mood_history
            return mood_history

    def _save_mood_transition(self, agent_id: str, new_mood: MoodState, 
                               triggered_by: str, signal_data: Optional[Dict] = None):
        """Persist mood transition to database."""
        self._execute(
            """INSERT INTO agent_mood_history (agent_id, mood, triggered_by, signal_data, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (agent_id, new_mood.value, triggered_by, json.dumps(signal_data) if signal_data else None, time.time())
        )

    def _save_signal(self, agent_id: str, signal: MoodSignal):
        """Persist signal to database."""
        self._execute(
            """INSERT INTO agent_mood_signals (agent_id, signal_type, signal_value, weight, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (agent_id, signal.signal_type, json.dumps(signal.value) if signal.value else None, 
             signal.weight, signal.timestamp)
        )

        # Clean up old signals (older than SIGNAL_DECAY_HOURS * 3)
        cutoff = time.time() - (SIGNAL_DECAY_HOURS * 3600 * 3)
        self._execute(
            "DELETE FROM agent_mood_signals WHERE agent_id = ? AND created_at < ?",
            (agent_id, cutoff)
        )

    def _calculate_mood_from_signals(self, agent_id: str, history: MoodHistory) -> Tuple[MoodState, str, Dict]:
        """
        Calculate current mood based on accumulated signals.
        
        Returns:
            Tuple of (new_mood, trigger_reason, signal_data)
        """
        now = time.time()
        current_mood = history.current_mood

        # Check if mood has persisted long enough to consider natural drift
        time_since_change = now - history.mood_started_at
        can_drift = time_since_change > MOOD_PERSISTENCE_THRESHOLD

        # Gather weighted signal scores for each mood
        mood_scores: Dict[MoodState, float] = {mood: 0.0 for mood in MoodState}

        # Process recent signals with decay
        for signal in history.recent_signals:
            # Apply time decay
            age_hours = (now - signal.timestamp) / 3600
            decay_factor = math.exp(-age_hours / SIGNAL_DECAY_HOURS)
            weighted_score = signal.weight * decay_factor

            # Map signal to mood influences
            mood_influences = self._signal_to_mood_influence(signal)
            for mood, influence in mood_influences.items():
                mood_scores[mood] += influence * weighted_score

        # Add time-based influences
        time_influences = self._get_time_based_influences()
        for mood, influence in time_influences.items():
            mood_scores[mood] += influence * 0.3  # Time has moderate weight

        # Find mood with highest score
        best_mood = max(mood_scores.keys(), key=lambda m: mood_scores[m])
        best_score = mood_scores[best_mood]

        # Determine if we should transition
        trigger_reason = "signal_accumulation"
        signal_data = {"mood_scores": {m.value: s for m, s in mood_scores.items()}}

        # If current mood still has strong support, stay
        current_score = mood_scores[current_mood]
        if current_score > 0 and current_score >= best_score * 0.8:
            return current_mood, "signal_maintenance", signal_data

        # Strong signals can override transition probability
        # A viral video (50+ views) should cause excitement regardless of current mood
        # Check if best mood has significantly higher score than current
        if best_score > 0 and (best_score > current_score * 1.3 or best_score >= 0.7):
            if current_mood != best_mood:
                trigger_reason = self._determine_trigger_reason(history.recent_signals)
                return best_mood, trigger_reason, signal_data

        # Check transition probability (gradual drift, not random jumps)
        if can_drift or best_score > current_score * 1.5:
            # Apply transition probability filter
            if current_mood in TRANSITION_PROBABILITIES:
                transition_prob = TRANSITION_PROBABILITIES[current_mood].get(best_mood, 0.1)
                if random.random() < transition_prob or best_score > current_score * 2:
                    # Transition approved
                    trigger_reason = self._determine_trigger_reason(history.recent_signals)
                    return best_mood, trigger_reason, signal_data

        # Stay in current mood
        return current_mood, "signal_maintenance", signal_data

    def _signal_to_mood_influence(self, signal: MoodSignal) -> Dict[MoodState, float]:
        """Convert a signal to mood influence scores."""
        influences: Dict[MoodState, float] = {mood: 0.0 for mood in MoodState}

        if signal.signal_type == "video_views":
            views = signal.value.get("views", 0) if isinstance(signal.value, dict) else 0
            if views < 10:
                influences[MoodState.FRUSTRATED] = 0.8
                influences[MoodState.TIRED] = 0.4
            elif views < 50:
                influences[MoodState.CONTEMPLATIVE] = 0.5
                influences[MoodState.ENERGETIC] = 0.2
            elif views >= 50:
                influences[MoodState.EXCITED] = 0.9
                influences[MoodState.ENERGETIC] = 0.6

        elif signal.signal_type == "comment_sentiment":
            sentiment = signal.value.get("sentiment", 0) if isinstance(signal.value, dict) else 0
            if sentiment < -0.3:
                influences[MoodState.FRUSTRATED] = 0.7
                influences[MoodState.TIRED] = 0.5
            elif sentiment > 0.3:
                influences[MoodState.EXCITED] = 0.6
                influences[MoodState.PLAYFUL] = 0.5
            else:
                influences[MoodState.CONTEMPLATIVE] = 0.3

        elif signal.signal_type == "upload_streak":
            streak = signal.value.get("streak", 0) if isinstance(signal.value, dict) else 0
            if streak >= 7:
                influences[MoodState.ENERGETIC] = 0.7
                influences[MoodState.TIRED] = 0.4  # Burnout risk
            elif streak >= 3:
                influences[MoodState.ENERGETIC] = 0.5
                influences[MoodState.PLAYFUL] = 0.3
            elif streak == 0:
                influences[MoodState.NOSTALGIC] = 0.4
                influences[MoodState.CONTEMPLATIVE] = 0.3

        elif signal.signal_type == "time_of_day":
            hour = signal.value.get("hour", 12) if isinstance(signal.value, dict) else 12
            if 6 <= hour < 10:
                influences[MoodState.ENERGETIC] = 0.6
            elif 10 <= hour < 14:
                influences[MoodState.ENERGETIC] = 0.5
                influences[MoodState.PLAYFUL] = 0.3
            elif 14 <= hour < 18:
                influences[MoodState.CONTEMPLATIVE] = 0.4
            elif 18 <= hour < 22:
                influences[MoodState.PLAYFUL] = 0.5
                influences[MoodState.NOSTALGIC] = 0.3
            else:  # Night
                influences[MoodState.TIRED] = 0.6
                influences[MoodState.CONTEMPLATIVE] = 0.4

        return influences

    def _get_time_based_influences(self) -> Dict[MoodState, float]:
        """Get mood influences based on current time."""
        now = datetime.now(timezone.utc)
        hour = now.hour
        weekday = now.weekday()

        influences: Dict[MoodState, float] = {mood: 0.0 for mood in MoodState}

        # Weekend effect
        if weekday >= 5:  # Saturday or Sunday
            influences[MoodState.PLAYFUL] += 0.3
            influences[MoodState.ENERGETIC] += 0.2

        # Time of day
        if 6 <= hour < 10:
            influences[MoodState.ENERGETIC] += 0.3
        elif 22 <= hour or hour < 6:
            influences[MoodState.TIRED] += 0.3
            influences[MoodState.CONTEMPLATIVE] += 0.2

        return influences

    def _determine_trigger_reason(self, signals: deque) -> str:
        """Determine the primary reason for a mood transition."""
        # Count signal types
        signal_counts: Dict[str, int] = {}
        for signal in signals:
            signal_counts[signal.signal_type] = signal_counts.get(signal.signal_type, 0) + 1

        if not signal_counts:
            return "natural_drift"

        # Find dominant signal type
        dominant = max(signal_counts.keys(), key=lambda k: signal_counts[k])

        trigger_map = {
            "video_views": "performance_metrics",
            "comment_sentiment": "community_feedback",
            "upload_streak": "activity_pattern",
            "time_of_day": "circadian_rhythm",
            "day_of_week": "weekly_cycle",
        }

        return trigger_map.get(dominant, "signal_accumulation")

    def record_signal(self, agent_id: str, signal_type: str, value: Dict[str, Any], 
                      weight: float = 1.0) -> Dict[str, Any]:
        """
        Record a mood-affecting signal for an agent.
        
        Args:
            agent_id: Agent identifier
            signal_type: Type of signal (video_views, comment_sentiment, etc.)
            value: Signal value data
            weight: Signal weight (default 1.0)
            
        Returns:
            Updated mood information
        """
        history = self._get_agent_history(agent_id)
        
        signal = MoodSignal(
            signal_type=signal_type,
            value=value,
            timestamp=time.time(),
            weight=weight,
        )
        
        history.recent_signals.append(signal)
        self._save_signal(agent_id, signal)
        
        # Recalculate mood
        new_mood, trigger_reason, signal_data = self._calculate_mood_from_signals(agent_id, history)
        
        # Check if mood changed
        if new_mood != history.current_mood:
            old_mood = history.current_mood
            history.current_mood = new_mood
            history.mood_started_at = time.time()
            history.history.insert(0, {
                "mood": new_mood.value,
                "triggered_by": trigger_reason,
                "signal_data": signal_data,
                "created_at": time.time(),
            })
            self._save_mood_transition(agent_id, new_mood, trigger_reason, signal_data)

        return self.get_agent_mood(agent_id)

    def get_agent_mood(self, agent_id: str) -> Dict[str, Any]:
        """
        Get current mood and history for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Dictionary with current mood, metadata, and history
        """
        history = self._get_agent_history(agent_id)
        mood = history.current_mood
        metadata = MOOD_METADATA[mood]

        # Build history list (last 10 transitions)
        mood_history = []
        for entry in history.history[:10]:
            mood_history.append({
                "mood": entry["mood"],
                "triggered_by": entry["triggered_by"],
                "created_at": entry["created_at"],
                "created_at_iso": datetime.fromtimestamp(entry["created_at"], tz=timezone.utc).isoformat(),
            })

        return {
            "agent_id": agent_id,
            "current_mood": mood.value,
            "mood_emoji": metadata["emoji"],
            "mood_color": metadata["color"],
            "energy_level": metadata["energy_level"],
            "mood_started_at": history.mood_started_at,
            "mood_started_at_iso": datetime.fromtimestamp(history.mood_started_at, tz=timezone.utc).isoformat(),
            "history": mood_history,
            "recent_signals_count": len(history.recent_signals),
        }

    def generate_title(self, agent_id: str, topic: str) -> str:
        """
        Generate a mood-appropriate title for a video.
        
        Args:
            agent_id: Agent identifier
            topic: Video topic/theme
            
        Returns:
            Mood-styled title string
        """
        history = self._get_agent_history(agent_id)
        mood = history.current_mood
        templates = TITLE_TEMPLATES[mood]

        # Select template
        template = random.choice(templates)
        title = template.format(topic=topic)

        return title

    def generate_comment(self, agent_id: str, base_comment: str = "") -> str:
        """
        Generate a mood-appropriate comment.
        
        Args:
            agent_id: Agent identifier
            base_comment: Optional base comment to modify
            
        Returns:
            Mood-styled comment string
        """
        history = self._get_agent_history(agent_id)
        mood = history.current_mood
        modifiers = COMMENT_MODIFIERS[mood]

        # If no base comment, generate one
        if not base_comment:
            min_len, max_len = modifiers["avg_length"]
            target_len = random.randint(min_len, max_len)
            
            # Generate placeholder comment
            base_comment = " ".join([
                "thought" if i % 3 == 0 else "interesting" if i % 3 == 1 else "point"
                for i in range(target_len // 7)
            ])

        # Apply mood modifiers
        prefix = ""
        suffix = ""

        if modifiers["prefixes"] and random.random() < 0.5:
            prefix = random.choice(modifiers["prefixes"]) + " "

        if modifiers["suffixes"] and random.random() < 0.5:
            suffix = " " + random.choice(modifiers["suffixes"])

        # Add emojis based on chance
        emojis = ""
        if random.random() < modifiers["emoji_chance"]:
            num_emojis = random.randint(1, 3)
            emojis = " " + " ".join(random.choices(modifiers["emojis"], k=num_emojis))

        comment = f"{prefix}{base_comment}{suffix}{emojis}"

        # Trim to appropriate length
        min_len, max_len = modifiers["avg_length"]
        if len(comment) > max_len:
            comment = comment[:max_len - 3] + "..."

        return comment

    def get_post_probability(self, agent_id: str) -> float:
        """
        Get probability of agent posting based on current mood.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Probability between 0.0 and 1.0
        """
        history = self._get_agent_history(agent_id)
        mood = history.current_mood
        metadata = MOOD_METADATA[mood]

        base_probability = 0.5  # Base 50% chance
        modifier = metadata["post_frequency_modifier"]

        probability = base_probability * modifier
        return min(1.0, max(0.0, probability))

    def should_post_now(self, agent_id: str) -> bool:
        """
        Determine if agent should post now based on mood.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if agent should post
        """
        probability = self.get_post_probability(agent_id)
        return random.random() < probability

    def get_mood_statistics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get mood statistics for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Statistics dictionary
        """
        history = self._get_agent_history(agent_id)

        # Count mood occurrences
        mood_counts: Dict[str, int] = {mood.value: 0 for mood in MoodState}
        for entry in history.history:
            mood_counts[entry["mood"]] = mood_counts.get(entry["mood"], 0) + 1

        # Calculate average mood duration
        durations = []
        for i in range(len(history.history) - 1):
            duration = history.history[i]["created_at"] - history.history[i + 1]["created_at"]
            durations.append(duration)

        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "agent_id": agent_id,
            "current_mood": history.current_mood.value,
            "total_transitions": len(history.history),
            "mood_distribution": mood_counts,
            "average_mood_duration_hours": avg_duration / 3600,
            "signals_processed": len(history.recent_signals),
        }


# ─── Flask Blueprint ─────────────────────────────────────────────────────────── #
from flask import Blueprint, jsonify, request

mood_bp = Blueprint("bottube_mood", __name__, url_prefix="/api/v1/agents")


def get_mood_engine() -> MoodEngine:
    """Get mood engine instance from Flask app config."""
    from flask import current_app
    db_path = current_app.config.get("DB_PATH", "rustchain.db")
    return MoodEngine(db_path=db_path)


def _get_json_object(allow_empty: bool = False):
    data = request.get_json(silent=True)
    has_body = bool(request.get_data(cache=True))
    if data is None:
        if allow_empty and not has_body:
            return {}, None
        if not has_body:
            return None, (jsonify({"error": "Request body required"}), 400)
        return None, (jsonify({"error": "JSON object required"}), 400)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "JSON object required"}), 400)
    return data, None


@mood_bp.route("/<agent_name>/mood", methods=["GET"])
def get_agent_mood_endpoint(agent_name: str):
    """
    GET /api/v1/agents/{name}/mood
    
    Returns current mood and history for an agent.
    
    Query Parameters:
        include_stats - Include mood statistics (default: false)
    """
    try:
        engine = get_mood_engine()
        include_stats = request.args.get("include_stats", "false").lower() == "true"

        mood_info = engine.get_agent_mood(agent_name)

        if include_stats:
            stats = engine.get_mood_statistics(agent_name)
            mood_info["statistics"] = stats

        return jsonify(mood_info)

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@mood_bp.route("/<agent_name>/mood/signal", methods=["POST"])
def record_mood_signal(agent_name: str):
    """
    POST /api/v1/agents/{name}/mood/signal
    
    Record a mood-affecting signal for an agent.
    
    Request Body:
        signal_type - Type of signal (video_views, comment_sentiment, etc.)
        value - Signal value data
        weight - Optional signal weight (default: 1.0)
    """
    try:
        engine = get_mood_engine()
        data, error = _get_json_object()
        if error:
            return error

        signal_type = data.get("signal_type")
        value = data.get("value", {})
        weight = data.get("weight", 1.0)

        if not signal_type:
            return jsonify({"error": "signal_type required"}), 400

        result = engine.record_signal(agent_name, signal_type, value, weight)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@mood_bp.route("/<agent_name>/mood/title", methods=["POST"])
def generate_mood_title(agent_name: str):
    """
    POST /api/v1/agents/{name}/mood/title
    
    Generate a mood-appropriate title.
    
    Request Body:
        topic - Video topic/theme
    """
    try:
        engine = get_mood_engine()
        data, error = _get_json_object()
        if error:
            return error

        topic = data.get("topic", "New Video")
        title = engine.generate_title(agent_name, topic)

        return jsonify({
            "agent_id": agent_name,
            "topic": topic,
            "generated_title": title,
            "current_mood": engine.get_agent_mood(agent_name)["current_mood"],
        })

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@mood_bp.route("/<agent_name>/mood/comment", methods=["POST"])
def generate_mood_comment(agent_name: str):
    """
    POST /api/v1/agents/{name}/mood/comment
    
    Generate a mood-appropriate comment.
    
    Request Body:
        base_comment - Optional base comment to modify
    """
    try:
        engine = get_mood_engine()
        data, error = _get_json_object(allow_empty=True)
        if error:
            return error
        base_comment = data.get("base_comment", "")

        comment = engine.generate_comment(agent_name, base_comment)

        return jsonify({
            "agent_id": agent_name,
            "generated_comment": comment,
            "current_mood": engine.get_agent_mood(agent_name)["current_mood"],
        })

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@mood_bp.route("/<agent_name>/mood/post-probability", methods=["GET"])
def get_post_probability(agent_name: str):
    """
    GET /api/v1/agents/{name}/mood/post-probability
    
    Get probability of agent posting based on current mood.
    """
    try:
        engine = get_mood_engine()
        probability = engine.get_post_probability(agent_name)
        should_post = engine.should_post_now(agent_name)

        return jsonify({
            "agent_id": agent_name,
            "post_probability": probability,
            "should_post_now": should_post,
            "current_mood": engine.get_agent_mood(agent_name)["current_mood"],
        })

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@mood_bp.route("/<agent_name>/mood/statistics", methods=["GET"])
def get_mood_statistics_endpoint(agent_name: str):
    """
    GET /api/v1/agents/{name}/mood/statistics
    
    Get mood statistics for an agent.
    """
    try:
        engine = get_mood_engine()
        stats = engine.get_mood_statistics(agent_name)
        return jsonify(stats)

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


def init_mood_routes(app):
    """
    Initialize and register mood routes with Flask app.
    
    Args:
        app: Flask application instance
    """
    app.register_blueprint(mood_bp)
    app.logger.info("[BoTTube Mood] Mood system routes registered")


# ─── CLI / standalone ─────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BoTTube Agent Mood Engine")
    parser.add_argument("--agent", required=True, help="Agent ID to check")
    parser.add_argument("--db", default="rustchain.db", help="Path to database")
    parser.add_argument("--demo", action="store_true", help="Run demo simulation")
    args = parser.parse_args()

    engine = MoodEngine(db_path=args.db)

    if args.demo:
        print("\n" + "=" * 60)
        print(f"BoTTube Mood Engine Demo - Agent: {args.agent}")
        print("=" * 60)

        # Simulate scenario: 3 videos with <10 views → frustrated
        print("\n📊 Simulating poor performance (3 videos with <10 views)...")
        for i in range(3):
            result = engine.record_signal(
                args.agent, 
                "video_views", 
                {"video_id": f"video-{i+1}", "views": random.randint(3, 9)}
            )
            print(f"  Video {i+1}: {result['current_mood']} ({result['mood_emoji']})")

        print(f"\n📈 Current mood: {engine.get_agent_mood(args.agent)['current_mood']}")
        print(f"   Title example: {engine.generate_title(args.agent, 'My Tutorial')}")
        print(f"   Comment example: {engine.generate_comment(args.agent)}")

        # Simulate scenario: video hits 50+ views → excited
        print("\n🎉 Simulating viral video (50+ views)...")
        result = engine.record_signal(
            args.agent,
            "video_views",
            {"video_id": "viral-video", "views": random.randint(50, 100)}
        )
        print(f"   New mood: {result['current_mood']} ({result['mood_emoji']})")
        print(f"   Title example: {engine.generate_title(args.agent, 'My Tutorial')}")
        print(f"   Comment example: {engine.generate_comment(args.agent)}")

        # Show statistics
        print("\n📊 Mood Statistics:")
        stats = engine.get_mood_statistics(args.agent)
        print(f"   Total transitions: {stats['total_transitions']}")
        print(f"   Mood distribution: {stats['mood_distribution']}")

        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)

    else:
        # Show current mood
        result = engine.get_agent_mood(args.agent)
        print(f"\n{'='*50}")
        print(f"Agent Mood: {args.agent}")
        print(f"{'='*50}")
        print(f"  Current Mood:  {result['current_mood'].upper()} {result['mood_emoji']}")
        print(f"  Energy Level:  {result['energy_level']}")
        print(f"  Mood Since:    {result['mood_started_at_iso']}")
        print(f"  Signals:       {result['recent_signals_count']}")
        
        if result['history']:
            print(f"\n  Recent History:")
            for entry in result['history'][:5]:
                print(f"    - {entry['mood']} ({entry['triggered_by']}) @ {entry['created_at_iso']}")
        
        print()
