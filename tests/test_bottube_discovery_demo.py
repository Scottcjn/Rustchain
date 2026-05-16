from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import bottube_discovery_demo as demo


class FakeVideoDiscovery:
    instances: list["FakeVideoDiscovery"] = []

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.indexed: list[tuple] = []
        self.views: list[tuple] = []
        self.closed = False
        FakeVideoDiscovery.instances.append(self)

    def index_video(
        self,
        video_id: str,
        title: str,
        description: str,
        tags: list[str],
        agent_id: str,
        duration_s: int,
        created_at: float,
    ) -> None:
        self.indexed.append((video_id, title, description, tags, agent_id, duration_s, created_at))

    def record_view(self, video_id: str, *, viewed_at: float) -> None:
        self.views.append((video_id, viewed_at))

    def video_count(self) -> int:
        return len(self.indexed)

    def search(self, query: str, *, limit: int) -> list[dict]:
        assert query == "rust async performance"
        assert limit == 5
        return [{"video_id": "v026", "title": "Async Rust with Tokio"}]

    def get_recommendations(self, video_id: str, *, limit: int) -> list[dict]:
        assert video_id == "v005"
        assert limit == 5
        return [{"video_id": "v010", "title": "BoTTube Architecture Overview"}]

    def get_trending(self, *, hours: int, limit: int) -> list[dict]:
        assert hours == 24
        assert limit == 5
        return [{"video_id": "v050", "title": "BoTTube 2026 Roadmap", "view_count": 25}]

    def get_by_tag(self, tag: str, *, limit: int) -> list[dict]:
        assert tag == "blockchain"
        assert limit == 5
        return [{"video_id": "v002", "title": "Building a Blockchain in Python"}]

    def get_by_agent(self, agent_id: str, *, limit: int) -> list[dict]:
        assert agent_id == "agent_alpha"
        assert limit == 5
        return [{"video_id": "v001", "title": "Rust in 2026: What Changed?"}]

    def get_new(self, *, limit: int) -> list[dict]:
        assert limit == 5
        return [{"video_id": "v050", "title": "BoTTube 2026 Roadmap"}]

    def close(self) -> None:
        self.closed = True


def test_mock_video_catalog_has_expected_shape() -> None:
    assert len(demo.MOCK_VIDEOS) == 50
    first = demo.MOCK_VIDEOS[0]
    last = demo.MOCK_VIDEOS[-1]
    assert first == (
        "v001",
        "Rust in 2026: What Changed?",
        "A deep dive into Rust language evolution",
        ["rust", "programming", "systems"],
        "agent_alpha",
        720,
    )
    assert last[0] == "v050"
    assert last[3] == ["bottube", "roadmap", "community"]


def test_discovery_demo_indexes_videos_records_views_and_prints_sections(monkeypatch, capsys) -> None:
    FakeVideoDiscovery.instances = []
    monkeypatch.setattr(demo, "VideoDiscovery", FakeVideoDiscovery)

    demo.main()

    assert len(FakeVideoDiscovery.instances) == 1
    discovery = FakeVideoDiscovery.instances[0]
    assert discovery.db_path == ":memory:"
    assert len(discovery.indexed) == 50
    assert discovery.indexed[0][0] == "v001"
    assert discovery.indexed[-1][0] == "v050"
    assert all(discovery.indexed[i][6] < discovery.indexed[i + 1][6] for i in range(49))
    assert len(discovery.views) == 114
    view_counts = {video_id: 0 for video_id, _ in discovery.views}
    for video_id, _ in discovery.views:
        view_counts[video_id] += 1
    assert view_counts == {
        "v005": 12,
        "v010": 20,
        "v019": 8,
        "v035": 15,
        "v050": 25,
        "v039": 10,
        "v044": 18,
        "v002": 6,
    }
    assert discovery.closed is True

    output = capsys.readouterr().out
    assert "BoTTube Discovery Engine" in output
    assert "Indexed 50 videos" in output
    assert "Search: 'rust async performance'" in output
    assert "Recommendations for v005" in output
    assert "Trending (last 24h)" in output
    assert "Videos tagged 'blockchain'" in output
    assert "Videos by agent_alpha" in output
    assert "Newest videos" in output
    assert "[v026] Async Rust with Tokio" in output
    assert "[v050] BoTTube 2026 Roadmap" in output
    assert "Demo complete." in output
