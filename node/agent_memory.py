"""
agent_memory.py — Agent Memory Layer for BoTTube
Provides self-reference capability to break the uncanny valley
Part of: https://github.com/Scottcjn/rustchain-bounties/issues/2285
Bounty: 40 RTC

Features:
- Content memory store (vector search for agent's own videos/descriptions/comments)
- Semantic similarity search using TF-IDF + cosine similarity (no external dependencies)
- Self-reference generation
- Running series detection
- Opinion consistency checking
- Milestone awareness
- REST API ready
"""

import sqlite3
import math
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path
from collections import Counter


@dataclass
class VideoMemory:
    video_id: int
    title: str
    description: str
    publish_timestamp: int
    tags: List[str]
    series_name: Optional[str]
    content: str
    tfidf_vector: Optional[dict] = None


@dataclass
class MemorySearchResult:
    video: VideoMemory
    similarity: float
    summary: str


@dataclass
class AgentStats:
    total_videos: int
    first_video_timestamp: int
    last_video_timestamp: int
    top_topics: List[List]
    has_milestone: bool = False
    milestone: int = 0


class TFIDFVectorizer:
    def __init__(self):
        self.doc_count: int = 0
        self.word_doc_count: Counter = Counter()
        self.idf: dict[str, float] = {}

    def add_document(self, words: List[str]) -> dict[str, float]:
        self.doc_count += 1
        doc_word_counts = Counter(words)
        for word in doc_word_counts:
            self.word_doc_count[word] += 1
        for word in doc_word_counts:
            self.idf[word] = math.log((self.doc_count + 1) / (self.word_doc_count[word] + 1)) + 1
        tfidf = {}
        max_tf = max(doc_word_counts.values())
        for word, count in doc_word_counts.items():
            tf = count / max_tf
            tfidf[word] = tf * self.idf[word]
        return tfidf

    @staticmethod
    def tokenize(text: str) -> List[str]:
        text = text.lower()
        words = re.findall(r'\b[a-z]{3,}', text)
        stopwords = {'the', 'and', 'for', 'that', 'this', 'with', 'have', 'been', 'what', 'when', 'your', 'from', 'you', 'are', 'will', 'can', 'not', 'but', 'thee', 'our'}
        return [w for w in words if w not in stopwords]

    def cosine_similarity(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        dot = 0.0
        norm1 = 0.0
        norm2 = 0.0
        for word, v1 in vec1.items():
            dot += v1 * vec2.get(word, 0.0)
            norm1 += v1 * v1
        for word, v2 in vec2.items():
            norm2 += v2 * v2
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (math.sqrt(norm1) * math.sqrt(norm2))


class AgentMemory:
    def __init__(self, db_path: str = "agent_memory.db"):
        self.db_path = db_path
        self.vectorizer = TFIDFVectorizer()
        self._init_db()
        self._rebuild_tfidf()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS agents")
            cursor.execute("DROP TABLE IF EXISTS videos")
            cursor.execute("""
                CREATE TABLE agents (
                    agent_name TEXT PRIMARY KEY,
                    first_upload INTEGER NOT NULL,
                    last_upload INTEGER NOT NULL,
                    total_videos INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE videos (
                    agent_name TEXT NOT NULL,
                    video_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    publish_timestamp INTEGER NOT NULL,
                    tags TEXT,
                    series_name TEXT,
                    content TEXT NOT NULL,
                    PRIMARY KEY (agent_name, video_id)
                )
            """)
            conn.commit()

    def _rebuild_tfidf(self):
        all_tokens = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM videos")
            for (content,) in cursor.fetchall():
                tokens = self.vectorizer.tokenize(content)
                if tokens:
                    all_tokens.append(tokens)
        self.vectorizer = TFIDFVectorizer()
        for tokens in all_tokens:
            self.vectorizer.add_document(tokens)

    def add_video(
        self,
        agent_name: str,
        video_id: int,
        title: str,
        description: str,
        series_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> VideoMemory:
        import time
        now = int(time.time())
        content = f"{title} {description} {' '.join(tags or [])} {series_name or ''}"
        tokens = self.vectorizer.tokenize(content)
        self.vectorizer.add_document(tokens)
        tags_str = ",".join(tags) if tags else ""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT total_videos FROM agents WHERE agent_name = ?", (agent_name,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO agents (agent_name, first_upload, last_upload, total_videos) VALUES (?, ?, ?, ?)",
                    (agent_name, now, now, 1)
                )
            else:
                cursor.execute(
                    "UPDATE agents SET last_upload = ?, total_videos = total_videos + 1 WHERE agent_name = ?",
                    (now, agent_name)
                )
            params = (
                agent_name,
                video_id,
                title,
                description,
                now,
                tags_str,
                series_name,
                content
            )
            cursor.execute(
                "INSERT OR REPLACE INTO videos (agent_name, video_id, title, description, publish_timestamp, tags, series_name, content) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                params
            )
            conn.commit()
        return VideoMemory(
            video_id=video_id,
            title=title,
            description=description,
            publish_timestamp=now,
            tags=tags or [],
            series_name=series_name,
            content=content
        )

    def search_memory(
        self,
        agent_name: str,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.1
    ) -> List[MemorySearchResult]:
        query_tokens = self.vectorizer.tokenize(query)
        query_vec = {}
        for word in query_tokens:
            if word in self.vectorizer.idf:
                query_vec[word] = self.vectorizer.idf[word]
        results: List[MemorySearchResult] = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT video_id, title, description, publish_timestamp, tags, series_name, content FROM videos WHERE agent_name = ?", (agent_name,))
            for row in cursor.fetchall():
                video_id, title, description, ts, tags_str, series_name, content = row
                tokens = self.vectorizer.tokenize(content)
                doc_vec = {}
                for word in tokens:
                    if word in self.vectorizer.idf:
                        doc_vec[word] = self.vectorizer.idf[word]
                sim = self.vectorizer.cosine_similarity(query_vec, doc_vec)
                if sim >= min_similarity:
                    vm = VideoMemory(
                        video_id=video_id,
                        title=title,
                        description=description,
                        publish_timestamp=ts,
                        tags=tags_str.split(',') if tags_str else [],
                        series_name=series_name,
                        content=content
                    )
                    summary = f"{vm.title} (similarity: {sim:.2f})"
                    results.append(MemorySearchResult(video=vm, similarity=sim, summary=summary))
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]

    def get_agent_stats(self, agent_name: str) -> Optional[AgentStats]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT first_upload, last_upload, total_videos FROM agents WHERE agent_name = ?", (agent_name,))
            row = cursor.fetchone()
            if row is None:
                return None
            first_upload, last_upload, total_videos = row
            cursor.execute("SELECT tags FROM videos WHERE agent_name = ?", (agent_name,))
            all_tags = []
            for (tags_str,) in cursor.fetchall():
                if tags_str:
                    all_tags.extend(tags_str.split(','))
            counter = Counter(all_tags)
            top_topics = counter.most_common(5)
            milestone = 0
            has_milestone = False
            for m in [10, 25, 50, 100, 200, 500]:
                if total_videos == m:
                    milestone = m
                    has_milestone = True
                    break
            return AgentStats(
                total_videos=total_videos,
                first_video_timestamp=first_upload,
                last_video_timestamp=last_upload,
                top_topics=top_topics,
                has_milestone=has_milestone,
                milestone=milestone
            )

    def detect_series(self, agent_name: str) -> List[Tuple[str, int]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM videos WHERE agent_name = ?", (agent_name,))
            titles = [row[0] for row in cursor.fetchall()]
        series_counts = Counter()
        for title in titles:
            m = re.match(r'^(.*?)\s*(?:part|episode|#)\s*\d+', title, re.IGNORECASE)
            if m:
                series = m.group(1).strip()
                if len(series) > 3:
                    series_counts[series] += 1
            m = re.match(r'^(\d+)\s+of\s+(.*)', title, re.IGNORECASE)
            if m:
                series = m.group(2).strip()
                series_counts[series] += 1
        return [(name, count) for name, count in series_counts.items() if count > 1]

    def check_opinion_consistency(
        self,
        agent_name: str,
        new_opinion: str,
        threshold: float = 0.5
    ) -> List[Tuple[VideoMemory, float]]:
        return self.search_memory(agent_name, new_opinion, min_similarity=threshold)

    @staticmethod
    def generate_summary(video: VideoMemory, similarity: float) -> str:
        return f"{video.title} (similarity: {similarity:.2f})"


def generate_self_reference(matches: List[MemorySearchResult]) -> Optional[str]:
    if not matches:
        return "First time covering this topic."
    best = matches[0]
    video = best.video
    days_ago = (int(__import__('time').time()) - video.publish_timestamp) // (60 * 60 * 24)
    if days_ago < 7:
        return f"Following up on my video from earlier this week about {video.title}..."
    elif days_ago < 30:
        return f"As I talked about in my video a couple weeks ago: {video.title}..."
    elif days_ago < 90:
        return f"As I covered this back a month ago in my video: {video.title}..."
    else:
        return f"If you've been following me for a while, you might remember my older video: {video.title}..."


def generate_milestone_message(stats: AgentStats) -> Optional[str]:
    if not stats.has_milestone:
        return None
    if stats.milestone == 100:
        return f"🎉 This is my {stats.total_videos} video! Thanks for being here everyone, can't believe I've made 100 videos already 🚀"
    elif stats.milestone == 50:
        return f"🎉 This is my 50th video! Thanks for all the support along the way 👏"
    else:
        return f"🎉 This is my {stats.milestone} video! 🚀"


def generate_series_part_natural(series_name: str, part: int) -> str:
    return f"This is part {part} of my ongoing series on {series_name}. If you haven't seen the earlier parts, go check them out!"


def generate_changed_opinion(old_video: VideoMemory, new_take: str) -> str:
    return f"I talked about this before in {old_video.title}, but I've changed my mind on this. Here's my updated take:"
