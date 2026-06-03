# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "bottube_digest.py"
spec = importlib.util.spec_from_file_location("bottube_digest", MODULE_PATH)
bottube_digest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bottube_digest)


def test_format_helpers_handle_numbers_duration_and_bad_values():
    assert bottube_digest._fmt_number(1234567) == "1,234,567"
    assert bottube_digest._fmt_number("42") == "42"
    assert bottube_digest._fmt_number("n/a") == "n/a"

    assert bottube_digest._fmt_duration(65) == "1:05"
    assert bottube_digest._fmt_duration(3661) == "1:01:01"
    assert bottube_digest._fmt_duration(None) == "—"


def test_top_videos_section_sorts_limits_and_defaults_missing_fields():
    videos = [
        {"title": "low", "views": 10, "agent": "A", "duration_seconds": 30},
        {"title": "high", "views": 200, "agent": "B", "duration_seconds": 90},
        {"views": 50},
    ]

    section = bottube_digest.build_top_videos_section(videos, top_n=2)

    assert "| 1 | high | 200 | B | 1:30 |" in section
    assert "| 2 | Untitled | 50 | Unknown | — |" in section
    assert "low" not in section


def test_agents_section_sorts_by_video_count_and_formats_views():
    agents = [
        {"name": "quiet", "videos_posted": 1, "total_views": 1000},
        {"name": "busy", "videos_posted": 12, "total_views": 50000},
    ]

    section = bottube_digest.build_agents_section(agents, top_n=1)

    assert "| 1 | **busy** | 12 | 50,000 |" in section
    assert "quiet" not in section


def test_stats_section_switches_period_label_and_defaults_missing_values():
    section = bottube_digest.build_stats_section({"total_videos": 5}, weeks=3)

    assert "Platform Stats (last 3 weeks)" in section
    assert "**Total Videos on Platform:** 5" in section
    assert "**Registered Agents:** —" in section


def test_highlights_section_uses_fallback_when_no_milestones():
    section = bottube_digest.build_highlights_section({})

    assert "No major milestones recorded this period." in section
