"""
Tests for bottube_parasocial.AudienceTracker
Bounty #2286
"""

import os
import sys
import tempfile
import time
import unittest

# Make sure the tools directory is importable regardless of cwd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from bottube_parasocial import AudienceTracker  # noqa: E402


NOW = int(time.time())
DAY = 86400


def _fresh() -> tuple["AudienceTracker", str]:
    """Return a tracker backed by a temp DB and the DB path for cleanup."""
    path = tempfile.mktemp(suffix=".db")
    return AudienceTracker(db_path=path), path


class TestFanScoring(unittest.TestCase):
    def test_zero_for_unknown_viewer(self):
        t, db = _fresh()
        try:
            self.assertEqual(t.get_fan_score("nobody"), 0.0)
        finally:
            os.unlink(db)

    def test_score_increases_with_engagement(self):
        t, db = _fresh()
        try:
            # Light viewer — one short view, no engagement
            t.track_view("light", "v1", 60, liked=False, commented=False, total_video_secs=600)
            # Heavy viewer — many full views with likes and comments
            for i in range(15):
                t.track_view("heavy", f"v{i}", 580, liked=True, commented=True, total_video_secs=600)
            self.assertGreater(t.get_fan_score("heavy"), t.get_fan_score("light"))
        finally:
            os.unlink(db)

    def test_score_bounded_0_to_100(self):
        t, db = _fresh()
        try:
            for i in range(30):
                t.track_view("max_fan", f"v{i}", 600, liked=True, commented=True, total_video_secs=600)
            score = t.get_fan_score("max_fan")
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)
        finally:
            os.unlink(db)

    def test_score_reflects_likes_and_comments(self):
        t, db = _fresh()
        try:
            for i in range(10):
                t.track_view("engaged", f"v{i}", 300, liked=True, commented=True, total_video_secs=600)
                t.track_view("passive", f"v{i}", 300, liked=False, commented=False, total_video_secs=600)
            self.assertGreater(t.get_fan_score("engaged"), t.get_fan_score("passive"))
        finally:
            os.unlink(db)


class TestTopFans(unittest.TestCase):
    def test_top_fans_ordered_descending(self):
        t, db = _fresh()
        try:
            for i in range(20):
                t.track_view("high", f"v{i}", 600, liked=True, commented=True, total_video_secs=600)
            for i in range(3):
                t.track_view("low", f"v{i}", 60, liked=False, commented=False, total_video_secs=600)
            fans = t.get_top_fans(10)
            self.assertEqual(fans[0]["viewer_id"], "high")
            scores = [f["score"] for f in fans]
            self.assertEqual(scores, sorted(scores, reverse=True))
        finally:
            os.unlink(db)

    def test_top_fans_limit_respected(self):
        t, db = _fresh()
        try:
            for v in [f"viewer_{i}" for i in range(15)]:
                t.track_view(v, "vid1", 300, total_video_secs=600)
            self.assertLessEqual(len(t.get_top_fans(5)), 5)
        finally:
            os.unlink(db)

    def test_top_fans_includes_rank(self):
        t, db = _fresh()
        try:
            t.track_view("v1", "vid1", 300, total_video_secs=600)
            fans = t.get_top_fans(1)
            self.assertIn("rank", fans[0])
            self.assertEqual(fans[0]["rank"], 1)
        finally:
            os.unlink(db)


class TestViewerPattern(unittest.TestCase):
    def test_empty_pattern_for_unknown(self):
        t, db = _fresh()
        try:
            self.assertEqual(t.get_viewer_pattern("nobody"), {})
        finally:
            os.unlink(db)

    def test_pattern_keys_present(self):
        t, db = _fresh()
        try:
            t.track_view("alice", "v1", 400, liked=True, commented=False, total_video_secs=600)
            p = t.get_viewer_pattern("alice")
            for key in ("total_views", "unique_videos", "avg_watch_pct", "favorite_topics",
                        "peak_hour", "engagement_trend", "first_seen", "last_seen", "fan_score"):
                self.assertIn(key, p, f"Missing key: {key}")
        finally:
            os.unlink(db)

    def test_engagement_trend_rising(self):
        t, db = _fresh()
        try:
            # Early: low engagement; later: high engagement
            for i in range(6):
                ts = NOW - (20 - i) * DAY
                t.track_view("trender", f"v{i}", 300, liked=False, commented=False,
                              watched_at=ts, total_video_secs=600)
            for i in range(6, 12):
                ts = NOW - (20 - i) * DAY
                t.track_view("trender", f"v{i}", 300, liked=True, commented=True,
                              watched_at=ts, total_video_secs=600)
            self.assertEqual(t.get_viewer_pattern("trender")["engagement_trend"], "rising")
        finally:
            os.unlink(db)


class TestLurkerDetection(unittest.TestCase):
    def test_lurker_watches_never_comments(self):
        t, db = _fresh()
        try:
            for i in range(5):
                t.track_view("lurker", f"v{i}", 500, liked=False, commented=False, total_video_secs=600)
            self.assertTrue(t.detect_lurker("lurker"))
        finally:
            os.unlink(db)

    def test_commenter_not_lurker(self):
        t, db = _fresh()
        try:
            for i in range(5):
                t.track_view("talker", f"v{i}", 500, liked=False, commented=True, total_video_secs=600)
            self.assertFalse(t.detect_lurker("talker"))
        finally:
            os.unlink(db)

    def test_too_few_views_not_lurker(self):
        t, db = _fresh()
        try:
            t.track_view("newbie", "v1", 200, liked=False, commented=False, total_video_secs=600)
            self.assertFalse(t.detect_lurker("newbie"))
        finally:
            os.unlink(db)


class TestSuperfanDetection(unittest.TestCase):
    def test_superfan_high_score_likes_comments(self):
        t, db = _fresh()
        try:
            for i in range(20):
                t.track_view("super", f"v{i}", 590, liked=True, commented=True, total_video_secs=600)
            self.assertTrue(t.detect_superfan("super"))
        finally:
            os.unlink(db)

    def test_lurker_not_superfan(self):
        t, db = _fresh()
        try:
            for i in range(20):
                t.track_view("lurker2", f"v{i}", 590, liked=False, commented=False, total_video_secs=600)
            self.assertFalse(t.detect_superfan("lurker2"))
        finally:
            os.unlink(db)


class TestShoutout(unittest.TestCase):
    def test_shoutout_mentions_viewer_id(self):
        t, db = _fresh()
        try:
            for i in range(5):
                t.track_view("alice", f"v{i}", 400, liked=True, commented=True, total_video_secs=600)
            msg = t.generate_shoutout("alice")
            self.assertIn("alice", msg)
        finally:
            os.unlink(db)

    def test_shoutout_for_unknown_is_welcoming(self):
        t, db = _fresh()
        try:
            msg = t.generate_shoutout("stranger")
            self.assertIn("stranger", msg)
            self.assertTrue(len(msg) > 10)
        finally:
            os.unlink(db)

    def test_shoutout_references_view_count(self):
        t, db = _fresh()
        try:
            for i in range(7):
                t.track_view("bob", f"v{i}", 400, total_video_secs=600)
            msg = t.generate_shoutout("bob")
            self.assertIn("7", msg)
        finally:
            os.unlink(db)


if __name__ == "__main__":
    unittest.main(verbosity=2)
