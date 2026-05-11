#!/usr/bin/env python3
"""
Tests for BoTTube Agent Memory API Routes
==========================================

Run with:
    python -m pytest tests/test_memory_routes.py -v
    python tests/test_memory_routes.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flask import Flask

from memory_routes import init_memory_routes


class MemoryRoutesTestCase(unittest.TestCase):
    """Test case for memory API routes."""

    def setUp(self) -> None:
        """Set up test Flask app."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.config["MEMORY_DB_PATH"] = ":memory:"

        init_memory_routes(self.app)
        self.client = self.app.test_client()

    def test_health_check(self) -> None:
        """Test health check endpoint."""
        response = self.client.get("/api/memory/health")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "agent-memory")

    def test_record_content(self) -> None:
        """Test recording content."""
        payload = {
            "agent_id": "test-agent",
            "content_id": "video-001",
            "content_type": "video",
            "title": "Test Video",
            "tags": ["test", "demo"]
        }

        response = self.client.post(
            "/api/memory/record",
            json=payload,
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("reference_id", data)

    def test_record_content_missing_agent_id(self) -> None:
        """Test recording content without agent_id."""
        payload = {
            "content_id": "video-001"
        }

        response = self.client.post(
            "/api/memory/record",
            json=payload,
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_record_content_missing_content_id(self) -> None:
        """Test recording content without content_id."""
        payload = {
            "agent_id": "test-agent"
        }

        response = self.client.post(
            "/api/memory/record",
            json=payload,
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_json_routes_reject_non_object_bodies(self) -> None:
        """Test JSON mutation routes reject arrays and other non-object bodies."""
        routes = (
            ("post", "/api/memory/record"),
            ("post", "/api/memory/reference"),
            ("post", "/api/memory/link"),
        )

        for method, path in routes:
            with self.subTest(path=path):
                response = getattr(self.client, method)(
                    path,
                    json=["not", "an", "object"],
                    content_type="application/json"
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": "JSON object required"})

    def test_get_recent(self) -> None:
        """Test getting recent content."""
        # First record some content
        for i in range(5):
            self.client.post(
                "/api/memory/record",
                json={
                    "agent_id": "test-agent",
                    "content_id": f"video-{i}",
                    "title": f"Video {i}"
                },
                content_type="application/json"
            )

        response = self.client.get(
            "/api/memory/recent?agent_id=test-agent&limit=3"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["recalls"]), 3)

    def test_get_recent_missing_agent_id(self) -> None:
        """Test getting recent content without agent_id."""
        response = self.client.get("/api/memory/recent")
        self.assertEqual(response.status_code, 400)

    def test_get_recent_invalid_limit(self) -> None:
        """Test getting recent content with invalid limit."""
        response = self.client.get(
            "/api/memory/recent?agent_id=test-agent&limit=invalid"
        )
        self.assertEqual(response.status_code, 400)

    def test_get_recent_rejects_non_positive_limit(self) -> None:
        """Test recent content rejects zero and negative limits."""
        for limit in ("0", "-1"):
            with self.subTest(limit=limit):
                response = self.client.get(
                    f"/api/memory/recent?agent_id=test-agent&limit={limit}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": "limit must be positive"})

    def test_search_topic(self) -> None:
        """Test searching by topic."""
        # Record content with mining context
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-mining",
                "title": "Mining Tutorial",
                "context": "Complete guide to RustChain mining"
            },
            content_type="application/json"
        )

        # Record unrelated content
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-cooking",
                "title": "Cooking Basics"
            },
            content_type="application/json"
        )

        response = self.client.get(
            "/api/memory/search?agent_id=test-agent&topic=mining"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["recalls"]), 1)
        self.assertEqual(data["recalls"][0]["content_id"], "video-mining")

    def test_search_topic_missing_topic(self) -> None:
        """Test searching without topic parameter."""
        response = self.client.get(
            "/api/memory/search?agent_id=test-agent"
        )
        self.assertEqual(response.status_code, 400)

    def test_search_topic_rejects_non_positive_limit(self) -> None:
        """Test topic search rejects zero and negative limits."""
        for limit in ("0", "-1"):
            with self.subTest(limit=limit):
                response = self.client.get(
                    f"/api/memory/search?agent_id=test-agent&topic=mining&limit={limit}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": "limit must be positive"})

    def test_search_by_tags(self) -> None:
        """Test searching by tags."""
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-001",
                "tags": ["mining", "tutorial", "beginner"]
            },
            content_type="application/json"
        )

        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-002",
                "tags": ["mining", "advanced"]
            },
            content_type="application/json"
        )

        # Search by single tag
        response = self.client.get(
            "/api/memory/tags?agent_id=test-agent&tags=tutorial"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["recalls"]), 1)

    def test_search_by_tags_match_all(self) -> None:
        """Test searching by tags with match_all."""
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-001",
                "tags": ["mining", "tutorial"]
            },
            content_type="application/json"
        )

        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-002",
                "tags": ["mining"]
            },
            content_type="application/json"
        )

        # Match all tags
        response = self.client.get(
            "/api/memory/tags?agent_id=test-agent&tags=mining,tutorial&match_all=true"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["recalls"]), 1)

    def test_search_by_tags_rejects_non_positive_limit(self) -> None:
        """Test tag search rejects zero and negative limits."""
        for limit in ("0", "-1"):
            with self.subTest(limit=limit):
                response = self.client.get(
                    f"/api/memory/tags?agent_id=test-agent&tags=mining&limit={limit}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": "limit must be positive"})

    def test_get_context(self) -> None:
        """Test building memory context."""
        # Record content
        for i in range(3):
            self.client.post(
                "/api/memory/record",
                json={
                    "agent_id": "test-agent",
                    "content_id": f"video-{i}",
                    "title": f"Mining Part {i + 1}",
                    "tags": ["mining", "series"]
                },
                content_type="application/json"
            )

        response = self.client.get(
            "/api/memory/context?agent_id=test-agent&topic=mining&max_items=5"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("context", data)

        context = data["context"]
        self.assertEqual(context["agent_id"], "test-agent")
        self.assertEqual(context["topic"], "mining")
        self.assertGreater(len(context["references"]), 0)
        self.assertIn("summary", context)
        self.assertIn("related_topics", context)

    def test_get_context_missing_agent_id(self) -> None:
        """Test context without agent_id."""
        response = self.client.get("/api/memory/context")
        self.assertEqual(response.status_code, 400)

    def test_get_context_rejects_non_positive_max_items(self) -> None:
        """Test context rejects zero and negative max_items values."""
        for max_items in ("0", "-1"):
            with self.subTest(max_items=max_items):
                response = self.client.get(
                    f"/api/memory/context?agent_id=test-agent&max_items={max_items}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": "max_items must be positive"})

    def test_generate_reference_casual(self) -> None:
        """Test generating casual self-reference."""
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-001",
                "title": "Mining Basics",
                "tags": ["mining"]
            },
            content_type="application/json"
        )

        response = self.client.post(
            "/api/memory/reference",
            json={
                "agent_id": "test-agent",
                "topic": "mining",
                "style": "casual"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("statement", data)
        self.assertIsInstance(data["statement"], str)

    def test_generate_reference_formal(self) -> None:
        """Test generating formal self-reference."""
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-001",
                "title": "Mining Guide"
            },
            content_type="application/json"
        )

        response = self.client.post(
            "/api/memory/reference",
            json={
                "agent_id": "test-agent",
                "topic": "mining",
                "style": "formal"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("video-001", data["statement"])

    def test_generate_reference_no_content(self) -> None:
        """Test generating reference when no content exists."""
        response = self.client.post(
            "/api/memory/reference",
            json={
                "agent_id": "test-agent",
                "topic": "unknown-topic"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("haven't covered", data["statement"].lower())

    def test_generate_reference_invalid_style(self) -> None:
        """Test generating reference with invalid style."""
        response = self.client.post(
            "/api/memory/reference",
            json={
                "agent_id": "test-agent",
                "topic": "mining",
                "style": "invalid-style"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_link_content(self) -> None:
        """Test linking content items."""
        # Record content
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-part1",
                "title": "Part 1"
            },
            content_type="application/json"
        )

        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-part2",
                "title": "Part 2"
            },
            content_type="application/json"
        )

        response = self.client.post(
            "/api/memory/link",
            json={
                "agent_id": "test-agent",
                "source_content_id": "video-part1",
                "target_content_id": "video-part2",
                "relationship_type": "sequel"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])

    def test_link_content_invalid_relationship_type(self) -> None:
        """Test linking with invalid relationship type."""
        response = self.client.post(
            "/api/memory/link",
            json={
                "agent_id": "test-agent",
                "source_content_id": "video-1",
                "target_content_id": "video-2",
                "relationship_type": "invalid-type"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_link_content_not_found(self) -> None:
        """Test linking non-existent content."""
        response = self.client.post(
            "/api/memory/link",
            json={
                "agent_id": "test-agent",
                "source_content_id": "nonexistent-1",
                "target_content_id": "nonexistent-2",
                "relationship_type": "sequel"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)

    def test_get_stats(self) -> None:
        """Test getting memory statistics."""
        # Record some content
        for i in range(3):
            self.client.post(
                "/api/memory/record",
                json={
                    "agent_id": "test-agent",
                    "content_id": f"video-{i}",
                    "content_type": "video"
                },
                content_type="application/json"
            )

        response = self.client.get(
            "/api/memory/stats?agent_id=test-agent"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])

        stats = data["stats"]
        self.assertEqual(stats["agent_id"], "test-agent")
        self.assertEqual(stats["total_references"], 3)
        self.assertIn("by_content_type", stats)

    def test_clear_memory(self) -> None:
        """Test clearing agent memory."""
        # Record some content
        for i in range(5):
            self.client.post(
                "/api/memory/record",
                json={
                    "agent_id": "test-agent",
                    "content_id": f"video-{i}"
                },
                content_type="application/json"
            )

        response = self.client.delete(
            "/api/memory/clear?agent_id=test-agent"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["deleted_count"], 5)

        # Verify memory is cleared
        recent_response = self.client.get(
            "/api/memory/recent?agent_id=test-agent"
        )
        recent_data = recent_response.get_json()
        self.assertEqual(len(recent_data["recalls"]), 0)

    def test_record_with_importance(self) -> None:
        """Test recording content with importance score."""
        response = self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-important",
                "importance": 8.5
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)

        # Verify via stats
        stats_response = self.client.get(
            "/api/memory/stats?agent_id=test-agent"
        )
        stats = stats_response.get_json()["stats"]
        self.assertEqual(stats["average_importance"], 8.5)

    def test_context_without_summary(self) -> None:
        """Test building context without summary."""
        self.client.post(
            "/api/memory/record",
            json={
                "agent_id": "test-agent",
                "content_id": "video-001"
            },
            content_type="application/json"
        )

        response = self.client.get(
            "/api/memory/context?agent_id=test-agent&include_summary=false"
        )

        self.assertEqual(response.status_code, 200)
        context = response.get_json()["context"]
        self.assertEqual(context["summary"], "")


class TestMemoryRoutesIntegration(unittest.TestCase):
    """Integration tests for memory routes."""

    def setUp(self) -> None:
        """Set up test Flask app."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.config["MEMORY_DB_PATH"] = ":memory:"
        init_memory_routes(self.app)
        self.client = self.app.test_client()

    def test_full_workflow(self) -> None:
        """Test complete API workflow."""
        agent_id = "integration-agent"

        # 1. Record content
        content_ids = []
        for i in range(3):
            response = self.client.post(
                "/api/memory/record",
                json={
                    "agent_id": agent_id,
                    "content_id": f"video-{i}",
                    "title": f"Video {i}",
                    "tags": ["series", f"part-{i}"],
                    "importance": 1.0 + i * 0.5
                },
                content_type="application/json"
            )
            self.assertEqual(response.status_code, 201)
            content_ids.append(response.get_json()["reference_id"])

        # 2. Get recent content
        response = self.client.get(
            f"/api/memory/recent?agent_id={agent_id}&limit=2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["recalls"]), 2)

        # 3. Search by topic
        response = self.client.get(
            f"/api/memory/search?agent_id={agent_id}&topic=video"
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.get_json()["recalls"]), 0)

        # 4. Search by tags
        response = self.client.get(
            f"/api/memory/tags?agent_id={agent_id}&tags=series"
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.get_json()["recalls"]), 0)

        # 5. Build context
        response = self.client.get(
            f"/api/memory/context?agent_id={agent_id}&max_items=5"
        )
        self.assertEqual(response.status_code, 200)
        context = response.get_json()["context"]
        self.assertEqual(context["agent_id"], agent_id)

        # 6. Generate self-reference
        response = self.client.post(
            "/api/memory/reference",
            json={
                "agent_id": agent_id,
                "topic": "series",
                "style": "educational"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("statement", response.get_json())

        # 7. Link content
        response = self.client.post(
            "/api/memory/link",
            json={
                "agent_id": agent_id,
                "source_content_id": "video-0",
                "target_content_id": "video-1",
                "relationship_type": "prerequisite"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # 8. Get stats
        response = self.client.get(
            f"/api/memory/stats?agent_id={agent_id}"
        )
        self.assertEqual(response.status_code, 200)
        stats = response.get_json()["stats"]
        self.assertEqual(stats["total_references"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
