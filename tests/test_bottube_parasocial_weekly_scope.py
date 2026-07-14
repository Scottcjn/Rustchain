#!/usr/bin/env python3
"""Regression test: weekly shoutouts must be scoped to their own week.

Bounty #2286 follow-up. `_update_weekly_stats` used to derive each week's
`top_commenters` / `most_active_video` from the tracker's ALL-TIME
`video_comments`, so every week collapsed onto the same all-time leaders and
the "top commenters this week" shoutout was meaningless. These tests fail on
the pre-fix code and pass once the tallies are scoped per week.

Run:
    python3 -m pytest tests/test_bottube_parasocial_weekly_scope.py -v
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

PARASOCIAL_DIR = Path(__file__).parent.parent / "integrations" / "bottube_parasocial"
sys.path.insert(0, str(PARASOCIAL_DIR))

from audience_tracker import AudienceTracker  # noqa: E402

# Two distinct ISO weeks (both Mondays).
WEEK1 = "2025-01-06T10:00:00"   # week starting 2025-01-06
WEEK2 = "2025-01-13T10:00:00"   # week starting 2025-01-13


class TestWeeklyStatsScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tracker = AudienceTracker(agent_id="agent1", state_dir=Path(self.tmp))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_top_commenters_scoped_to_week(self):
        # Week 1: alice comments a lot on vid1.
        for i in range(5):
            self.tracker.add_comment("vid1", "alice", f"nice {i}", timestamp=WEEK1)

        # Week 2: only bob comments (once, on vid2). alice is silent this week.
        self.tracker.add_comment("vid2", "bob", "hello", timestamp=WEEK2)

        w1 = self.tracker.weekly_stats["2025-01-06"]
        w2 = self.tracker.weekly_stats["2025-01-13"]

        # Week 1's leader is alice; week 2's leader is bob — NOT the all-time
        # leader alice (that was the bug).
        self.assertEqual(w1.top_commenters, ["alice"])
        self.assertEqual(w2.top_commenters, ["bob"])
        self.assertNotIn("alice", w2.top_commenters)

    def test_most_active_video_scoped_to_week(self):
        for i in range(5):
            self.tracker.add_comment("vid1", "alice", f"nice {i}", timestamp=WEEK1)
        self.tracker.add_comment("vid2", "bob", "hello", timestamp=WEEK2)

        w2 = self.tracker.weekly_stats["2025-01-13"]
        # vid2 is the only video active in week 2, even though vid1 has more
        # all-time comments.
        self.assertEqual(w2.most_active_video, "vid2")

    def test_weekly_counts_persist_round_trip(self):
        for i in range(3):
            self.tracker.add_comment("vid1", "alice", f"c{i}", timestamp=WEEK1)
        self.tracker._save_state()

        reloaded = AudienceTracker(agent_id="agent1", state_dir=Path(self.tmp))
        w1 = reloaded.weekly_stats["2025-01-06"]
        self.assertEqual(w1.commenter_counts.get("alice"), 3)
        self.assertEqual(w1.top_commenters, ["alice"])


if __name__ == "__main__":
    unittest.main()
