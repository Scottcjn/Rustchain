#!/usr/bin/env python3
"""
BoTTube Agent Memory Example
=============================

Demonstrates usage of the Agent Memory system for self-referencing past content.

Usage:
    python examples/memory_agent_example.py

Requirements:
    - Python 3.9+
    - Flask (for API demo)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory_engine import AgentMemoryEngine
from memory_store import AgentMemoryStore


def demo_basic_usage() -> None:
    """Demonstrate basic memory operations."""
    print("=" * 60)
    print("BoTTube Agent Memory - Basic Usage Demo")
    print("=" * 60)
    print()

    # Initialize engine with in-memory database
    engine = AgentMemoryEngine(":memory:")

    # Record some content
    print("1. Recording content...")
    ref_id = engine.record_content(
        agent_id="demo-agent",
        content_id="video-001",
        content_type="video",
        title="Introduction to RustChain Mining",
        description="Learn the basics of mining on RustChain",
        tags=["mining", "tutorial", "beginner"],
        importance_score=3.0
    )
    print(f"   Recorded: video-001 (reference_id: {ref_id})")

    ref_id = engine.record_content(
        agent_id="demo-agent",
        content_id="video-002",
        content_type="video",
        title="Advanced Mining Optimization",
        description="Optimize your mining setup for maximum rewards",
        tags=["mining", "advanced", "optimization"],
        importance_score=4.0
    )
    print(f"   Recorded: video-002 (reference_id: {ref_id})")

    ref_id = engine.record_content(
        agent_id="demo-agent",
        content_id="video-003",
        content_type="video",
        title="Understanding RIP-200 Epoch Rewards",
        description="Deep dive into epoch rewards system",
        tags=["rewards", "epoch", "rip-200"],
        importance_score=5.0
    )
    print(f"   Recorded: video-003 (reference_id: {ref_id})")
    print()

    # Recall recent content
    print("2. Recalling recent content...")
    recent = engine.recall_recent("demo-agent", limit=2)
    for recall in recent:
        title = recall.metadata.get("title", recall.content_id)
        print(f"   - {title} (relevance: {recall.relevance_score})")
    print()

    # Search by topic
    print("3. Searching by topic 'mining'...")
    mining_results = engine.recall_by_topic("demo-agent", "mining")
    for recall in mining_results:
        title = recall.metadata.get("title", recall.content_id)
        print(f"   - {title} (relevance: {recall.relevance_score:.2f})")
    print()

    # Search by tags
    print("4. Searching by tags ['mining', 'tutorial']...")
    tag_results = engine.recall_by_tags(
        "demo-agent",
        ["mining", "tutorial"],
        match_all=True
    )
    for recall in tag_results:
        title = recall.metadata.get("title", recall.content_id)
        print(f"   - {title} (tags: {', '.join(recall.tags)})")
    print()

    # Build context
    print("5. Building context for 'mining'...")
    context = engine.build_context("demo-agent", topic="mining", max_items=5)
    print(f"   Summary: {context.summary}")
    print(f"   Related topics: {', '.join(context.related_topics[:5])}")
    print()

    # Generate self-references
    print("6. Generating self-references...")

    casual = engine.generate_self_reference(
        "demo-agent", "mining", style="casual"
    )
    print(f"   Casual: {casual}")

    formal = engine.generate_self_reference(
        "demo-agent", "mining", style="formal"
    )
    print(f"   Formal: {formal}")

    educational = engine.generate_self_reference(
        "demo-agent", "mining", style="educational"
    )
    print(f"   Educational: {educational}")
    print()

    # Link content
    print("7. Linking content (video-001 -> video-002 as sequel)...")
    success = engine.link_content(
        "demo-agent",
        "video-001",
        "video-002",
        "prerequisite"
    )
    print(f"   Link created: {success}")
    print()

    # Get statistics
    print("8. Memory statistics...")
    stats = engine.get_memory_stats("demo-agent")
    print(f"   Total references: {stats['total_references']}")
    print(f"   By content type: {stats['by_content_type']}")
    print(f"   Average importance: {stats['average_importance']}")
    print(f"   Total relationships: {stats['total_relationships']}")
    print()

    # Clean up
    engine.close()
    print("Demo completed!")
    print()


def demo_use_case_video_series() -> None:
    """Demonstrate video series use case."""
    print("=" * 60)
    print("Use Case: Video Series Management")
    print("=" * 60)
    print()

    engine = AgentMemoryEngine(":memory:")
    agent_id = "series-creator"

    # Record a video series
    series_parts = [
        ("Mining Part 1: Basics", "Introduction to mining concepts", ["mining", "series", "part-1"]),
        ("Mining Part 2: Setup", "Setting up your mining operation", ["mining", "series", "part-2"]),
        ("Mining Part 3: Optimization", "Optimizing for maximum rewards", ["mining", "series", "part-3"]),
    ]

    print("Recording video series...")
    content_ids = []
    for title, desc, tags in series_parts:
        ref_id = engine.record_content(
            agent_id=agent_id,
            content_id=f"mining-series-{len(content_ids) + 1}",
            title=title,
            description=desc,
            tags=tags,
            importance_score=4.0
        )
        content_ids.append(f"mining-series-{len(content_ids) + 1}")
        print(f"  Recorded: {title}")
    print()

    # Link series parts
    print("Linking series parts...")
    for i in range(len(content_ids) - 1):
        engine.link_content(
            agent_id,
            content_ids[i],
            content_ids[i + 1],
            "sequel"
        )
    print("  Parts linked as sequel chain")
    print()

    # When creating a new video, reference the series
    print("Building context for new video...")
    context = engine.build_context(agent_id, topic="mining series")
    print(f"  Context summary: {context.summary}")
    print()

    # Generate reference for new video description
    print("Generating series reference...")
    statement = engine.generate_self_reference(
        agent_id, "mining", style="educational"
    )
    print(f"  Reference: {statement}")
    print()

    engine.close()
    print("Use case demo completed!")
    print()


def demo_use_case_topic_authority() -> None:
    """Demonstrate topic authority building use case."""
    print("=" * 60)
    print("Use Case: Topic Authority Building")
    print("=" * 60)
    print()

    engine = AgentMemoryEngine(":memory:")
    agent_id = "expert-agent"

    # Record multiple pieces on same topic
    topics_content = [
        ("DeFi Basics", ["defi", "beginner", "fundamentals"]),
        ("DeFi Yield Farming", ["defi", "yield", "intermediate"]),
        ("DeFi Risk Management", ["defi", "risk", "advanced"]),
        ("DeFi Protocol Analysis", ["defi", "analysis", "expert"]),
    ]

    print("Building topic authority on 'DeFi'...")
    for title, tags in topics_content:
        engine.record_content(
            agent_id=agent_id,
            content_id=f"defi-{len(tags)}",
            title=title,
            tags=tags,
            importance_score=3.0 + len(tags)
        )
        print(f"  Added: {title}")
    print()

    # Query all DeFi content
    print("Querying all DeFi content...")
    defi_content = engine.recall_by_tags(
        agent_id, ["defi"], match_all=False, limit=10
    )
    print(f"  Found {len(defi_content)} pieces on DeFi")

    for item in defi_content:
        title = item.metadata.get("title", item.content_id)
        print(f"    - {title} (tags: {', '.join(item.tags)})")
    print()

    # Generate authority statement
    print("Generating authority statement...")
    statement = engine.generate_self_reference(
        agent_id, "defi", style="formal"
    )
    print(f"  Statement: {statement}")
    print()

    # Get stats
    stats = engine.get_memory_stats(agent_id)
    print(f"Topic coverage: {stats['total_references']} pieces")
    print()

    engine.close()
    print("Use case demo completed!")
    print()


def demo_api_workflow() -> None:
    """Demonstrate API-style workflow."""
    print("=" * 60)
    print("API Workflow Demo")
    print("=" * 60)
    print()

    store = AgentMemoryStore(":memory:")
    agent_id = "api-user"

    # Simulate API calls
    print("1. POST /api/memory/record")
    ref_id = store.add_reference(
        agent_id=agent_id,
        content_id="content-123",
        content_type="video",
        context="API demo content",
        tags=["api", "demo"],
        importance_score=2.0
    )
    print(f"   Response: {{'success': true, 'reference_id': {ref_id}}}")
    print()

    print("2. GET /api/memory/recent?agent_id=api-user&limit=10")
    refs = store.get_references(agent_id, limit=10)
    print(f"   Response: {{'success': true, 'recalls': [{len(refs)} items]}}")
    print()

    print("3. GET /api/memory/search?agent_id=api-user&topic=demo")
    results = store.search_references(agent_id, "demo")
    print(f"   Response: {{'success': true, 'recalls': [{len(results)} items]}}")
    print()

    print("4. GET /api/memory/stats?agent_id=api-user")
    stats = store.get_stats(agent_id)
    print(f"   Response: {{'success': true, 'stats': {stats}}}")
    print()

    print("5. DELETE /api/memory/clear?agent_id=api-user")
    deleted = store.clear_agent_memory(agent_id)
    print(f"   Response: {{'success': true, 'deleted_count': {deleted}}}")
    print()

    store.close()
    print("API workflow demo completed!")
    print()


def main() -> None:
    """Run all demos."""
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "BoTTube Agent Memory System" + " " * 19 + "║")
    print("║" + " " * 15 + "Issue #2285 Implementation" + " " * 17 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    demo_basic_usage()
    demo_use_case_video_series()
    demo_use_case_topic_authority()
    demo_api_workflow()

    print("=" * 60)
    print("All demos completed successfully!")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
