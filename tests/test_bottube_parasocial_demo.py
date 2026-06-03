from __future__ import annotations

import os
import runpy
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import bottube_parasocial_demo as demo


class RecordingAudienceTracker:
    instances: list["RecordingAudienceTracker"] = []

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.views: list[tuple] = []
        RecordingAudienceTracker.instances.append(self)

    def track_view(
        self,
        viewer_id: str,
        video_id: str,
        duration: float,
        liked: bool,
        commented: bool,
        *,
        watched_at: int,
        topic: str,
        total_video_secs: float,
    ) -> None:
        self.views.append(
            (
                viewer_id,
                video_id,
                duration,
                liked,
                commented,
                watched_at,
                topic,
                total_video_secs,
            )
        )

    def get_top_fans(self, limit: int) -> list[dict]:
        return [
            {"rank": 1, "viewer_id": "superfan_alice", "score": 98.5},
            {"rank": 2, "viewer_id": "superfan_bob", "score": 95.0},
        ][:limit]

    def detect_lurker(self, viewer_id: str) -> bool:
        return viewer_id.startswith("lurker_")

    def detect_superfan(self, viewer_id: str) -> bool:
        return viewer_id.startswith("superfan_")

    def generate_shoutout(self, viewer_id: str) -> str:
        return f"shoutout for {viewer_id}"

    def get_viewer_pattern(self, viewer_id: str) -> dict:
        return {"viewer_id": viewer_id, "total_views": 30, "favorite_topic": "coding"}


def test_simulate_records_deterministic_view_events() -> None:
    tracker = RecordingAudienceTracker(":memory:")

    demo.random.seed(42)
    demo.simulate(tracker)

    assert len(demo.VIEWERS) == 20
    assert len(demo.VIDEOS) == 30
    assert len(tracker.views) == 261
    first = tracker.views[0]
    last = tracker.views[-1]
    assert first[0] == "superfan_alice"
    assert first[1] == "vid_001"
    assert first[4] is False
    assert first[6] == "coding"
    assert first[7] == demo.VIDEO_DURATION
    assert last[0] == "cheerleader_paul"
    assert last[1] == "vid_030"
    assert last[6] == "gaming"


def test_script_main_prints_rankings_and_cleans_temp_db(monkeypatch, capsys) -> None:
    RecordingAudienceTracker.instances = []
    fake_module = types.SimpleNamespace(AudienceTracker=RecordingAudienceTracker)
    script_path = Path(__file__).resolve().parents[1] / "tools" / "bottube_parasocial_demo.py"
    temp_db = "/tmp/bottube_parasocial_demo_test.db"
    removed_paths: list[str] = []

    monkeypatch.setitem(sys.modules, "bottube_parasocial", fake_module)
    monkeypatch.setattr(tempfile, "mktemp", lambda suffix="": temp_db)
    monkeypatch.setattr(os, "unlink", removed_paths.append)

    runpy.run_path(str(script_path), run_name="__main__")

    assert len(RecordingAudienceTracker.instances) == 1
    tracker = RecordingAudienceTracker.instances[0]
    assert tracker.db_path == temp_db
    assert len(tracker.views) == 261
    assert removed_paths == [temp_db]

    output = capsys.readouterr().out
    assert "Simulating 20 viewers over 30 days" in output
    assert "TOP 10 FANS" in output
    assert "superfan_alice" in output
    assert "LURKERS & SUPERFANS" in output
    assert "lurker_eve" in output
    assert "SHOUTOUTS" in output
    assert "shoutout for ghost_kate" in output
    assert "VIEWER PATTERN" in output
    assert "favorite_topic" in output
