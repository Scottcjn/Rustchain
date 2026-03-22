#!/usr/bin/env python3
"""
Tests for BoTTube Agent Memory System
======================================

Run with:
    python -m pytest tests/test_memory.py -v
    python tests/test_memory.py

Covers:
- memory_store: AgentMemoryStore tests
- memory_engine: AgentMemoryEngine tests
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory_store import AgentMemoryStore
from memory_engine import AgentMemoryEngine, MemoryContext, ContentRecall


class TestAgentMemoryStore(unittest.TestCase):
    """Test AgentMemoryStore functionality."""

    def setUp(self) -> None:
        """Set up in-memory store for each test."""
        self.store = AgentMemoryStore(":memory:")

    def tearDown(self) -> None:
        """Clean up."""
        self.store.close()

    def test_add_reference(self) -> None:
        """Test adding a reference."""
        ref_id = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001",
            content_type="video",
            context="Tutorial on mining",
            tags=["mining", "tutorial"],
            importance_score=2.5
        )
        self.assertIsInstance(ref_id, int)
        self.assertGreater(ref_id, 0)

    def test_get_reference(self) -> None:
        """Test retrieving a reference by ID."""
        ref_id = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001",
            content_type="video",
            tags=["test"]
        )

        ref = self.store.get_reference(ref_id)
        self.assertIsNotNone(ref)
        self.assertEqual(ref["content_id"], "video-001")
        self.assertEqual(ref["agent_id"], "test-agent")
        self.assertEqual(ref["tags"], ["test"])

    def test_get_reference_not_found(self) -> None:
        """Test retrieving non-existent reference."""
        ref = self.store.get_reference(99999)
        self.assertIsNone(ref)

    def test_get_references_by_agent(self) -> None:
        """Test getting references filtered by agent."""
        # Add multiple references
        for i in range(5):
            self.store.add_reference(
                agent_id="agent-a",
                content_id=f"video-{i}",
                tags=["test"]
            )

        # Add references for different agent
        self.store.add_reference(
            agent_id="agent-b",
            content_id="video-other",
            tags=["test"]
        )

        refs = self.store.get_references("agent-a", limit=10)
        self.assertEqual(len(refs), 5)

    def test_get_references_by_content_type(self) -> None:
        """Test filtering by content type."""
        self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001",
            content_type="video"
        )
        self.store.add_reference(
            agent_id="test-agent",
            content_id="article-001",
            content_type="article"
        )

        video_refs = self.store.get_references("test-agent", content_type="video")
        self.assertEqual(len(video_refs), 1)
        self.assertEqual(video_refs[0]["content_type"], "video")

    def test_get_references_by_tags(self) -> None:
        """Test filtering by tags."""
        self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001",
            tags=["mining", "tutorial", "beginner"]
        )
        self.store.add_reference(
            agent_id="test-agent",
            content_id="video-002",
            tags=["mining", "advanced"]
        )

        # Filter by single tag
        refs = self.store.get_references("test-agent", tags=["tutorial"])
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["content_id"], "video-001")

    def test_get_references_limit(self) -> None:
        """Test limit is applied."""
        for i in range(20):
            self.store.add_reference(
                agent_id="test-agent",
                content_id=f"video-{i}",
                tags=["test"]
            )

        refs = self.store.get_references("test-agent", limit=10)
        self.assertEqual(len(refs), 10)

    def test_search_references(self) -> None:
        """Test searching references by context."""
        self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001",
            context="Introduction to RustChain mining setup"
        )
        self.store.add_reference(
            agent_id="test-agent",
            content_id="video-002",
            context="Advanced optimization techniques"
        )

        results = self.store.search_references("test-agent", "mining")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["content_id"], "video-001")

    def test_update_reference(self) -> None:
        """Test updating a reference."""
        ref_id = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001",
            tags=["old-tag"],
            importance_score=1.0
        )

        updated = self.store.update_reference(
            ref_id=ref_id,
            tags=["new-tag", "updated"],
            importance_score=5.0
        )
        self.assertTrue(updated)

        ref = self.store.get_reference(ref_id)
        self.assertEqual(ref["tags"], ["new-tag", "updated"])
        self.assertEqual(ref["importance_score"], 5.0)

    def test_delete_reference(self) -> None:
        """Test deleting a reference."""
        ref_id = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001"
        )

        deleted = self.store.delete_reference(ref_id)
        self.assertTrue(deleted)

        ref = self.store.get_reference(ref_id)
        self.assertIsNone(ref)

    def test_add_relationship(self) -> None:
        """Test adding relationship between references."""
        ref1 = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001"
        )
        ref2 = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-002"
        )

        rel_id = self.store.add_relationship(ref1, ref2, "sequel")
        self.assertIsInstance(rel_id, int)

    def test_get_related_references(self) -> None:
        """Test getting related references."""
        ref1 = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001"
        )
        ref2 = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-002"
        )
        ref3 = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-003"
        )

        self.store.add_relationship(ref1, ref2, "sequel")
        self.store.add_relationship(ref1, ref3, "related")

        related = self.store.get_related_references(ref1)
        self.assertEqual(len(related), 2)

        sequel_related = self.store.get_related_references(ref1, relationship_type="sequel")
        self.assertEqual(len(sequel_related), 1)
        self.assertEqual(sequel_related[0]["content_id"], "video-002")

    def test_get_stats(self) -> None:
        """Test getting memory statistics."""
        for i in range(3):
            self.store.add_reference(
                agent_id="test-agent",
                content_id=f"video-{i}",
                content_type="video",
                importance_score=2.0
            )

        for i in range(2):
            self.store.add_reference(
                agent_id="test-agent",
                content_id=f"article-{i}",
                content_type="article",
                importance_score=3.0
            )

        stats = self.store.get_stats("test-agent")

        self.assertEqual(stats["total_references"], 5)
        self.assertEqual(stats["by_content_type"]["video"], 3)
        self.assertEqual(stats["by_content_type"]["article"], 2)
        self.assertAlmostEqual(stats["average_importance"], 2.4, places=1)

    def test_clear_agent_memory(self) -> None:
        """Test clearing all agent memory."""
        for i in range(10):
            self.store.add_reference(
                agent_id="test-agent",
                content_id=f"video-{i}"
            )

        deleted = self.store.clear_agent_memory("test-agent")
        self.assertEqual(deleted, 10)

        refs = self.store.get_references("test-agent")
        self.assertEqual(len(refs), 0)

    def test_importance_score_clamping(self) -> None:
        """Test that importance scores are clamped to 0-10 range."""
        ref_id_low = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-low",
            importance_score=-5.0
        )
        ref_id_high = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-high",
            importance_score=100.0
        )

        ref_low = self.store.get_reference(ref_id_low)
        ref_high = self.store.get_reference(ref_id_high)

        self.assertEqual(ref_low["importance_score"], 0.0)
        self.assertEqual(ref_high["importance_score"], 10.0)

    def test_public_private_filtering(self) -> None:
        """Test public/private reference filtering."""
        self.store.add_reference(
            agent_id="test-agent",
            content_id="video-public",
            is_public=True
        )
        self.store.add_reference(
            agent_id="test-agent",
            content_id="video-private",
            is_public=False
        )

        refs = self.store.get_references("test-agent", include_public_only=True)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["content_id"], "video-public")

    def test_json_metadata_parsing(self) -> None:
        """Test that JSON fields are properly parsed."""
        ref_id = self.store.add_reference(
            agent_id="test-agent",
            content_id="video-001",
            tags=["tag1", "tag2"],
            metadata={"key": "value", "number": 42}
        )

        ref = self.store.get_reference(ref_id)
        self.assertIsInstance(ref["tags"], list)
        self.assertEqual(ref["tags"], ["tag1", "tag2"])
        self.assertIsInstance(ref["metadata"], dict)
        self.assertEqual(ref["metadata"]["key"], "value")
        self.assertEqual(ref["metadata"]["number"], 42)


class TestAgentMemoryEngine(unittest.TestCase):
    """Test AgentMemoryEngine functionality."""

    def setUp(self) -> None:
        """Set up engine for each test."""
        self.engine = AgentMemoryEngine(":memory:")

    def tearDown(self) -> None:
        """Clean up."""
        self.engine.close()

    def test_record_content(self) -> None:
        """Test recording content."""
        ref_id = self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            content_type="video",
            title="Mining Tutorial",
            description="Learn how to mine",
            tags=["mining", "tutorial"]
        )
        self.assertIsInstance(ref_id, int)

    def test_record_content_builds_context(self) -> None:
        """Test that context is built from title/description."""
        ref_id = self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Test Title",
            description="Test Description"
        )

        ref = self.engine.store.get_reference(ref_id)
        self.assertIn("Title: Test Title", ref["context"])
        self.assertIn("Description: Test Description", ref["context"])

    def test_recall_by_topic(self) -> None:
        """Test recalling content by topic."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="RustChain Mining Guide",
            context="Complete guide to mining on RustChain",
            tags=["mining", "rustchain"]
        )
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-002",
            title="Cooking Basics",
            context="Learn to cook delicious meals",
            tags=["cooking"]
        )

        recalls = self.engine.recall_by_topic("test-agent", "mining")
        self.assertEqual(len(recalls), 1)
        self.assertEqual(recalls[0].content_id, "video-001")
        self.assertGreater(recalls[0].relevance_score, 0)

    def test_recall_recent(self) -> None:
        """Test recalling recent content."""
        for i in range(5):
            self.engine.record_content(
                agent_id="test-agent",
                content_id=f"video-{i}",
                title=f"Video {i}"
            )

        recalls = self.engine.recall_recent("test-agent", limit=3)
        self.assertEqual(len(recalls), 3)

    def test_recall_by_tags(self) -> None:
        """Test recalling content by tags."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            tags=["mining", "tutorial", "beginner"]
        )
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-002",
            tags=["mining", "advanced"]
        )

        recalls = self.engine.recall_by_tags("test-agent", ["tutorial"])
        self.assertEqual(len(recalls), 1)
        self.assertEqual(recalls[0].content_id, "video-001")

    def test_recall_by_tags_match_all(self) -> None:
        """Test recalling content requiring all tags."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            tags=["mining", "tutorial"]
        )
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-002",
            tags=["mining", "cooking"]
        )

        # Match all: should only return video-001
        recalls = self.engine.recall_by_tags(
            "test-agent", ["mining", "tutorial"], match_all=True
        )
        self.assertEqual(len(recalls), 1)

    def test_build_context(self) -> None:
        """Test building memory context."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Mining Part 1",
            tags=["mining", "series"]
        )
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-002",
            title="Mining Part 2",
            tags=["mining", "series"]
        )

        context = self.engine.build_context(
            agent_id="test-agent",
            topic="mining",
            max_items=5
        )

        self.assertIsInstance(context, MemoryContext)
        self.assertEqual(context.agent_id, "test-agent")
        self.assertEqual(context.topic, "mining")
        self.assertGreater(len(context.references), 0)
        self.assertIn("mining", context.summary.lower())
        self.assertIn("mining", context.related_topics)

    def test_build_context_no_topic(self) -> None:
        """Test building context without specific topic."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Recent Video"
        )

        context = self.engine.build_context(
            agent_id="test-agent",
            max_items=5
        )

        self.assertEqual(context.agent_id, "test-agent")
        self.assertIsNone(context.topic)
        self.assertGreater(len(context.references), 0)

    def test_generate_self_reference_casual(self) -> None:
        """Test generating casual self-reference."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Mining Basics",
            tags=["mining"]
        )

        statement = self.engine.generate_self_reference(
            agent_id="test-agent",
            topic="mining",
            style="casual"
        )

        self.assertIsInstance(statement, str)
        self.assertGreater(len(statement), 0)

    def test_generate_self_reference_formal(self) -> None:
        """Test generating formal self-reference."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Mining Basics"
        )

        statement = self.engine.generate_self_reference(
            agent_id="test-agent",
            topic="mining",
            style="formal"
        )

        self.assertIsInstance(statement, str)
        self.assertIn("video-001", statement)

    def test_generate_self_reference_educational(self) -> None:
        """Test generating educational self-reference."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Mining Lesson",
            tags=["educational"]
        )

        statement = self.engine.generate_self_reference(
            agent_id="test-agent",
            topic="mining",
            style="educational"
        )

        self.assertIsInstance(statement, str)
        self.assertIn("Mining Lesson", statement)

    def test_generate_self_reference_no_content(self) -> None:
        """Test generating reference when no content exists."""
        statement = self.engine.generate_self_reference(
            agent_id="test-agent",
            topic="unknown-topic"
        )

        self.assertIn("haven't covered", statement.lower())

    def test_link_content(self) -> None:
        """Test linking content items."""
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Part 1"
        )
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-002",
            title="Part 2"
        )

        success = self.engine.link_content(
            agent_id="test-agent",
            source_content_id="video-001",
            target_content_id="video-002",
            relationship_type="sequel"
        )
        self.assertTrue(success)

    def test_link_content_not_found(self) -> None:
        """Test linking non-existent content."""
        success = self.engine.link_content(
            agent_id="test-agent",
            source_content_id="nonexistent-1",
            target_content_id="nonexistent-2",
            relationship_type="sequel"
        )
        self.assertFalse(success)

    def test_get_memory_stats(self) -> None:
        """Test getting comprehensive stats."""
        for i in range(3):
            self.engine.record_content(
                agent_id="test-agent",
                content_id=f"video-{i}",
                content_type="video"
            )

        stats = self.engine.get_memory_stats("test-agent")

        self.assertEqual(stats["agent_id"], "test-agent")
        self.assertEqual(stats["total_references"], 3)

    def test_relevance_computation(self) -> None:
        """Test relevance score computation."""
        # High relevance: topic in title
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-001",
            title="Complete Mining Guide",
            context="Everything about mining"
        )

        # Lower relevance: topic only in context
        self.engine.record_content(
            agent_id="test-agent",
            content_id="video-002",
            title="Random Video",
            context="Briefly mentioned mining once"
        )

        recalls = self.engine.recall_by_topic("test-agent", "mining", limit=5)

        # video-001 should have higher relevance
        mining_video = next(r for r in recalls if r.content_id == "video-001")
        random_video = next(r for r in recalls if r.content_id == "video-002")

        self.assertGreater(mining_video.relevance_score, random_video.relevance_score)

    def test_memory_context_to_dict(self) -> None:
        """Test MemoryContext serialization."""
        context = MemoryContext(
            agent_id="test-agent",
            topic="test",
            references=[],
            summary="Test summary",
            related_topics=["topic1"]
        )

        data = context.to_dict()
        self.assertEqual(data["agent_id"], "test-agent")
        self.assertEqual(data["topic"], "test")
        self.assertEqual(data["summary"], "Test summary")
        self.assertIn("generated_at", data)


class TestContentRecall(unittest.TestCase):
    """Test ContentRecall dataclass."""

    def test_content_recall_creation(self) -> None:
        """Test creating ContentRecall instance."""
        recall = ContentRecall(
            content_id="video-001",
            content_type="video",
            context="Test context",
            tags=["test"],
            metadata={"key": "value"},
            relevance_score=0.8,
            recall_reason="topic_match"
        )

        self.assertEqual(recall.content_id, "video-001")
        self.assertEqual(recall.relevance_score, 0.8)

    def test_content_recall_to_dict(self) -> None:
        """Test ContentRecall dictionary conversion."""
        recall = ContentRecall(
            content_id="video-001",
            content_type="video",
            context=None,
            tags=[],
            metadata={},
            relevance_score=1.0,
            recall_reason="recent"
        )

        data = recall.__dict__
        self.assertEqual(data["content_id"], "video-001")


class TestIntegration(unittest.TestCase):
    """Integration tests for the memory system."""

    def setUp(self) -> None:
        """Set up for integration tests."""
        self.engine = AgentMemoryEngine(":memory:")

    def tearDown(self) -> None:
        """Clean up."""
        self.engine.close()

    def test_full_workflow(self) -> None:
        """Test complete workflow: record, search, recall, link."""
        agent_id = "integration-agent"

        # Record multiple content items
        self.engine.record_content(
            agent_id=agent_id,
            content_id="video-mining-101",
            title="Mining 101",
            description="Introduction to mining",
            tags=["mining", "beginner", "tutorial"],
            importance_score=3.0
        )

        self.engine.record_content(
            agent_id=agent_id,
            content_id="video-mining-201",
            title="Mining 201",
            description="Advanced mining techniques",
            tags=["mining", "advanced"],
            importance_score=4.0
        )

        self.engine.record_content(
            agent_id=agent_id,
            content_id="video-cooking-101",
            title="Cooking Basics",
            tags=["cooking", "beginner"]
        )

        # Search by topic
        mining_results = self.engine.recall_by_topic(agent_id, "mining")
        self.assertEqual(len(mining_results), 2)

        # Build context
        context = self.engine.build_context(agent_id, topic="mining")
        self.assertIn("mining", context.summary.lower())

        # Generate self-reference
        statement = self.engine.generate_self_reference(agent_id, "mining")
        self.assertIsInstance(statement, str)

        # Link content
        linked = self.engine.link_content(
            agent_id,
            "video-mining-101",
            "video-mining-201",
            "prerequisite"
        )
        self.assertTrue(linked)

        # Get stats
        stats = self.engine.get_memory_stats(agent_id)
        self.assertEqual(stats["total_references"], 3)

    def test_multiple_agents_isolation(self) -> None:
        """Test that agent memories are isolated."""
        self.engine.record_content(
            agent_id="agent-a",
            content_id="video-a1",
            tags=["unique-a"]
        )

        self.engine.record_content(
            agent_id="agent-b",
            content_id="video-b1",
            tags=["unique-b"]
        )

        # Agent A should only see their content
        a_refs = self.engine.recall_recent("agent-a")
        self.assertEqual(len(a_refs), 1)
        self.assertEqual(a_refs[0].content_id, "video-a1")

        # Agent B should only see their content
        b_refs = self.engine.recall_recent("agent-b")
        self.assertEqual(len(b_refs), 1)
        self.assertEqual(b_refs[0].content_id, "video-b1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
