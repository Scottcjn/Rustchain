#!/usr/bin/env python3
"""
BoTTube Agent Memory Store
===========================

SQLite-backed persistent storage for agent content references.
Enables agents to self-reference their past content (videos, interactions, metadata).

Usage:
    from memory_store import AgentMemoryStore

    store = AgentMemoryStore("memory.db")
    store.add_reference(agent_id="agent-1", content_id="video-123", context="tutorial")
    refs = store.get_references(agent_id="agent-1", limit=10)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class AgentMemoryStore:
    """
    Persistent storage for agent content references.

    Stores structured references to past content that agents can query
    to build self-referencing context (e.g., "in my previous video about X...").
    """

    DEFAULT_SCHEMA_VERSION = "1.0.0"

    def __init__(self, db_path: str = ":memory:") -> None:
        """
        Initialize the memory store.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory store
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Schema version tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)

        # Main memory references table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                content_id TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'video',
                context TEXT,
                tags TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 1.0,
                is_public INTEGER DEFAULT 1
            )
        """)

        # Index for efficient agent-based queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_content
            ON memory_references(agent_id, content_type, created_at DESC)
        """)

        # Index for tag-based queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tags
            ON memory_references(agent_id, tags)
        """)

        # Index for importance-based retrieval
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_importance
            ON memory_references(agent_id, importance_score DESC)
        """)

        # Content relationships table (for linking related content)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_ref_id INTEGER NOT NULL,
                target_ref_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_ref_id) REFERENCES memory_references(id) ON DELETE CASCADE,
                FOREIGN KEY (target_ref_id) REFERENCES memory_references(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationships
            ON memory_relationships(source_ref_id, target_ref_id)
        """)

        # Initialize schema version if not exists
        cursor.execute("SELECT version FROM _schema_version WHERE id = 1")
        if not cursor.fetchone():
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO _schema_version (id, version, applied_at) VALUES (1, ?, ?)",
                (self.DEFAULT_SCHEMA_VERSION, now)
            )

        conn.commit()

    def add_reference(
        self,
        agent_id: str,
        content_id: str,
        content_type: str = "video",
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: float = 1.0,
        is_public: bool = True
    ) -> int:
        """
        Add a content reference to agent memory.

        Args:
            agent_id: Unique identifier for the agent
            content_id: Unique identifier for the content (e.g., video ID)
            content_type: Type of content (video, article, podcast, etc.)
            context: Optional context description for the reference
            tags: Optional list of tags for categorization
            metadata: Optional additional metadata dictionary
            importance_score: Importance weight (0.0-10.0, default 1.0)
            is_public: Whether this reference is publicly visible

        Returns:
            The ID of the newly created reference
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags) if tags else "[]"
        metadata_json = json.dumps(metadata) if metadata else "{}"

        cursor.execute("""
            INSERT INTO memory_references
            (agent_id, content_id, content_type, context, tags, metadata,
             created_at, updated_at, importance_score, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_id, content_id, content_type, context,
            tags_json, metadata_json, now, now,
            min(max(importance_score, 0.0), 10.0),  # Clamp to 0-10
            1 if is_public else 0
        ))

        conn.commit()
        return cursor.lastrowid

    def get_reference(self, ref_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single reference by ID.

        Args:
            ref_id: Reference ID

        Returns:
            Reference dictionary or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM memory_references WHERE id = ?
        """, (ref_id,))

        row = cursor.fetchone()
        if not row:
            return None

        # Increment access count
        cursor.execute("""
            UPDATE memory_references SET access_count = access_count + 1,
            updated_at = ? WHERE id = ?
        """, (datetime.now(timezone.utc).isoformat(), ref_id))
        conn.commit()

        return self._row_to_dict(row)

    def get_references(
        self,
        agent_id: str,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0,
        min_importance: float = 0.0,
        include_public_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve references for an agent.

        Args:
            agent_id: Agent identifier
            content_type: Filter by content type
            tags: Filter by tags (must have ALL specified tags)
            limit: Maximum number of results
            offset: Pagination offset
            min_importance: Minimum importance score
            include_public_only: Only return public references

        Returns:
            List of reference dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM memory_references WHERE agent_id = ?"
        params: List[Any] = [agent_id]

        if content_type:
            query += " AND content_type = ?"
            params.append(content_type)

        if include_public_only:
            query += " AND is_public = 1"

        if min_importance > 0:
            query += " AND importance_score >= ?"
            params.append(min_importance)

        query += " ORDER BY importance_score DESC, created_at DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = [self._row_to_dict(row) for row in rows]

        # Filter by tags if specified (post-filter for JSON array)
        if tags:
            results = [
                r for r in results
                if all(tag in r.get("tags", []) for tag in tags)
            ]

        return results

    def search_references(
        self,
        agent_id: str,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search references by context/content.

        Args:
            agent_id: Agent identifier
            query: Search query string
            limit: Maximum results

        Returns:
            List of matching references
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        search_pattern = f"%{query}%"
        cursor.execute("""
            SELECT * FROM memory_references
            WHERE agent_id = ?
              AND is_public = 1
              AND (context LIKE ? OR content_id LIKE ?)
            ORDER BY importance_score DESC, created_at DESC
            LIMIT ?
        """, (agent_id, search_pattern, search_pattern, limit))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def update_reference(
        self,
        ref_id: int,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: Optional[float] = None,
        is_public: Optional[bool] = None
    ) -> bool:
        """
        Update a reference.

        Args:
            ref_id: Reference ID
            context: New context (optional)
            tags: New tags (optional)
            metadata: New metadata (optional)
            importance_score: New importance score (optional)
            is_public: New visibility setting (optional)

        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        updates = []
        params: List[Any] = []

        if context is not None:
            updates.append("context = ?")
            params.append(context)

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if importance_score is not None:
            updates.append("importance_score = ?")
            params.append(min(max(importance_score, 0.0), 10.0))

        if is_public is not None:
            updates.append("is_public = ?")
            params.append(1 if is_public else 0)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(ref_id)

        cursor.execute(f"""
            UPDATE memory_references SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()
        return cursor.rowcount > 0

    def delete_reference(self, ref_id: int) -> bool:
        """
        Delete a reference.

        Args:
            ref_id: Reference ID

        Returns:
            True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Delete associated relationships first
        cursor.execute("""
            DELETE FROM memory_relationships
            WHERE source_ref_id = ? OR target_ref_id = ?
        """, (ref_id, ref_id))

        cursor.execute("""
            DELETE FROM memory_references WHERE id = ?
        """, (ref_id,))

        conn.commit()
        return cursor.rowcount > 0

    def add_relationship(
        self,
        source_ref_id: int,
        target_ref_id: int,
        relationship_type: str
    ) -> int:
        """
        Add a relationship between two references.

        Args:
            source_ref_id: Source reference ID
            target_ref_id: Target reference ID
            relationship_type: Type of relationship (e.g., "sequel", "part-of", "references")

        Returns:
            Relationship ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO memory_relationships
            (source_ref_id, target_ref_id, relationship_type, created_at)
            VALUES (?, ?, ?, ?)
        """, (source_ref_id, target_ref_id, relationship_type, now))

        conn.commit()
        return cursor.lastrowid

    def get_related_references(
        self,
        ref_id: int,
        relationship_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get references related to a given reference.

        Args:
            ref_id: Reference ID
            relationship_type: Filter by relationship type
            limit: Maximum results

        Returns:
            List of related references
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if relationship_type:
            cursor.execute("""
                SELECT mr.* FROM memory_references mr
                JOIN memory_relationships rel ON mr.id = rel.target_ref_id
                WHERE rel.source_ref_id = ? AND rel.relationship_type = ?
                LIMIT ?
            """, (ref_id, relationship_type, limit))
        else:
            cursor.execute("""
                SELECT mr.* FROM memory_references mr
                JOIN memory_relationships rel ON mr.id = rel.target_ref_id
                WHERE rel.source_ref_id = ?
                LIMIT ?
            """, (ref_id, limit))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_stats(self, agent_id: str) -> Dict[str, Any]:
        """
        Get memory statistics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Statistics dictionary
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total references
        cursor.execute("""
            SELECT COUNT(*) as count FROM memory_references
            WHERE agent_id = ? AND is_public = 1
        """, (agent_id,))
        total = cursor.fetchone()["count"]

        # By content type
        cursor.execute("""
            SELECT content_type, COUNT(*) as count
            FROM memory_references
            WHERE agent_id = ? AND is_public = 1
            GROUP BY content_type
        """, (agent_id,))
        by_type = {row["content_type"]: row["count"] for row in cursor.fetchall()}

        # Average importance
        cursor.execute("""
            SELECT AVG(importance_score) as avg_score
            FROM memory_references
            WHERE agent_id = ? AND is_public = 1
        """, (agent_id,))
        avg_importance = cursor.fetchone()["avg_score"] or 0.0

        # Total relationships
        cursor.execute("""
            SELECT COUNT(*) as count FROM memory_relationships rel
            JOIN memory_references mr ON rel.source_ref_id = mr.id
            WHERE mr.agent_id = ?
        """, (agent_id,))
        total_relationships = cursor.fetchone()["count"]

        return {
            "agent_id": agent_id,
            "total_references": total,
            "by_content_type": by_type,
            "average_importance": round(avg_importance, 2),
            "total_relationships": total_relationships,
        }

    def clear_agent_memory(self, agent_id: str) -> int:
        """
        Clear all memory for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Number of references deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get all reference IDs first
        cursor.execute("""
            SELECT id FROM memory_references WHERE agent_id = ?
        """, (agent_id,))
        ref_ids = [row["id"] for row in cursor.fetchall()]

        # Delete relationships
        for ref_id in ref_ids:
            cursor.execute("""
                DELETE FROM memory_relationships
                WHERE source_ref_id = ? OR target_ref_id = ?
            """, (ref_id, ref_id))

        # Delete references
        cursor.execute("""
            DELETE FROM memory_references WHERE agent_id = ?
        """, (agent_id,))

        conn.commit()
        return len(ref_ids)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        data = dict(row)
        # Parse JSON fields
        data["tags"] = json.loads(data.get("tags") or "[]")
        data["metadata"] = json.loads(data.get("metadata") or "{}")
        data["is_public"] = bool(data.get("is_public", 1))
        return data

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
