import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import bottube_digest


def test_fmt_number_adds_commas_and_preserves_invalid_values():
    assert bottube_digest._fmt_number(1234567) == "1,234,567"
    assert bottube_digest._fmt_number("98765") == "98,765"
    assert bottube_digest._fmt_number(None) == "None"
    assert bottube_digest._fmt_number("not-a-number") == "not-a-number"


def test_fmt_duration_formats_minutes_hours_and_invalid_values():
    assert bottube_digest._fmt_duration(65) == "1:05"
    assert bottube_digest._fmt_duration(3661) == "1:01:01"
    assert bottube_digest._fmt_duration("742") == "12:22"
    assert bottube_digest._fmt_duration(None) == "—"


def test_build_top_videos_section_sorts_by_views_and_limits_results():
    videos = [
        {"title": "Low", "views": 10, "agent": "A", "duration_seconds": 30},
        {"title": "High", "views": 2000, "agent": "B", "duration_seconds": 90},
        {"title": "Mid", "views": 100, "agent": "C", "duration_seconds": 3600},
    ]

    section = bottube_digest.build_top_videos_section(videos, top_n=2)

    assert "| 1 | High | 2,000 | B | 1:30 |" in section
    assert "| 2 | Mid | 100 | C | 1:00:00 |" in section
    assert "Low" not in section


def test_build_agents_section_sorts_by_videos_posted():
    agents = [
        {"name": "Quiet", "videos_posted": 1, "total_views": 50},
        {"name": "Busy", "videos_posted": 12, "total_views": 12345},
    ]

    section = bottube_digest.build_agents_section(agents)

    assert section.index("Busy") < section.index("Quiet")
    assert "12" in section
    assert "12,345" in section


def test_fetch_platform_data_falls_back_per_endpoint(monkeypatch):
    responses = {
        "videos": {"videos": [{"title": "API video", "views": 1}]},
        "agents": None,
        "stats": {"total_videos": 9, "milestones": []},
    }

    def fake_fetch_json(url):
        if url.endswith("/api/videos?weeks=2"):
            return responses["videos"]
        if url.endswith("/api/agents?weeks=2"):
            return responses["agents"]
        if url.endswith("/api/stats?weeks=2"):
            return responses["stats"]
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(bottube_digest, "fetch_json", fake_fetch_json)

    data = bottube_digest.fetch_platform_data("https://example.test/", weeks=2)

    assert data["videos"] == responses["videos"]["videos"]
    assert data["agents"] == bottube_digest.MOCK_AGENTS
    assert data["stats"] == responses["stats"]
    assert data["using_mock"] == ["agents"]


def test_build_newsletter_mentions_mock_data_when_fallback_used(monkeypatch):
    class FixedDatetime(bottube_digest.datetime.datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 5, 12, 0, 0)

    monkeypatch.setattr(bottube_digest.datetime, "datetime", FixedDatetime)
    data = {
        "videos": [],
        "agents": [],
        "stats": {"milestones": []},
        "using_mock": ["videos", "stats"],
    }

    newsletter = bottube_digest.build_newsletter(data, weeks=1, base_url="https://example.test")

    assert "BoTTube Weekly Community Digest" in newsletter
    assert "May 05, 2026 → May 12, 2026" in newsletter
    assert "Mock data used for: videos, stats" in newsletter
    assert "https://example.test" in newsletter
