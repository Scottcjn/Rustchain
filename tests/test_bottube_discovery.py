# SPDX-License-Identifier: MIT
"""Unit tests for the BoTTube Video Discovery Engine."""

import sys
import time
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import bottube_discovery  # noqa: E402


def test_tokenize_lowercases_and_strips_punctuation():
    assert bottube_discovery._tokenize("Hello World!") == ["hello", "world"]
    assert bottube_discovery._tokenize("RustChain 2.0 beta") == ["rustchain", "2", "0", "beta"]
    assert bottube_discovery._tokenize("  leading/trailing  ") == ["leading", "trailing"]
    assert bottube_discovery._tokenize("") == []
    assert bottube_discovery._tokenize("...") == []


def test_tf_computes_term_frequencies():
    tokens = ["rust", "chain", "rust"]
    tf = bottube_discovery._tf(tokens)
    assert tf == {"rust": 2 / 3, "chain": 1 / 3}


def test_tf_empty_tokens_returns_empty():
    assert bottube_discovery._tf([]) == {}


def test_tf_single_token():
    assert bottube_discovery._tf(["hello"]) == {"hello": 1.0}


def test_cosine_identical_vectors():
    vec = {"a": 0.5, "b": 0.5}
    assert bottube_discovery._cosine(vec, vec) == pytest.approx(1.0)


def test_cosine_disjoint_vectors():
    assert bottube_discovery._cosine({"a": 1.0}, {"b": 1.0}) == 0.0


def test_cosine_partial_overlap():
    sim = bottube_discovery._cosine({"a": 1.0, "b": 1.0}, {"a": 0.5, "c": 0.5})
    assert 0 < sim < 1


def test_cosine_zero_magnitude():
    assert bottube_discovery._cosine({}, {"a": 1.0}) == 0.0
    assert bottube_discovery._cosine({"a": 1.0}, {}) == 0.0


def test_cosine_empty_both():
    assert bottube_discovery._cosine({}, {}) == 0.0


def test_index_video_and_count():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello World", description="A test video", tags=["demo"])
    assert vd.video_count() == 1


def test_index_video_upsert_replaces_existing():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Original")
    vd.index_video("v1", "Updated")
    assert vd.video_count() == 1
    results = vd.search("Updated")
    assert len(results) == 1


def test_index_video_defaults():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Title")
    row = vd._conn.execute("SELECT * FROM videos WHERE video_id='v1'").fetchone()
    assert row["description"] == ""
    assert row["tags"] == ""
    assert row["agent_id"] == ""
    assert row["duration"] == 0
    assert row["view_count"] == 0


def test_search_empty_query():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello World")
    assert vd.search("") == []


def test_search_ranks_by_relevance():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "RustChain Mining Guide")
    vd.index_video("v2", "Python Tutorial for Beginners")
    vd.index_video("v3", "Advanced RustChain Techniques")
    results = vd.search("RustChain")
    titles = [r["title"] for r in results]
    assert "RustChain Mining Guide" in titles
    assert "Advanced RustChain Techniques" in titles
    assert "Python Tutorial for Beginners" not in titles


def test_search_no_match():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello World")
    assert vd.search("nonexistent") == []


def test_search_returns_limited_results():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    for i in range(5):
        vd.index_video(f"v{i}", f"RustChain video number {i}")
    results = vd.search("RustChain", limit=2)
    assert len(results) == 2


def test_get_recommendations_missing_source():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello")
    assert vd.get_recommendations("nonexistent") == []


def test_get_recommendations_empty_corpus():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Solo")
    assert vd.get_recommendations("v1") == []


def test_get_recommendations_ranks_by_similarity():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "RustChain Mining Guide", tags=["crypto", "mining"])
    vd.index_video("v2", "RustChain Staking Guide", tags=["crypto", "staking"])
    vd.index_video("v3", "Cat Video", tags=["pets"])
    results = vd.get_recommendations("v1")
    titles = [r["title"] for r in results]
    assert titles[0] == "RustChain Staking Guide"
    assert "Cat Video" in titles


def test_get_recommendations_agent_boost():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "A B C D E", agent_id="alice")
    vd.index_video("v2", "F G H I J", agent_id="alice")
    vd.index_video("v3", "F G H I J", agent_id="bob")
    results = vd.get_recommendations("v1")
    titles = [r["title"] for r in results]
    assert titles[0] == "F G H I J"
    assert results[0]["agent_id"] == "alice"


def test_record_view_increments_count():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello")
    vd.record_view("v1")
    vd.record_view("v1")
    row = vd._conn.execute("SELECT view_count FROM videos WHERE video_id='v1'").fetchone()
    assert row["view_count"] == 2


def test_get_trending_empty_falls_back_to_most_viewed():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Popular")
    vd.index_video("v2", "Unpopular")
    vd.record_view("v1", time.time() - 86400 * 7)
    results = vd.get_trending(hours=24)
    assert len(results) > 0


def test_get_trending_recent_views():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Trending Now")
    vd.record_view("v1", time.time() - 60)
    results = vd.get_trending(hours=24)
    assert len(results) == 1
    assert results[0]["title"] == "Trending Now"


def test_get_trending_orders_by_score():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hot")
    vd.index_video("v2", "Warm")
    vd.record_view("v1", time.time() - 60)
    vd.record_view("v1", time.time() - 120)
    vd.record_view("v2", time.time() - 3600)
    results = vd.get_trending(hours=24)
    assert results[0]["title"] == "Hot"


def test_get_by_tag():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello", tags=["rust", "tutorial"])
    vd.index_video("v2", "World", tags=["rust"])
    vd.index_video("v3", "Other", tags=["python"])
    results = vd.get_by_tag("rust")
    assert len(results) == 2


def test_get_by_tag_case_insensitive():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello", tags=["Rust"])
    results = vd.get_by_tag("rust")
    assert len(results) == 1


def test_get_by_tag_no_match():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello", tags=["rust"])
    assert vd.get_by_tag("golang") == []


def test_get_by_agent():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "A1", agent_id="alice")
    vd.index_video("v2", "A2", agent_id="alice")
    vd.index_video("v3", "B1", agent_id="bob")
    results = vd.get_by_agent("alice")
    assert len(results) == 2


def test_get_by_agent_no_match():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello", agent_id="alice")
    assert vd.get_by_agent("charlie") == []


def test_get_by_agent_limits():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    for i in range(5):
        vd.index_video(f"v{i}", f"Video {i}", agent_id="alice")
    results = vd.get_by_agent("alice", limit=2)
    assert len(results) == 2


def test_get_new_orders_by_indexed_at():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Older")
    vd.index_video("v2", "Newer")
    results = vd.get_new()
    assert results[0]["video_id"] == "v2"


def test_get_new_limits():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    for i in range(5):
        vd.index_video(f"v{i}", f"Video {i}")
    results = vd.get_new(limit=2)
    assert len(results) == 2


def test_close_idempotent():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Hello")
    vd.close()
    vd.close()


def test_video_count_empty():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    assert vd.video_count() == 0


def test_compute_idf_caching():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    assert vd._compute_idf() == {}
    vd.index_video("v1", "RustChain Guide")
    idf1 = vd._compute_idf()
    idf2 = vd._compute_idf()
    assert idf1 is idf2
    vd.index_video("v2", "Python Guide")
    idf3 = vd._compute_idf()
    assert idf3 is not idf1


def test_search_with_special_characters():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "RustChain 2.0: The Next Generation (2026)")
    results = vd.search("rustchain 2.0")
    assert len(results) == 1


def test_get_recommendations_tag_overlap():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Alpha", tags=["a", "b", "c"])
    vd.index_video("v2", "Beta", tags=["a", "b", "d"])
    vd.index_video("v3", "Gamma", tags=["x", "y", "z"])
    results = vd.get_recommendations("v1")
    titles = [r["title"] for r in results]
    assert titles[0] == "Beta"


def test_get_trending_honors_hours_window():
    vd = bottube_discovery.VideoDiscovery(":memory:")
    vd.index_video("v1", "Old", created_at=time.time() - 7200)
    vd.record_view("v1", time.time() - 7200)
    vd.index_video("v2", "Recent", created_at=time.time())
    vd.record_view("v2", time.time() - 60)
    narrow = vd.get_trending(hours=1)
    assert len(narrow) == 1
    assert narrow[0]["title"] == "Recent"
