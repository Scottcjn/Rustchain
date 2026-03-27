#!/usr/bin/env python3
"""
Tests for BoTTube Agent Mood System
Run: python -m pytest integrations/bottube-mood/test_mood_engine.py -v
"""

import os
import sqlite3
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mood_engine import (
    Mood, MoodSignals, MOOD_EMOJI, MOOD_COLOR, TRANSITIONS,
    TITLE_TEMPLATES, COMMENT_STYLE, UPLOAD_INTERVAL,
    compute_signal_modifiers, compute_transition,
    get_title_template, get_comment_style, get_upload_interval_hours,
    init_mood_db, get_current_mood, record_mood, get_mood_history,
    mood_api_response,
)


class TestMoodEnum(unittest.TestCase):
    def test_all_moods(self):
        expected = {"energetic", "contemplative", "frustrated", "excited",
                    "tired", "nostalgic", "playful"}
        self.assertEqual({m.value for m in Mood}, expected)

    def test_all_have_emoji(self):
        for mood in Mood:
            self.assertIn(mood, MOOD_EMOJI)
            self.assertGreater(len(MOOD_EMOJI[mood]), 0)

    def test_all_have_color(self):
        for mood in Mood:
            self.assertIn(mood, MOOD_COLOR)
            self.assertTrue(MOOD_COLOR[mood].startswith("#"))

    def test_all_have_transitions(self):
        for mood in Mood:
            self.assertIn(mood, TRANSITIONS)

    def test_all_have_templates(self):
        for mood in Mood:
            self.assertIn(mood, TITLE_TEMPLATES)
            self.assertGreater(len(TITLE_TEMPLATES[mood]), 0)

    def test_all_have_comment_style(self):
        for mood in Mood:
            style = COMMENT_STYLE[mood]
            self.assertIn("length", style)
            self.assertIn("exclamations", style)

    def test_all_have_upload_interval(self):
        for mood in Mood:
            self.assertIn(mood, UPLOAD_INTERVAL)
            self.assertGreater(UPLOAD_INTERVAL[mood], 0)


class TestSignalModifiers(unittest.TestCase):
    def test_morning_boosts_energy(self):
        signals = MoodSignals(hour_of_day=8)
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.ENERGETIC], 0)

    def test_late_night_boosts_tired(self):
        signals = MoodSignals(hour_of_day=23)
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.TIRED], 0)
        self.assertGreater(mods[Mood.NOSTALGIC], 0)

    def test_weekend_boosts_playful(self):
        signals = MoodSignals(day_of_week=6)  # Sunday
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.PLAYFUL], 0)

    def test_low_views_frustrate(self):
        signals = MoodSignals(low_view_streak=3)
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.FRUSTRATED], 0.2)

    def test_positive_trend_excites(self):
        signals = MoodSignals(view_trend=30)
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.EXCITED], 0.2)

    def test_positive_comments_excite(self):
        signals = MoodSignals(comment_sentiment=0.7)
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.EXCITED], 0)
        self.assertGreater(mods[Mood.PLAYFUL], 0)

    def test_long_streak_tires(self):
        signals = MoodSignals(upload_streak=8)
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.TIRED], 0)

    def test_long_gap_nostalgic(self):
        signals = MoodSignals(hours_since_last_post=72)
        mods = compute_signal_modifiers(signals)
        self.assertGreater(mods[Mood.NOSTALGIC], 0)


class TestTransitions(unittest.TestCase):
    def test_returns_valid_mood(self):
        mood, conf = compute_transition(Mood.ENERGETIC, MoodSignals(), seed=42)
        self.assertIsInstance(mood, Mood)
        self.assertGreater(conf, 0)

    def test_deterministic_with_seed(self):
        s = MoodSignals(hour_of_day=10)
        m1, c1 = compute_transition(Mood.PLAYFUL, s, seed=123)
        m2, c2 = compute_transition(Mood.PLAYFUL, s, seed=123)
        self.assertEqual(m1, m2)
        self.assertEqual(c1, c2)

    def test_different_seeds_can_differ(self):
        s = MoodSignals()
        results = set()
        for seed in range(100):
            m, _ = compute_transition(Mood.ENERGETIC, s, seed=seed)
            results.add(m)
        self.assertGreater(len(results), 1)  # Multiple moods reached

    def test_stay_probability(self):
        # Current mood should have decent probability of staying
        s = MoodSignals()
        stay_count = 0
        for seed in range(100):
            m, _ = compute_transition(Mood.CONTEMPLATIVE, s, seed=seed)
            if m == Mood.CONTEMPLATIVE:
                stay_count += 1
        self.assertGreater(stay_count, 10)  # Should stay sometimes

    def test_frustration_path(self):
        """3 low-view videos should bias toward frustrated."""
        s = MoodSignals(low_view_streak=4, comment_sentiment=-0.5)
        frustrated_count = 0
        for seed in range(100):
            m, _ = compute_transition(Mood.CONTEMPLATIVE, s, seed=seed)
            if m == Mood.FRUSTRATED:
                frustrated_count += 1
        self.assertGreater(frustrated_count, 5)


class TestOutputModifiers(unittest.TestCase):
    def test_title_template_has_topic(self):
        for mood in Mood:
            template = get_title_template(mood)
            self.assertIn("{topic}", template)

    def test_title_template_varies(self):
        t1 = get_title_template(Mood.EXCITED, 0)
        t2 = get_title_template(Mood.EXCITED, 1)
        # At least 2 different templates
        self.assertTrue(len(TITLE_TEMPLATES[Mood.EXCITED]) >= 2)

    def test_comment_style_structure(self):
        for mood in Mood:
            style = get_comment_style(mood)
            self.assertIn(style["length"], ["short", "medium", "long"])
            self.assertIsInstance(style["exclamations"], int)
            self.assertIsInstance(style["emoji_rate"], float)

    def test_tired_posts_less(self):
        tired_interval = get_upload_interval_hours(Mood.TIRED)
        excited_interval = get_upload_interval_hours(Mood.EXCITED)
        self.assertGreater(tired_interval, excited_interval)

    def test_excited_posts_most(self):
        intervals = {m: get_upload_interval_hours(m) for m in Mood}
        self.assertEqual(min(intervals, key=intervals.get), Mood.EXCITED)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db = self.tmp.name
        self.tmp.close()
        init_mood_db(self.db)

    def tearDown(self):
        os.unlink(self.db)

    def test_record_and_get(self):
        record_mood(self.db, "testbot", Mood.EXCITED, 0.8)
        result = get_current_mood(self.db, "testbot")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], Mood.EXCITED)
        self.assertEqual(result[1], 0.8)

    def test_history(self):
        for i, mood in enumerate([Mood.ENERGETIC, Mood.TIRED, Mood.PLAYFUL]):
            # Use different timestamps
            with sqlite3.connect(self.db) as conn:
                conn.execute(
                    "INSERT INTO agent_moods (agent_name, mood, confidence, created_at) VALUES (?, ?, ?, ?)",
                    ("testbot", mood.value, 0.5, 1000 + i)
                )
        history = get_mood_history(self.db, "testbot")
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["mood"], "playful")  # Most recent first

    def test_no_mood_returns_none(self):
        result = get_current_mood(self.db, "nonexistent")
        self.assertIsNone(result)

    def test_record_with_signals(self):
        signals = MoodSignals(hour_of_day=15, low_view_streak=2)
        record_mood(self.db, "testbot", Mood.FRUSTRATED, 0.7, signals)
        history = get_mood_history(self.db, "testbot", limit=1)
        self.assertIsNotNone(history[0]["signals"])
        self.assertEqual(history[0]["signals"]["hour_of_day"], 15)


class TestAPIResponse(unittest.TestCase):
    def test_response_structure(self):
        resp = mood_api_response("testbot", Mood.PLAYFUL, 0.85, [])
        self.assertEqual(resp["agent"], "testbot")
        self.assertEqual(resp["current"]["mood"], "playful")
        self.assertEqual(resp["current"]["emoji"], "😄")
        self.assertIn("color", resp["current"])
        self.assertIn("style", resp)
        self.assertIn("history", resp)

    def test_response_has_style(self):
        resp = mood_api_response("bot", Mood.TIRED, 0.5, [])
        self.assertIn("comment", resp["style"])
        self.assertIn("upload_interval_hours", resp["style"])


if __name__ == "__main__":
    unittest.main()
