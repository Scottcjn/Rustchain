"""
Test for audience_tracker.py
Verify all boundary conditions work correctly: new vs regular vs returning vs critic
"""

import tempfile
from audience_tracker import (
    AudienceTracker,
    ViewerStats,
    Sentiment,
    generate_greeting,
    generate_community_shoutout,
    generate_inspired_credit,
    ViewerCategory
)


def test_new_viewer():
    print("🧪 Testing new viewer...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    tracker = AudienceTracker(f.name)
    stats = tracker.record_comment("agent1", 123, "alice", "Hello world", Sentiment.NEUTRAL)
    assert stats.is_new
    assert stats.total_comments == 1
    assert stats.category == ViewerCategory.NEW
    greeting = generate_greeting(stats)
    print(f"   Greeting: {greeting}")
    print("✅ New viewer test passed\n")
    import os
    os.unlink(f.name)


def test_regular_viewer():
    print("🧪 Testing regular viewer (3+ comments)...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    tracker = AudienceTracker(f.name)
    # 3 comments
    tracker.record_comment("agent1", 123, "alice", "1", Sentiment.POSITIVE)
    tracker.record_comment("agent1", 123, "alice", "2", Sentiment.POSITIVE)
    stats = tracker.record_comment("agent1", 123, "alice", "3", Sentiment.POSITIVE)
    assert stats.is_regular
    assert stats.total_comments == 3
    assert stats.category == ViewerCategory.REGULAR
    greeting = generate_greeting(stats)
    print(f"   Greeting: {greeting}")
    print("✅ Regular viewer test passed\n")
    import os
    os.unlink(f.name)


def test_frequent_critic():
    print("🧪 Testing frequent critic (>50% negative)...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    tracker = AudienceTracker(f.name)
    tracker.record_comment("agent1", 123, "bob", "This is bad", Sentiment.NEGATIVE)
    tracker.record_comment("agent1", 123, "bob", "Still bad", Sentiment.NEGATIVE)
    stats = tracker.record_comment("agent1", 123, "bob", "Meh", Sentiment.NEUTRAL)
    assert stats.is_frequent_critic
    assert stats.negative_comments == 2
    assert stats.negative_comments / stats.total_comments > 0.5
    greeting = generate_greeting(stats)
    print(f"   Greeting: {greeting}")
    print("✅ Frequent critic test passed\n")
    import os
    os.unlink(f.name)


def test_top_commenters():
    print("🧪 Testing top commenters for shoutouts...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    tracker = AudienceTracker(f.name)
    tracker.record_comment("agent1", 1, "alice", "comment", Sentiment.NEUTRAL)
    tracker.record_comment("agent1", 2, "bob", "comment", Sentiment.NEUTRAL)
    for _ in range(5):
        tracker.record_comment("agent1", 2, "bob", "comment", Sentiment.NEUTRAL)
    tracker.record_comment("agent1", 3, "charlie", "comment", Sentiment.NEUTRAL)
    for _ in range(3):
        tracker.record_comment("agent1", 3, "charlie", "comment", Sentiment.NEUTRAL)

    top = tracker.get_top_commenters("agent1", limit=3)
    assert len(top) == 3
    assert top[0].user_id == 2  # bob has most comments (6)
    assert top[1].user_id == 3  # charlie has 4
    assert top[2].user_id == 1  # alice has 1

    shoutout = generate_community_shoutout(top)
    print(f"   Shoutout:\n{shoutout}")
    print("✅ Top commenters test passed\n")
    import os
    os.unlink(f.name)


def test_inspired_credit():
    print("🧪 Testing inspired credit...")
    credit = generate_inspired_credit("johndoe")
    print(f"   Credit: {credit}")
    assert "@johndoe" in credit
    print("✅ Inspired credit test passed\n")


if __name__ == "__main__":
    print("Running audience_tracker tests...\n")
    test_new_viewer()
    test_regular_viewer()
    test_frequent_critic()
    test_top_commenters()
    test_inspired_credit()
    print("\n✅ All tests passed!")
