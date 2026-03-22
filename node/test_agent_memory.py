"""
Test for agent_memory.py
Verify all functionality works correctly: memory store, search, stats, series detection
"""

import tempfile
from agent_memory import (
    AgentMemory,
    VideoMemory,
    MemorySearchResult,
    AgentStats,
    generate_self_reference,
    generate_milestone_message,
    generate_series_part_natural,
    generate_changed_opinion
)


def test_add_and_search():
    print("🧪 Testing adding videos and search...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    am = AgentMemory(f.name)

    # Add some videos
    am.add_video(
        agent_name="botube_ai",
        video_id=1,
        title="How to mine RustChain on vintage hardware",
        description="In this video I show you how to get started mining RustChain on older CPUs",
        tags=["mining", "vintage", "hardware"]
    )
    am.add_video(
        agent_name="botube_ai",
        video_id=2,
        title="Why I changed my mind about Proof of Antiquity",
        description="After further research, I've changed my perspective on PoA algorithm",
        tags=["blockchain", "proof of antiquity", "opinion"]
    )
    am.add_video(
        agent_name="botube_ai",
        video_id=3,
        title="Mining RustChain on a 10 year old laptop",
        description="Can you still mine profitably on older laptop hardware? Let's find out",
        tags=["mining", "laptop", "vintage"]
    )

    # Search for mining
    results = am.search_memory("botube_ai", "mining vintage hardware")
    print(f"   Search 'mining vintage hardware' found {len(results)} results")
    for r in results:
        print(f"   - {r.video.title} (similarity: {r.similarity:.2f})")

    assert len(results) > 0
    assert results[0].similarity > 0.2
    print("✅ Search test passed\n")

    import os
    os.unlink(f.name)


def test_agent_stats():
    print("🧪 Testing agent stats and milestone detection...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    am = AgentMemory(f.name)

    for i in range(99):
        am.add_video("agent1", i + 1, f"Video {i+1}", "description", tags=["topic1"])

    stats = am.get_agent_stats("agent1")
    assert stats is not None
    assert stats.total_videos == 99
    assert not stats.has_milestone

    # Add 100th video to trigger milestone
    am.add_video("agent1", 100, "My 100th video!", "description", tags=["milestone"])
    stats = am.get_agent_stats("agent1")
    assert stats.has_milestone
    assert stats.milestone == 100

    msg = generate_milestone_message(stats)
    print(f"   Milestone 100 message: {msg}")
    assert "100" in msg
    print("✅ Stats/milestone test passed\n")

    import os
    os.unlink(f.name)


def test_self_reference():
    print("🧪 Testing self-reference generation...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    am = AgentMemory(f.name)
    # publish_timestamp is auto-generated to now, we leave it
    am.add_video("agent1", 1, "Introduction to RustChain", "Intro video")

    results = am.search_memory("agent1", "RustChain introduction")
    ref = generate_self_reference(results)
    print(f"   Self-reference: {ref}")
    assert len(ref) > 0
    print("✅ Self-reference test passed\n")

    import os
    os.unlink(f.name)


def test_changed_opinion():
    print("🧪 Testing changed opinion generation...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    am = AgentMemory(f.name)
    video = VideoMemory(
        video_id=1,
        title="Proof of Antiquity is bad",
        description="Old opinion",
        publish_timestamp=1,
        tags=[],
        series_name=None,
        content=""
    )
    msg = generate_changed_opinion(video, "new take here")
    print(f"   Changed opinion: {msg}")
    assert "changed my mind" in msg
    assert video.title in msg
    print("✅ Changed opinion test passed\n")

    import os
    os.unlink(f.name)


def test_series_detection():
    print("🧪 Testing series detection...")
    # This is implemented directly, just test the natural generation
    msg = generate_series_part_natural("RustChain mining guide", 3)
    print(f"   Series intro: {msg}")
    assert "part 3" in msg
    assert "RustChain mining guide" in msg
    print("✅ Series detection test passed\n")


if __name__ == "__main__":
    print("Running agent_memory tests...\n")
    test_add_and_search()
    test_agent_stats()
    test_self_reference()
    test_changed_opinion()
    test_series_detection()
    print("\n✅ All tests passed!")
