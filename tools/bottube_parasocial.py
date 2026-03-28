"""
BoTTube Parasocial Hooks — Audience Tracker Module
Bounty #2286

Tracks viewer engagement patterns and generates personalized parasocial
responses for BoTTube agents. Agents can reference viewer history in
natural language responses ("I noticed you always watch my late-night streams...").
"""

import sqlite3
import time
import math
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict


DB_PATH = "bottube_parasocial.db"


class AudienceTracker:
    """
    Tracks viewer engagement across videos and generates personality hooks
    for BoTTube agents to use in personalized responses.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------ #
    # DB setup
    # ------------------------------------------------------------------ #

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS views (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    viewer_id   TEXT    NOT NULL,
                    video_id    TEXT    NOT NULL,
                    watched_at  INTEGER NOT NULL,   -- unix timestamp
                    duration    REAL    NOT NULL,   -- seconds watched
                    liked       INTEGER NOT NULL DEFAULT 0,
                    commented   INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_views_viewer ON views(viewer_id);
                CREATE INDEX IF NOT EXISTS idx_views_video  ON views(video_id);

                CREATE TABLE IF NOT EXISTS video_meta (
                    video_id    TEXT PRIMARY KEY,
                    topic       TEXT,
                    total_secs  REAL NOT NULL DEFAULT 0
                );
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------ #
    # Core tracking
    # ------------------------------------------------------------------ #

    def track_view(
        self,
        viewer_id: str,
        video_id: str,
        watch_duration: float,
        liked: bool = False,
        commented: bool = False,
        watched_at: Optional[int] = None,
        topic: str = "general",
        total_video_secs: float = 600.0,
    ):
        """Record a viewer interaction with a video."""
        ts = watched_at or int(time.time())
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO views (viewer_id, video_id, watched_at, duration, liked, commented)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (viewer_id, video_id, ts, watch_duration, int(liked), int(commented)),
            )
            conn.execute(
                """INSERT INTO video_meta (video_id, topic, total_secs)
                   VALUES (?, ?, ?)
                   ON CONFLICT(video_id) DO UPDATE SET
                       topic = excluded.topic,
                       total_secs = excluded.total_secs""",
                (video_id, topic, total_video_secs),
            )

    # ------------------------------------------------------------------ #
    # Fan scoring
    # ------------------------------------------------------------------ #

    def get_fan_score(self, viewer_id: str) -> float:
        """
        Return a fan score 0–100 based on:
        - Watch frequency  (40 pts)
        - Watch duration % (30 pts)
        - Likes            (15 pts)
        - Comments         (15 pts)
        """
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT v.duration, v.liked, v.commented, m.total_secs
                   FROM views v
                   LEFT JOIN video_meta m ON v.video_id = m.video_id
                   WHERE v.viewer_id = ?""",
                (viewer_id,),
            ).fetchall()

        if not rows:
            return 0.0

        n = len(rows)
        total_duration_pct = sum(
            min(r["duration"] / max(r["total_secs"] or 600, 1), 1.0) for r in rows
        ) / n
        like_rate = sum(r["liked"] for r in rows) / n
        comment_rate = sum(r["commented"] for r in rows) / n

        # Frequency: log-scale, 20 views ≈ max
        freq_score = min(math.log1p(n) / math.log1p(20), 1.0)

        score = (
            freq_score * 40
            + total_duration_pct * 30
            + like_rate * 15
            + comment_rate * 15
        )
        return round(min(score, 100.0), 2)

    # ------------------------------------------------------------------ #
    # Rankings
    # ------------------------------------------------------------------ #

    def get_top_fans(self, limit: int = 10) -> list[dict]:
        """Return ranked list of top fans with their scores."""
        with self._conn() as conn:
            viewer_ids = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT viewer_id FROM views"
                ).fetchall()
            ]

        ranked = sorted(
            [{"viewer_id": vid, "score": self.get_fan_score(vid)} for vid in viewer_ids],
            key=lambda x: x["score"],
            reverse=True,
        )
        for i, entry in enumerate(ranked, 1):
            entry["rank"] = i
        return ranked[:limit]

    # ------------------------------------------------------------------ #
    # Viewer pattern analysis
    # ------------------------------------------------------------------ #

    def get_viewer_pattern(self, viewer_id: str) -> dict:
        """
        Return a dict describing a viewer's watch habits:
        - total_views, unique_videos
        - avg_watch_pct
        - favorite_topics (list)
        - peak_hour (0-23 UTC)
        - engagement_trend: 'rising' | 'stable' | 'fading'
        - first_seen, last_seen (ISO strings)
        """
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT v.*, m.topic, m.total_secs
                   FROM views v
                   LEFT JOIN video_meta m ON v.video_id = m.video_id
                   WHERE v.viewer_id = ?
                   ORDER BY v.watched_at ASC""",
                (viewer_id,),
            ).fetchall()

        if not rows:
            return {}

        hours = [datetime.fromtimestamp(r["watched_at"], tz=timezone.utc).hour for r in rows]
        peak_hour = max(set(hours), key=hours.count)

        topic_counts: dict[str, int] = defaultdict(int)
        for r in rows:
            topic_counts[r["topic"] or "general"] += 1
        fav_topics = sorted(topic_counts, key=topic_counts.get, reverse=True)[:3]  # type: ignore[arg-type]

        avg_pct = sum(
            min(r["duration"] / max(r["total_secs"] or 600, 1), 1.0) for r in rows
        ) / len(rows)

        # Trend: compare engagement of first half vs second half
        mid = len(rows) // 2
        def _eng(subset):
            return sum(r["liked"] + r["commented"] for r in subset) / max(len(subset), 1)

        if mid > 0:
            early, late = _eng(rows[:mid]), _eng(rows[mid:])
            trend = "rising" if late > early + 0.1 else ("fading" if early > late + 0.1 else "stable")
        else:
            trend = "stable"

        first_seen = datetime.fromtimestamp(rows[0]["watched_at"], tz=timezone.utc).isoformat()
        last_seen  = datetime.fromtimestamp(rows[-1]["watched_at"], tz=timezone.utc).isoformat()

        return {
            "total_views":       len(rows),
            "unique_videos":     len({r["video_id"] for r in rows}),
            "avg_watch_pct":     round(avg_pct * 100, 1),
            "favorite_topics":   fav_topics,
            "peak_hour":         peak_hour,
            "engagement_trend":  trend,
            "first_seen":        first_seen,
            "last_seen":         last_seen,
            "fan_score":         self.get_fan_score(viewer_id),
        }

    # ------------------------------------------------------------------ #
    # Personality hooks
    # ------------------------------------------------------------------ #

    def generate_shoutout(self, viewer_id: str) -> str:
        """
        Generate a personalized shoutout message the agent can deliver.
        References real viewing patterns for an authentic parasocial feel.
        """
        pattern = self.get_viewer_pattern(viewer_id)
        if not pattern:
            return f"Hey {viewer_id}, welcome — I don't know you yet but I'm glad you're here! 👋"

        score = pattern["fan_score"]
        peak  = pattern["peak_hour"]
        topics = pattern["favorite_topics"]
        trend  = pattern["engagement_trend"]
        views  = pattern["total_views"]

        # Time-of-day flavour
        if 0 <= peak < 6:
            time_hook = "night-owl"
        elif 6 <= peak < 12:
            time_hook = "morning-stream"
        elif 12 <= peak < 18:
            time_hook = "afternoon"
        else:
            time_hook = "evening"

        topic_str = f" especially anything about **{topics[0]}**" if topics else ""

        if score >= 75:
            tier = "absolute legend"
            action = "I seriously see you in almost every stream"
        elif score >= 50:
            tier = "super-fan"
            action = "you show up consistently and it means a lot"
        elif score >= 25:
            tier = "regular"
            action = "I've noticed you dropping by"
        else:
            tier = "viewer"
            action = "you've been checking things out"

        trend_line = ""
        if trend == "rising":
            trend_line = " You've been getting more and more engaged lately — love to see it! 📈"
        elif trend == "fading":
            trend_line = " Hope everything's okay — I've missed seeing you around! ❤️"

        msg = (
            f"Shoutout to **{viewer_id}**, a {tier} in this community! 🎉 "
            f"I've noticed {action} — you're always here for the {time_hook} content,{topic_str}. "
            f"You've watched {views} stream(s) with us.{trend_line} "
            f"We see you and we appreciate you! 🙌"
        )
        return msg

    # ------------------------------------------------------------------ #
    # Detection helpers
    # ------------------------------------------------------------------ #

    def detect_lurker(self, viewer_id: str) -> bool:
        """
        Lurker: watches content but has never commented.
        Must have at least 3 views to qualify (not just a casual passer-by).
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n, SUM(commented) AS c FROM views WHERE viewer_id = ?",
                (viewer_id,),
            ).fetchone()
        return row["n"] >= 3 and (row["c"] or 0) == 0

    def detect_superfan(self, viewer_id: str) -> bool:
        """
        Superfan: watches essentially everything, likes and comments regularly.
        Criteria: fan score ≥ 70, like_rate ≥ 50%, comment_rate ≥ 30%.
        """
        if self.get_fan_score(viewer_id) < 70:
            return False
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n, SUM(liked) AS l, SUM(commented) AS c FROM views WHERE viewer_id = ?",
                (viewer_id,),
            ).fetchone()
        n = row["n"] or 0
        if n == 0:
            return False
        return (row["l"] or 0) / n >= 0.5 and (row["c"] or 0) / n >= 0.3
