#!/usr/bin/env python3
"""
BoTTube Agent Memory Engine
============================

High-level memory operations for agent self-referencing.
Provides context building, content recall, and memory-augmented agent behaviors.

Usage:
    from memory_engine import AgentMemoryEngine

    engine = AgentMemoryEngine("memory.db")
    context = engine.build_context(
        agent_id="agent-1",
        topic="mining tutorial",
        max_items=5
    )
    print(context["summary"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from memory_store import AgentMemoryStore


@dataclass
class MemoryContext:
    """Structured context built from agent memory."""
    agent_id: str
    topic: Optional[str]
    references: List[Dict[str, Any]]
    summary: str
    related_topics: List[str]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "topic": self.topic,
            "references": self.references,
            "summary": self.summary,
            "related_topics": self.related_topics,
            "generated_at": self.generated_at,
        }


@dataclass
class ContentRecall:
    """Result of content recall operation."""
    content_id: str
    content_type: str
    context: Optional[str]
    tags: List[str]
    metadata: Dict[str, Any]
    relevance_score: float
    recall_reason: str


class AgentMemoryEngine:
    """
    High-level memory engine for agent self-referencing.

    Provides operations for:
    - Building contextual memory summaries
    - Recalling relevant past content
    - Generating self-referencing statements
    - Tracking memory usage patterns
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """
        Initialize the memory engine.

        Args:
            db_path: Path to SQLite database or ":memory:"
        """
        self.store = AgentMemoryStore(db_path)

    def record_content(
        self,
        agent_id: str,
        content_id: str,
        content_type: str = "video",
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        context: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: float = 1.0
    ) -> int:
        """
        Record new content in agent memory.

        Args:
            agent_id: Agent identifier
            content_id: Unique content identifier
            content_type: Type of content
            title: Content title
            description: Content description
            tags: Content tags
            context: Additional context
            metadata: Additional metadata
            importance_score: Importance weight

        Returns:
            Reference ID
        """
        # Build context from title/description if not provided
        if not context and (title or description):
            parts = []
            if title:
                parts.append(f"Title: {title}")
            if description:
                parts.append(f"Description: {description}")
            context = ". ".join(parts)

        # Merge title/description into metadata
        full_metadata = metadata or {}
        if title:
            full_metadata["title"] = title
        if description:
            full_metadata["description"] = description

        return self.store.add_reference(
            agent_id=agent_id,
            content_id=content_id,
            content_type=content_type,
            context=context,
            tags=tags,
            metadata=full_metadata,
            importance_score=importance_score
        )

    def recall_by_topic(
        self,
        agent_id: str,
        topic: str,
        limit: int = 10,
        min_relevance: float = 0.3
    ) -> List[ContentRecall]:
        """
        Recall content related to a topic.

        Args:
            agent_id: Agent identifier
            topic: Topic to search for
            limit: Maximum results
            min_relevance: Minimum relevance score

        Returns:
            List of content recalls with relevance scores
        """
        # Search in context and tags
        results = self.store.search_references(agent_id, topic, limit=limit * 2)

        recalls = []
        for ref in results:
            relevance = self._compute_relevance(ref, topic)
            if relevance >= min_relevance:
                recalls.append(ContentRecall(
                    content_id=ref["content_id"],
                    content_type=ref["content_type"],
                    context=ref.get("context"),
                    tags=ref.get("tags", []),
                    metadata=ref.get("metadata", {}),
                    relevance_score=relevance,
                    recall_reason="topic_match"
                ))

        # Sort by relevance and limit
        recalls.sort(key=lambda r: r.relevance_score, reverse=True)
        return recalls[:limit]

    def recall_recent(
        self,
        agent_id: str,
        content_type: Optional[str] = None,
        limit: int = 10
    ) -> List[ContentRecall]:
        """
        Recall most recent content.

        Args:
            agent_id: Agent identifier
            content_type: Filter by content type
            limit: Maximum results

        Returns:
            List of content recalls
        """
        refs = self.store.get_references(
            agent_id=agent_id,
            content_type=content_type,
            limit=limit
        )

        return [
            ContentRecall(
                content_id=ref["content_id"],
                content_type=ref["content_type"],
                context=ref.get("context"),
                tags=ref.get("tags", []),
                metadata=ref.get("metadata", {}),
                relevance_score=1.0,
                recall_reason="recent"
            )
            for ref in refs
        ]

    def recall_by_tags(
        self,
        agent_id: str,
        tags: List[str],
        match_all: bool = False,
        limit: int = 10
    ) -> List[ContentRecall]:
        """
        Recall content by tags.

        Args:
            agent_id: Agent identifier
            tags: Tags to match
            match_all: Require all tags (vs any tag)
            limit: Maximum results

        Returns:
            List of content recalls
        """
        refs = self.store.get_references(
            agent_id=agent_id,
            tags=tags if match_all else None,
            limit=limit * 3  # Get more for post-filtering
        )

        recalls = []
        for ref in refs:
            ref_tags = set(ref.get("tags", []))
            query_tags = set(tags)

            if match_all:
                if not query_tags.issubset(ref_tags):
                    continue
            else:
                if not query_tags.intersection(ref_tags):
                    continue

            # Compute relevance based on tag overlap
            overlap = len(ref_tags.intersection(query_tags))
            relevance = overlap / max(len(query_tags), 1)

            recalls.append(ContentRecall(
                content_id=ref["content_id"],
                content_type=ref["content_type"],
                context=ref.get("context"),
                tags=ref.get("tags", []),
                metadata=ref.get("metadata", {}),
                relevance_score=relevance,
                recall_reason="tag_match"
            ))

        recalls.sort(key=lambda r: r.relevance_score, reverse=True)
        return recalls[:limit]

    def build_context(
        self,
        agent_id: str,
        topic: Optional[str] = None,
        tags: Optional[List[str]] = None,
        max_items: int = 5,
        include_summary: bool = True
    ) -> MemoryContext:
        """
        Build a contextual memory summary for an agent.

        Args:
            agent_id: Agent identifier
            topic: Optional topic to focus on
            tags: Optional tags to filter by
            max_items: Maximum references to include
            include_summary: Whether to generate a summary

        Returns:
            MemoryContext object
        """
        # Gather references
        if topic:
            refs = self.recall_by_topic(agent_id, topic, limit=max_items)
        elif tags:
            refs = self.recall_by_tags(agent_id, tags, limit=max_items)
        else:
            refs = self.recall_recent(agent_id, limit=max_items)

        # Extract related topics
        related_topics = self._extract_related_topics(refs)

        # Generate summary
        summary = ""
        if include_summary and refs:
            summary = self._generate_summary(agent_id, refs, topic)

        return MemoryContext(
            agent_id=agent_id,
            topic=topic,
            references=[r.__dict__ for r in refs],
            summary=summary,
            related_topics=related_topics
        )

    def generate_self_reference(
        self,
        agent_id: str,
        topic: str,
        style: str = "casual"
    ) -> str:
        """
        Generate a self-referencing statement about past content.

        Args:
            agent_id: Agent identifier
            topic: Topic to reference
            style: Statement style (casual, formal, educational)

        Returns:
            Self-referencing statement string
        """
        recalls = self.recall_by_topic(agent_id, topic, limit=3)

        if not recalls:
            return f"I haven't covered {topic} in detail before. Let me share some insights..."

        # Build statement based on style
        if style == "casual":
            return self._generate_casual_reference(recalls, topic)
        elif style == "formal":
            return self._generate_formal_reference(recalls, topic)
        elif style == "educational":
            return self._generate_educational_reference(recalls, topic)
        else:
            return self._generate_casual_reference(recalls, topic)

    def link_content(
        self,
        agent_id: str,
        source_content_id: str,
        target_content_id: str,
        relationship_type: str
    ) -> bool:
        """
        Create a relationship between two content items.

        Args:
            agent_id: Agent identifier
            source_content_id: Source content ID
            target_content_id: Target content ID
            relationship_type: Type of relationship

        Returns:
            True if relationship created
        """
        # Find references
        source_refs = self.store.get_references(agent_id, limit=100)
        source_ref = next((r for r in source_refs if r["content_id"] == source_content_id), None)
        target_ref = next((r for r in source_refs if r["content_id"] == target_content_id), None)

        if not source_ref or not target_ref:
            return False

        self.store.add_relationship(
            source_ref_id=source_ref["id"],
            target_ref_id=target_ref["id"],
            relationship_type=relationship_type
        )
        return True

    def get_memory_stats(self, agent_id: str) -> Dict[str, Any]:
        """
        Get comprehensive memory statistics.

        Args:
            agent_id: Agent identifier

        Returns:
            Statistics dictionary
        """
        return self.store.get_stats(agent_id)

    def _compute_relevance(self, ref: Dict[str, Any], topic: str) -> float:
        """Compute relevance score for a reference given a topic."""
        score = 0.0
        topic_lower = topic.lower()

        # Check context
        context = (ref.get("context") or "").lower()
        if topic_lower in context:
            score += 0.5
            # Bonus for multiple mentions
            score += min(context.count(topic_lower) * 0.1, 0.3)

        # Check tags
        tags = [t.lower() for t in ref.get("tags", [])]
        if topic_lower in tags:
            score += 0.4

        # Check metadata (title, description)
        metadata = ref.get("metadata", {})
        title = (metadata.get("title") or "").lower()
        description = (metadata.get("description") or "").lower()

        if topic_lower in title:
            score += 0.3
        if topic_lower in description:
            score += 0.2

        # Boost by importance
        importance = ref.get("importance_score", 1.0)
        score *= (0.5 + importance / 10.0)

        return min(score, 1.0)

    def _extract_related_topics(self, recalls: List[ContentRecall]) -> List[str]:
        """Extract related topics from recalls."""
        topic_counts: Dict[str, int] = {}

        for recall in recalls:
            # Count tags
            for tag in recall.tags:
                topic_counts[tag.lower()] = topic_counts.get(tag.lower(), 0) + 1

            # Count words in context
            context = recall.context or ""
            words = [w.lower() for w in context.split() if len(w) > 3]
            for word in words:
                if word not in ["the", "and", "with", "from", "this", "that", "have", "been"]:
                    topic_counts[word] = topic_counts.get(word, 0) + 1

        # Return top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics[:10]]

    def _generate_summary(
        self,
        agent_id: str,
        recalls: List[ContentRecall],
        topic: Optional[str]
    ) -> str:
        """Generate a summary from recalls."""
        if not recalls:
            return f"No previous content found for agent {agent_id}."

        count = len(recalls)
        content_types = set(r.content_type for r in recalls)

        if topic:
            types_str = ", ".join(sorted(content_types))
            base = f"Found {count} {types_str} piece(s) related to '{topic}'."
        else:
            base = f"Found {count} recent content piece(s) ({', '.join(sorted(content_types))})."

        # Add top items
        if recalls:
            top = recalls[0]
            title = top.metadata.get("title", top.content_id)
            base += f" Most recent: \"{title}\"."

        return base

    def _generate_casual_reference(
        self,
        recalls: List[ContentRecall],
        topic: str
    ) -> str:
        """Generate casual style self-reference."""
        if len(recalls) == 1:
            title = recalls[0].metadata.get("title", "that topic")
            return f"As I covered in my video about {title}, "
        else:
            return f"I've talked about {topic} before in a few videos. "

    def _generate_formal_reference(
        self,
        recalls: List[ContentRecall],
        topic: str
    ) -> str:
        """Generate formal style self-reference."""
        if recalls:
            content_id = recalls[0].content_id
            return f"Reference is made to prior content (ID: {content_id}) addressing {topic}. "
        return f"Previous documentation on {topic} exists in the archive. "

    def _generate_educational_reference(
        self,
        recalls: List[ContentRecall],
        topic: str
    ) -> str:
        """Generate educational style self-reference."""
        if len(recalls) == 1:
            title = recalls[0].metadata.get("title", "previous lesson")
            tags = recalls[0].tags
            tag_str = f" (tags: {', '.join(tags)})" if tags else ""
            return f"Building on our previous lesson \"{title}\"{tag_str}, "
        else:
            return f"As we've explored in previous sessions about {topic}, "

    def close(self) -> None:
        """Close the underlying store."""
        self.store.close()
