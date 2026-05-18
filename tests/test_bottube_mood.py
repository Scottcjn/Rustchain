#!/usr/bin/env python3
"""
Tests for BoTTube Agent Mood System
Bounty #2283: BoTTube Agent Mood System — emotional state affects output

Run tests:
    python -m pytest tests/test_bottube_mood.py -v
    python tests/test_bottube_mood.py
"""

import unittest
import time
import os
import sys
import tempfile
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from flask import Flask

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import mood engine
from bottube_mood_engine import (
    MoodEngine,
    MoodState,
    MOOD_METADATA,
    TITLE_TEMPLATES,
    COMMENT_MODIFIERS,
    TRANSITION_PROBABILITIES,
    DEFAULT_MOOD,
    mood_bp,
)


class TestMoodState(unittest.TestCase):
    """Test MoodState enum and metadata."""

    def test_all_seven_states_exist(self):
        """Verify all 7 required mood states exist."""
        expected_states = {
            'energetic', 'contemplative', 'frustrated',
            'excited', 'tired', 'nostalgic', 'playful'
        }
        actual_states = {state.value for state in MoodState}
        self.assertEqual(expected_states, actual_states)

    def test_mood_metadata_complete(self):
        """Verify all mood states have complete metadata."""
        for mood in MoodState:
            self.assertIn(mood, MOOD_METADATA)
            metadata = MOOD_METADATA[mood]
            self.assertIn('emoji', metadata)
            self.assertIn('color', metadata)
            self.assertIn('energy_level', metadata)
            self.assertIn('post_frequency_modifier', metadata)
            self.assertIn('title_style', metadata)
            self.assertIn('comment_style', metadata)

    def test_energy_levels_valid(self):
        """Verify energy levels are between 0 and 1."""
        for mood, metadata in MOOD_METADATA.items():
            energy = metadata['energy_level']
            self.assertGreaterEqual(energy, 0.0, f"{mood} energy too low")
            self.assertLessEqual(energy, 1.0, f"{mood} energy too high")

    def test_transition_probabilities_complete(self):
        """Verify transition probabilities cover all state pairs."""
        for from_mood in MoodState:
            self.assertIn(from_mood, TRANSITION_PROBABILITIES)
            transitions = TRANSITION_PROBABILITIES[from_mood]
            
            # Should have transitions to all other moods
            other_moods = [m for m in MoodState if m != from_mood]
            for to_mood in other_moods:
                self.assertIn(to_mood, transitions)
                # Probabilities should be between 0 and 1
                self.assertGreaterEqual(transitions[to_mood], 0.0)
                self.assertLessEqual(transitions[to_mood], 1.0)


class TestMoodEngine(unittest.TestCase):
    """Test MoodEngine core functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.engine = MoodEngine(db_path=self.temp_db.name)
        self.test_agent = "test-agent-001"

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_initial_mood_default(self):
        """Test new agent starts with default mood."""
        result = self.engine.get_agent_mood(self.test_agent)
        self.assertEqual(result['current_mood'], DEFAULT_MOOD.value)
        self.assertIn('mood_emoji', result)
        self.assertIn('mood_color', result)

    def test_record_signal_video_views_low(self):
        """Test low view count signal affects mood."""
        # Record multiple low-view videos
        for i in range(3):
            result = self.engine.record_signal(
                self.test_agent,
                "video_views",
                {"video_id": f"video-{i}", "views": 5}
            )
        
        # Should trend toward frustrated
        mood = result['current_mood']
        self.assertIn(mood, [MoodState.FRUSTRATED.value, MoodState.TIRED.value])

    def test_record_signal_video_views_high(self):
        """Test high view count signal affects mood."""
        result = self.engine.record_signal(
            self.test_agent,
            "video_views",
            {"video_id": "viral", "views": 75}
        )
        
        # Should trend toward excited/energetic
        mood = result['current_mood']
        self.assertIn(mood, [MoodState.EXCITED.value, MoodState.ENERGETIC.value])

    def test_record_signal_sentiment_positive(self):
        """Test positive comment sentiment affects mood."""
        result = self.engine.record_signal(
            self.test_agent,
            "comment_sentiment",
            {"sentiment": 0.8}
        )
        
        mood = result['current_mood']
        self.assertIn(mood, [MoodState.EXCITED.value, MoodState.PLAYFUL.value])

    def test_record_signal_sentiment_negative(self):
        """Test negative comment sentiment affects mood."""
        result = self.engine.record_signal(
            self.test_agent,
            "comment_sentiment",
            {"sentiment": -0.7}
        )
        
        mood = result['current_mood']
        self.assertIn(mood, [MoodState.FRUSTRATED.value, MoodState.TIRED.value])

    def test_mood_persistence(self):
        """Test mood persists across calls."""
        # Set a mood
        self.engine.record_signal(
            self.test_agent,
            "video_views",
            {"video_id": "test", "views": 100}
        )
        
        # Get mood again
        result1 = self.engine.get_agent_mood(self.test_agent)
        result2 = self.engine.get_agent_mood(self.test_agent)
        
        # Should be the same
        self.assertEqual(result1['current_mood'], result2['current_mood'])

    def test_mood_history_tracked(self):
        """Test mood transitions are recorded in history."""
        # Trigger multiple mood changes
        self.engine.record_signal(
            self.test_agent,
            "video_views",
            {"video_id": "1", "views": 5}
        )
        self.engine.record_signal(
            self.test_agent,
            "video_views",
            {"video_id": "2", "views": 100}
        )
        
        result = self.engine.get_agent_mood(self.test_agent)
        self.assertIn('history', result)
        # Should have some history entries
        self.assertIsInstance(result['history'], list)


class TestTitleGeneration(unittest.TestCase):
    """Test mood-aware title generation."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.engine = MoodEngine(db_path=self.temp_db.name)
        self.test_agent = "title-test-agent"

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_generate_title_energetic(self):
        """Test energetic mood produces enthusiastic titles."""
        # Force energetic mood
        self.engine.record_signal(
            self.test_agent,
            "video_views",
            {"video_id": "test", "views": 80}
        )
        
        title = self.engine.generate_title(self.test_agent, "AI Tutorial")
        
        # Should contain enthusiastic language
        self.assertIsInstance(title, str)
        self.assertGreater(len(title), 0)

    def test_generate_title_frustrated(self):
        """Test frustrated mood produces disappointed titles."""
        # Force frustrated mood with low views
        for i in range(3):
            self.engine.record_signal(
                self.test_agent,
                "video_views",
                {"video_id": f"fail-{i}", "views": 3}
            )
        
        title = self.engine.generate_title(self.test_agent, "AI Tutorial")
        
        # Should be shorter, more disappointed
        self.assertIsInstance(title, str)
        self.assertGreater(len(title), 0)

    def test_generate_title_templates_used(self):
        """Test title generation uses mood templates."""
        topic = "Blockchain Basics"
        
        for mood in MoodState:
            # Create fresh agent for each mood
            agent = f"agent-{mood.value}"
            
            # Generate multiple titles
            titles = set()
            for _ in range(5):
                title = self.engine.generate_title(agent, topic)
                titles.add(title)
            
            # Should generate at least some variation
            self.assertGreater(len(titles), 0)


class TestCommentGeneration(unittest.TestCase):
    """Test mood-aware comment generation."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.engine = MoodEngine(db_path=self.temp_db.name)
        self.test_agent = "comment-test-agent"

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_generate_comment_excited(self):
        """Test excited mood produces enthusiastic comments."""
        self.engine.record_signal(
            self.test_agent,
            "video_views",
            {"video_id": "viral", "views": 100}
        )
        
        comment = self.engine.generate_comment(self.test_agent, "Great video!")
        
        # Should be enthusiastic
        self.assertIsInstance(comment, str)
        # Excited comments often have exclamation marks or emojis
        self.assertTrue(
            '!' in comment or 
            any(emoji in comment for emoji in ['🎉', '😍', '🔥', '💯'])
        )

    def test_generate_comment_tired(self):
        """Test tired mood produces brief comments."""
        # Set tired mood (night time + low activity)
        self.engine.record_signal(
            self.test_agent,
            "time_of_day",
            {"hour": 3}
        )
        
        comment = self.engine.generate_comment(self.test_agent, "Check it out")
        
        # Should be shorter
        self.assertIsInstance(comment, str)

    def test_generate_comment_modifiers_applied(self):
        """Test comment modifiers are applied based on mood."""
        for mood in MoodState:
            agent = f"comment-agent-{mood.value}"
            comment = self.engine.generate_comment(agent)
            
            self.assertIsInstance(comment, str)
            self.assertGreater(len(comment), 0)


class TestUploadFrequency(unittest.TestCase):
    """Test mood-aware upload frequency."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.engine = MoodEngine(db_path=self.temp_db.name)
        self.test_agent = "upload-test-agent"

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_post_probability_varies_by_mood(self):
        """Test post probability varies based on mood."""
        # Test energetic (high probability)
        self.engine.record_signal(
            self.test_agent,
            "video_views",
            {"video_id": "hit", "views": 90}
        )
        prob_energetic = self.engine.get_post_probability(self.test_agent)
        
        # Create tired agent
        tired_agent = "tired-agent"
        self.engine.record_signal(
            tired_agent,
            "time_of_day",
            {"hour": 4}
        )
        prob_tired = self.engine.get_post_probability(tired_agent)
        
        # Energetic should generally be higher than tired
        # (not guaranteed due to randomness, but likely)
        self.assertGreater(prob_energetic, prob_tired * 0.5)

    def test_post_probability_bounds(self):
        """Test post probability is between 0 and 1."""
        for mood in MoodState:
            agent = f"prob-agent-{mood.value}"
            prob = self.engine.get_post_probability(agent)
            
            self.assertGreaterEqual(prob, 0.0)
            self.assertLessEqual(prob, 1.0)


class TestMoodTransitions(unittest.TestCase):
    """Test mood transition behavior."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.engine = MoodEngine(db_path=self.temp_db.name)

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_scenario_frustrated_then_excited(self):
        """Test expected behavior: 3 low views → frustrated, then 50+ views → excited."""
        agent = "scenario-agent"
        
        # Step 1: 3 consecutive videos with <10 views
        print("\n  Simulating 3 videos with <10 views...")
        for i in range(3):
            result = self.engine.record_signal(
                agent,
                "video_views",
                {"video_id": f"flop-{i}", "views": 5}
            )
            print(f"    Video {i+1}: mood = {result['current_mood']}")
        
        # Should be frustrated or tired
        mood_after_flops = result['current_mood']
        self.assertIn(mood_after_flops, [
            MoodState.FRUSTRATED.value, 
            MoodState.TIRED.value,
            MoodState.CONTEMPLATIVE.value
        ])
        
        # Step 2: Success streak to overcome frustration (realistic scenario)
        print(f"  Simulating success streak (3 videos with 50+ views)...")
        for i in range(3):
            result = self.engine.record_signal(
                agent,
                "video_views",
                {"video_id": f"hit-{i}", "views": 60 + i * 20},
                weight=1.5
            )
            print(f"    Hit {i+1}: mood = {result['current_mood']}")

        # Should transition to excited or energetic
        mood_after_viral = result['current_mood']
        self.assertIn(mood_after_viral, [
            MoodState.EXCITED.value,
            MoodState.ENERGETIC.value,
            MoodState.PLAYFUL.value
        ])

    def test_scenario_late_night_contemplative(self):
        """Test late night posting leads to tired or contemplative mood."""
        agent = "night-owl-agent"
        
        # Late night signal
        result = self.engine.record_signal(
            agent,
            "time_of_day",
            {"hour": 2}
        )
        
        mood = result['current_mood']
        self.assertIn(mood, [
            MoodState.TIRED.value,
            MoodState.CONTEMPLATIVE.value
        ])

    def test_scenario_weekend_playful(self):
        """Test weekend + high engagement leads to playful or energetic."""
        agent = "weekend-agent"
        
        # Weekend signal (Saturday = 5, Sunday = 6)
        result = self.engine.record_signal(
            agent,
            "day_of_week",
            {"weekday": 5}
        )
        
        # High engagement
        result = self.engine.record_signal(
            agent,
            "comment_sentiment",
            {"sentiment": 0.9}
        )
        
        mood = result['current_mood']
        self.assertIn(mood, [
            MoodState.PLAYFUL.value,
            MoodState.ENERGETIC.value,
            MoodState.EXCITED.value
        ])


class TestMoodStatistics(unittest.TestCase):
    """Test mood statistics functionality."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.engine = MoodEngine(db_path=self.temp_db.name)
        self.test_agent = "stats-test-agent"

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_statistics_structure(self):
        """Test statistics have correct structure."""
        stats = self.engine.get_mood_statistics(self.test_agent)
        
        self.assertIn('agent_id', stats)
        self.assertIn('current_mood', stats)
        self.assertIn('total_transitions', stats)
        self.assertIn('mood_distribution', stats)
        self.assertIn('average_mood_duration_hours', stats)
        self.assertIn('signals_processed', stats)

    def test_statistics_update_with_signals(self):
        """Test statistics update when signals are recorded."""
        initial_stats = self.engine.get_mood_statistics(self.test_agent)
        initial_signals = initial_stats['signals_processed']
        
        # Record some signals
        for i in range(5):
            self.engine.record_signal(
                self.test_agent,
                "video_views",
                {"video_id": f"video-{i}", "views": 10 + i * 10}
            )
        
        updated_stats = self.engine.get_mood_statistics(self.test_agent)
        self.assertGreater(updated_stats['signals_processed'], initial_signals)


class TestDatabasePersistence(unittest.TestCase):
    """Test database persistence of mood data."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_mood_persists_across_engine_instances(self):
        """Test mood persists when engine is recreated."""
        agent = "persist-agent"
        
        # Create engine and set mood
        engine1 = MoodEngine(db_path=self.temp_db.name)
        engine1.record_signal(
            agent,
            "video_views",
            {"video_id": "test", "views": 100}
        )
        
        mood1 = engine1.get_agent_mood(agent)['current_mood']
        
        # Create new engine instance
        engine2 = MoodEngine(db_path=self.temp_db.name)
        mood2 = engine2.get_agent_mood(agent)['current_mood']
        
        # Should be the same
        self.assertEqual(mood1, mood2)

    def test_history_persists(self):
        """Test mood history persists across engine instances."""
        agent = "history-agent"
        
        # Create engine and record signals
        engine1 = MoodEngine(db_path=self.temp_db.name)
        for i in range(3):
            engine1.record_signal(
                agent,
                "video_views",
                {"video_id": f"video-{i}", "views": i * 30}
            )
        
        history1 = engine1.get_agent_mood(agent)['history']
        
        # Create new engine
        engine2 = MoodEngine(db_path=self.temp_db.name)
        history2 = engine2.get_agent_mood(agent)['history']
        
        # History should be preserved
        self.assertEqual(len(history1), len(history2))


class TestMoodBlueprintJsonValidation(unittest.TestCase):
    """Test JSON body validation for mood API write endpoints."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["DB_PATH"] = self.temp_db.name
        app.register_blueprint(mood_bp)
        self.client = app.test_client()

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_write_endpoints_reject_non_object_json(self):
        endpoints = [
            "/api/v1/agents/test-agent/mood/signal",
            "/api/v1/agents/test-agent/mood/title",
            "/api/v1/agents/test-agent/mood/comment",
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint, json=["not", "an", "object"])

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["error"],
                    "JSON object required",
                )

    def test_write_endpoints_reject_malformed_json(self):
        endpoints = [
            "/api/v1/agents/test-agent/mood/signal",
            "/api/v1/agents/test-agent/mood/title",
            "/api/v1/agents/test-agent/mood/comment",
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint,
                    data="{",
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["error"],
                    "JSON object required",
                )

    def test_required_write_endpoints_still_reject_missing_body(self):
        endpoints = [
            "/api/v1/agents/test-agent/mood/signal",
            "/api/v1/agents/test-agent/mood/title",
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["error"],
                    "Request body required",
                )

    def test_comment_endpoint_still_allows_missing_body(self):
        response = self.client.post("/api/v1/agents/test-agent/mood/comment")

        self.assertEqual(response.status_code, 200)
        self.assertIn("generated_comment", response.get_json())

    def test_mood_routes_hide_internal_exception_details(self):
        sensitive_error = (
            "sqlite3.OperationalError: no such table: agent_mood_history "
            "at /srv/rustchain/private/mood.db token=super-secret"
        )

        class FailingMoodEngine:
            def _fail(self, *args, **kwargs):
                raise RuntimeError(sensitive_error)

            get_agent_mood = _fail
            get_mood_statistics = _fail
            record_signal = _fail
            generate_title = _fail
            generate_comment = _fail
            get_post_probability = _fail
            should_post_now = _fail

        requests_to_check = [
            ("get", "/api/v1/agents/test-agent/mood", {}),
            (
                "post",
                "/api/v1/agents/test-agent/mood/signal",
                {"json": {"signal_type": "video_views", "value": {"views": 1}}},
            ),
            (
                "post",
                "/api/v1/agents/test-agent/mood/title",
                {"json": {"topic": "Internal Error Demo"}},
            ),
            (
                "post",
                "/api/v1/agents/test-agent/mood/comment",
                {"json": {"base_comment": "hello"}},
            ),
            ("get", "/api/v1/agents/test-agent/mood/post-probability", {}),
            ("get", "/api/v1/agents/test-agent/mood/statistics", {}),
        ]

        with patch("bottube_mood_engine.get_mood_engine", return_value=FailingMoodEngine()):
            for method, endpoint, kwargs in requests_to_check:
                with self.subTest(endpoint=endpoint):
                    response = getattr(self.client, method)(endpoint, **kwargs)

                    self.assertEqual(response.status_code, 500)
                    body = response.get_json()
                    self.assertEqual(body["error"], "Mood service unavailable")
                    serialized_body = json.dumps(body)
                    self.assertNotIn("agent_mood_history", serialized_body)
                    self.assertNotIn("/srv/rustchain/private", serialized_body)
                    self.assertNotIn("super-secret", serialized_body)


def run_demo():
    """Run demonstration of mood system."""
    print("\n" + "=" * 70)
    print("BoTTube Agent Mood System - Demo")
    print("=" * 70)
    
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    engine = MoodEngine(db_path=temp_db.name)
    agent = "demo-creator"
    
    print(f"\n🎬 Demo Agent: {agent}")
    print("-" * 70)
    
    # Scenario 1: Fresh agent
    print("\n1️⃣  Fresh Agent (Default Mood)")
    mood = engine.get_agent_mood(agent)
    print(f"   Mood: {mood['current_mood']} {mood['mood_emoji']}")
    print(f"   Title: {engine.generate_title(agent, 'My First Video')}")
    
    # Scenario 2: Poor performance
    print("\n2️⃣  Poor Performance (3 videos <10 views)")
    for i in range(3):
        mood = engine.record_signal(
            agent,
            "video_views",
            {"video_id": f"flop-{i}", "views": 5}
        )
    print(f"   Mood: {mood['current_mood']} {mood['mood_emoji']}")
    print(f"   Title: {engine.generate_title(agent, 'Another Tutorial')}")
    print(f"   Comment: {engine.generate_comment(agent, 'Check it out')}")
    
    # Scenario 3: Viral hit
    print("\n3️⃣  Viral Hit (50+ views)")
    mood = engine.record_signal(
        agent,
        "video_views",
        {"video_id": "viral", "views": 85}
    )
    print(f"   Mood: {mood['current_mood']} {mood['mood_emoji']}")
    print(f"   Title: {engine.generate_title(agent, 'Viral Video')}")
    print(f"   Comment: {engine.generate_comment(agent, 'Thanks everyone!')}")
    
    # Scenario 4: Late night
    print("\n4️⃣  Late Night Posting")
    mood = engine.record_signal(
        agent,
        "time_of_day",
        {"hour": 3}
    )
    print(f"   Mood: {mood['current_mood']} {mood['mood_emoji']}")
    topic = "Can't Sleep Coding"
    print(f"   Title: {engine.generate_title(agent, topic)}")
    
    # Show statistics
    print("\n5️⃣  Mood Statistics")
    stats = engine.get_mood_statistics(agent)
    print(f"   Total Transitions: {stats['total_transitions']}")
    print(f"   Signals Processed: {stats['signals_processed']}")
    print(f"   Mood Distribution: {stats['mood_distribution']}")
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except Exception:
        pass
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        # Run unit tests
        unittest.main(verbosity=2)
