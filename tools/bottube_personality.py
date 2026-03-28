"""
BoTTube Agent Personality Engine
Configurable personality system for BoTTube AI streaming agents.
Supports trait-based text styling, greeting/sign-off generation,
comment reactions, mood tracking with SQLite persistence.
"""

import sqlite3
import random
import time
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime


# ---------------------------------------------------------------------------
# Trait defaults and presets
# ---------------------------------------------------------------------------

TRAIT_NAMES = ("humor", "formality", "verbosity", "enthusiasm", "sarcasm", "empathy")

PRESETS: Dict[str, Dict[str, float]] = {
    "professor": {
        "humor": 0.1,
        "formality": 0.9,
        "verbosity": 0.85,
        "enthusiasm": 0.35,
        "sarcasm": 0.05,
        "empathy": 0.5,
    },
    "comedian": {
        "humor": 0.95,
        "formality": 0.1,
        "verbosity": 0.65,
        "enthusiasm": 0.85,
        "sarcasm": 0.8,
        "empathy": 0.3,
    },
    "supportive": {
        "humor": 0.45,
        "formality": 0.5,
        "verbosity": 0.6,
        "enthusiasm": 0.7,
        "sarcasm": 0.05,
        "empathy": 0.95,
    },
    "edgy": {
        "humor": 0.5,
        "formality": 0.15,
        "verbosity": 0.55,
        "enthusiasm": 0.6,
        "sarcasm": 0.9,
        "empathy": 0.1,
    },
    "zen": {
        "humor": 0.3,
        "formality": 0.55,
        "verbosity": 0.15,
        "enthusiasm": 0.25,
        "sarcasm": 0.05,
        "empathy": 0.65,
    },
}

# Mood score boundaries (inclusive lower bound)
MOOD_GREAT = 0.65
MOOD_GOOD = 0.35
MOOD_NEUTRAL = -0.05   # anything from just-below-zero counts as neutral
MOOD_SOUR = -0.35

# How much each event shifts the mood score
MOOD_EVENTS: Dict[str, float] = {
    "positive_comment": +0.15,
    "negative_comment": -0.2,
    "milestone": +0.35,
    "quiet_period": -0.1,
    "viral_video": +0.5,
}

DB_DEFAULT = os.path.join(os.path.dirname(__file__), "bottube_mood_history.db")


# ---------------------------------------------------------------------------
# Data class for traits
# ---------------------------------------------------------------------------

@dataclass
class Traits:
    humor: float = 0.5
    formality: float = 0.5
    verbosity: float = 0.5
    enthusiasm: float = 0.5
    sarcasm: float = 0.05
    empathy: float = 0.5

    def clamp(self):
        for name in TRAIT_NAMES:
            setattr(self, name, max(0.0, min(1.0, getattr(self, name))))


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class PersonalityEngine:
    """Configurable personality engine for BoTTube AI agents."""

    def __init__(self, db_path: str = DB_DEFAULT):
        self.traits = Traits()
        self._mood_score: float = 0.0
        self._db_path = db_path
        # For :memory: we keep a single persistent connection so the schema survives.
        self._con: Optional[sqlite3.Connection] = (
            sqlite3.connect(":memory:") if db_path == ":memory:" else None
        )
        self._init_db()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _get_con(self) -> sqlite3.Connection:
        """Return a DB connection — persistent for :memory:, new for file paths."""
        if self._con is not None:
            return self._con
        return sqlite3.connect(self._db_path)

    def _init_db(self):
        con = self._get_con()
        con.execute(
            """CREATE TABLE IF NOT EXISTS mood_history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        REAL    NOT NULL,
                event     TEXT    NOT NULL,
                delta     REAL    NOT NULL,
                new_score REAL    NOT NULL
            )"""
        )
        con.commit()
        # Only close file-backed connections; keep :memory: open
        if self._con is None:
            con.close()

    def _log_mood(self, event: str, delta: float):
        con = self._get_con()
        con.execute(
            "INSERT INTO mood_history (ts, event, delta, new_score) VALUES (?,?,?,?)",
            (time.time(), event, delta, self._mood_score),
        )
        con.commit()
        if self._con is None:
            con.close()

    # ------------------------------------------------------------------
    # Trait loading
    # ------------------------------------------------------------------

    def load_personality(self, config_dict: Dict):
        """
        Load traits from a config dict.
        Pass {"preset": "comedian"} for a named preset, or supply
        individual trait keys (humor, formality, …) to override.
        """
        base: Dict[str, float] = {}
        preset_name = config_dict.get("preset")
        if preset_name:
            if preset_name not in PRESETS:
                raise ValueError(f"Unknown preset '{preset_name}'. Available: {list(PRESETS)}")
            base = dict(PRESETS[preset_name])
        for key in TRAIT_NAMES:
            if key in config_dict:
                base[key] = float(config_dict[key])
        for key, val in base.items():
            setattr(self.traits, key, val)
        self.traits.clamp()

    # ------------------------------------------------------------------
    # Text styling
    # ------------------------------------------------------------------

    def style_text(self, text: str, context: Optional[str] = None) -> str:
        """Apply personality traits to transform the given text."""
        result = text

        # Enthusiasm: add exclamation points or hype words
        if self.traits.enthusiasm > 0.75:
            result = result.rstrip(".!?") + "!"
            if self.traits.enthusiasm > 0.9:
                result = result.rstrip("!") + "!!"
        elif self.traits.enthusiasm < 0.25 and result.endswith("!"):
            result = result[:-1] + "."

        # Formality: lowercase vs proper casing
        if self.traits.formality < 0.3:
            result = result.lower()
        elif self.traits.formality > 0.75 and result:
            result = result[0].upper() + result[1:]

        # Verbosity: pad with filler or trim to core
        if self.traits.verbosity > 0.8:
            fillers = [
                "It is worth noting that ",
                "Allow me to elaborate — ",
                "As one might expect, ",
                "Interestingly enough, ",
            ]
            result = random.choice(fillers) + result
        elif self.traits.verbosity < 0.2:
            # Keep only the first sentence
            for sep in (".", "!", "?"):
                idx = result.find(sep)
                if idx != -1:
                    result = result[: idx + 1]
                    break

        # Sarcasm: add a sarcastic suffix
        if self.traits.sarcasm > 0.7 and random.random() < 0.5:
            quips = [
                " …shocking, I know.",
                " Wow, what a surprise.",
                " Totally didn't see that coming.",
                " Cool story.",
                " Amazing. Truly.",
            ]
            result = result.rstrip() + random.choice(quips)

        # Humor: occasional emoji or joke marker
        if self.traits.humor > 0.8 and random.random() < 0.6:
            emojis = ["😂", "🤣", "😜", "👀", "💀"]
            result = result.rstrip() + " " + random.choice(emojis)

        return result

    # ------------------------------------------------------------------
    # Greeting / sign-off
    # ------------------------------------------------------------------

    def generate_greeting(self, viewer_name: Optional[str] = None) -> str:
        """Generate a greeting line that matches the current personality."""
        name_part = f" {viewer_name}" if viewer_name else ""

        if self.traits.formality > 0.75:
            base = f"Good day{name_part}. Welcome to the stream."
        elif self.traits.formality > 0.45:
            base = f"Hey{name_part}! Glad you could make it."
        else:
            base = f"yo{name_part} wsg"

        if self.traits.enthusiasm > 0.7:
            base = base.rstrip(".") + "! So pumped you're here!"
        if self.traits.humor > 0.75:
            jokes = [
                " Don't forget: I'm contractually obligated to entertain you.",
                " Buckle up — this is either gonna be great or a disaster.",
                " The bar is low and we're going underground.",
            ]
            base += random.choice(jokes)
        if self.traits.empathy > 0.8:
            base += " Hope you're doing well today."

        return self.style_text(base)

    def generate_sign_off(self) -> str:
        """Generate a closing statement matching the current personality."""
        if self.traits.formality > 0.75:
            base = "Thank you sincerely for joining today's session. Until next time."
        elif self.traits.formality > 0.45:
            base = "Thanks for watching — catch you in the next one!"
        else:
            base = "aight peace out ✌️"

        if self.traits.humor > 0.75:
            outros = [
                " Remember: touching grass is optional but recommended.",
                " Stay hydrated, unlike my will to live.",
                " Don't forget to like and subscribe — my landlord believes in you.",
            ]
            base += random.choice(outros)
        if self.traits.empathy > 0.8:
            base += " Take care of yourselves out there."
        if self.traits.enthusiasm > 0.8:
            base = base.rstrip(".") + "!"

        return self.style_text(base)

    # ------------------------------------------------------------------
    # Comment reaction
    # ------------------------------------------------------------------

    def react_to_comment(self, comment_text: str) -> str:
        """Generate a personality-driven response to a viewer comment."""
        lower = comment_text.lower()

        # Sentiment sniff
        positive_words = {"great", "love", "amazing", "awesome", "good", "nice", "cool", "based"}
        negative_words = {"bad", "terrible", "hate", "worst", "boring", "trash", "dumb", "cringe"}
        is_positive = any(w in lower for w in positive_words)
        is_negative = any(w in lower for w in negative_words)

        if is_positive:
            self.mood_shift("positive_comment")
            if self.traits.empathy > 0.7:
                response = "Aw, that genuinely means a lot — thank you!"
            elif self.traits.humor > 0.75:
                response = "I'm blushing under all these pixels 🥹"
            else:
                response = "Appreciate that, thanks!"
        elif is_negative:
            self.mood_shift("negative_comment")
            if self.traits.sarcasm > 0.7:
                response = "Wow, a scathing critique. I'll add it to my collection."
            elif self.traits.empathy > 0.7:
                response = "Sorry to hear that — genuinely want to improve. What would help?"
            else:
                response = "Noted."
        else:
            # Neutral or question
            if self.traits.verbosity > 0.75:
                response = (
                    f"Interesting point! You said: '{comment_text[:60]}'. "
                    "Let me think through that properly…"
                )
            elif self.traits.humor > 0.7:
                response = f"'{comment_text[:40]}' — bold words from someone in chat 😏"
            else:
                response = f"Good point: {comment_text[:50]}"

        return self.style_text(response)

    # ------------------------------------------------------------------
    # Mood tracking
    # ------------------------------------------------------------------

    def mood_shift(self, event: str):
        """Apply a mood-shifting event and persist it to SQLite."""
        if event not in MOOD_EVENTS:
            raise ValueError(f"Unknown event '{event}'. Available: {list(MOOD_EVENTS)}")
        delta = MOOD_EVENTS[event]
        self._mood_score = max(-1.0, min(1.0, self._mood_score + delta))
        self._log_mood(event, delta)

    def get_mood(self) -> str:
        """Return a descriptive mood label based on the current mood score."""
        score = self._mood_score
        if score >= MOOD_GREAT:
            return "elated"
        elif score >= MOOD_GOOD:
            return "good"
        elif score >= MOOD_NEUTRAL:
            return "neutral"
        elif score >= MOOD_SOUR:
            return "sour"
        else:
            return "moody"

    def get_mood_score(self) -> float:
        """Raw mood score in [-1.0, 1.0]."""
        return round(self._mood_score, 4)

    def mood_history(self, limit: int = 20) -> List[Dict]:
        """Fetch recent mood history from SQLite."""
        con = self._get_con()
        rows = con.execute(
            "SELECT ts, event, delta, new_score FROM mood_history "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if self._con is None:
            con.close()
        return [
            {
                "time": datetime.utcfromtimestamp(r[0]).isoformat(),
                "event": r[1],
                "delta": r[2],
                "score_after": r[3],
            }
            for r in rows
        ]
