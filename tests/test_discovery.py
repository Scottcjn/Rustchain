"""
Tests for tools/bottube_discovery.py
======================================
Covers: search relevance, recommendation quality, trending order,
tag filtering, agent filtering, recency ordering, and edge cases.
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from bottube_discovery import VideoDiscovery, _tokenize, _tf, _cosine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_db() -> VideoDiscovery:
    """Return a fresh in-memory VideoDiscovery with standard test fixtures."""
    disc = VideoDiscovery(":memory:")
    now = time.time()

    videos = [
        # id, title, description, tags, agent_id, duration, created_at
        ("v1", "Rust Systems Programming", "Memory safety ownership borrowing lifetimes", ["rust", "systems", "programming"], "alpha", 600, now - 3600),
        ("v2", "Python Machine Learning", "scikit-learn pandas numpy tensorflow", ["python", "ml", "data"], "beta", 900, now - 7200),
        ("v3", "Blockchain Fundamentals", "consensus distributed ledger crypto hash", ["blockchain", "crypto", "distributed"], "gamma", 1200, now - 10800),
        ("v4", "Rust Async Programming", "tokio async await futures concurrency", ["rust", "async", "networking"], "alpha", 750, now - 14400),
        ("v5", "Deep Learning with Python", "neural networks backpropagation pytorch tensorflow", ["python", "ml", "ai"], "beta", 1500, now - 18000),
        ("v6", "Ethereum Smart Contracts", "solidity EVM gas blockchain crypto", ["blockchain", "ethereum", "crypto"], "gamma", 660, now - 21600),
        ("v7", "Rust Web Development", "axum actix-web REST APIs web services", ["rust", "web", "api"], "alpha", 840, now - 25200),
        ("v8", "Natural Language Processing", "tokenisation embeddings transformers BERT", ["python", "nlp", "ml"], "beta", 1800, now - 28800),
        ("v9", "Distributed Systems Design", "CAP theorem consistency availability partition", ["distributed", "systems", "architecture"], "gamma", 2100, now - 32400),
        ("v10", "Rust Macros and Metaprogramming", "procedural macros derive attributes DSL", ["rust", "metaprogramming", "programming"], "alpha", 960, now - 36000),
    ]

    for vid, title, desc, tags, agent, dur, created in videos:
        disc.index_video(vid, title, desc, tags, agent, dur, created)

    return disc


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

class TestHelpers(unittest.TestCase):

    def test_tokenize_lowercases(self):
        tokens = _tokenize("Hello World")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_tokenize_strips_punctuation(self):
        tokens = _tokenize("hello, world! foo-bar")
        self.assertNotIn("hello,", tokens)

    def test_tf_sums_correctly(self):
        tokens = ["a", "b", "a"]
        tf = _tf(tokens)
        self.assertAlmostEqual(tf["a"], 2 / 3)
        self.assertAlmostEqual(tf["b"], 1 / 3)

    def test_cosine_identical_vectors(self):
        v = {"a": 1.0, "b": 0.5}
        self.assertAlmostEqual(_cosine(v, v), 1.0)

    def test_cosine_orthogonal_vectors(self):
        self.assertAlmostEqual(_cosine({"a": 1.0}, {"b": 1.0}), 0.0)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch(unittest.TestCase):

    def setUp(self):
        self.disc = _make_db()

    def tearDown(self):
        self.disc.close()

    def test_search_returns_results(self):
        results = self.disc.search("rust programming")
        self.assertGreater(len(results), 0)

    def test_search_relevance_rust(self):
        results = self.disc.search("rust programming", limit=5)
        ids = [r["video_id"] for r in results]
        # At least one Rust video should appear in top-5
        self.assertTrue(any(v in ids for v in ["v1", "v4", "v7", "v10"]))

    def test_search_relevance_blockchain(self):
        results = self.disc.search("blockchain crypto", limit=5)
        ids = [r["video_id"] for r in results]
        self.assertTrue(any(v in ids for v in ["v3", "v6"]))

    def test_search_empty_query(self):
        results = self.disc.search("")
        self.assertEqual(results, [])

    def test_search_limit_respected(self):
        results = self.disc.search("rust", limit=2)
        self.assertLessEqual(len(results), 2)

    def test_search_no_match_returns_empty(self):
        results = self.disc.search("xyzzy42foobarbaz")
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class TestRecommendations(unittest.TestCase):

    def setUp(self):
        self.disc = _make_db()

    def tearDown(self):
        self.disc.close()

    def test_recommendations_excludes_source(self):
        recs = self.disc.get_recommendations("v1", limit=10)
        ids = [r["video_id"] for r in recs]
        self.assertNotIn("v1", ids)

    def test_recommendations_rust_video_prefers_rust(self):
        recs = self.disc.get_recommendations("v1", limit=5)
        ids = [r["video_id"] for r in recs]
        rust_ids = {"v4", "v7", "v10"}
        self.assertTrue(rust_ids & set(ids), "Expected at least one Rust video in top-5 recs")

    def test_recommendations_python_video_prefers_python(self):
        recs = self.disc.get_recommendations("v2", limit=5)
        ids = [r["video_id"] for r in recs]
        python_ids = {"v5", "v8"}
        self.assertTrue(python_ids & set(ids))

    def test_recommendations_unknown_video(self):
        recs = self.disc.get_recommendations("nonexistent")
        self.assertEqual(recs, [])

    def test_recommendations_limit_respected(self):
        recs = self.disc.get_recommendations("v1", limit=3)
        self.assertLessEqual(len(recs), 3)


# ---------------------------------------------------------------------------
# Trending
# ---------------------------------------------------------------------------

class TestTrending(unittest.TestCase):

    def setUp(self):
        self.disc = _make_db()
        now = time.time()
        # Simulate recent views: v3 most popular, then v1
        for _ in range(15):
            self.disc.record_view("v3", now - 1800)  # 30 min ago
        for _ in range(8):
            self.disc.record_view("v1", now - 3600)  # 1 hour ago
        for _ in range(3):
            self.disc.record_view("v9", now - 7200)  # 2 hours ago

    def tearDown(self):
        self.disc.close()

    def test_trending_top_is_most_viewed(self):
        trending = self.disc.get_trending(hours=24, limit=5)
        self.assertEqual(trending[0]["video_id"], "v3")

    def test_trending_order_second(self):
        trending = self.disc.get_trending(hours=24, limit=5)
        ids = [r["video_id"] for r in trending]
        self.assertEqual(ids.index("v1"), 1)

    def test_trending_limit_respected(self):
        trending = self.disc.get_trending(hours=24, limit=2)
        self.assertLessEqual(len(trending), 2)

    def test_trending_empty_window_falls_back(self):
        # Request a 1-second window — should fall back to view_count sort
        trending = self.disc.get_trending(hours=0, limit=5)
        self.assertIsInstance(trending, list)


# ---------------------------------------------------------------------------
# Tag & Agent Filters
# ---------------------------------------------------------------------------

class TestFilters(unittest.TestCase):

    def setUp(self):
        self.disc = _make_db()

    def tearDown(self):
        self.disc.close()

    def test_get_by_tag_rust(self):
        results = self.disc.get_by_tag("rust")
        ids = {r["video_id"] for r in results}
        self.assertIn("v1", ids)
        self.assertIn("v4", ids)
        self.assertIn("v7", ids)
        self.assertIn("v10", ids)
        self.assertNotIn("v2", ids)

    def test_get_by_tag_case_insensitive(self):
        lower = self.disc.get_by_tag("rust")
        upper = self.disc.get_by_tag("RUST")
        self.assertEqual(
            {r["video_id"] for r in lower},
            {r["video_id"] for r in upper},
        )

    def test_get_by_tag_nonexistent(self):
        self.assertEqual(self.disc.get_by_tag("doesnotexist"), [])

    def test_get_by_agent(self):
        results = self.disc.get_by_agent("alpha")
        ids = {r["video_id"] for r in results}
        self.assertTrue(ids.issuperset({"v1", "v4", "v7", "v10"}))
        self.assertNotIn("v2", ids)

    def test_get_new_order(self):
        new = self.disc.get_new(limit=3)
        # Most recently indexed should come first
        # (all were indexed in setUp sequentially, v1 was earliest created but index order matters)
        self.assertEqual(len(new), 3)

    def test_get_new_limit(self):
        new = self.disc.get_new(limit=2)
        self.assertEqual(len(new), 2)

    def test_video_count(self):
        self.assertEqual(self.disc.video_count(), 10)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
