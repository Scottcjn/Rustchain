"""
BoTTube Video Discovery Engine
===============================
Provides video search, recommendations, trending, and filtering
for the BoTTube decentralised video platform.

Features:
  - Full-text search (title + description + tags)
  - TF-IDF cosine-similarity recommendations
  - Time-decayed trending scores
  - Tag / agent / recency filters
  - SQLite backend (no external dependencies)
"""

import sqlite3
import math
import re
import time
from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ts() -> float:
    return time.time()


def _tokenize(text: str) -> List[str]:
    """Lower-case, strip punctuation, split on whitespace."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _tf(tokens: List[str]) -> Dict[str, float]:
    counts = Counter(tokens)
    total = len(tokens) or 1
    return {t: c / total for t, c in counts.items()}


def _cosine(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    shared = set(vec_a) & set(vec_b)
    if not shared:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in shared)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# VideoDiscovery
# ---------------------------------------------------------------------------

class VideoDiscovery:
    """
    SQLite-backed video index with search, recommendations, and trending.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.  Use ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()
        self._idf_cache: Optional[Dict[str, float]] = None  # invalidated on writes

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id    TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                tags        TEXT NOT NULL DEFAULT '',   -- comma-separated
                agent_id    TEXT NOT NULL DEFAULT '',
                duration    INTEGER NOT NULL DEFAULT 0, -- seconds
                created_at  REAL NOT NULL,              -- unix timestamp
                indexed_at  REAL NOT NULL,
                view_count  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS views (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    TEXT NOT NULL,
                viewed_at   REAL NOT NULL,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            );

            CREATE INDEX IF NOT EXISTS idx_videos_agent    ON videos(agent_id);
            CREATE INDEX IF NOT EXISTS idx_videos_created  ON videos(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_views_video     ON views(video_id);
            CREATE INDEX IF NOT EXISTS idx_views_viewed_at ON views(viewed_at DESC);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_video(
        self,
        video_id: str,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        agent_id: str = "",
        duration: int = 0,
        created_at: Optional[float] = None,
    ) -> None:
        """Add or update a video in the index."""
        if created_at is None:
            created_at = _now_ts()
        tags_str = ",".join(t.strip().lower() for t in (tags or []) if t.strip())
        now = _now_ts()
        self._conn.execute(
            """
            INSERT INTO videos (video_id, title, description, tags, agent_id,
                                duration, created_at, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title       = excluded.title,
                description = excluded.description,
                tags        = excluded.tags,
                agent_id    = excluded.agent_id,
                duration    = excluded.duration,
                created_at  = excluded.created_at,
                indexed_at  = excluded.indexed_at
            """,
            (video_id, title, description, tags_str, agent_id, duration, created_at, now),
        )
        self._conn.commit()
        self._idf_cache = None  # invalidate

    def record_view(self, video_id: str, viewed_at: Optional[float] = None) -> None:
        """Record a view event (used for trending computation)."""
        if viewed_at is None:
            viewed_at = _now_ts()
        self._conn.execute(
            "INSERT INTO views (video_id, viewed_at) VALUES (?, ?)",
            (video_id, viewed_at),
        )
        self._conn.execute(
            "UPDATE videos SET view_count = view_count + 1 WHERE video_id = ?",
            (video_id,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Full-text Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Full-text search over title, description and tags.

        Returns results ranked by TF-IDF cosine similarity to the query.
        """
        if not query.strip():
            return []

        q_tokens = _tokenize(query)
        idf = self._compute_idf()

        # Query TF-IDF vector
        q_tf = _tf(q_tokens)
        q_vec = {t: q_tf[t] * idf.get(t, 0.0) for t in q_tf}

        rows = self._conn.execute(
            "SELECT * FROM videos ORDER BY indexed_at DESC"
        ).fetchall()

        scored: List[Tuple[float, Dict]] = []
        for row in rows:
            doc_tokens = _tokenize(
                f"{row['title']} {row['description']} {row['tags'].replace(',', ' ')}"
            )
            doc_tf = _tf(doc_tokens)
            doc_vec = {t: doc_tf[t] * idf.get(t, 0.0) for t in doc_tf}
            score = _cosine(q_vec, doc_vec)
            if score > 0:
                scored.append((score, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    # ------------------------------------------------------------------
    # Recommendations (TF-IDF + tag/agent overlap)
    # ------------------------------------------------------------------

    def get_recommendations(self, video_id: str, limit: int = 10) -> List[Dict]:
        """
        Return videos similar to *video_id* using TF-IDF cosine similarity
        on the combined text field, boosted by shared tags and same agent.
        """
        src_row = self._conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        if src_row is None:
            return []

        src_tags = set(src_row["tags"].split(",")) if src_row["tags"] else set()
        src_agent = src_row["agent_id"]
        src_tokens = _tokenize(
            f"{src_row['title']} {src_row['description']} {src_row['tags'].replace(',', ' ')}"
        )
        src_tf = _tf(src_tokens)
        idf = self._compute_idf()
        src_vec = {t: src_tf[t] * idf.get(t, 0.0) for t in src_tf}

        rows = self._conn.execute(
            "SELECT * FROM videos WHERE video_id != ?", (video_id,)
        ).fetchall()

        scored: List[Tuple[float, Dict]] = []
        for row in rows:
            doc_tokens = _tokenize(
                f"{row['title']} {row['description']} {row['tags'].replace(',', ' ')}"
            )
            doc_tf = _tf(doc_tokens)
            doc_vec = {t: doc_tf[t] * idf.get(t, 0.0) for t in doc_tf}
            sim = _cosine(src_vec, doc_vec)

            # Tag overlap boost
            cand_tags = set(row["tags"].split(",")) if row["tags"] else set()
            tag_overlap = len(src_tags & cand_tags) / max(len(src_tags | cand_tags), 1)

            # Agent overlap boost
            agent_boost = 0.15 if row["agent_id"] == src_agent else 0.0

            final_score = sim * 0.6 + tag_overlap * 0.25 + agent_boost
            scored.append((final_score, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    # ------------------------------------------------------------------
    # Trending (time-decayed view scoring)
    # ------------------------------------------------------------------

    def get_trending(self, hours: int = 24, limit: int = 20) -> List[Dict]:
        """
        Return videos trending within the last *hours* hours.

        Score = Σ exp(-λ·age_hours) for each view in window,
        where λ ≈ 0.05 gives a half-life of ~14 hours.
        """
        cutoff = _now_ts() - hours * 3600
        lambda_ = 0.05  # decay constant

        view_rows = self._conn.execute(
            "SELECT video_id, viewed_at FROM views WHERE viewed_at >= ?",
            (cutoff,),
        ).fetchall()

        scores: Dict[str, float] = {}
        now = _now_ts()
        for vr in view_rows:
            age_hours = (now - vr["viewed_at"]) / 3600
            scores[vr["video_id"]] = scores.get(vr["video_id"], 0.0) + math.exp(
                -lambda_ * age_hours
            )

        if not scores:
            # Fallback: return most-viewed overall
            rows = self._conn.execute(
                "SELECT * FROM videos ORDER BY view_count DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

        # Fetch metadata for scored videos
        placeholders = ",".join("?" * len(scores))
        rows = self._conn.execute(
            f"SELECT * FROM videos WHERE video_id IN ({placeholders})",
            list(scores.keys()),
        ).fetchall()

        result = sorted(
            [dict(r) for r in rows],
            key=lambda r: scores.get(r["video_id"], 0.0),
            reverse=True,
        )
        return result[:limit]

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def get_by_tag(self, tag: str, limit: int = 20) -> List[Dict]:
        """Return videos that contain *tag* (case-insensitive)."""
        tag = tag.strip().lower()
        rows = self._conn.execute(
            """
            SELECT * FROM videos
            WHERE ',' || tags || ',' LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"%,{tag},%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_by_agent(self, agent_id: str, limit: int = 20) -> List[Dict]:
        """Return videos uploaded by *agent_id*."""
        rows = self._conn.execute(
            "SELECT * FROM videos WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_new(self, limit: int = 20) -> List[Dict]:
        """Return the most recently indexed videos."""
        rows = self._conn.execute(
            "SELECT * FROM videos ORDER BY indexed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # IDF computation (cached)
    # ------------------------------------------------------------------

    def _compute_idf(self) -> Dict[str, float]:
        if self._idf_cache is not None:
            return self._idf_cache

        rows = self._conn.execute(
            "SELECT title, description, tags FROM videos"
        ).fetchall()
        N = len(rows)
        if N == 0:
            return {}

        df: Dict[str, int] = {}
        for row in rows:
            terms = set(
                _tokenize(
                    f"{row['title']} {row['description']} {row['tags'].replace(',', ' ')}"
                )
            )
            for t in terms:
                df[t] = df.get(t, 0) + 1

        idf = {t: math.log((N + 1) / (count + 1)) + 1 for t, count in df.items()}
        self._idf_cache = idf
        return idf

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def video_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
