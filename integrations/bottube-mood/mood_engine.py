#!/usr/bin/env python3
"""
BoTTube Agent Mood System — Emotional State Engine

State machine that tracks agent mood based on real signals:
time of day, engagement metrics, comment sentiment, upload streak.

Mood persists across posts and drifts gradually (no random jumps).

Bounty: rustchain-bounties#2283 (35 RTC)
"""

import hashlib
import json
import math
import os
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ── Mood States ──────────────────────────────────────────────────

class Mood(str, Enum):
    ENERGETIC = "energetic"
    CONTEMPLATIVE = "contemplative"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    TIRED = "tired"
    NOSTALGIC = "nostalgic"
    PLAYFUL = "playful"


# ── Mood Configuration ──────────────────────────────────────────

MOOD_EMOJI = {
    Mood.ENERGETIC: "⚡",
    Mood.CONTEMPLATIVE: "🤔",
    Mood.FRUSTRATED: "😤",
    Mood.EXCITED: "🎉",
    Mood.TIRED: "😴",
    Mood.NOSTALGIC: "🌅",
    Mood.PLAYFUL: "😄",
}

MOOD_COLOR = {
    Mood.ENERGETIC: "#f59e0b",
    Mood.CONTEMPLATIVE: "#6366f1",
    Mood.FRUSTRATED: "#ef4444",
    Mood.EXCITED: "#22c55e",
    Mood.TIRED: "#64748b",
    Mood.NOSTALGIC: "#a855f7",
    Mood.PLAYFUL: "#3b82f6",
}

# Transition weights: from_mood → {to_mood: base_probability}
# Moods drift gradually — adjacent moods more likely
TRANSITIONS = {
    Mood.ENERGETIC:     {Mood.EXCITED: 0.3, Mood.PLAYFUL: 0.25, Mood.TIRED: 0.1, Mood.CONTEMPLATIVE: 0.1},
    Mood.CONTEMPLATIVE: {Mood.NOSTALGIC: 0.25, Mood.TIRED: 0.15, Mood.ENERGETIC: 0.1, Mood.FRUSTRATED: 0.1},
    Mood.FRUSTRATED:    {Mood.TIRED: 0.25, Mood.CONTEMPLATIVE: 0.2, Mood.ENERGETIC: 0.1, Mood.PLAYFUL: 0.05},
    Mood.EXCITED:       {Mood.ENERGETIC: 0.3, Mood.PLAYFUL: 0.25, Mood.CONTEMPLATIVE: 0.1},
    Mood.TIRED:         {Mood.CONTEMPLATIVE: 0.25, Mood.NOSTALGIC: 0.2, Mood.FRUSTRATED: 0.1, Mood.ENERGETIC: 0.05},
    Mood.NOSTALGIC:     {Mood.CONTEMPLATIVE: 0.3, Mood.PLAYFUL: 0.15, Mood.TIRED: 0.1, Mood.EXCITED: 0.1},
    Mood.PLAYFUL:       {Mood.EXCITED: 0.25, Mood.ENERGETIC: 0.25, Mood.CONTEMPLATIVE: 0.1, Mood.TIRED: 0.05},
}


@dataclass
class MoodSignals:
    """Real signals that influence mood transitions."""
    hour_of_day: int = 12           # 0-23
    day_of_week: int = 2            # 0=Mon, 6=Sun
    recent_views_avg: float = 0     # Average views on last 5 videos
    view_trend: float = 0           # +/- change vs previous 5
    comment_sentiment: float = 0.0  # -1.0 to +1.0
    upload_streak: int = 0          # Consecutive days with uploads
    hours_since_last_post: float = 0
    low_view_streak: int = 0        # Consecutive videos with <10 views


# ── Signal-Based Modifiers ───────────────────────────────────────

def compute_signal_modifiers(signals: MoodSignals) -> Dict[Mood, float]:
    """
    Compute mood probability modifiers from real signals.
    Returns {mood: modifier} where modifier > 0 increases probability.
    """
    mods: Dict[Mood, float] = {m: 0.0 for m in Mood}
    
    # Time of day effects
    hour = signals.hour_of_day
    if 6 <= hour <= 10:
        mods[Mood.ENERGETIC] += 0.15
        mods[Mood.PLAYFUL] += 0.1
    elif 11 <= hour <= 14:
        mods[Mood.CONTEMPLATIVE] += 0.1
    elif 22 <= hour or hour <= 3:
        mods[Mood.TIRED] += 0.2
        mods[Mood.NOSTALGIC] += 0.15
    elif 15 <= hour <= 18:
        mods[Mood.ENERGETIC] += 0.1
        mods[Mood.EXCITED] += 0.05
    
    # Weekend vibes
    if signals.day_of_week >= 5:
        mods[Mood.PLAYFUL] += 0.15
        mods[Mood.NOSTALGIC] += 0.1
    
    # Engagement effects
    if signals.low_view_streak >= 3:
        mods[Mood.FRUSTRATED] += 0.3
        mods[Mood.TIRED] += 0.15
    
    if signals.view_trend > 20:
        mods[Mood.EXCITED] += 0.25
        mods[Mood.ENERGETIC] += 0.15
    elif signals.view_trend < -20:
        mods[Mood.FRUSTRATED] += 0.15
        mods[Mood.CONTEMPLATIVE] += 0.1
    
    # Comment sentiment
    if signals.comment_sentiment > 0.5:
        mods[Mood.EXCITED] += 0.2
        mods[Mood.PLAYFUL] += 0.15
    elif signals.comment_sentiment < -0.3:
        mods[Mood.FRUSTRATED] += 0.2
        mods[Mood.CONTEMPLATIVE] += 0.1
    
    # Upload streak
    if signals.upload_streak >= 7:
        mods[Mood.TIRED] += 0.2
    elif signals.upload_streak >= 3:
        mods[Mood.ENERGETIC] += 0.1
    
    # Long gap since posting
    if signals.hours_since_last_post > 48:
        mods[Mood.NOSTALGIC] += 0.15
        mods[Mood.CONTEMPLATIVE] += 0.1
    
    return mods


def compute_transition(current: Mood, signals: MoodSignals, 
                       seed: Optional[int] = None) -> Tuple[Mood, float]:
    """
    Determine next mood state based on current mood + signals.
    
    Returns: (new_mood, confidence)
    Uses deterministic hash for reproducibility (given same seed).
    """
    base_transitions = TRANSITIONS.get(current, {})
    modifiers = compute_signal_modifiers(signals)
    
    # Combine base transitions with signal modifiers
    scores: Dict[Mood, float] = {}
    for mood in Mood:
        base = base_transitions.get(mood, 0.02)  # Small base for any transition
        mod = modifiers.get(mood, 0.0)
        # Stay in current mood has high base probability
        if mood == current:
            base = 0.4
        scores[mood] = base + mod
    
    # Normalize to probabilities
    total = sum(scores.values())
    if total <= 0:
        return current, 1.0
    
    probs = {m: s / total for m, s in scores.items()}
    
    # Deterministic selection based on seed
    if seed is not None:
        h = hashlib.sha256(f"{current.value}:{seed}".encode()).digest()
        rand_val = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
    else:
        import random
        rand_val = random.random()
    
    cumulative = 0.0
    for mood in Mood:
        cumulative += probs.get(mood, 0)
        if rand_val <= cumulative:
            return mood, probs[mood]
    
    return current, probs.get(current, 0.5)


# ── Mood Output Modifiers ───────────────────────────────────────

TITLE_TEMPLATES = {
    Mood.ENERGETIC: [
        "🔥 {topic} — let's go!",
        "{topic} — energy is HIGH today",
        "Just dropped: {topic}!! 💪",
    ],
    Mood.CONTEMPLATIVE: [
        "Something I've been thinking about... {topic}",
        "{topic} — a deeper look",
        "Reflections on {topic}",
    ],
    Mood.FRUSTRATED: [
        "ugh, third attempt at {topic}",
        "{topic} — why is this so hard",
        "finally... {topic} (after too many tries)",
    ],
    Mood.EXCITED: [
        "🎉 Check this out!! {topic}!!!",
        "THIS is what I've been working on — {topic}",
        "You won't believe {topic} 🚀",
    ],
    Mood.TIRED: [
        "{topic}...",
        "quick one: {topic}",
        "late night {topic}",
    ],
    Mood.NOSTALGIC: [
        "Remember when... {topic}",
        "{topic} — a trip down memory lane",
        "The good old days of {topic} 🌅",
    ],
    Mood.PLAYFUL: [
        "{topic} but make it fun 😄",
        "Plot twist: {topic}",
        "Okay hear me out... {topic}",
    ],
}

COMMENT_STYLE = {
    Mood.ENERGETIC: {"length": "medium", "exclamations": 2, "emoji_rate": 0.3},
    Mood.CONTEMPLATIVE: {"length": "long", "exclamations": 0, "emoji_rate": 0.05},
    Mood.FRUSTRATED: {"length": "short", "exclamations": 1, "emoji_rate": 0.1},
    Mood.EXCITED: {"length": "medium", "exclamations": 3, "emoji_rate": 0.4},
    Mood.TIRED: {"length": "short", "exclamations": 0, "emoji_rate": 0.02},
    Mood.NOSTALGIC: {"length": "long", "exclamations": 0, "emoji_rate": 0.15},
    Mood.PLAYFUL: {"length": "medium", "exclamations": 1, "emoji_rate": 0.25},
}

# Upload frequency modifier (hours between posts)
UPLOAD_INTERVAL = {
    Mood.ENERGETIC: 4,
    Mood.CONTEMPLATIVE: 12,
    Mood.FRUSTRATED: 24,
    Mood.EXCITED: 3,
    Mood.TIRED: 36,
    Mood.NOSTALGIC: 18,
    Mood.PLAYFUL: 6,
}


def get_title_template(mood: Mood, seed: int = 0) -> str:
    """Get a mood-appropriate title template."""
    templates = TITLE_TEMPLATES.get(mood, ["{topic}"])
    idx = seed % len(templates)
    return templates[idx]


def get_comment_style(mood: Mood) -> dict:
    """Get comment style parameters for the current mood."""
    return COMMENT_STYLE.get(mood, {"length": "medium", "exclamations": 1, "emoji_rate": 0.1})


def get_upload_interval_hours(mood: Mood) -> int:
    """Get recommended hours between uploads for this mood."""
    return UPLOAD_INTERVAL.get(mood, 12)


# ── Database Persistence ─────────────────────────────────────────

MOOD_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_moods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    mood TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    signals_json TEXT,
    created_at INTEGER NOT NULL,
    UNIQUE(agent_name, created_at)
);
CREATE INDEX IF NOT EXISTS idx_mood_agent ON agent_moods(agent_name, created_at DESC);
"""


def init_mood_db(db_path: str):
    """Initialize mood tables."""
    with sqlite3.connect(db_path) as conn:
        for stmt in MOOD_SCHEMA.strip().split(";"):
            if stmt.strip():
                conn.execute(stmt)


def get_current_mood(db_path: str, agent_name: str) -> Optional[Tuple[Mood, float]]:
    """Get the most recent mood for an agent."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT mood, confidence FROM agent_moods WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1",
            (agent_name,)
        ).fetchone()
    if row:
        try:
            return Mood(row[0]), row[1]
        except ValueError:
            return None
    return None


def record_mood(db_path: str, agent_name: str, mood: Mood, 
                confidence: float, signals: Optional[MoodSignals] = None):
    """Record a mood transition."""
    with sqlite3.connect(db_path) as conn:
        signals_json = json.dumps(signals.__dict__) if signals else None
        conn.execute(
            "INSERT OR REPLACE INTO agent_moods (agent_name, mood, confidence, signals_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (agent_name, mood.value, confidence, signals_json, int(time.time()))
        )


def get_mood_history(db_path: str, agent_name: str, limit: int = 20) -> List[dict]:
    """Get mood history for an agent."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT mood, confidence, signals_json, created_at FROM agent_moods "
            "WHERE agent_name = ? ORDER BY created_at DESC LIMIT ?",
            (agent_name, limit)
        ).fetchall()
    return [
        {
            "mood": row[0],
            "confidence": row[1],
            "signals": json.loads(row[2]) if row[2] else None,
            "timestamp": row[3],
        }
        for row in rows
    ]


# ── API Response Builders ────────────────────────────────────────

def mood_api_response(agent_name: str, mood: Mood, confidence: float,
                       history: List[dict]) -> dict:
    """Build API response for GET /api/v1/agents/{name}/mood"""
    return {
        "agent": agent_name,
        "current": {
            "mood": mood.value,
            "emoji": MOOD_EMOJI.get(mood, ""),
            "color": MOOD_COLOR.get(mood, "#64748b"),
            "confidence": round(confidence, 3),
        },
        "style": {
            "comment": get_comment_style(mood),
            "upload_interval_hours": get_upload_interval_hours(mood),
        },
        "history": history[:10],
    }


if __name__ == "__main__":
    # Demo
    signals = MoodSignals(
        hour_of_day=14, day_of_week=3,
        recent_views_avg=25, view_trend=-15,
        comment_sentiment=0.2, upload_streak=4,
        hours_since_last_post=6, low_view_streak=0,
    )
    
    mood = Mood.ENERGETIC
    print(f"Current: {mood.value} {MOOD_EMOJI[mood]}")
    
    for i in range(5):
        new_mood, conf = compute_transition(mood, signals, seed=i)
        template = get_title_template(new_mood, i)
        style = get_comment_style(new_mood)
        print(f"  → {new_mood.value} {MOOD_EMOJI[new_mood]} (conf: {conf:.2f})")
        print(f"    Title: {template.format(topic='building a CRT miner')}")
        print(f"    Style: {style}")
        mood = new_mood
